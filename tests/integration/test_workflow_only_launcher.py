"""Actual launcher/controller/HTTP workflow path; model and telemetry are seams."""
import http.client
import json
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from hanni.dashboard import launcher
from hanni.dashboard.server import DashboardServer

def test_workflow_only_uses_original_controller_and_keeps_backend_alive(tmp_path, monkeypatch):
    source = tmp_path / 'launcher-evidence.txt'
    source.write_text('launcher evidence', encoding='utf-8')
    replies = iter([{'summary': 'Read the requested local text.', 'unsupported_reason': None, 'steps': [{'description': 'Read the local file ' + str(source), 'kind': 'tool', 'capability_id': 'file.read', 'arguments': {'path': str(source)}}]}])
    calls = []

    class Client:

        def health(self):
            return SimpleNamespace(ok=True)

        def chat(self, messages, **kwargs):
            calls.append(kwargs)
            return json.dumps(next(replies))

    class Telemetry:

        def __init__(self, config):
            self.config = config
            self.closed = False

        def snapshot(self):
            return {'sampled_at': time.time(), 'resources': {'ram_percent': 20}}

        def start(self):
            pass

        def close(self):
            self.closed = True
    manager = Mock()
    ready = threading.Event()
    owned = {}
    outcomes = {}

    def make_manager(config, **kwargs):
        owned['shutdown'] = kwargs['shutdown_event']
        return manager

    def make_server(*args, **kwargs):
        server = DashboardServer(*args, **kwargs)
        owned['server'] = server
        ready.set()
        return server

    def drive_real_http_goal():
        try:
            assert ready.wait(10), 'The actual local server did not start.'
            server = owned['server']
            deadline = time.monotonic() + 10
            while not server.workflows.runner_attached and time.monotonic() < deadline:
                owned['shutdown'].wait(0.02)
            assert server.workflows.runner_attached, server.workflows.error
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request('POST', '/api/workflows', body=json.dumps({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Read the local text file ' + str(source), 'mode': 'supervised'}}), headers={'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{server.server_port}', 'X-Hanni-Token': server.chat.token})
                response = connection.getresponse()
                result = json.loads(response.read())
                assert response.status == 200, result
            finally:
                connection.close()
            detail = server.workflows.service.wait(result['workflow_id'], timeout=10, predicate=lambda record: record['status'] in {'completed', 'blocked', 'failed'})
            assert detail['status'] == 'completed', detail.get('error') or detail
            assert detail['steps'][0]['result']['data']['text'] == 'launcher evidence'
            assert detail['counts']['verified'] == 1
            assert len(detail['invocations']) == 1
            assert not owned['shutdown'].is_set()
            assert server.workflows.runner_attached
            outcomes['detail'] = detail
        except BaseException as exc:
            outcomes['error'] = exc
        finally:
            if 'shutdown' in owned:
                owned['shutdown'].set()
    monkeypatch.setattr(launcher, 'Telemetry', Telemetry)
    monkeypatch.setattr(launcher, 'DashboardServer', make_server)
    monkeypatch.setattr(launcher, 'create_client', lambda *args, **kwargs: Client())
    monkeypatch.setattr('hanni.models.manager.ModelManager', make_manager)
    monkeypatch.setattr('hanni.laya.manager.start_shadow_from_env', lambda: None)
    monkeypatch.setattr('hanni.laya.manager.stop_shadow', lambda: None)
    cli = Mock(side_effect=AssertionError('Workflow-only must not open interactive input.'))
    desktop, browser = (Mock(), Mock())
    monkeypatch.setattr('hanni.cli.run', cli)
    monkeypatch.setattr(launcher, 'launch_desktop', desktop)
    monkeypatch.setattr(launcher.webbrowser, 'open', browser)
    with socket.socket() as unused:
        unused.bind(('127.0.0.1', 0))
        port = unused.getsockname()[1]
    driver = threading.Thread(target=drive_real_http_goal, daemon=True)
    driver.start()
    try:
        result = launcher.main(['--workflow-only', '--no-browser', '--port', str(port), '--data-dir', str(tmp_path / 'state')])
    finally:
        if 'shutdown' in owned:
            owned['shutdown'].set()
        driver.join(3)
    assert not driver.is_alive()
    if 'error' in outcomes:
        raise outcomes['error']
    assert result == 0 and 'detail' in outcomes
    assert len(calls) == 1
    cli.assert_not_called()
    desktop.assert_not_called()
    browser.assert_not_called()
    manager.ensure_loaded.assert_called_once_with('supervisor')
    manager.close.assert_called_once()
    assert owned['server'].workflows.closed
    assert owned['server'].telemetry.closed
    assert owned['server'].socket.fileno() == -1
