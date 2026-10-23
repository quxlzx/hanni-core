"""Real original SDK HTTP with controlled bytes; no physical inference provider."""
from dataclasses import replace
import pytest
from hanni.models.adaptive import ModelSelectionError
from hanni.models.client import LlamaCppClient, ModelProtocolError
from scripts.campaign5_intelligence.controlled import controlled_engine, request, MESSAGES
from scripts.campaign5_intelligence.http_identity import identity_endpoint

@pytest.mark.parametrize('mode', ['chat', 'tools', 'late_stream'])
@pytest.mark.parametrize('reported', ['controlled_expected', None, 'different_controlled_model'])
def test_original_local_http_rejects_present_mismatched_model(tmp_path, mode, reported):
    with controlled_engine(tmp_path) as engine, identity_endpoint(mode, reported) as (endpoint, calls):
        spec = replace(engine.config.models.supervisor, id='campaign5_owned_http', api_model='controlled_expected', endpoint=endpoint)
        client = LlamaCppClient(spec, max_attempts=1)

        def call():
            if mode == 'tools':
                return client.complete_with_tools(MESSAGES, tools=[{'type': 'function', 'function': {'name': 'controlled_read', 'parameters': {'type': 'object', 'properties': {'key': {'type': 'string'}}}}}])
            return client.chat(MESSAGES, max_tokens=64)
        if reported == 'different_controlled_model':
            with pytest.raises(ModelProtocolError):
                call()
        else:
            assert call()
        assert len(calls) == 1

def test_mismatched_http_identity_never_counts_as_configured_model_incorrectness(tmp_path):
    with controlled_engine(tmp_path) as engine, identity_endpoint('chat', 'different_controlled_model') as (endpoint, calls):
        spec = replace(engine.config.models.supervisor, api_model='controlled_expected', endpoint=endpoint)
        engine.config = replace(engine.config, models=replace(engine.config.models, models=(spec,)))
        engine.observations['local:supervisor']['model_id'] = 'controlled_expected'
        engine.record_capability_evidence('local:supervisor', identity=engine.endpoint_identity('local:supervisor'), capabilities=['text'], context_tokens=8192, observed_prompt_tokens=7600, retrieval_passed=True, evidence_sha256='c' * 64, environment='controlled protocol fixture; not real model evidence')
        with pytest.raises(ModelSelectionError):
            engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0)
        assert len(calls) == 1
        profile = engine.snapshot()['endpoints'][0]['profiles']['conversation']
        assert profile['error_count'] == 1
        assert profile['correctness_sample_count'] == 0
        assert profile['accuracy'] is None
        assert engine.snapshot()['decisions'][0]['fallbacks'][0]['trigger'] == 'model_identity_mismatch'
