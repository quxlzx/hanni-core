from contextlib import nullcontext
import http.client
import json
import subprocess
import sys
import time
import threading
from types import SimpleNamespace
import pytest
from hanni.dashboard import cluster
from hanni.dashboard.server import DashboardServer
from tests.unit.cluster_fixture import NODES

@pytest.fixture(autouse=True)
def configured_roster(monkeypatch):
    monkeypatch.setattr(cluster, 'NODES', NODES)
SAMPLE = {'cpu_percent': 12.5, 'ram_percent': 50, 'ram_used_bytes': 8 * 1024 ** 3, 'ram_total_bytes': 16 * 1024 ** 3}
WORKLOAD = {'uptime_seconds': 90123.5, 'processes': [{'name': 'llama-server', 'cpu_percent': 125.0, 'ram_percent': 30.0}]}

def test_remote_script_stdin_preserves_lf_on_windows():
    result = cluster._run([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'], input='set -eu\nprintf ok\n')
    assert result.returncode == 0 and result.stdout == 'set -eu\nprintf ok\n'

def test_remote_command_timeout_is_bounded_and_closes_owned_process():
    began = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        cluster._run([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=0.1)
    assert time.monotonic() - began < 3

def connected(monkeypatch):
    monkeypatch.setattr(cluster.socket, 'create_connection', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(cluster.shutil, 'which', lambda name: name)

def test_linux_probe_collects_valid_real_fields_without_installing_or_accepting_keys(monkeypatch):
    connected(monkeypatch)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({**SAMPLE, **WORKLOAD}), stderr='')
    monkeypatch.setattr(cluster, '_run', run)
    row = cluster.probe_node(cluster.NODES[0], {'online': True, 'os': 'linux'})
    assert row['metrics'] == SAMPLE
    assert row['status'] == 'online' and row['availability_source'] == 'telemetry'
    assert row['connection'] == 'lan' and row['address'] == '192.0.2.10'
    assert row['sampled_at'] is not None
    assert row['uptime_seconds'] == WORKLOAD['uptime_seconds'] and row['processes'] == WORKLOAD['processes']
    command, kwargs = calls[0]
    assert 'StrictHostKeyChecking=yes' in command and 'BatchMode=yes' in command
    assert command[-2:] == ['athena@192.0.2.10', 'python3 -u - once']
    assert kwargs['input'] == cluster.LINUX_SAMPLE

def test_windows_probe_uses_noninteractive_readonly_system_counters(monkeypatch):
    connected(monkeypatch)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(SAMPLE), stderr='')
    monkeypatch.setattr(cluster, '_run', run)
    assert cluster.probe_node(cluster.NODES[1], {'online': True, 'os': 'windows'})['metrics'] == SAMPLE
    assert commands[0][-1].startswith('powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand ')

def test_tailscale_ssh_uses_existing_tailnet_auth_and_verified_keys(monkeypatch):
    connected(monkeypatch)

    def connect(target, **kwargs):
        if target[0] == NODES[0].lan_ip:
            raise TimeoutError('LAN unavailable')
        return nullcontext()
    monkeypatch.setattr(cluster.socket, 'create_connection', connect)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(SAMPLE), stderr='')
    monkeypatch.setattr(cluster, '_run', run)
    row = cluster.probe_node(cluster.NODES[0], {'online': True, 'os': 'linux', 'ssh_enabled': True})
    assert row['metrics'] == SAMPLE
    assert commands[0][:3] == ['tailscale', 'ssh', 'athena@' + '.'.join(('100', '64', '0', '10')) + '']
    assert 'StrictHostKeyChecking=yes' in commands[0] and 'BatchMode=yes' in commands[0]
    assert commands[0][-1] == 'python3 -u - once'

@pytest.mark.parametrize('error, hint', [('Host key verification failed.', 'host key'), ('Permission denied (publickey).', 'authentication'), ('# Tailscale SSH requires an additional check.\n# To authenticate, visit: https://login.tailscale.com/private-check', 'fresh sign-in')])
def test_online_tailnet_presence_does_not_invent_resource_usage(monkeypatch, error, hint):
    connected(monkeypatch)
    monkeypatch.setattr(cluster, '_run', lambda *args, **kwargs: SimpleNamespace(returncode=255, stdout='', stderr=error))
    row = cluster.probe_node(cluster.NODES[0], {'online': True, 'os': 'linux'})
    assert row['status'] == 'online' and row['availability_source'] == 'tailscale'
    assert hint in row['message']
    assert row['metrics'] is None and row['sampled_at'] is None
    assert 'https://login.tailscale.com/' not in row['message']

def test_repair_node_never_opens_a_connection(monkeypatch):

    def forbidden(*args, **kwargs):
        raise AssertionError('Maintenance node must not be probed')
    monkeypatch.setattr(cluster.socket, 'create_connection', forbidden)
    row = cluster.probe_node(cluster.NODES[-1])
    assert row['status'] == 'repair' and row['metrics'] is None
    assert cluster.NODES[-1].emoji == '🪼'

def test_tailnet_failure_and_offline_are_distinct_and_lan_fallback_is_supported(monkeypatch):
    attempted = []

    def connect(target, **kwargs):
        attempted.append(target[0])
        if target[0].startswith('100.'):
            raise TimeoutError('No tailnet route')
        return nullcontext()
    monkeypatch.setattr(cluster.socket, 'create_connection', connect)
    monkeypatch.setattr(cluster.shutil, 'which', lambda name: name)
    monkeypatch.setattr(cluster, '_run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(SAMPLE), stderr=''))
    row = cluster.probe_node(cluster.NODES[0], {'online': False, 'os': 'linux'})
    assert attempted == ['192.0.2.10']
    assert row['connection'] == 'lan' and row['status'] == 'online'

    def unavailable(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(cluster.socket, 'create_connection', unavailable)
    assert cluster.probe_node(cluster.NODES[0], {'online': False})['status'] == 'offline'
    assert cluster.probe_node(cluster.NODES[0])['status'] == 'unreachable'
    assert cluster.probe_node(cluster.NODES[0], {'online': True})['status'] == 'online'

@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1, 101, True, '42'])
def test_invalid_resource_usage_is_rejected(bad):
    with pytest.raises(ValueError):
        cluster.validate_sample({**SAMPLE, 'cpu_percent': bad})

def test_inconsistent_memory_is_rejected():
    with pytest.raises(ValueError):
        cluster.validate_sample({**SAMPLE, 'ram_percent': 12})
    with pytest.raises(ValueError):
        cluster.validate_sample({**SAMPLE, 'ram_total_bytes': 0})

def test_workload_only_projects_bounded_process_names_and_real_uptime():
    raw = {**WORKLOAD, 'processes': [{'name': 'llama-server\x00', 'cpu_percent': 250.0, 'ram_percent': 30.0, 'arguments': '--secret-token hidden'}, {'name': 'invalid', 'cpu_percent': float('nan'), 'ram_percent': 0}, {'name': 'worker', 'cpu_percent': 1.0, 'ram_percent': 2.0}, {'name': 'not-returned', 'cpu_percent': 1.0, 'ram_percent': 1.0}]}
    row = cluster.workload_sample(raw)
    assert row['uptime_seconds'] == 90123.5
    assert row['processes'] == [{'name': 'llama-server', 'cpu_percent': 250.0, 'ram_percent': 30.0}, {'name': 'worker', 'cpu_percent': 1.0, 'ram_percent': 2.0}]
    assert cluster.workload_sample({'uptime_seconds': -1, 'processes': None}) == {'uptime_seconds': None, 'processes': None}

def test_persistent_stream_delivers_multiple_frames_and_closes_on_shutdown(monkeypatch):
    frame = json.dumps({**SAMPLE, **WORKLOAD})
    program = f'import time; print({frame!r},flush=True); print({frame!r},flush=True); time.sleep(20)'
    monkeypatch.setattr(cluster, '_ssh_prefix', lambda *args, **kwargs: [sys.executable, '-u', '-c', program])
    monitor = cluster.ClusterMonitor()
    node = cluster.NODES[0]
    initial = {'connection': 'lan', 'address': node.lan_ip, 'os': 'linux', 'status': 'online', 'message': None}
    frames = monitor._stream_node(node, initial, {})
    try:
        first, second = (next(frames), next(frames))
        assert first['metrics'] == second['metrics'] == SAMPLE
        assert first['processes'] == second['processes'] == WORKLOAD['processes']
        assert len(monitor._processes) == 1
        process = monitor._processes[node.id]
        monitor.close()
        assert process.poll() is not None
    finally:
        frames.close()
        monitor.close()
    assert not monitor._processes

def test_monitor_retains_bounded_history_with_gaps_and_never_probes_yunjin():
    failed = [False]
    probed = []

    def probe(node, peer):
        probed.append(node.id)
        return {'status': 'offline' if failed[0] else 'online', 'checked_at': 10.0, 'sampled_at': None if failed[0] else 10.0, 'metrics': None if failed[0] else SAMPLE, 'message': 'Offline' if failed[0] else None}
    monitor = cluster.ClusterMonitor(probe=probe, tailnet=lambda: {'state': 'connected', 'peers': {}})
    assert monitor._worker is None
    for _ in range(cluster.HISTORY_LENGTH + 1):
        monitor.sample_once()
    failed[0] = True
    monitor.sample_once()
    snapshot = monitor.snapshot()
    assert len(snapshot['nodes']) == 9 and snapshot['refresh_seconds'] == 1 and (snapshot['history_seconds'] == 60)
    assert 'yunjin' not in probed
    node = snapshot['nodes'][0]
    assert len(node['history']) == cluster.HISTORY_LENGTH
    assert node['history'][-1] == {'at': 10.0, 'cpu': None, 'ram': None}
    assert node['metrics'] is None and node['last_online_at'] == 10.0
    node['history'].clear()
    assert monitor.snapshot()['nodes'][0]['history']
    assert snapshot['nodes'][-1]['status'] == 'repair'

def test_tailscale_projection_excludes_other_devices_and_user_information(monkeypatch):
    monkeypatch.setattr(cluster.shutil, 'which', lambda name: name)
    raw = {'BackendState': 'Running', 'User': {'1': {'LoginName': 'private@example.test'}}, 'Peer': {'1': {'Online': True, 'OS': 'linux', 'TailscaleIPs': ['' + '.'.join(('100', '64', '0', '10')) + ''], 'sshHostKeys': ['ssh-ed25519 public-key']}, '2': {'Online': True, 'TailscaleIPs': ['' + '.'.join(('11', '42', '0', '13')) + '']}}}
    monkeypatch.setattr(cluster, '_run', lambda *args: SimpleNamespace(returncode=0, stdout=json.dumps(raw)))
    assert cluster.tailscale_snapshot() == {'state': 'connected', 'peers': {'' + '.'.join(('100', '64', '0', '10')) + '': {'online': True, 'os': 'linux', 'ssh_enabled': True}}}
    raw['BackendState'] = 'Stopped'
    assert cluster.tailscale_snapshot()['peers']['' + '.'.join(('100', '64', '0', '10')) + '']['online'] is None

def test_timeout_never_changes_online_presence_to_fake_zero_usage(monkeypatch):
    connected(monkeypatch)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('ssh', 2.5)
    monkeypatch.setattr(cluster, '_run', timeout)
    row = cluster.probe_node(cluster.NODES[0], {'online': True, 'os': 'linux'})
    assert row['status'] == 'online' and row['metrics'] is None and ('timed out' in row['message'])

def test_cluster_endpoint_is_readonly_same_origin_and_closes_monitor():
    started, closed = ([], [])
    monitor = SimpleNamespace(start=lambda: started.append(True), close=lambda: closed.append(True), snapshot=lambda: {'nodes': []})
    server = DashboardServer(0, SimpleNamespace(), cluster=monitor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = f'127.0.0.1:{server.server_port}'

    def call(method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            conn.request(method, '/api/cluster', headers=headers or {}, body=body)
            res = conn.getresponse()
            return (res.status, json.loads(res.read()))
        finally:
            conn.close()
    try:
        for headers in [{'Origin': 'https://evil.example'}, {'Host': 'evil.example'}, {'Sec-Fetch-Site': 'cross-site'}]:
            assert call(headers=headers)[0] == 403
        assert started == []
        assert call() == (200, {'nodes': []})
        assert len(started) == 1
        assert call('POST', {'Origin': f'http://{host}', 'X-Hanni-Token': server.chat.token, 'Content-Type': 'application/json'}, '{}')[0] == 404
        assert len(started) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        server.chat.close()
        server.chat.db.close()
    assert closed == [True]
