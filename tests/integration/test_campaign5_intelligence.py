"""Original policy and result boundaries with explicitly synthetic dependencies."""
from dataclasses import replace
import threading
import pytest
from hanni.models.adaptive import ModelSelectionError
from scripts.campaign5_intelligence.controlled import controlled_engine, request, MESSAGES

@pytest.fixture
def engine(tmp_path):
    with controlled_engine(tmp_path) as value:
        yield value

@pytest.mark.parametrize('category', ['conversation', 'tool_selection', 'computer_diagnostics', 'planning', 'coding', 'analysis', 'long_context', 'memory', 'structured_output'])
@pytest.mark.parametrize('policy', ['balanced', 'fast', 'quality', 'manual'])
def test_policy_keeps_native_privacy_capability_context_and_identity_guards(engine, category, policy):
    engine.configure(policy=policy, manual_endpoint_id='worker:controlled' if policy == 'manual' else None)
    valid = request(task_category=category)
    assert engine.select(valid)['endpoint'] is not None
    for invalid in (replace(valid, context_tokens=8192), replace(valid, capabilities=frozenset({'vision'})), replace(valid, privacy_categories=frozenset({'sensitive'}), local_only=False)):
        selected = engine.select(invalid)
        if invalid.privacy_categories == frozenset({'sensitive'}) and policy != 'manual':
            assert selected['endpoint']['local']
        else:
            assert selected['endpoint'] is None
    assert engine.compute.transport.calls == []

@pytest.mark.parametrize('phase', ['before_dispatch', 'before_admit'])
def test_admission_callback_cancellation_withdraws_local_result(engine, phase):
    event = threading.Event()
    counts = {'admission': 0, 'operation': 0}

    def admission():
        counts['admission'] += 1
        if counts['admission'] == (1 if phase == 'before_dispatch' else 2):
            event.set()

    def operation(client):
        counts['operation'] += 1
        return 'controlled source value'
    with pytest.raises(ModelSelectionError):
        engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, admission=admission, cancellation=event, local_operation=operation)
    assert counts['operation'] == (0 if phase == 'before_dispatch' else 1)
    assert engine.active.get('local:supervisor', 0) == 0
    decision = engine.snapshot()['decisions'][0]
    assert decision['status'] == 'cancelled'
    assert decision['fallbacks'] == []
    assert not engine.snapshot()['endpoints'][0]['profiles']

@pytest.mark.parametrize('field,value', [('status', 'unhealthy'), ('ram_available_bytes', 1024), ('vram_free_bytes', 1024)])
def test_local_return_requires_current_eligibility(engine, field, value):

    def operation(client):
        engine.observations['local:supervisor'][field] = value
        return 'controlled source value'
    with pytest.raises(ModelSelectionError):
        engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation)
    assert engine.active.get('local:supervisor', 0) == 0
    assert engine.snapshot()['decisions'][0]['status'] != 'completed'

@pytest.mark.parametrize('endpoint', ['local:supervisor', 'worker:controlled'])
@pytest.mark.parametrize('field', ['ram_available_bytes', 'vram_free_bytes'])
@pytest.mark.parametrize('value', [False, -1, float('nan'), float('inf'), '8192'])
def test_invalid_observed_resource_never_grants_admission(engine, endpoint, field, value):
    if endpoint.startswith('local:'):
        engine.observations[endpoint][field] = value
    else:
        engine.compute.registry.observe('controlled', **{field: value})
    selected = engine.select(request(), allowed_endpoint_ids=(endpoint,))
    assert selected['endpoint'] is None
    assert engine.compute.transport.calls == []

def test_no_callback_cancellation_retains_valid_local_completion(engine):
    event = threading.Event()
    result = engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, cancellation=event, local_operation=lambda client: 'controlled source value')
    assert result == 'controlled source value'
    assert engine.snapshot()['decisions'][0]['status'] == 'completed'
    assert engine.snapshot()['endpoints'][0]['profiles']['conversation']['correctness_sample_count'] == 0

def test_cancel_during_transport_is_not_an_endpoint_failure(engine):
    event = threading.Event()

    def operation(client):
        event.set()
        return 'controlled source value'
    with pytest.raises(ModelSelectionError):
        engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, cancellation=event, local_operation=operation)
    decision = engine.snapshot()['decisions'][0]
    assert decision['status'] == 'cancelled'
    assert decision['fallbacks'] == []
    assert not engine.snapshot()['endpoints'][0]['profiles']

@pytest.mark.parametrize('change', ['queue', 'another_reservation'])
def test_new_dispatch_load_does_not_withdraw_already_returned_local_result(engine, change):

    def operation(client):
        if change == 'queue':
            engine.observations['local:supervisor']['queue_depth'] = 20
        else:
            engine.active['local:supervisor'] += 1
        return 'controlled source value'
    assert engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation) == 'controlled source value'

@pytest.mark.parametrize('refreshed_status', ['healthy', 'unhealthy'])
def test_expired_local_result_lease_requires_a_genuine_probe(tmp_path, refreshed_status):
    now = [1000]
    with controlled_engine(tmp_path, clock=lambda: now[0]) as engine:
        probes = []
        original = engine.local_probe

        def probe(row):
            probes.append('genuine controlled endpoint probe')
            return {**original(row), 'status': refreshed_status}
        engine.local_probe = probe

        def operation(client):
            now[0] += 31
            return 'controlled source value'
        if refreshed_status == 'unhealthy':
            with pytest.raises(ModelSelectionError):
                engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation)
        else:
            assert engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation) == 'controlled source value'
        assert probes == ['genuine controlled endpoint probe']
