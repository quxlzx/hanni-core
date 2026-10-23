"""Bounded pure-inference retries keep identity, privacy and verification intact."""
import pytest
from hanni.models.adaptive import ModelSelectionError
from hanni.models.client import ModelUnavailableError
from scripts.campaign5_intelligence.controlled import controlled_engine, request, MESSAGES

@pytest.fixture
def engine(tmp_path):
    with controlled_engine(tmp_path) as value:
        value.compute.registry.record_context_verified('controlled', target_tokens=8192, prompt_tokens=7600, model_id='controlled.gguf', prompt_sha256='a' * 64, response_sha256='b' * 64)
        yield value

@pytest.mark.parametrize('failure', ['timeout', 'unavailable', 'rejected_output'])
def test_pure_inference_failure_has_one_bounded_native_fallback(engine, monkeypatch, failure):
    entries = []

    def local(*args, **kwargs):
        entries.append('local')
        if failure == 'timeout':
            raise TimeoutError('Controlled timeout.')
        if failure == 'unavailable':
            raise ModelUnavailableError('Controlled unavailable endpoint.')
        return 'unverified controlled draft'
    monkeypatch.setattr('hanni.models.adaptive._BoundedInferenceClient.chat', local)
    result = engine.execute(MESSAGES, request=request(), validator=lambda value: value == 'controlled source value')
    assert result == 'controlled source value'
    assert entries == ['local']
    assert len(engine.compute.transport.calls) == 1
    decision = engine.snapshot()['decisions'][0]
    assert len(decision['fallbacks']) == 1
    assert decision['fallbacks'][0]['from_endpoint_id'] == 'local:supervisor'
    assert decision['fallbacks'][0]['to_endpoint_id'] == 'worker:controlled'
    assert decision['status'] == 'completed'

@pytest.mark.parametrize('constraint', ['pinned', 'manual', 'local_only', 'no_fallback'])
def test_native_constraints_prevent_reassignment_on_failure(engine, monkeypatch, constraint):
    monkeypatch.setattr('hanni.models.adaptive._BoundedInferenceClient.chat', lambda *args, **kwargs: (_ for _ in ()).throw(ModelUnavailableError('Controlled outage.')))
    kwargs = {'endpoint_id': 'local:supervisor'} if constraint == 'pinned' else {}
    if constraint == 'manual':
        engine.configure(policy='manual', manual_endpoint_id='local:supervisor')
    if constraint == 'no_fallback':
        kwargs['max_fallbacks'] = 0
    with pytest.raises(ModelSelectionError):
        engine.execute(MESSAGES, request=request(local_only=constraint == 'local_only'), **kwargs)
    assert engine.compute.transport.calls == []
    assert engine.snapshot()['decisions'][0]['status'] != 'completed'

def test_fallback_budget_cannot_be_increased_by_caller(engine):
    with pytest.raises(ModelSelectionError):
        engine.execute(MESSAGES, request=request(), max_fallbacks=engine._settings()['max_fallbacks'] + 1)
    assert engine.compute.transport.calls == []
