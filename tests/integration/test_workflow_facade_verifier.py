"""Independent private HTTP and cleanup fault tests; engine not simulated as working."""
import http.client
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.server import DashboardServer
from hanni.dashboard.workflows import WorkflowHub

@pytest.fixture
def private_server():
    adapter = Mock()
    adapter.snapshot.return_value = {'available': False, 'items': [], 'runner_attached': False}
    adapter.detail.return_value = {'available': False, 'workflow': None}
    server = DashboardServer(0, SimpleNamespace(snapshot=lambda: {}), workflows=adapter)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (server, adapter)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        server.chat.close()
        server.chat.db.close()

def request(server, *, method='GET', path='/api/workflows', overrides=None):
    headers = {'Host': f'127.0.0.1:{server.server_port}', 'X-Hanni-Token': server.chat.token}
    body = None
    if method == 'POST':
        headers.update({'Origin': f'http://127.0.0.1:{server.server_port}', 'Content-Type': 'application/json'})
        body = json.dumps({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Isolated denied request'}})
    for key, value in (overrides or {}).items():
        if value is None:
            headers.pop(key, None)
        else:
            headers[key] = value
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()

def test_private_read_host_origin_fetch_and_token_denials_precede_lookup(private_server):
    server, adapter = private_server
    variants = [{'Host': 'attacker.invalid'}, {'Origin': 'http://attacker.invalid'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}, {'X-Hanni-Token': None}, {'X-Hanni-Token': 'stale'}]
    for headers in variants:
        for path in ['/api/workflows', '/api/workflows/wf_' + 'a' * 32]:
            assert request(server, path=path, overrides=headers) == 403
    assert request(server, path='/api/workflows?token=' + server.chat.token, overrides={'X-Hanni-Token': None}) == 403
    adapter.snapshot.assert_not_called()
    adapter.detail.assert_not_called()

def test_private_mutation_denials_precede_any_operation(private_server):
    server, adapter = private_server
    for headers in [{'Host': 'attacker.invalid'}, {'Origin': None}, {'Origin': 'http://attacker.invalid'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}, {'X-Hanni-Token': None}, {'X-Hanni-Token': 'stale'}]:
        assert request(server, method='POST', overrides=headers) == 403
    assert request(server, method='POST', path='/api/workflows/__class__') == 404
    adapter.mutate.assert_not_called()

def test_failed_controller_replacement_does_not_report_old_attachment(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    service = Mock()
    service.snapshot.return_value = []
    hub = WorkflowHub(config, Mock(), SimpleNamespace(snapshot=lambda: {}), service=service)
    first, second = (Mock(), Mock())
    hub.attach_controller(first, Mock(), Mock())
    assert hub._envelope()['controller_attached']
    service.attach.side_effect = RuntimeError('Injected replacement startup failure')
    try:
        hub.attach_controller(second, Mock(), Mock())
        envelope = hub._envelope()
        assert not envelope['runner_attached']
        assert not envelope['controller_attached'], 'Detached original controller must not be reported attached after replacement failure'
    finally:
        hub.close()

def test_workflow_detach_error_does_not_skip_original_session_cleanup():
    from hanni.cli import _close_interactive_session
    registry = SimpleNamespace(context=SimpleNamespace(reliability=None))
    session = SimpleNamespace(close=Mock(), fallback_session=None)
    with patch('hanni.mcp.runtime.detach_controller', side_effect=RuntimeError('Injected detach storage failure')):
        try:
            _close_interactive_session(session, registry=registry)
        except RuntimeError:
            pass
    session.close.assert_called_once()

def test_detach_fault_disables_admission_before_propagation(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    service = Mock()
    hub = WorkflowHub(config, Mock(), SimpleNamespace(snapshot=lambda: {}), service=service)
    registry = Mock()
    hub.attach_controller(registry, Mock(), Mock())
    service.detach.side_effect = RuntimeError('Injected detach storage failure')
    try:
        try:
            hub.detach_controller(registry)
        except RuntimeError:
            pass
        assert not hub._envelope()['runner_attached']
        assert not hub._envelope()['controller_attached']
        with pytest.raises(RuntimeError):
            hub.mutate({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Must not be admitted after detach failure'}})
        service.mutate.assert_not_called()
    finally:
        hub.close()
