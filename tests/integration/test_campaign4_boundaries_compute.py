"""Actual owned HTTP disconnect/late result through original workflow compute path."""
import json
from pathlib import Path
import threading
import pytest
from scripts.campaign4_boundaries.compute_fixture import analysis_client, endpoint, evidence, scheduler
from scripts.campaign4_boundaries.harness import ServiceFixture, reviewed_start

@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'observed-counts.json'
    path.write_text('{"passed":4,"total":10}', encoding='utf-8')
    return path

def retain(record_property, final, engine, workers):
    record_property('native_compute_evidence', json.dumps(evidence(final, engine, workers), sort_keys=True))

@pytest.mark.parametrize('fallback', [False, True])
def test_actual_worker_socket_disconnect_respects_fallback_and_preserves_receipts(tmp_path, source, fallback, record_property):
    client = analysis_client(source, local_fallback=fallback)
    with endpoint('controlled_disconnect', behavior='disconnect') as worker:
        with scheduler(tmp_path / 'workers', [worker], fallback_local=fallback) as engine:
            with ServiceFixture(tmp_path / 'run', client=client) as box:
                box.service.compute = engine
                box.observe('file.write')
                key = box.submit('Read the JSON file ' + str(source) + ', calculate the percentage and save a checked report.')
                reviewed_start(box, key)
                final = box.await_state(key, 'completed', 'blocked')
                retain(record_property, final, engine, [worker])
                assert worker['disconnections'] == len(worker['calls']) == 1
                job = engine.registry.jobs(key)[0]
                assert job['state'] == 'LOST_CONNECTION' and 'output_sha256' not in job
                assert job['workflow_id'] == key and job['invocation_id'] == final['invocations'][1]['invocation_id']
                assert not any(engine.registry.active.values())
                if fallback:
                    assert final['status'] == 'completed' and final['counts']['verified'] == 3, final
                    assert len(client.calls) == 3 and box.ledger.entries('file.write') == 1
                    assert any((row['kind'] == 'compute_local_fallback' for row in final['checkpoints']))
                    saved = Path(final['steps'][-1]['resolved_arguments']['path'])
                    assert json.loads(saved.read_text())['observations'][0]['value'] == 40
                else:
                    assert final['status'] == 'blocked' and final['counts']['verified'] == 1, final
                    assert len(client.calls) == 2 and box.ledger.entries('file.write') == 0
                box.service.compute = None

def test_actual_disconnect_reassignment_uses_original_job_and_verified_sources(tmp_path, source, record_property):
    with endpoint('controlled_disconnected_first', behavior='disconnect') as first:
        with endpoint('controlled_remaining_second') as second:
            with scheduler(tmp_path / 'workers', [first, second], retries=1, timeout=2) as engine:
                with ServiceFixture(tmp_path / 'run', client=analysis_client(source)) as box:
                    box.service.compute = engine
                    key = box.submit('Read the JSON file ' + str(source) + ', calculate the percentage and save it.')
                    reviewed_start(box, key)
                    final = box.await_state(key, 'completed', 'blocked')
                    retain(record_property, final, engine, [first, second])
                    assert final['status'] == 'completed' and final['counts']['verified'] == 3, final
                    assert first['disconnections'] == len(first['calls']) == len(second['calls']) == 1
                    jobs = engine.registry.jobs(key)
                    assert len(jobs) == 1 and jobs[0]['attempt'] == 2 and (jobs[0]['state'] == 'VERIFIED')
                    lost = [row for row in jobs[0]['events'] if row['state'] == 'LOST_CONNECTION']
                    assert len(lost) == 1 and lost[0]['worker_id'] == 'controlled_worker_0'
                    assert jobs[0]['worker_id'] == 'controlled_worker_1'
                    assert len(box.client.calls) == 2 and (not any(engine.registry.active.values()))
                    box.service.compute = None

@pytest.mark.parametrize('value', [40, 41])
def test_actual_complete_http_response_requires_original_source_verification(tmp_path, source, value, record_property):
    with endpoint('controlled_complete', value=value) as worker:
        with scheduler(tmp_path / 'workers', [worker]) as engine:
            with ServiceFixture(tmp_path / 'run', client=analysis_client(source)) as box:
                box.service.compute = engine
                box.observe('file.write')
                key = box.submit('Read the JSON file ' + str(source) + ', calculate the cited percentage and save it.')
                reviewed_start(box, key)
                final = box.await_state(key, 'completed', 'blocked', 'partially_completed')
                retain(record_property, final, engine, [worker])
                job = engine.registry.jobs(key)[0]
                assert len(worker['calls']) == 1 and (not any(engine.registry.active.values()))
                assert (final['status'] == 'completed') is (value == 40), final
                assert job['state'] == ('VERIFIED' if value == 40 else 'FAILED')
                assert box.ledger.entries('file.write') == (1 if value == 40 else 0)
                box.service.compute = None

@pytest.mark.parametrize('operation', ['pause', 'cancel'])
def test_actual_late_worker_response_cannot_finish_after_owner_control(tmp_path, source, operation, record_property):
    gate = threading.Event()
    with endpoint('controlled_late_cancel', gate=gate) as worker:
        with scheduler(tmp_path / 'workers', [worker], fallback_local=True, timeout=2) as engine:
            with ServiceFixture(tmp_path / 'run', client=analysis_client(source, local_fallback=True)) as box:
                box.service.compute = engine
                box.observe('file.write')
                key = box.submit('Read the JSON file ' + str(source) + ', calculate the percentage and save it.')
                reviewed_start(box, key)
                try:
                    assert worker['entered'].wait(3)
                    before = box.detail(key)
                    assert before['active_uninterruptible']
                    box.control(key, operation)
                    assert box.detail(key)['active_uninterruptible'], 'Synchronous HTTP remains visible until returned.'
                finally:
                    gate.set()
                expected = 'paused' if operation == 'pause' else 'cancelled'
                final = box.service.wait(key, predicate=lambda row: row['status'] == expected and (not row['active_uninterruptible']))
                retain(record_property, final, engine, [worker])
                assert final['status'] == expected and final['counts']['verified'] == 1, final
                assert len(box.client.calls) == 2 and box.ledger.entries('file.write') == 0
                job = engine.registry.jobs(key)[0]
                assert job['state'] == 'BLOCKED' and 'output_sha256' not in job
                assert not any(engine.registry.active.values())
                box.service.compute = None

def test_actual_http_timeout_preserves_failed_job_then_explicit_refresh_recovers_new_work(tmp_path, source, record_property):
    gate = threading.Event()
    with endpoint('controlled_timeout_recovery', gate=gate) as worker:
        with scheduler(tmp_path / 'workers', [worker], timeout=1) as engine:
            with ServiceFixture(tmp_path / 'first-run', client=analysis_client(source)) as first:
                first.service.compute = engine
                first.observe('file.write')
                key = first.submit('Read the JSON file ' + str(source) + ', calculate the percentage and save it.')
                reviewed_start(first, key)
                try:
                    assert worker['entered'].wait(3)
                    blocked = first.await_state(key, 'blocked')
                    record_property('native_timeout_evidence', json.dumps(evidence(blocked, engine, [worker]), sort_keys=True))
                    assert blocked['counts']['verified'] == 1 and first.ledger.entries('file.write') == 0
                    original_job = engine.registry.jobs(key)[0]
                    assert original_job['state'] == 'LOST_CONNECTION' and 'output_sha256' not in original_job
                    assert len(worker['calls']) == 1 and (not any(engine.registry.active.values()))
                finally:
                    gate.set()
                    first.service.compute = None
            engine.refresh()
            with ServiceFixture(tmp_path / 'second-run', client=analysis_client(source)) as second:
                second.service.compute = engine
                recovered_key = second.submit('Read the JSON file ' + str(source) + ', calculate the percentage and save it.')
                reviewed_start(second, recovered_key)
                recovered = second.await_state(recovered_key, 'completed', 'blocked')
                retain(record_property, recovered, engine, [worker])
                assert recovered['status'] == 'completed' and recovered['counts']['verified'] == 3, recovered
                assert len(worker['calls']) == 2 and (not any(engine.registry.active.values()))
                assert engine.registry.jobs(key)[0]['job_id'] == original_job['job_id']
                assert engine.registry.jobs(key)[0]['state'] == 'LOST_CONNECTION'
                assert engine.registry.jobs(recovered_key)[0]['state'] == 'VERIFIED'
                assert engine.registry.jobs(recovered_key)[0]['job_id'] != original_job['job_id']
                second.service.compute = None
