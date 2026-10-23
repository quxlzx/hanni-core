"""Prospective original cluster controls, controlled dependencies, no live nodes."""
from copy import deepcopy
import json
import math
import subprocess
import threading
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.compute.registry import ComputeError
from hanni.dashboard import cluster
from scripts.campaign6_cluster.controlled import GIB, GPU, ControlledSocket, deployment, mock_resources, mock_tunnels, replace_config, sample

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    path, raw, registry, transport = deployment(tmp_path)
    yield (path, raw, registry, transport)
    transport.close()
    registry.close()

@pytest.mark.parametrize('frame', [[], None, True, 3, 'not a resource map', {'gpus': None}, {'gpus': 'not a GPU list'}, {'gpus': [None]}, {'gpus': [3]}], ids=['list', 'null', 'bool', 'number', 'string', 'gpu-null', 'gpu-string', 'gpu-null-row', 'gpu-number-row'])
def test_malformed_resource_shape_fails_closed_as_unknown_or_compute_error(isolated, monkeypatch, frame):
    _, _, registry, transport = isolated
    mock_resources(monkeypatch, transport, [frame])
    try:
        result = transport.resources(registry.worker('c6-worker'))
    except ComputeError:
        return
    assert result['ram_available_bytes'] is None
    assert result['vram_free_bytes'] is None
    assert result.get('node_hardware') is None

@pytest.mark.parametrize('field,value', [('ram_available_bytes', 17 * GIB), ('ram_available_bytes', True), ('ram_available_bytes', float('nan')), ('ram_total_bytes', -1), ('ram_total_bytes', False), ('ram_total_bytes', float('inf'))], ids=['available-exceeds-total', 'bool-available', 'nan-available', 'negative-total', 'bool-total', 'infinite-total'])
def test_invalid_ram_does_not_advertise_current_capacity(isolated, monkeypatch, field, value):
    _, _, registry, transport = isolated
    frame = sample()
    frame[field] = value
    mock_resources(monkeypatch, transport, [frame])
    result = transport.resources(registry.worker('c6-worker'))
    assert result['ram_available_bytes'] is None
    hardware = result.get('node_hardware') or {}
    assert hardware.get('ram_available_bytes') is None
    assert hardware.get('ram_total_bytes') is None

@pytest.mark.parametrize('field,value', [('vram_free_bytes', 13 * GIB), ('vram_free_bytes', True), ('vram_total_bytes', -1), ('vram_total_bytes', False), ('vram_total_bytes', float('inf')), ('utilization_percent', 101), ('utilization_percent', -1), ('utilization_percent', True), ('utilization_percent', float('nan'))], ids=['free-exceeds-total', 'bool-free', 'negative-total', 'bool-total', 'infinite-total', 'util-over-100', 'negative-util', 'bool-util', 'nan-util'])
def test_invalid_gpu_never_advertises_a_valid_gpu_row(isolated, monkeypatch, field, value):
    _, _, registry, transport = isolated
    frame = sample()
    frame['gpus'][0][field] = value
    mock_resources(monkeypatch, transport, [frame])
    result = transport.resources(registry.worker('c6-worker'))
    gpu = result.get('gpu_measurement')
    assert gpu is None or (gpu.get('vram_total_bytes') is None and gpu.get('vram_free_bytes') is None and (gpu.get('utilization_percent') is None))
    assert result['vram_free_bytes'] is None

def test_valid_resource_sample_and_cache_preserve_original_measurements(isolated, monkeypatch):
    _, _, registry, transport = isolated
    calls = mock_resources(monkeypatch, transport, [sample()])
    first = transport.resources(registry.worker('c6-worker'))
    second = transport.resources(registry.worker('c6-worker'))
    assert len(calls) == 1
    assert first == second
    assert first['ram_available_bytes'] == 8 * GIB
    assert first['vram_free_bytes'] == 6 * GIB
    assert first['gpu_measurement']['utilization_percent'] == 25
    assert math.isfinite(first['resource_sampled_at'])

def test_unknown_gpu_never_invents_vram_from_another_device(isolated, monkeypatch):
    _, raw, registry, transport = isolated
    worker = registry.worker('c6-worker')
    worker['startup']['gpu_device'] = 'GPU-87654321-4321-4321-4321-abcdef123456'
    mock_resources(monkeypatch, transport, [sample()])
    result = transport.resources(worker)
    assert result['ram_available_bytes'] == 8 * GIB
    assert result['vram_free_bytes'] is None
    assert result['gpu_measurement'] is None

@pytest.mark.parametrize('change', ['lan_ip', 'tailscale_ip', 'username'])
def test_address_cache_is_bound_to_current_protected_node(isolated, monkeypatch, change):
    path, raw, registry, transport = isolated
    calls = []
    monkeypatch.setattr('hanni.compute.transport.socket.create_connection', lambda *args, **kwargs: ControlledSocket())
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kw: ['fixture-ssh', node['username'], address])

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', run)
    transport._address(registry.node('owned-fixture'))
    raw['nodes'][0][change] = {'lan_ip': '' + '.'.join(('10', '42', '0', '6')) + '', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '21')) + '', 'username': 'fixture2'}[change]
    replace_config(path, raw, registry)
    result = transport._address(registry.node('owned-fixture'))
    assert len(calls) == 2, 'A changed target/account must receive a fresh verified SSH check.'
    assert result == raw['nodes'][0]['lan_ip']
    assert calls[-1][1] == raw['nodes'][0]['username']

@pytest.mark.parametrize('change', ['lan_ip', 'username', 'remote_port'])
def test_tunnel_cache_is_bound_to_current_protected_target(isolated, monkeypatch, change):
    path, raw, registry, transport = isolated
    created, cleaned = mock_tunnels(monkeypatch, transport)
    transport.endpoint(registry.worker('c6-worker'))
    if change == 'remote_port':
        raw['workers'][0][change] = 16102
    else:
        raw['nodes'][0][change] = {'lan_ip': '' + '.'.join(('10', '42', '0', '6')) + '', 'username': 'fixture2'}[change]
    replace_config(path, raw, registry)
    transport.endpoint(registry.worker('c6-worker'))
    assert len(created) == 2, 'A protected target change must not reuse its old active tunnel.'
    assert created[0] in cleaned
    assert created[-1].command[1:3] == [raw['nodes'][0]['username'], raw['nodes'][0]['lan_ip']]
    assert created[-1].command[-1].endswith(':' + str(raw['workers'][0]['remote_port']))

def test_resource_cache_cannot_relabel_old_node_sample_as_new_target(isolated, monkeypatch):
    path, raw, registry, transport = isolated
    changed = sample()
    changed['ram_available_bytes'] = 4 * GIB
    calls = mock_resources(monkeypatch, transport, [sample(), changed])
    transport.resources(registry.worker('c6-worker'))
    raw['nodes'][0]['lan_ip'] = '' + '.'.join(('10', '42', '0', '6')) + ''
    replace_config(path, raw, registry)
    result = transport.resources(registry.worker('c6-worker'))
    assert len(calls) == 2
    assert result['ram_available_bytes'] == 4 * GIB
    assert calls[-1]['address'] == '' + '.'.join(('10', '42', '0', '6')) + ''

@pytest.mark.parametrize('change', ['auth_config_file', 'username'])
def test_auth_cache_cannot_forward_previous_target_credential(isolated, monkeypatch, change):
    path, raw, registry, transport = isolated
    raw['workers'][0]['auth_config_file'] = '/run/c6/auth-a.json'
    replace_config(path, raw, registry)
    secrets = [uuid4().hex, uuid4().hex]
    reads, header_matches = ([], [])
    monkeypatch.setattr(transport, 'endpoint', lambda worker: 'http://127.0.0.1:16191')
    monkeypatch.setattr(transport, '_address', lambda node: node['lan_ip'])
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kw: ['fixture-ssh', address])

    def run(command, **kwargs):
        reads.append(True)
        return SimpleNamespace(returncode=0, stdout=secrets[len(reads) - 1].encode())
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', run)

    class Client:

        def __init__(self, **kwargs):
            assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, *args, **kwargs):
            index = len(header_matches)
            header_matches.append(kwargs['headers'].get('Authorization') == 'Bearer ' + secrets[index])
            return SimpleNamespace(is_redirect=False, raise_for_status=lambda: None, content=b'{}', json=lambda: {})
    monkeypatch.setattr('hanni.compute.transport.httpx.Client', Client)
    transport.request(registry.worker('c6-worker'), 'GET', '/health')
    if change == 'auth_config_file':
        raw['workers'][0][change] = '/run/c6/auth-b.json'
    else:
        raw['nodes'][0][change] = 'fixture2'
    replace_config(path, raw, registry)
    transport.request(registry.worker('c6-worker'), 'GET', '/health')
    assert len(reads) == 2, 'Credential cache must follow the exact protected target/account/auth path.'
    assert all(header_matches), 'Previous target credential must not be sent to the changed target.'

def current_row(at):
    return {'status': 'online', 'checked_at': at, 'sampled_at': at, 'metrics': {'cpu_percent': 25.0, 'ram_percent': 50.0, 'ram_used_bytes': 4 * GIB, 'ram_total_bytes': 8 * GIB}, 'address': '' + '.'.join(('10', '42', '0', '5')) + '', 'connection': 'lan', 'availability_source': 'telemetry', 'tailscale_online': None, 'os': 'linux', 'message': None, 'uptime_seconds': 60.0, 'processes': [{'name': 'controlled', 'cpu_percent': 25.0, 'ram_percent': 5.0}]}

@pytest.mark.parametrize('age', [7, 30, 180])
def test_expired_cluster_snapshot_cannot_present_stale_current_measurements(monkeypatch, age):
    clock = [1000.0]
    monkeypatch.setattr(cluster.time, 'time', lambda: clock[0])
    node = cluster.Node('c6', 'Controlled fixture', '', '' + '.'.join(('10', '42', '0', '5')) + '', None, 'fixture')
    monitor = cluster.ClusterMonitor(nodes=[node], tailnet=lambda: {'state': 'unavailable', 'peers': {}})
    monitor._record(node, current_row(clock[0]))
    clock[0] += age
    result = monitor.snapshot()['nodes'][0]
    assert result['metrics'] is None, 'Expired readings must not appear to be current.'
    assert result['uptime_seconds'] is None and result['processes'] is None
    assert result['availability_source'] != 'telemetry' or result['status'] != 'online'
    assert result['history'][-1]['cpu'] == 25.0, 'Historical readings remain truthful history.'

def test_fresh_cluster_snapshot_retains_current_measurements(monkeypatch):
    monkeypatch.setattr(cluster.time, 'time', lambda: 1001.0)
    node = cluster.Node('c6', 'Controlled fixture', '', '' + '.'.join(('10', '42', '0', '5')) + '', None, 'fixture')
    monitor = cluster.ClusterMonitor(nodes=[node], tailnet=lambda: {'state': 'unavailable', 'peers': {}})
    monitor._record(node, current_row(1000.0))
    result = monitor.snapshot()['nodes'][0]
    assert result['metrics']['cpu_percent'] == 25.0
    assert result['uptime_seconds'] == 60.0
    assert result['status'] == 'online'

@pytest.mark.parametrize('value', [101.0, float('inf'), float('nan'), True])
def test_invalid_process_ram_percentage_is_withheld(value):
    result = cluster.workload_sample({'uptime_seconds': 60.0, 'processes': [{'name': 'controlled', 'cpu_percent': 12.0, 'ram_percent': value}]})
    assert result['processes'] == []

def test_multicore_process_cpu_and_valid_process_ram_are_preserved():
    result = cluster.workload_sample({'uptime_seconds': 60.0, 'processes': [{'name': 'controlled', 'cpu_percent': 240.0, 'ram_percent': 50.0}]})
    assert result['processes'][0]['cpu_percent'] == 240.0
    assert result['processes'][0]['ram_percent'] == 50.0

def test_cancel_closes_only_matching_owned_http_request(isolated):
    _, _, _, transport = isolated
    events = [threading.Event(), threading.Event()]
    closed = []
    first = SimpleNamespace(close=lambda: closed.append('selected'))
    second = SimpleNamespace(close=lambda: closed.append('other'))
    transport.clients = {1: ('c6-worker', first, events[0]), 2: ('other-worker', second, events[1])}
    transport.cancel('c6-worker', events[0])
    assert closed == ['selected']
    assert events[0].is_set() and (not events[1].is_set())
    transport.clients.clear()

def test_precancel_never_opens_tunnel_or_reads_credential(isolated, monkeypatch):
    _, _, registry, transport = isolated
    event = threading.Event()
    event.set()
    monkeypatch.setattr(transport, 'endpoint', lambda worker: pytest.fail('Precancel opened endpoint.'))
    with pytest.raises(ComputeError, match='cancel'):
        transport.request(registry.worker('c6-worker'), 'GET', '/health', cancel=event)

def test_close_only_cleans_owned_tunnel_objects(isolated, monkeypatch):
    _, _, registry, transport = isolated
    created, cleaned = mock_tunnels(monkeypatch, transport)
    transport.endpoint(registry.worker('c6-worker'))
    transport.close()
    assert cleaned == created
    assert transport.tunnels == {}

def test_transport_and_monitor_reads_preserve_exact_protected_deployment_bytes(isolated, monkeypatch):
    path, _, registry, transport = isolated
    original = path.read_bytes()
    mock_resources(monkeypatch, transport, [sample()])
    transport.resources(registry.worker('c6-worker'))
    cluster.load_nodes(path.parent.parent)
    registry.snapshot()
    assert path.read_bytes() == original

@pytest.mark.parametrize('tailscale', [False, True])
def test_original_ssh_options_keep_authentication_and_host_checks(monkeypatch, tailscale):
    node = cluster.Node('c6', 'Controlled', '', '' + '.'.join(('10', '42', '0', '5')) + '', '' + '.'.join(('100', '64', '0', '19')) + '', 'fixture')
    command = cluster._ssh_prefix(node, node.tailscale_ip if tailscale else node.lan_ip, tailscale='controlled-tailscale' if tailscale else None)
    assert 'StrictHostKeyChecking=yes' in command
    assert 'BatchMode=yes' in command and 'RequestTTY=no' in command
    assert 'ClearAllForwardings=yes' in command and 'ConnectionAttempts=1' in command
    assert not any(('StrictHostKeyChecking=no' in part or 'accept-new' in part for part in command))

@pytest.mark.parametrize('error,hint', [('Host key verification failed', 'host key'), ('REMOTE HOST IDENTIFICATION HAS CHANGED', 'host key'), ('Permission denied (publickey)', 'authentication'), ('Tailscale SSH requires an additional check', 'fresh sign-in'), ('connection reset', 'unavailable')])
def test_ssh_classification_does_not_export_raw_credentials_or_login_urls(error, hint):
    generated = uuid4().hex
    message = cluster._ssh_error(error + '\nhttps://example.invalid/' + generated)
    assert hint in message
    assert (generated in message) is False
    assert 'https://' not in message

def test_roster_projection_omits_tailnet_identity_and_unrelated_nodes(monkeypatch):
    generated = uuid4().hex
    raw = {'BackendState': 'Running', 'Peer': {'fixture': {'TailscaleIPs': ['' + '.'.join(('100', '64', '0', '19')) + ''], 'Online': True, 'OS': 'linux', 'sshHostKeys': [generated], 'UserID': generated, 'HostName': generated}, 'foreign': {'TailscaleIPs': ['' + '.'.join(('100', '64', '0', '22')) + ''], 'Online': True, 'OS': 'linux'}}}
    monkeypatch.setattr(cluster, '_tailscale_executable', lambda: 'controlled-tailscale')
    monkeypatch.setattr(cluster, '_run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(raw)))
    node = cluster.Node('c6', 'Controlled', '', None, '' + '.'.join(('100', '64', '0', '19')) + '', 'fixture')
    result = cluster.tailscale_snapshot([node])
    assert result == {'state': 'connected', 'peers': {'' + '.'.join(('100', '64', '0', '19')) + '': {'online': True, 'os': 'linux', 'ssh_enabled': True}}}
    assert (generated in json.dumps(result)) is False

@pytest.mark.parametrize('reason', ['trust', 'auth', 'timeout'])
def test_failed_lan_authentication_requires_verified_tailnet_fallback(isolated, monkeypatch, reason):
    _, _, registry, transport = isolated
    calls = []
    monkeypatch.setattr('hanni.compute.transport.socket.create_connection', lambda *args, **kwargs: ControlledSocket())
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kwargs: ['controlled-ssh', address])

    def run(command, **kwargs):
        calls.append(command[1])
        if len(calls) == 1:
            if reason == 'timeout':
                raise subprocess.TimeoutExpired('controlled-ssh', 5)
            return SimpleNamespace(returncode=255)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', run)
    address = transport._address(registry.node('owned-fixture'))
    assert calls == ['' + '.'.join(('10', '42', '0', '5')) + '', '' + '.'.join(('100', '64', '0', '19')) + '']
    assert address == '' + '.'.join(('100', '64', '0', '19')) + ''

def test_unverified_connectivity_cannot_create_a_reusable_address_cache(isolated, monkeypatch):
    _, _, registry, transport = isolated
    monkeypatch.setattr('hanni.compute.transport.socket.create_connection', lambda *args, **kwargs: ControlledSocket())
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kwargs: ['controlled-ssh', address])
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', lambda *args, **kwargs: SimpleNamespace(returncode=255))
    with pytest.raises(ComputeError):
        transport._address(registry.node('owned-fixture'))
    assert transport.addresses == {}

def test_current_health_timestamp_does_not_survive_expiry_as_healthy(isolated):
    _, _, registry, _ = isolated
    clock = [1000.0]
    registry.clock = lambda: clock[0]
    registry.observe('c6-worker', status='healthy', last_heartbeat=1000.0)
    assert registry.snapshot()['workers'][0]['status'] == 'healthy'
    clock[0] += 31
    assert registry.snapshot()['workers'][0]['status'] != 'healthy'

def test_remote_timeout_returns_unknown_resources_without_raw_error(isolated, monkeypatch):
    _, _, registry, transport = isolated
    generated = uuid4().hex
    monkeypatch.setattr(transport, '_address', lambda node: node['lan_ip'])
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kwargs: ['controlled-ssh'])

    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired(generated, 6, output=generated.encode())
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', run)
    result = transport.resources(registry.worker('c6-worker'))
    assert result['ram_available_bytes'] is None and result['vram_free_bytes'] is None
    assert result.get('resource_sampled_at') is None
    assert (generated in json.dumps(result)) is False

@pytest.mark.parametrize('change', ['lan_ip', 'tailscale_ip', 'username'])
def test_context_proof_cannot_authorize_same_id_different_ssh_target(isolated, change):
    path, raw, registry, _ = isolated
    registry.record_context_verified('c6-worker', target_tokens=8192, prompt_tokens=7500, model_id='c6-synthetic-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
    original_identity = registry._worker_identity(registry.worker('c6-worker'))
    raw['nodes'][0][change] = {'lan_ip': '' + '.'.join(('10', '42', '0', '6')) + '', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '21')) + '', 'username': 'fixture2'}[change]
    replace_config(path, raw, registry)
    assert registry._worker_identity(registry.worker('c6-worker')) != original_identity
    assert registry.prior_verified_context('c6-worker') == 0
    assert registry.snapshot()['workers'][0]['max_context_verified'] is None

@pytest.mark.parametrize('change', ['lan_ip', 'tailscale_ip', 'username'])
def test_health_resource_observation_cannot_represent_changed_ssh_target(isolated, change):
    path, raw, registry, _ = isolated
    registry.observe('c6-worker', status='healthy', last_heartbeat=registry.clock(), ram_available_bytes=8 * GIB, vram_free_bytes=6 * GIB, runtime_identity='controlled-old-host', runtime_files_identity='controlled-old-files')
    raw['nodes'][0][change] = {'lan_ip': '' + '.'.join(('10', '42', '0', '6')) + '', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '21')) + '', 'username': 'fixture2'}[change]
    replace_config(path, raw, registry)
    result = registry.snapshot()['workers'][0]
    assert result['status'] != 'healthy'
    assert result['ram_available_bytes'] is None
    assert result['vram_free_bytes'] is None

def test_display_name_change_does_not_withdraw_same_runtime_context_proof(isolated):
    path, raw, registry, _ = isolated
    registry.record_context_verified('c6-worker', target_tokens=8192, prompt_tokens=7500, model_id='c6-synthetic-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
    identity = registry._worker_identity(registry.worker('c6-worker'))
    raw['nodes'][0]['name'] = 'Renamed controlled display'
    replace_config(path, raw, registry)
    assert registry._worker_identity(registry.worker('c6-worker')) == identity
    assert registry.prior_verified_context('c6-worker') == 8192

def test_rebinding_withholds_existing_proof_without_modifying_its_durable_bytes(isolated):
    path, raw, registry, _ = isolated
    registry.record_context_verified('c6-worker', target_tokens=8192, prompt_tokens=7500, model_id='c6-synthetic-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
    proof = path.with_name('context-measurements.json')
    original = proof.read_bytes()
    raw['nodes'][0]['username'] = 'fixture2'
    replace_config(path, raw, registry)
    assert registry.prior_verified_context('c6-worker') == 0
    assert proof.read_bytes() == original

def test_registry_snapshot_exposes_original_resource_measurement_timestamp(isolated):
    _, _, registry, _ = isolated
    registry.observe('c6-worker', status='healthy', last_heartbeat=registry.clock(), ram_available_bytes=8 * GIB, resource_sampled_at=1234.0)
    assert registry.snapshot()['workers'][0]['resource_sampled_at'] == 1234.0

@pytest.mark.parametrize('age,expected', [(6.0, True), (6.001, False), (-1.0, False)])
def test_current_cluster_sample_has_bounded_nonfuture_freshness(monkeypatch, age, expected):
    monkeypatch.setattr(cluster.time, 'time', lambda: 1000.0 + age)
    node = cluster.Node('c6', 'Controlled', '', '' + '.'.join(('10', '42', '0', '5')) + '', None, 'fixture')
    monitor = cluster.ClusterMonitor(nodes=[node])
    monitor._record(node, current_row(1000.0))
    assert (monitor.snapshot()['nodes'][0]['metrics'] is not None) is expected

def test_closed_transport_retains_no_auth_or_resource_cache(isolated, monkeypatch):
    _, _, registry, transport = isolated
    mock_resources(monkeypatch, transport, [sample()])
    transport.resources(registry.worker('c6-worker'))
    transport.auth['c6-worker', 'controlled-scope'] = uuid4().hex
    transport.close()
    assert transport.auth == {}
    assert transport.resource_cache == {}
    assert transport.addresses == {} and transport.identity_file_cache == {}

@pytest.mark.parametrize('device', [0, '0'])
@pytest.mark.parametrize('protocol', ['openai', 'strata_openai'])
def test_unobserved_gpu_index_never_becomes_uuid_assignment(isolated, monkeypatch, device, protocol):
    _, _, registry, transport = isolated
    worker = registry.worker('c6-worker')
    worker['startup']['gpu_device'] = device
    worker['protocol'] = protocol
    mock_resources(monkeypatch, transport, [sample()])
    result = transport.resources(worker)
    assert result['gpu_measurement'] is None
    assert result['vram_free_bytes'] is None

@pytest.mark.parametrize('revocation', ['removed', 'malformed'])
def test_reintroduced_source_after_authority_loss_needs_new_health_resources(isolated, revocation):
    path, raw, registry, _ = isolated
    registry.observe('c6-worker', status='healthy', last_heartbeat=registry.clock(), ram_available_bytes=8 * GIB, vram_free_bytes=6 * GIB, resource_sampled_at=registry.clock())
    if revocation == 'removed':
        path.unlink()
    else:
        path.write_text('{', encoding='utf8')
    registry.reload()
    assert registry.workers() == []
    raw['nodes'][0]['username'] = 'fixture2'
    replace_config(path, raw, registry)
    result = registry.snapshot()['workers'][0]
    assert result['status'] != 'healthy'
    assert result['ram_available_bytes'] is None and result['vram_free_bytes'] is None

@pytest.mark.parametrize('boundary', ['endpoint', 'auth', 'client', 'response'])
def test_source_withdrawal_at_each_request_boundary_prevents_completion(isolated, monkeypatch, boundary):
    path, raw, registry, transport = isolated
    raw['workers'][0]['auth_config_file'] = '/run/c6/auth.json'
    replace_config(path, raw, registry)
    sends, reads = ([], [])
    token = uuid4().hex

    def withdraw():
        raw['nodes'][0]['username'] = 'replacement'
        replace_config(path, raw, registry)

    def endpoint(worker):
        if boundary == 'endpoint':
            withdraw()
        return 'http://127.0.0.1:16191'

    def read(command, **kwargs):
        reads.append(command[1])
        if boundary == 'auth':
            withdraw()
        return SimpleNamespace(returncode=0, stdout=token.encode())

    class Client:

        def __init__(self, **kwargs):
            if boundary == 'client':
                withdraw()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, *args, **kwargs):
            sends.append(True)
            if boundary == 'response':
                withdraw()
            return SimpleNamespace(is_redirect=False, content=b'{}', json=lambda: {}, raise_for_status=lambda: None)
    monkeypatch.setattr(transport, 'endpoint', endpoint)
    monkeypatch.setattr(transport, '_address', lambda node: node['lan_ip'])
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kw: ['controlled-ssh', node['username'], address])
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', read)
    monkeypatch.setattr('hanni.compute.transport.httpx.Client', Client)
    with pytest.raises(ComputeError):
        transport.request(registry.worker('c6-worker'), 'GET', '/health')
    assert len(sends) == (1 if boundary == 'response' else 0)
    assert reads == ([] if boundary == 'endpoint' else ['fixture'])
    assert transport.clients == {}

def test_known_tunnel_binding_mismatch_is_rejected_before_authentication(isolated, monkeypatch):
    _, _, registry, transport = isolated
    created, _ = mock_tunnels(monkeypatch, transport)
    worker = registry.worker('c6-worker')
    transport.endpoint(worker)
    transport.tunnels['c6-worker']['binding'] = 'different-controlled-source'
    monkeypatch.setattr(transport, 'endpoint', lambda worker: 'http://127.0.0.1:16191')
    with pytest.raises(ComputeError, match='forwarding source'):
        transport.request(worker, 'GET', '/health')
    assert created and transport.clients == {}

def test_cancel_during_endpoint_resolution_never_dispatches_http(isolated, monkeypatch):
    _, _, registry, transport = isolated
    event = threading.Event()

    def endpoint(worker):
        event.set()
        return 'http://127.0.0.1:16191'
    monkeypatch.setattr(transport, 'endpoint', endpoint)
    monkeypatch.setattr('hanni.compute.transport.httpx.Client', lambda **kwargs: pytest.fail('Cancelled resolution opened an HTTP client.'))
    with pytest.raises(ComputeError, match='cancel'):
        transport.request(registry.worker('c6-worker'), 'GET', '/health', cancel=event)
    assert transport.clients == {}

@pytest.mark.parametrize('scope', ['global', 'worker'])
@pytest.mark.parametrize('boundary', ['endpoint', 'auth', 'client', 'response', 'already_disabled'])
def test_request_pins_authority_flags_but_allows_stable_disabled_health(isolated, monkeypatch, scope, boundary):
    path, raw, registry, transport = isolated
    raw['workers'][0]['auth_config_file'] = '/run/c6/auth.json'
    replace_config(path, raw, registry)

    def disable():
        target = raw if scope == 'global' else raw['workers'][0]
        target['enabled'] = False
        replace_config(path, raw, registry)
    if boundary == 'already_disabled':
        disable()
    sends = []
    token = uuid4().hex

    def endpoint(worker):
        if boundary == 'endpoint':
            disable()
        return 'http://127.0.0.1:16193'

    def secure_read(*args, **kwargs):
        if boundary == 'auth':
            disable()
        return SimpleNamespace(returncode=0, stdout=token.encode())

    class Client:

        def __init__(self, **kwargs):
            if boundary == 'client':
                disable()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, *args, **kwargs):
            sends.append(True)
            if boundary == 'response':
                disable()
            return SimpleNamespace(is_redirect=False, content=b'{}', json=lambda: {}, raise_for_status=lambda: None)
    monkeypatch.setattr(transport, 'endpoint', endpoint)
    monkeypatch.setattr(transport, '_address', lambda node: node['lan_ip'])
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kw: ['controlled-ssh', node['username'], address])
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', secure_read)
    monkeypatch.setattr('hanni.compute.transport.httpx.Client', Client)
    if boundary == 'already_disabled':
        assert transport.request(registry.worker('c6-worker'), 'GET', '/health') == {}
    else:
        with pytest.raises(ComputeError, match='authority changed'):
            transport.request(registry.worker('c6-worker'), 'GET', '/health')
    assert len(sends) == (1 if boundary in {'response', 'already_disabled'} else 0)
    assert transport.clients == {}
