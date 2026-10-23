from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import http.client
import json
import subprocess
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.dashboard.cluster import ClusterMonitor
from tests.unit.cluster_fixture import NODES
from hanni.dashboard.cluster_power import ClusterPower, ACTIONS, check_power
from hanni.dashboard.server import DashboardServer
from hanni.config.secrets import Secret

@pytest.fixture
def power(tmp_path):
    monitor = ClusterMonitor(nodes=NODES)
    row = monitor._rows['hanni']
    row.update(os='linux', status='online', sampled_at=time.time(), address=NODES[0].tailscale_ip, connection='tailscale', metrics={'cpu_percent': 0, 'ram_percent': 0})
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)
    controller = ClusterPower(monitor, tmp_path, run=run)
    controller._capabilities['hanni'] = {'actions': {action: {'enabled': True, 'reason': None} for action in ACTIONS}, 'methods': {}, 'root': True, 'native': True, 'address': NODES[0].tailscale_ip, 'checked_at': time.time()}
    return (controller, calls)

def payload(**changes):
    return {'id': str(uuid4()), 'node': 'hanni', 'action': 'reboot', 'confirmed': True, **changes}

@pytest.mark.parametrize('changes', [{'confirmed': False}, {'confirmed': 'yes'}, {'node': 'yunjin'}, {'node': 'arbitrary-host'}, {'action': 'reboot; rm -rf /'}, {'action': ['reboot']}, {'id': 'bad'}, {'command': 'something'}])
def test_power_rejects_unconfirmed_unknown_or_injected_requests(power, changes):
    controller, calls = power
    with pytest.raises(ValueError):
        controller.execute(payload(**changes))
    assert not calls

def test_power_uses_roster_root_authorization_and_deduplicates_requests(power):
    controller, calls = power
    data = payload()
    first = controller.execute(data)
    assert first['status'] == 'accepted' and controller.execute(data) == first
    assert len(calls) == 1 and 'root@' + '.'.join(('100', '64', '0', '10')) + '' in calls[0]
    assert calls[0][-1] == ACTIONS['reboot'] and '--force' not in calls[0][-1]
    with pytest.raises(ValueError):
        controller.execute({**data, 'action': 'sleep'})
    with pytest.raises(RuntimeError, match='pending'):
        controller.execute(payload(action='sleep'))
    assert len(calls) == 1

def test_concurrent_confirmation_only_dispatches_once(power):
    controller, calls = power
    data = payload()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: controller.execute(data), range(4)))
    assert len(calls) == 1
    assert all((row['id'] == data['id'] for row in results))

def test_power_blocks_stale_unsupported_and_safe_mode(power):
    controller, calls = power
    controller.monitor._rows['hanni']['sampled_at'] = time.time() - 20
    with pytest.raises(RuntimeError, match='fresh SSH'):
        controller.execute(payload())
    controller.monitor._rows['hanni']['sampled_at'] = time.time()
    controller._capabilities['hanni']['actions']['sleep'] = {'enabled': False, 'reason': 'Sleep is unavailable.'}
    with pytest.raises(RuntimeError, match='Sleep is unavailable'):
        controller.execute(payload(action='sleep'))
    (controller.data_dir / 'emergency_stop.json').write_text('invalid state')
    with pytest.raises(RuntimeError, match='Safe Mode'):
        controller.execute(payload())
    assert not calls

@pytest.mark.parametrize('code, status', [(0, 'accepted'), (1, 'failed'), (255, 'unknown')])
def test_power_reports_remote_acknowledgment_not_guessed_completion(power, code, status):
    controller, calls = power
    controller._execute = lambda *args, **kwargs: SimpleNamespace(returncode=code)
    data = payload(action='sleep')
    assert controller.execute(data)['status'] == status
    assert controller.execute(data)['status'] == status

def test_timeout_is_not_automatically_retried(power):
    controller, calls = power

    def timeout(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired('ssh', 8)
    controller._execute = timeout
    data = payload()
    assert controller.execute(data)['status'] == 'unknown'
    assert controller.execute(data)['status'] == 'unknown'
    assert len(calls) == 1

def test_capability_checks_are_readonly_and_project_disabled_sleep(monkeypatch):
    from hanni.dashboard import cluster_power as module
    commands = []

    def run(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({'actions': {'reboot': {'enabled': True, 'reason': None}, 'sleep': {'enabled': False, 'reason': 'Unavailable in this node’s power configuration.'}}, 'methods': {}}))
    monkeypatch.setattr(module, '_run', run)
    monkeypatch.setattr(module, '_tailscale_executable', lambda: 'tailscale')
    cap = check_power(NODES[0], {'os': 'linux', 'address': NODES[0].tailscale_ip, 'connection': 'tailscale'}, {'ssh_enabled': True})
    assert cap['root'] and cap['actions']['reboot']['enabled'] and (not cap['actions']['sleep']['enabled'])
    assert commands[0][0][-1] == 'python3 -u -'
    assert 'CanReboot' in commands[0][1]['input'] and 'CanSuspend' in commands[0][1]['input']

@pytest.mark.parametrize('code, enabled', [(0, True), (1, False), (255, False)])
@pytest.mark.parametrize('listed_without_password', [False, True])
def test_password_authorization_checks_exact_reboot_policy_without_execution(monkeypatch, code, enabled, listed_without_password):
    from hanni.dashboard import cluster_power as module
    credential = Secret('unit-only-sudo-credential')
    calls = []
    raw = {'actions': {action: {'enabled': False, 'reason': 'Needs authorization.'} for action in ACTIONS}, 'methods': {'reboot': 'sudo', 'sleep': 'direct'}}
    raw['actions']['reboot']['enabled'] = listed_without_password

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(raw)) if len(calls) == 1 else SimpleNamespace(returncode=code)
    monkeypatch.setattr(module, '_run', run)
    cap = check_power(NODES[0], {'os': 'linux', 'address': NODES[0].tailscale_ip, 'connection': 'ssh'}, {}, password=credential)
    assert cap['actions']['reboot']['enabled'] is enabled
    assert not cap['actions']['sleep']['enabled']
    assert calls[1][0][-1] == "sudo -S -p '' -l -- /usr/bin/systemctl -i reboot"
    assert calls[1][1]['input'] == credential.reveal() + '\n'
    assert credential.reveal() not in repr([call[0] for call in calls])
    assert credential.reveal() not in json.dumps(cap)
    if enabled:
        assert cap['methods']['reboot'] == 'sudo_password'

def test_password_reboot_uses_private_stdin_and_preserves_exactly_once(power):
    controller, _ = power
    credential = Secret('unit-only-reboot-password')
    controller._password = lambda node, data_dir: credential
    controller._capabilities['hanni'].update(root=False, methods={'reboot': 'sudo_password'})
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)
    controller._execute = run
    data = payload()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: controller.execute(data), range(4)))
    assert len(calls) == 1
    assert 'athena@' + '.'.join(('100', '64', '0', '10')) + '' in calls[0][0]
    assert calls[0][0][-1] == "sudo -S -p '' -- /usr/bin/systemctl -i reboot"
    assert calls[0][1]['input'] == credential.reveal() + '\n'
    assert credential.reveal() not in repr(calls[0][0])
    assert credential.reveal() not in json.dumps(results)
    assert all((result['id'] == data['id'] and result['status'] in {'sending', 'accepted'} for result in results))
    assert controller.execute(data)['status'] == 'accepted'

def test_missing_saved_password_blocks_before_reserving_or_dispatching(power):
    controller, calls = power
    controller._password = lambda node, data_dir: None
    controller._capabilities['hanni'].update(root=False, methods={'reboot': 'sudo_password'})
    with pytest.raises(RuntimeError, match='credential is unavailable'):
        controller.execute(payload())
    assert not calls and (not controller._operations)

def test_passwordless_sudo_reboot_uses_inhibitor_override_without_password(power):
    controller, _ = power
    controller._capabilities['hanni'].update(root=False, methods={'reboot': 'sudo'})
    controller._password = lambda *args: pytest.fail('Passwordless execution must not read a credential.')
    calls = []
    controller._execute = lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0)
    controller.execute(payload())
    assert calls[0][0][-1] == 'sudo -n -- /usr/bin/systemctl -i reboot'
    assert 'input' not in calls[0][1]

def test_remote_policy_probe_checks_new_reboot_command_without_power_execution(monkeypatch, capsys):
    import os
    from hanni.dashboard.cluster_power import CAPABILITY_SCRIPT
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == '/usr/bin/busctl':
            return SimpleNamespace(returncode=0, stdout='s "challenge"' if command[-1] == 'CanReboot' else 's "na"')
        assert command[:5] == ['sudo', '-n', '-l', '--', '/usr/bin/systemctl']
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(os, 'geteuid', lambda: 1000, raising=False)
    monkeypatch.setattr(subprocess, 'run', run)
    exec(CAPABILITY_SCRIPT, {})
    result = json.loads(capsys.readouterr().out)
    assert ['sudo', '-n', '-l', '--', '/usr/bin/systemctl', '-i', 'reboot'] in calls
    assert not result['actions']['reboot']['enabled']
    assert not result['actions']['sleep']['enabled']

def test_power_capability_explains_tailscale_sign_in_without_exposing_login_link(monkeypatch):
    from hanni.dashboard import cluster_power as module
    monkeypatch.setattr(module, '_run', lambda *args, **kwargs: SimpleNamespace(returncode=255, stderr='# Tailscale SSH requires an additional check.\nhttps://login.tailscale.com/private-check'))
    cap = check_power(NODES[0], {'os': 'linux', 'address': NODES[0].tailscale_ip, 'connection': 'ssh'}, {})
    assert not cap['actions']['reboot']['enabled']
    assert 'fresh sign-in' in cap['actions']['reboot']['reason']
    assert 'https://login.tailscale.com/' not in json.dumps(cap)

def test_expired_tailscale_check_is_failed_before_remote_execution_not_unknown(power):
    controller, _ = power
    controller._execute = lambda *args, **kwargs: SimpleNamespace(returncode=255, stderr='# Tailscale SSH requires an additional check.\nhttps://login.tailscale.com/private-check')
    result = controller.execute(payload())
    assert result['status'] == 'failed' and 'fresh sign-in' in result['message']
    assert 'https://login.tailscale.com/' not in json.dumps(result)

def test_authorized_root_reboot_does_not_depend_on_inhibitor_policy(monkeypatch, capsys):
    import os
    from hanni.dashboard.cluster_power import CAPABILITY_SCRIPT
    monkeypatch.setattr(os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(os.path, 'isfile', lambda name: name == '/usr/bin/systemctl')
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert command[-1] == 'CanSuspend'
        return SimpleNamespace(returncode=0, stdout='s "na"')
    monkeypatch.setattr(subprocess, 'run', run)
    exec(CAPABILITY_SCRIPT, {})
    result = json.loads(capsys.readouterr().out)
    assert result['actions']['reboot']['enabled'] and result['methods']['reboot'] == 'direct'
    assert not result['actions']['sleep']['enabled'] and len(calls) == 1

def test_power_route_requires_matching_origin_token_and_json(power):
    controller, calls = power
    server = DashboardServer(0, SimpleNamespace(), cluster=controller.monitor, cluster_power=controller)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'

    def call(headers, data):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            connection.request('POST', '/api/cluster/power', headers=headers, body=json.dumps(data))
            response = connection.getresponse()
            return (response.status, json.loads(response.read()))
        finally:
            connection.close()
    headers = {'Origin': origin, 'X-Hanni-Token': server.chat.token, 'Content-Type': 'application/json'}
    try:
        assert call({**headers, 'Origin': 'https://evil.example'}, payload())[0] == 403
        assert call({**headers, 'X-Hanni-Token': 'wrong'}, payload())[0] == 403
        assert call({**headers, 'Content-Type': 'text/plain'}, payload())[0] == 415
        assert call(headers, payload(confirmed=False))[0] == 400
        assert not calls
        assert call(headers, payload())[0] == 202 and len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        server.chat.close()
        server.chat.db.close()
