"""Public development goals and deterministic client; no sealed evaluation inputs."""
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.base import ToolPermissionError, ToolValidationError
from hanni.tools.registry import build_default_registry
from hanni.workflows.planner import WorkflowPlanner
from hanni.workflows.policy import WorkflowAuthority, definition_fingerprint, pin_application, validate_policy
from hanni.workflows.references import resolve, referenced_steps
from hanni.workflows.store import WorkflowStore
from hanni.workflows.types import WorkflowError, canonical_json, fingerprint
from tests.helpers import write_config_dir

class QueuedClient:

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return json.dumps(self.responses.pop(0))

@pytest.fixture
def host(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    return McpHost(build_default_registry(config), read_only=True)

def outline(description='Show CPU and RAM usage', *, kind='tool', dependencies=None):
    return {'summary': 'Inspect the requested current measurements.', 'unsupported_reason': None, 'steps': [{'step_id': 'measure', 'description': description, 'kind': kind, 'dependencies': dependencies or [], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/cpu_percent', 'expected': None}]}]}

def binding(name='system.stats', arguments=None):
    return {'unsupported_reason': None, 'steps': [{'step_id': 'measure', 'capability_id': name, 'arguments': arguments or {}}]}

def test_planner_uses_original_client_router_schema_and_never_executes(host, tmp_path, monkeypatch):
    monkeypatch.setattr(host.registry, 'execute', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('executed')))
    client = QueuedClient(outline(), binding())
    phases = []
    plan = WorkflowPlanner(host, client, observer=lambda *event: phases.append(event)).plan('Show CPU and RAM usage', mode='assisted', artifact_root=tmp_path / 'artifacts')
    step = plan['steps'][0]
    assert step['capability_id'] == 'system.stats'
    assert step['definition_hash'] == definition_fingerprint(host.registry.get('system.stats'))
    assert len(client.calls) == 2
    assert phases == [('plan_validation', {'stage': 'outline'}), ('plan_validation', {'stage': 'binding'})]
    assert all((call[1]['response_format']['type'] == 'json_schema' for call in client.calls))
    assert 'confirmed' not in plan and 'mode' not in plan

@pytest.mark.parametrize('extra', ['confirmed', 'actor_profile', 'scope', 'mode', 'approved'])
def test_model_cannot_supply_authority(host, tmp_path, extra):
    proposal = outline()
    proposal[extra] = True
    with pytest.raises(WorkflowError, match='invalid bounded'):
        WorkflowPlanner(host, QueuedClient(proposal)).plan('Public fixture goal', mode='assisted', artifact_root=tmp_path / 'artifacts')

def test_unrouted_invented_capability_is_rejected(host, tmp_path):
    with pytest.raises(WorkflowError, match='original routed menu'):
        WorkflowPlanner(host, QueuedClient(outline(), binding('invented.benchmark'))).plan('Show CPU and RAM usage', mode='assisted', artifact_root=tmp_path / 'artifacts')

def test_cycle_is_rejected_before_binding(host, tmp_path):
    proposal = outline()
    proposal['steps'][0]['dependencies'] = ['measure']
    client = QueuedClient(proposal)
    with pytest.raises(WorkflowError, match='cycle'):
        WorkflowPlanner(host, client).plan('Inspect fixture', mode='assisted', artifact_root=tmp_path)
    assert len(client.calls) == 1

def test_unsupported_work_is_blocked_not_replaced_with_shell(host, tmp_path):
    proposal = outline('Execute an arbitrary external benchmark command')
    proposal['unsupported_reason'] = 'No approved benchmark execution capability is registered.'
    with pytest.raises(WorkflowError, match='blocked'):
        WorkflowPlanner(host, QueuedClient(proposal)).plan('Execute benchmark', mode='assisted', artifact_root=tmp_path)

def test_analysis_requires_real_prerequisites_and_evidence_criteria(host, tmp_path):
    with pytest.raises(WorkflowError, match='Analysis requires'):
        WorkflowPlanner(host, QueuedClient(outline(kind='analysis'))).plan('Analyze observed data', mode='assisted', artifact_root=tmp_path)

def test_prepare_uses_original_sensitive_and_reserved_guards(host, tmp_path):
    credential = host._as_tool(host.registry.get('file.read'))
    with pytest.raises(ToolPermissionError):
        host.prepare_call(credential, {'path': str(tmp_path / 'credentials.json')})
    calendar = host._as_tool(host.registry.get('google_calendar.agenda'))
    with pytest.raises(ToolValidationError):
        host.prepare_call(calendar, {'time_min': '2030-01-01T00:00:00Z'})

def test_prepare_pins_absolute_path_and_fixed_values(host, tmp_path):
    tool = host._as_tool(host.registry.get('file.stat'), fixed_arguments={'path': str(tmp_path / 'notes.txt')})
    request = host.prepare_call(tool, {'path': 'elsewhere.txt'})
    assert request.arguments['path'] == str((tmp_path / 'notes.txt').resolve())
    assert request.confirmed is False

def test_artifact_preview_does_not_grant_execution_and_exact_scope_is_checked(host, tmp_path):
    root = tmp_path / 'artifacts'
    args = {'path': str(root / 'report.txt'), 'text': 'Actual isolated fixture content'}
    definition = host.registry.get('file.write')
    tool = host._as_tool(definition)
    request = host.prepare_call(tool, args, artifact_root=root)
    assert not host.call(tool, args)['ok']
    assert not Path(args['path']).exists()
    authority = WorkflowAuthority('owner', True, 'assisted', root, ('file.write',), definition_fingerprint(definition), fingerprint(request.arguments), (tmp_path,))
    wrong = replace(authority, argument_hash=fingerprint({'path': args['path'], 'text': 'other'}))
    assert not host.call(tool, args, workflow_authority=wrong)['ok']
    assert not Path(args['path']).exists()
    result = host.call(tool, args, workflow_authority=authority)
    assert result['ok'] and Path(args['path']).read_text() == args['text']

def test_personal_write_cannot_bypass_original_host_readonly_policy(host, tmp_path):
    definition = host.registry.get('file.write')
    args = {'path': str(tmp_path / 'personal.txt'), 'text': 'fixture'}
    authority = WorkflowAuthority('owner', True, 'assisted', tmp_path / 'artifacts', ('file.write',), definition_fingerprint(definition), fingerprint(args))
    result = host.call(host._as_tool(definition), args, workflow_authority=authority)
    assert not result['ok'] and (not Path(args['path']).exists())

def test_schema_or_implementation_change_invalidates_workflow_hash(host):
    definition = host.registry.get('system.stats')
    for changed in (replace(definition, schema_version=2), replace(definition, background_allowed=False), replace(definition, handler=lambda *args: None)):
        assert definition_fingerprint(changed) != definition_fingerprint(definition)

def test_typed_refs_reject_failed_unverified_or_undeclared_sources():
    ref = {'$ref': {'step_id': 'read', 'path': '/data/value', 'type': 'integer'}}
    assert referenced_steps({'value': ref}) == {'read'}
    completed = {'read': {'status': 'verified', 'verification': {'status': 'VERIFIED'}, 'result': {'data': {'value': 4}}}}
    assert resolve({'value': ref}, ['read'], completed) == {'value': 4}
    for state in ('failed', 'unverified', 'pending'):
        altered = {'read': dict(completed['read'], status=state)}
        with pytest.raises(WorkflowError):
            resolve(ref, ['read'], altered)
    with pytest.raises(WorkflowError):
        resolve(ref, [], completed)
    with pytest.raises(WorkflowError):
        resolve({'$ref': dict(ref['$ref'], type='string')}, ['read'], completed)
    with pytest.raises(WorkflowError):
        referenced_steps({'$ref': dict(ref['$ref'], type=[])})

def test_deep_and_cyclic_json_fail_safely():
    value = []
    value.append(value)
    with pytest.raises(WorkflowError, match='depth'):
        canonical_json(value)
    with pytest.raises(WorkflowError, match='element'):
        canonical_json([0] * 10001)

def test_crash_read_attempt_budget_and_backoff_are_durable(tmp_path):
    clock = [1800000000.0]
    store = WorkflowStore(tmp_path, clock=lambda: clock[0])
    try:
        lease = store.claim(str(uuid4()))
        record = store.create('Durable retry budget fixture', 'assisted')
        step = {'step_id': 'read', 'dependencies': [], 'definition_hash': 'hash'}
        record = store.save_plan(record['workflow_id'], 1, {'steps': [step]}, [step], lease=lease)
        record = store.update(record['workflow_id'], record['revision'], {'status': 'ready'})
        _, record = store.begin_invocation(record['workflow_id'], record['revision'], 'read', lease=lease, arguments={}, definition_hash='hash', write=False, retry_safe=True)
        clock[0] += 11
        lease = store.claim(str(uuid4()))
        store.recover(lease)
        record = store.get(record['workflow_id'])
        record = store.update(record['workflow_id'], record['revision'], {'status': 'ready'})
        with pytest.raises(WorkflowError, match='backoff'):
            store.begin_invocation(record['workflow_id'], record['revision'], 'read', lease=lease, arguments={}, definition_hash='hash', write=False, retry_safe=True)
        clock[0] += 2
        _, record = store.begin_invocation(record['workflow_id'], record['revision'], 'read', lease=lease, arguments={}, definition_hash='hash', write=False, retry_safe=True)
        clock[0] += 11
        lease = store.claim(str(uuid4()))
        store.recover(lease)
        assert store.steps(record['workflow_id'])[0]['attempts'] == 2
        assert store.get(record['workflow_id'])['status'] == 'blocked'
        assert store.steps(record['workflow_id'])[0]['status'] == 'blocked'
    finally:
        store.close()

@pytest.mark.parametrize('app', ['generated.cmd', 'C:\\fixture\\generated.cmd', 'powershell', 'notepad.exe argument', 'terminal'])
def test_autonomous_shell_open_is_blocked_before_execution(host, tmp_path, app):
    with pytest.raises(WorkflowError, match='Workflow application'):
        validate_policy(host.registry.get('app.open'), {'app': app}, mode='assisted', artifact_root=tmp_path / 'artifacts')

def test_artifacts_cannot_generate_scripts(host, tmp_path):
    with pytest.raises(WorkflowError, match='not executable'):
        validate_policy(host.registry.get('file.write'), {'path': str(tmp_path / 'artifacts' / 'generated.cmd'), 'text': 'echo fixture'}, mode='assisted', artifact_root=tmp_path / 'artifacts')

def test_application_preview_pins_protected_binary_and_fixed_context(host, tmp_path, monkeypatch):
    from hanni.tools import windows
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(windows, '_find_start_menu_shortcut', lambda _: None)
    try:
        target = pin_application('notepad')
    except WorkflowError:
        pytest.skip('Protected Windows Notepad binary is not installed on this test platform.')
    allowed = McpHost(host.registry, read_only=True, allowed_actions=('app.open',))
    tool = allowed._as_tool(host.registry.get('app.open'), fixed_arguments={'app': target})
    request = allowed.prepare_call(tool, {'app': 'powershell'})
    assert request.arguments['app'] == target
    assert Path(target).is_absolute() and Path(target).name.casefold() == 'notepad.exe'
    validate_policy(host.registry.get('app.open'), request.arguments, mode='assisted', artifact_root=tmp_path / 'artifacts')
