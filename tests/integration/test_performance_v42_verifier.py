"""Independent behavior and safety checks for bounded performance optimizations.

All synthetic endpoint observations are test fixtures, not hardware claims.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
import pytest
from hanni.compute.registry import ComputeError
from hanni.config.loader import load_config
from hanni.memory.retrieval import ContextAwareRetriever
from hanni.memory.store import MemoryStore
from hanni.models.adaptive import AdaptiveModelEngine
from hanni.models.performance import recent_performance, server_rates
from hanni.models.client import LlamaCppClient
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/v42_verification'))
from controlled_benchmark import endpoint, infer, scheduler

def await_waiting(service, count=1):
    deadline = time.monotonic() + 2
    while len(service.waiting) < count and time.monotonic() < deadline:
        time.sleep(0.001)
    assert len(service.waiting) >= count

def test_idle_independent_worker_finishes_before_older_busy_worker(tmp_path):
    with endpoint('controlled_A') as first, endpoint('controlled_B') as second:
        service = scheduler(tmp_path, [first, second])
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                occupied = pool.submit(infer, service, 'occupier', {'worker_0'})
                assert first['entered'].wait(2)
                older = pool.submit(infer, service, 'older_A', {'worker_0'})
                await_waiting(service)
                idle = pool.submit(infer, service, 'free_B', {'worker_1'}).result(2)
                assert idle['passed'] and idle['worker_id'] == 'worker_1'
                assert not occupied.done(), 'Free independent capacity should finish while A is still busy.'
                assert not older.done()
                assert occupied.result(3)['passed'] and older.result(3)['passed']
            assert not service.waiting and all((value == 0 for value in service.registry.active.values()))
        finally:
            service.close()

def test_queue_optimization_preserves_same_worker_fifo(tmp_path):
    with endpoint('controlled_A') as first:
        service = scheduler(tmp_path, [first])
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                occupied = pool.submit(infer, service, 'occupier')
                assert first['entered'].wait(2)
                older = pool.submit(infer, service, 'older')
                await_waiting(service)
                younger = pool.submit(infer, service, 'younger')
                await_waiting(service, 2)
                assert occupied.result(3)['passed']
                a, b = (older.result(3), younger.result(3))
                assert a['passed'] and b['passed']
                assert a['job']['started_at'] <= b['job']['started_at']
        finally:
            service.close()

def test_reserved_capacity_stays_available_to_interactive_user(tmp_path):
    with endpoint('controlled_A') as first:
        service = scheduler(tmp_path, [first], concurrency=2, reserve=1)
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                occupied = pool.submit(infer, service, 'occupier')
                assert first['entered'].wait(2)
                queued = pool.submit(infer, service, 'background')
                await_waiting(service)
                result = infer(service, 'interactive', interactive=True)
                assert result['passed'] and (not occupied.done()) and (not queued.done())
                assert occupied.result(3)['passed'] and queued.result(3)['passed']
        finally:
            service.close()

def test_eligibility_optimization_does_not_forward_private_context(tmp_path):
    with endpoint('controlled_A') as first, endpoint('controlled_B') as second:
        service = scheduler(tmp_path, [first, second])
        cancel = threading.Event()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(service.chat, [{'role': 'user', 'content': 'Synthetic private-memory canary'}], workflow_id='private', step_id='private', invocation_id='private', categories=['memory'], cancellation=cancel, max_tokens=32)
                await_waiting(service)
                assert all((value == 0 for value in service.registry.active.values()))
                cancel.set()
                with service.condition:
                    service.condition.notify_all()
                with pytest.raises(ComputeError):
                    future.result(2)
            assert not service.waiting and all((value == 0 for value in service.registry.active.values()))
            assert service.registry.jobs()[0]['state'] == 'CANCELLED'
        finally:
            service.close()

def test_cancelled_old_ticket_does_not_block_available_worker(tmp_path):
    with endpoint('controlled_A') as first, endpoint('controlled_B') as second:
        service = scheduler(tmp_path, [first, second])
        cancel = threading.Event()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                occupied = pool.submit(infer, service, 'occupier', {'worker_0'})
                assert first['entered'].wait(2)
                blocked = pool.submit(infer, service, 'blocked', {'worker_0'}, cancellation=cancel)
                await_waiting(service)
                cancel.set()
                with service.condition:
                    service.condition.notify_all()
                result = infer(service, 'free_after_cancel', {'worker_1'})
                assert result['passed'] and (not occupied.done())
                with pytest.raises(ComputeError):
                    blocked.result(2)
                assert occupied.result(3)['passed']
            assert not service.waiting
        finally:
            service.close()

def test_bounded_queue_refuses_excess_without_losing_existing_work(tmp_path):
    with endpoint('controlled_A') as first:
        service = scheduler(tmp_path, [first], max_queue=1)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                occupied = pool.submit(infer, service, 'occupier')
                assert first['entered'].wait(2)
                blocked = pool.submit(infer, service, 'queued')
                await_waiting(service)
                with pytest.raises(ComputeError, match='queue is full'):
                    infer(service, 'excess')
                assert occupied.result(3)['passed'] and blocked.result(3)['passed']
            assert not service.waiting and all((value == 0 for value in service.registry.active.values()))
        finally:
            service.close()

def test_profile_result_cannot_be_mutated_by_a_snapshot_consumer(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    engine = AdaptiveModelEngine(config)
    payload = {'correct': True, 'verified_success': True, 'latency_ms': 5, 'queue_ms': 0, 'generation_tps': None, 'prompt_tps': None, 'error': False, 'environment': 'synthetic independent', 'created_at': 1}
    try:
        db = engine._connect()
        db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('initial', 'local:supervisor', 'fixture', 'analysis', json.dumps(payload)))
        db.commit()
        original = engine._profiles('local:supervisor', 'fixture')
        original['analysis']['sample_count'] = 999
        original['analysis']['evaluation_environment'].append('consumer injection')
        current = engine._profiles('local:supervisor', 'fixture')
        assert current['analysis']['sample_count'] == 1 and current['analysis']['evaluation_environment'] == ['synthetic independent']
    finally:
        engine.close()

def test_profile_cache_cross_connection_and_same_connection_invalidation(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    engine = AdaptiveModelEngine(config)
    good = {'correct': True, 'verified_success': True, 'latency_ms': 5, 'queue_ms': 0, 'generation_tps': None, 'prompt_tps': None, 'error': False, 'environment': 'synthetic independent', 'created_at': 1}
    bad = dict(good, correct=False, verified_success=False, error=True)
    try:
        db = engine._connect()
        db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('one', 'local:supervisor', 'fixture', 'analysis', json.dumps(good)))
        db.commit()
        assert engine._profiles('local:supervisor', 'fixture')['analysis']['correct_count'] == 1
        db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('two', 'local:supervisor', 'fixture', 'analysis', json.dumps(bad)))
        db.commit()
        assert engine._profiles('local:supervisor', 'fixture')['analysis']['sample_count'] == 2
        with sqlite3.connect(tmp_path / 'model-routing/profiles.sqlite3') as outside:
            outside.execute('UPDATE measurements SET payload=? WHERE id=?', (json.dumps(bad), 'one'))
        current = engine._profiles('local:supervisor', 'fixture')['analysis']
        assert current['correct_count'] == 0 and current['error_count'] == 2
        assert engine._profiles('local:supervisor', 'different_identity') == {}
    finally:
        engine.close()

def test_rolled_back_profile_transaction_cannot_reuse_cached_correctness(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    engine = AdaptiveModelEngine(config)
    good = {'correct': True, 'verified_success': True, 'latency_ms': 5, 'queue_ms': 0, 'generation_tps': None, 'prompt_tps': None, 'error': False, 'environment': 'synthetic transaction fixture', 'created_at': 1}
    bad = dict(good, correct=False, verified_success=False, error=True)
    try:
        db = engine._connect()
        db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('rolled-back', 'local:supervisor', 'fixture', 'analysis', json.dumps(good)))
        assert engine._profiles('local:supervisor', 'fixture')['analysis']['correct_count'] == 1
        db.rollback()
        db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('committed', 'local:supervisor', 'fixture', 'analysis', json.dumps(bad)))
        db.commit()
        result = engine._profiles('local:supervisor', 'fixture')['analysis']
        assert result['sample_count'] == 1 and result['correct_count'] == 0 and (result['error_count'] == 1)
    finally:
        engine.close()

@pytest.mark.parametrize('change', ['same_timestamp_correction', 'same_timestamp_semantic', 'delete', 'insert'])
def test_memory_recall_observes_cross_connection_changes_immediately(tmp_path, change):
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    with store._connect() as db:
        db.execute('INSERT INTO memories(id,content,normalized_content,memory_type,source,confidence,created_at,updated_at,project_id,semantic_status,source_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?)', ('alpha', 'Synthetic atlas dispatch code is amber.', 'synthetic atlas dispatch code is amber.', 'fact', 'synthetic', 1, '2026-10-09T00:00:00+00:00', '2026-10-09T00:00:00+00:00', 'audit', 'statement', 'independent-original'))
    reader = ContextAwareRetriever(store, project_id='audit')
    original = reader.retrieve('atlas dispatch code')
    assert 'amber' in original.text
    with sqlite3.connect(store.path) as outside:
        if change == 'same_timestamp_correction':
            outside.execute("UPDATE memories SET content='Synthetic atlas dispatch code is coral.', normalized_content='synthetic atlas dispatch code is coral.' WHERE id='alpha'")
        elif change == 'same_timestamp_semantic':
            outside.execute("UPDATE memories SET semantic_status='hypothetical' WHERE id='alpha'")
        elif change == 'delete':
            outside.execute("DELETE FROM memories WHERE id='alpha'")
        else:
            outside.execute("INSERT INTO memories SELECT 'beta','Synthetic atlas dispatch code is coral.','synthetic atlas dispatch code is coral.',memory_type,source,confidence,created_at,updated_at,fact_key,fact_value,project_id,semantic_status,source_ref FROM memories WHERE id='alpha'")
    current = reader.retrieve('atlas dispatch code')
    if change in {'same_timestamp_semantic', 'delete'}:
        assert not current.text and (not current.matches)
    else:
        assert 'coral' in current.text and current.text != original.text
    if change == 'same_timestamp_correction':
        assert 'amber' not in current.text

def test_memory_recall_retains_budget_and_project_isolation(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    for project in ('audit', 'private-other'):
        store.remember(f'Synthetic atlas dispatch code for {project} is ' + ('amber' if project == 'audit' else 'violet'), source='synthetic', project_id=project)
    reader = ContextAwareRetriever(store, project_id='audit', max_chars=512, max_tokens=512)
    for _ in range(5):
        context = reader.retrieve('atlas dispatch code')
        assert len(context.text.encode()) <= 512 and 'violet' not in context.text

@pytest.mark.parametrize('invalid', [None, True, False, -1, float('nan'), float('inf'), 10 ** 10, '85'])
def test_invalid_server_rate_never_becomes_measured_telemetry(invalid):
    assert server_rates({'timings': {'prompt_per_second': invalid, 'predicted_per_second': invalid}}) == {}

def test_server_phase_rates_do_not_invent_first_token_or_queue_duration():
    assert server_rates({'timings': {'prompt_per_second': 0, 'predicted_per_second': 12}}) == {'prompt_tps': 0, 'generation_tps': 12}
    assert server_rates({'usage': {'completion_tokens': 100}, 'latency_ms': 1}) == {}

def test_recent_metrics_bound_window_count_and_preserve_unknown():
    samples = [{'created_at': 1000 + i, 'latency_ms': i + 1, 'ttft_ms': None, 'generation_tps': None, 'prompt_tps': None, 'queue_ms': None, 'error': i % 10 == 0} for i in range(150)]
    samples.extend([dict(samples[0], created_at=1), dict(samples[0], created_at=1201)])
    result = recent_performance(samples, 1200, window_seconds=200)
    assert result['sample_count'] == 100 and len(result['history']) == 32
    assert result['history'][0]['sampled_at'] == 1118 and result['history'][-1]['sampled_at'] == 1149
    assert result['ttft_ms'] is None and result['generation_tps'] is None and (result['queue_ms'] is None)
    assert result['recent_failures'] == 10 and result['percentile_method'] == 'nearest_rank'

def test_recent_metrics_empty_and_zero_are_distinct():
    empty = recent_performance([], 1000)
    assert empty['sample_count'] == 0 and empty['p50_latency_ms'] is None and (not empty['history'])
    zero = recent_performance([{'created_at': 1000, 'latency_ms': 0, 'ttft_ms': 0, 'generation_tps': 0, 'prompt_tps': 0, 'queue_ms': 0, 'error': False}], 1000)
    assert zero['sample_count'] == 1 and zero['p50_latency_ms'] == 0 and (zero['ttft_ms'] == 0)

def test_original_private_http_endpoint_bounds_current_identity_telemetry_and_keeps_token_gate():
    import urllib.error
    import urllib.request
    from hanni.reliability.execution import close_service
    sys.path.insert(0, str(ROOT / 'scripts/desktop_review'))
    from phase_fixture import PhaseReviewFixture
    fixture = PhaseReviewFixture()
    fixture.__enter__()
    try:
        engine = fixture.server.model_routing
        engine.refresh()
        identity = engine.endpoint_identity('local:supervisor')
        now = time.time()
        payload = {'correct': None, 'verified_success': None, 'latency_ms': 100, 'queue_ms': 0, 'generation_tps': None, 'prompt_tps': None, 'ttft_ms': None, 'error': False, 'environment': 'synthetic HTTP telemetry fixture', 'created_at': now}
        with engine.lock:
            db = engine._connect()
            db.executemany('INSERT INTO measurements VALUES(?,?,?,?,?)', [(f'current-{i}', 'local:supervisor', identity, 'analysis', json.dumps(dict(payload, created_at=now - i * 0.01))) for i in range(120)])
            db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('old-identity', 'local:supervisor', 'replaced-identity', 'analysis', json.dumps(dict(payload, latency_ms=999999))))
            db.commit()
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(fixture.url + 'api/model-routing', timeout=5)
        assert denied.value.code == 403
        request = urllib.request.Request(fixture.url + 'api/model-routing', headers={'X-Hanni-Token': fixture.hub.token})
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.load(response)
        row = next((row for row in value['endpoints'] if row['endpoint_id'] == 'local:supervisor'))
        performance = row['performance']
        assert performance['sample_count'] == 100 and len(performance['history']) == 32
        assert performance['p95_latency_ms'] == 100 and performance['recent_failures'] == 0
        assert performance['ttft_ms'] is None and performance['generation_tps'] is None
        encoded = json.dumps(performance)
        assert 'synthetic HTTP telemetry fixture' not in encoded and 'replaced-identity' not in encoded
        assert set(performance['history'][0]) == {'sampled_at', 'latency_ms', 'ttft_ms', 'generation_tps', 'prompt_tps', 'queue_ms', 'error'}
        assert row.get('gpu_measurement') is None or set(row['gpu_measurement']) <= {'vram_total_bytes', 'vram_free_bytes', 'utilization_percent', 'sampled_at'}
    finally:
        fixture.server.shutdown()
        fixture.server.server_close()
        fixture.thread.join(3)
        close_service(fixture.config.paths.data_dir)
        fixture.hub.close()
        fixture.hub.db.close()
        fixture.temporary.cleanup()

def test_stream_cancellation_closes_held_transport_before_releasing_lease(tmp_path, monkeypatch):
    from contextlib import contextmanager
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    client = LlamaCppClient(config.models.supervisor, max_attempts=1)
    closed = []
    lease_exit = []

    def incoming():
        try:
            yield 'visible chunk'
            yield 'late chunk'
        finally:
            closed.append(True)
    held = incoming()
    monkeypatch.setattr(client, '_stream_chat', lambda *_args, **_kwargs: held)

    @contextmanager
    def lease(_spec):
        try:
            yield
        finally:
            lease_exit.append(bool(closed))
    monkeypatch.setattr('hanni.models.manager.inference_lease', lease)
    outer = client.stream_chat([{'role': 'user', 'content': 'synthetic cancellation'}], performance={})
    assert next(outer) == 'visible chunk'
    outer.close()
    assert closed == [True] and lease_exit == [True]
    assert list(held) == []

def test_previously_safe_recall_becomes_ineligible_after_dynamic_secret_registration(tmp_path):
    from uuid import uuid4
    from hanni.logs import redaction
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    content = 'Synthetic atlas shipment label is quartz-v42-8429.'
    store.remember(content, source='synthetic', project_id='audit')
    retriever = ContextAwareRetriever(store, project_id='audit')
    assert content in retriever.retrieve('atlas shipment label').text
    name = 'independent-v42-' + uuid4().hex
    try:
        redaction.register_secret(name, 'quartz-v42-8429')
        recalled = retriever.retrieve('atlas shipment label')
        assert not recalled.text and (not recalled.matches)
    finally:
        with redaction._lock:
            redaction._registry.pop(name, None)

def test_registry_change_during_recall_fails_closed_before_context_return(tmp_path, monkeypatch):
    from uuid import uuid4
    from hanni.logs import redaction
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    content = 'Synthetic atlas shipment label is quartz-v42-9430.'
    store.remember(content, source='synthetic', project_id='audit')
    retriever = ContextAwareRetriever(store, project_id='audit')
    assert content in retriever.retrieve('atlas shipment label').text
    name = 'independent-v42-mid-' + uuid4().hex
    original = store.iter_records

    def observe(*args, **kwargs):
        for record in original(*args, **kwargs):
            yield record
            redaction.register_secret(name, 'quartz-v42-9430')
    monkeypatch.setattr(store, 'iter_records', observe)
    try:
        recalled = retriever.retrieve('atlas shipment label')
        assert not recalled.text and (not recalled.matches)
    finally:
        with redaction._lock:
            redaction._registry.pop(name, None)
