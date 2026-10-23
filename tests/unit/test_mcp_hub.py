"""Local official-SDK MCP integration and fail-closed configuration tests."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import pytest
from hanni.mcp.manager import MCPManager
from hanni.mcp.security import MCPConfigurationError, endpoint, normalize_config, resolve_credentials, validate_schema
ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / 'tests' / 'fixtures' / 'mcp_hub_mock.py'

@pytest.fixture
def manager(tmp_path):
    hub = MCPManager(tmp_path)
    yield hub
    hub.close()

def stdio_config(tmp_path):
    control, ledger = (tmp_path / 'control.json', tmp_path / 'ledger.jsonl')
    control.write_text('{}', encoding='utf-8')
    return {'name': 'Fixture', 'transport': 'stdio', 'command': sys.executable, 'args': [str(MOCK), '--control', str(control), '--ledger', str(ledger)], 'timeout_seconds': 3}

def connect(hub, config):
    server = hub.add(config)
    result = hub.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
    return result['servers'][0]

def ledger(tmp_path):
    path = tmp_path / 'ledger.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

@pytest.fixture
def http_server(tmp_path):
    config = stdio_config(tmp_path)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, *config['args'], '--transport', 'http', '--port', str(port)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                with urlopen(url + '/health', timeout=0.3):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError('Mock HTTP server failed to start')
        yield {'name': 'HTTP Fixture', 'transport': 'streamable_http', 'url': url + '/mcp/', 'allow_local_http': True, 'timeout_seconds': 3}
    finally:
        process.terminate()
        process.wait(timeout=5)

def test_stdio_initializes_and_discovers_all_pages_without_calling_tools(manager, tmp_path):
    config = stdio_config(tmp_path)
    saved = manager.add(config)
    assert saved['state'] == 'disabled' and manager.runtime is None and (ledger(tmp_path) == [])
    with pytest.raises(MCPConfigurationError):
        manager.connect(saved['id'])
    result = manager.connect(saved['id'], approved=True, expected_config_hash=saved['config_hash'])
    server = result['servers'][0]
    assert server['state'] == 'connected', server['error']
    assert [tool['original_name'] for tool in server['tools']] == ['mock.get_status', 'mock.echo', 'mock.create_record']
    assert all((not tool['enabled'] and (not tool['available']) and (tool['classification'] == 'unknown') for tool in server['tools']))
    assert [row['event'] for row in ledger(tmp_path)] == ['list', 'list']
    assert server['tools'][1]['input_schema']['required'] == ['message']
    assert server['tools'][1]['metadata']['_meta'] == {'fixture': 'echo-v1'}
    assert server['last_connected_at'] and server['last_discovery_at']

def test_streamable_http_initializes_with_actual_protocol(manager, http_server, tmp_path):
    server = connect(manager, http_server)
    assert server['state'] == 'connected', server['error']
    assert len(server['tools']) == 3
    assert all((row['event'] == 'list' for row in ledger(tmp_path)))

def test_persistence_never_launches_or_reenables_disabled_servers(tmp_path):
    hub = MCPManager(tmp_path / 'data')
    config = stdio_config(tmp_path)
    server = connect(hub, config)
    hub.disable_server(server['id'])
    hub.close()
    restored = MCPManager(tmp_path / 'data')
    try:
        item = restored.snapshot()['servers'][0]
        assert item['id'] == server['id'] and item['state'] == 'disabled'
        assert len(item['tools']) == 3 and restored.runtime is None
        assert not any((tool['available'] for tool in item['tools']))
    finally:
        restored.close()

def test_stale_connection_approval_and_update_are_rejected_without_launch(manager, tmp_path):
    server = manager.add(stdio_config(tmp_path))
    changed = {**server['config'], 'args': [*server['config']['args'], '--transport', 'stdio']}
    manager.update(server['id'], changed, expected_config_hash=server['config_hash'])
    with pytest.raises(MCPConfigurationError):
        manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
    with pytest.raises(MCPConfigurationError):
        manager.update(server['id'], changed, expected_config_hash=server['config_hash'])
    assert manager.runtime is None and ledger(tmp_path) == []

def test_refresh_changes_schema_or_description_revokes_definition_approval(manager, tmp_path):
    server = connect(manager, stdio_config(tmp_path))
    tool = server['tools'][1]
    manager.approve_tools(server['id'], [{'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': 'read_only'}])
    from tests.fixtures.mcp_hub_mock import TOOLS
    changed = deepcopy(TOOLS)
    changed[1]['description'] = 'Changed behavior; inspect again.'
    (tmp_path / 'control.json').write_text(json.dumps({'tools': changed}), encoding='utf-8')
    server = manager.refresh(server['id'])['servers'][0]
    updated = server['tools'][1]
    assert updated['version'] == 2 and updated['definition_hash'] != tool['definition_hash']
    assert not updated['enabled'] and updated['approval'] is None
    with pytest.raises(MCPConfigurationError):
        manager.approve_tools(server['id'], [{'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': 'read_only'}])

def test_import_preview_revalidates_and_never_launches_or_overwrites(manager, tmp_path):
    config = stdio_config(tmp_path)
    document = {'mcpServers': {'Imported': {'command': config['command'], 'args': config['args'], 'env': {'FIXTURE_AUTH': '${HANNI_FIXTURE_TOKEN}'}}}}
    preview = manager.preview_import(document)
    assert len(preview['candidates']) == 1 and preview['warnings']
    assert manager.snapshot()['servers'] == [] and manager.runtime is None
    manager.import_configs(preview['candidates'])
    with pytest.raises(MCPConfigurationError):
        manager.import_configs(preview['candidates'])
    assert len(manager.snapshot()['servers']) == 1 and manager.runtime is None
    exported = manager.export_configs()
    assert exported['mcpServers']['Imported']['env_refs'] == {'FIXTURE_AUTH': 'HANNI_FIXTURE_TOKEN'}
    document['mcpServers']['Imported']['env']['FIXTURE_AUTH'] = 'plaintext-private-token'
    assert manager.preview_import(document)['candidates'] == []

@pytest.mark.parametrize('url', ['http://example.com/mcp', 'https://' + '.'.join(('10', '42', '0', '29')) + '/mcp', 'https://' + '.'.join(('10', '42', '0', '30')) + '/mcp', 'https://127.0.0.1/mcp', 'https://user:password@example.com/mcp', 'https://example.com/mcp?token=secret', 'https://example.com/mcp#secret', 'http://127.0.0.1:80/mcp'])
def test_unsafe_endpoints_are_rejected(url):
    with pytest.raises(MCPConfigurationError):
        endpoint(url, allow_local_http=True)

def test_mixed_public_private_dns_is_rejected():
    resolver = lambda *args, **kwargs: [(socket.AF_INET, 0, 0, '', ('' + '.'.join(('11', '42', '0', '36')) + '', 443)), (socket.AF_INET, 0, 0, '', ('127.0.0.1', 443))]
    with pytest.raises(MCPConfigurationError):
        endpoint('https://example.com/mcp', resolve=True, resolver=resolver)

def test_plaintext_secrets_and_automatic_package_download_settings_rejected():
    with pytest.raises(MCPConfigurationError):
        normalize_config({'name': 'Bad', 'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'unknown-package']})
    with pytest.raises(MCPConfigurationError):
        normalize_config({'name': 'Bad', 'transport': 'stdio', 'command': 'python', 'args': ['--token=private']})
    with pytest.raises(MCPConfigurationError):
        normalize_config({'name': 'Bad', 'transport': 'stdio', 'command': 'python', 'env': {'TOKEN': 'secret'}})

def test_credentials_only_resolve_explicit_references():
    config = normalize_config({'name': 'Auth', 'transport': 'streamable_http', 'url': 'https://example.com/mcp', 'auth': {'type': 'bearer_env', 'reference': 'MCP_FIXTURE_AUTH'}})
    env, headers = resolve_credentials(config, env={'MCP_FIXTURE_AUTH': 'fixture-private-token', 'UNRELATED': 'never-inherit'})
    assert env == {} and headers == {'Authorization': 'Bearer fixture-private-token'}
    assert 'fixture-private-token' not in json.dumps(config)

@pytest.mark.parametrize('schema', [{'type': 'object', '$ref': 'https://example.com/schema'}, {'type': 'object', 'properties': {'text': {'type': 'string', 'pattern': '(a+)+$'}}}, {'type': 'array'}, {'type': 'object', 'required': 'not-an-array'}])
def test_unsupported_or_malformed_schemas_are_not_executable(schema):
    with pytest.raises(MCPConfigurationError):
        validate_schema(schema)

def test_remove_leaves_unrelated_user_files(manager, tmp_path):
    unrelated = tmp_path / 'personal-note.txt'
    unrelated.write_text('keep', encoding='utf-8')
    server = manager.add(stdio_config(tmp_path))
    manager.remove(server['id'])
    assert manager.snapshot()['servers'] == [] and unrelated.read_text(encoding='utf-8') == 'keep'

def test_remote_authentication_uses_env_reference_and_never_persists_token(tmp_path, http_server):
    secret = 'isolated-mcp-authentication-token'
    (tmp_path / 'control.json').write_text(json.dumps({'require_bearer': secret}), encoding='utf-8')
    hub = MCPManager(tmp_path / 'authenticated', env={'FIXTURE_TOKEN': secret})
    try:
        config = {**http_server, 'auth': {'type': 'bearer_env', 'reference': 'FIXTURE_TOKEN'}}
        server = connect(hub, config)
        assert server['state'] == 'connected', server['error']
        assert secret not in json.dumps(hub.snapshot()) and secret not in json.dumps(hub.export_configs())
        assert secret.encode() not in hub.store.path.read_bytes()
        hub.disconnect(server['id'])
        hub.env = {}
        server = hub.reconnect(server['id'])['servers'][0]
        assert server['state'] == 'authentication_required'
    finally:
        hub.close()

def test_http_redirect_is_blocked_before_following_endpoint(manager, http_server, tmp_path):
    server = connect(manager, {**http_server, 'url': http_server['url'].replace('/mcp/', '/redirect')})
    assert server['state'] == 'failed' and server['tools'] == []
    assert ledger(tmp_path) == []

def test_connection_timeout_cleans_up_owned_stdio_server(manager, tmp_path):
    config = stdio_config(tmp_path)
    (tmp_path / 'control.json').write_text(json.dumps({'list_delay': 30}), encoding='utf-8')
    start = time.monotonic()
    server = connect(manager, {**config, 'timeout_seconds': 2})
    assert server['state'] == 'failed' and (not server['tools'])
    assert time.monotonic() - start < 8
    assert not manager.connections and (not manager.pending)
    import psutil
    assert not psutil.pid_exists(int((tmp_path / 'ledger.pid').read_text(encoding='utf-8')))

def test_corrupt_and_future_version_store_remain_preserved(tmp_path):
    import sqlite3
    path = tmp_path / 'mcp' / 'hub.sqlite3'
    path.parent.mkdir()
    path.write_bytes(b'not-a-sqlite-database')
    with pytest.raises(MCPConfigurationError):
        MCPManager(tmp_path)
    assert path.read_bytes() == b'not-a-sqlite-database'
    path.unlink()
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=99')
    original = path.read_bytes()
    with pytest.raises(MCPConfigurationError):
        MCPManager(tmp_path)
    assert path.read_bytes() == original

@pytest.mark.parametrize('reference', ['#/$defs/missing', '#/$defs/cycle'])
def test_dangling_and_recursive_schema_references_are_rejected(reference):
    schema = {'type': 'object', 'properties': {'nested': {'$ref': reference}}, '$defs': {'cycle': {'$ref': '#/$defs/cycle'}}}
    with pytest.raises(MCPConfigurationError):
        validate_schema(schema)

def test_local_schema_definitions_are_preserved():
    schema = {'type': 'object', 'properties': {'nested': {'$ref': '#/$defs/value'}}, '$defs': {'value': {'type': 'integer', 'minimum': 0}}}
    assert validate_schema(schema) == schema

@pytest.mark.parametrize('secret', ['A7x!', 'long-isolated-mcp-authentication-credential'])
def test_credential_reflected_in_definition_is_never_persisted_or_exposed(tmp_path, http_server, secret):
    from tests.fixtures.mcp_hub_mock import TOOLS
    tools = deepcopy(TOOLS)
    tools[1]['description'] = 'Reflected credential: ' + secret
    (tmp_path / 'control.json').write_text(json.dumps({'require_bearer': secret, 'tools': tools}), encoding='utf-8')
    root = tmp_path / 'reflected'
    hub = MCPManager(root, env={'ISOLATED_CREDENTIAL': secret})
    config = {**http_server, 'auth': {'type': 'bearer_env', 'reference': 'ISOLATED_CREDENTIAL'}}
    try:
        server = connect(hub, config)
        assert server['state'] == 'failed' and server['tools'] == []
        assert secret not in json.dumps(hub.snapshot()) and secret not in json.dumps(hub.export_configs())
        path = hub.store.path
    finally:
        hub.close()
    assert secret.encode() not in path.read_bytes()

def test_short_vault_credential_is_loaded_only_after_approval_and_reflection_withheld(tmp_path, http_server):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from tests.fixtures.mcp_hub_mock import TOOLS
    secret = 'zP4!'
    tools = deepcopy(TOOLS)
    tools[0]['_meta'] = {'reflected': secret}
    (tmp_path / 'control.json').write_text(json.dumps({'require_bearer': secret, 'tools': tools}), encoding='utf-8')
    vault = SimpleNamespace(get_password=Mock(return_value=secret))
    hub = MCPManager(tmp_path / 'vault-reflection', env={}, vault=vault)
    config = {**http_server, 'auth': {'type': 'bearer_secret', 'reference': 'isolated-vault-entry'}}
    try:
        server = hub.add(config)
        vault.get_password.assert_not_called()
        server = hub.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])['servers'][0]
        vault.get_password.assert_called_once_with('HANNI.MCP.v1', 'isolated-vault-entry')
        assert server['state'] == 'failed' and server['tools'] == []
        assert secret not in json.dumps(hub.snapshot()) and secret not in json.dumps(hub.export_configs())
        path = hub.store.path
    finally:
        hub.close()
    assert secret.encode() not in path.read_bytes()
