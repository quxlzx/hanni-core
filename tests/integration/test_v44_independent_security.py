"""Fresh independent V4.4 authority/fault probes; simulated endpoints, not quality.

No final task or oracle is imported. These exercise original scheduler/adaptive
entry points with declared transport seams and never contact owner hardware.
"""
from copy import deepcopy
import json
import threading
import time
import pytest
from hanni.compute.registry import ComputeError
from hanni.models.adaptive import ModelRequest, ModelSelectionError
from tests.integration.test_adaptive_v40_verifier import audit_engine

def dispatch(compute, **kwargs):
    return compute.chat([{'role': 'user', 'content': 'Independent synthetic authority probe.'}], workflow_id='v44_independent', step_id='reason', invocation_id='probe', categories={'synthetic'}, max_tokens=32, max_queue_seconds=0.1, max_retries_override=0, **kwargs)

@pytest.mark.parametrize('field', ['ram_available_bytes', 'vram_free_bytes'])
def test_unknown_remote_resources_reject_original_scheduler_dispatch(audit_engine, field):
    _, compute, calls, _ = audit_engine
    deployment = deepcopy(compute.registry.deployment)
    deployment['workers'][0]['gpu'] = 'Synthetic GPU fixture'
    (compute.registry.root / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
    compute.registry.reload()
    compute.registry.record_context_verified('remote-fixture', target_tokens=8192, prompt_tokens=7800, model_id='synthetic-control-model', prompt_sha256='c' * 64, response_sha256='d' * 64)
    compute.registry.observations['remote-fixture'][field] = None
    with pytest.raises(ComputeError):
        dispatch(compute)
    assert calls == []
    assert not compute.waiting and (not compute.inflight) and (not compute.queued)

def test_response_schema_is_part_of_remote_context_admission(audit_engine):
    _, compute, calls, _ = audit_engine
    schema = {'type': 'json_schema', 'json_schema': {'name': 'large_schema', 'schema': {'type': 'object', 'description': 'structured context ' * 700}}}
    with pytest.raises(ComputeError):
        dispatch(compute, response_format=schema)
    assert calls == []

def test_late_transport_cancellation_suppresses_response_admission(audit_engine, monkeypatch):
    _, compute, calls, response = audit_engine
    cancelled = threading.Event()

    def transport(*args, **kwargs):
        calls.append(('controlled-completed-transport', {}))
        cancelled.set()
        return deepcopy(response)
    monkeypatch.setattr(compute.transport, 'request', transport)
    with pytest.raises(ComputeError):
        dispatch(compute, cancellation=cancelled)
    assert len(calls) == 1
    assert not compute.inflight
    assert not any((row['state'] == 'COMPLETED' for row in compute.registry.snapshot()['jobs']))

def test_authorization_revocation_during_transport_never_admits_output(audit_engine, monkeypatch):
    _, compute, calls, response = audit_engine

    def transport(*args, **kwargs):
        calls.append(('controlled-return-after-revocation', {}))
        deployment = deepcopy(compute.registry.deployment)
        deployment['enabled'] = False
        (compute.registry.root / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
        return deepcopy(response)
    monkeypatch.setattr(compute.transport, 'request', transport)
    with pytest.raises(ComputeError):
        dispatch(compute)
    assert len(calls) == 1
    assert not any((row['state'] == 'COMPLETED' for row in compute.registry.snapshot()['jobs']))

@pytest.mark.parametrize('privacy', ['project', 'conversation', 'memory', 'screen', 'sensitive'])
def test_remote_assignment_cannot_downgrade_private_source_categories(audit_engine, privacy):
    engine, _, calls, _ = audit_engine
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'Independent private-context sentinel.'}], request=ModelRequest(privacy_categories=frozenset({privacy}), output_tokens=32), endpoint_id='worker:remote-fixture', max_fallbacks=0)
    assert calls == []

@pytest.mark.parametrize('finish', ['length', 'tool_calls', None])
def test_incomplete_remote_responses_never_become_completed(audit_engine, finish):
    _, compute, calls, response = audit_engine
    response['choices'][0]['finish_reason'] = finish
    with pytest.raises(ComputeError):
        dispatch(compute)
    assert len(calls) == 1
    assert not any((row['state'] == 'COMPLETED' for row in compute.registry.snapshot()['jobs']))

def test_unknown_worker_assignment_never_dispatches(audit_engine):
    _, compute, calls, _ = audit_engine
    with pytest.raises(ComputeError):
        dispatch(compute, allowed_worker_ids=('unregistered-v44',))
    assert calls == []

def test_precancelled_request_does_not_touch_transport(audit_engine):
    _, compute, calls, _ = audit_engine
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(ComputeError):
        dispatch(compute, cancellation=cancelled)
    assert not calls and (not compute.inflight) and (not compute.waiting)

def test_remote_receipts_never_retain_private_messages(audit_engine):
    _, compute, _, _ = audit_engine
    marker = 'SYNTHETIC_PRIVATE_MARKER_V44_654b'
    text, job = compute.chat([{'role': 'user', 'content': marker}], workflow_id='v44_privacy', step_id='reason', invocation_id='unique_probe', categories={'synthetic'}, max_tokens=32, max_queue_seconds=0.1, max_retries_override=0)
    assert text and job['input_sha256']
    assert marker not in repr(compute.registry.snapshot())
    assert marker.encode() not in (compute.registry.root / 'jobs.sqlite3').read_bytes()

@pytest.mark.parametrize('change', ['categories', 'identity', 'disabled'])
def test_original_admission_revocation_blocks_before_transport(audit_engine, change):
    _, compute, calls, _ = audit_engine

    def withdraw():
        deployment = deepcopy(compute.registry.deployment)
        worker = deployment['workers'][0]
        if change == 'categories':
            worker['allowed_categories'] = []
        elif change == 'identity':
            worker['model_id'] = 'different-configured-model'
        else:
            worker['enabled'] = False
        (compute.registry.root / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
    with pytest.raises((ComputeError, RuntimeError)):
        dispatch(compute, admission=withdraw)
    assert calls == []

@pytest.mark.parametrize('change', ['categories', 'identity', 'disabled'])
def test_protected_worker_changes_during_transport_block_result(audit_engine, monkeypatch, change):
    _, compute, calls, response = audit_engine

    def transport(*args, **kwargs):
        calls.append(('controlled-late-worker-revocation', {}))
        deployment = deepcopy(compute.registry.deployment)
        worker = deployment['workers'][0]
        if change == 'categories':
            worker['allowed_categories'] = []
        elif change == 'identity':
            worker['model_id'] = 'different-configured-model'
        else:
            worker['enabled'] = False
        (compute.registry.root / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
        return deepcopy(response)
    monkeypatch.setattr(compute.transport, 'request', transport)
    with pytest.raises(ComputeError):
        dispatch(compute)
    assert len(calls) == 1
    assert not any((row['state'] == 'COMPLETED' for row in compute.registry.snapshot()['jobs']))

@pytest.mark.parametrize('phase', ['initial', 'final'])
def test_cancellation_from_original_admission_callback_is_immediate(audit_engine, phase):
    _, compute, calls, _ = audit_engine
    cancelled = threading.Event()
    admissions = []

    def callback():
        admissions.append(True)
        if len(admissions) == (1 if phase == 'initial' else 2):
            cancelled.set()
    with pytest.raises(ComputeError):
        dispatch(compute, cancellation=cancelled, admission=callback)
    assert len(calls) == (0 if phase == 'initial' else 1)
    assert not any((row['state'] == 'COMPLETED' for row in compute.registry.snapshot()['jobs']))

def test_startup_gpu_device_requires_measured_vram_without_display_label(audit_engine):
    _, compute, calls, _ = audit_engine
    deployment = deepcopy(compute.registry.deployment)
    deployment['workers'][0]['startup'] = {'gpu_device': 'CUDA0'}
    (compute.registry.root / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
    compute.registry.reload()
    compute.registry.record_context_verified('remote-fixture', target_tokens=8192, prompt_tokens=7800, model_id='synthetic-control-model', prompt_sha256='e' * 64, response_sha256='f' * 64)
    compute.registry.observations['remote-fixture']['vram_free_bytes'] = None
    with pytest.raises(ComputeError):
        dispatch(compute)
    assert calls == []

def test_slow_failed_remotes_do_not_expire_genuinely_reprobed_local_health(audit_engine, monkeypatch):
    engine, compute, _, _ = audit_engine
    now = [1000]
    engine.clock = lambda: now[0]
    original_local = deepcopy(engine.observations['local:supervisor'])
    probes = []

    def slow_remote():
        now[0] += 35
        compute.registry.observe('remote-fixture', status='unhealthy', last_heartbeat=now[0])

    def local(row):
        probes.append(now[0])
        return dict(original_local, last_heartbeat=now[0])
    monkeypatch.setattr(compute, 'refresh', slow_remote)
    engine.local_probe = local
    engine.refresh()
    assert probes == [1035]
    request = ModelRequest(output_tokens=32)
    assert engine.select(request)['endpoint']['endpoint_id'] == 'local:supervisor'
    now[0] += 31
    assert engine.select(request)['endpoint'] is None

def test_unhealthy_remote_does_not_receive_resource_request(audit_engine, monkeypatch):
    _, compute, calls, _ = audit_engine
    monkeypatch.setattr(compute.transport, 'health', lambda w: {'status': 'unhealthy', 'last_heartbeat': 1000, 'model_id': w['model_id']})

    def forbidden(worker):
        calls.append(('unexpected-resources-call', {}))
        raise AssertionError('Resources must not be polled on an unhealthy endpoint.')
    monkeypatch.setattr(compute.transport, 'resources', forbidden)
    compute.refresh()
    assert not calls

def test_remote_resource_failure_clears_old_headroom_and_preserves_local_discovery(audit_engine, monkeypatch):
    engine, compute, _, _ = audit_engine

    def unavailable(worker):
        raise ComputeError('Independent controlled resource connection lost.')
    monkeypatch.setattr(compute.transport, 'resources', unavailable)
    engine.refresh()
    observed = compute.registry.observations['remote-fixture']
    assert observed.get('ram_available_bytes') is None and observed.get('vram_free_bytes') is None
    engine.configure(policy='manual', manual_endpoint_id='worker:remote-fixture')
    assert engine.select(ModelRequest(output_tokens=32, privacy_categories=frozenset({'synthetic'})))['endpoint'] is None
    engine.configure(policy='balanced')
    assert engine.select(ModelRequest(output_tokens=32))['endpoint']['endpoint_id'] == 'local:supervisor'

def test_resource_monitor_survives_fault_and_admits_fresh_later_sample(audit_engine, monkeypatch):
    _, compute, _, _ = audit_engine
    sampled = []

    def resources(worker):
        sampled.append(True)
        if len(sampled) == 1:
            raise ComputeError('First independent resource sample failed.')
        return {'ram_available_bytes': 6 * 1024 ** 3, 'vram_free_bytes': 1 * 1024 ** 3, 'resource_sampled_at': compute.registry.clock()}
    monkeypatch.setattr(compute.transport, 'resources', resources)
    compute.start_monitor()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and compute.registry.observations['remote-fixture'].get('ram_available_bytes') is not None:
        time.sleep(0.01)
    assert compute.registry.observations['remote-fixture'].get('ram_available_bytes') is None
    assert compute.monitor.is_alive() and (not compute.halt.is_set())
    compute.request_refresh()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and compute.registry.observations['remote-fixture'].get('ram_available_bytes') != 6 * 1024 ** 3:
        time.sleep(0.01)
    assert len(sampled) >= 2 and compute.monitor.is_alive()
    assert compute.registry.observations['remote-fixture']['ram_available_bytes'] == 6 * 1024 ** 3
