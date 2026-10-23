"""Independent controlled eligibility/fault audit; fixtures are not model benchmarks."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import pytest
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.compute.registry import ComputeError
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest, ModelSelectionError
from hanni.models.client import ModelUnavailableError
from tests.helpers import write_config_dir

@pytest.fixture
def audit_engine(tmp_path):
    state = tmp_path / 'state'
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=state, env={})
    protected = state / 'compute'
    protected.mkdir(parents=True)
    deployment = {'version': 1, 'enabled': True, 'nodes': [{'id': 'remote-fixture'}], 'workers': [{'worker_id': 'remote-fixture', 'node_id': 'remote-fixture', 'remote_port': 19991, 'model_id': 'synthetic-control-model', 'protocol': 'llama_cpp', 'enabled': True, 'context_configured': 8192, 'allowed_categories': ['synthetic'], 'capabilities': ['analysis', 'structured_json'], 'concurrency': 1}], 'policy': {'timeout_seconds': 10, 'max_retries': 1}}
    (protected / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8')
    registry = ComputeRegistry(state, clock=lambda: 1000)
    remote_response = {'model': 'synthetic-control-model', 'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 5}}
    calls = []

    class Transport:

        def health(self, worker):
            return {'status': 'healthy', 'model_id': worker['model_id'], 'last_heartbeat': 1000, 'context_reported': 8192, 'runtime_identity': 'remote-fixture-runtime'}

        def resources(self, worker):
            return {'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 2 * 1024 ** 3, 'resource_sampled_at': registry.clock()}

        def request(self, worker, method, path, **options):
            calls.append((worker['worker_id'], deepcopy({k: v for k, v in options.items() if k != 'cancel'})))
            return deepcopy(remote_response)

        def close(self):
            pass

        def cancel(self, **kwargs):
            pass
    compute = ComputeScheduler(registry, transport=Transport())

    def local_probe(row):
        return {'status': 'healthy', 'model_id': config.models.supervisor.api_model, 'last_heartbeat': 1000, 'context_reported': 16384, 'runtime_identity': 'local-fixture-runtime', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 2 * 1024 ** 3}
    engine = AdaptiveModelEngine(config, compute_scheduler=compute, clock=lambda: 1000, local_probe=local_probe)
    engine.refresh()
    registry.record_context_verified('remote-fixture', target_tokens=8192, prompt_tokens=7800, model_id='synthetic-control-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
    for key, capacity in [('local:supervisor', 16384), ('worker:remote-fixture', 8192)]:
        engine.record_capability_evidence(key, identity=engine.endpoint_identity(key), capabilities=['text', 'structured_json'] + (['tool_calling'] if key.startswith('local:') else []), context_tokens=capacity, observed_prompt_tokens=int(0.95 * capacity), retrieval_passed=True, evidence_sha256='a' * 64, environment='controlled fixture; not live performance')
    yield (engine, compute, calls, remote_response)
    engine.close()
    compute.close()

@pytest.mark.parametrize('policy', ['balanced', 'fast', 'quality', 'manual'])
@pytest.mark.parametrize('category', ['synthetic', 'project', 'conversation', 'memory', 'screen', 'sensitive'])
@pytest.mark.parametrize('local_only', [False, True])
def test_controlled_eligibility_matrix_never_forwards_unauthorized_context(audit_engine, policy, category, local_only):
    engine, _, _, _ = audit_engine
    engine.configure(policy=policy, manual_endpoint_id='worker:remote-fixture' if policy == 'manual' else None)
    req = ModelRequest(privacy_categories=frozenset({category}), local_only=local_only, context_tokens=900, output_tokens=100)
    result = engine.select(req)
    if policy == 'manual' and (category != 'synthetic' or local_only):
        assert result['endpoint'] is None
    else:
        row = result['endpoint']
        assert row is not None
        assert set(req.privacy_categories) <= set(row['allowed_categories'])
        assert not local_only or row['local']
        assert row['max_context_verified'] >= req.context_tokens + req.output_tokens

@pytest.mark.parametrize('tokens', [16384, 32768, 90000, 131072])
def test_controlled_verified_context_is_not_replaced_by_allocation(audit_engine, tokens):
    engine, _, _, _ = audit_engine
    result = engine.select(ModelRequest(context_tokens=tokens, output_tokens=1, privacy_categories=frozenset({'synthetic'})))
    assert result['endpoint'] is None
    assert all(('required_context_not_verified' in row['reasons'] for row in result['excluded']))

def test_controlled_vision_not_inferred_from_openai_api(audit_engine):
    engine, _, _, _ = audit_engine
    assert engine.select(ModelRequest(capabilities=frozenset({'vision'}), privacy_categories=frozenset({'screen'})))['endpoint'] is None

def test_controlled_unknown_remote_memory_prevents_selection(audit_engine):
    engine, compute, _, _ = audit_engine
    compute.registry.observations['remote-fixture']['vram_free_bytes'] = None
    engine.configure(policy='manual', manual_endpoint_id='worker:remote-fixture')
    result = engine.select(ModelRequest(privacy_categories=frozenset({'synthetic'})))
    assert result['endpoint'] is None
    assert 'resource_measurement_unknown' in result['excluded'][1]['reasons']

def test_controlled_health_stale_or_wrong_identity_prevents_override(audit_engine):
    engine, compute, _, _ = audit_engine
    engine.configure(policy='manual', manual_endpoint_id='worker:remote-fixture')
    compute.registry.observe('remote-fixture', model_id='not-the-registered-model')
    assert engine.select(ModelRequest(privacy_categories=frozenset({'synthetic'})))['endpoint'] is None
    compute.registry.observe('remote-fixture', model_id='synthetic-control-model', last_heartbeat=969)
    assert engine.select(ModelRequest(privacy_categories=frozenset({'synthetic'})))['endpoint'] is None

def test_controlled_privacy_forbids_fallback_after_local_failure(audit_engine, monkeypatch):
    engine, _, calls, _ = audit_engine
    local_calls = []

    def fail(client, messages, **options):
        local_calls.append(messages)
        raise ModelUnavailableError('Controlled local endpoint outage')
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', fail)
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'PRIVATE_SENTINEL_v40_83a'}], request=ModelRequest(privacy_categories=frozenset({'memory', 'sensitive'})))
    assert len(local_calls) == 1
    assert calls == []
    stored = (engine.root / 'profiles.sqlite3').read_bytes()
    assert b'PRIVATE_SENTINEL_v40_83a' not in stored

def test_controlled_invalid_output_can_retry_inference_without_executing_tools(audit_engine, monkeypatch):
    engine, _, calls, _ = audit_engine
    local_calls = []

    def invalid(client, messages, **options):
        local_calls.append(messages)
        return '{"ok":false}'
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.chat', invalid)
    result = engine.execute([{'role': 'user', 'content': 'Synthetic verification probe'}], request=ModelRequest(privacy_categories=frozenset({'synthetic'})), validator=lambda value: json.loads(value) == {'ok': True})
    assert json.loads(result) == {'ok': True}
    assert len(local_calls) == len(calls) == 1
    snapshot = engine.snapshot()
    assert snapshot['decisions'][0]['fallbacks'][0]['trigger'] == 'verification_failed'
    assert snapshot['decisions'][0]['fallbacks'][0]['to_endpoint_id'] == 'worker:remote-fixture'

def test_controlled_remote_wrong_response_model_is_rejected(audit_engine, monkeypatch):
    engine, _, calls, response = audit_engine
    engine.configure(policy='manual', manual_endpoint_id='worker:remote-fixture')
    response['model'] = 'alien-model'
    with pytest.raises(ModelSelectionError):
        engine.execute([{'role': 'user', 'content': 'Synthetic identity check'}], request=ModelRequest(privacy_categories=frozenset({'synthetic'})))
    assert len(calls) == 1

def test_controlled_messages_and_tool_schema_share_context_budget(audit_engine, monkeypatch):
    engine, _, _, _ = audit_engine
    calls = []
    fake = SimpleNamespace(spec=engine.config.models.supervisor)
    adapter = engine.wrap_client(fake)
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.complete_with_tools', lambda *args, **kwargs: calls.append(kwargs))
    messages = [{'role': 'user', 'content': 'x' * 9500}]
    tools = [{'type': 'function', 'function': {'name': 'synthetic_read', 'description': 'y' * 9500, 'parameters': {'type': 'object'}}}]
    with pytest.raises(ModelSelectionError):
        adapter.complete_with_tools(messages, tools=tools)
    assert not calls

def test_controlled_runtime_change_invalidates_measured_capabilities(audit_engine):
    engine, _, _, _ = audit_engine
    before = engine.endpoint_identity('local:supervisor')
    engine.observations['local:supervisor']['runtime_identity'] = 'different-file-same-alias'
    assert engine.endpoint_identity('local:supervisor') != before
    row = next((row for row in engine.snapshot()['endpoints'] if row['endpoint_id'] == 'local:supervisor'))
    assert row['capabilities'] == []
    assert row['max_context_verified'] is None

def test_controlled_minimal_samples_do_not_certify_quality(audit_engine):
    engine, _, _, _ = audit_engine
    key = 'worker:remote-fixture'
    engine.record_evaluation(key, identity=engine.endpoint_identity(key), task_category='analysis', correct=True, verified_success=True, latency_ms=1, evidence_sha256='b' * 64, environment='controlled fixture, one example', evaluation_id='one-only')
    profile = next((row for row in engine.snapshot()['endpoints'] if row['endpoint_id'] == key))['profiles']['analysis']
    assert profile['confidence'] == 'insufficient'
    assert profile['accuracy_lower_bound'] < 0.7
    assert engine.select(ModelRequest(task_category='analysis', privacy_categories=frozenset({'synthetic'})))['endpoint']['local']

def test_controlled_original_host_never_replays_uncertain_write_with_adaptive_client(audit_engine, monkeypatch):
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    from hanni.models.client import ModelTurn, ModelToolCall
    from hanni.tools.registry import build_default_registry
    from hanni.tools.base import ToolResult
    engine, _, remote_calls, _ = audit_engine
    registry = build_default_registry(engine.config)
    writes = []
    original = registry.get('app.open')
    registry.unregister('app.open', expected=original)

    def uncertain(arguments, context, request):
        writes.append(dict(arguments))
        return ToolResult('app.open', False, 'Controlled response lost after a possible write.', error={'code': 'TIMEOUT', 'retryable': True})
    registry.register(replace(original, handler=uncertain))

    def repeated(client, messages, **options):
        return ModelTurn('', (ModelToolCall('same-intent', McpHost._wire_name('app.open'), {'app': 'Notepad'}),))
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.complete_with_tools', repeated)
    adapter = engine.wrap_client(SimpleNamespace(spec=engine.config.models.supervisor))

    class Fallback:
        history = ()

        def stream_response(self, *args, **kwargs):
            yield 'Controlled fallback.'

        def record_turn(self, *args, **kwargs):
            pass
    session = McpToolSession(Fallback(), adapter, McpHost(registry, read_only=True, allowed_actions=('app.open',)))
    try:
        answer = ''.join(session.stream_response('open notepad'))
        assert len(writes) == 1
        assert remote_calls == []
        assert session.last_trace['verification_status'] == 'UNVERIFIED'
        assert 'successfully opened' not in answer.lower()
    finally:
        if registry.context.reliability:
            registry.context.reliability.close()

def test_controlled_remote_override_cannot_execute_local_tools(audit_engine, monkeypatch):
    engine, _, calls, _ = audit_engine
    engine.record_capability_evidence('worker:remote-fixture', identity=engine.endpoint_identity('worker:remote-fixture'), capabilities=['tool_calling'], evidence_sha256='e' * 64, environment='controlled native-format proof; analysis-only transport remains authoritative', metadata={'tool_calling_formats': ['openai_function']})
    engine.configure(policy='manual', manual_endpoint_id='worker:remote-fixture')
    adapter = engine.wrap_client(SimpleNamespace(spec=engine.config.models.supervisor))
    with pytest.raises(ModelSelectionError):
        adapter.complete_with_tools([{'role': 'user', 'content': 'Synthetic diagnostic'}], tools=[{'type': 'function', 'function': {'name': 'synthetic_read', 'parameters': {'type': 'object'}}}])
    assert not calls

def test_controlled_native_callback_inherits_selected_output_budget(audit_engine, monkeypatch):
    from hanni.models.client import ModelTurn
    engine, _, _, _ = audit_engine
    observed = []

    def native(client, messages, **options):
        observed.append(options.get('max_tokens', client.spec.max_tokens))
        return ModelTurn('Controlled output.')
    monkeypatch.setattr('hanni.models.adaptive.LlamaCppClient.complete_with_tools', native)
    engine.execute([{'role': 'user', 'content': 'Synthetic controlled callback'}], request=ModelRequest(output_tokens=31, privacy_categories=frozenset({'synthetic'})), local_operation=lambda client: client.complete_with_tools([], tools=[]))
    assert observed == [31]

@pytest.mark.parametrize('change', ['weights', 'build', 'quantization', 'template', 'kv_key', 'kv_value'])
def test_controlled_same_alias_and_filename_do_not_reuse_prior_identity(audit_engine, tmp_path, change):
    old, _, _, _ = audit_engine
    weights = tmp_path / old.config.models.supervisor.model_file
    weights.write_bytes(b'GGUF' + b'A' * 256)
    props = {'model_path': str(weights), 'model_alias': old.config.models.supervisor.api_model, 'model_ftype': 'Q4_K - Medium', 'chat_template': 'fixture original template', 'modalities': {'vision': False}, 'build_info': 'fixture-build-one', 'default_generation_settings': {'n_ctx': 16384}}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            body = {'status': 'ok'} if self.path == '/health' else {'data': [{'id': old.config.models.supervisor.api_model}]} if self.path == '/v1/models' else props
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    spec = replace(old.config.models.supervisor, endpoint=f'http://127.0.0.1:{server.server_port}/v1')
    config = replace(old.config, models=replace(old.config.models, models=(spec,)))
    engine = AdaptiveModelEngine(config, data_dir=tmp_path / 'actual-probe-control')
    try:
        engine.refresh()
        before = engine.endpoint_identity('local:supervisor')
        engine.record_capability_evidence('local:supervisor', identity=before, capabilities=['text'], context_tokens=16384, observed_prompt_tokens=15600, retrieval_passed=True, evidence_sha256='c' * 64, environment='controlled file and HTTP identity fixture')
        engine.record_evaluation('local:supervisor', identity=before, task_category='analysis', correct=True, verified_success=True, latency_ms=1, evidence_sha256='d' * 64, environment='controlled file and HTTP identity fixture', evaluation_id='fixture-before-change')
        if change == 'weights':
            weights.write_bytes(b'GGUF' + b'B' * 256)
        elif change == 'build':
            props['build_info'] = 'fixture-build-two'
        elif change == 'quantization':
            props['model_ftype'] = 'IQ3_S'
        elif change == 'template':
            props['chat_template'] = 'fixture replacement template'
        elif change == 'kv_key':
            engine.config = replace(config, models=replace(config.models, models=(replace(spec, kv_key_type='f16'),)))
        elif change == 'kv_value':
            engine.config = replace(config, models=replace(config.models, models=(replace(spec, kv_value_type='f16'),)))
        engine.refresh()
        assert engine.endpoint_identity('local:supervisor') != before
        row = engine.snapshot()['endpoints'][0]
        assert row['capabilities'] == []
        assert row['max_context_verified'] is None
        assert row['profiles'] == {}
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        thread.join(2)

def test_controlled_resource_history_cannot_certify_quality_or_fill_unknown_headroom(audit_engine):
    engine, compute, _, _ = audit_engine
    endpoint = 'worker:remote-fixture'
    for item in range(25):
        engine.record_evaluation(endpoint, identity=engine.endpoint_identity(endpoint), task_category='conversation', correct=None, verified_success=None, latency_ms=1, evidence_sha256='e' * 64, environment='controlled ungraded headroom history', evaluation_id=f'ungraded-resource-{item}', resource_observations={'ram_available_bytes': 2 ** 40, 'vram_free_bytes': None, 'current_requests': 0})
    remote = next((row for row in engine.snapshot()['endpoints'] if row['endpoint_id'] == endpoint))
    profile = remote['profiles']['conversation']
    assert profile['sample_count'] == profile['resource_sample_count'] == 25
    assert profile['correctness_sample_count'] == 0
    assert profile['accuracy'] is profile['accuracy_lower_bound'] is None
    assert profile['confidence'] == 'insufficient'
    assert profile['resource_observations']['vram_free_bytes'] == {'sample_count': 0, 'mean': None, 'min': None, 'max': None}
    engine.configure(policy='quality')
    assert engine.select(ModelRequest(privacy_categories=frozenset({'synthetic'})))['endpoint']['local']
    compute.registry.observations['remote-fixture']['ram_available_bytes'] = None
    engine.configure(policy='manual', manual_endpoint_id=endpoint)
    result = engine.select(ModelRequest(privacy_categories=frozenset({'synthetic'})))
    assert result['endpoint'] is None
    assert any(('resource_measurement_unknown' in row['reasons'] for row in result['excluded']))

def test_controlled_cancelled_stream_releases_resource_and_does_not_store_private_text(audit_engine):
    engine, _, calls, _ = audit_engine
    events = []

    def stream(*args, **kwargs):
        events.append('started')
        try:
            yield 'PRIVATE_OUTPUT_SENTINEL_61c8'
            events.append('unwanted_resume')
            yield 'second'
        finally:
            events.append('closed')
    original = SimpleNamespace(spec=engine.config.models.supervisor, stream_chat=stream)
    response = engine.wrap_client(original).stream_chat([{'role': 'user', 'content': 'PRIVATE_INPUT_SENTINEL_61c8'}])
    assert next(response) == 'PRIVATE_OUTPUT_SENTINEL_61c8'
    assert engine.active['local:supervisor'] == 1
    response.close()
    assert events == ['started', 'closed']
    assert engine.active['local:supervisor'] == 0 and calls == []
    snapshot = engine.snapshot()
    assert snapshot['decisions'][0]['status'] == 'cancelled_after_partial'
    assert snapshot['decisions'][0]['fallbacks'] == []
    profile = snapshot['endpoints'][0]['profiles']['conversation']
    assert profile['correctness_sample_count'] == profile['error_count'] == 0
    assert profile['resource_observations']['current_requests']['mean'] == 0
    assert profile['resource_observations']['queue_depth']['mean'] is None
    for payload, in engine._connect().execute('SELECT payload FROM measurements UNION ALL SELECT payload FROM decisions'):
        assert 'PRIVATE_INPUT_SENTINEL_61c8' not in payload
        assert 'PRIVATE_OUTPUT_SENTINEL_61c8' not in payload

def test_controlled_partial_stream_failure_records_unknown_resources_without_replay(audit_engine):
    engine, _, calls, _ = audit_engine
    engine.observations['local:supervisor']['ram_available_bytes'] = None
    engine.observations['local:supervisor']['vram_free_bytes'] = None
    started = []

    def stream(*args, **kwargs):
        started.append(1)
        yield 'PRIVATE_PARTIAL_SENTINEL_447b'
        raise ModelUnavailableError('PRIVATE_ERROR_SENTINEL_447b')
    original = SimpleNamespace(spec=engine.config.models.supervisor, stream_chat=stream)
    response = engine.wrap_client(original).stream_chat([{'role': 'user', 'content': 'PRIVATE_PROMPT_SENTINEL_447b'}])
    assert next(response) == 'PRIVATE_PARTIAL_SENTINEL_447b'
    with pytest.raises(ModelUnavailableError):
        next(response)
    assert started == [1] and calls == []
    assert engine.active['local:supervisor'] == 0
    snapshot = engine.snapshot()
    assert snapshot['decisions'][0]['status'] == 'failed_after_partial'
    assert snapshot['decisions'][0]['fallbacks'] == []
    profile = snapshot['endpoints'][0]['profiles']['conversation']
    assert profile['sample_count'] == profile['error_count'] == 1
    assert profile['correctness_sample_count'] == 0 and profile['accuracy'] is None
    for field in ('ram_available_bytes', 'vram_free_bytes'):
        assert profile['resource_observations'][field] == {'sample_count': 0, 'mean': None, 'min': None, 'max': None}
    for payload, in engine._connect().execute('SELECT payload FROM measurements UNION ALL SELECT payload FROM decisions'):
        assert 'PRIVATE_' not in payload
