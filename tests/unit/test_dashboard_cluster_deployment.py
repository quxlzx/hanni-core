from contextlib import nullcontext
from dataclasses import asdict, replace
import json
from types import SimpleNamespace
import pytest
from hanni.dashboard import cluster, cluster_credentials
from hanni.dashboard.cluster_power import ClusterPower
from hanni.dashboard.cluster_terminal import ClusterTerminal
from tests.unit.cluster_fixture import NODES

def deployment(tmp_path, rows):
    path = tmp_path / 'compute/deployment.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'enabled': False, 'nodes': rows, 'workers': [], 'policy': {}}), encoding='utf-8')
    return path

def test_missing_deployment_retains_display_names_without_network_targets(tmp_path):
    nodes = cluster.load_nodes(tmp_path)
    assert len(nodes) == 9 and nodes[-1].emoji == '🪼' and nodes[-1].maintenance
    assert all((node.lan_ip is node.tailscale_ip is node.username is None for node in nodes))
    result = cluster.probe_node(nodes[0])
    assert result['metrics'] is None and result['status'] == 'unreachable'

def test_protected_roster_is_shared_by_monitor_power_terminal_and_vault(tmp_path, monkeypatch):
    node = replace(NODES[0], id='owner-node', name='Owner node')
    deployment(tmp_path, [asdict(node)])
    monitor = cluster.ClusterMonitor(data_dir=tmp_path)
    assert monitor.nodes == (node,)
    assert ClusterPower(monitor, tmp_path).nodes == (node,)
    assert ClusterTerminal(monitor, tmp_path).nodes == (node,)
    entries = {}
    monkeypatch.setattr(cluster_credentials, '_backend', lambda: SimpleNamespace(set_password=lambda service, key, value: entries.__setitem__((service, key), value), get_password=lambda service, key: entries.get((service, key))))
    cluster_credentials.set_sudo_password(node, tmp_path, 'synthetic-password')
    assert cluster_credentials.get_sudo_password(node, tmp_path).reveal() == 'synthetic-password'
    assert cluster_credentials.get_sudo_password(replace(node, tailscale_ip='' + '.'.join(('100', '64', '0', '99')) + ''), tmp_path) is None

@pytest.mark.parametrize('changes', [{'username': 'owner; reboot'}, {'lan_ip': '' + '.'.join(('11', '42', '0', '36')) + ''}, {'maintenance': 'false'}, {'command': 'whoami'}])
def test_invalid_deployment_never_supplies_network_targets(tmp_path, changes):
    deployment(tmp_path, [{**asdict(NODES[0]), **changes}])
    with pytest.raises(ValueError):
        cluster.load_nodes(tmp_path)
    monitor = cluster.ClusterMonitor(data_dir=tmp_path)
    assert monitor.configuration_error and all((node.lan_ip is None for node in monitor.nodes))

def test_duplicate_node_identity_is_rejected(tmp_path):
    deployment(tmp_path, [asdict(NODES[0]), asdict(NODES[0])])
    with pytest.raises(ValueError):
        cluster.load_nodes(tmp_path)

def test_unverified_lan_host_falls_back_to_verified_tailnet_without_accepting_keys(monkeypatch):
    calls = []
    monkeypatch.setattr(cluster.socket, 'create_connection', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(cluster.shutil, 'which', lambda name: name)
    monkeypatch.setattr(cluster, '_tailscale_executable', lambda: 'tailscale')

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == 'ssh':
            return SimpleNamespace(returncode=255, stdout='', stderr='Host key verification failed.')
        return SimpleNamespace(returncode=0, stdout=json.dumps({'cpu_percent': 12, 'ram_percent': 50, 'ram_used_bytes': 8, 'ram_total_bytes': 16}), stderr='')
    monkeypatch.setattr(cluster, '_run', run)
    result = cluster.probe_node(NODES[0], {'online': True, 'os': 'linux', 'ssh_enabled': True})
    assert len(calls) == 2 and result['connection'] == 'tailscale' and (result['metrics']['cpu_percent'] == 12)
    assert all(('StrictHostKeyChecking=yes' in call for call in calls))
    assert calls[1][:3] == ['tailscale', 'ssh', f'athena@{NODES[0].tailscale_ip}']
