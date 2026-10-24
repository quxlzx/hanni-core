"""Native agent calls the dashboard-owned official SDK connection, with receipts."""
import http.client
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hanni.dashboard.server import DashboardServer
from hanni.hermes.state import TaskStore
from hanni.native import mcp_client, worker
from tests.unit.test_mcp_hub_api import config_for
from tests.unit.test_mcp_hub import stdio_config, ledger
from tests.test_native_loop import FakeClient


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_BRIDGE_URL', 'http://127.0.0.1:9998')
    (tmp_path / 'bridge.token').write_text('fixture-native-mcp-credential-32chars')
    server = DashboardServer(0, SimpleNamespace(config=config_for(tmp_path), snapshot=lambda: {}))
    monkeypatch.setenv('HANNI_DASHBOARD_URL', f'http://127.0.0.1:{server.server_port}')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join()
        server.chat.close(); server.chat.db.close()


def connect(service, tmp_path, classification='read_only', name='mock.echo'):
    manager = service.mcp.manager
    server = manager.add(stdio_config(tmp_path))
    server = manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])['servers'][0]
    tool = next(item for item in server['tools'] if item['original_name'] == name)
    manager.approve_tools(server['id'], [{'original_name': name, 'definition_hash': tool['definition_hash'], 'classification': classification}])
    return server['id']


def action_for(tmp_path, spec, arguments):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('native-test', {'prompt': 'Use the fixture MCP tool', 'windows_tools': [], 'origin': 'hanni', 'context': {}})
    action = store.request_action(task['id'], 'call-1', spec, arguments)
    return store, task, action


def test_unapproved_tools_are_not_exposed_to_native_agent(service, tmp_path):
    manager = service.mcp.manager
    server = manager.add(stdio_config(tmp_path))
    manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
    assert mcp_client.discover(tmp_path) == []
    assert all(row['event'] == 'list' for row in ledger(tmp_path))


def test_real_native_http_execution_is_persisted_and_never_replayed(service, tmp_path):
    connect(service, tmp_path)
    spec = mcp_client.discover(tmp_path)[0]
    assert spec['target'] == 'mcp'
    store, task, action = action_for(tmp_path, spec, {'message': 'NATIVE_MCP_OK'})
    try:
        result = mcp_client.execute(store, task['id'], action)
        assert result['ok'], result
        assert result['data']['structured_content']['message'] == 'NATIVE_MCP_OK'
        assert store.action(action['id'])['state'] == 'fulfilled'
        assert service.native_mcp.call(action['id']) == result
        assert len([row for row in ledger(tmp_path) if row['event'] == 'call']) == 1
        assert (tmp_path / 'logs/tool_audit.jsonl').exists()
    finally:
        store.close()


def test_write_requires_owner_action_before_dispatch_and_uses_real_receipt(service, tmp_path):
    connect(service, tmp_path, 'write', 'mock.create_record')
    spec = mcp_client.discover(tmp_path)[0]
    store, task, action = action_for(tmp_path, spec, {'title': 'Authorized write'})
    try:
        with pytest.raises(ValueError, match='not authorized'):
            service.native_mcp.call(action['id'])
        assert not any(row['event'] == 'call' for row in ledger(tmp_path))
        store.settle(action['id'], 'dispatching')
        result = mcp_client.execute(store, task['id'], store.action(action['id']))
        assert result['ok'], result
        assert result['data']['structured_content']['created'] is True
    finally:
        store.close()


def test_disabled_or_changed_tool_cannot_execute_captured_native_spec(service, tmp_path):
    server_id = connect(service, tmp_path)
    spec = mcp_client.discover(tmp_path)[0]
    store, task, action = action_for(tmp_path, spec, {'message': 'must not run'})
    try:
        service.mcp.manager.disable_tools(server_id, ['mock.echo'])
        result = mcp_client.execute(store, task['id'], action)
        assert not result['ok']
        assert not any(row['event'] == 'call' for row in ledger(tmp_path))
    finally:
        store.close()


def test_browser_token_cannot_access_internal_execution_endpoint(service, tmp_path):
    client = http.client.HTTPConnection('127.0.0.1', service.server_port)
    try:
        client.request('GET', '/api/native-mcp/tools', headers={'X-Hanni-Token': service.chat.token})
        response = client.getresponse(); response.read()
        assert response.status == 403
        client.request('POST', '/api/native-mcp/call', body=json.dumps({'action_id': 'invalid'}), headers={'Content-Type': 'application/json', 'X-Hanni-Token': service.chat.token})
        response = client.getresponse(); response.read()
        assert response.status == 403
    finally:
        client.close()


def test_native_loop_discovers_and_calls_an_enabled_dashboard_mcp_tool(service, tmp_path):
    connect(service, tmp_path)
    tool = mcp_client.discover(tmp_path)[0]
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('worker-test', {'prompt': 'Use mock.echo to echo LOOP_MCP_OK', 'windows_tools': [], 'origin': 'hanni', 'context': {}})
    fake = FakeClient([{'message': {'tool_calls': [{'id': 'call-1', 'function': {'name': tool['name'], 'arguments': json.dumps({'message': 'LOOP_MCP_OK'})}}]}},
                       {'message': {'content': 'LOOP_MCP_OK'}}])
    try:
        with patch.object(worker, 'NativeClient', return_value=fake), patch.object(worker, 'load_model', return_value={'context_length': 65536}):
            fake.max_tokens = 1200
            worker.run(store.path, task['id'], {'entries': []})
        result = store.get(task['id'])
        assert result['state'] == 'review_required', result
        assert result['result']['model_claims'] == 'LOOP_MCP_OK'
        assert result['actions'][0]['receipt']['ok']
        assert len([row for row in ledger(tmp_path) if row['event'] == 'call']) == 1
    finally:
        store.close()
