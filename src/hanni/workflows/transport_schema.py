"""Small generation grammar; original local schemas remain the authority.

llama.cpp expands bounded string/array repetitions into grammar rules. Nested
workflow bounds can exceed that compiler's rule budget before generation starts.
Only the response-format projection omits repetition constraints; token limits,
finite payload bounds and full original JSON-schema validation still apply.
"""
from copy import deepcopy

from .types import canonical_json


_LOCAL_REPETITION = frozenset({'minLength', 'maxLength', 'minItems', 'maxItems', 'pattern'})
_SCHEMA_VALUES = frozenset({'items', 'additionalProperties', 'additionalItems', 'contains',
                            'propertyNames', 'not', 'if', 'then', 'else',
                            'unevaluatedItems', 'unevaluatedProperties'})
_SCHEMA_MAPS = frozenset({'properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'})
_SCHEMA_LISTS = frozenset({'allOf', 'anyOf', 'oneOf', 'prefixItems'})
_JSON_TYPES = ('object', 'array', 'string', 'number', 'boolean', 'null')


def generation_schema(schema):
    """Copy schema nodes, retaining shape/type/enum and literal data unchanged.

    This does not project raw model/tool data or edit property/enum values whose
    names happen to match a schema constraint. Callers must validate responses
    against their original schema, never against this transport projection.
    """
    if not isinstance(schema, dict):
        return deepcopy(schema)
    projected = {}
    for key, value in schema.items():
        if key in _LOCAL_REPETITION:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            projected[key] = {name: generation_schema(child) for name, child in value.items()}
        elif key in _SCHEMA_LISTS and isinstance(value, list):
            projected[key] = [generation_schema(child) for child in value]
        elif key in _SCHEMA_VALUES:
            projected[key] = ([generation_schema(child) for child in value]
                              if isinstance(value, list) else generation_schema(value))
        else:
            projected[key] = deepcopy(value)
    # This runtime's converter treats {} as object-only, contrary to JSON
    # Schema. An explicit type union preserves an unconstrained JSON value
    # (criterion.expected/report.value) without changing its local schema.
    return projected if projected else {'type': list(_JSON_TYPES)}


def schema_messages(instructions, data, schema, *, maximum):
    """Expose the full local contract to the model and bound the entire context."""
    contract = canonical_json(schema, maximum=maximum, private=False)
    payload = canonical_json(data, maximum=maximum)
    messages = [
        {'role': 'system', 'content': instructions + '\nAuthoritative output JSON Schema:\n' + contract},
        {'role': 'user', 'content': payload},
    ]
    canonical_json(messages, maximum=maximum, private=False)
    return messages
