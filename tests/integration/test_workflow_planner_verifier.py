"""Exposed independent planner/host/reference checks, not sealed goal evaluation.

All planner model replies are scripted. Original registry metadata, router,
host preparation and validation remain real. No handlers or model servers run.
"""
import json
from pathlib import Path
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.base import ToolValidationError
from hanni.tools.registry import build_default_registry
from hanni.workflows.planner import WorkflowPlanner
from hanni.workflows.references import resolve, referenced_steps
from hanni.workflows.policy import validate_policy
from hanni.workflows.types import WorkflowError

class QueuePlanClient:

    def __init__(self, *replies):
        self.replies = iter(replies)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({'messages': messages, 'kwargs': kwargs})
        return json.dumps(next(self.replies), allow_nan=False)

@pytest.fixture
def planning(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path / 'state', env={})
    registry = build_default_registry(config)
    host = McpHost(registry, read_only=True)
    try:
        yield (host, tmp_path / 'artifacts')
    finally:
        registry.context.reliability.close()

def outline(*steps):
    return {'summary': 'Public independent fixture plan', 'unsupported_reason': None, 'steps': list(steps)}

def step(identifier='clock', *, description='what time is it', dependencies=None, kind='tool', criteria=None):
    return {'step_id': identifier, 'description': description, 'kind': kind, 'dependencies': dependencies or [], 'required': True, 'criteria': criteria or [{'operator': 'present', 'path': '/data/utc_iso', 'expected': True}]}

def binding(*rows):
    return {'unsupported_reason': None, 'steps': list(rows)}

def bound(identifier='clock', capability='time.now', arguments=None):
    return {'step_id': identifier, 'capability_id': capability, 'arguments': arguments or {}}

def compile_plan(planning, first, second, *, goal='Check the clock', mode='assisted'):
    host, artifact_root = planning
    client = QueuePlanClient(first, second)
    planner = WorkflowPlanner(host, client)
    return (planner.plan(goal, mode=mode, artifact_root=artifact_root), client)

@pytest.mark.parametrize('field,value', [('confirmed', True), ('actor_profile', 'owner'), ('mode', 'background'), ('authority', {'approved': True})])
def test_outline_cannot_supply_authority_fields(planning, field, value):
    first = outline(step())
    first[field] = value
    with pytest.raises(WorkflowError):
        compile_plan(planning, first, binding(bound()))

def test_binding_cannot_supply_authority_fields(planning):
    row = bound()
    row['confirmed'] = True
    with pytest.raises(WorkflowError):
        compile_plan(planning, outline(step()), binding(row))

def test_authority_inside_tool_arguments_is_not_accepted(planning):
    with pytest.raises((WorkflowError, ToolValidationError)):
        compile_plan(planning, outline(step()), binding(bound(arguments={'confirmed': True})))

def test_nonregistered_tool_selection_is_not_executable_plan(planning):
    with pytest.raises(WorkflowError):
        compile_plan(planning, outline(step()), binding(bound(capability='fiction.execute')))

def test_explicit_unsupported_requirement_cannot_create_executable_plan(planning):
    first = outline(step())
    first['unsupported_reason'] = 'A required local capability is unavailable.'
    with pytest.raises(WorkflowError):
        compile_plan(planning, first, binding(bound()))

def test_binding_cannot_silently_drop_proposed_required_step(planning):
    first = outline(step(), step('second_clock', dependencies=['clock']))
    with pytest.raises(WorkflowError):
        compile_plan(planning, first, binding(bound()))

@pytest.mark.parametrize('dependencies', [['absent'], ['clock']])
def test_missing_or_self_dependency_blocks_plan(planning, dependencies):
    with pytest.raises(WorkflowError):
        compile_plan(planning, outline(step(dependencies=dependencies)), binding(bound()))

def test_analysis_cannot_use_nonempty_text_as_proof_of_conclusions(planning):
    first = outline(step(), step('analysis', description='Explain the measurements', kind='analysis', dependencies=['clock'], criteria=[{'operator': 'nonempty', 'path': '/text', 'expected': True}]))
    with pytest.raises(WorkflowError):
        compile_plan(planning, first, binding(bound(), bound('analysis', None, {'sources': ['clock']})))

def test_successful_compilation_executes_no_original_handler(planning):
    host, _ = planning
    from scripts.v3_review.fixtures import HandlerLedger
    ledger = HandlerLedger()
    ledger.observe(host.registry, 'time.now')
    plan, client = compile_plan(planning, outline(step()), binding(bound()))
    assert len(client.calls) == 2
    assert plan['steps'][0]['capability_id'] == 'time.now'
    assert ledger.entries('time.now') == 0
    assert all((call['kwargs']['response_format']['type'] == 'json_schema' for call in client.calls))

def test_fixed_calendar_values_win_without_model_account_widening(planning):
    host, _ = planning
    definition = host.registry.get('google_calendar.agenda')
    fixed = {'account': 'fixture-owner', 'time_min': '2030-04-08T00:00:00Z', 'time_max': '2030-04-09T00:00:00Z'}
    tool = host._as_tool(definition, fixed_arguments=fixed)
    request = host.prepare_call(tool, {'account': 'all', 'time_min': '1999-01-01T00:00:00Z'})
    assert request.arguments['account'] == fixed['account']
    assert request.arguments['time_min'] == fixed['time_min']
    assert request.arguments['time_max'] == fixed['time_max']
    assert request.confirmed is False

def test_unfixed_calendar_scope_cannot_be_injected(planning):
    host, _ = planning
    tool = host._as_tool(host.registry.get('google_calendar.agenda'))
    with pytest.raises(ToolValidationError):
        host.prepare_call(tool, {'time_min': '1999-01-01T00:00:00Z'})

def test_generated_script_artifact_cannot_be_opened_by_workflow_policy(planning):
    host, root = planning
    with pytest.raises(WorkflowError):
        validate_policy(host.registry.get('app.open'), {'app': str(root / 'generated.cmd')}, mode='background', artifact_root=root)

def result_reference(**changes):
    value = {'step_id': 'read', 'path': '/data/value', 'type': 'integer'}
    value.update(changes)
    return {'$ref': value}

@pytest.mark.parametrize('step_status,evidence_status,value', [('failed', 'VERIFIED', 1), ('unverified', 'UNVERIFIED', 1), ('verified', 'UNVERIFIED', 1), ('verified', 'VERIFIED', True)])
def test_refs_reject_failed_unverified_or_bool_as_integer(step_status, evidence_status, value):
    completed = {'read': {'status': step_status, 'verification': {'status': evidence_status}, 'result': {'data': {'value': value}}}}
    with pytest.raises(WorkflowError):
        resolve(result_reference(), ['read'], completed)

def test_malformed_reference_type_has_safe_error():
    with pytest.raises(WorkflowError):
        referenced_steps(result_reference(type=[]))

def test_verified_reference_does_not_expand_dependency_scope():
    completed = {'read': {'status': 'verified', 'verification': {'status': 'VERIFIED'}, 'result': {'data': {'value': 7}}}}
    with pytest.raises(WorkflowError):
        resolve(result_reference(), [], completed)
    assert resolve(result_reference(), ['read'], completed) == 7

def test_application_alias_cannot_authorize_existing_cwd_file(planning, tmp_path, monkeypatch):
    """Original Windows resolution prefers this local file over the safe alias."""
    host, root = planning
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'notepad').write_text('Isolated shadow target; never executed.', encoding='utf-8')
    with pytest.raises(WorkflowError):
        validate_policy(host.registry.get('app.open'), {'app': 'notepad'}, mode='assisted', artifact_root=root)

def test_application_alias_cannot_authorize_uninspected_shortcut(planning, tmp_path, monkeypatch):
    """A shortcut name does not establish its target or trusted executable identity."""
    from hanni.tools import windows
    host, root = planning
    shortcut = tmp_path / 'Notepad.lnk'
    shortcut.write_bytes(b'Not a runnable shortcut; isolated verifier fixture.')
    monkeypatch.setattr(windows, '_find_start_menu_shortcut', lambda app: shortcut)
    with pytest.raises(WorkflowError):
        validate_policy(host.registry.get('app.open'), {'app': 'notepad'}, mode='assisted', artifact_root=root)
