"""Public input-only bridge for controlled original Systems integrations.

This is deliberately separate from the sealed development runner. It does not
attach a conversational controller, interpret an owner prompt, or grant a plan
from a turn's confirmed flag. Root owns the genuine controller/model path.
"""
from copy import deepcopy
from pathlib import Path
import time
from uuid import uuid4
from scripts.campaign10_verification.contracts import DIMENSIONS, validate_case
from .runner import ALIASES, run_case
OPERATIONS = {'memory': {'memory.retrieve', 'memory.correct', 'memory.delete', 'memory.reopen', 'memory.propose', 'memory.review', 'project.resolve', 'project.package', 'project.alias', 'project.remove_alias', 'project.workspace'}, 'project': {'memory.retrieve', 'memory.correct', 'memory.delete', 'memory.reopen', 'memory.propose', 'memory.review', 'project.resolve', 'project.package', 'project.alias', 'project.remove_alias', 'project.workspace'}, 'workflow': {'workflow.run'}, 'compute': {'compute.chat', 'compute.withdraw', 'compute.refresh'}, 'cluster': {'cluster.sample', 'cluster.snapshot'}, 'voice_text': {'voice_text.classify'}, 'voice_stop': {'voice_stop.run'}, 'voice_rate': {'voice_rate.run'}, 'screen': {'screen.awareness', 'screen.project', 'screen.invalid_image'}}
REQUIRED_ARGS = {'memory.retrieve': {'query'}, 'memory.correct': {'index', 'content'}, 'memory.delete': {'index'}, 'memory.propose': {'content'}, 'memory.review': {'decision'}, 'project.resolve': {'query'}, 'project.package': {'project'}, 'project.alias': {'project', 'alias'}, 'project.remove_alias': {'project', 'alias'}, 'compute.chat': {'categories'}, 'compute.withdraw': {'field', 'value'}, 'voice_text.classify': {'text'}}

def _unavailable(case, reason, *, category='NOT_IMPLEMENTED'):
    return {'id': case['id'], 'family': case['family'], 'evidence_categories': [category], 'observations': [], 'actions': [], 'harness_error': None, 'adapter_limitation': reason, 'original_service_calls': 0, 'original_adapter_invocations': 0}

def _preflight(case, root):
    fixture = case['fixtures']
    adapter = fixture.get('adapter')
    if adapter not in OPERATIONS:
        return 'An explicit supported fixture adapter is required; no default service or plan was inferred.'
    if not case['actions']:
        return 'Explicit service actions are required; user text is not a controlled action plan.'
    for action in case['actions']:
        if 'bind' in action:
            return 'Cross-action result binding is not implemented by this direct-service adapter.'
        operation = ALIASES.get(action['operation'], action['operation'])
        if operation not in OPERATIONS[adapter]:
            return 'Unsupported operation for the explicit fixture adapter: ' + operation
        if not REQUIRED_ARGS.get(operation, set()).issubset(action['args']):
            return 'Missing explicit original-service arguments for ' + operation
        if {'actor_profile', 'confirmed', 'scope'}.intersection(action['args']):
            return 'Action arguments cannot override the shared turn actor or create an execution scope.'
    if len({turn['actor_profile'] for turn in case['user_turns']}) != 1:
        return 'Mixed actors have no action-to-turn binding in this direct-service adapter.'
    if adapter != 'workflow':
        if case['user_turns'][0]['actor_profile'] != 'owner':
            return 'This direct-service interface has no non-owner actor API; no owner role was substituted.'
        return None
    if len(case['actions']) != 1 or case['actions'][0]['args']:
        return 'workflow.run accepts one explicit fixture plan, not an inferred or alternate action plan.'
    if not isinstance(fixture.get('goal'), str) or not fixture['goal'].strip():
        return 'An explicit original workflow goal is required.'
    if fixture['goal'] != case['user_turns'][0]['prompt']:
        return 'The controlled workflow goal must match the supplied owner turn exactly.'
    if case['user_turns'][0]['actor_profile'] != 'owner':
        return None
    if not isinstance(fixture.get('steps'), list) or not fixture['steps'] or fixture.get('mode') not in {'assisted', 'supervised'}:
        return 'Original workflow steps and mode are required; no outline, binding or mode was substituted.'
    for field in ('auto_approve', 'auto_start'):
        if field in fixture and type(fixture[field]) is not bool:
            return 'Controlled approval/start flags must be exact Booleans.'
    declared = {step.get('step_id'): step for step in fixture['steps'] if isinstance(step, dict)}
    for step in fixture['steps']:
        if not isinstance(step, dict) or step.get('capability_id') not in {'file.read', 'file.stat', 'file.write'}:
            return 'This controlled workflow fixture supports only isolated original file operations.'
        path = step.get('arguments', {}).get('path')
        if isinstance(path, dict):
            reference = path.get('$ref')
            source = declared.get(reference.get('step_id')) if isinstance(reference, dict) else None
            if set(path) != {'$ref'} or not isinstance(reference, dict) or set(reference) != {'step_id', 'path', 'type'} or (reference.get('path') != '/data/path') or (reference.get('type') != 'string') or (reference.get('step_id') not in step.get('dependencies', [])) or (not source) or (source.get('capability_id') not in {'file.stat', 'file.write'}):
                return 'An isolated workflow path reference must use a declared predecessor owned /data/path receipt.'
        elif isinstance(path, str):
            prefix = next((value for value in ('{root}/', '{artifact_root}/') if path.startswith(value)), None)
            if prefix is None:
                return 'Literal workflow sources must be below the disposable root or managed artifact root.'
            suffix = path[len(prefix):]
            owned = root if prefix == '{root}/' else root / 'workflow' / 'data' / 'workflows' / 'artifacts'
            target = (owned / suffix).resolve()
            if not target.is_relative_to(owned.resolve()) or target == owned.resolve():
                return 'A workflow literal path escapes its disposable source boundary.'
        else:
            return 'Workflow file arguments need an explicit owned path or typed predecessor reference.'
    return None

def _nonowner_workflow(case, root):
    from hanni.workflows.service import WorkflowService
    from hanni.workflows.types import WorkflowError
    actor = case['user_turns'][0]['actor_profile']
    service = WorkflowService(root / 'workflow-authority')
    before = service.store.list()
    try:
        try:
            result = service.mutate({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': case['fixtures']['goal'], 'mode': case['fixtures'].get('mode', 'assisted')}}, actor_profile=actor)
        except WorkflowError as error:
            observation = {'accepted': False, 'error_type': type(error).__name__, 'reason': str(error)}
        else:
            observation = {'accepted': True, 'result': result}
        after = service.store.list()
    finally:
        service.close()
    return {'id': case['id'], 'family': case['family'], 'harness_error': None, 'evidence_categories': ['ISOLATED_IMPLEMENTATION'], 'observations': [{'operation': 'workflow.goal.submit', 'data': observation, 'error': None}], 'original_service_calls': 1, 'original_adapter_invocations': 1, 'workflow_count_before': len(before), 'workflow_count_after': len(after), 'planner_calls': 0, 'tool_dispatches': 0, 'actor_path_original': True, 'authority_scope': 'Original WorkflowService.mutate owner gate, before controller availability or planning.'}

def execute_input(case, case_root):
    """Callable for verifier.run_input; consumes public inputs, never oracles.

    The verifier precreates case_root. A fresh contained child is used by the
    historical integration runner; existing state is never reused or deleted.
    """
    case = validate_case(case)
    started = time.perf_counter()
    parent = Path(case_root).resolve()
    if not parent.is_dir():
        raise ValueError('The shared adapter requires its precreated disposable case directory.')
    root = parent / 'services'
    if root.exists() or root.is_symlink():
        raise ValueError('Shared service storage must be fresh; no existing state may be reused.')
    limitation = _preflight(case, root)
    if limitation:
        receipt = _unavailable(case, limitation)
    elif case['fixtures']['adapter'] == 'workflow' and case['user_turns'][0]['actor_profile'] != 'owner':
        root.mkdir()
        receipt = _nonowner_workflow(case, root)
    else:
        controlled = deepcopy(case)
        if controlled['fixtures']['adapter'] == 'workflow':
            controlled['fixtures'].setdefault('auto_approve', False)
            controlled['fixtures'].setdefault('auto_start', False)
        receipt = run_case(controlled, root)
        receipt['original_adapter_invocations'] = 1
        receipt['original_service_calls'] = None
        receipt['authority_scope'] = 'Explicit controlled fixture review/start; original hashes, revision and gates retained.' if case['fixtures']['adapter'] == 'workflow' else 'Original persistence/component API; this is not a registry actor-authorization measurement.'
        if 'TEXT_ONLY' in receipt['evidence_categories']:
            receipt['evidence_categories'].remove('TEXT_ONLY')
            receipt['audio_measurement_scope'] = 'TEXT_ONLY; no microphone, ASR, VAD or playback.'
        if receipt.get('harness_error'):
            receipt['evidence_categories'].append('NOT_RUN')
    receipt.update(mode='CONTROLLED_ORIGINAL_CONTRACT', request_path_original=False, actual_generated=False, actual_model_calls=0, real_model_requests=0, real_provider_requests=0, real_remote_calls=0, physical_audio_calls=0, user_turns_observed=deepcopy(case['user_turns']), controller_attached=False, model_intent='NOT_MEASURED', model_tool_selection='NOT_MEASURED', model_final_response='NOT_MEASURED', dimensions={key: {'status': 'NOT_MEASURED', 'reason': 'Raw controlled service evidence; independent prospective scoring required.'} for key in DIMENSIONS}, duration_ms=(time.perf_counter() - started) * 1000, disposable_service_root=str(root))
    receipt.setdefault('actions', receipt.get('observations', []))
    return receipt
