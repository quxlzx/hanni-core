"""V4.4 fault probes using isolated, scripted transports; never model quality."""
from copy import deepcopy
import json
import threading
import pytest
from hanni.compute import ComputeError, ComputeRegistry, ComputeScheduler
from hanni.models.adaptive import ModelRequest
from tests.unit.test_adaptive_model_routing import engine, prove

@pytest.fixture
def scheduler_probe(tmp_path):
    directory = tmp_path / 'compute'
    directory.mkdir()
    worker = {'worker_id': 'probe', 'node_id': 'remote-probe', 'remote_port': 19091, 'gpu': 'synthetic-gpu', 'model_id': 'synthetic-v44', 'enabled': True, 'context_configured': 8192, 'capabilities': ['analysis', 'structured_json'], 'allowed_categories': ['synthetic'], 'concurrency': 1}
    deployment = {'version': 1, 'enabled': True, 'nodes': [{'id': 'remote-probe'}], 'workers': [worker], 'policy': {'timeout_seconds': 1, 'max_retries': 0}}
    (directory / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
    registry = ComputeRegistry(tmp_path, clock=lambda: 1000)
    registry.observe('probe', status='healthy', model_id='synthetic-v44', context_reported=8192, max_context_verified=8192, last_heartbeat=1000, ram_available_bytes=8 * 1024 ** 3, vram_free_bytes=2 * 1024 ** 3, resource_sampled_at=registry.clock())

    class Transport:

        def __init__(self):
            self.calls = []
            self.cancel_on_return = False

        def request(self, worker, method, path, **kwargs):
            self.calls.append(deepcopy(kwargs['payload']))
            if self.cancel_on_return:
                kwargs['cancel'].set()
            return {'model': worker['model_id'], 'choices': [{'message': {'content': '{"fixture":true}'}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 4}}

        def close(self):
            pass
    transport = Transport()
    scheduler = ComputeScheduler(registry, transport=transport)
    yield (scheduler, transport)
    scheduler.close()

def probe_call(scheduler, **kwargs):
    return scheduler.chat([{'role': 'user', 'content': 'Synthetic source probe.'}], workflow_id='v44_probe', step_id='analysis', invocation_id='invocation', categories=['synthetic'], max_tokens=32, max_queue_seconds=0.05, **kwargs)

def test_direct_compute_counts_response_schema_in_context_budget(scheduler_probe):
    scheduler, transport = scheduler_probe
    response_format = {'type': 'json_schema', 'json_schema': {'name': 'probe', 'schema': {'type': 'object', 'description': 'synthetic ' * 1000, 'properties': {'fixture': {'type': 'boolean'}}}}}
    with pytest.raises(ComputeError):
        probe_call(scheduler, response_format=response_format)
    assert transport.calls == []
    assert not scheduler.waiting and (not scheduler.inflight) and (not scheduler.queued)

def test_direct_compute_withdraws_result_after_transport_cancellation(scheduler_probe):
    scheduler, transport = scheduler_probe
    transport.cancel_on_return = True
    event = threading.Event()
    with pytest.raises(ComputeError):
        probe_call(scheduler, cancellation=event)
    assert event.is_set() and len(transport.calls) == 1
    assert scheduler.registry.jobs()[0]['state'] == 'CANCELLED'
    assert scheduler.registry.snapshot()['workers'][0]['status'] == 'healthy'
    assert scheduler.registry.active['probe'] == 0
    assert not scheduler.waiting and (not scheduler.inflight) and (not scheduler.queued)

@pytest.mark.parametrize('cancel_on_admission', [1, 2])
def test_original_admission_cancellation_is_honored_immediately(scheduler_probe, cancel_on_admission):
    scheduler, transport = scheduler_probe
    event = threading.Event()
    checks = []

    def admission():
        checks.append(True)
        if len(checks) == cancel_on_admission:
            event.set()
    with pytest.raises(ComputeError):
        probe_call(scheduler, cancellation=event, admission=admission)
    assert len(transport.calls) == cancel_on_admission - 1
    assert scheduler.registry.jobs()[0]['state'] == 'CANCELLED'
    assert scheduler.registry.snapshot()['workers'][0]['status'] == 'healthy'
    assert scheduler.registry.active['probe'] == 0

@pytest.mark.parametrize('field', ['ram_available_bytes', 'vram_free_bytes'])
def test_direct_compute_requires_known_remote_memory_before_dispatch(scheduler_probe, field):
    scheduler, transport = scheduler_probe
    scheduler.registry.observe('probe', **{field: None})
    with pytest.raises(ComputeError):
        probe_call(scheduler)
    assert transport.calls == []
    assert not scheduler.waiting and (not scheduler.inflight) and (not scheduler.queued)

def test_remote_cpu_only_worker_does_not_require_gpu_memory(scheduler_probe):
    scheduler, transport = scheduler_probe
    path = scheduler.registry.root / 'deployment.json'
    deployment = json.loads(path.read_text(encoding='utf8'))
    deployment['workers'][0].pop('gpu')
    path.write_text(json.dumps(deployment), encoding='utf8')
    scheduler.registry.reload()
    scheduler.registry.observe('probe', status='healthy', model_id='synthetic-v44', max_context_verified=8192, context_reported=8192, last_heartbeat=1000, ram_available_bytes=8 * 1024 ** 3, vram_free_bytes=None, resource_sampled_at=scheduler.registry.clock())
    assert probe_call(scheduler)[0] == '{"fixture":true}'
    assert len(transport.calls) == 1

def test_gpu_device_without_display_label_still_requires_memory(scheduler_probe):
    scheduler, transport = scheduler_probe
    path = scheduler.registry.root / 'deployment.json'
    deployment = json.loads(path.read_text(encoding='utf8'))
    deployment['workers'][0].pop('gpu')
    deployment['workers'][0]['startup'] = {'gpu_device': 'synthetic-gpu-identity'}
    path.write_text(json.dumps(deployment), encoding='utf8')
    scheduler.registry.reload()
    scheduler.registry.observe('probe', status='healthy', model_id='synthetic-v44', max_context_verified=8192, context_reported=8192, last_heartbeat=1000, ram_available_bytes=8 * 1024 ** 3, vram_free_bytes=None, resource_sampled_at=scheduler.registry.clock())
    with pytest.raises(ComputeError):
        probe_call(scheduler)
    assert transport.calls == []

@pytest.mark.parametrize('withdraw', ['ram', 'proof', 'health'])
def test_worker_capacity_is_rechecked_after_original_admission(scheduler_probe, withdraw):
    scheduler, transport = scheduler_probe

    def admission():
        change = {'ram': {'ram_available_bytes': None}, 'proof': {'max_context_verified': None}, 'health': {'status': 'unhealthy'}}[withdraw]
        scheduler.registry.observe('probe', **change)
    with pytest.raises(RuntimeError, match='capacity changed'):
        probe_call(scheduler, admission=admission)
    assert transport.calls == []
    assert scheduler.registry.jobs()[0]['state'] == 'BLOCKED'
    assert scheduler.registry.active['probe'] == 0

def test_original_admission_is_rechecked_before_returning_result(scheduler_probe):
    scheduler, transport = scheduler_probe
    checks = []

    def admission():
        checks.append(True)
        if len(checks) == 2:
            raise RuntimeError('Original lease was withdrawn.')
    with pytest.raises(RuntimeError, match='lease was withdrawn'):
        probe_call(scheduler, admission=admission)
    assert len(checks) == 2 and len(transport.calls) == 1
    assert scheduler.registry.jobs()[0]['state'] == 'BLOCKED'
    assert scheduler.registry.active['probe'] == 0

def test_protected_permission_withdrawal_prevents_dispatch(scheduler_probe):
    scheduler, transport = scheduler_probe

    def admission():
        path = scheduler.registry.root / 'deployment.json'
        deployment = json.loads(path.read_text(encoding='utf8'))
        deployment['workers'][0]['allowed_categories'] = []
        path.write_text(json.dumps(deployment), encoding='utf8')
    with pytest.raises((RuntimeError, ComputeError)):
        probe_call(scheduler, admission=admission)
    assert transport.calls == []
    assert scheduler.registry.jobs()[0]['state'] == 'BLOCKED'

@pytest.mark.parametrize('response_format', [[], False, {'type': 'unknown'}, {'type': 'json_schema', 'password': 'example-public-56db29a6d039'}, {'type': 'json_schema', 'description': 'safe ' * 60000}])
def test_unsafe_or_unbounded_response_format_is_rejected_before_queue(scheduler_probe, response_format):
    scheduler, transport = scheduler_probe
    with pytest.raises(ComputeError):
        probe_call(scheduler, response_format=response_format)
    assert transport.calls == [] and scheduler.registry.jobs() == []

def test_slow_failed_remote_refresh_does_not_expire_new_local_health(engine, monkeypatch):
    now = [1000]
    observations = []
    engine.clock = lambda: now[0]
    engine.compute.registry.clock = engine.clock
    original_probe = engine.local_probe

    def local_probe(row):
        observations.append(('local', now[0]))
        return dict(original_probe(row), last_heartbeat=now[0])

    def remote_health(worker):
        now[0] += 35
        observations.append(('remote', now[0]))
        return {'status': 'unhealthy', 'last_heartbeat': now[0], 'error': 'Controlled slow unreachable worker.'}
    engine.local_probe = local_probe
    monkeypatch.setattr(engine.compute.transport, 'health', remote_health)
    prove(engine, 'local:supervisor', ('text',))
    engine.refresh()
    request = ModelRequest(privacy_categories=frozenset({'synthetic'}), local_only=True, output_tokens=64)
    selection = engine.select(request)
    assert selection['endpoint'] is not None
    assert selection['endpoint']['endpoint_id'] == 'local:supervisor'
    assert engine.observations['local:supervisor']['last_heartbeat'] == now[0]
    assert observations == [('remote', 1035), ('local', 1035)]
    assert engine.compute.transport.calls == []
    now[0] += 31
    assert engine.select(request)['endpoint'] is None

def test_failed_remote_health_does_not_trigger_another_resource_connection(engine, monkeypatch):
    resource_calls = []
    monkeypatch.setattr(engine.compute.transport, 'health', lambda worker: {'status': 'unhealthy', 'last_heartbeat': 1000, 'error': 'Controlled unreachable worker.'})

    def unreachable_resources(worker):
        resource_calls.append(worker['worker_id'])
        raise ComputeError('Controlled resource SSH unavailable.')
    monkeypatch.setattr(engine.compute.transport, 'resources', unreachable_resources)
    prove(engine, 'local:supervisor', ('text',))
    engine.refresh()
    assert resource_calls == []
    assert engine.select(ModelRequest(local_only=True, privacy_categories=frozenset({'synthetic'}), output_tokens=64))['endpoint'] is not None

@pytest.mark.parametrize('background', [False, True])
def test_remote_resource_failure_discards_stale_capacity_and_keeps_health_loop(engine, monkeypatch, background):

    def unavailable_resources(worker):
        engine.compute.halt.set()
        engine.compute.health_wake.set()
        raise ComputeError('Controlled resource sampling failure.')
    monkeypatch.setattr(engine.compute.transport, 'resources', unavailable_resources)
    if background:
        engine.compute._monitor()
    else:
        engine.compute.refresh()
    observed = engine.compute.registry.observations['fixture']
    assert observed['ram_available_bytes'] is None
    assert observed['vram_free_bytes'] is None
    assert observed['gpu_measurement'] is None
    assert observed['resource_sampled_at'] is None
    assert engine.compute.transport.calls == []
