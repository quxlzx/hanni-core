import pytest
from hanni.mcp.security import MCPConfigurationError
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.inert_mcp import configure, TOOL, TOOL_NAME
from scripts.campaign8_ui.mcp_tool_controls import cases

def test_original_discovery_definition_approval_registration_and_disable(tmp_path):
    with original_backend(tmp_path / 'owned') as backend:
        fixture = configure(backend, tool_metadata=True)
        manager = backend.server.mcp.require()
        server = manager.snapshot()['servers'][0]
        tool = server['tools'][0]
        assert tool['original_name'] == TOOL_NAME
        assert tool['input_schema'] == TOOL['inputSchema']
        assert tool['approval'] is None and tool['enabled'] is False
        before = len(backend.calls)
        with pytest.raises(MCPConfigurationError, match='changed or is invalid'):
            manager.approve_tools(fixture['server_id'], [{'original_name': TOOL_NAME, 'definition_hash': 'wrong', 'classification': 'read_only'}])
        assert len(backend.calls) == before
        manager.approve_tools(fixture['server_id'], [{'original_name': TOOL_NAME, 'definition_hash': tool['definition_hash'], 'classification': 'read_only'}])
        approved = manager.snapshot()['servers'][0]['tools'][0]
        assert approved['enabled'] and approved['available']
        assert backend.registry.get(tool['internal_id']).name == tool['internal_id']
        connection = manager.connections[fixture['server_id']]
        with pytest.raises(OSError, match='No external tool execution'):
            connection.request('call', {'name': TOOL_NAME, 'arguments': {'label': 'synthetic'}})
        manager.disable_tools(fixture['server_id'], [TOOL_NAME])
        disabled = manager.snapshot()['servers'][0]['tools'][0]
        assert not disabled['enabled'] and (not disabled['available'])
        assert disabled['approval']['definition_hash'] == tool['definition_hash']
        assert all((r['dependency'] != 'inert MCP call' for r in backend.calls))

def test_metadata_inputs_are_finite_and_never_invoke_tools():
    inputs, oracles = cases()
    assert len(inputs) == 4
    assert {r['id'] for r in inputs} == {r['id'] for r in oracles}
    assert not any((s.get('name') in {'Send message', 'Start benchmark', 'Test & Discover', 'Reconnect', 'Confirm server startup'} for r in inputs for s in r['steps']))
