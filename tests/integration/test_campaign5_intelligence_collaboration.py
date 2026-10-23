"""Advisory agreement, externally graded evidence, and late withdrawal controls."""
import json
import threading
import pytest
from scripts.campaign5_intelligence.controlled import controlled_engine, request, MESSAGES

@pytest.fixture
def engine(tmp_path):
    with controlled_engine(tmp_path) as value:
        value.compute.registry.record_context_verified('controlled', target_tokens=8192, prompt_tokens=7600, model_id='controlled.gguf', prompt_sha256='a' * 64, response_sha256='b' * 64)
        yield value

def test_late_independent_verifier_cancellation_withholds_selected_output(engine):
    event = threading.Event()

    def verify(text):
        event.set()
        return {'status': 'VERIFIED', 'checks': {'synthetic_source': True}}
    result = engine.collaboration.run(MESSAGES, request=request(), preference='single', verify=verify, cancellation=event, local_operation=lambda client: 'controlled source value')
    assert result['state'] == 'cancelled'
    assert result['selected_output'] is None
    assert result['selected_endpoint_id'] is None
    assert result['final_verification']['status'] == 'UNVERIFIED'
    assert result['participants'][0]['state'] == 'cancelled'

def test_declared_context_requirement_survives_assignment_to_dispatch(engine):
    operations = []

    def progress(state):
        if state['participants'][0]['state'] == 'running':
            engine.observations['local:supervisor']['context_reported'] = 512
    result = engine.collaboration.run(MESSAGES, request=request(context_tokens=4096), preference='single', on_progress=progress, local_operation=lambda client: operations.append('entered') or 'controlled source value')
    assert result['selected_output'] is None
    assert operations == []
    assert result['participants'][0]['state'] == 'failed'

@pytest.mark.parametrize('same_answer,verification', [(True, 'UNVERIFIED'), (False, 'UNVERIFIED'), (True, 'VERIFIED'), (False, 'VERIFIED')])
def test_independent_source_verification_stays_separate_from_model_agreement(engine, same_answer, verification):
    engine.compute.transport.outputs = ['controlled source value' if same_answer else 'other controlled value']
    result = engine.collaboration.run(MESSAGES, request=request(), preference='parallel', verify=lambda text: {'status': verification, 'checks': {'synthetic_source': verification == 'VERIFIED'}}, local_operation=lambda client: 'controlled source value')
    assert result['state'] == 'completed'
    assert result['final_verification']['status'] == verification
    assert bool(result['conflicts']) is (not same_answer)
    assert len({p['endpoint_id'] for p in result['participants']}) == 2
    assert len(engine.compute.transport.calls) == 1

def test_verified_secondary_selected_over_unverified_primary(engine):
    engine.compute.transport.outputs = ['controlled exact source']
    result = engine.collaboration.run(MESSAGES, request=request(), preference='parallel', verify=lambda text: {'status': 'VERIFIED' if text == 'controlled exact source' else 'UNVERIFIED'}, local_operation=lambda client: 'unsupported controlled draft')
    assert result['selected_endpoint_id'] == 'worker:controlled'
    assert result['final_verification']['status'] == 'VERIFIED'
    assert result['conflicts'][0]['kind'] == 'different_outputs'

def test_failed_secondary_never_establishes_source_verification_or_replays_primary(engine):
    engine.compute.transport.failure = True
    calls = []
    result = engine.collaboration.run(MESSAGES, request=request(), preference='parallel', local_operation=lambda client: calls.append('entered') or 'controlled source value')
    assert result['selected_endpoint_id'] == 'local:supervisor'
    assert result['final_verification']['status'] == 'UNVERIFIED'
    assert calls == ['entered']
    assert len(engine.compute.transport.calls) == 1
    assert result['participants'][1]['state'] == 'failed'
