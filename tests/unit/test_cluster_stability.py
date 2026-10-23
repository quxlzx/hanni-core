"""Fresh evidence, independent heartbeats and controlled disconnections."""
import json
import sys
import threading
import time
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from hanni.compute import ComputeError, ComputeRegistry, ComputeScheduler
from hanni.compute.transport import InferenceTransport
from hanni.dashboard import cluster
from tests.unit.cluster_fixture import NODES
SAMPLE = {'cpu_percent': 12.5, 'ram_percent': 50.0, 'ram_used_bytes': 1024.0, 'ram_total_bytes': 2048.0}

def record(at, *, status='online', metrics=True):
    return {'status': status, 'checked_at': at, 'sampled_at': at if metrics else None, 'metrics': dict(SAMPLE) if metrics else None, 'message': None, 'availability_source': 'telemetry' if metrics else 'network-probe'}

def test_delayed_ssh_readings_do_not_override_fresh_tailnet_presence(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cluster.time, 'time', lambda: now[0])
    node = NODES[0]
    monitor = cluster.ClusterMonitor(nodes=[node])
    monitor._record(node, record(100))
    monitor._peers = {node.tailscale_ip: {'online': True}}
    monitor._tailnet_checked_at = 100
    now[0] = 107
    row = monitor.snapshot()['nodes'][0]
    assert row['status'] == 'online' and row['availability_source'] == 'tailscale'
    assert row['telemetry_stale'] and row['metrics'] is None
    assert row['uptime_seconds'] is None and row['processes'] is None
    assert row['availability_checked_at'] == 100 and row['availability_stale_seconds'] == 25
    now[0] = 126
    row = monitor.snapshot()['nodes'][0]
    assert row['status'] == 'checking' and row['tailscale_online'] is None
    assert row['metrics'] is None
    monitor._peers = {node.tailscale_ip: {'online': False}}
    monitor._tailnet_checked_at = 126
    monitor._record(node, record(126))
    assert monitor.snapshot()['nodes'][0]['availability_source'] == 'telemetry'
    assert monitor.snapshot()['nodes'][0]['status'] == 'online'

def test_one_failed_node_probe_is_rechecked_and_repeated_failure_is_reported(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cluster.time, 'time', lambda: now[0])
    node = NODES[0]
    monitor = cluster.ClusterMonitor(nodes=[node])
    monitor._record(node, record(100))
    now[0] = 101
    monitor._record(node, record(101, status='offline', metrics=False))
    assert monitor.snapshot()['nodes'][0]['status'] == 'checking'
    assert monitor.snapshot()['nodes'][0]['metrics'] is None
    now[0] = 104
    monitor._record(node, record(104, status='offline', metrics=False))
    assert monitor.snapshot()['nodes'][0]['status'] == 'offline'
    now[0] = 105
    monitor._record(node, record(105))
    assert monitor.snapshot()['nodes'][0]['status'] == 'online'

def test_stream_startup_uses_own_clock_instead_of_previous_probe_age(monkeypatch):
    node = NODES[0]
    program = f'import time; time.sleep(1.3); print({json.dumps(SAMPLE)!r},flush=True); time.sleep(20)'
    monkeypatch.setattr(cluster, '_ssh_prefix', lambda *args, **kwargs: [sys.executable, '-u', '-c', program])
    initial = {**record(time.time() - 30), 'connection': 'lan', 'address': node.lan_ip, 'os': 'linux'}
    monitor = cluster.ClusterMonitor(nodes=[node], probe=lambda *args: dict(initial), tailnet=lambda: {'state': 'connected', 'peers': {}})
    monitor.start()
    try:
        end = time.monotonic() + 4
        while monitor.snapshot()['nodes'][0]['metrics'] is None and time.monotonic() < end:
            time.sleep(0.02)
        row = monitor.snapshot()['nodes'][0]
        assert row['metrics'] == SAMPLE and row['status'] == 'online'
        assert monitor._processes[node.id].poll() is None
    finally:
        monitor.close()

def make_registry(tmp_path):
    root = tmp_path / 'compute'
    root.mkdir()
    workers = [{'worker_id': key, 'node_id': 'local', 'local_url': f'http://127.0.0.1:{44000 + i}', 'model_id': key + '-model', 'enabled': True, 'capabilities': ['analysis'], 'allowed_categories': ['synthetic'], 'concurrency': 1, 'context_configured': 8192} for i, key in enumerate(('slow', 'fast'))]
    (root / 'deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [], 'workers': workers, 'policy': {}}), encoding='utf8')
    return ComputeRegistry(tmp_path)

def test_slow_worker_never_blocks_other_health_checks_and_refresh(tmp_path):
    registry = make_registry(tmp_path)
    entered, release = (threading.Event(), threading.Event())
    counts = {'slow': 0, 'fast': 0}

    def health(worker):
        key = worker['worker_id']
        counts[key] += 1
        if key == 'slow':
            entered.set()
            assert release.wait(5)
        return {'status': 'healthy', 'model_id': worker['model_id'], 'last_heartbeat': registry.clock()}
    transport = SimpleNamespace(health=health, resources=lambda _: {}, close=lambda: release.set())
    scheduler = ComputeScheduler(registry, transport=transport)
    scheduler.start_monitor()
    try:
        assert entered.wait(2)
        end = time.monotonic() + 1
        while registry.snapshot()['workers'][1]['status'] != 'healthy' and time.monotonic() < end:
            time.sleep(0.01)
        assert registry.snapshot()['workers'][1]['status'] == 'healthy'
        scheduler.request_refresh()
        end = time.monotonic() + 1
        while counts['fast'] < 2 and time.monotonic() < end:
            time.sleep(0.01)
        assert counts['fast'] >= 2 and (not release.is_set())
    finally:
        scheduler.close()
    assert not any((worker.is_alive() for worker in scheduler.health_workers.values()))

def test_unhealthy_worker_cannot_be_scheduled_despite_recent_good_heartbeat(tmp_path):
    registry = make_registry(tmp_path)
    scheduler = ComputeScheduler(registry, transport=SimpleNamespace(close=lambda: None))
    try:
        at = registry.clock()
        registry.observe('fast', status='healthy', model_id='fast-model', last_heartbeat=at)
        registry.observe('fast', status='unhealthy', model_id=None, last_heartbeat=at + 1)
        row = registry.snapshot()['workers'][1]
        registry.observe('fast', status='unhealthy', last_heartbeat=at)
        row = registry.snapshot()['workers'][1]
        assert row['status'] == 'unhealthy' and row['last_healthy_at'] == at
        assert row['consecutive_health_failures'] == 2
        assert scheduler._choices({'synthetic'}, 128) == []
    finally:
        scheduler.close()

def test_late_health_result_cannot_restore_disabled_worker(tmp_path):
    registry = make_registry(tmp_path)

    def health(worker):
        registry.configure_worker(worker['worker_id'], enabled=False)
        return {'status': 'healthy', 'model_id': worker['model_id'], 'last_heartbeat': registry.clock()}
    scheduler = ComputeScheduler(registry, transport=SimpleNamespace(health=health, close=lambda: None))
    try:
        scheduler._check_worker(registry.worker('fast'))
        row = registry.snapshot()['workers'][1]
        assert not row['enabled'] and row['status'] == 'unknown'
    finally:
        scheduler.close()

def test_stalled_ssh_setup_does_not_lock_existing_other_worker_tunnel():
    node = {'id': 'test', 'lan_ip': '192.0.2.10', 'username': 'fixture'}
    registry = SimpleNamespace(node=lambda _: deepcopy(node))
    transport = InferenceTransport(registry)
    slow = {'worker_id': 'slow', 'node_id': 'test', 'remote_port': 44000}
    fast = {**slow, 'worker_id': 'fast', 'remote_port': 44001}
    process = Mock()
    process.poll.return_value = None
    transport.tunnels['fast'] = {'process': process, 'url': 'http://127.0.0.1:44001', 'binding': transport._worker_binding(fast, node)}
    entered, release = (threading.Event(), threading.Event())

    def address(_):
        entered.set()
        assert release.wait(3)
        raise ComputeError('Controlled SSH disconnection')
    transport._address = address

    def attempt():
        with pytest.raises(ComputeError):
            transport.endpoint(slow)
    thread = threading.Thread(target=attempt)
    thread.start()
    try:
        assert entered.wait(1)
        result = []
        other = threading.Thread(target=lambda: result.append(transport.endpoint(fast)))
        other.start()
        other.join(0.5)
        assert result == ['http://127.0.0.1:44001']
    finally:
        release.set()
        thread.join(3)
        transport.tunnels.clear()
        transport.close()

def test_worker_recovers_automatically_after_more_than_five_failed_checks(tmp_path):
    registry = make_registry(tmp_path)
    now = [0.0]
    observations = threading.Condition()
    calls = [0]

    def health(worker):
        with observations:
            calls[0] += 1
            status = 'healthy' if calls[0] > 6 else 'unhealthy'
            observations.notify_all()
        return {'status': status, 'model_id': worker['model_id'] if status == 'healthy' else None, 'last_heartbeat': registry.clock()}
    scheduler = ComputeScheduler(registry, clock=lambda: now[0], transport=SimpleNamespace(health=health, resources=lambda _: {}, close=lambda: None))
    thread = threading.Thread(target=scheduler._monitor_worker, args=('fast',))
    scheduler.health_workers['fast'] = thread
    thread.start()
    try:
        for expected in range(1, 8):
            with observations:
                assert observations.wait_for(lambda: calls[0] >= expected, timeout=2)
            with scheduler.condition:
                if expected < 7:
                    now[0] += 61
                    scheduler.condition.notify_all()
        deadline = time.monotonic() + 1
        while registry.snapshot()['workers'][1]['status'] != 'healthy' and time.monotonic() < deadline:
            time.sleep(0.01)
        row = registry.snapshot()['workers'][1]
        assert row['status'] == 'healthy' and row['consecutive_health_failures'] == 0
    finally:
        scheduler.close()
    assert not thread.is_alive()

def test_closed_transport_cannot_create_tunnel_after_delayed_authentication(monkeypatch):
    node = {'id': 'test', 'lan_ip': '192.0.2.10', 'username': 'fixture'}
    transport = InferenceTransport(SimpleNamespace(node=lambda _: deepcopy(node)))
    worker = {'worker_id': 'test', 'node_id': 'test', 'remote_port': 44000}
    launched = Mock()
    monkeypatch.setattr('hanni.compute.transport.subprocess.Popen', launched)

    def address(_):
        transport.close()
        return node['lan_ip']
    transport._address = address
    with pytest.raises(ComputeError, match='closed'):
        transport.endpoint(worker)
    launched.assert_not_called()
