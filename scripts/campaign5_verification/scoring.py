"""Independent model task scoring, outside execution and routing authority.

This module never reads private inputs/oracles at import and never executes model
code. Its caller supplies a frozen case, separate oracle and recorded raw result.
Scoring is post-run only; it must not be passed as an inference validator.
"""
from __future__ import annotations
import ast
from collections import Counter
import json
import math
import re
import jsonschema

def strict_json(value):

    def invalid(constant):
        raise ValueError('Non-finite JSON constants are not accepted.')
    if not isinstance(value, str) or len(value.encode()) > 262144:
        raise ValueError('Missing or oversized original model text.')

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON keys are not accepted.')
            result[key] = item
        return result
    return json.loads(value, parse_constant=invalid, object_pairs_hook=unique)

def equivalent(observed, expected, *, tolerance=0):
    """Bool is never numeric; object keys and list order remain meaningful."""
    if isinstance(expected, bool) or isinstance(observed, bool):
        return type(observed) is type(expected) and observed == expected
    if expected is None or observed is None:
        return observed is expected
    if isinstance(expected, (int, float)):
        if type(observed) not in (int, float):
            return False
        try:
            return math.isfinite(observed) and math.isfinite(expected) and (abs(observed - expected) <= tolerance)
        except OverflowError:
            return type(observed) is int and type(expected) is int and (observed == expected)
    if isinstance(expected, dict):
        return isinstance(observed, dict) and observed.keys() == expected.keys() and all((equivalent(observed[key], value, tolerance=tolerance) for key, value in expected.items()))
    if isinstance(expected, list):
        return isinstance(observed, list) and len(observed) == len(expected) and all((equivalent(a, b, tolerance=tolerance) for a, b in zip(observed, expected)))
    return type(observed) is type(expected) and observed == expected

def _ast(line):
    if not isinstance(line, str) or len(line.encode()) > 4096:
        raise ValueError('Invalid bounded replacement line.')
    parsed = ast.parse(line.strip(), mode='exec')
    if len(list(ast.walk(parsed))) > 256:
        raise ValueError('Replacement line exceeds bounded AST size.')
    return ast.dump(parsed, include_attributes=False)

def _message(result):
    """Accept explicit original response shapes; never reinterpret text as a call."""
    if isinstance(result, str):
        return {'content': result, 'tool_calls': []}
    if not isinstance(result, dict):
        raise ValueError('Original result shape is unavailable.')
    if 'choices' in result:
        return result['choices'][0]['message']
    if 'text' in result:
        return {'content': result['text'], 'tool_calls': result.get('tool_calls') or []}
    if 'content' in result or 'tool_calls' in result:
        return result
    raise ValueError('Original result shape is unavailable.')

def native_tool_score(case, expected, result):
    message = _message(result)
    calls = message.get('tool_calls') or []
    if not isinstance(calls, (list, tuple)):
        raise ValueError('Malformed actual tool calls.')
    menu = {t['function']['name']: t['function']['parameters'] for t in case['tools']}
    name_valid = True
    schemas_valid = True
    arguments_match = True
    prepared = []
    for raw in calls:
        if not isinstance(raw, dict):
            raise ValueError('Recorded original tool call must be structured.')
        function = raw.get('function', raw)
        name = function.get('name')
        arguments = function.get('arguments')
        if isinstance(arguments, str):
            try:
                arguments = strict_json(arguments)
            except (ValueError, json.JSONDecodeError):
                schemas_valid = False
                arguments = None
        if name not in menu:
            name_valid = False
            schemas_valid = False
        else:
            try:
                jsonschema.Draft202012Validator(menu[name]).validate(arguments)
            except (jsonschema.ValidationError, jsonschema.SchemaError):
                schemas_valid = False
        arguments_match = arguments_match and isinstance(arguments, dict) and all((key in arguments and equivalent(arguments[key], value) for key, value in expected.get('arguments_subset', {}).items()))
        prepared.append({'name': name, 'arguments': arguments})
    count_valid = len(calls) == expected['calls'] and len(calls) <= 1
    selected_name = len(calls) == 1 and prepared[0]['name'] == expected.get('name') if expected['calls'] else not calls
    clarification = True
    if expected.get('clarification_required'):
        text = message.get('content')
        clarification = isinstance(text, str) and bool(text.strip()) and all((any((re.search('\\b' + re.escape(term) + '\\b', text.casefold()) for term in group)) for group in expected['clarification_groups']))
    checks = {'native_single_call_protocol': count_valid, 'offered_wire_names': name_valid, 'schema_valid': schemas_valid, 'selected_name_correct': selected_name, 'semantic_arguments_correct': arguments_match, 'clarification_evidence': clarification}
    return {'correct': all(checks.values()), 'checks': checks, 'actual_native_calls': len(calls)}

def score(case, oracle, result, *, actual_model_http_requests, outcome='returned'):
    """No live response means semantic correctness is null, never a canned pass."""
    if case['id'] != oracle['id'] or case['checker_id'] != oracle['checker_id']:
        raise ValueError('Input and independent oracle identifiers disagree.')
    record = {'id': case['id'], 'category': case['category'], 'checker_id': case['checker_id'], 'actual_model_http_requests': actual_model_http_requests, 'outcome': outcome, 'correct': None, 'schema_valid': None, 'unconditional_task_passed': False, 'evidence_scope': 'Post-run deterministic independent reference; no routing, fallback, profile or execution authority.'}
    if type(actual_model_http_requests) is not int or actual_model_http_requests < 0:
        raise ValueError('Actual HTTP request count must be observed nonnegative integer.')
    if actual_model_http_requests == 0:
        record['unmeasured_reason'] = 'No recorded actual generation HTTP; cannot score model correctness.'
        return record
    if result is None:
        record['unmeasured_reason'] = 'Raw response unavailable after an attempted generation; retain infrastructure/parser outcome separately.'
        return record
    parameters = oracle['checker_inputs']
    try:
        if case['checker_id'] == 'native_tool':
            judged = native_tool_score(case, parameters['expected'], result)
            record.update(judged)
            record['schema_valid'] = judged['checks']['schema_valid']
        else:
            content = _message(result).get('content')
            parsed = strict_json(content)
            schema = parameters.get('schema')
            if schema is not None:
                try:
                    jsonschema.Draft202012Validator(schema).validate(parsed)
                    record['schema_valid'] = True
                except jsonschema.ValidationError:
                    record['schema_valid'] = False
            if case['checker_id'] == 'python_line_ast':
                reference = parameters['references']['accepted_lines']
                record['correct'] = isinstance(parsed, dict) and set(parsed) == {'line'} and (_ast(parsed['line']) in {_ast(line) for line in reference})
                record['coding_scope'] = 'Canonical AST-equivalent reference patches only; model code is never executed.'
            elif case['checker_id'] in {'json_exact', 'json_numeric_tolerance'}:
                tolerance = parameters.get('references', {}).get('absolute_tolerance', 0) if parameters.get('references') else 0
                if case['checker_id'] == 'json_exact':
                    tolerance = 0
                if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance < 0:
                    raise ValueError('Invalid frozen numeric tolerance.')
                record['correct'] = equivalent(parsed, parameters['expected'], tolerance=tolerance)
            else:
                raise ValueError('Unsupported frozen checker.')
            if record['schema_valid'] is False:
                record['correct'] = False
        record['unconditional_task_passed'] = record['correct'] is True and outcome == 'returned'
    except (ValueError, TypeError, KeyError, IndexError, SyntaxError, jsonschema.SchemaError) as exc:
        record['correct'] = False
        record['evaluation_error_type'] = type(exc).__name__
        record['failure_scope'] = 'Malformed or noncanonical actual response; original parser status remains separately recorded.'
    return record

def summary(rows):
    observable = [r for r in rows if r['correct'] is not None]
    return {'planned_or_attempted': len(rows), 'semantic_response_eligible': len(observable), 'independently_correct': sum((r['correct'] is True for r in observable)), 'semantic_accuracy': sum((r['correct'] is True for r in observable)) / len(observable) if observable else None, 'unconditional_task_successes': sum((r['unconditional_task_passed'] for r in rows)), 'actual_model_http_requests': sum((r['actual_model_http_requests'] for r in rows)), 'unmeasured': sum((r['correct'] is None for r in rows)), 'outcomes': dict(Counter((r['outcome'] for r in rows)))}
