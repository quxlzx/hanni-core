"""Post-execution checks against sealed mechanical expectations.

This module is never imported by the execution adapter. A contract result does
not establish natural-language understanding, a model decision or reply quality.
"""
from __future__ import annotations
from copy import deepcopy
import math
from .harness import DIMENSIONS

class MissingEvidence(LookupError):
    pass

def pointer(value, path):
    current = value
    for part in path.strip('/').split('/') if path.strip('/') else ():
        try:
            current = current[int(part)] if isinstance(current, list) else current[part]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MissingEvidence(path) from exc
    return current

def observation(name, actual, expected, passed, *, scope):
    return {'check': name, 'passed': bool(passed), 'observed': actual, 'expected': expected, 'scope': scope}

def score(case, oracle, raw):
    """Strict original-oracle contract score. No oracle correction or inference."""
    checks = []
    for check in oracle.get('checks', []):
        try:
            actual = pointer(raw, check['pointer'])
            if check['op'] == 'equal':
                passed = actual == check['value']
            elif check['op'] == 'contains':
                passed = check['value'] in actual
            elif check['op'] == 'length':
                actual = len(actual)
                passed = actual == check['value']
            else:
                raise ValueError('Unsupported sealed checker operation.')
            checks.append(observation(check['pointer'], actual, check['value'], passed, scope='Actual original implementation output; sealed expectation unchanged'))
        except (MissingEvidence, TypeError) as exc:
            checks.append(observation(check['pointer'], {'missing': str(exc)}, check['value'], False, scope='Required actual evidence is missing, not assumed successful'))
    effects = oracle.get('effects', {})
    before, after = (raw.get('files_before', {}), raw.get('files_after', {}))
    for key, value in effects.items():
        try:
            if key == 'sha256_matches_file':
                actual = pointer(raw, 'actions/' + value['action'] + '/result/data/sha256')
                expected = after[value['file']]['sha256']
                passed = actual == expected
            elif key == 'same_bytes':
                actual = [after[p] for p in value]
                expected = 'Equal full byte hashes and byte lengths'
                passed = len(actual) >= 2 and all((item == actual[0] for item in actual))
            elif key == 'same_bytes_pairs':
                actual = [[after[a], after[b]] for a, b in value]
                expected = 'Every original/extracted byte hash and length matches'
                passed = all((a == b for a, b in actual))
            elif key == 'no_tool_dispatch_prefix':
                actual = [e for a in raw.get('actions', {}).values() for e in a.get('handler_entries', []) if isinstance(e.get('tool'), str) and e['tool'].startswith(value)]
                expected = []
                passed = not actual
            elif key == 'equal_refs':
                actual = [pointer(raw.get('actions', {}), p) for p in value]
                expected = 'Equal original dynamically assigned values'
                passed = len(actual) >= 2 and all((item == actual[0] for item in actual))
            elif key == 'unchanged_files':
                actual = {p: {'before': before.get(p), 'after': after.get(p)} for p in value}
                expected = 'Every named file exists and retains its exact bytes'
                passed = all((before.get(p) is not None and before[p] == after.get(p) for p in value))
            elif key == 'absent_files':
                actual = {p: after.get(p) for p in value}
                expected = {p: None for p in value}
                passed = actual == expected
            elif key == 'mcp_calls':
                actual = len(raw.get('inert_mcp_provider_calls', []))
                expected = value
                passed = actual == expected
            else:
                raise ValueError('Unsupported sealed effect checker: ' + key)
            checks.append(observation(key, actual, expected, passed, scope='Named original implementation side effect, independent of reply text'))
        except (MissingEvidence, KeyError, TypeError) as exc:
            checks.append(observation(key, {'missing': str(exc)}, value, False, scope='Required side-effect evidence absent'))
    errors = [a.get('error') for a in raw.get('actions', {}).values() if a.get('error')]
    harness_errors = [e for e in errors if e['type'].startswith('HARNESS_')]
    if raw.get('mode') == 'HARNESS_ERROR' or raw.get('error'):
        harness_errors.append(raw.get('error') or {'type': 'HARNESS_ERROR', 'message': 'No original receipt'})
    passed = bool(checks) and all((c['passed'] for c in checks)) and (not harness_errors)
    dimensions = {d: {'status': 'NOT_MEASURED', 'scope': 'No actual semantic model grading is inferred from prescribed actions'} for d in DIMENSIONS}
    entered = [e for a in raw.get('actions', {}).values() for e in a.get('handler_entries', [])]
    dimensions['tools'] = {'status': 'PASS' if entered else 'NOT_MEASURED', 'scope': 'Original handler-entry provenance only; prescribed tool contracts, not model selection', 'observed': [e['tool'] for e in entered]}
    dimensions['arguments'] = {'status': 'PASS' if entered else 'NOT_MEASURED', 'scope': 'Original handler parsed argument receipts only; not model argument accuracy'}
    dimensions['authorization'] = {'status': 'PASS' if raw.get('audit') else 'NOT_MEASURED', 'scope': 'Original authorization/audit observed; denial and side effects remain individually checked'}
    dimensions['execution'] = {'status': 'FAIL' if harness_errors else 'PASS', 'scope': 'Original implementation invocation returned or raised; success is scored separately'}
    dimensions['outcome_verification'] = {'status': 'PASS' if passed else 'FAIL', 'scope': 'All immutable mechanical expectations including intended rejections'}
    elapsed = raw.get('elapsed_ms')
    dimensions['latency'] = {'status': 'PASS' if isinstance(elapsed, (int, float)) and (not isinstance(elapsed, bool)) and math.isfinite(elapsed) and (elapsed >= 0) else 'NOT_MEASURED', 'scope': 'Whole isolated case time; individual original action durations retained', 'milliseconds': elapsed}
    dimensions['recovery'] = {'status': ('PASS' if passed else 'FAIL') if oracle.get('recovery_required') else 'NOT_APPLICABLE', 'scope': 'Prospectively specified original state/readback recovery; no process-restart claim'}
    return {'id': case['id'], 'passed': passed, 'checks': checks, 'dimensions': dimensions, 'harness_errors': harness_errors, 'actual_generated': raw.get('actual_generated', False), 'model_call_count': raw.get('model_call_count', 0), 'semantic_model_accuracy': None, 'oracle_unchanged': True}

def live_readback_score(case, oracle, raw):
    """Exact applicable contract outputs mapped to genuine observed call IDs.

    Required unobserved actions fail the strict comparison. This is a development
    contract diagnostic, never a new oracle or a semantic-model accuracy score.
    Native desktop/MCP/Lab setup cannot be invented from the textual response.
    """
    view = deepcopy(raw)
    calls = raw.get('actual_registry_calls', [])
    used, aliases = (set(), {})
    for expected in case.get('actions', []):
        if expected.get('target') != 'registry':
            continue
        for index, observed in enumerate(calls):
            if index not in used and observed.get('name') == expected['name']:
                used.add(index)
                aliases[expected['id']] = {'result': observed.get('result'), 'error': observed.get('error'), 'arguments': observed.get('arguments'), 'handler_entries': []}
                break
    view['actions'] = aliases
    result = score(case, oracle, view)
    result['scope'] = 'Development diagnostic using unchanged mechanical checks and chronological exact-name actual call aliases; absent prescribed actions are missing evidence. This does not score model intent or natural-language final reply.'
    result['call_aliases'] = {key: {'result_observed': value['result'] is not None, 'error': value['error']} for key, value in aliases.items()}
    result['unmapped_actual_calls'] = [call for index, call in enumerate(calls) if index not in used]
    result['actual_generated'] = raw.get('actual_generated', False)
    result['model_call_count'] = raw.get('actual_model_calls', raw.get('model_call_count', 0))
    return result
