"""Imported definitions use HANNI's original registry/host/session execution gates."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
import psutil
import pytest
from hanni.config.loader import load_config
from hanni.core.shutdown import Actor, StopSource
from hanni.mcp.adapter import result_contract
from hanni.mcp.host import McpHost
from hanni.mcp.manager import MCPManager
from hanni.tools.base import ConfirmationRequired, ToolError, ToolPermissionError, ToolRequest, ToolValidationError, UnknownToolError
from hanni.tools.registry import build_default_registry
from tests.helpers import write_config_dir
from tests.unit.test_mcp_hub import connect, ledger, stdio_config

@pytest.fixture
def imported(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    count = len(registry.definitions())
    manager = MCPManager(config.paths.data_dir, registry)
    server = connect(manager, stdio_config(tmp_path))
    yield (manager, registry, server, count)
    manager.close()

def enable(manager, server, name='mock.echo', classification='read_only'):
    tool = next((tool for tool in server['tools'] if tool['original_name'] == name))
    manager.approve_tools(server['id'], [{'original_name': name, 'definition_hash': tool['definition_hash'], 'classification': classification}])
    return tool['internal_id']

def test_hot_registry_original_name_execution_and_correlated_private_audit(imported, tmp_path):
    hub, registry, server, count = imported
    cached_search = registry.capabilities.search('fixture echo message')
    assert not any((item['id'].startswith('mcp.') for item in cached_search))
    identity = enable(hub, server)
    assert len(registry.definitions()) == count + 1
    assert any((item['id'] == identity for item in registry.capabilities.search('fixture echo message')))
    schema = registry.capabilities.get(identity)
    assert schema['input_schema'] == server['tools'][1]['input_schema']
    assert schema['returns'] == server['tools'][1]['output_schema'] and schema['source'] == 'mcp'
    private = 'private-owner-message-never-in-audit'
    result = registry.capabilities.call(ToolRequest(identity, {'message': private}))
    assert result.ok and result.data['structured_content'] == {'message': private}
    calls = [row for row in ledger(tmp_path) if row['event'] == 'call']
    assert [row['name'] for row in calls] == ['mock.echo']
    audit = registry.context.audit.tail(1)[0]
    assert audit['correlation_id'] == result.data['correlation']['correlation_id']
    assert private not in json.dumps(audit)
    with hub.store.lock:
        manager_audit = hub.store.db.execute("SELECT details FROM audit WHERE operation='call_completed'").fetchone()[0]
    assert audit['correlation_id'] in manager_audit and private not in manager_audit
    hub.disable_tools(server['id'], ['mock.echo'])
    assert len(registry.definitions()) == count
    assert not any((item['id'] == identity for item in registry.capabilities.search('fixture echo message')))

def test_generic_retrieval_index_tracks_real_mcp_approval_disable_and_permission(imported):
    from hanni.tools.discovery import index_for
    hub, registry, server, _ = imported
    before = index_for(registry)
    assert not any((row.name.startswith('mcp.') for row in before.rank('fixture echo message')))
    identity = enable(hub, server)
    current = index_for(registry)
    assert current is not before
    assert any((row.name == identity for row in current.rank('fixture echo message')))
    assert registry.get(identity).argument_schema() == next((t for t in server['tools'] if t['original_name'] == 'mock.echo'))['input_schema']
    write = enable(hub, server, 'mock.create_record', 'write')
    host = McpHost(registry)
    assert [tool.capability_id for tool in host.select_tools('echo a supplied fixture message')] == [identity]
    assert all((row.name != write for row in host._retrieval_candidates('fixture create record title')))
    hub.disable_tools(server['id'], ['mock.echo'])
    removed = index_for(registry)
    assert removed is not current
    assert not any((row.name == identity for row in removed.rank('fixture echo message')))

def test_original_host_retrieves_import_and_preserves_read_only_policy(imported):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    host = McpHost(registry)
    selected = host.select_tools('Use the connected Fixture echo tool to echo a supplied message.')
    assert [tool.capability_id for tool in selected] == [identity]
    assert selected[0].openai_schema()['function']['parameters'] == server['tools'][1]['input_schema']
    assert host.call(selected[0], {'message': 'HANNI integration'})['ok']
    write = enable(hub, server, 'mock.create_record', 'write')
    assert host.select_tools('Use Fixture create_record to create a record.') == ()
    assert host.call(host._as_tool(registry.get(write)), {'title': 'record'})['error']['code'] == 'PERMISSION_DENIED'

def test_disabled_removed_and_stale_handlers_never_invoke_external_server(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    old = registry.get(identity)
    old_menu = McpHost(registry)._as_tool(old)
    hub.disable_tools(server['id'], ['mock.echo'])
    with pytest.raises(UnknownToolError):
        registry.execute(ToolRequest(identity, {'message': 'denied'}))
    with pytest.raises(ToolPermissionError):
        old.handler({'message': 'denied'}, registry.context, ToolRequest(identity, {'message': 'denied'}))
    assert not McpHost(registry).call(old_menu, {'message': 'denied'})['ok']
    hub.remove(server['id'])
    with pytest.raises((ToolPermissionError, ValueError)):
        old.handler({'message': 'denied'}, registry.context, ToolRequest(identity, {}))
    assert not any((row['event'] == 'call' for row in ledger(tmp_path)))

def test_schema_validation_preserves_nested_types_and_does_not_call_on_invalid_input(imported, tmp_path):
    hub, registry, server, _ = imported
    from tests.fixtures.mcp_hub_mock import TOOLS
    tools = deepcopy(TOOLS)
    tools[1]['inputSchema'] = {'type': 'object', 'properties': {'message': {'type': 'string'}, 'payload': {'type': 'object', 'properties': {'count': {'type': 'integer'}, 'items': {'type': 'array', 'items': {'type': 'number'}}}, 'required': ['count'], 'additionalProperties': False}}, 'required': ['message', 'payload'], 'additionalProperties': False}
    (tmp_path / 'control.json').write_text(json.dumps({'tools': tools}), encoding='utf-8')
    refreshed = hub.refresh(server['id'])['servers'][0]
    identity = enable(hub, refreshed)
    for arguments in [{'message': 'x'}, {'message': 'x', 'payload': {'count': True}}, {'message': 'x', 'payload': {'count': 1, 'unknown': 1}}, {'message': 'x', 'payload': {'count': 1, 'items': ['not-a-number']}}]:
        with pytest.raises(ToolValidationError):
            registry.execute(ToolRequest(identity, arguments))
    assert not any((row['event'] == 'call' for row in ledger(tmp_path)))
    assert registry.execute(ToolRequest(identity, {'message': 'ok', 'payload': {'count': 1, 'items': [2.5]}})).ok

def test_imported_write_requires_original_confirmation_and_profile(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server, 'mock.create_record', 'write')
    with pytest.raises(ConfirmationRequired):
        registry.execute(ToolRequest(identity, {'title': 'write'}))
    with pytest.raises(ToolPermissionError):
        registry.execute(ToolRequest(identity, {'title': 'write'}, actor_profile='everyone_else', confirmed=True))
    assert not any((row['event'] == 'call' for row in ledger(tmp_path)))
    result = registry.execute(ToolRequest(identity, {'title': 'approved'}, confirmed=True))
    assert result.ok and result.data['structured_content']['created']

def test_refresh_prevents_old_model_menu_from_invoking_reapproved_changed_tool(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    host = McpHost(registry)
    old = host._as_tool(registry.get(identity))
    from tests.fixtures.mcp_hub_mock import TOOLS
    tools = deepcopy(TOOLS)
    tools[1]['description'] = 'Echo a message with changed behavior.'
    (tmp_path / 'control.json').write_text(json.dumps({'tools': tools}), encoding='utf-8')
    refreshed = hub.refresh(server['id'])['servers'][0]
    enable(hub, refreshed)
    assert host.call(old, {'message': 'stale'})['error']['code'] == 'DEFINITION_CHANGED'
    assert not any((row['event'] == 'call' for row in ledger(tmp_path)))

def test_external_error_and_output_schema_rejection(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    (tmp_path / 'control.json').write_text(json.dumps({'error': True}), encoding='utf-8')
    result = registry.execute(ToolRequest(identity, {'message': 'error'}))
    assert not result.ok and result.error['code'] == 'MCP_TOOL_ERROR'
    (tmp_path / 'control.json').write_text(json.dumps({'invalid_output': True}), encoding='utf-8')
    with pytest.raises(ToolError, match='output schema'):
        registry.execute(ToolRequest(identity, {'message': 'invalid'}))

def test_binary_and_resource_contents_are_inert_bounded_data():
    raw = {'content': [{'type': 'image', 'mimeType': 'image/png', 'data': 'AA=='}, {'type': 'resource_link', 'name': 'Fixture', 'uri': 'https://example.com/resource'}]}
    ok, _, data = result_contract(raw, None)
    assert ok and data['content'] == raw['content']
    with pytest.raises(ValueError):
        result_contract({'content': [{'type': 'text', 'text': 'x' * 1100000}]}, None)

def test_emergency_stop_cancels_live_request_and_owned_pid_without_auto_reconnect(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    (tmp_path / 'control.json').write_text(json.dumps({'delay': 30}), encoding='utf-8')
    outcomes = []

    def invoke():
        try:
            registry.execute(ToolRequest(identity, {'message': 'cancel'}))
        except BaseException as exc:
            outcomes.append(exc)
    thread = threading.Thread(target=invoke)
    thread.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and (not any((row['event'] == 'call' for row in ledger(tmp_path)))):
        time.sleep(0.02)
    start = time.monotonic()
    registry.context.emergency_stop.trip(source=StopSource.LOCAL_TERMINAL, requested_by=Actor.local('fixture'), reason='isolated test')
    assert time.monotonic() - start < 0.5
    thread.join(timeout=5)
    assert not thread.is_alive() and outcomes
    pid = int((tmp_path / 'ledger.pid').read_text(encoding='utf-8'))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and psutil.pid_exists(pid):
        time.sleep(0.02)
    assert not psutil.pid_exists(pid)
    registry.context.emergency_stop.clear(Actor.local('fixture'))
    assert hub.snapshot()['servers'][0]['state'] == 'disconnected'
    assert identity not in {item.name for item in registry.definitions()}

def test_call_timeout_does_not_replay_or_spawn_replacement(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    (tmp_path / 'control.json').write_text(json.dumps({'delay': 30}), encoding='utf-8')
    with pytest.raises(TimeoutError):
        registry.execute(ToolRequest(identity, {'message': 'timeout'}))
    assert len([row for row in ledger(tmp_path) if row['event'] == 'call']) == 1

def test_unexpected_server_death_revokes_idle_registry_availability(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    process = psutil.Process(int((tmp_path / 'ledger.pid').read_text(encoding='utf-8')))
    process.kill()
    process.wait(timeout=3)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and hub.snapshot()['servers'][0]['state'] == 'connected':
        time.sleep(0.02)
    snapshot = hub.snapshot()['servers'][0]
    assert snapshot['state'] == 'failed' and (not any((tool['available'] for tool in snapshot['tools'])))
    assert identity not in {tool.name for tool in registry.definitions()}

def test_actual_list_changed_notification_refreshes_and_revokes_changed_approval(imported, tmp_path):
    hub, registry, server, _ = imported
    identity = enable(hub, server)
    from tests.fixtures.mcp_hub_mock import TOOLS
    tools = deepcopy(TOOLS)
    tools[1]['description'] = 'Changed echo description from an actual notification.'
    (tmp_path / 'control.json').write_text(json.dumps({'tools': tools, 'notify_revision': 1}), encoding='utf-8')
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = hub.snapshot()['servers'][0]
        if current['tools'][1]['version'] == 2:
            break
        time.sleep(0.02)
    assert current['tools'][1]['version'] == 2 and (not current['tools'][1]['enabled'])
    assert identity not in {tool.name for tool in registry.definitions()}
    assert any((row['event'] == 'notification' for row in ledger(tmp_path)))
    assert not any((row['event'] == 'call' for row in ledger(tmp_path)))

def test_common_server_label_does_not_steal_original_builtin_routing(imported):
    hub, registry, server, _ = imported
    config = {**server['config'], 'name': 'Status'}
    hub.update(server['id'], config, expected_config_hash=server['config_hash'])
    saved = hub.snapshot()['servers'][0]
    server = hub.connect(server['id'], approved=True, expected_config_hash=saved['config_hash'])['servers'][0]
    enable(hub, server, 'mock.get_status')
    host = McpHost(registry)
    assert all((not tool.capability_id.startswith('mcp.') for tool in host.route('What is my CPU status right now?').tools))

def test_unrelated_namespace_collision_rejects_approval_without_mutating_other_tools(imported):
    from hanni.mcp.security import MCPConfigurationError
    from hanni.tools.base import ToolDefinition, ToolResult
    hub, registry, server, count = imported
    identity = server['tools'][1]['internal_id']
    registry.register(ToolDefinition(identity, 'Unrelated trusted extension', 0, 0, {}, {}, lambda args, ctx, request: ToolResult(identity, True, 'Unrelated')))
    unrelated = registry.get(identity)
    with pytest.raises(MCPConfigurationError):
        enable(hub, server)
    assert registry.get(identity) is unrelated
    assert not hub.snapshot()['servers'][0]['tools'][1]['enabled']
    hub.remove(server['id'])
    assert registry.get(identity) is unrelated and len(registry.definitions()) == count + 1
