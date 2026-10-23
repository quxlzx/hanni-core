"""Deterministic eligibility, evidence integrity and original-controller fallback."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from hanni.config import load_config
from hanni.compute import ComputeRegistry, ComputeScheduler, ComputeError
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest, ModelSelectionError, install, uninstall, current, model_request_scope
from hanni.models.client import ModelProtocolError, ModelUnavailableError, ModelTurn, ModelToolCall

class Transport:

    def __init__(self):
        self.calls = []
        self.outputs = ['valid']
        self.fail = False

    def health(self, worker):
        return {'status': 'healthy', 'model_id': worker['model_id'], 'context_reported': 8192, 'last_heartbeat': 1000, 'runtime_identity': 'runtime-worker'}

    def resources(self, worker):
        return {'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 1024 ** 3, 'queue_depth': 0, 'resource_sampled_at': 1000}

    def request(self, worker, method, path, **kwargs):
        self.calls.append((worker['worker_id'], kwargs.get('payload')))
        if self.fail:
            raise ComputeError('Controlled endpoint outage.')
        return {'model': worker['model_id'], 'choices': [{'message': {'content': self.outputs.pop(0)}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 3}}

    def close(self):
        pass

@pytest.fixture
def engine(tmp_path):
    config = load_config(data_dir=tmp_path)
    spec = replace(config.models.supervisor, context_length=8192, max_tokens=64)
    config = replace(config, models=replace(config.models, models=(spec,)))
    directory = tmp_path / 'compute'
    directory.mkdir()
    worker = {'worker_id': 'fixture', 'node_id': 'other', 'remote_port': 18080, 'model_id': '/private/account/fixture-model.gguf', 'enabled': True, 'capabilities': ['analysis', 'structured_json'], 'allowed_categories': ['synthetic'], 'context_configured': 8192, 'concurrency': 1}
    (directory / 'deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [{'id': 'other', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '17')) + '', 'username': 'fixture'}], 'workers': [worker], 'policy': {}}))
    registry = ComputeRegistry(tmp_path, clock=lambda: 1000)
    registry.record_context_verified('fixture', target_tokens=8192, prompt_tokens=7600, model_id=worker['model_id'], prompt_sha256='a' * 64, response_sha256='b' * 64)
    transport = Transport()
    compute = ComputeScheduler(registry, transport=transport)

    def probe(row):
        return {'status': 'healthy', 'model_id': spec.api_model, 'context_reported': 8192, 'last_heartbeat': 1000, 'runtime_identity': 'runtime-local', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 1024 ** 3}
    result = AdaptiveModelEngine(config, compute_scheduler=compute, clock=lambda: 1000, local_probe=probe)
    result.refresh()
    yield result
    result.close()
    compute.close()

def prove(engine, key, capabilities=('text', 'structured_json', 'tool_calling')):
    engine.record_capability_evidence(key, identity=engine.endpoint_identity(key), capabilities=capabilities, context_tokens=8192, observed_prompt_tokens=7600, retrieval_passed=True, evidence_sha256='c' * 64, environment='controlled; temp0; thinkingoff')

def request(**kwargs):
    return ModelRequest(privacy_categories=frozenset({'synthetic'}), output_tokens=64, **kwargs)

def test_configured_model_and_openai_health_do_not_imply_capabilities(engine):
    selected = engine.select(request(capabilities=frozenset({'tool_calling'})))
    assert selected['endpoint'] is None
    assert 'required_capability_not_verified' in selected['excluded'][1]['reasons']
    assert all((not row['capabilities'] for row in engine.snapshot()['endpoints']))

def test_verified_identity_context_and_capability_required_before_remote_selection(engine):
    prove(engine, 'worker:fixture', ('text', 'structured_json'))
    chosen = engine.select(request())['endpoint']
    assert chosen['endpoint_id'] == 'worker:fixture'
    assert chosen['max_context_verified'] == 8192
    assert engine.select(request(context_tokens=8192))['endpoint'] is None
    assert engine.select(request(capabilities=frozenset({'vision'})))['endpoint'] is None

@pytest.mark.parametrize('privacy', ['conversation', 'memory', 'screen', 'sensitive', 'project'])
def test_current_synthetic_only_workers_never_receive_private_context(engine, privacy):
    prove(engine, 'worker:fixture', ('text',))
    chosen = engine.select(ModelRequest(privacy_categories=frozenset({privacy}), output_tokens=64))
    assert chosen['endpoint'] is None
    assert 'privacy_not_authorized' in chosen['excluded'][1]['reasons']
    assert engine.compute.transport.calls == []

def test_manual_override_still_applies_all_filters(engine):
    prove(engine, 'worker:fixture', ('text',))
    engine.configure(policy='manual', manual_endpoint_id='worker:fixture')
    assert engine.select(ModelRequest())['endpoint'] is None
    with pytest.raises(ModelSelectionError):
        engine.configure(policy='manual', manual_endpoint_id='unknown')

@pytest.mark.parametrize('field,value', [('status', 'unhealthy'), ('last_heartbeat', 900), ('ram_available_bytes', 1024), ('vram_free_bytes', 1024), ('ram_available_bytes', None), ('queue_depth', 20)])
def test_health_resources_and_queue_pressure_remove_endpoint(engine, field, value):
    prove(engine, 'worker:fixture', ('text',))
    engine.compute.registry.observe('fixture', **{field: value})
    assert engine.select(request())['endpoint'] is None

def test_endpoint_load_and_model_mismatch_block(engine):
    prove(engine, 'worker:fixture', ('text',))
    engine.compute.registry.active['fixture'] = 1
    assert engine.select(request())['endpoint'] is None
    engine.compute.registry.active['fixture'] = 0
    engine.compute.registry.observe('fixture', model_id='swapped')
    assert engine.select(request())['endpoint'] is None

def test_profile_identity_changes_invalidate_capability_and_quality(engine):
    prove(engine, 'worker:fixture', ('text',))
    identity = engine.endpoint_identity('worker:fixture')
    engine.record_evaluation('worker:fixture', identity=identity, task_category='analysis', correct=True, verified_success=True, latency_ms=500, evidence_sha256='d' * 64, environment='unseen packet', evaluation_id='sealed-1')
    engine.compute.registry.observe('fixture', runtime_identity='different-backend-build')
    row = engine.snapshot()['endpoints'][1]
    assert row['capabilities'] == [] and row['profiles'] == {}
    with pytest.raises(ModelSelectionError):
        engine.record_capability_evidence('worker:fixture', identity=identity, capabilities=['text'], evidence_sha256='d' * 64, environment='different runtime')

def test_small_samples_do_not_outrank_the_retained_default(engine):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key, ('text',))
    for index in range(2):
        engine.record_evaluation('worker:fixture', identity=engine.endpoint_identity('worker:fixture'), task_category='analysis', correct=True, verified_success=True, latency_ms=1, evidence_sha256='d' * 64, environment='small packet', evaluation_id=f'small-{index}')
    for policy in ('balanced', 'fast', 'quality'):
        engine.configure(policy=policy)
        assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'local:supervisor'
    assert engine.snapshot()['endpoints'][1]['profiles']['analysis']['confidence'] == 'insufficient'

def test_sufficient_verified_task_history_can_select_measured_faster_worker(engine):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key, ('text',))
    for index in range(30):
        engine.record_evaluation('worker:fixture', identity=engine.endpoint_identity('worker:fixture'), task_category='analysis', correct=True, verified_success=True, latency_ms=1, evidence_sha256='d' * 64, environment='sealed independently scored sample', evaluation_id=f'large-{index}')
    engine.configure(policy='fast')
    assert engine.select(request(task_category='analysis'))['endpoint']['endpoint_id'] == 'worker:fixture'

def test_registry_persists_measured_profiles_and_never_promotes_short_context_probe(engine):
    key = 'worker:fixture'
    identity = engine.endpoint_identity(key)
    with pytest.raises(ModelSelectionError):
        engine.record_capability_evidence(key, identity=identity, capabilities=['text'], context_tokens=131072, observed_prompt_tokens=128, retrieval_passed=True, evidence_sha256='d' * 64, environment='short probe')
    prove(engine, key, ('text',))
    engine.record_evaluation(key, identity=identity, task_category='analysis', correct=False, verified_success=False, latency_ms=10, evidence_sha256='d' * 64, environment='sealed packet', evaluation_id='persisted')
    next_engine = AdaptiveModelEngine(engine.config, compute_scheduler=engine.compute, clock=lambda: 1000, local_probe=engine.local_probe)
    next_engine.refresh()
    assert next_engine.snapshot()['endpoints'][1]['profiles']['analysis']['accuracy'] == 0
    next_engine.close()

def test_duplicate_evaluation_ids_are_bound_and_cannot_inflate_accuracy(engine):
    key = 'worker:fixture'
    identity = engine.endpoint_identity(key)
    options = dict(identity=identity, task_category='analysis', correct=True, verified_success=True, latency_ms=10, evidence_sha256='d' * 64, environment='packet', evaluation_id='same')
    engine.record_evaluation(key, **options)
    engine.record_evaluation(key, **options)
    assert engine.snapshot()['endpoints'][1]['profiles']['analysis']['sample_count'] == 1
    with pytest.raises(ModelSelectionError):
        engine.record_evaluation(key, **dict(options, correct=False))

def test_public_snapshot_contains_no_remote_model_path_or_private_user_content(engine):
    prove(engine, 'worker:fixture', ('text',))
    result = engine.execute([{'role': 'user', 'content': 'sealed synthetic number 42'}], request=request(), validator=lambda value: value == 'valid')
    assert result == 'valid'
    text = json.dumps(engine.snapshot())
    assert '/private/account/' not in text
    assert 'sealed synthetic number 42' not in text
    assert '' + '.'.join(('100', '64', '0', '17')) + '' not in text

def test_remote_request_uses_original_compute_receipt_and_external_validator(engine):
    prove(engine, 'worker:fixture', ('text',))
    result = engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request(), validator=lambda value: value == 'valid')
    assert result == 'valid'
    jobs = engine.compute.registry.jobs()
    assert len(jobs) == 1 and jobs[0]['state'] == 'VERIFIED'
    assert engine.snapshot()['decisions'][0]['status'] == 'completed'
    profile = engine.snapshot()['endpoints'][1]['profiles']['conversation']
    assert profile['accuracy'] is None and profile['verified_success_count'] == 0

def test_transport_failure_falls_back_without_replaying_tool_operations(engine, monkeypatch):
    prove(engine, 'local:supervisor', ('text',))
    prove(engine, 'worker:fixture', ('text',))
    calls = []

    def chat(self, messages, **kwargs):
        calls.append(self.spec.id)
        raise ModelUnavailableError('controlled outage')
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', chat)
    result = engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request(), validator=lambda value: value == 'valid')
    assert result == 'valid' and calls == ['supervisor']
    event = engine.snapshot()['decisions'][0]
    assert event['fallbacks'][0] == {'from_endpoint_id': 'local:supervisor', 'to_endpoint_id': 'worker:fixture', 'trigger': 'endpoint_failed_or_timeout'}

def test_private_fallback_does_not_use_unauthorized_remote(engine, monkeypatch):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key, ('text',))
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', lambda *args, **kwargs: (_ for _ in ()).throw(ModelUnavailableError('down')))
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'private email'}], request=ModelRequest(output_tokens=64))
    assert engine.compute.transport.calls == []

def test_structured_verification_failure_can_fall_back_pure_inference(engine, monkeypatch):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key, ('text', 'structured_json'))
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', lambda *args, **kwargs: 'invalid')
    result = engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request(capabilities=frozenset({'structured_json'})), validator=lambda value: value == 'valid')
    assert result == 'valid'
    assert engine.snapshot()['decisions'][0]['fallbacks'][0]['trigger'] == 'verification_failed'

def test_manual_failure_never_silently_ignores_override(engine, monkeypatch):
    prove(engine, 'local:supervisor', ('text',))
    prove(engine, 'worker:fixture', ('text',))
    engine.configure(policy='manual', manual_endpoint_id='local:supervisor')
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', lambda *args, **kwargs: (_ for _ in ()).throw(ModelUnavailableError('down')))
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request())
    assert engine.compute.transport.calls == []

def test_schema_budget_is_added_to_messages_and_output(engine):
    prove(engine, 'worker:fixture', ('text',))
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'x' * 5000}], request=request(schema_tokens=4000))
    assert engine.compute.transport.calls == []

def test_legacy_default_is_explicit_never_proves_context_or_vision(engine):
    selected = engine.select(ModelRequest(allow_legacy_default=True, output_tokens=64))
    assert selected['endpoint']['endpoint_id'] == 'local:supervisor'
    assert 'legacy' in selected['reason'] and selected['endpoint']['max_context_verified'] is None
    assert engine.select(ModelRequest(allow_legacy_default=True, capabilities=frozenset({'vision'}), output_tokens=64))['endpoint'] is None
    assert engine.select(ModelRequest(allow_legacy_default=True, context_tokens=90000, output_tokens=64))['endpoint'] is None

@pytest.mark.parametrize('format_field,format_value,capability', [('response_format', 'json_schema', 'structured_json'), ('tool_calling_format', 'openai_function', 'tool_calling')])
def test_legacy_default_reason_identifies_unverified_native_format(engine, format_field, format_value, capability):
    prove(engine, 'local:supervisor', ('text', capability))
    selection = engine.select(ModelRequest(allow_legacy_default=True, output_tokens=64, capabilities=frozenset({'text', capability}), **{format_field: format_value}))
    assert selection['endpoint']['endpoint_id'] == 'local:supervisor'
    assert 'unverified legacy' in selection['reason'] and 'format' in selection['reason']

def test_original_controller_admission_is_rechecked_and_never_retried(engine):
    prove(engine, 'worker:fixture', ('text',))
    calls = []

    def admission():
        calls.append(1)
        raise RuntimeError('permission withdrawn')
    with pytest.raises(RuntimeError):
        engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request(), admission=admission)
    assert calls == [1] and engine.compute.transport.calls == []
    assert engine.snapshot()['decisions'][0]['status'] == 'blocked'

def test_runtime_globals_are_isolated_by_authoritative_data_root(engine, tmp_path):
    other_config = replace(engine.config, paths=replace(engine.config.paths, data_dir=tmp_path / 'isolated'))
    other = AdaptiveModelEngine(other_config)
    try:
        install(engine)
        install(other)
        assert current(engine.config) is engine and current(other_config) is other and (current() is None)
        uninstall(other)
        assert current(engine.config) is engine
    finally:
        other.close()
        uninstall(engine)

@pytest.mark.parametrize('value', [1, 'true', float('nan')])
def test_nonboolean_accuracy_and_nonfinite_measurements_are_rejected(engine, value):
    with pytest.raises(ModelSelectionError):
        engine.record_evaluation('worker:fixture', identity=engine.endpoint_identity('worker:fixture'), task_category='analysis', correct=value, verified_success=None, latency_ms=1, evidence_sha256='d' * 64, environment='packet')

def test_actual_output_budget_cannot_exceed_measured_context_by_understating_request(engine):
    prove(engine, 'worker:fixture', ('text',))
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'x' * 1000}], request=ModelRequest(output_tokens=1, privacy_categories=frozenset({'synthetic'})), max_tokens=8192)
    assert engine.compute.transport.calls == []

def test_actual_format_and_schema_cannot_bypass_format_evidence(engine):
    prove(engine, 'worker:fixture', ('text', 'structured_json'))
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request(), response_format={'type': 'json_schema', 'json_schema': {'schema': {'type': 'object'}}})
    assert engine.compute.transport.calls == []

def test_local_full_weights_digest_changes_for_same_path_tensor_replacement(engine, tmp_path):
    path = tmp_path / 'fixture.gguf'
    path.write_bytes(b'GGUF' + b'a' * 131072)
    before = engine._weights_identity(str(path))
    path.write_bytes(b'GGUF' + b'a' * 65536 + b'b' * 65536)
    after = engine._weights_identity(str(path))
    assert before['sha256'] != after['sha256']
    assert engine._weights_identity(str(path)) == after

def test_cold_wrapper_refreshes_original_primary_before_first_inference(engine, monkeypatch):
    engine.observations.clear()
    adapter = engine.wrap_client(SimpleNamespace(spec=engine.config.models.supervisor))
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', lambda *args, **options: 'hello')
    assert adapter.chat([{'role': 'user', 'content': 'hello'}]) == 'hello'
    assert engine.observations['local:supervisor']['status'] == 'healthy'

def test_closed_snapshot_does_not_reopen_persistent_database(engine):
    engine.close()
    assert engine.snapshot()['available'] is False and engine.db is None

def test_model_routing_configuration_validation_preserves_resource_and_sample_bounds():
    from hanni.config.schema import parse_hanni, ConfigError
    for field, value in [('max_fallbacks', 3), ('minimum_samples', 1), ('max_queue_seconds', float('nan')), ('minimum_accuracy_lower_bound', float('inf'))]:
        with pytest.raises(ConfigError):
            parse_hanni({'hanni': {}, 'model_routing': {field: value}})
    valid = parse_hanni({'hanni': {}, 'model_routing': {'max_fallbacks': 0, 'max_queue_seconds': 2}})
    assert valid.model_routing.max_fallbacks == 0 and valid.model_routing.max_queue_seconds == 2

def test_verified_native_worker_format_does_not_enable_unsupported_transport_operations(engine):
    engine.record_capability_evidence('worker:fixture', identity=engine.endpoint_identity('worker:fixture'), capabilities=['text', 'tool_calling'], context_tokens=8192, observed_prompt_tokens=7600, retrieval_passed=True, metadata={'tool_calling_formats': ['openai_function']}, evidence_sha256='e' * 64, environment='native format controlled probe')
    engine.configure(policy='manual', manual_endpoint_id='worker:fixture')
    selection = engine.select(request(capabilities=frozenset({'tool_calling'}), tool_calling_format='openai_function'))
    assert selection['endpoint'] is None
    assert 'transport_unsupported_tool_or_vision' in selection['excluded'][1]['reasons']
    assert engine.compute.transport.calls == []

@pytest.mark.parametrize('image_type', ['image_url', 'input_image'])
def test_actual_image_payload_cannot_use_text_request_to_bypass_modality_check(engine, image_type):
    prove(engine, 'worker:fixture', ('text',))
    with pytest.raises(ModelSelectionError, match='multimodal'):
        engine.execute([{'role': 'user', 'content': [{'type': image_type, 'image_url': 'data:image/png;base64,AAAA'}]}], request=request())
    assert engine.compute.transport.calls == []

def test_resource_observations_persist_per_category_without_inventing_unknowns(engine):
    key = 'worker:fixture'
    identity = engine.endpoint_identity(key)
    options = dict(identity=identity, task_category='analysis', correct=None, verified_success=None, latency_ms=10, evidence_sha256='a' * 64, environment='measured resources')
    engine.record_evaluation(key, **options, evaluation_id='old-format')
    engine.record_evaluation(key, **options, evaluation_id='with-resources', resource_observations={'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': None, 'current_requests': 0, 'queue_depth': 2, 'sampled_at': 1000})
    reader = AdaptiveModelEngine(engine.config, compute_scheduler=engine.compute, clock=lambda: 1000, local_probe=engine.local_probe)
    try:
        reader.refresh()
        profile = reader.snapshot()['endpoints'][1]['profiles']['analysis']
        assert profile['sample_count'] == 2 and profile['resource_sample_count'] == 1
        assert profile['resource_observations']['ram_available_bytes'] == {'sample_count': 1, 'mean': 8 * 1024 ** 3, 'min': 8 * 1024 ** 3, 'max': 8 * 1024 ** 3}
        assert profile['resource_observations']['vram_free_bytes'] == {'sample_count': 0, 'mean': None, 'min': None, 'max': None}
        assert profile['resource_observations']['current_requests']['mean'] == 0
        assert reader.snapshot()['endpoints'][1]['ram_requirement_bytes'] is None
        reader.record_evaluation(key, **options, evaluation_id='old-format')
        row = reader._connect().execute('SELECT payload FROM measurements WHERE id=?', ('old-format',)).fetchone()
        assert 'resource_observations' not in json.loads(row[0])
    finally:
        reader.close()

@pytest.mark.parametrize('field,value', [('ram_available_bytes', -1), ('ram_available_bytes', 2 ** 51), ('vram_free_bytes', float('nan')), ('current_requests', True), ('queue_depth', 1.5), ('queue_depth', 1000001), ('sampled_at', float('inf')), ('sampled_at', -1), ('unexpected', 0)])
def test_invalid_resource_observations_cannot_be_persisted(engine, field, value):
    with pytest.raises(ModelSelectionError):
        engine.record_evaluation('worker:fixture', identity=engine.endpoint_identity('worker:fixture'), task_category='analysis', correct=None, verified_success=None, latency_ms=1, evidence_sha256='a' * 64, environment='invalid resource observation', resource_observations={field: value})
    assert 'analysis' not in engine.snapshot()['endpoints'][1]['profiles']

def test_runtime_attempts_record_actual_admission_headroom_and_load(engine, monkeypatch):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key, ('text',))
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', lambda *args, **options: (_ for _ in ()).throw(ModelUnavailableError('controlled outage')))
    assert engine.execute([{'role': 'user', 'content': 'synthetic'}], request=request()) == 'valid'
    for row in engine.snapshot()['endpoints']:
        profile = row['profiles']['conversation']
        assert profile['resource_sample_count'] == 1
        assert profile['resource_observations']['ram_available_bytes']['mean'] == 8 * 1024 ** 3
        assert profile['resource_observations']['vram_free_bytes']['mean'] == 1024 ** 3
        assert profile['resource_observations']['current_requests']['mean'] == 0
    local, remote = engine.snapshot()['endpoints']
    assert local['profiles']['conversation']['resource_observations']['queue_depth']['mean'] is None
    assert remote['profiles']['conversation']['resource_observations']['queue_depth']['mean'] == 0

def test_local_stream_records_actual_resource_observations_without_claiming_correctness(engine):
    original = SimpleNamespace(spec=engine.config.models.supervisor, stream_chat=lambda *args, **options: iter(['hello', ' there']))
    assert ''.join(engine.wrap_client(original).stream_chat([{'role': 'user', 'content': 'hello'}])) == 'hello there'
    profile = engine.snapshot()['endpoints'][0]['profiles']['conversation']
    assert profile['resource_sample_count'] == 1
    assert profile['resource_observations']['ram_available_bytes']['mean'] == 8 * 1024 ** 3
    assert profile['accuracy'] is None and profile['correctness_sample_count'] == 0

def test_closed_local_stream_records_partial_cancellation_without_retry(engine):
    calls = []

    def stream(*args, **options):
        calls.append(1)
        yield 'first'
        yield 'second'
    original = SimpleNamespace(spec=engine.config.models.supervisor, stream_chat=stream)
    result = engine.wrap_client(original).stream_chat([{'role': 'user', 'content': 'hello'}])
    assert next(result) == 'first'
    result.close()
    assert calls == [1] and engine.compute.transport.calls == []
    assert engine.active['local:supervisor'] == 0
    snapshot = engine.snapshot()
    assert snapshot['decisions'][0]['status'] == 'cancelled_after_partial'
    profile = snapshot['endpoints'][0]['profiles']['conversation']
    assert profile['sample_count'] == profile['resource_sample_count'] == 1
    assert profile['error_count'] == profile['correctness_sample_count'] == 0
    assert profile['accuracy'] is None
