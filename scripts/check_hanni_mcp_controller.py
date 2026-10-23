"""Real configured local model -> original controller -> SDK MCP mock server.

Temporary state and an explicitly approved read-only fixture only. No GUI,
microphone, service credentials or external server is required for this proof.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def call(url, path, *, token=None, body=None, timeout=30):
    headers = {}
    if token:
        headers.update({'X-Hanni-Token': token, 'Origin': url})
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(url + path, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def operation(url, token, name, data):
    return call(url, '/api/mcp', token=token,
                body={'id': str(uuid4()), 'operation': name, 'data': data, 'confirmed': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/hanni-mcp-hub-review/live-controller')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'checks': [],
              'disclosure': 'Actual configured local model and original dashboard launcher/text controller; official SDK stdio fixture; isolated state. No GUI, voice or external services.'}
    controller = None
    url = f'http://127.0.0.1:{free_port()}'
    with tempfile.TemporaryDirectory(prefix='hanni-mcp-controller-') as directory:
        state = Path(directory)
        control, ledger = state / 'fixture.json', state / 'fixture-ledger.jsonl'
        control.write_text('{}', encoding='utf-8')
        env = os.environ.copy()
        env.update(HANNI_DATA_DIR=directory, HANNI_CHAT_HISTORY='session', HANNI_LAYA_SHADOW_ENABLED='0')
        with (args.output / 'controller.log').open('w', encoding='utf-8') as log:
            try:
                controller = subprocess.Popen([sys.executable, '-m', 'hanni.dashboard.launcher',
                    '--no-browser', '--text', '--port', url.rsplit(':', 1)[1], '--data-dir', directory,
                    '--startup-timeout', '180'], cwd=ROOT, env=env, stdin=subprocess.PIPE,
                    stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                deadline = time.monotonic() + 190
                chat = None
                while time.monotonic() < deadline:
                    if controller.poll() is not None:
                        raise RuntimeError('Original controller exited before readiness; see isolated controller.log.')
                    try:
                        chat = call(url, '/api/chat', timeout=3)
                        if chat.get('ready'):
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(.25)
                assert chat and chat['ready'], 'Original controller did not become ready.'
                token = chat['token']
                hub = call(url, '/api/mcp', token=token)
                assert hub['controller_attached'] and hub['model_tools_enabled']
                result['checks'].append('Original controller and configured local model ready; same live registry bound')

                added = operation(url, token, 'add', {'config': {
                    'name': 'Integration fixture', 'transport': 'stdio', 'command': sys.executable,
                    'args': [str(ROOT / 'tests/fixtures/mcp_hub_mock.py'), '--control', str(control),
                             '--ledger', str(ledger)], 'timeout_seconds': 10}})
                server_id = added['id']
                discovered = operation(url, token, 'test_discover', {
                    'server_id': server_id, 'approved': True, 'expected_config_hash': added['config_hash']})
                server = next(row for row in discovered['servers'] if row['id'] == server_id)
                assert server['state'] == 'connected' and len(server['tools']) == 3
                assert all(not tool['enabled'] and not tool['available'] for tool in server['tools'])
                events = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()]
                assert not any(row['event'] == 'call' for row in events)
                result['checks'].append('Private Hub API discovered three disabled real tools with pagination and no calls')

                echo = next(tool for tool in server['tools'] if tool['original_name'] == 'mock.echo')
                operation(url, token, 'approve_tools', {'server_id': server_id, 'tools': [{
                    'original_name': echo['original_name'], 'definition_hash': echo['definition_hash'],
                    'classification': 'read_only'}]})
                contract = call(url, '/api/workspace')
                assert echo['internal_id'] in {tool['name'] for tool in contract['capabilities']}
                result['checks'].append('Approved imported capability hot-added to actual controller contract')

                prompt = 'Use the connected Integration fixture echo tool to echo the message "HANNI MCP verification". Report its returned message.'
                call(url, '/api/chat', token=token, body={'id': str(uuid4()), 'message': prompt})
                deadline, replies = time.monotonic() + 150, []
                while time.monotonic() < deadline:
                    snapshot = call(url, '/api/chat', timeout=4)
                    replies = [message for message in snapshot['messages'] if
                               message['role'] == 'assistant' and message['status'] == 'complete' and message['content']]
                    if replies:
                        break
                    time.sleep(.25)
                assert replies, 'Original controller did not finish the request.'
                events = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()]
                names = [event['name'] for event in events if event['event'] == 'call']
                rows = [json.loads(line) for line in (state / 'logs/tool_audit.jsonl').read_text(encoding='utf-8').splitlines()]
                successful = [row for row in rows if row['tool'] == echo['internal_id'] and row['ok']]
                assert names == ['mock.echo'], f'Expected original external tool invocation; observed {names}'
                assert successful and all(not row['confirmed'] for row in successful)
                assert 'HANNI MCP verification' in replies[-1]['content']
                result['checks'].append('Real local model selected imported tool through original router/session, executed exact external name and returned its evidence')
                result['external_calls'] = names
                result['imported_capability'] = echo['internal_id']
                result['reply'] = replies[-1]['content']

                operation(url, token, 'disable_tools', {'server_id': server_id, 'names': ['mock.echo']})
                assert echo['internal_id'] not in {tool['name'] for tool in call(url, '/api/workspace')['capabilities']}
                operation(url, token, 'remove', {'server_id': server_id})
                assert call(url, '/api/mcp', token=token)['servers'] == []
                result['checks'].append('Live disable/removal withdrew imported capability without controller restart')
                call(url, '/api/shutdown', token=token, body={})
                controller.wait(timeout=45)
                assert controller.returncode == 0
                result['checks'].append('Original shutdown closed MCP connections and controller cleanly')
                result['passed'] = True
            except Exception as error:
                result['error'] = str(error)
            finally:
                if controller is not None and controller.poll() is None:
                    try:
                        if chat and chat.get('token'):
                            call(url, '/api/shutdown', token=chat['token'], body={})
                        controller.wait(timeout=30)
                    except (OSError, subprocess.TimeoutExpired):
                        if os.name == 'nt':
                            subprocess.run(['taskkill', '/PID', str(controller.pid), '/T', '/F'], capture_output=True)
                        else:
                            controller.terminate()
                            controller.wait(timeout=10)
        # Credential-free fixture/controller audit retained for independent proof.
        audit = state / 'logs/tool_audit.jsonl'
        if audit.exists():
            (args.output / 'controller-audit.jsonl').write_bytes(audit.read_bytes())
        if ledger.exists():
            (args.output / 'fixture-ledger.jsonl').write_bytes(ledger.read_bytes())
    (args.output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
