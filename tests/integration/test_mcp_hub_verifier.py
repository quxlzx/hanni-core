"""Independent adversarial tests using actual SDK transports and isolated stores.

These tests belong to verification, not application implementation. No private
CRUD or protocol result is mocked. DNS resolver injection is disclosed per test.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import pytest
from hanni.mcp.manager import MCPManager
from hanni.mcp.security import MCPConfigurationError, endpoint, validate_schema
ROOT = Path(__file__).resolve().parents[2]
SDK_MOCK = ROOT / 'tests/fixtures/mcp_hub_mock.py'
ENV_MOCK = ROOT / 'scripts/mcp_hub_review/adversarial_server.py'

def entries(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

def local_config(root, *, wrapper=False):
    root.mkdir(parents=True, exist_ok=True)
    control, ledger = (root / 'control.json', root / 'ledger.jsonl')
    control.write_text('{}', encoding='utf-8')
    return ({'name': 'Independent fixture', 'transport': 'stdio', 'command': sys.executable, 'args': [str(ENV_MOCK if wrapper else SDK_MOCK), '--control', str(control), '--ledger', str(ledger)], 'timeout_seconds': 3}, control, ledger)

def connected(manager, config):
    server = manager.add(config)
    snapshot = manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
    item = next((row for row in snapshot['servers'] if row['id'] == server['id']))
    return item

@contextmanager
def actual_http_fixture(root):
    config, control, ledger = local_config(root)
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        port = connection.getsockname()[1]
    process = subprocess.Popen([sys.executable, *config['args'], '--transport', 'http', '--port', str(port)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        until = time.monotonic() + 10
        while time.monotonic() < until:
            try:
                with urlopen(origin + '/health', timeout=0.3):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError('Actual SDK HTTP mock did not become ready')
        yield ({'name': 'Independent HTTP fixture', 'transport': 'streamable_http', 'url': origin + '/mcp/', 'allow_local_http': True, 'timeout_seconds': 3}, control, ledger)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=8)

def test_actual_stdio_restricts_inheritance_but_preserves_explicit_reference(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_MCP_UNRELATED_TEST_SECRET', 'independent-unrelated-synthetic')
    config, _, ledger = local_config(tmp_path / 'server', wrapper=True)
    config['env_refs'] = {'HANNI_MCP_EXPLICIT_CHILD': 'INDEPENDENT_SOURCE_REFERENCE'}
    manager = MCPManager(tmp_path / 'data', env={'INDEPENDENT_SOURCE_REFERENCE': 'independent-explicit-synthetic'})
    try:
        saved = manager.add(config)
        assert entries(ledger) == [] and manager.runtime is None
        with pytest.raises(MCPConfigurationError):
            manager.connect(saved['id'])
        assert entries(ledger) == []
        result = manager.connect(saved['id'], approved=True, expected_config_hash=saved['config_hash'])
        server = result['servers'][0]
        assert server['state'] == 'connected', server['error']
        start = next((row for row in entries(ledger) if row['event'] == 'process-start'))
        assert start == {'event': 'process-start', 'unrelated_present': False, 'explicit_present': True}
        assert not [row for row in entries(ledger) if row['event'] == 'call']
        serialized = json.dumps(manager.snapshot()) + json.dumps(manager.export_configs())
        assert 'independent-explicit-synthetic' not in serialized
        assert 'independent-unrelated-synthetic' not in serialized
    finally:
        manager.close()

def test_actual_http_auth_failure_and_recovery_never_persist_or_export_token(tmp_path):
    secret = 'independent-bearer-synthetic-unique'
    with actual_http_fixture(tmp_path / 'server') as (config, control, ledger):
        control.write_text(json.dumps({'require_bearer': secret}), encoding='utf-8')
        config['auth'] = {'type': 'bearer_env', 'reference': 'INDEPENDENT_AUTH_REF'}
        manager = MCPManager(tmp_path / 'data', env={'INDEPENDENT_AUTH_REF': 'incorrect-synthetic'})
        try:
            server = connected(manager, config)
            assert server['state'] == 'authentication_required', server
            assert not entries(ledger)
            manager.env['INDEPENDENT_AUTH_REF'] = secret
            snapshot = manager.reconnect(server['id'])
            server = snapshot['servers'][0]
            assert server['state'] == 'connected', server['error']
            assert len(server['tools']) == 3
            assert all((row['event'] == 'list' for row in entries(ledger)))
            assert secret not in json.dumps(snapshot) + json.dumps(manager.export_configs())
        finally:
            manager.close()
        assert secret.encode() not in (tmp_path / 'data/mcp/hub.sqlite3').read_bytes()

def test_actual_http_redirect_never_contacts_target_or_forwards_authorization(tmp_path):
    hits = []

    class Target(BaseHTTPRequestHandler):

        def do_GET(self):
            hits.append({'method': self.command, 'has_auth': bool(self.headers.get('Authorization'))})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{}')
        do_POST = do_GET

        def log_message(self, *args):
            pass
    target = ThreadingHTTPServer(('127.0.0.1', 0), Target)
    thread = threading.Thread(target=target.serve_forever, daemon=True)
    thread.start()
    try:
        with actual_http_fixture(tmp_path / 'server') as (config, control, ledger):
            control.write_text(json.dumps({'redirect': f'http://127.0.0.1:{target.server_port}/sensitive'}), encoding='utf-8')
            config['url'] = config['url'].replace('/mcp/', '/redirect')
            config['auth'] = {'type': 'bearer_env', 'reference': 'INDEPENDENT_AUTH_REF'}
            manager = MCPManager(tmp_path / 'data', env={'INDEPENDENT_AUTH_REF': 'redirect-synthetic-secret'})
            try:
                server = connected(manager, config)
                assert server['state'] == 'failed', server
                assert hits == [] and entries(ledger) == []
                assert 'redirect-synthetic-secret' not in json.dumps(manager.snapshot())
            finally:
                manager.close()
    finally:
        target.shutdown()
        target.server_close()
        thread.join(timeout=3)

@pytest.mark.parametrize('address', ['127.0.0.1', '::1', '' + '.'.join(('10', '42', '0', '29')) + '', '' + '.'.join(('10', '42', '0', '3')) + '', '2001:db8::ffff'])
def test_endpoint_rejects_public_hostname_resolving_to_sensitive_address(address):
    resolver = lambda *args, **kwargs: [(socket.AF_INET6 if ':' in address else socket.AF_INET, 0, 0, '', (address, 443))]
    with pytest.raises(MCPConfigurationError):
        endpoint('https://public-verification.invalid/mcp', resolve=True, resolver=resolver)

def test_future_store_version_rejection_preserves_original_database(tmp_path):
    database = tmp_path / 'mcp/hub.sqlite3'
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE future_user_data(value TEXT)')
        connection.execute("INSERT INTO future_user_data VALUES('keep-independent-fixture')")
        connection.execute('PRAGMA user_version=999')
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    with pytest.raises(MCPConfigurationError):
        MCPManager(tmp_path)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    with sqlite3.connect(database) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 999
        assert connection.execute('SELECT value FROM future_user_data').fetchone()[0] == 'keep-independent-fixture'

@pytest.mark.parametrize('reference', ['#/$defs/missing', '#/properties/value'])
def test_dangling_or_nonprogressing_local_schema_reference_is_rejected(reference):
    schema = {'type': 'object', 'properties': {'value': {'$ref': reference}}, '$defs': {}}
    with pytest.raises(MCPConfigurationError):
        validate_schema(schema)
