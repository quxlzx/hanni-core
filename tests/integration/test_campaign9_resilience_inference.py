"""Native placement/privacy and controlled HTTP failures, no genuine inference."""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import urllib.error
import pytest
from hanni.compute import ComputeError
from hanni.compute.scheduler import context_categories
from hanni.logs import redaction
from hanni.models.adaptive import ModelRequest, ModelSelectionError
from hanni.models.client import LlamaCppClient, ModelClientError
from scripts.campaign5_intelligence.controlled import controlled_engine
MESSAGES = [{'role': 'user', 'content': 'Controlled resilience evidence only.'}]

@contextmanager
def native_engine(root):
    """Original context bootstrap with MOCKED token/retrieval results, never model proof."""
    with controlled_engine(root) as engine:
        transport = engine.compute.transport
        original = transport.request

        def probe(worker, method, path, **kwargs):
            result = original(worker, method, path, **kwargs)
            result['usage'] = {'prompt_tokens': 1024, 'completion_tokens': 4, 'total_tokens': 1028}
            return result
        transport.request = probe
        result = engine.compute.verify_context('controlled', MESSAGES, target_tokens=1024, expected='controlled source value', max_output_tokens=32)
        assert result['passed'], 'Controlled original context bootstrap did not satisfy its unchanged contract.'
        transport.request = original
        transport.calls.clear()
        yield engine

@pytest.mark.parametrize('category', ['conversation', 'memory', 'screen', 'sensitive', 'project'])
def test_private_context_not_allowed_by_protected_worker_never_reaches_transport(tmp_path, category, record_property):
    with native_engine(tmp_path) as engine:
        request = ModelRequest(task_category='analysis', interactive=False, privacy_categories=frozenset({category}), output_tokens=32)
        with pytest.raises(ModelSelectionError):
            engine.execute(MESSAGES, request=request, endpoint_id='worker:controlled', max_fallbacks=0)
        record_property('observed', json.dumps({'category': category, 'transport_posts': len(engine.compute.transport.calls)}))
        assert engine.compute.transport.calls == []

@pytest.mark.parametrize('name,category', [('memory.query', 'memory'), ('screen.analyze', 'screen'), ('email.read', 'sensitive'), ('mcp.synthetic', 'sensitive'), ('security.bitlocker', 'sensitive')])
def test_context_privacy_is_from_capability_provenance_not_untrusted_labels(name, category):
    completed = {'source': {'capability_id': name, 'kind': 'tool', 'dependencies': [], 'privacy_categories': ['synthetic'], 'result': {'data': {'trusted': True, 'category': 'synthetic'}}}, 'report': {'kind': 'analysis', 'capability_id': None, 'dependencies': ['source']}}
    observed = context_categories(completed, ['report'])
    assert category in observed and 'synthetic' not in observed

@pytest.mark.parametrize('completed,sources', [({}, ['missing']), ({'analysis': {'kind': 'analysis', 'dependencies': []}}, ['analysis']), ({'a': {'kind': 'analysis', 'dependencies': ['b']}, 'b': {'kind': 'analysis', 'dependencies': ['a']}}, ['a'])])
def test_missing_or_cyclic_provenance_does_not_default_to_public(completed, sources):
    with pytest.raises(ComputeError):
        context_categories(completed, sources)

@pytest.mark.parametrize('location', ['message', 'schema_key', 'registered_secret'])
def test_credentials_never_enter_remote_message_or_response_schema(tmp_path, monkeypatch, location):
    with native_engine(tmp_path) as engine:
        messages, options = (MESSAGES, {})
        if location == 'message':
            messages = [{'role': 'user', 'content': 'Bearer synthetic-auth-c9-never-send'}]
        elif location == 'schema_key':
            options['response_format'] = {'type': 'json_schema', 'json_schema': {'api_key': 'example-public-4a8692e356d5'}}
        else:
            value = 'C9_REGISTERED_SYNTHETIC_SECRET_41794'
            monkeypatch.setitem(redaction._registry, 'C9_REMOTE', value)
            messages = [{'role': 'user', 'content': value}]
        with pytest.raises(ValueError):
            engine.compute.chat(messages, workflow_id='c9', step_id='privacy', invocation_id='c9-privacy', categories={'synthetic'}, max_tokens=32, max_retries_override=0, max_queue_seconds=0.1, **options)
        assert not engine.compute.transport.calls and sum(engine.compute.registry.active.values()) == 0

@pytest.mark.parametrize('fault', ['network', 'gpu_oom', 'malformed_choices', 'truncated', 'invalid_identity'])
def test_remote_fault_releases_reservation_without_verified_success_or_retry(tmp_path, fault, record_property):
    with native_engine(tmp_path) as engine:
        transport = engine.compute.transport
        original = transport.request

        def broken(worker, method, path, **kwargs):
            if fault in {'network', 'gpu_oom'}:
                transport.calls.append({'worker_id': worker['worker_id'], 'path': path})
                raise ComputeError('Controlled worker disconnect.' if fault == 'network' else 'Controlled GPU OOM.')
            result = original(worker, method, path, **kwargs)
            if fault == 'malformed_choices':
                result['choices'] = []
            if fault == 'truncated':
                result['choices'][0]['finish_reason'] = 'length'
            if fault == 'invalid_identity':
                result['model'] = 'a_different_fixture_model'
            return result
        transport.request = broken
        with pytest.raises(ComputeError):
            engine.compute.chat(MESSAGES, workflow_id='c9', step_id='fault', invocation_id='c9-fault', categories={'synthetic'}, max_tokens=32, max_retries_override=0, max_queue_seconds=0.1)
        record_property('observed', json.dumps({'transport_posts': len(transport.calls), 'active_total': sum(engine.compute.registry.active.values()), 'queued': len(engine.compute.queued)}))
        assert len(transport.calls) == 1 and sum(engine.compute.registry.active.values()) == 0
        assert not engine.compute.waiting and (not engine.compute.queued)

@pytest.mark.parametrize('phase', ['pre_dispatch', 'transport_return'])
def test_remote_cancel_does_not_retry_or_poison_worker_health(tmp_path, phase):
    with native_engine(tmp_path) as engine:
        cancellation = threading.Event()
        if phase == 'pre_dispatch':
            cancellation.set()
        else:
            engine.compute.transport.before_return = cancellation.set
        with pytest.raises(ComputeError):
            engine.compute.chat(MESSAGES, workflow_id='c9', step_id='cancel', invocation_id='c9-cancel', categories={'synthetic'}, max_tokens=32, cancellation=cancellation, max_retries_override=0, max_queue_seconds=0.1)
        assert len(engine.compute.transport.calls) == (0 if phase == 'pre_dispatch' else 1)
        assert engine.compute.registry.observations['controlled']['status'] == 'healthy'
        assert sum(engine.compute.registry.active.values()) == 0

@contextmanager
def http_fixture(kind, *, target=None):
    observed = {'requests': [], 'bodies': []}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.reply()

        def do_POST(self):
            self.reply()

        def reply(self):
            observed['requests'].append({'method': self.command, 'path': self.path})
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            observed['bodies'].append(body)
            if kind == 'redirect':
                self.send_response(302)
                self.send_header('Location', target + '/replacement')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if kind == 'auth_error':
                self.send_response(401)
                body = b'{"error":"password=C9_SYNTHETIC_HTTP_PRIVATE_4419"}'
            elif self.path.endswith('/health'):
                self.send_response(200)
                body = b'{"status":"ok"}'
            else:
                self.send_response(200)
                body = b'data: {"choices":[{"delta":{"content":"Controlled stream."}}]}\n\ndata: [DONE]\n\n'
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ('http://127.0.0.1:' + str(server.server_port), observed)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
    assert not thread.is_alive()

@pytest.mark.parametrize('mode', ['health', 'chat'])
def test_original_local_client_does_not_follow_endpoint_redirect(mode, tmp_path, record_property):
    with controlled_engine(tmp_path) as engine, http_fixture('ok') as (replacement, received), http_fixture('redirect', target=replacement) as (original, sent):
        spec = replace(engine.config.models.supervisor, endpoint=original + '/v1', request_timeout_seconds=1)
        client = LlamaCppClient(spec, max_attempts=1)
        if mode == 'health':
            client.health()
        else:
            try:
                client.chat(MESSAGES, max_tokens=16)
            except ModelClientError:
                pass
        record_property('observed', json.dumps({'original_requests': len(sent['requests']), 'replacement_requests': len(received['requests']), 'replacement_body_bytes': sum(map(len, received['bodies']))}))
        assert len(sent['requests']) == 1
        assert not received['requests'], 'Original model client followed an untrusted endpoint redirect.'

@pytest.mark.parametrize('mode', ['health', 'chat', 'tool_json'])
def test_model_http_failure_detail_does_not_expose_synthetic_credentials(tmp_path, mode, record_property):
    with controlled_engine(tmp_path) as engine, http_fixture('auth_error') as (url, observed):
        client = LlamaCppClient(replace(engine.config.models.supervisor, endpoint=url + '/v1'), max_attempts=1)
        if mode == 'health':
            text = client.health().detail
        else:
            try:
                if mode == 'chat':
                    client.chat(MESSAGES, max_tokens=16)
                else:
                    client.complete_with_tools(MESSAGES, tools=[])
            except ModelClientError as error:
                text = str(error)
            else:
                raise AssertionError('Unauthorized response was accepted.')
        leaked = 'C9_SYNTHETIC_HTTP_PRIVATE_4419' in text
        record_property('observed', json.dumps({'requests': len(observed['requests']), 'leaked_synthetic_secret': leaked}))
        assert not leaked, 'Original model error detail disclosed synthetic credentials.'
        assert len(observed['requests']) == 1

def test_model_partial_timeout_never_replays_visible_response(tmp_path, monkeypatch):
    from hanni.models import client as module
    observed = {'requests': 0}

    class Response:

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"Original partial."}}]}\n'
            raise TimeoutError('Controlled connection timeout after partial output.')

    def open_request(*args, **kwargs):
        observed['requests'] += 1
        return Response()
    monkeypatch.setattr(module.LlamaCppClient, '_open', open_request)
    with controlled_engine(tmp_path) as engine:
        client = LlamaCppClient(engine.config.models.supervisor, max_attempts=3)
        stream = client.stream_chat(MESSAGES)
        assert next(stream) == 'Original partial.'
        with pytest.raises(ModelClientError):
            list(stream)
        assert observed['requests'] == 1

def test_local_client_owned_opener_does_not_install_global_transport_or_use_ambient_proxy(tmp_path, monkeypatch, record_property):
    from hanni.models import client as module
    before = module.urllib.request._opener
    with controlled_engine(tmp_path) as engine, http_fixture('ok') as (origin, observed), http_fixture('auth_error') as (proxy, intercepted):
        for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY'):
            monkeypatch.setenv(name, proxy)
        monkeypatch.setenv('NO_PROXY', '')
        monkeypatch.setenv('no_proxy', '')
        client = LlamaCppClient(replace(engine.config.models.supervisor, endpoint=origin + '/v1'), max_attempts=1)
        health = client.health()
        record_property('observed', json.dumps({'original_requests': len(observed['requests']), 'ambient_proxy_requests': len(intercepted['requests']), 'healthy': health.ok, 'global_opener_unchanged': module.urllib.request._opener is before}))
        assert health.ok and len(observed['requests']) == 1 and (not intercepted['requests'])
        assert module.urllib.request._opener is before

@pytest.mark.parametrize('mode', ['chat', 'tool_json'])
def test_repeated_authorization_failure_retains_native_retry_cap(tmp_path, monkeypatch, mode, record_property):
    from hanni.models import client as module
    delays = []
    monkeypatch.setattr(module.time, 'sleep', lambda value: delays.append(value))
    with controlled_engine(tmp_path) as engine, http_fixture('auth_error') as (url, observed):
        client = LlamaCppClient(replace(engine.config.models.supervisor, endpoint=url + '/v1'), max_attempts=3)
        with pytest.raises(ModelClientError):
            if mode == 'chat':
                client.chat(MESSAGES, max_tokens=16)
            else:
                client.complete_with_tools(MESSAGES, tools=[])
        record_property('observed', json.dumps({'requests': len(observed['requests']), 'backoff_delays': delays, 'side_effect_tool_dispatches': 0}))
        assert len(observed['requests']) == 3 and delays == [0.2, 0.4]

@pytest.mark.parametrize('mode', ['health', 'chat', 'tool_json'])
def test_model_network_failure_detail_rechecks_shared_redaction(tmp_path, monkeypatch, mode):
    from hanni.models import client as module
    value = 'C9_NETWORK_SYNTHETIC_CREDENTIAL_15429'
    monkeypatch.setitem(redaction._registry, 'C9_NETWORK', value)

    def failed(*args, **kwargs):
        raise urllib.error.URLError('synthetic connection outage ' + value)
    monkeypatch.setattr(module.LlamaCppClient, '_open', failed)
    with controlled_engine(tmp_path) as engine:
        client = LlamaCppClient(engine.config.models.supervisor, max_attempts=1)
        if mode == 'health':
            reply = client.health().detail
        else:
            try:
                if mode == 'chat':
                    client.chat(MESSAGES, max_tokens=16)
                else:
                    client.complete_with_tools(MESSAGES, tools=[])
            except ModelClientError as error:
                reply = str(error)
            else:
                raise AssertionError('Controlled network failure was accepted.')
        assert value not in reply and 'REDACTED' in reply
