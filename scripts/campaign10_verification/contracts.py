"""Input-only contract and evidence checks; this module contains no holdout data."""
from copy import deepcopy
import math
from pathlib import Path
DIMENSIONS = ('intent', 'retrieved_context', 'tools', 'arguments', 'authorization', 'execution', 'outcome_verification', 'final_response', 'latency', 'recovery')
STATUSES = frozenset({'PASS', 'FAIL', 'BLOCKED', 'NOT_MEASURED', 'NOT_APPLICABLE'})
EVIDENCE = frozenset({'LIVE_READ_ONLY', 'LIVE_MODEL_ISOLATED_SERVICES', 'ISOLATED_IMPLEMENTATION', 'MOCK_DEPENDENCY', 'BLOCKED', 'NOT_IMPLEMENTED', 'NOT_RUN'})
FORBIDDEN = frozenset({'expected', 'expected_result', 'expected_answer', 'oracle', 'oracles', 'checker', 'checker_inputs', 'required_checks', 'acceptance', 'solution'})

def _native_null_criterion(value, path, workflow_fixture):
    return workflow_fixture and len(path) == 5 and (path[0:2] == ('fixtures', 'steps')) and (type(path[2]) is int) and (path[3] == 'criteria') and (type(path[4]) is int) and (set(value) == {'operator', 'path', 'expected'}) and (value['expected'] is None) and (value['operator'] in {'present', 'nonempty', 'json_valid', 'evidence_report'}) and isinstance(value['path'], str) and value['path'].startswith('/')

def reject_oracles(value, path=(), workflow_fixture=None):
    if workflow_fixture is None:
        workflow_fixture = isinstance(value, dict) and isinstance(value.get('fixtures'), dict) and (value['fixtures'].get('adapter') == 'workflow')
    if isinstance(value, dict):
        forbidden = FORBIDDEN.intersection(value)
        if 'expected' in forbidden and _native_null_criterion(value, path, workflow_fixture):
            forbidden = forbidden - {'expected'}
        if forbidden:
            raise ValueError('Oracles and expected answers are forbidden in execution input.')
        for key, item in value.items():
            reject_oracles(item, path + (key,), workflow_fixture)
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            reject_oracles(item, path + (index,), workflow_fixture)

def validate_case(case):
    reject_oracles(case)
    if not isinstance(case, dict):
        raise ValueError('Case must be an input object.')
    required = {'version', 'id', 'family', 'difficulty', 'description', 'user_turns', 'fixtures', 'actions'}
    if not required.issubset(case):
        raise ValueError('Missing shared input-envelope fields.')
    if case['version'] != 1 or isinstance(case['version'], bool):
        raise ValueError('Unsupported case version.')
    if any((not isinstance(case[k], str) or not case[k].strip() for k in ('id', 'family', 'description'))):
        raise ValueError('Identity, family and description must be nonempty text.')
    if case['difficulty'] not in {'easy', 'medium', 'hard'}:
        raise ValueError('Unknown difficulty.')
    if not isinstance(case['fixtures'], dict) or not isinstance(case['actions'], list):
        raise ValueError('Fixtures and actions have invalid types.')
    if not isinstance(case['user_turns'], list) or not case['user_turns']:
        raise ValueError('At least one user turn is required.')
    for turn in case['user_turns']:
        if not isinstance(turn, dict) or not isinstance(turn.get('prompt'), str) or (not turn['prompt'].strip()):
            raise ValueError('User turn needs an ordinary prompt.')
        if turn.get('actor_profile') not in {'owner', 'everyone_else'} or type(turn.get('confirmed')) is not bool:
            raise ValueError('Actor and exact Boolean authority are required.')
    for action in case['actions']:
        if not isinstance(action, dict) or not isinstance(action.get('operation'), str) or (not isinstance(action.get('args'), dict)):
            raise ValueError('Each action needs an operation and input-only arguments.')
    return deepcopy(case)

def contained_path(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError('Fixture paths must stay below their disposable case root.')
    return candidate

def json_pointer(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('Evidence citations must be JSON pointers.')
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value

def opaque_observation(value):
    """Preserve runtime-only receipt objects as labelled observations, never call them."""
    kind = type(value)
    return {'opaque_runtime_type': kind.__module__ + '.' + kind.__qualname__, 'observed_repr': repr(value), 'measurement': 'OPAQUE_RUNTIME_OBJECT_NOT_GRADED'}

def receipt_observation(value, ancestors=None):
    """Store complete raw receipts without executing opaque objects or hiding NaN."""
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else {'measurement': 'NONFINITE_NUMBER_NOT_GRADED', 'observed_repr': repr(value)}
    ancestors = set() if ancestors is None else ancestors
    if isinstance(value, (dict, list, tuple)):
        if id(value) in ancestors:
            return {'measurement': 'CYCLIC_RUNTIME_OBJECT_NOT_GRADED', 'observed_repr': repr(value)}
        branch = ancestors | {id(value)}
        if isinstance(value, dict):
            return {str(k): receipt_observation(v, branch) for k, v in value.items()}
        return [receipt_observation(v, branch) for v in value]
    return opaque_observation(value)

def normalize_receipt(case, raw):
    """Validate identity and retain raw evidence without manufacturing observations."""
    if not isinstance(raw, dict):
        raise ValueError('Adapter must return an actual receipt object.')
    if raw.get('id') not in {None, case['id']}:
        raise ValueError('Receipt identity mismatch.')
    result = deepcopy(raw)
    result['id'] = case['id']
    result['family'] = case['family']
    result['difficulty'] = case['difficulty']
    result.setdefault('evidence_categories', ['NOT_RUN'])
    if not isinstance(result['evidence_categories'], list) or not set(result['evidence_categories']).issubset(EVIDENCE):
        raise ValueError('Unknown or malformed evidence category.')
    result.setdefault('dimensions', {})
    for dimension in DIMENSIONS:
        row = result['dimensions'].setdefault(dimension, {'status': 'NOT_MEASURED', 'reason': 'No original evidence.'})
        if not isinstance(row, dict) or row.get('status') not in STATUSES:
            raise ValueError('Invalid dimension measurement status.')
    elapsed = result.get('duration_ms')
    if elapsed is not None and (type(elapsed) not in {int, float} or not math.isfinite(elapsed) or elapsed < 0):
        raise ValueError('Elapsed measurement must be finite and nonnegative.')
    return result

def scope_satisfied(required, receipt):
    categories = set(receipt.get('evidence_categories', ()))
    if categories.intersection({'BLOCKED', 'NOT_IMPLEMENTED', 'NOT_RUN'}):
        return False
    if required == 'live_model':
        return 'LIVE_MODEL_ISOLATED_SERVICES' in categories and type(receipt.get('actual_model_calls')) is int and (receipt['actual_model_calls'] > 0) and (receipt.get('actual_generated') is True) and (receipt.get('mock_model') is not True)
    if required == 'physical':
        return receipt.get('physical_supervision_verified') is True and receipt.get('physical_required_operations_verified') is True
    if required == 'live_read':
        return 'LIVE_READ_ONLY' in categories
    if required == 'mock_leaf_original':
        return bool(categories.intersection({'MOCK_DEPENDENCY', 'LIVE_READ_ONLY', 'LIVE_MODEL_ISOLATED_SERVICES'}))
    if required in {'isolated_original', 'software_original'}:
        return bool(categories.intersection({'ISOLATED_IMPLEMENTATION', 'MOCK_DEPENDENCY', 'LIVE_READ_ONLY', 'LIVE_MODEL_ISOLATED_SERVICES'}))
    return False
