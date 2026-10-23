"""Bounded typed references to verified predecessor data, never instructions."""
import math
from .types import WorkflowError, canonical_json, identifier, validate_json_bounds


KINDS = {'string', 'integer', 'number', 'boolean', 'object', 'array', 'null'}


def reference(value):
    if not isinstance(value, dict) or '$ref' not in value:
        return None
    if set(value) != {'$ref'} or not isinstance(value['$ref'], dict):
        raise WorkflowError('A result reference must contain only its typed reference.')
    item = value['$ref']
    if set(item) != {'step_id', 'path', 'type'}:
        raise WorkflowError('A result reference requires step ID, JSON pointer and type.')
    identifier(item['step_id'])
    path = item['path']
    if (not isinstance(path, str) or len(path) > 512 or path and not path.startswith('/')
            or not isinstance(item['type'], str) or item['type'] not in KINDS):
        raise WorkflowError('Invalid typed result reference.')
    return item


def referenced_steps(value):
    validate_json_bounds(value)
    found, pending = set(), [value]
    while pending:
        item = pending.pop()
        ref = reference(item)
        if ref:
            found.add(ref['step_id'])
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return found


def pointer(value, path):
    if path == '':
        return value
    if not isinstance(path, str) or not path.startswith('/') or len(path) > 512:
        raise WorkflowError('Invalid evidence JSON pointer.')
    for part in path[1:].split('/'):
        # Reject invalid escaping instead of interpreting an ambiguous field.
        import re
        if re.search(r'~(?![01])', part):
            raise WorkflowError('Invalid evidence JSON pointer escape.')
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and str(int(part)) == part and int(part) < len(value):
            value = value[int(part)]
        else:
            raise WorkflowError('Prerequisite evidence field is unavailable.')
    return value


def matches_type(value, kind):
    # Check only the requested kind. A bounded JSON integer can be larger than
    # a float, and unrelated type checks must not attempt its float conversion.
    if kind == 'number':
        if type(value) not in (int, float):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    return {
        'string': isinstance(value, str), 'integer': type(value) is int,
        'boolean': type(value) is bool, 'object': isinstance(value, dict),
        'array': isinstance(value, list), 'null': value is None,
    }.get(kind, False)


def resolve(value, dependencies, completed):
    validate_json_bounds(value)
    def walk(item):
        ref = reference(item)
        if ref:
            if ref['step_id'] not in dependencies:
                raise WorkflowError('Result reference is outside the declared prerequisites.')
            source = completed.get(ref['step_id'])
            if not source or source.get('status') != 'verified':
                raise WorkflowError('Result reference requires a verified prerequisite.')
            evidence = source.get('verification') or {}
            if evidence.get('status') != 'VERIFIED':
                raise WorkflowError('Prerequisite result is not verified evidence.')
            result = pointer(source.get('result'), ref['path'])
            if not matches_type(result, ref['type']):
                raise WorkflowError('Prerequisite result type does not match the reference.')
            canonical_json(result)  # Recheck privacy/size before reuse in a later request.
            return result
        if isinstance(item, dict):
            return {key: walk(child) for key, child in item.items()}
        if isinstance(item, list):
            return [walk(child) for child in item]
        return item
    return walk(value)
