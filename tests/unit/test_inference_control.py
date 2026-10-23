from contextlib import contextmanager
import http.client
import importlib.util
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from hanni.dashboard.inference import InferenceControl, InferenceError, _InferenceStream
from hanni.dashboard.server import DashboardServer

@pytest.fixture
def control(tmp_path):
    result = InferenceControl(Mock(), tmp_path)
    result._connection = Mock(return_value=('http://127.0.0.1:8200', {'Authorization': 'Bearer test'}))
    return result

@pytest.mark.parametrize('method,path', [('POST', '/api/inference/models/swift-1.5/run'), ('GET', '/api/inference/models/unknown/health'), ('POST', '/api/inference/models/swift-1.5/stop?lines=2'), ('GET', '/api/inference/models/swift-1.5/logs?lines=1001'), ('GET', '/api/inference/models/swift-1.5/logs?lines=2&lines=3'), ('GET', '/api/inference/models/../hosts'), ('POST', '/api/inference/session')])
def test_only_fixed_operations_and_bounded_queries(method, path):
    with pytest.raises(InferenceError):
        InferenceControl.route(method, path)

def test_cancel_and_history_remain_available_during_emergency_stop(control):
    (control.data_dir / 'emergency_stop.json').write_text('invalid stop state')
    for method, suffix in [('POST', 'chat'), ('POST', 'restart'), ('POST', 'start')]:
        with pytest.raises(InferenceError) as error:
            control.guard(method, '/api/inference/models/swift-1.5/' + suffix)
        assert error.value.status == 423
    control.guard('POST', '/api/inference/models/swift-1.5/cancel')
    control.guard('GET', '/api/inference/models/swift-1.5/history')
    control.guard('DELETE', '/api/inference/models/swift-1.5/history')

def test_protected_runtime_changes_never_contact_upstream(control):
    with pytest.raises(InferenceError) as error:
        control.request('POST', '/api/inference/models/flash-next/stop')
    assert error.value.status == 423
    control._connection.assert_not_called()

@pytest.mark.parametrize('values', [{'max_tokens': 0}, {'max_tokens': 8193}, {'max_tokens': True}, {'temperature': float('nan')}, {'top_p': 0}, {'command': 'anything'}, {'reasoning_budget': 4097}, {'messages': []}])
def test_invalid_chat_parameters_rejected_before_network(control, values):
    body = {'messages': [{'role': 'user', 'content': 'test'}], **values}
    with pytest.raises(InferenceError) as error:
        control.stream('/api/inference/models/swift-1.5/chat', body)
    assert error.value.status == 422
    control._connection.assert_not_called()

def test_metrics_and_history_use_original_controller(control):
    response = Mock(status_code=200, is_error=False, is_redirect=False)
    response.json.return_value = [{'role': 'assistant', 'content': 'Saved reply'}]
    with patch('hanni.dashboard.inference.httpx.Client') as client:
        client.return_value.__enter__.return_value.request.return_value = response
        result = control.request('GET', '/api/inference/models/nex-n2-mini/history')
    assert result == response.json.return_value
    assert client.return_value.__enter__.return_value.request.call_args.args[:2] == ('GET', 'http://127.0.0.1:8200/api/models/nex-n2-mini/history')

def test_stream_closes_on_emergency_stop(control):
    response = Mock(status_code=200, headers={'content-type': 'text/event-stream'})

    def chunks():
        yield b'event: delta\ndata: {"content":"one"}\n\n'
        (control.data_dir / 'emergency_stop.json').write_text('invalid stop state')
        yield b'event: delta\ndata: {"content":"two"}\n\n'
    response.iter_bytes.side_effect = chunks
    with patch('hanni.dashboard.inference.httpx.Client') as client:
        manager = client.return_value.stream.return_value
        manager.__enter__.return_value = response
        stream = _InferenceStream(control, 'http://127.0.0.1:8200/api/models/swift-1.5/chat', {}, {}, '/api/inference/models/swift-1.5/chat')
        assert len(list(stream.chunks())) == 1
        stream.close()
        manager.__exit__.assert_called_once()
        client.return_value.close.assert_called_once()

def test_import_replaces_overlaps_preserves_other_workers_and_permissions():
    path = Path(__file__).resolve().parents[2] / 'scripts/import_control_center.py'
    spec = importlib.util.spec_from_file_location('import_control_center', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = {'version': 1, 'enabled': True, 'nodes': [{'id': 'hanni'}, {'id': 'wonyoung'}], 'workers': [{'worker_id': 'athena-p40', 'allowed_categories': ['project'], 'enabled': False}, {'worker_id': 'other', 'node_id': 'hanni', 'remote_port': 9000, 'enabled': False}], 'policy': {'timeout_seconds': 100}}
    updated = module.migrate(raw)
    workers = {w['worker_id']: w for w in updated['workers']}
    assert workers['athena-p40']['model_id'] == 'mellum-2.1'
    assert workers['athena-p40']['remote_port'] == 8103
    assert workers['athena-p40']['allowed_categories'] == ['project']
    assert workers['athena-p40']['enabled'] is False
    assert workers['athena-p40']['startup']['authorized'] is False
    assert workers['wonyoung-strata']['context_configured'] == 131072
    assert workers['other'] == raw['workers'][1]
    assert updated['policy'] == raw['policy']
    assert module.migrate(updated) == updated

@pytest.fixture
def server(control):
    server = DashboardServer(0, SimpleNamespace(snapshot=lambda: {}))
    server.inference = control
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()

def http_request(server, method, path, body=None, authorized=True):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    headers = {'Content-Type': 'application/json'}
    if authorized:
        headers.update({'X-Hanni-Token': server.chat.token, 'Origin': f'http://127.0.0.1:{server.server_port}'})
    conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    response = conn.getresponse()
    result = (response.status, response.read())
    conn.close()
    return result

@pytest.mark.parametrize('method,suffix', [('GET', 'history'), ('PUT', 'history'), ('DELETE', 'history'), ('POST', 'start'), ('POST', 'chat')])
def test_all_native_inference_methods_require_dashboard_auth(server, method, suffix):
    server.inference.request = Mock()
    status, _ = http_request(server, method, '/api/inference/models/swift-1.5/' + suffix, {'messages': []}, authorized=False)
    assert status == 403
    server.inference.request.assert_not_called()

def test_native_history_save_and_clear_route_to_correct_model(server):
    server.inference.request = Mock(return_value=[])
    path = '/api/inference/models/swift-1.5/history'
    assert http_request(server, 'PUT', path, {'messages': []})[0] == 200
    server.inference.request.assert_called_with('PUT', path, {'messages': []})
    assert http_request(server, 'DELETE', path)[0] == 200
    server.inference.request.assert_called_with('DELETE', path, None)

def test_native_stream_keeps_sse_events_and_closes_upstream(server):
    stream = Mock()
    stream.chunks.return_value = iter([b'event: delta\ndata: {"content":"Hi"}\n\n', b'event: done\ndata: {}\n\n'])
    server.inference.stream = Mock(return_value=stream)
    status, body = http_request(server, 'POST', '/api/inference/models/swift-1.5/chat', {'messages': [{'role': 'user', 'content': 'Hello'}]})
    assert status == 200
    assert b'event: delta' in body and b'event: done' in body
    stream.close.assert_called_once()
