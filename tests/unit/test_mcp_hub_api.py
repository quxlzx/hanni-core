"""Owner/session controls and original-controller binding for MCP Hub."""
from dataclasses import replace
import http.client
import json
from pathlib import Path
from types import SimpleNamespace
import threading
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.mcp_hub import MCPHub
from hanni.mcp import runtime
from hanni.tools.base import ToolPermissionError
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]

def config_for(path):
    return load_config(ROOT / 'config', data_dir=path, env={})

def body(operation, data=None, key=None):
    return {'id': key or str(uuid4()), 'operation': operation, 'data': data or {}, 'confirmed': True}

class ManagerProbe:

    def __init__(self):
        self.calls, self.attached = ([], [])

    def add(self, config):
        self.calls.append(('add', config))
        return {'id': 'a' * 32}

    def connect(self, server_id, **kwargs):
        self.calls.append(('connect', server_id, kwargs))
        return {'servers': []}

    def snapshot(self):
        return {'available': True, 'servers': [], 'revision': 0}

    def attach_registry(self, registry):
        self.attached.append(registry)

    def close(self):
        self.calls.append(('close',))

def test_management_uses_original_permission_gate_and_private_audit(tmp_path):
    config = config_for(tmp_path)
    manager = ManagerProbe()
    hub = MCPHub(config, DesktopFeatures(config), manager=manager)
    private = 'owner-private-import-body'
    request = body('add', {'config': {'args': [private]}})
    result = hub.mutate(request)
    assert result['id'] == 'a' * 32
    assert len(manager.calls) == 1
    assert hub.mutate(request) == result and len(manager.calls) == 1
    with pytest.raises(ValueError, match='different action'):
        hub.mutate({**request, 'data': {'config': {}}})
    audit = tmp_path / 'logs/tool_audit.jsonl'
    text = audit.read_text(encoding='utf-8')
    assert private not in text
    row = json.loads(text.splitlines()[0])
    assert row['tool'] == 'workspace.mcp.manage' and row['confirmed'] is True
    assert row['source'] == 'desktop-mcp-hub'
    assert row['correlation_id'] == request['id']
    chat_only = replace(config.permissions.profiles['owner'], chat_only=True)
    restricted = replace(config, permissions=replace(config.permissions, profiles={**config.permissions.profiles, 'owner': chat_only}))
    denied = ManagerProbe()
    with pytest.raises(ToolPermissionError):
        MCPHub(restricted, DesktopFeatures(restricted), manager=denied).mutate(body('add', {'config': {}}))
    assert not denied.calls

@pytest.mark.parametrize('payload', [{'id': str(uuid4()), 'operation': 'add', 'data': {}, 'confirmed': False}, body('powershell.run', {'script': 'arbitrary'}), {**body('export'), 'arguments': {}}, body('test_discover', {'server_id': 'a' * 32, 'approved': True}), body('test_discover', {'server_id': 'a' * 32, 'approved': False, 'expected_config_hash': 'b' * 64})])
def test_no_generic_execution_or_unbound_connection_approval(tmp_path, payload):
    config, manager = (config_for(tmp_path), ManagerProbe())
    hub = MCPHub(config, DesktopFeatures(config), manager=manager)
    with pytest.raises(ValueError):
        hub.mutate(payload)
    assert not manager.calls

def test_explicit_connection_receives_captured_configuration_hash(tmp_path):
    config, manager = (config_for(tmp_path), ManagerProbe())
    hub = MCPHub(config, DesktopFeatures(config), manager=manager)
    hub.mutate(body('test_discover', {'server_id': 'a' * 32, 'approved': True, 'expected_config_hash': 'b' * 64}))
    assert manager.calls == [('connect', 'a' * 32, {'approved': True, 'expected_config_hash': 'b' * 64})]

def test_runtime_only_binds_actual_controller_from_same_data_directory(tmp_path):
    config, manager = (config_for(tmp_path), ManagerProbe())
    hub = MCPHub(config, DesktopFeatures(config), manager=manager)
    registry = build_default_registry(config)
    runtime.install(hub)
    try:
        runtime.attach_controller(config_for(tmp_path / 'other'), registry)
        assert not manager.attached
        runtime.attach_controller(config, registry)
        assert manager.attached == [registry]
        assert hub.controller_registry is registry
        assert hub.snapshot()['controller_attached']
        hub.close()
        runtime.attach_controller(config, registry)
        assert manager.attached == [registry]
    finally:
        runtime.uninstall(hub)

def test_live_controller_stop_has_final_authority_over_management(tmp_path):
    from hanni.core.shutdown import Actor, EmergencyStopActive, StopSource
    config, manager = (config_for(tmp_path), ManagerProbe())
    hub = MCPHub(config, DesktopFeatures(config), manager=manager)
    registry = build_default_registry(config)
    hub.attach_controller(registry, model_tools_enabled=True, observe_first=True)
    registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('MCP verification'), reason='Verify stop authority')
    with pytest.raises(EmergencyStopActive):
        hub.mutate(body('add', {'config': {}}))
    assert not manager.calls

@pytest.fixture
def server(tmp_path):
    from hanni.dashboard.server import DashboardServer
    telemetry = SimpleNamespace(config=config_for(tmp_path), snapshot=lambda: {})
    service = DashboardServer(0, telemetry)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    yield service
    service.shutdown()
    service.server_close()
    thread.join(timeout=5)

def http_call(server, path, *, method='GET', data=None, authorized=True, origin=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    headers = {'Content-Type': 'application/json'}
    if authorized:
        headers['X-Hanni-Token'] = server.chat.token
        headers['Origin'] = origin or f'http://127.0.0.1:{server.server_port}'
    try:
        connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

def test_private_mcp_projection_and_mutation_are_session_isolated(server):
    assert http_call(server, '/api/mcp', authorized=False)[0] == 403
    assert http_call(server, '/api/mcp/export', authorized=False)[0] == 403
    assert http_call(server, '/api/mcp', origin='http://foreign.invalid')[0] == 403
    request = body('add', {'config': {'name': 'Persisted test server', 'transport': 'stdio', 'command': 'missing-executable'}})
    assert http_call(server, '/api/mcp', method='POST', data=request, authorized=False)[0] == 403
    assert http_call(server, '/api/mcp', method='POST', data=request, origin='http://foreign.invalid')[0] == 403
    status, snapshot = http_call(server, '/api/mcp')
    assert status == 200 and snapshot['servers'] == []
    status, added = http_call(server, '/api/mcp', method='POST', data=request)
    assert status == 200 and added['state'] == 'disabled'
    assert http_call(server, '/api/mcp', method='POST', data=request)[1] == added
    status, snapshot = http_call(server, '/api/mcp')
    assert status == 200 and len(snapshot['servers']) == 1
    assert snapshot['servers'][0]['tools'] == []
    assert not snapshot['controller_attached']
    assert http_call(server, '/api/mcp/call', method='POST', data=body('call'))[0] == 404

def test_export_is_fixed_atomic_nonsecret_local_file_and_idempotent(server):
    request = body('export')
    status, result = http_call(server, '/api/mcp', method='POST', data=request)
    assert status == 200
    path = Path(result['file']['path'])
    assert path.parent == server.mcp.root / 'mcp' / 'exports'
    assert json.loads(path.read_text(encoding='utf-8')) == result['configuration']
    assert http_call(server, '/api/mcp', method='POST', data=request)[1] == result
    assert len(list(path.parent.glob('*.json'))) == 1
    assert list(path.parent.glob('*.tmp')) == []
    assert http_call(server, '/api/mcp/export')[1] == result['configuration']
    assert http_call(server, '/api/mcp', method='POST', data=body('export', {'path': 'arbitrary'}))[0] == 400
