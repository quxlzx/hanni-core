"""Real official SDK/auth/redirect boundary on one exact owned loopback child.

Provider data is synthetic; this is protocol execution, never third-party access.
The registered HANNI handler and manager are not replaced.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from unittest.mock import patch
from scripts.campaign9_tools.harness import fixture_config, EmptyVault

def run(out):
    from hanni.tools.registry import build_default_registry
    from hanni.tools.google_access import GoogleAccess
    from hanni.tools.base import ToolRequest
    from hanni.mcp.manager import MCPManager
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    spec = {'cases': ['missing_auth', 'wrong_auth', 'valid_auth_echo', 'redirect_refused'], 'scope': 'One owned loopback official SDK endpoint; synthetic bearer, no external connections.'}
    (out / 'PROSPECTIVE.json').write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='hanni-c9-sdk-') as temporary:
        root = Path(temporary)
        config = fixture_config(root)
        original_google = GoogleAccess.__init__

        def google_init(instance, vault=None, transport=None, timezone_name=None):
            original_google(instance, vault=EmptyVault(), transport=transport, timezone_name=timezone_name)
        with patch.object(GoogleAccess, '__init__', google_init):
            registry = build_default_registry(config)
        registry.context.reliability = None
        control = root / 'control.json'
        ledger = root / 'ledger.jsonl'
        bearer = 'C9_ONLY_LOOPBACK_SYNTHETIC_BEARER'
        control.write_text(json.dumps({'require_bearer': bearer}), encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/mcp_hub_mock.py'
        command = [sys.executable, str(fixture), '--transport', 'http', '--port', str(port), '--control', str(control), '--ledger', str(ledger)]
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner = {'pid': process.pid, 'command_sha256': hashlib.sha256('\x00'.join(command).encode()).hexdigest()}
        rows = []
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=0.3):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise RuntimeError('Owned SDK fixture did not become ready.')
            for label, value in [('missing_auth', None), ('wrong_auth', 'C9_ONLY_WRONG_SYNTHETIC'), ('valid_auth_echo', bearer), ('redirect_refused', bearer)]:
                manager = MCPManager(root / label, registry, env={} if value is None else {'C9_AUTH': value}, vault=EmptyVault())
                try:
                    server = manager.add({'name': 'Synthetic loopback ' + label, 'transport': 'streamable_http', 'url': f'http://127.0.0.1:{port}/' + ('redirect' if label == 'redirect_refused' else 'mcp/'), 'allow_local_http': True, 'timeout_seconds': 2, 'auth': {'type': 'none'} if value is None else {'type': 'bearer_env', 'reference': 'C9_AUTH'}})
                    connected = manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])['servers'][0]
                    row = {'case': label, 'state': connected['state'], 'error': connected.get('error'), 'tool_calls': 0}
                    if label == 'valid_auth_echo' and connected['state'] == 'connected':
                        tool = next((t for t in connected['tools'] if t['original_name'] == 'mock.echo'))
                        manager.approve_tools(server['id'], [{'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': 'read_only'}])
                        result = registry.execute(ToolRequest(tool['internal_id'], {'message': 'Original SDK controlled echo'}))
                        row.update(ok=result.ok, echo_match=result.data['structured_content'] == {'message': 'Original SDK controlled echo'}, tool_calls=1)
                    row['passed'] = row.get('ok') is True and row.get('echo_match') is True if label == 'valid_auth_echo' else connected['state'] != 'connected' and (not connected['tools'])
                    rows.append(row)
                finally:
                    manager.close()
        finally:
            process.terminate()
            process.wait(timeout=5)
        receipt = {'source_fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'owned_child': owner, 'child_exit': process.returncode, 'closed': process.poll() is not None, 'results': rows, 'provider_ledger': [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else [], 'passed': sum((r['passed'] for r in rows)), 'cases': len(rows), 'evidence_class': 'ORIGINAL_SDK_LOOPBACK_SYNTHETIC_PROVIDER'}
        (out / 'RESULTS.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
        return receipt
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = run(a.out)
    print(json.dumps({key: result[key] for key in ['cases', 'passed', 'closed', 'child_exit']}))
