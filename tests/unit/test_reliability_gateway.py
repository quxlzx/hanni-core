"""Controller-to-desktop trace integration and request boundary checks."""
import http.client
import json
import threading
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.chat import ChatHub, ChatSession
from hanni.dashboard.executions import execution_snapshot
from hanni.dashboard.server import DashboardServer
from hanni.reliability.context import current_request_id, request_scope
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolRequest
from hanni.tools.registry import build_default_registry
from tests.helpers import REPO_ROOT

@pytest.fixture
def execution_server(tmp_path):
    config = load_config(REPO_ROOT / 'config', data_dir=tmp_path, env={})
    server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {}))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (server, config)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        server.chat.close()
        server.chat.db.close()
        close_service(tmp_path)

def get(server, path='/api/executions', headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        conn.request('GET', path, headers=headers or {})
        response = conn.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        conn.close()

def test_execution_api_observes_original_shared_registry_without_discovery_writes(execution_server):
    server, config = execution_server
    headers = {'X-Hanni-Token': server.chat.token}
    status, empty = get(server, headers=headers)
    assert status == 200 and empty['available'] and (empty['tasks'] == [])
    assert not (config.paths.data_dir / 'logs').exists()
    controller = build_default_registry(config)
    assert controller.context.reliability is server.features.registry.context.reliability
    identifier = str(uuid4())
    with request_scope(identifier, 'terminal'):
        result = controller.execute(ToolRequest('time.now', {'timezone': 'UTC'}))
    assert result.ok
    status, snapshot = get(server, headers=headers)
    assert status == 200 and len(snapshot['tasks']) == 1
    task = snapshot['tasks'][0]
    assert task['request_id'] == identifier and task['source'] == 'terminal'
    assert task['execution_status'] == 'succeeded'
    assert task['steps'][0]['capability_id'] == 'time.now'
    states = [event['state'] for event in task['steps'][0]['events']]
    assert states == ['REQUESTED', 'PLANNED', 'EXECUTING', 'TOOL_COMPLETED', 'VERIFYING', 'VERIFIED']
    assert 'utc_iso' not in json.dumps(snapshot)
    assert (config.paths.data_dir / 'logs' / 'execution_traces.sqlite3').exists()

@pytest.mark.parametrize('headers', [{}, {'X-Hanni-Token': 'stale'}, {'Origin': 'https://evil.example'}, {'Host': 'evil.example'}, {'Sec-Fetch-Site': 'cross-site'}])
def test_execution_api_keeps_private_route_security(execution_server, headers):
    server, _ = execution_server
    supplied = {'X-Hanni-Token': server.chat.token, **headers} if headers else {}
    assert get(server, headers=supplied)[0] == 403

def test_execution_api_limits_and_token_rotation(execution_server):
    server, _ = execution_server
    token = server.chat.token
    for value in ('0', '101', '-1', 'oops', '1.5'):
        assert get(server, '/api/executions?limit=' + value, {'X-Hanni-Token': token})[0] == 400
    server.chat.ready = True
    server.chat.clear()
    assert get(server, headers={'X-Hanni-Token': token})[0] == 403
    assert get(server, headers={'X-Hanni-Token': server.chat.token})[0] == 200

def test_execution_projection_uses_attached_controller_context(execution_server):
    server, _ = execution_server
    from hanni.reliability.execution import ReliabilityService
    service = ReliabilityService()
    with service.task('test') as trace:
        trace.select(['time.now'])
    server.mcp.controller_registry = SimpleNamespace(context=SimpleNamespace(reliability=service))
    projected = execution_snapshot(server)
    assert projected['tasks'][0]['task_id'] == trace.record['task_id']
    server.mcp.controller_registry = None

def test_explicit_desktop_write_preserves_its_request_id_and_private_content(execution_server):
    server, _ = execution_server
    identifier = str(uuid4())
    title = 'Private fixture task title for request correlation'
    body = {'id': identifier, 'operation': 'task.create', 'data': {'title': title}, 'confirmed': True}
    result = server.features.mutate('productivity', body)
    assert result['task']['title'] == title
    assert server.features.mutate('productivity', body) == result
    snapshot = execution_snapshot(server)
    assert len(snapshot['tasks']) == 1
    task = snapshot['tasks'][0]
    assert task['request_id'] == identifier and task['source'] == 'dashboard'
    assert task['selected_capabilities'] == ['workspace.task.create']
    assert task['steps'][0]['approval'] == 'explicit_confirmation'
    assert title not in json.dumps(snapshot)

def test_browser_and_voice_trace_ids_share_chat_turns_and_do_not_leak_kwargs(tmp_path):
    config = load_config(REPO_ROOT / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config)
    hub = ChatHub()
    hub.ready = True
    received_kwargs = []

    class ExistingSession:

        def stream_response(self, prompt, **kwargs):
            received_kwargs.append(kwargs)
            registry.execute(ToolRequest('time.now', {'timezone': 'UTC'}))
            yield 'Actual clock read.'
    session = ChatSession(ExistingSession(), hub, 'voice')
    try:
        assert ''.join(session.stream_response('Clock please', max_tokens=20))
        browser_id = str(uuid4())
        hub.submit(browser_id, 'Clock again')
        assert hub.take() == 'Clock again'
        generator = session.stream_response('Clock again')
        assert next(generator) == 'Actual clock read.'
        generator.close()
        assert current_request_id() is None
        tasks = registry.context.reliability.snapshot()['tasks']
        messages = hub.snapshot()['messages']
        assert tasks[0]['request_id'] == browser_id and tasks[0]['source'] == 'browser'
        assert tasks[1]['request_id'] == messages[0]['turn'] and tasks[1]['source'] == 'voice'
        assert received_kwargs == [{'max_tokens': 20}, {}]
        assert messages[-1]['status'] == 'interrupted'
    finally:
        hub.close()
        hub.db.close()
        close_service(tmp_path)

@pytest.mark.parametrize('command', ['tool-run', 'capability-call'])
def test_one_shot_cli_releases_observational_database(command, tmp_path, capsys):
    from hanni.cli import run
    code = run([command, 'time.now', '--config-dir', str(REPO_ROOT / 'config'), '--data-dir', str(tmp_path), '--env-file', str(tmp_path / 'missing.env'), '--no-file-log', '--json'])
    assert code == 0
    assert json.loads(capsys.readouterr().out)['ok'] is True
    path = tmp_path / 'logs' / 'execution_traces.sqlite3'
    assert path.exists()
    path.unlink()
