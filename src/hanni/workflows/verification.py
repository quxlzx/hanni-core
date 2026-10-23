"""Bounded acceptance checks over original results and cited prerequisite facts.

No tool executes here. A model's receipt or prose never upgrades original V2
verification. Analysis can verify quoted facts and deterministic calculations;
this scope does not establish historical causes or free-form conclusions.
"""
from __future__ import annotations

import json
import math

import jsonschema

from .references import pointer
from .types import WorkflowError, canonical_json, validate_json_bounds


REPORT_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['observations'],
    'properties': {'observations': {
        'type': 'array', 'minItems': 1, 'maxItems': 16,
        'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['operation', 'sources', 'value'],
            'properties': {
                'operation': {'enum': ['value', 'sum', 'difference', 'ratio', 'percentage', 'count']},
                'sources': {'type': 'array', 'minItems': 1, 'maxItems': 16,
                    'items': {'type': 'object', 'additionalProperties': False,
                        'required': ['step_id', 'path', 'json_path'],
                        'properties': {
                            'step_id': {'type': 'string', 'pattern': '^[A-Za-z0-9_-]{1,64}$'},
                            'path': {'type': 'string', 'maxLength': 512},
                            'json_path': {'type': ['string', 'null'], 'maxLength': 512},
                        }}},
                'value': {},
            },
        },
    }},
}


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkflowError('Structured evidence contains duplicate keys.')
        result[key] = value
    return result


def parse_evidence_json(text):
    """Finite, size/depth/node-bounded JSON; no tolerant parser or duplicate keys."""
    if not isinstance(text, str):
        raise WorkflowError('Structured evidence exceeds its text limit.')
    try:
        if len(text.encode('utf-8')) > 65536:
            raise WorkflowError('Structured evidence exceeds its text limit.')
        value = json.loads(text, object_pairs_hook=_strict_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               WorkflowError('Structured evidence must be finite JSON.')))
        canonical_json(value, maximum=65536)
        return value
    except (ValueError, RecursionError, TypeError, UnicodeError) as exc:
        raise WorkflowError('Structured evidence is not valid bounded JSON.') from exc


def _numeric(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _same(actual, expected):
    # bool is an int subclass in Python; JSON true must not equal numeric one.
    if _numeric(actual) and _numeric(expected):
        return actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(_same(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(_same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def render_report(report):
    """The saved report's text is computed from checked facts, never model prose."""
    canonical_json(report, maximum=65536)
    jsonschema.Draft202012Validator(REPORT_SCHEMA).validate(report)
    return json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)


def _verified_source(source_id, completed, visiting, checked):
    source = completed.get(source_id)
    if not isinstance(source, dict) or source.get('status') != 'verified':
        raise WorkflowError('Report citation requires a verified prerequisite.')
    evidence, result = source.get('verification'), source.get('result')
    if (not isinstance(evidence, dict) or evidence.get('status') != 'VERIFIED'
            or not isinstance(result, dict) or result.get('ok') is not True):
        raise WorkflowError('Prerequisite projection contradicts its original outcome.')
    if source_id in checked:
        return result
    if source.get('kind') == 'analysis':
        if source_id in visiting or len(visiting) >= 32:
            raise WorkflowError('Analysis evidence provenance is cyclic or too deep.')
        checks, data = evidence.get('checks'), result.get('data')
        if (evidence.get('scope') != 'cited_observations_and_calculations'
                or not isinstance(checks, dict) or checks.get('required_criteria_met') is not True
                or not isinstance(data, dict) or 'report' not in data or set(data) - {'report', 'text'}):
            raise WorkflowError('Analysis predecessor lacks checked factual scope.')
        visiting.add(source_id)
        try:
            verify_report(data['report'], source, completed, _visiting=visiting, _checked=checked)
            if 'text' in data and data['text'] != render_report(data['report']):
                raise WorkflowError('Analysis predecessor text contains unsupported claims.')
        finally:
            visiting.remove(source_id)
    else:
        original = result.get('verification')
        if (not isinstance(original, dict) or original.get('status') != 'VERIFIED'
                or str(source.get('capability_id', result.get('name', ''))).startswith('mcp.')
                or source.get('external_definition_hash')):
            raise WorkflowError('Original prerequisite evidence remains unverified.')
    checked.add(source_id)
    return result


def verify_report(report, step, completed, *, _visiting=None, _checked=None):
    """Check every report observation against verified, declared prerequisites."""
    canonical_json(report, maximum=65536)
    jsonschema.Draft202012Validator(REPORT_SCHEMA).validate(report)
    if not isinstance(step, dict) or not isinstance(completed, dict):
        raise WorkflowError('Analysis evidence records are invalid.')
    visiting = set() if _visiting is None else _visiting
    checked = set() if _checked is None else _checked
    declared = set(step.get('dependencies', []))
    requested = set((step.get('resolved_arguments') or step.get('arguments') or {}).get('sources', []))
    if not declared or not requested or not requested <= declared:
        raise WorkflowError('Analysis requires declared prerequisite evidence.')
    used = set()
    for observation in report['observations']:
        values = []
        for citation in observation['sources']:
            source_id = citation['step_id']
            if source_id not in requested:
                raise WorkflowError('Report citation requires an authorized verified prerequisite.')
            value = pointer(_verified_source(source_id, completed, visiting, checked), citation['path'])
            if citation['json_path'] is not None:
                value = pointer(parse_evidence_json(value), citation['json_path'])
            canonical_json(value, maximum=65536)
            values.append(value)
            used.add(source_id)
        operation = observation['operation']
        if operation in {'value', 'count'} and len(values) != 1:
            raise WorkflowError('This observation requires one cited value.')
        if operation in {'difference', 'ratio', 'percentage'} and len(values) != 2:
            raise WorkflowError('This calculation requires two cited values.')
        if operation == 'value':
            actual = values[0]
        elif operation == 'count':
            if not isinstance(values[0], (str, list, dict)):
                raise WorkflowError('Count requires cited text, an array or an object.')
            actual = len(values[0])
        else:
            if not all(_numeric(value) for value in values):
                raise WorkflowError('Calculation requires finite numeric evidence.')
            if operation == 'sum':
                actual = sum(values)
            elif operation == 'difference':
                actual = values[0] - values[1]
            else:
                if values[1] == 0:
                    raise WorkflowError('A cited zero denominator cannot support this calculation.')
                actual = values[0] / values[1] * (100 if operation == 'percentage' else 1)
            if not _numeric(actual):
                raise WorkflowError('Calculation exceeds finite numeric evidence.')
        if not _same(observation['value'], actual):
            raise WorkflowError('Report claim does not match its cited evidence.')
    if used != requested:
        raise WorkflowError('Report omitted requested prerequisite evidence.')
    return True


def _report_at(value):
    if isinstance(value, dict) and 'report' in value:
        return value['report']
    return value


def evaluate_step(step, result, completed):
    """Return conservative step evidence; no actions, follow-ups or authority.

    Analysis results contain data.report and optionally data.text generated by
    render_report. Required artifact reports must preserve a verified analysis
    predecessor's generated text when such an analysis is declared.
    """
    checks = {'execution_succeeded': False, 'original_result_verified': False,
              'required_criteria_met': False}
    evidence = {'status': 'UNVERIFIED', 'method': 'workflow_acceptance',
                'scope': 'required_step_criteria', 'independent': False,
                'checks': checks, 'criteria': []}
    try:
        canonical_json(result, maximum=262144)
        validate_json_bounds(step)
        if not isinstance(step, dict) or not isinstance(completed, dict):
            raise WorkflowError('Outcome evidence records are invalid.')
        if not isinstance(result, dict) or result.get('ok') is not True:
            return {**evidence, 'status': 'FAILED', 'reason': 'Step execution did not succeed.'}
        checks['execution_succeeded'] = True
        analysis = step.get('kind') == 'analysis'
        criteria = step.get('criteria')
        if not isinstance(criteria, list) or not 1 <= len(criteria) <= 8:
            raise WorkflowError('A required step needs bounded acceptance criteria.')
        if analysis:
            data = result.get('data')
            if not isinstance(data, dict) or set(data) - {'report', 'text'} or 'report' not in data:
                raise WorkflowError('Analysis returns structured cited facts only.')
            verify_report(data['report'], step, completed)
            if 'text' in data and data['text'] != render_report(data['report']):
                raise WorkflowError('Report text contains unsupported claims.')
            if not any(item.get('operator') == 'evidence_report' for item in criteria if isinstance(item, dict)):
                raise WorkflowError('Analysis requires deterministic evidence-report acceptance.')
            checks['original_result_verified'] = True
            evidence['scope'] = 'cited_observations_and_calculations'
        else:
            original = result.get('verification') or {}
            checks['original_result_verified'] = (
                isinstance(original, dict) and original.get('status') == 'VERIFIED'
                and not str(step.get('capability_id', '')).startswith('mcp.')
                and not step.get('external_definition_hash'))
            evidence['original_scope'] = original.get('scope') if isinstance(original, dict) else None
            evidence['independent'] = bool(original.get('independent')) if isinstance(original, dict) else False
        for criterion in criteria:
            if not isinstance(criterion, dict) or set(criterion) != {'operator', 'path', 'expected'}:
                raise WorkflowError('Acceptance criterion is invalid.')
            operation, path, expected = criterion['operator'], criterion['path'], criterion['expected']
            actual = pointer(result, path)
            if operation == 'present':
                passed = actual is not None
            elif operation == 'nonempty':
                passed = isinstance(actual, (str, list, dict)) and bool(actual)
            elif operation == 'equals':
                passed = _same(actual, expected)
            elif operation == 'count_equals':
                passed = isinstance(actual, (list, dict, str)) and type(expected) is int and len(actual) == expected
            elif operation in {'minimum', 'maximum'}:
                passed = _numeric(actual) and _numeric(expected) and (
                    actual >= expected if operation == 'minimum' else actual <= expected)
            elif operation == 'json_valid':
                parse_evidence_json(actual)
                passed = True
            elif operation == 'evidence_report':
                if not analysis:
                    raise WorkflowError('A tool receipt cannot prove report analysis.')
                verify_report(_report_at(actual), step, completed)
                passed = True
            else:
                raise WorkflowError('Acceptance operator is unsupported.')
            evidence['criteria'].append({'operator': operation, 'path': path, 'passed': bool(passed)})
            if not passed:
                raise WorkflowError('A required acceptance criterion failed.')
        if step.get('kind') == 'artifact':
            reports = [completed.get(key) for key in step.get('dependencies', [])]
            reports = [source for source in reports if isinstance(source, dict) and source.get('kind') == 'analysis']
            if reports:
                text = (step.get('resolved_arguments') or {}).get('text')
                matched = False
                for key in step.get('dependencies', []):
                    predecessor = completed.get(key)
                    if isinstance(predecessor, dict) and predecessor.get('kind') == 'analysis':
                        original = _verified_source(key, completed, set(), set())
                        matched |= isinstance(text, str) and text == (original.get('data') or {}).get('text')
                if not matched:
                    raise WorkflowError('Saved report does not preserve its verified analysis.')
        checks['required_criteria_met'] = True
        if checks['original_result_verified']:
            return {**evidence, 'status': 'VERIFIED'}
        return {**evidence, 'reason': 'Original outcome evidence is unverified.'}
    except (WorkflowError, jsonschema.ValidationError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        return {**evidence, 'reason': 'Required outcome evidence is absent, invalid or contradictory.'}
