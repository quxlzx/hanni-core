import pytest
from hanni.mcp.security import MCPConfigurationError
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.inert_mcp import configure, NAME, COMMAND
from scripts.campaign8_ui.safe_gaps import cases
from hanni.laya.intelligence import analyze_statement

def config(name='Other unapproved fixture'):
    return {'name': name, 'transport': 'stdio', 'command': COMMAND, 'args': [], 'auto_connect': False}

def test_original_approved_hash_gates_enable_disable_mock_initialization(tmp_path):
    with original_backend(tmp_path / 'owned') as backend:
        fixture = configure(backend)
        manager = backend.server.mcp.require()
        row = manager.snapshot()['servers'][0]
        assert row['name'] == NAME and row['enabled'] is False
        enabled = manager.enable_server(fixture['server_id'])['servers'][0]
        assert enabled['enabled'] is True and enabled['state'] == 'connected'
        assert enabled['tools'] == []
        disabled = manager.disable_server(fixture['server_id'])['servers'][0]
        assert disabled['enabled'] is False and disabled['state'] == 'disabled'
        assert backend.chat.ready is False
        assert all((r['outcome'] in {'CONTROLLED_UNAVAILABLE', 'CONTROLLED_MOCK'} for r in backend.calls))

def test_unapproved_import_cannot_initialize_or_enable_even_with_fixture_leaf(tmp_path):
    with original_backend(tmp_path / 'owned') as backend:
        configure(backend)
        manager = backend.server.mcp.require()
        row = manager.add(config())
        before = len(backend.calls)
        with pytest.raises(MCPConfigurationError, match='Review and approve'):
            manager.enable_server(row['id'])
        with pytest.raises(MCPConfigurationError, match='approval does not match'):
            manager.connect(row['id'], approved=True, expected_config_hash='wrong')
        assert len(backend.calls) == before
        assert manager.snapshot()['servers'][1]['enabled'] is False

def test_every_nonfixture_initialization_is_denied_no_external_fallback(tmp_path):
    with original_backend(tmp_path / 'owned') as backend:
        configure(backend)
        manager = backend.server.mcp.require()
        row = manager.add(config())
        result = manager.connect(row['id'], approved=True, expected_config_hash=row['config_hash'])
        failed = next((r for r in result['servers'] if r['id'] == row['id']))
        assert failed['state'] == 'failed' and failed['tools'] == []
        assert all((r['outcome'] in {'CONTROLLED_UNAVAILABLE', 'CONTROLLED_MOCK'} for r in backend.calls))

def test_final_inputs_use_existing_local_rule_and_no_inference_or_execution():
    inputs, oracles = cases()
    assert {r['id'] for r in inputs} == {r['id'] for r in oracles}
    positive = next((r for r in inputs if r['id'] == 'safe-gap-positive-local-proposal'))
    text = next((s['value'] for s in positive['steps'] if s['action'] == 'fill'))
    candidate = analyze_statement(text)
    assert candidate is not None and candidate.memory_type == 'preference'
    assert all((s.get('name') not in {'Start benchmark', 'Test & Discover', 'Reconnect', 'Confirm server startup', 'Send message', 'Listen now'} for r in inputs for s in r['steps']))
