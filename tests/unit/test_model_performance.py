"""Numeric telemetry and quality-preserving bounded adaptation."""
from dataclasses import replace
from contextlib import contextmanager
import json
import threading
from types import SimpleNamespace
import pytest
from hanni.models.adaptive import ModelRequest, ModelSelectionError
from hanni.models.client import LlamaCppClient, _iter_sse_content
from hanni.models.performance import recent_performance, server_rates
from tests.unit.test_adaptive_model_routing import engine, prove, request

def observe(engine, key, latency, *, category='analysis', correct=None, verified=None, error=False, count=3):
    for index in range(count):
        engine.record_evaluation(key, identity=engine.endpoint_identity(key), task_category=category, correct=correct, verified_success=verified, latency_ms=latency, error=error, evidence_sha256='e' * 64, environment='controlled performance fixture')

def prepare(engine):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key, ('text',))
    engine.clock = lambda: 500
    observe(engine, 'local:supervisor', 100, correct=True, verified=True, count=20)
    observe(engine, 'worker:fixture', 200, correct=True, verified=True, count=20)
    engine.clock = lambda: 1000
    engine.configure(policy='fast')

def refresh_heartbeat(engine, now):
    engine.clock = lambda: now
    engine.observations['local:supervisor']['last_heartbeat'] = now
    engine.compute.registry.observe('fixture', last_heartbeat=now)

def test_recent_same_category_uses_minimum_samples_and_hold(engine):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 20)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'worker:fixture'
    observe(engine, 'local:supervisor', 100, count=4)
    observe(engine, 'worker:fixture', 400, count=4)
    held = engine.select(request(task_category='analysis'))
    assert held['endpoint']['endpoint_id'] == 'worker:fixture' and 'placement hold' in held['reason']
    refresh_heartbeat(engine, 1031)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'

@pytest.mark.parametrize('error,verified,correct', [(True, False, None), (False, False, None), (False, True, False)])
def test_short_failures_cannot_look_like_fast_success(engine, error, verified, correct):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 0, error=error, verified=verified, correct=correct)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'

def test_unrelated_category_and_two_samples_cannot_drive_adaptation(engine):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 1, category='conversation')
    observe(engine, 'worker:fixture', 1, count=2)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'

def test_three_recent_failures_release_hold_only_for_proven_healthy_peer(engine):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 20)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'worker:fixture'
    observe(engine, 'worker:fixture', 0, error=True, verified=False)
    selected = engine.select(request(task_category='analysis'))
    assert selected['endpoint']['endpoint_id'] == 'local:supervisor'
    assert '3 consecutive recent failures' in selected['reason']

@pytest.mark.parametrize('now', [1400, 450])
def test_expired_or_future_observations_revert_to_original_default(engine, now):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 20)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'worker:fixture'
    refresh_heartbeat(engine, now)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'

def test_small_speed_fluctuations_do_not_switch(engine):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 180)
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'

def test_manual_policy_and_current_privacy_are_not_overridden_by_speed(engine):
    prepare(engine)
    observe(engine, 'local:supervisor', 200)
    observe(engine, 'worker:fixture', 1)
    engine.configure(policy='manual', manual_endpoint_id='local:supervisor')
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'
    engine.configure(policy='fast')
    assert engine.select(ModelRequest(task_category='analysis', privacy_categories=frozenset({'memory'})))['endpoint']['endpoint_id'] == 'local:supervisor'

def test_trusted_background_flag_preserves_existing_worker_reserve(engine):
    path = engine.compute.registry.root / 'deployment.json'
    deployment = json.loads(path.read_text())
    deployment['workers'][0]['interactive_reserve'] = 1
    path.write_text(json.dumps(deployment))
    prove(engine, 'worker:fixture', ('text',))
    allowed = frozenset({'worker:fixture'})
    assert engine.select(request(interactive=True), allowed_endpoint_ids=allowed)['endpoint'] is not None
    assert engine.select(request(interactive=False), allowed_endpoint_ids=allowed)['endpoint'] is None
    with pytest.raises(ModelSelectionError):
        request(interactive=1)

def test_specialists_cannot_escalate_background_parent_priority(engine, monkeypatch):
    from hanni.models.collaboration import SpecialistTask
    prepare(engine)
    collaboration = engine.collaboration
    received = []

    def run(messages, *, request, **options):
        received.append(request.interactive)
        return {'participants': [{'participant_id': 'primary'}], 'selected_output': 'fixture', 'final_verification': {'status': 'VERIFIED'}, 'generated_tokens': 1, 'conflicts': []}
    monkeypatch.setattr(collaboration, 'run', run)
    tasks = [SpecialistTask('task_' + str(index), 'Synthetic assigned task', ({'role': 'user', 'content': 'Synthetic calculation'},), request(task_category='analysis', interactive=True)) for index in range(2)]
    collaboration.run_specialists(tasks, request=request(task_category='analysis', interactive=False))
    assert received == [False, False]

def test_server_rates_are_separate_from_token_usage_and_unknown_ttft():
    usage, performance = ({}, {})
    lines = [b'data: {"choices":[{"delta":{"content":"ok"}}],"usage":{"prompt_tokens":4},"timings":{"prompt_per_second":12.5,"predicted_per_second":8}}\n', b'data: [DONE]\n']
    assert ''.join(_iter_sse_content(lines, usage=usage, performance=performance)) == 'ok'
    assert usage == {'prompt_tokens': 4}
    assert performance == {'prompt_tps': 12.5, 'generation_tps': 8}
    assert server_rates({'timings': {'prompt_per_second': True, 'predicted_per_second': float('nan')}}) == {}

def test_performance_window_bounded_unknowns_and_percentiles():
    samples = [{'created_at': index, 'latency_ms': index, 'queue_ms': 0, 'error': False} for index in range(150)]
    result = recent_performance(samples, 150)
    assert result['sample_count'] == 100 and len(result['history']) == 32
    assert result['p50_latency_ms'] == 99 and result['p95_latency_ms'] == 144
    assert result['ttft_ms'] is None and result['generation_tps'] is None
    assert recent_performance(samples, -1)['sample_count'] == 0

def test_local_gpu_observation_reuses_only_unambiguous_existing_capture(engine, monkeypatch):
    spec = engine.config.models.supervisor
    name = spec.device_name_hints[0] if spec.device_name_hints else 'Synthetic GPU'
    gpu = SimpleNamespace(name=name, memory_total_mb=6144, memory_used_mb=1024, utilization_percent=17)
    manager = SimpleNamespace(lock=threading.RLock(), last_resources=SimpleNamespace(gpus=(gpu,)), last_resources_sampled_at=1000)
    monkeypatch.setattr('hanni.models.manager.current', lambda spec: manager)
    monkeypatch.setattr(engine.compute.transport, 'request', lambda *args, **options: {})
    engine.local_probe = None
    observation = engine._probe_local(engine._inventory()[0])
    assert observation['gpu_measurement'] == {'vram_total_bytes': 6 * 1024 ** 3, 'vram_free_bytes': 5 * 1024 ** 3, 'utilization_percent': 17}
    assert observation['resource_sampled_at'] == 1000
    manager.last_resources = SimpleNamespace(gpus=(gpu, gpu))
    ambiguous = engine._probe_local(engine._inventory()[0])
    assert ambiguous['gpu_measurement'] is None and ambiguous['resource_sampled_at'] is None

def test_uncommitted_aggregate_cannot_survive_rollback_generation_collision(engine):
    key = 'local:supervisor'
    identity = engine.endpoint_identity(key)
    db = engine._connect()
    payload = {'correct': True, 'verified_success': True, 'latency_ms': 5, 'queue_ms': 0, 'generation_tps': None, 'prompt_tps': None, 'error': False, 'environment': 'controlled rollback fixture', 'created_at': 1000}
    db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('rolled-back', key, identity, 'analysis', json.dumps(payload)))
    assert db.in_transaction
    assert engine._profiles(key, identity)['analysis']['correct_count'] == 1
    db.rollback()
    db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('committed', key, identity, 'analysis', json.dumps(dict(payload, correct=False, verified_success=False, error=True))))
    db.commit()
    assert engine._profiles(key, identity)['analysis']['correct_count'] == 0

def test_client_cancellation_closes_held_inner_stream_before_releasing_lease(engine, monkeypatch):
    events = []

    @contextmanager
    def lease(spec):
        events.append('lease_enter')
        try:
            yield
        finally:
            events.append('lease_exit')

    def inner():
        try:
            yield 'first'
            yield 'second'
        finally:
            events.append('inner_close')
    held = inner()
    client = LlamaCppClient(engine.config.models.supervisor)
    monkeypatch.setattr('hanni.models.manager.inference_lease', lease)
    monkeypatch.setattr(client, '_stream_chat', lambda *args, **kwargs: held)
    stream = client.stream_chat([{'role': 'user', 'content': 'Synthetic request'}])
    assert next(stream) == 'first'
    stream.close()
    assert events == ['lease_enter', 'inner_close', 'lease_exit']
    assert list(held) == []

def test_adaptive_cancellation_explicitly_closes_held_client_stream(engine, monkeypatch):
    prove(engine, 'local:supervisor', ('text',))
    events = []

    def inner():
        try:
            yield 'first'
            yield 'second'
        finally:
            events.append(engine.active.get('local:supervisor'))
    held = inner()
    client = LlamaCppClient(engine.config.models.supervisor)
    monkeypatch.setattr(client, 'stream_chat', lambda *args, **kwargs: held)
    stream = engine.wrap_client(client).stream_chat([{'role': 'user', 'content': 'Synthetic request'}])
    assert next(stream) == 'first'
    stream.close()
    assert events == [1] and engine.active['local:supervisor'] == 0
    assert list(held) == []
