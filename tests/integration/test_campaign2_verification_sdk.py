"""Independent representative real SDK probes; all provider data is controlled."""
import json
from pathlib import Path
import time
import pytest
from hanni.mcp.host import McpHost
from hanni.core.identity import Actor
from hanni.core.shutdown import EmergencyStopActive, StopSource
from hanni.tools.base import ToolPermissionError, ToolValidationError, UnknownToolError, ToolError
from scripts.campaign2.mcp_harness import OwnedHub, eventually

@pytest.fixture(scope='module')
def owned_sdk(tmp_path_factory):
    hub = OwnedHub(tmp_path_factory.mktemp('campaign2-independent-sdk'), 'stdio')
    yield hub
    hub.close()

def save_receipt(hub, label, **extra):
    out = hub.path / 'verification-receipts'
    out.mkdir(parents=True, exist_ok=True)
    record = {'scope': 'Actual original MCP Manager and installed SDK stdio transport; controlled local fixture data, no resident model.', 'initialization': hub.initialization, 'snapshot': hub.manager.snapshot(), 'events': hub.events(), 'base_count': hub.base_count, **extra}
    (out / f'{label}.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')

def test_genuinely_discovered_read_has_real_transport_input_output_and_correlation(owned_sdk):
    hub = owned_sdk
    before = len(hub.calls())
    source = hub.tool('quartz.inspect_flux_band')
    result = hub.call('quartz.inspect_flux_band', {'calibration': 'BQ-04'})
    assert result.ok
    assert result.data['structured_content'] == {'calibration': 'BQ-04', 'band': 'broad', 'intensity': 0.18}
    assert len(hub.calls()) == before + 1
    assert hub.calls()[-1]['arguments'] == {'calibration': 'BQ-04'}
    assert result.data['correlation']['capability_id'] == source['internal_id']
    assert result.data['correlation']['definition_hash'] == source['definition_hash']
    save_receipt(hub, 'discovered-read', result=result.to_dict(), dispatch_count=1)

def test_nested_arguments_bad_boolean_never_reach_actual_sdk(owned_sdk):
    hub = owned_sdk
    before = len(hub.calls())
    with pytest.raises(ToolValidationError):
        hub.call('prism.decode_profile', {'profile': {'enabled': 1, 'channels': ['green'], 'label': None}})
    assert len(hub.calls()) == before
    result = hub.call('prism.decode_profile', {'profile': {'enabled': False, 'channels': ['green'], 'label': None}})
    assert result.ok and result.data['structured_content']['profile']['enabled'] is False
    save_receipt(hub, 'nested-validation', result=result.to_dict(), rejected_transport_calls=0)

def test_actual_sdk_disabled_adapter_withdraws_cached_handler_menu_alias_and_get(owned_sdk):
    hub = owned_sdk
    name = 'prism.echo_label'
    source = hub.tool(name)
    old = hub.registry.get(source['internal_id'])
    host = McpHost(hub.registry)
    cached = host._as_tool(old)
    assert hub.registry.capabilities.get(old.name)['id'] == old.name
    before = len(hub.calls())
    request = hub.request(name, {'label': 'independent-late-proof'})
    hub.manager.disable_tools(hub.server_id, [name])
    try:
        with pytest.raises(UnknownToolError):
            hub.registry.capabilities.get(old.name)
        with pytest.raises(UnknownToolError):
            hub.registry.execute(request)
        with pytest.raises(ToolPermissionError):
            old.handler(request.arguments, hub.registry.context, request)
        assert not host.call(cached, request.arguments)['ok']
        assert len(hub.calls()) == before
        save_receipt(hub, 'cached-withdrawal', disabled_id=old.name, postwithdrawal_transport_calls=0)
    finally:
        hub.approve([name])

def test_original_sdk_timeout_is_failure_and_bounded_explicit_recovery(tmp_path):
    with OwnedHub(tmp_path / 'independent-timeout', 'stdio') as hub:
        hub.change(delay=3.6)
        before = len(hub.calls())
        started = time.monotonic()
        try:
            with pytest.raises((TimeoutError, ToolError)):
                hub.registry.execute(hub.request('prism.defer_read'))
        finally:
            hub.change(delay=0)
        elapsed = time.monotonic() - started
        assert elapsed < 7 and len(hub.calls()) == before + 1
        failed_state = hub.snapshot()['state']
        if failed_state != 'connected':
            assert len(hub.registry.definitions()) == hub.base_count
            hub.connect()
        result = hub.call('prism.defer_read')
        assert result.ok and result.data['structured_content']['complete'] is True
        save_receipt(hub, 'timeout-recovery', timeout_is_failure=True, failed_state=failed_state, elapsed_seconds=elapsed, recovery_result=result.to_dict())

def test_original_sdk_safe_stop_withdraws_then_rejects_preexisting_request(tmp_path):
    with OwnedHub(tmp_path / 'independent-stop', 'stdio') as hub:
        request = hub.request('prism.read_alignment', {'axis': 'y'})
        cached = hub.registry.get(request.name)
        before = len(hub.calls())
        hub.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('campaign2-verifier'), reason='Owned isolated stop boundary.')
        with pytest.raises(UnknownToolError):
            hub.registry.execute(request)
        with pytest.raises((ToolPermissionError, EmergencyStopActive)):
            cached.handler(request.arguments, hub.registry.context, request)
        eventually(lambda: not hub.manager.connections)
        assert len(hub.registry.definitions()) == hub.base_count and len(hub.calls()) == before
        save_receipt(hub, 'stop-withdrawal', poststop_transport_calls=0, original_request_rejection='UnknownToolError')
