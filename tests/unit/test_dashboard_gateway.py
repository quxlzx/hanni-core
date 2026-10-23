import http.client
import json
import threading
from types import SimpleNamespace
from hanni.config.loader import load_config
from hanni.dashboard.gateway import activity_snapshot, workspace_contract
from hanni.dashboard.server import DashboardServer
from hanni.logs.redaction import register_secret, clear_registry
from hanni.tools.base import ToolRegistry
from tests.helpers import REPO_ROOT

def test_workspace_contract_only_discovers_existing_definitions(tmp_path, monkeypatch):
    config = load_config(REPO_ROOT / 'config', data_dir=tmp_path, env={})

    def forbidden(*args, **kwargs):
        raise AssertionError('UI discovery must never execute a tool')
    monkeypatch.setattr(ToolRegistry, 'execute', forbidden)
    contract = workspace_contract(config)
    assert contract['screens'] == ['home', 'chat', 'voice', 'planner', 'tasks', 'calendar', 'projects', 'memory', 'mission', 'models', 'agents', 'cluster', 'activity', 'screen', 'notifications', 'settings', 'mcp', 'workflows', 'model-routing']
    assert {item['name'] for item in contract['capabilities']} >= {'system.stats', 'process.top_memory'}
    assert contract['models'][0]['id'] == config.models.supervisor.id
    assert contract['timezone'] == config.hanni.user.timezone
    assert contract['features']['agents']
    assert contract['features']['planner'] and contract['features']['memory_browser']
    assert not contract['features']['agent_runtime']
    assert not contract['features']['live_approval_queue']
    assert not contract['features']['screen_awareness']
    assert contract['features']['cluster']
    assert contract['features']['workflows']
    assert contract['features']['model_routing']
    assert not contract['features']['output_audio_levels']
    assert contract['policies']['allowed_actions'] == list(config.hanni.mcp.allowed_actions)
    assert not (tmp_path / 'memory.sqlite3').exists()
    assert not (tmp_path / 'logs').exists()

def test_missing_configuration_does_not_fabricate_models_or_policies():
    contract = workspace_contract(None)
    assert contract['models'] == [] and contract['capabilities'] == []
    assert contract['policies'] is None
    assert not contract['features']['gpu_routing']
    assert not contract['features']['workflows']
    assert not contract['features']['model_routing']

def test_activity_projects_only_safe_recorded_fields(tmp_path):
    path = tmp_path / 'logs' / 'tool_audit.jsonl'
    path.parent.mkdir()
    secret = 'never-return-this-secret'
    register_secret('test-secret', secret)
    try:
        records = [{'tool': 'system.stats', 'timestamp': '2026-10-09T12:00:00Z', 'ok': True, 'duration_ms': 14.0, 'arguments': {'nested': {'api_key': 'example-public-e263658f228f'}, 'value': secret}, 'message': 'Bearer raw-token', 'internal_credentials': 'not-public'}, {'tool': 'google.calendar.events', 'ok': False, 'arguments': {'query': 'private-calendar-text'}, 'message': 'private-result', 'error': 'private-error'}]
        path.write_text('\n'.join((json.dumps(row) for row in records)), encoding='utf-8')
        result = activity_snapshot(tmp_path)
        serialized = json.dumps(result)
        for value in [secret, 'example-public-e263658f228f', 'raw-token', 'private-calendar-text', 'private-result', 'private-error', 'not-public']:
            assert value not in serialized
        assert result['events'][0]['status'] == 'failed'
        assert result['events'][1]['duration_ms'] == 14
        assert 'internal_credentials' not in result['events'][1]
    finally:
        clear_registry()

def test_activity_ignores_incomplete_rows_and_limits_history(tmp_path):
    path = tmp_path / 'logs' / 'tool_audit.jsonl'
    path.parent.mkdir()
    rows = [json.dumps({'tool': f'system.sample{i}', 'ok': True}) for i in range(50)]
    path.write_text('not-json\n' + '\n'.join(rows) + '\n{"tool":', encoding='utf-8')
    events = activity_snapshot(tmp_path)['events']
    assert len(events) == 30
    assert events[0]['tool'] == 'system.sample49'
    assert events[-1]['tool'] == 'system.sample20'

def test_empty_and_unavailable_activity_are_distinct(tmp_path):
    assert activity_snapshot(tmp_path)['available'] is True
    assert activity_snapshot(tmp_path)['events'] == []
    assert activity_snapshot(None)['available'] is False

def test_gateway_routes_keep_host_origin_and_write_protection(tmp_path):
    config = load_config(REPO_ROOT / 'config', data_dir=tmp_path, env={})
    server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {}))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = f'127.0.0.1:{server.server_port}'

    def call(path, method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {}, body=body)
            res = conn.getresponse()
            return (res.status, json.loads(res.read()))
        finally:
            conn.close()
    try:
        for path in ['/api/workspace', '/api/activity']:
            assert call(path)[0] == 200
            assert call(path, headers={'Origin': 'https://evil.example'})[0] == 403
            assert call(path, headers={'Host': 'evil.example'})[0] == 403
            assert call(path, headers={'Sec-Fetch-Site': 'cross-site'})[0] == 403
            assert call(path, 'POST', {'Origin': f'http://{host}', 'X-Hanni-Token': server.chat.token, 'Content-Type': 'application/json'}, '{}')[0] == 404
        assert not (tmp_path / 'logs').exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        server.chat.close()
        server.chat.db.close()
