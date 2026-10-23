"""Fresh independent original-registry authority, stale cache and file readback."""
from pathlib import Path
import pytest
from hanni.config.loader import load_config
from hanni.core.identity import Actor
from hanni.core.shutdown import EmergencyStopActive, StopSource
from hanni.mcp.adapter import result_contract, validate_json_arguments
from hanni.mcp.host import McpHost
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolDefinition, ToolPermissionError, ToolRequest, ToolResult, ToolValidationError, UnknownToolError, ConfirmationRequired, ToolError
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def registry(tmp_path):
    state = tmp_path / 'state'
    cfg = load_config(ROOT / 'config', data_dir=state, env={})
    registry = build_default_registry(cfg, data_dir=state)
    yield registry
    close_service(state)

def add_owned(registry, calls, *, write=False):
    name = 'independent.owned_record'

    def handler(args, context, request):
        calls.append({'args': dict(args), 'actor': request.actor_profile})
        return ToolResult(name, True, 'Campaign-owned observation.', {'value': args['value']})
    registry.register(ToolDefinition(name, 'Independent disposable observation.', 3 if write else 0, 3 if write else 0, {'value': int}, {'value': 'integer'}, handler, aliases=('independent specimen',), argument_constraints={'value': {'required': True, 'nullable': False}}, side_effect='destructive' if write else 'read'))
    return registry.get(name)

def test_removed_definition_invalidates_alias_contract_menu_and_original_dispatch(registry):
    calls = []
    definition = add_owned(registry, calls)
    api = registry.capabilities
    host = McpHost(registry)
    menu = host._as_tool(definition)
    assert api.resolve_id('independent specimen') == definition.name
    assert api.get(definition.name)['id'] == definition.name
    assert api.invoke({'id': definition.name, 'arguments': {'value': 4}})['ok']
    calls.clear()
    assert registry.unregister(definition.name, expected=definition)
    assert api.resolve_id('independent specimen') is None
    with pytest.raises(UnknownToolError):
        api.get(definition.name)
    with pytest.raises(UnknownToolError):
        registry.execute(ToolRequest(definition.name, {'value': 4}))
    assert not api.invoke({'id': definition.name, 'arguments': {'value': 4}})['ok']
    assert not host.call(menu, {'value': 4})['ok']
    assert calls == []

def test_stale_owner_unregister_cannot_remove_new_definition(registry):
    calls = []
    old = add_owned(registry, calls)
    assert registry.unregister(old.name, expected=old)
    new = add_owned(registry, calls)
    assert not registry.unregister(old.name, expected=old)
    assert registry.get(old.name) is new
    with pytest.raises(ToolPermissionError):
        registry.execute(ToolRequest(old.name, {'value': 9}, expected_definition=old))
    assert calls == []

@pytest.mark.parametrize('profile', ['everyone_else', 'independent_unknown_actor'])
def test_original_actor_gate_denies_before_handler(registry, profile):
    calls = []
    definition = add_owned(registry, calls)
    with pytest.raises(ToolPermissionError):
        registry.execute(ToolRequest(definition.name, {'value': 2}, actor_profile=profile, confirmed=True))
    assert calls == []

def test_model_payload_cannot_inject_confirmation_or_actor(registry):
    calls = []
    definition = add_owned(registry, calls, write=True)
    for key, value in [('confirmed', True), ('actor_profile', 'owner'), ('source', 'desktop-mcp-hub')]:
        out = registry.capabilities.invoke({'id': definition.name, 'arguments': {'value': 2}, key: value})
        assert not out['ok'] and out['error']['code'] == 'INVALID_ARGUMENTS'
    with pytest.raises(ConfirmationRequired):
        registry.execute(ToolRequest(definition.name, {'value': 2}))
    assert calls == []

def test_actual_safe_mode_blocks_original_before_handler(registry):
    calls = []
    definition = add_owned(registry, calls)
    registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('campaign2-verifier'))
    try:
        with pytest.raises(EmergencyStopActive):
            registry.execute(ToolRequest(definition.name, {'value': 2}))
        assert calls == []
    finally:
        registry.context.emergency_stop.clear(Actor.local('campaign2-verifier'))

def test_builtin_original_handlers_create_and_independently_read_owned_file(registry, tmp_path):
    file = tmp_path / 'independent.txt'
    contents = 'Violet instrument journal\n42\n'
    before = {definition.name: id(definition.handler) for definition in registry.definitions()}
    created = registry.execute(ToolRequest('file.write', {'path': str(file), 'text': contents}, confirmed=True))
    assert created.ok and file.read_text(encoding='utf8') == contents
    observed = registry.execute(ToolRequest('file.read', {'path': str(file)}))
    assert observed.ok and observed.data['text'] == contents
    import hashlib
    measured = registry.execute(ToolRequest('file.stat', {'path': str(file), 'hash': True}))
    assert measured.ok and measured.data['sha256'] == hashlib.sha256(file.read_bytes()).hexdigest()
    assert before == {definition.name: id(definition.handler) for definition in registry.definitions()}

def test_external_strict_schema_preserves_nullability_nested_boolean_and_arrays():
    schema = {'type': 'object', 'properties': {'samples': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 1}, 'profile': {'type': 'object', 'properties': {'enabled': {'type': 'boolean'}, 'label': {'type': ['string', 'null']}}, 'required': ['enabled', 'label'], 'additionalProperties': False}}, 'required': ['samples', 'profile'], 'additionalProperties': False}
    good = {'samples': [2.5], 'profile': {'enabled': True, 'label': None}}
    assert validate_json_arguments(schema, good) == good
    for bad in [{'samples': [True], 'profile': good['profile']}, {'samples': [], 'profile': good['profile']}, {'samples': [1], 'profile': {'enabled': 'yes', 'label': None}}, {'samples': [1], 'profile': {'enabled': True}}, {**good, 'confirmed': True}]:
        with pytest.raises(ToolValidationError):
            validate_json_arguments(schema, bad)

def test_external_output_schema_is_applied_to_structured_content():
    schema = {'type': 'object', 'properties': {'reading': {'type': 'integer'}}, 'required': ['reading'], 'additionalProperties': False}
    source = {'content': [{'type': 'text', 'text': 'controlled result'}], 'structuredContent': {'reading': 7}, 'isError': False}
    ok, message, out = result_contract(source, schema)
    assert ok is True
    assert out['structured_content'] == {'reading': 7}
    for changed in [{'reading': True}, {'other': 7}, {'reading': 7, 'extra': 8}]:
        with pytest.raises(ToolError):
            result_contract({**source, 'structuredContent': changed}, schema)

def test_external_error_never_requires_success_contract_or_reports_success():
    source = {'content': [{'type': 'text', 'text': 'controlled dependency unavailable'}], 'isError': True}
    ok, message, out = result_contract(source, {'type': 'object', 'required': ['success_value']})
    assert ok is False and out['is_error'] is True
