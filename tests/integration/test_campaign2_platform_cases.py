"""Original 72 platform handlers through controlled OS dependency boundaries."""
import os
import importlib
from pathlib import Path
import pytest
import psutil
from unittest.mock import patch
from hanni.config.loader import load_config
from hanni.tools.base import ToolRequest, ToolValidationError
from hanni.tools.registry import build_default_registry
from scripts.campaign2.platform_cases import case, definitions
from scripts.campaign2.platform_fixtures import MODULE_NAMES, Proxy, Function
ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS = definitions()

@pytest.fixture
def registry(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path / 'registry', env={})
    value = build_default_registry(config)
    yield value
    value.context.reliability.close()

def test_dynamic_platform_coverage_is_exhaustive(registry):
    actual = [definition for definition in registry.definitions() if definition.handler.__module__.rsplit('.', 1)[-1] in MODULE_NAMES]
    assert {definition.name for definition in DEFINITIONS} == {definition.name for definition in actual}
    assert len({definition.name for definition in DEFINITIONS}) == len(DEFINITIONS)
    assert {definition.handler.__module__.rsplit('.', 1)[-1] for definition in DEFINITIONS} == {'system', 'windows', 'apps', 'media', 'spotify', 'net', 'power', 'security', 'devices', 'uiextra', 'envtools'}

@pytest.mark.skipif(os.name != 'nt', reason='actual Windows handler and callback paths')
@pytest.mark.parametrize('definition', DEFINITIONS, ids=lambda definition: definition.name)
def test_original_platform_valid_semantics(registry, definition, tmp_path):
    original = registry.get(definition.name).handler
    scenario = case(definition, tmp_path / 'fixture')
    with scenario.deps(scenario.args, controlled=True):
        assert registry.get(definition.name).handler is original
        result = registry.execute(ToolRequest(definition.name, dict(scenario.args), confirmed=True, source='campaign2-platform-controlled'))
        errors = scenario.verify(result, scenario.args)
        assert not errors, errors
    assert registry.get(definition.name).handler is original

@pytest.mark.parametrize('definition', DEFINITIONS, ids=lambda definition: definition.name)
def test_unknown_argument_rejected_before_platform_entry(registry, definition, tmp_path):
    scenario = case(definition, tmp_path / 'fixture')
    with pytest.raises(ToolValidationError):
        registry.execute(ToolRequest(definition.name, {**scenario.args, 'campaign2_unknown_argument': True}, confirmed=True, source='campaign2-platform-invalid'))

@pytest.mark.skipif(os.name != 'nt', reason='actual Windows handler and callback paths')
@pytest.mark.parametrize('definition', DEFINITIONS, ids=lambda definition: definition.name)
def test_original_platform_dependency_unavailable(registry, definition, tmp_path):
    scenario = case(definition, tmp_path / 'fixture')
    with scenario.deps(scenario.args, unavailable=True):
        try:
            result = registry.execute(ToolRequest(definition.name, dict(scenario.args), confirmed=True, source='campaign2-platform-unavailable'))
        except (OSError, RuntimeError, LookupError, psutil.Error):
            return
        errors = scenario.verify(result, scenario.args)
        assert not errors, errors

@pytest.mark.skipif(os.name != 'nt', reason='controlled Windows API failure reproduction')
@pytest.mark.parametrize('name', ['spotify.focus', 'spotify.volume', 'audio.mute', 'audio.set_volume', 'display.brightness', 'power.set_plan', 'power.set_idle', 'ui.window_state', 'ui.minimize_all'])
def test_semantic_oracle_detects_silent_control_failure(registry, name, tmp_path):
    scenario = case(registry.get(name), tmp_path / 'fixture')
    with scenario.deps(scenario.args, controlled=True, noop=True):
        result = registry.execute(ToolRequest(name, dict(scenario.args), confirmed=True, source='campaign2-platform-silent-failure'))
        errors = scenario.verify(result, scenario.args)
        assert not result.ok, (name, result.to_dict())
        assert errors, (name, result.to_dict())

@pytest.mark.parametrize('name,key', [('security.defender', 'realtime_protection'), ('security.firewall', 'all_enabled'), ('security.pending_reboot', 'pending'), ('device.disk_health', 'available')])
def test_empty_security_or_health_provider_is_unknown_not_healthy(registry, name, key):
    module = importlib.import_module(registry.get(name).handler.__module__)
    with patch.object(module, 'run_powershell_json', lambda *a, **k: []):
        result = registry.execute(ToolRequest(name, source='campaign2-empty-diagnostic'))
    assert not result.ok
    assert result.data['available'] is False
    assert result.data[key] is (False if key == 'available' else None)
    assert 'unknown' in result.message.casefold() or 'unavailable' in result.message.casefold()
    assert 'all report healthy' not in result.message.casefold()
    assert 'all profiles enabled' not in result.message.casefold()

@pytest.mark.parametrize('name,present,plugged', [('system.battery', 'available', 'power_plugged'), ('power.battery_detail', 'present', 'plugged_in')])
def test_missing_battery_publishes_no_fabricated_measurements(registry, name, present, plugged):
    module = importlib.import_module(registry.get(name).handler.__module__)
    with patch.object(module, 'psutil', Proxy(psutil, sensors_battery=lambda: None)):
        result = registry.execute(ToolRequest(name, source='campaign2-no-battery'))
    assert not result.ok and result.data[present] is False
    assert result.data['percent'] is None and result.data[plugged] is None
    assert all((key in result.data for key in registry.get(name).output_schema))
    if name == 'power.battery_detail':
        assert result.data['minutes_remaining'] is None

@pytest.mark.skipif(os.name != 'nt', reason='Win32 previous visibility is not success')
def test_minimize_counts_observed_state_even_if_showwindow_returns_zero(registry, tmp_path):
    scenario = case(registry.get('ui.minimize_all'), tmp_path / 'fixture')
    with scenario.deps(scenario.args, controlled=True) as state:
        show = state.user32.ShowWindow

        def previous_hidden(*args):
            show(*args)
            return 0
        state.user32.ShowWindow = Function(previous_hidden)
        result = registry.execute(ToolRequest('ui.minimize_all', confirmed=True))
        assert result.ok and result.data['minimized'] == 2
        assert not scenario.verify(result, scenario.args)

@pytest.mark.parametrize('name,payload,scalar', [('security.defender', {'AMServiceEnabled': True}, 'realtime_protection'), ('security.firewall', [{'Name': 'Synthetic missing state'}], 'all_enabled'), ('security.pending_reboot', {'cbs': False, 'wu': False}, 'pending'), ('device.disk_health', [{'FriendlyName': 'Synthetic missing health', 'Size': 1024}], 'available')])
def test_incomplete_measurements_do_not_become_boolean_certainty(registry, name, payload, scalar):
    module = importlib.import_module(registry.get(name).handler.__module__)
    with patch.object(module, 'run_powershell_json', lambda *a, **k: payload):
        result = registry.execute(ToolRequest(name, source='campaign2-partial-diagnostic'))
    assert not result.ok and result.data['available'] is False
    assert result.data[scalar] is (False if scalar == 'available' else None)

@pytest.mark.parametrize('value', ['false', '0', 2, 1.0, [], {'unexpected': True}, None])
@pytest.mark.parametrize('name,scalar', [('security.defender', 'realtime_protection'), ('security.firewall', 'all_enabled'), ('security.pending_reboot', 'pending')])
def test_security_boolean_provider_types_are_not_coerced(registry, name, scalar, value):
    payload = {'RealTimeProtectionEnabled': value, 'AMServiceEnabled': value} if name == 'security.defender' else [{'Name': 'Synthetic', 'Enabled': value}] if name == 'security.firewall' else {'cbs': value, 'wu': value, 'rename': value}
    module = importlib.import_module(registry.get(name).handler.__module__)
    with patch.object(module, 'run_powershell_json', lambda *a, **k: payload):
        result = registry.execute(ToolRequest(name, source='campaign2-malformed-boolean'))
    assert not result.ok and result.data[scalar] is None and (result.data['available'] is False)

@pytest.mark.parametrize('value,expected', [(True, True), (False, False), (1, True), (0, False)])
@pytest.mark.parametrize('name,scalar', [('security.defender', 'realtime_protection'), ('security.firewall', 'all_enabled'), ('security.pending_reboot', 'pending')])
def test_security_native_booleans_and_numeric_enums_preserve_measurement(registry, name, scalar, value, expected):
    payload = {'RealTimeProtectionEnabled': value, 'AMServiceEnabled': value} if name == 'security.defender' else [{'Name': 'Synthetic', 'Enabled': value}] if name == 'security.firewall' else {'cbs': value, 'wu': value, 'rename': value}
    module = importlib.import_module(registry.get(name).handler.__module__)
    with patch.object(module, 'run_powershell_json', lambda *a, **k: payload):
        result = registry.execute(ToolRequest(name, source='campaign2-native-boolean'))
    assert result.ok and result.data[scalar] is expected and (result.data['available'] is True)
