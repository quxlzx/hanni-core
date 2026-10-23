"""Prospective independent development boundaries; private finals are separate."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import pytest
from hanni.compute import ComputeScheduler
from hanni.compute.registry import ComputeError
from hanni.dashboard import cluster
from scripts.campaign6_verification.boundary_controls import GIB, DEVICE, LeafSocket, cluster_frame, environment, replace, resource_frame, resource_leaves, bind_controlled_proof

@pytest.mark.parametrize('frame', [[], None, 11, {'gpus': [False]}])
def test_malformed_original_resource_response_has_typed_unknown_outcome(tmp_path, frame):
    with environment(tmp_path) as env, resource_leaves(env, [frame]):
        try:
            receipt = env.transport.resources(env.worker())
        except ComputeError:
            return
        assert receipt['ram_available_bytes'] is None
        assert receipt['vram_free_bytes'] is None
        assert receipt.get('node_hardware') is None

@pytest.mark.parametrize('field,value', [('ram_available_bytes', 13 * GIB), ('ram_total_bytes', True)])
def test_contradictory_ram_measurement_is_not_current_capacity(tmp_path, field, value):
    frame = resource_frame()
    frame[field] = value
    with environment(tmp_path) as env, resource_leaves(env, [frame]):
        receipt = env.transport.resources(env.worker())
        assert receipt['ram_available_bytes'] is None
        assert (receipt.get('node_hardware') or {}).get('ram_available_bytes') is None

@pytest.mark.parametrize('field,value', [('vram_free_bytes', 11 * GIB), ('utilization_percent', 117)])
def test_invalid_gpu_measurement_is_not_dispatch_capacity(tmp_path, field, value):
    frame = resource_frame()
    frame['gpus'][0][field] = value
    with environment(tmp_path) as env, resource_leaves(env, [frame]):
        receipt = env.transport.resources(env.worker())
        assert receipt['vram_free_bytes'] is None
        assert receipt.get('gpu_measurement') is None or receipt['gpu_measurement'].get('vram_free_bytes') is None

def test_exact_gpu_uuid_and_valid_capacity_positive_control(tmp_path):
    with environment(tmp_path) as env, resource_leaves(env, [resource_frame()]) as calls:
        receipt = env.transport.resources(env.worker())
        assert receipt['ram_available_bytes'] == 5 * GIB
        assert receipt['vram_free_bytes'] == 4 * GIB
        assert receipt['gpu_measurement']['id'] == DEVICE
        assert len(calls) == 1

def test_other_gpu_must_not_supply_registered_device_capacity(tmp_path):
    frame = resource_frame()
    frame['gpus'][0]['id'] = 'GPU-1234abcd-5678-9012-abcd-1234567890ab'
    with environment(tmp_path) as env, resource_leaves(env, [frame]):
        receipt = env.transport.resources(env.worker())
        assert receipt['ram_available_bytes'] == 5 * GIB
        assert receipt['vram_free_bytes'] is None
        assert receipt.get('gpu_measurement') is None

@pytest.mark.parametrize('field,value', [('lan_ip', '' + '.'.join(('10', '42', '0', '8')) + ''), ('username', 'observer2')])
def test_protected_target_change_requires_fresh_original_ssh_check(tmp_path, field, value):
    with environment(tmp_path) as env:
        commands = []

        def execute(command, **kwargs):
            commands.append(command)
            return SimpleNamespace(returncode=0)
        with patch('hanni.compute.transport.socket.create_connection', lambda *args, **kw: LeafSocket()), patch.object(env.transport, '_ssh', lambda node, address, **kw: ['owned', node['username'], address]), patch('hanni.compute.transport.subprocess.run', execute):
            env.transport._address(env.registry.node('probe-node'))
            env.data['nodes'][0][field] = value
            replace(env)
            env.transport._address(env.registry.node('probe-node'))
            assert len(commands) == 2
            assert commands[-1][1:3] == [env.data['nodes'][0]['username'], env.data['nodes'][0]['lan_ip']]

def test_changed_node_does_not_inherit_previous_target_hardware(tmp_path):
    replacement = resource_frame()
    replacement['ram_available_bytes'] = 3 * GIB
    with environment(tmp_path) as env, resource_leaves(env, [resource_frame(), replacement]) as calls:
        env.transport.resources(env.worker())
        env.data['nodes'][0]['lan_ip'] = '' + '.'.join(('10', '42', '0', '9')) + ''
        replace(env)
        receipt = env.transport.resources(env.worker())
        assert calls == ['' + '.'.join(('10', '42', '0', '7')) + '', '' + '.'.join(('10', '42', '0', '9')) + '']
        assert receipt['ram_available_bytes'] == 3 * GIB

@pytest.mark.parametrize('change', ['auth_path', 'account'])
def test_protected_auth_identity_change_never_reuses_previous_secret(tmp_path, change):
    with environment(tmp_path) as env:
        env.data['workers'][0]['auth_config_file'] = '/run/owned/c6-a.json'
        replace(env)
        secrets = [uuid4().hex, uuid4().hex]
        reads, matches = ([], [])

        def execute(*args, **kwargs):
            reads.append(True)
            return SimpleNamespace(returncode=0, stdout=secrets[len(reads) - 1].encode())

        class Client:

            def __init__(self, **kwargs):
                assert not kwargs['trust_env'] and (not kwargs['follow_redirects'])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def request(self, *args, **kwargs):
                matches.append(kwargs['headers'].get('Authorization') == 'Bearer ' + secrets[len(matches)])
                return SimpleNamespace(is_redirect=False, content=b'{}', json=lambda: {}, raise_for_status=lambda: None)
        with patch.object(env.transport, 'endpoint', lambda worker: 'http://127.0.0.1:17381'), patch.object(env.transport, '_address', lambda node: node['lan_ip']), patch.object(env.transport, '_ssh', lambda *args, **kw: ['owned']), patch('hanni.compute.transport.subprocess.run', execute), patch('hanni.compute.transport.httpx.Client', Client):
            env.transport.request(env.worker(), 'GET', '/health')
            if change == 'auth_path':
                env.data['workers'][0]['auth_config_file'] = '/run/owned/c6-b.json'
            else:
                env.data['nodes'][0]['username'] = 'observer3'
            replace(env)
            env.transport.request(env.worker(), 'GET', '/health')
            assert len(reads) == 2, 'Changed protected auth identity requires an original secure re-read.'
            assert all(matches), 'A prior synthetic credential crossed its protected target boundary.'

@pytest.mark.parametrize('age', [9.0, 49.0])
def test_current_cluster_metrics_expire_while_history_remains(tmp_path, age):
    clock = [8100.0]
    node = cluster.Node('owned', 'Owned synthetic node', '', '' + '.'.join(('10', '42', '0', '7')) + '', None, 'observer')
    with patch('hanni.dashboard.cluster.time.time', lambda: clock[0]):
        monitor = cluster.ClusterMonitor(nodes=[node], tailnet=lambda: {'state': 'unavailable', 'peers': {}})
        monitor._record(node, cluster_frame(clock[0]))
        clock[0] += age
        row = monitor.snapshot()['nodes'][0]
        assert row['metrics'] is None and row['uptime_seconds'] is None and (row['processes'] is None)
        assert row['status'] != 'online' or row['availability_source'] != 'telemetry'
        assert row['history'][-1]['cpu'] == 31.0

def test_fresh_cluster_and_multicore_process_cpu_positive_controls():
    node = cluster.Node('owned', 'Owned', '', '' + '.'.join(('10', '42', '0', '7')) + '', None, 'observer')
    with patch('hanni.dashboard.cluster.time.time', lambda: 8102.0):
        monitor = cluster.ClusterMonitor(nodes=[node])
        monitor._record(node, cluster_frame(8100.0))
        assert monitor.snapshot()['nodes'][0]['metrics']['cpu_percent'] == 31.0
    row = cluster.workload_sample({'uptime_seconds': 7.0, 'processes': [{'name': 'owned', 'cpu_percent': 321.0, 'ram_percent': 26.0}]})
    assert row['processes'][0]['cpu_percent'] == 321.0

def test_process_ram_percentage_cannot_exceed_total_memory():
    row = cluster.workload_sample({'uptime_seconds': 7.0, 'processes': [{'name': 'owned', 'cpu_percent': 12.0, 'ram_percent': 109.0}]})
    assert row['processes'] == []

def test_fresh_health_does_not_make_expired_capacity_current(tmp_path):
    with environment(tmp_path) as env:
        env.registry.observe('probe-worker', status='healthy', last_heartbeat=7000.0, model_id='controlled-protocol-model', context_reported=8192, ram_available_bytes=5 * GIB, vram_free_bytes=4 * GIB, gpu_measurement=resource_frame()['gpus'][0], resource_sampled_at=6935.0)
        bind_controlled_proof(env)
        scheduler = ComputeScheduler(env.registry, transport=env.transport)
        try:
            assert scheduler._choices({'synthetic'}, 100) == [], 'Expired GPU/RAM sampling is not current admission proof.'
        finally:
            scheduler.close()

@pytest.mark.parametrize('field,value', [('lan_ip', '' + '.'.join(('10', '42', '0', '11')) + ''), ('tailscale_ip', '' + '.'.join(('100', '64', '0', '24')) + ''), ('username', 'observer4')])
def test_protected_node_identity_change_withdraws_original_proof_and_health(tmp_path, field, value):
    with environment(tmp_path) as env:
        env.registry.observe('probe-worker', status='healthy', last_heartbeat=7000.0, model_id='controlled-protocol-model', context_reported=8192, ram_available_bytes=5 * GIB, vram_free_bytes=4 * GIB, resource_sampled_at=7000.0)
        bind_controlled_proof(env)
        before = env.registry._worker_identity(env.worker())
        env.data['nodes'][0][field] = value
        replace(env)
        after = env.registry._worker_identity(env.worker())
        assert after != before, 'Protected account/address must be part of the serving identity.'
        row = env.registry.snapshot()['workers'][0]
        assert row['status'] != 'healthy'
        assert not row['max_context_verified']
        assert row['ram_available_bytes'] is None and row['vram_free_bytes'] is None

def test_display_metadata_change_retains_original_identity_and_proof(tmp_path):
    with environment(tmp_path) as env:
        env.registry.observe('probe-worker', status='healthy', last_heartbeat=7000.0, model_id='controlled-protocol-model', context_reported=8192, ram_available_bytes=5 * GIB, vram_free_bytes=4 * GIB, resource_sampled_at=7000.0)
        bind_controlled_proof(env)
        before = env.registry._worker_identity(env.worker())
        env.data['nodes'][0]['name'] = 'Renamed display label'
        replace(env)
        assert env.registry._worker_identity(env.worker()) == before
        assert env.registry.snapshot()['workers'][0]['max_context_verified'] == 8192

def test_retained_context_proof_cannot_override_actual_configured_allocation(tmp_path):
    with environment(tmp_path) as env:
        env.data['workers'][0]['context_configured'] = 256
        replace(env)
        env.registry.observe('probe-worker', status='healthy', last_heartbeat=7000.0, model_id='controlled-protocol-model', context_reported=8192, ram_available_bytes=5 * GIB, vram_free_bytes=4 * GIB, resource_sampled_at=7000.0)
        bind_controlled_proof(env)
        scheduler = ComputeScheduler(env.registry, transport=env.transport)
        try:
            assert scheduler._choices({'synthetic'}, 1000) == [], 'Configured allocation is an independent upper bound.'
        finally:
            scheduler.close()

def public_case(scenario='chat', **kwargs):
    worker = {'id': 'public-development', 'node_id': 'owned-public', 'enabled': True, 'protocol': 'openai', 'concurrency': 1, 'interactive_reserve': 0, 'categories': ['synthetic'], 'capabilities': ['analysis', 'structured_json'], 'context_configured': 8192, 'context_reported': 8192, 'verified_context': 8192, 'health': 'healthy', 'heartbeat_age_seconds': 0, 'resource_sample_age_seconds': 0, 'resources': {'ram_available_bytes': 6 * GIB, 'vram_free_bytes': GIB}, 'gpu': 'controlled-gpu', 'latency_ms': 30, 'active_jobs': 0, 'response_behavior': 'complete'}
    worker.update(kwargs.pop('worker', {}))
    case = {'id': 'PUBLIC-C6-CONTRACT', 'category': 'public_contract', 'scenario': scenario, 'workers': [worker], 'request': {'messages': [{'role': 'user', 'content': 'Independent exposed synthetic receipt.'}], 'categories': ['synthetic'], 'max_tokens': 48, 'interactive': False, 'retry_override': 0, 'queue_seconds': 0.2}, 'controls': {}, 'policy': {'max_queue': 2, 'max_retries': 1, 'timeout_seconds': 2}, 'scope': 'Controlled public executor contract; no private final data or actual model.'}
    case.update(kwargs)
    return case

def test_executor_original_http_and_original_source_acceptance(tmp_path):
    from scripts.campaign6_verification.executor import run_case
    row = run_case(public_case('verified_chat', controls={'verify_against_source': True}), tmp_path / 'case')
    assert len(row['results']) == 1
    assert row['jobs'][0]['state'] == 'VERIFIED'
    assert row['source_verification'][0]['original_read']['verification']['status'] == 'VERIFIED'
    assert row['all_reservations_released'] and row['owned_providers_closed']

def test_executor_original_verifier_rejects_controlled_unsupported_claim(tmp_path):
    from scripts.campaign6_verification.executor import run_case
    row = run_case(public_case('verified_chat', worker={'response_behavior': 'unsupported_claim'}, controls={'verify_against_source': True}), tmp_path / 'case')
    assert len(row['results']) == 1
    assert row['jobs'][0]['state'] == 'FAILED'
    assert row['all_reservations_released'] and row['owned_providers_closed']

def test_executor_no_expected_fields_and_scoring_separated(tmp_path):
    from scripts.campaign6_verification.executor import run_case
    case = public_case()
    case['expected'] = {'not_allowed': True}
    with pytest.raises(ValueError, match='oracle'):
        run_case(case, tmp_path / 'case')

def test_original_dispatch_cannot_exceed_configured_allocation(tmp_path):
    from scripts.campaign6_verification.executor import run_case
    case = public_case(worker={'context_configured': 128})
    case['request']['messages'][0]['content'] = 'Owned synthetic source ' * 20
    row = run_case(case, tmp_path / 'case')
    assert sum((len(calls) for calls in row['provider_calls'].values())) == 0
    assert len(row['results']) == 0

def test_queue_executor_does_not_release_unowned_preexisting_reservation(tmp_path):
    from scripts.campaign6_verification.executor import run_case
    row = run_case(public_case('queue_full', worker={'active_jobs': 1}, controls={'cancel_queued_after_second': True}, policy={'max_queue': 1, 'max_retries': 1, 'timeout_seconds': 2}), tmp_path / 'case')
    assert row['first_observed_queued'] and row['second_queue_rejected']
    assert row['active_reservations'] == row['preexisting_reservations'] == {'public-development': 1}
    assert row['all_reservations_released']

@pytest.mark.parametrize('capacity,barrier,overlap', [(1, False, 1), (2, True, 2)])
def test_public_executor_parallel_overlap_is_observed_not_inferred(tmp_path, capacity, barrier, overlap):
    from scripts.campaign6_verification.executor import run_case
    case = public_case('parallel', worker={'concurrency': capacity}, controls={'parallel_requests': 2, 'barrier': barrier})
    case['request']['queue_seconds'] = 1
    row = run_case(case, tmp_path / 'case')
    assert len(row['results']) == 2
    assert row['max_active'] == overlap
    assert row['all_reservations_released'] and row['owned_providers_closed']

def test_public_executor_queued_release_obeys_original_waiter(tmp_path):
    from scripts.campaign6_verification.executor import run_case
    row = run_case(public_case('queued_release', worker={'active_jobs': 1}, controls={'release_preexisting_busy': True}), tmp_path / 'case')
    assert row['first_observed_queued']
    assert len(row['results']) == 1
    assert row['all_reservations_released'] and row['owned_providers_closed']

def test_explicit_numeric_gpu_zero_needs_identity_evidence(tmp_path):
    with environment(tmp_path) as env, resource_leaves(env, [resource_frame()]):
        worker = env.worker()
        worker['protocol'] = 'strata_openai'
        worker['startup']['gpu_device'] = 0
        receipt = env.transport.resources(worker)
        assert receipt['gpu_measurement'] is None and receipt['vram_free_bytes'] is None

def test_strata_single_gpu_without_explicit_device_positive_control(tmp_path):
    with environment(tmp_path) as env, resource_leaves(env, [resource_frame()]):
        worker = env.worker()
        worker['protocol'] = 'strata_openai'
        worker['startup'] = {}
        receipt = env.transport.resources(worker)
        assert receipt['gpu_measurement']['id'] == DEVICE
        assert receipt['vram_free_bytes'] == 4 * GIB

@pytest.mark.parametrize('loss', ['missing', 'malformed'])
def test_reintroduced_protected_source_does_not_reuse_revoked_observations(tmp_path, loss):
    with environment(tmp_path) as env:
        env.registry.observe('probe-worker', status='healthy', last_heartbeat=7000.0, model_id='controlled-protocol-model', context_reported=8192, ram_available_bytes=5 * GIB, vram_free_bytes=4 * GIB, resource_sampled_at=7000.0)
        bind_controlled_proof(env)
        if loss == 'missing':
            env.path.unlink()
        else:
            env.path.write_text('{ invalid protected deployment', encoding='utf-8')
        env.registry.reload()
        assert not env.registry.workers()
        env.data['nodes'][0]['username'] = 'reintroduced_account'
        replace(env)
        row = env.registry.snapshot()['workers'][0]
        assert row['status'] != 'healthy', 'A restored new source needs its own actual health observation.'
        assert row['ram_available_bytes'] is None and row['vram_free_bytes'] is None
        assert not row['max_context_verified']

def test_valid_identical_reload_preserves_current_source_observations(tmp_path):
    with environment(tmp_path) as env:
        env.registry.observe('probe-worker', status='healthy', last_heartbeat=7000.0, model_id='controlled-protocol-model', context_reported=8192, ram_available_bytes=5 * GIB, vram_free_bytes=4 * GIB, resource_sampled_at=7000.0)
        bind_controlled_proof(env)
        env.registry.reload()
        row = env.registry.snapshot()['workers'][0]
        assert row['status'] == 'healthy' and row['ram_available_bytes'] == 5 * GIB
        assert row['max_context_verified'] == 8192

@pytest.mark.parametrize('boundary', ['after_endpoint', 'after_auth_read'])
def test_auth_request_is_bound_to_one_protected_source_before_http(tmp_path, boundary):
    """Original pipeline, random in-memory tokens; no actual credential/network."""
    with environment(tmp_path) as env:
        env.data['workers'][0]['auth_config_file'] = '/run/owned/auth-source.json'
        replace(env)
        tokens = {'observer': uuid4().hex, 'replacement_account': uuid4().hex}
        reads, sends = ([], [])

        def withdraw():
            env.data['nodes'][0]['username'] = 'replacement_account'
            env.data['nodes'][0]['lan_ip'] = '' + '.'.join(('10', '42', '0', '12')) + ''
            replace(env)

        def endpoint(worker):
            if boundary == 'after_endpoint':
                withdraw()
            return 'http://127.0.0.1:17381'

        def secure_read(command, **kwargs):
            account = command[1]
            reads.append(account)
            if boundary == 'after_auth_read':
                withdraw()
            return SimpleNamespace(returncode=0, stdout=tokens[account].encode())

        class Client:

            def __init__(self, **kwargs):
                assert not kwargs['trust_env'] and (not kwargs['follow_redirects'])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def request(self, method, url, **kwargs):
                sends.append({'old_endpoint_used': url == 'http://127.0.0.1:17381/health', 'replacement_credential_forwarded': kwargs['headers'].get('Authorization') == 'Bearer ' + tokens['replacement_account']})
                return SimpleNamespace(is_redirect=False, content=b'{}', json=lambda: {}, raise_for_status=lambda: None)
        with patch.object(env.transport, 'endpoint', endpoint), patch.object(env.transport, '_address', lambda node: node['lan_ip']), patch.object(env.transport, '_ssh', lambda node, address, **kw: ['owned-secure-leaf', node['username'], address]), patch('hanni.compute.transport.subprocess.run', secure_read), patch('hanni.compute.transport.httpx.Client', Client):
            try:
                env.transport.request(env.worker(), 'GET', '/health')
            except ComputeError:
                pass
            assert sends == [], 'Changed authority between endpoint/auth boundaries must stop original HTTP dispatch.'

@pytest.mark.parametrize('withdraw_after_response', [False, True])
def test_request_result_requires_unchanged_source_with_stable_positive(tmp_path, withdraw_after_response):
    """A controlled response cannot survive source withdrawal; stable reads work."""
    with environment(tmp_path) as env:
        sends = []

        class Client:

            def __init__(self, **kwargs):
                assert not kwargs['trust_env'] and (not kwargs['follow_redirects'])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def request(self, method, url, **kwargs):
                sends.append({'method': method, 'path': '/health'})
                if withdraw_after_response:
                    env.data['nodes'][0]['username'] = 'changed_after_response'
                    replace(env)
                return SimpleNamespace(is_redirect=False, content=b'{"status":"healthy"}', json=lambda: {'status': 'healthy'}, raise_for_status=lambda: None)
        answer, error = (None, None)
        with patch.object(env.transport, 'endpoint', lambda worker: 'http://127.0.0.1:17383'), patch('hanni.compute.transport.httpx.Client', Client):
            try:
                answer = env.transport.request(env.worker(), 'GET', '/health')
            except ComputeError as exc:
                error = type(exc).__name__
        assert len(sends) == 1 and (not env.transport.clients)
        if withdraw_after_response:
            assert answer is None and error == 'ComputeError'
        else:
            assert answer == {'status': 'healthy'} and error is None

@pytest.mark.parametrize('scope,transition', [('global', True), ('worker', True), ('global', False), ('worker', False)])
def test_passive_request_flags_are_bound_without_banning_initially_disabled_health(tmp_path, scope, transition):
    """Original passive health is allowed; changed authorization must withdraw it."""
    with environment(tmp_path) as env:

        def disable():
            if scope == 'global':
                env.data['enabled'] = False
            else:
                env.data['workers'][0]['enabled'] = False
            replace(env)
        if not transition:
            disable()
        sends = []

        def endpoint(worker):
            if transition:
                disable()
            return 'http://127.0.0.1:17385'

        class Client:

            def __init__(self, **kwargs):
                assert not kwargs['trust_env'] and (not kwargs['follow_redirects'])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def request(self, method, url, **kwargs):
                sends.append({'method': method, 'path': '/health'})
                return SimpleNamespace(is_redirect=False, content=b'{"status":"healthy"}', json=lambda: {'status': 'healthy'}, raise_for_status=lambda: None)
        answer, error = (None, None)
        with patch.object(env.transport, 'endpoint', endpoint), patch('hanni.compute.transport.httpx.Client', Client):
            try:
                answer = env.transport.request(env.worker(), 'GET', '/health')
            except ComputeError as exc:
                error = type(exc).__name__
        assert not env.transport.clients
        if transition:
            assert not sends and answer is None and (error == 'ComputeError')
        else:
            assert len(sends) == 1 and answer == {'status': 'healthy'} and (error is None)
