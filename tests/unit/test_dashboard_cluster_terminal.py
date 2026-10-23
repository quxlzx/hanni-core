import base64
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import os
import subprocess
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.dashboard.cluster import ClusterMonitor
from tests.unit.cluster_fixture import NODES
from hanni.dashboard import cluster_terminal as module
from hanni.dashboard.server import DashboardServer
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows terminal launcher')

def which(name):
    return f"C:\\Tools with spaces\\Owner's tools\\{name}"

def script(command):
    return base64.b64decode(command[-1]).decode('utf-16le')

def payload(**changes):
    return {'id': str(uuid4()), 'node': 'hanni', **changes}

@pytest.fixture
def terminal(tmp_path, monkeypatch):
    monkeypatch.setattr(module, '_tailscale_executable', lambda: which('tailscale.exe'))
    monkeypatch.delenv('HANNI_CLUSTER_SSH_IDENTITY', raising=False)
    monitor = ClusterMonitor(nodes=NODES)
    monitor._rows['hanni'].update(checked_at=time.time(), status='offline', connection='tailscale', tailscale_ssh_enabled=True)
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(poll=lambda: None)
    controller = module.ClusterTerminal(monitor, tmp_path, popen=popen, which=which)
    return (controller, calls)

def test_terminal_opens_visible_tailscale_session_as_member_and_deduplicates(terminal):
    controller, calls = terminal
    data = payload()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: controller.execute(data), range(4)))
    assert len(calls) == 1 and all((result == results[0] for result in results))
    command, options = calls[0]
    assert command[:6] == [which('wt.exe'), '-w', 'new', 'new-tab', '--title', 'HANNI SSH']
    assert '-NoExit' in command and options['creationflags'] == subprocess.CREATE_NO_WINDOW
    remote = script(command)
    assert "Owner''s tools" in remote and "'tailscale.exe'" not in remote
    assert "'ssh' 'athena@" + '.'.join(('100', '64', '0', '10')) + "'" in remote and 'root@' not in remote
    assert "'ClearAllForwardings=yes'" in remote and 'BatchMode' not in remote
    assert 'StrictHostKeyChecking=no' not in remote and 'UserKnownHostsFile' not in remote
    assert results[0]['opened'] is True and 'SSH login runs in that window' in results[0]['message']
    with pytest.raises(ValueError, match='another node'):
        controller.execute({**data, 'node': 'haerin'})

@pytest.mark.parametrize('changes', [{'id': 'invalid'}, {'id': []}, {'node': 'yunjin'}, {'node': '' + '.'.join(('10', '42', '0', '30')) + ''}, {'node': 'hanni; reboot'}, {'node': []}, {'command': 'whoami'}, {'username': 'root'}])
def test_terminal_rejects_unknown_nodes_and_browser_commands(terminal, changes):
    controller, calls = terminal
    with pytest.raises(ValueError):
        controller.execute(payload(**changes))
    assert not calls

def test_terminal_uses_interactive_openssh_for_lan_and_literal_identity_path(terminal, monkeypatch):
    controller, calls = terminal
    controller.monitor._rows['hanni']['connection'] = 'lan'
    monkeypatch.setenv('HANNI_CLUSTER_SSH_IDENTITY', "C:\\keys\\Owner's $(whoami); key")
    controller.execute(payload())
    remote = script(calls[0][0])
    assert 'tailscale.exe' not in remote and 'ssh.exe' in remote
    assert "'athena@192.0.2.10'" in remote
    assert "'C:\\keys\\Owner''s $(whoami); key'" in remote
    assert "'IdentitiesOnly=yes'" in remote

def test_terminal_falls_back_to_visible_powershell_when_windows_terminal_fails(terminal):
    controller, calls = terminal

    def popen(command, **options):
        calls.append((command, options))
        if command[0].endswith('wt.exe'):
            raise FileNotFoundError('Unavailable app alias')
        return SimpleNamespace(poll=lambda: None)
    controller._popen = popen
    result = controller.execute(payload())
    assert len(calls) == 2 and calls[1][0][0] == which('powershell.exe')
    assert calls[1][1]['creationflags'] == subprocess.CREATE_NEW_CONSOLE
    assert 'Opened PowerShell' in result['message']

def test_terminal_without_windows_terminal_and_launch_failure(terminal):
    controller, calls = terminal
    controller._which = lambda name: None if name == 'wt.exe' else which(name)
    result = controller.execute(payload())
    assert calls[0][1]['creationflags'] == subprocess.CREATE_NEW_CONSOLE
    assert 'Opened PowerShell' in result['message']

    def fail(*args, **kwargs):
        raise OSError('Not launchable')
    controller._popen = fail
    with pytest.raises(RuntimeError, match='could not be opened'):
        controller.execute(payload())

def test_terminal_blocks_unconfigured_checking_and_safe_mode_sessions(terminal):
    controller, calls = terminal
    state = controller.project(controller.monitor.snapshot())
    assert next((row for row in state['nodes'] if row['id'] == 'yunjin'))['terminal']['enabled'] is False
    assert next((row for row in state['nodes'] if row['id'] == 'hanni'))['terminal']['enabled'] is True
    with pytest.raises(RuntimeError, match='Checking SSH'):
        controller.execute(payload(node='haerin'))
    (controller.data_dir / 'emergency_stop.json').write_text('invalid state')
    with pytest.raises(RuntimeError, match='Safe Mode'):
        controller.execute(payload())
    controller.data_dir = None
    with pytest.raises(RuntimeError, match='unavailable'):
        controller.execute(payload())
    assert not calls

def test_terminal_route_protects_local_launch_with_origin_token_and_shutdown(terminal):
    controller, calls = terminal
    shutdown = threading.Event()
    server = DashboardServer(0, SimpleNamespace(), cluster=controller.monitor, cluster_terminal=controller, shutdown_event=shutdown)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'

    def call(headers, data):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            connection.request('POST', '/api/cluster/terminal', headers=headers, body=json.dumps(data))
            response = connection.getresponse()
            return (response.status, json.loads(response.read()))
        finally:
            connection.close()
    headers = {'Origin': origin, 'X-Hanni-Token': server.chat.token, 'Content-Type': 'application/json'}
    try:
        assert call({**headers, 'Origin': 'https://evil.example'}, payload())[0] == 403
        assert call({**headers, 'X-Hanni-Token': 'wrong'}, payload())[0] == 403
        assert call({**headers, 'Host': 'evil.example'}, payload())[0] == 403
        assert call({**headers, 'Sec-Fetch-Site': 'cross-site'}, payload())[0] == 403
        assert call({**headers, 'Content-Type': 'text/plain'}, payload())[0] == 415
        assert call(headers, payload(command='whoami'))[0] == 400
        assert not calls
        data = payload()
        assert call(headers, data)[0] == 202 and call(headers, data)[0] == 202
        assert len(calls) == 1
        shutdown.set()
        assert call(headers, payload())[0] == 409 and len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        server.chat.close()
        server.chat.db.close()
