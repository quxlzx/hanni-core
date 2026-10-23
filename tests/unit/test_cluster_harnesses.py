"""Controlled cluster/model seams; these tests do not prove live deployment."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from hanni.compute.harnesses import SandboxJobs, digest, manifests, network_policy, validate_deployment, validate_task
from hanni.config.loader import load_config
from hanni.tools.base import ConfirmationRequired, ToolRequest
from hanni.tools.registry import build_default_registry
from tests.helpers import write_config_dir

def deployment():
    return {'version': 1, 'enabled': True, 'context': 'hanni-k3s', 'namespace': 'hanni-sandbox', 'runtime_class': 'gvisor', 'image': 'local/hanni@sha256:' + '1' * 64, 'node_selector': {'hanni.ai/worker-class': 'cpu', 'hanni.ai/sandbox-enabled': 'true'}, 'gateway_url': 'http://' + '.'.join(('10', '42', '0', '3')) + ':8765/api/sandbox/v1', 'storage_claim': 'projects', 'authorized_projects': ['sample'], 'models': {'manager': 'flash', 'coder': 'swift', 'editor': 'mellum', 'researcher': 'nex'}, 'deadline_seconds': 300}

def task():
    return {'task_id': 'run-one', 'project_id': 'sample', 'goal': 'Improve the supplied math program', 'roles': ['manager'], 'files': {'main.py': 'print(7)\n'}, 'checks': [['python', 'main.py']]}

@pytest.fixture
def jobs(tmp_path):
    value = SandboxJobs(tmp_path, admission=Mock())
    value.root.mkdir()
    (value.root / 'deployment.json').write_text(json.dumps(deployment()))
    return value

@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/host', 'a\\b', '.env', 'a/../b', 'a//b'])
def test_snapshot_traversal_and_credentials_rejected(name):
    value = task()
    value['files'] = {name: 'plain'}
    with pytest.raises(ValueError):
        validate_task(value)

@pytest.mark.parametrize('change', [lambda d: d.update(runtime_class='runc'), lambda d: d.update(image='local/latest'), lambda d: d.update(gateway_url='https://example.com:443/api/sandbox/v1'), lambda d: d.update(gateway_url='http://127.0.0.1:8765/api/sandbox/v1'), lambda d: d.update(node_selector={'hanni.ai/worker-class': 'gpu'}), lambda d: d.update(deadline_seconds=3600), lambda d: d.update(authorized_projects=[])])
def test_unbounded_or_public_deployment_rejected(change):
    value = deployment()
    change(value)
    with pytest.raises(ValueError):
        validate_deployment(value)

def test_job_is_cpu_only_scoped_nonroot_and_has_no_retry_or_host_mount():
    preview = manifests(deployment(), task())
    job = preview['objects'][1]
    spec = job['spec']['template']['spec']
    container = spec['containers'][0]
    assert spec['runtimeClassName'] == 'gvisor' and spec['automountServiceAccountToken'] is False
    assert spec['securityContext']['runAsNonRoot'] and container['securityContext']['readOnlyRootFilesystem']
    assert job['spec']['backoffLimit'] == 0 and job['spec']['podReplacementPolicy'] == 'Failed'
    assert not any(('hostPath' in v for v in spec['volumes']))
    assert 'nvidia.com/gpu' not in container['resources']['limits']
    assert container['resources']['requests']['memory'] == container['resources']['limits']['memory']
    mounts = container['volumeMounts']
    assert next((m for m in mounts if m['mountPath'] == '/snapshot'))['readOnly']
    assert next((m for m in mounts if m['mountPath'] == '/results'))['subPath'] == 'projects/sample/results/run-one'
    policy = network_policy(deployment())['spec']
    assert policy['ingress'] == [] and policy['egress'][0]['to'] == [{'ipBlock': {'cidr': '' + '.'.join(('10', '42', '0', '3')) + '/32'}}]

def test_project_scope_and_credentials_cannot_be_model_granted():
    value = task()
    value['project_id'] = 'other'
    with pytest.raises(ValueError):
        manifests(deployment(), value)
    value = task()
    value['files']['main.py'] = 'api_key = "secret-value"'
    with pytest.raises(ValueError):
        validate_task(value)

def test_coding_tasks_need_owner_checks_that_exist_in_approved_snapshot():
    value = task()
    value['roles'] = ['coder']
    with pytest.raises(ValueError, match='immutable'):
        validate_task(value)
    value['check_files'] = ['missing.py']
    with pytest.raises(ValueError, match='exact'):
        validate_task(value)
    value['files']['test_math.py'] = 'assert 3+4==7'
    value['check_files'] = ['test_math.py']
    assert validate_task(value)['check_files'] == ['test_math.py']

def test_disabled_preview_works_but_submission_has_no_external_effect(jobs):
    value = deployment()
    value['enabled'] = False
    (jobs.root / 'deployment.json').write_text(json.dumps(value))
    preview = jobs.preview(task())
    jobs._command = Mock()
    with pytest.raises(ValueError, match='disabled'):
        jobs.submit(task(), preview['binding'])
    jobs._command.assert_not_called()

def test_changed_preview_blocks_before_effect(jobs):
    preview = jobs.preview(task())
    value = task()
    value['goal'] = 'A changed goal'
    jobs._command = Mock()
    with pytest.raises(ValueError, match='changed'):
        jobs.submit(value, preview['binding'])
    jobs._command.assert_not_called()

def test_uncertain_write_not_repeated_after_restart(jobs):
    preview = jobs.preview(task())
    jobs._sandbox_evidence = Mock()
    jobs._command = Mock(side_effect=TimeoutError('ack lost'))
    first = jobs.submit(task(), preview['binding'])
    assert first['state'] == 'uncertain' and (not first['task_complete'])
    restored = SandboxJobs(jobs.root.parent, admission=Mock())
    restored._sandbox_evidence = Mock()
    restored._command = Mock()
    second = restored.submit(task(), preview['binding'])
    assert second['duplicate_suppressed'] and second['state'] == 'uncertain'
    restored._command.assert_not_called()

def test_acknowledged_job_never_claims_goal_completion(jobs):
    preview = jobs.preview(task())
    jobs._sandbox_evidence = Mock()
    reply = {'metadata': {'uid': 'unique', 'annotations': {'hanni/task-binding': preview['binding']}}, 'status': {'succeeded': 1}}
    jobs._command = Mock(side_effect=['{}', json.dumps(reply), json.dumps(reply)])
    result = jobs.submit(task(), preview['binding'])
    assert result['state'] == 'submitted' and (not result['task_complete'])
    assert jobs.inspect('run-one')['task_complete'] is False

def test_cancel_uses_uid_precondition_and_revokes_gateway_scope(jobs):
    jobs.inspect = Mock(return_value={'uid': 'unique'})
    with jobs._connect() as db:
        db.execute('INSERT INTO leases VALUES(?,?,?,?,?,?)', ('hash', 'run-one', 9999999999, 20, '{}', 'binding'))
    jobs._command = Mock(return_value='{}')
    with pytest.raises(ValueError):
        jobs.cancel('run-one', 'wrong')
    jobs._command.assert_not_called()
    assert jobs.cancel('run-one', 'unique')['state'] == 'cancel_requested'
    args, body = jobs._command.call_args.args[1:]
    assert '--raw=/apis/batch/v1/namespaces/hanni-sandbox/jobs/hanni-run-one' in args
    assert json.loads(body)['preconditions']['uid'] == 'unique'
    with jobs._connect() as db:
        assert db.execute('SELECT count(*) FROM leases').fetchone()[0] == 0

def test_missing_isolation_stops_before_create(jobs):
    preview = jobs.preview(task())
    jobs._command = Mock(return_value=json.dumps({'metadata': {'labels': {}}}))
    with pytest.raises(ValueError, match='Pod Security'):
        jobs.submit(task(), preview['binding'])
    assert len(jobs._command.call_args_list) == 1

@pytest.mark.parametrize('failure', ['extra-egress', 'no-ready-workers', 'unbound-storage'])
def test_cluster_checks_reach_and_block_actual_boundary_before_write(jobs, failure):
    policy = network_policy(deployment())

    def query(dep, args, payload=None):
        assert args[0] == 'get'
        kind = args[1]
        if kind == 'namespace':
            return json.dumps({'metadata': {'labels': {'pod-security.kubernetes.io/enforce': 'restricted'}}})
        if kind == 'runtimeclass':
            return '{"handler":"runsc"}'
        if kind == 'pvc':
            return json.dumps({'status': {'phase': 'Pending' if failure == 'unbound-storage' else 'Bound'}, 'spec': {'accessModes': ['ReadWriteMany']}})
        if kind == 'nodes':
            return json.dumps({'items': [] if failure == 'no-ready-workers' else [{'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
        if kind == 'networkpolicy':
            return json.dumps(policy if len(args) > 4 else {'items': [policy, policy] if failure == 'extra-egress' else [policy]})
        return '{"items":[]}'
    jobs._command = Mock(side_effect=query)
    with pytest.raises(ValueError):
        jobs.submit(task(), jobs.preview(task())['binding'])
    assert all((call.args[1][0] == 'get' for call in jobs._command.call_args_list))
    reached = [call.args[1][1] for call in jobs._command.call_args_list]
    assert {'extra-egress': 'networkpolicy', 'no-ready-workers': 'nodes', 'unbound-storage': 'pvc'}[failure] in reached

def test_unknown_job_cannot_be_read_or_cancelled(jobs):
    jobs._command = Mock()
    with pytest.raises(ValueError):
        jobs.inspect('unowned')
    jobs._command.assert_not_called()

def lease(jobs, token):
    with jobs._connect() as db:
        db.execute('INSERT INTO jobs VALUES(?,?,?,?)', ('run-one', 'binding', 'submitted', 'unique'))
        db.execute('INSERT INTO leases VALUES(?,?,?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), 'run-one', 9999999999, 2, '{"manager":"flash"}', digest(deployment())))

def test_gateway_uses_original_router_fixed_endpoint_no_fallback_and_budget(jobs):
    token = 'scoped-secret-value-123456789'
    lease(jobs, token)
    engine = Mock()
    engine.select.return_value = {'endpoint': {'model_id': 'flash'}}
    engine.execute.return_value = 'Advisory plan'
    guard = Mock()
    result = jobs.gateway(token, {'model': 'flash', 'messages': [{'role': 'user', 'content': 'small task'}]}, engine=engine, guard=guard)
    assert result['choices'][0]['message']['content'] == 'Advisory plan'
    options = engine.execute.call_args.kwargs
    assert options['endpoint_id'] == 'worker:wonyoung-strata' and options['max_fallbacks'] == 0
    assert options['request'].privacy_categories == frozenset({'project', 'conversation', 'sensitive'})
    assert options['max_tokens'] == 2048 and guard.call_count >= 2

@pytest.mark.parametrize('payload', [{'model': 'unapproved', 'messages': []}, {'model': 'flash', 'messages': [], 'tools': []}, {'model': 'flash', 'messages': [], 'max_tokens': 10000}])
def test_gateway_rejects_scope_expansion_before_inference(jobs, payload):
    token = 'scoped-secret-value-123456789'
    lease(jobs, token)
    engine = Mock()
    with pytest.raises(ValueError):
        jobs.gateway(token, payload, engine=engine, guard=Mock())
    engine.execute.assert_not_called()

def test_gateway_revocation_and_changed_config_prevent_inference(jobs):
    token = 'scoped-secret-value-123456789'
    lease(jobs, token)
    engine = Mock()
    value = deployment()
    value['deadline_seconds'] = 301
    (jobs.root / 'deployment.json').write_text(json.dumps(value))
    with pytest.raises(ValueError, match='changed'):
        jobs.gateway(token, {'model': 'flash', 'messages': []}, engine=engine, guard=Mock())
    engine.execute.assert_not_called()

def test_gateway_exhaustion_has_no_third_model_call(jobs):
    token = 'scoped-secret-value-123456789'
    lease(jobs, token)
    engine = Mock()
    engine.select.return_value = {'endpoint': {'model_id': 'flash'}}
    engine.execute.return_value = 'advisory'
    payload = {'model': 'flash', 'messages': [{'role': 'user', 'content': 'bounded'}]}
    for _ in range(2):
        jobs.gateway(token, payload, engine=engine, guard=Mock())
    with pytest.raises(ValueError, match='exhausted'):
        jobs.gateway(token, payload, engine=engine, guard=Mock())
    assert engine.execute.call_count == 2

def test_original_registry_confirmation_boundary_is_reached(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    directory = config.paths.data_dir / 'cluster-harnesses'
    directory.mkdir(parents=True)
    (directory / 'deployment.json').write_text(json.dumps(deployment()))
    registry = build_default_registry(config)
    assert len([d for d in registry.definitions() if d.name.startswith('cluster.task_')]) == 6
    with pytest.raises(ConfirmationRequired):
        registry.execute(ToolRequest('cluster.task_submit', {'task': task(), 'preview_binding': 'unreviewed'}))
    assert not (directory / 'jobs.sqlite3').exists()

def test_default_registry_has_no_new_harness_menu(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    assert not any((d.name.startswith('cluster.task_') for d in registry.definitions()))

def test_emergency_stop_revokes_all_scopes_before_remote_cleanup(jobs):
    token = 'scoped-secret-value-123456789'
    lease(jobs, token)
    jobs.cancel = Mock(side_effect=TimeoutError('cluster unavailable'))
    outcomes = jobs.stop_all()
    assert outcomes[0]['state'] == 'cancel_uncertain'
    with jobs._connect() as db:
        assert db.execute('SELECT count(*) FROM leases').fetchone()[0] == 0

def test_cleanup_never_deletes_an_active_job(jobs):
    jobs.inspect = Mock(return_value={'uid': 'unique', 'job_status': {'active': 1}})
    jobs._command = Mock()
    with pytest.raises(ValueError, match='terminal'):
        jobs.cleanup('run-one', 'unique')
    jobs._command.assert_not_called()

def test_result_hash_and_persistence_are_independent_of_job_completion(jobs):
    jobs.inspect = Mock(return_value={'uid': 'unique'})
    content = 'print(7)\n'
    receipt = {'task_id': 'run-one', 'task_complete': False, 'artifacts': {'main.py': {'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest()}}}
    jobs._command = Mock(return_value='HANNI_RESULT ' + json.dumps(receipt))
    result = jobs.result('run-one')
    assert result['applied_to_owner_project'] is False and result['task_complete'] is False
    with jobs._connect() as db:
        assert db.execute('SELECT uid FROM results').fetchone()[0] == 'unique'
    receipt['artifacts']['main.py']['sha256'] = '0' * 64
    jobs._command.return_value = 'HANNI_RESULT ' + json.dumps(receipt)
    with pytest.raises(ValueError, match='checksum'):
        jobs.result('run-one')

def test_finished_sandbox_cannot_self_assert_completed_goal(jobs):
    jobs.inspect = Mock(return_value={'uid': 'unique'})
    jobs._command = Mock(return_value='HANNI_RESULT ' + json.dumps({'task_id': 'run-one', 'task_complete': True, 'artifacts': {}}))
    with pytest.raises(ValueError, match='malformed'):
        jobs.result('run-one')
