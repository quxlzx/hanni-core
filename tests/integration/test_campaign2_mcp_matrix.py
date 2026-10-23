"""All eight newly discovered tools retain original gates over both real SDK transports."""
from copy import deepcopy
import pytest
from jsonschema import validate
from hanni.mcp.host import McpHost
from hanni.tools.base import ConfirmationRequired, ToolError, ToolPermissionError, ToolValidationError, UnknownToolError
from scripts.campaign2.mcp_contracts import CLASSIFICATIONS, INVALID, QUERIES, TOOLS, VALID
from scripts.campaign2.mcp_harness import OwnedHub, assert_schema_preserved
NAMES = [row['name'] for row in TOOLS]

@pytest.fixture(scope='module', params=['stdio', 'streamable_http'])
def matrix(request, tmp_path_factory):
    hub = OwnedHub(tmp_path_factory.mktemp('campaign2-mcp-matrix'), request.param)
    yield hub
    hub.capture('all-eight-matrix')
    hub.close()

def test_all_discovery_contracts_and_exact_classifications(matrix):
    assert matrix.initialization['serverInfo']['name'] == 'Campaign 2 owned SDK fixture'
    assert matrix.initialization['protocolVersion']
    assert matrix.initialization['capabilities']['tools']['listChanged']
    assert [row['original_name'] for row in matrix.snapshot()['tools']] == NAMES
    assert [row['cursor'] for row in matrix.events() if row['event'] == 'list'][:3] == [0, 3, 6]
    assert_schema_preserved(matrix)
    assert len(matrix.registry.definitions()) == matrix.base_count + 8
    for row in matrix.snapshot()['tools']:
        assert row['classification'] == CLASSIFICATIONS[row['original_name']]
        assert row['available'] and row['enabled'] and row['valid']
    erased = matrix.registry.get(matrix.tool('prism.erase_record')['internal_id'])
    assert erased.risk_level == erased.permission_level == 3
    assert erased.requires_confirmation_if is not None and erased.side_effect == 'destructive'

@pytest.mark.parametrize('name', NAMES)
def test_valid_original_registry_call_and_structured_output(matrix, name):
    before = len(matrix.calls())
    result = matrix.call(name)
    assert result.ok, result.to_dict()
    row = matrix.tool(name)
    validate(result.data['structured_content'], row['output_schema'])
    correlation = result.data['correlation']
    assert correlation['original_name'] == name
    assert correlation['definition_hash'] == row['definition_hash']
    assert correlation['capability_id'] == row['internal_id']
    assert correlation['correlation_id'].startswith('campaign2-')
    assert matrix.calls()[-1]['name'] == name
    assert len(matrix.calls()) == before + (2 if name == 'prism.erase_record' else 1)
    assert result.data['is_error'] is False

@pytest.mark.parametrize('name', NAMES)
def test_invalid_arguments_never_reach_sdk(matrix, name):
    before = len(matrix.calls())
    with pytest.raises(ToolValidationError):
        matrix.registry.execute(matrix.request(name, INVALID[name], confirmed=True))
    assert len(matrix.calls()) == before

@pytest.mark.parametrize('name', NAMES)
def test_required_arguments_never_reach_sdk(matrix, name):
    before = len(matrix.calls())
    with pytest.raises(ToolValidationError):
        matrix.registry.execute(matrix.request(name, {}, confirmed=True))
    assert len(matrix.calls()) == before

@pytest.mark.parametrize('name', NAMES)
def test_original_permission_profile_and_confirmation(matrix, name):
    before = len(matrix.calls())
    with pytest.raises(ToolPermissionError):
        matrix.registry.execute(matrix.request(name, actor_profile='campaign2-unrecognized-profile', confirmed=True))
    if CLASSIFICATIONS[name] != 'read_only':
        with pytest.raises(ConfirmationRequired):
            matrix.registry.execute(matrix.request(name, confirmed=False))
    assert len(matrix.calls()) == before

@pytest.mark.parametrize('name', NAMES)
def test_missing_connection_withdraws_live_and_cached_execution(matrix, name):
    row = matrix.tool(name)
    cached = matrix.registry.get(row['internal_id'])
    request = matrix.request(name, confirmed=True)
    before = len(matrix.calls())
    matrix.manager.disconnect(matrix.server_id)
    try:
        with pytest.raises(UnknownToolError):
            matrix.registry.execute(request)
        with pytest.raises(ToolPermissionError):
            cached.handler(request.arguments, matrix.registry.context, request)
        assert len(matrix.calls()) == before
    finally:
        matrix.connect()
    assert matrix.registry.get(row['internal_id']).external_definition_hash == row['definition_hash']

@pytest.mark.parametrize('name', NAMES)
def test_invalid_advertised_output_never_reports_success(matrix, name):
    matrix.change(invalid_output=True)
    try:
        with pytest.raises(ToolError):
            matrix.registry.execute(matrix.request(name, confirmed=True))
    finally:
        matrix.change(invalid_output=False)
    assert matrix.call(name).ok

@pytest.mark.parametrize('name', NAMES)
def test_natural_language_original_menu_preserves_policy(matrix, name):
    """Metadata retrieval only; real resident model selection belongs to Manager."""
    read = CLASSIFICATIONS[name] == 'read_only'
    host = McpHost(matrix.registry)
    decision = host.route(QUERIES[name])
    identities = {item.capability_id for item in decision.tools}
    target = matrix.tool(name)['internal_id']
    if read:
        assert target in identities, (name, decision)
        assert len(decision.tools) <= 8
    else:
        assert target not in identities
        explicit = host.route('Use Quartz Bench ' + name + ' now.')
        assert target in explicit.blocked_capabilities and explicit.status == 'blocked'

@pytest.mark.parametrize('name', NAMES)
def test_original_host_end_to_end_allowed_reads_and_denied_mutations(matrix, name):
    host = McpHost(matrix.registry)
    selected = host._as_tool(matrix.registry.get(matrix.tool(name)['internal_id']))
    before = len(matrix.calls())
    result = host.call(selected, deepcopy(VALID[name]))
    if CLASSIFICATIONS[name] == 'read_only':
        assert result['ok']
        validate(result['data']['structured_content'], matrix.tool(name)['output_schema'])
        assert len(matrix.calls()) == before + 1
    else:
        assert not result['ok'] and result['error']['code'] == 'PERMISSION_DENIED'
        assert len(matrix.calls()) == before
