"""Independent original-controller, schema and approval lifecycle evidence.

SDK servers, manager, registry, bounded retrieval and tool execution are real.
Only model selection uses the explicitly disclosed deterministic probe client.
Run after the M3 adapter implementation is frozen.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.mcp.manager import MCPManager
from hanni.tools.base import ConfirmationRequired, ToolError, ToolPermissionError, ToolRequest, ToolValidationError, UnknownToolError
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/mcp_hub_review'))
from session_probe import run_session_probe
from tests.integration.test_mcp_hub_verifier import actual_http_fixture, connected, entries, local_config

@pytest.fixture
def original_registry(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config, data_dir=config.paths.data_dir)

    class EmptyReviewVault:

        def labels(self):
            return ('personal', 'school')

        def get(self, account):
            return None

        def preferences(self):
            return {}
    registry.google_access._vault = EmptyReviewVault()
    return registry

def approve(manager, server, original_name, classification='read_only'):
    manager.enable_server(server['id'])
    current = next((row for row in manager.snapshot()['servers'] if row['id'] == server['id']))
    tool = next((row for row in current['tools'] if row['original_name'] == original_name))
    manager.approve_tools(server['id'], [{'original_name': original_name, 'definition_hash': tool['definition_hash'], 'classification': classification}])
    current = next((row for row in manager.snapshot()['servers'] if row['id'] == server['id']))
    return next((row for row in current['tools'] if row['original_name'] == original_name))

def assert_stale_handler_denied(definition, registry, request):
    try:
        result = definition.handler(dict(request.arguments), registry.context, request)
    except (ToolError, ValueError):
        return
    assert not result.ok, 'Cached adapter executed after approval was revoked'

@pytest.mark.parametrize('transport', ['stdio', 'streamable_http'])
def test_original_model_facing_session_executes_actual_external_name_and_audits(tmp_path, original_registry, transport):

    def exercise(config, ledger):
        builtin = original_registry.get('system.stats')
        host = McpHost(original_registry, read_only=True)
        assert not any((tool.capability_id.startswith('mcp.') for tool in host.route('mock.echo message').tools))
        manager = MCPManager(tmp_path / 'hub', registry=original_registry)
        try:
            server = connected(manager, config)
            tool = approve(manager, server, 'mock.echo')
            assert tool['enabled'] and tool['available']
            assert original_registry.get('system.stats') is builtin
            assert any((row.capability_id == tool['internal_id'] for row in host.route('Use mock.echo to echo a message').tools))
            result = run_session_probe(original_registry, 'Use mock.echo to echo the message independent-controller-proof', tool['internal_id'], {'message': 'independent-controller-proof'})
            assert 'independent-controller-proof' in result['answer']
            assert any((item['function']['parameters'] == tool['input_schema'] for menu in result['menus'] for item in menu))
            assert [row['name'] for row in entries(ledger) if row['event'] == 'call'] == ['mock.echo']
            audit = original_registry.context.audit.path
            rows = entries(audit)
            external = [row for row in rows if row.get('tool') == tool['internal_id']]
            assert external and external[-1]['source'] == 'mcp.model'
            definition = original_registry.get(tool['internal_id'])
            manager.disable_tools(server['id'], ['mock.echo'])
            assert not any((row.capability_id == tool['internal_id'] for row in host.route('Use mock.echo to echo a message').tools))
            before = len(entries(ledger))
            assert_stale_handler_denied(definition, original_registry, ToolRequest(tool['internal_id'], {'message': 'must-not-execute'}, source='independent-stale-cache'))
            assert len(entries(ledger)) == before
            with pytest.raises(UnknownToolError):
                original_registry.execute(ToolRequest(tool['internal_id'], {'message': 'must-not-execute'}))
            assert original_registry.get('system.stats') is builtin
        finally:
            manager.close()
    if transport == 'stdio':
        config, _, ledger = local_config(tmp_path / 'server')
        exercise(config, ledger)
    else:
        with actual_http_fixture(tmp_path / 'server') as (config, _, ledger):
            exercise(config, ledger)

def test_nested_full_schema_preserved_in_original_menu_and_enforced_before_dispatch(tmp_path, original_registry):
    config, control, ledger = local_config(tmp_path / 'server')
    schema = {'type': 'object', 'properties': {'payload': {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'$ref': '#/$defs/item'}, 'minItems': 2, 'maxItems': 3}, 'mode': {'enum': ['safe', 'review']}, 'nullable': {'type': ['string', 'null']}}, 'required': ['items', 'mode'], 'additionalProperties': False}}, 'required': ['payload'], 'additionalProperties': False, '$defs': {'item': {'type': 'integer', 'minimum': 1, 'maximum': 8}}, 'allOf': [{'properties': {'payload': {'oneOf': [{'properties': {'mode': {'const': 'safe'}}}, {'properties': {'mode': {'const': 'review'}}}]}}}]}
    raw = {'name': 'fixture.deep_echo', 'description': 'Echo the exact nested payload for independent schema verification.', 'inputSchema': schema, 'outputSchema': {'type': 'object', 'properties': {'original_name': {'type': 'string'}, 'arguments': {'type': 'object'}}, 'required': ['original_name', 'arguments'], 'additionalProperties': False}, 'annotations': {'readOnlyHint': True, 'title': 'Nested schema'}, '_meta': {'verifier': 'nested-v1'}}
    control.write_text(json.dumps({'tools': [raw]}), encoding='utf-8')
    manager = MCPManager(tmp_path / 'hub', registry=original_registry)
    try:
        server = connected(manager, config)
        tool = approve(manager, server, raw['name'])
        assert tool['input_schema'] == schema and tool['output_schema'] == raw['outputSchema']
        assert tool['annotations'] == raw['annotations'] and tool['metadata']['_meta'] == raw['_meta']
        definition = original_registry.get(tool['internal_id'])
        assert definition.argument_schema() == schema
        invalid = [{'payload': {'items': [1], 'mode': 'safe'}}, {'payload': {'items': [1, True], 'mode': 'safe'}}, {'payload': {'items': [1, 9], 'mode': 'safe'}}, {'payload': {'items': [1, 2], 'mode': 'unsafe'}}, {'payload': {'items': [1, 2], 'mode': 'safe', 'extra': 1}}, {'payload': {'items': [1, 2], 'mode': 'safe'}, 'extra': 1}]
        before = len(entries(ledger))
        for arguments in invalid:
            with pytest.raises(ToolValidationError):
                original_registry.execute(ToolRequest(tool['internal_id'], arguments))
        assert len(entries(ledger)) == before
        valid = {'payload': {'items': [1, 2], 'mode': 'safe', 'nullable': None}}
        response = run_session_probe(original_registry, 'Use fixture.deep_echo to echo a nested payload', tool['internal_id'], valid)
        assert 'fixture.deep_echo' in response['answer']
        assert [row['name'] for row in entries(ledger) if row['event'] == 'call'] == ['fixture.deep_echo']
        control.write_text(json.dumps({'tools': [raw], 'invalid_output': True}), encoding='utf-8')
        try:
            result = original_registry.execute(ToolRequest(tool['internal_id'], valid))
        except ToolError:
            pass
        else:
            assert not result.ok, 'Output outside the original output schema was accepted'
    finally:
        manager.close()

def test_long_shared_prefix_and_cross_server_names_have_distinct_original_controller_wires(tmp_path, original_registry):
    names = ['fixture.' + 'shared_prefix_' * 11 + suffix for suffix in ('alpha', 'beta')]
    raw_tools = [{'name': name, 'description': f'Independent {suffix} echo verification.', 'inputSchema': {'type': 'object', 'properties': {'message': {'type': 'string'}}, 'required': ['message'], 'additionalProperties': False}} for name, suffix in zip(names, ('alpha', 'beta'))]
    manager = MCPManager(tmp_path / 'hub', registry=original_registry)
    tools, ledgers = ([], [])
    try:
        for index in range(2):
            config, control, ledger = local_config(tmp_path / f'server-{index}')
            config['name'] = f'Independent collision server {index}'
            control.write_text(json.dumps({'tools': raw_tools}), encoding='utf-8')
            server = connected(manager, config)
            ledgers.append(ledger)
            tools.extend(({**approve(manager, server, name), 'verifier_server_name': config['name']} for name in names))
        assert len({tool['internal_id'] for tool in tools}) == 4
        host = McpHost(original_registry, read_only=True)
        wires = []
        for tool in tools:
            query = f"Use {tool['verifier_server_name']} {tool['original_name']} to echo the message collision proof"
            decision = host.route(query)
            selected = next((row for row in decision.tools if row.capability_id == tool['internal_id']))
            wires.append(selected.wire_name)
            probe = run_session_probe(original_registry, query, tool['internal_id'], {'message': 'collision proof'})
            assert tool['original_name'] in probe['answer']
        assert len(set(wires)) == 4 and all((len(wire) <= 64 for wire in wires))
        for ledger in ledgers:
            assert [row['name'] for row in entries(ledger) if row['event'] == 'call'] == names
        removed_server = manager.snapshot()['servers'][0]
        cached = original_registry.get(removed_server['tools'][0]['internal_id'])
        before = sum((len(entries(path)) for path in ledgers))
        manager.remove(removed_server['id'])
        assert_stale_handler_denied(cached, original_registry, ToolRequest(cached.name, {'message': 'must-not-execute'}))
        assert sum((len(entries(path)) for path in ledgers)) == before
        for tool in manager.snapshot()['servers'][0]['tools']:
            assert original_registry.get(tool['internal_id'])
    finally:
        manager.close()

@pytest.mark.parametrize('field', ['description', 'inputSchema', 'outputSchema', 'annotations', '_meta'])
def test_any_security_definition_change_revokes_cached_adapter_and_requires_exact_reapproval(tmp_path, original_registry, field):
    from tests.fixtures.mcp_hub_mock import TOOLS
    config, control, ledger = local_config(tmp_path / 'server')
    raw = deepcopy(TOOLS[1])
    control.write_text(json.dumps({'tools': [raw]}), encoding='utf-8')
    manager = MCPManager(tmp_path / 'hub', registry=original_registry)
    try:
        server = connected(manager, config)
        old = approve(manager, server, 'mock.echo')
        cached = original_registry.get(old['internal_id'])
        if field == 'description':
            raw[field] += ' Changed reviewed purpose.'
        elif field in {'inputSchema', 'outputSchema'}:
            raw[field]['description'] = 'Changed security definition'
        elif field == 'annotations':
            raw[field] = {'readOnlyHint': False, 'destructiveHint': True}
        else:
            raw[field] = {'fixture': 'changed-version'}
        control.write_text(json.dumps({'tools': [raw]}), encoding='utf-8')
        manager.refresh(server['id'])
        changed = manager.snapshot()['servers'][0]['tools'][0]
        assert changed['definition_hash'] != old['definition_hash']
        assert changed['version'] > old['version'] and (not changed['enabled']) and (not changed['available'])
        assert changed['classification'] == 'unknown' and changed['approval'] is None
        before = len(entries(ledger))
        assert_stale_handler_denied(cached, original_registry, ToolRequest(old['internal_id'], {'message': 'blocked'}))
        assert len(entries(ledger)) == before
        with pytest.raises(ValueError):
            manager.approve_tools(server['id'], [{'original_name': 'mock.echo', 'definition_hash': old['definition_hash'], 'classification': 'read_only'}])
        new = approve(manager, server, 'mock.echo')
        assert new['available']
    finally:
        manager.close()

def test_imported_write_retains_original_confirmation_profile_and_safe_mode_gates(tmp_path, original_registry):
    from hanni.core.identity import Actor
    from hanni.core.shutdown import EmergencyStopActive, StopSource
    config, _, ledger = local_config(tmp_path / 'server')
    manager = MCPManager(tmp_path / 'hub', registry=original_registry)
    try:
        server = connected(manager, config)
        tool = approve(manager, server, 'mock.create_record', 'write')
        arguments = {'title': 'Independent synthetic record'}
        before = len(entries(ledger))
        with pytest.raises(ConfirmationRequired):
            original_registry.execute(ToolRequest(tool['internal_id'], arguments))
        with pytest.raises(ToolPermissionError):
            original_registry.execute(ToolRequest(tool['internal_id'], arguments, actor_profile='nonexistent-profile', confirmed=True))
        original_registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('verification'), reason='Independent isolated gate test')
        with pytest.raises((EmergencyStopActive, UnknownToolError)):
            original_registry.execute(ToolRequest(tool['internal_id'], arguments, confirmed=True))
        assert len(entries(ledger)) == before
        original_registry.context.emergency_stop.clear(Actor.owner('verification'))
        assert not any((row['available'] for row in manager.snapshot()['servers'][0]['tools']))
        manager.reconnect(server['id'])
        result = original_registry.execute(ToolRequest(tool['internal_id'], arguments, confirmed=True))
        assert result.ok
        assert [row['name'] for row in entries(ledger) if row['event'] == 'call'] == ['mock.create_record']
    finally:
        manager.close()

@pytest.mark.parametrize('secret', ['ax4z', 'independent-long-credential-echo-unique'])
def test_server_echoed_authentication_value_never_reaches_public_snapshot_or_model_schema(tmp_path, original_registry, secret):
    from tests.fixtures.mcp_hub_mock import TOOLS
    with actual_http_fixture(tmp_path / 'server') as (config, control, ledger):
        raw = deepcopy(TOOLS[1])
        raw['description'] = f'Echo a message. Account reference {secret} is private.'
        control.write_text(json.dumps({'require_bearer': secret, 'tools': [raw]}), encoding='utf-8')
        config['auth'] = {'type': 'bearer_env', 'reference': 'INDEPENDENT_ECHO_AUTH_REF'}
        manager = MCPManager(tmp_path / 'hub', registry=original_registry, env={'INDEPENDENT_ECHO_AUTH_REF': secret})
        try:
            server = connected(manager, config)
            assert secret not in json.dumps(manager.snapshot())
            if server['state'] in {'authentication_required', 'failed'}:
                assert not server['tools']
                assert not any((row['event'] == 'call' for row in entries(ledger)))
                return
            assert server['state'] == 'connected', server['error']
            tool = approve(manager, server, 'mock.echo')
            decision = McpHost(original_registry, read_only=True).route('Use mock.echo to echo a supplied message')
            imported = next((row for row in decision.tools if row.capability_id == tool['internal_id']))
            assert secret not in json.dumps(imported.openai_schema())
            assert not any((row['event'] == 'call' for row in entries(ledger)))
        finally:
            manager.close()
            assert secret.encode() not in (tmp_path / 'hub/mcp/hub.sqlite3').read_bytes()

def test_genuine_sdk_tool_list_notification_revokes_approval_and_refreshes_definition(tmp_path, original_registry):
    config, control, ledger = local_config(tmp_path / 'server')
    config['args'][0] = str(ROOT / 'scripts/mcp_hub_review/notification_server.py')
    manager = MCPManager(tmp_path / 'hub', registry=original_registry)
    try:
        server = connected(manager, config)
        old = approve(manager, server, 'mock.echo')
        cached = original_registry.get(old['internal_id'])
        control.write_text(json.dumps({'revision': 1}), encoding='utf-8')
        until = time.monotonic() + 12
        changed = None
        while time.monotonic() < until:
            current = manager.snapshot()['servers'][0]
            if current['tools'] and current['tools'][0]['definition_hash'] != old['definition_hash']:
                changed = current['tools'][0]
                break
            time.sleep(0.05)
        assert any((row['event'] == 'notification' for row in entries(ledger))), entries(ledger)
        assert changed is not None, 'Actual SDK notification did not trigger refreshed definitions'
        assert not changed['enabled'] and (not changed['available']) and (changed['approval'] is None)
        before = len(entries(ledger))
        assert_stale_handler_denied(cached, original_registry, ToolRequest(old['internal_id'], {'message': 'must-not-execute'}))
        assert len(entries(ledger)) == before
        assert not any((row['event'] == 'call' for row in entries(ledger)))
    finally:
        manager.close()
