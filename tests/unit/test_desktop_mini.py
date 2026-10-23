"""Mini window boundaries and Windows accelerator semantics, without a desktop session."""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
ROOT = Path(__file__).resolve().parents[2]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
desktop = load('hanni_mini_desktop', 'desktop/main.py')
hotkey = load('hanni_mini_hotkey', 'desktop/hotkey.py')

def test_shortcut_conflict_retains_previous_registration_and_subsequent_change_releases_it():
    api = SimpleNamespace(RegisterHotKey=Mock(side_effect=[True, False, True]), UnregisterHotKey=Mock())
    keys = hotkey.HotkeyRegistration(api)
    first = keys.configure('Ctrl+Shift+Space')
    assert first['shortcut'] == 'Ctrl+Shift+Space' and first['error'] == ''
    first_id = keys.identifier
    conflict = keys.configure('Ctrl+Alt+Space')
    assert conflict['shortcut'] == 'Ctrl+Shift+Space' and 'in use' in conflict['error']
    api.UnregisterHotKey.assert_not_called()
    changed = keys.configure('Alt+Shift+Space')
    assert changed['shortcut'] == 'Alt+Shift+Space' and changed['error'] == ''
    api.UnregisterHotKey.assert_called_once_with(None, first_id)
    new_id = keys.identifier
    keys.close()
    assert api.UnregisterHotKey.call_args.args == (None, new_id)
    keys.close()
    assert api.UnregisterHotKey.call_count == 2

def test_default_shortcut_conflict_keeps_no_false_registered_state():
    api = SimpleNamespace(RegisterHotKey=Mock(return_value=False), UnregisterHotKey=Mock())
    keys = hotkey.HotkeyRegistration(api)
    result = keys.configure(hotkey.DEFAULT_SHORTCUT)
    assert result['shortcut'] is None and 'tray menu' in result['error']
    keys.close()
    api.UnregisterHotKey.assert_not_called()

def test_accelerators_use_norepeat_and_reject_unbounded_keyboard_configuration():
    api = SimpleNamespace(RegisterHotKey=Mock(return_value=True), UnregisterHotKey=Mock())
    keys = hotkey.HotkeyRegistration(api)
    for invalid in ['Win+L', 'A', '', 'Ctrl+Shift+Space; powershell.exe']:
        with pytest.raises(ValueError):
            keys.configure(invalid)
    api.RegisterHotKey.assert_not_called()
    for modifiers, _ in hotkey.SHORTCUTS.values():
        assert modifiers & 16384
    keys.configure(hotkey.DEFAULT_SHORTCUT)
    api.RegisterHotKey.reset_mock()
    keys.configure(hotkey.DEFAULT_SHORTCUT)
    api.RegisterHotKey.assert_not_called()

def app_fixture(tmp_path):
    session = SimpleNamespace(url=desktop.DEFAULT_URL, stop_owned=Mock())
    prefs = desktop.load_preferences(tmp_path / 'window.json')
    app = desktop.DesktopApp(session, tmp_path, 'HANNI OS', prefs)
    app.mini = SimpleNamespace(get_current_url=lambda: desktop.DEFAULT_URL + '/?view=mini', hide=Mock(), destroy=Mock(), on_top=False, native=None)
    app.hotkey = SimpleNamespace(status=lambda: {'shortcut': hotkey.DEFAULT_SHORTCUT, 'error': '', 'choices': list(hotkey.SHORTCUTS)}, configure=Mock(), stop=Mock())
    return app

def test_bridge_exposes_only_bounded_window_preferences_and_no_execution(tmp_path):
    app = app_fixture(tmp_path)
    bridge = desktop.MiniBridge(app)
    assert {name for name in dir(bridge) if not name.startswith('_')} == {'get_state', 'dismiss', 'expand', 'pin', 'configure_hotkey'}
    assert bridge.pin(True)['pinned'] is True
    assert app.mini.on_top is True
    stored = json.loads((tmp_path / 'window.json').read_text())
    assert stored['mini_pinned'] is True and 'token' not in stored
    with pytest.raises(ValueError):
        bridge.pin('true')
    with pytest.raises(ValueError):
        bridge.configure_hotkey('powershell.exe')
    app.hotkey.configure.assert_not_called()
    bridge.dismiss()
    app.mini.hide.assert_called_once()
    app.session.stop_owned.assert_not_called()

@pytest.mark.parametrize('url', ['http://example.com/?view=mini', desktop.DEFAULT_URL + '/#home', 'http://127.0.0.1:9999/?view=mini', desktop.DEFAULT_URL + '/?view=mini&command=run'])
def test_bridge_rejects_calls_outside_exact_mini_view(tmp_path, url):
    app = app_fixture(tmp_path)
    app.mini.get_current_url = lambda: url
    with pytest.raises(RuntimeError):
        desktop.MiniBridge(app).dismiss()
    app.mini.hide.assert_not_called()

def test_conflicting_preference_does_not_persist_as_active_shortcut(tmp_path):
    app = app_fixture(tmp_path)
    app.hotkey.configure.return_value = {**app.hotkey.status(), 'error': 'Shortcut in use.'}
    result = desktop.MiniBridge(app).configure_hotkey('Ctrl+Alt+Space')
    assert result['shortcut'] == hotkey.DEFAULT_SHORTCUT
    assert app.preferences['mini_shortcut'] == hotkey.DEFAULT_SHORTCUT
    assert not (tmp_path / 'window.json').exists()

def test_mini_close_dismisses_but_main_close_unregisters_and_destroys_secondary(tmp_path):
    app = app_fixture(tmp_path)
    assert app.mini_close_requested() is False
    app.session.stop_owned.assert_not_called()
    app.on_closed()
    app.hotkey.stop.assert_called_once()
    app.mini.destroy.assert_called_once()
    assert app.closed.is_set() and app.mini_close_requested() is True
    with pytest.raises(RuntimeError):
        desktop.MiniBridge(app).get_state()

def test_attach_identity_accepts_additional_real_screens_and_rejects_invalid_lists():
    contract = {'version': 1, 'transport': 'http-snapshots', 'features': {}, 'screens': ['home', 'chat', 'mission', 'cluster', 'settings', 'tasks', 'voice']}
    assert desktop.is_hanni(desktop.DEFAULT_URL, request=lambda *args: contract)
    for screens in [['chat'], ['home', 'chat', 'mission', 'cluster', {}], ['home', 'chat', 'mission', 'cluster', 'settings'] + ['x'] * 40]:
        assert not desktop.is_hanni(desktop.DEFAULT_URL, request=lambda *args: dict(contract, screens=screens))

def test_canceled_navigation_preserves_live_bridge_and_only_successful_local_navigation_injects():
    bridge = {'get_state': object()}
    original = dict(bridge)

    def reinject(sender, args):
        bridge.clear()
    sender = SimpleNamespace(Source=desktop.DEFAULT_URL + '/?view=mini')
    desktop.complete_local_navigation(sender, SimpleNamespace(IsSuccess=False), desktop.DEFAULT_URL, reinject)
    assert bridge == original
    desktop.complete_local_navigation(SimpleNamespace(Source='http://localhost:9123/foreign'), SimpleNamespace(IsSuccess=True), desktop.DEFAULT_URL, reinject)
    assert bridge == original
    desktop.complete_local_navigation(sender, SimpleNamespace(IsSuccess=True), desktop.DEFAULT_URL, reinject)
    assert bridge == {}

def test_shortcut_restores_visible_mini_from_other_foreground_window_and_dismisses_only_own_foreground(tmp_path, monkeypatch):
    app = app_fixture(tmp_path)
    app.mini.native = SimpleNamespace(Handle=SimpleNamespace(ToInt64=lambda: 101))
    foreground = Mock(return_value=202)
    monkeypatch.setattr(desktop.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(GetForegroundWindow=foreground)))
    app.mini_visible = True
    app.show_mini = Mock()
    app.dismiss_mini = Mock()
    app.toggle_mini()
    app.show_mini.assert_called_once()
    app.dismiss_mini.assert_not_called()
    foreground.return_value = 101
    app.toggle_mini()
    app.dismiss_mini.assert_called_once()
    app.preferences['mini_pinned'] = True
    app.toggle_mini()
    assert app.show_mini.call_count == 2

def test_pin_assignment_is_marshaled_onto_native_ui_thread(tmp_path, monkeypatch):
    app = app_fixture(tmp_path)
    pending = []
    app.mini.native = SimpleNamespace(Invoke=lambda action: pending.append(action))
    monkeypatch.setitem(sys.modules, 'System', SimpleNamespace(Action=lambda action: action))
    app.apply_mini_pin(True)
    assert app.mini.on_top is False
    assert len(pending) == 1
    pending.pop()()
    assert app.mini.on_top is True

def test_expand_uses_fixed_chat_route_and_restores_window_when_service_is_unavailable(tmp_path):
    app = app_fixture(tmp_path)
    app.window = SimpleNamespace(show=Mock(), restore=Mock(), evaluate_js=Mock())
    bridge = desktop.MiniBridge(app)
    bridge.expand()
    app.window.show.assert_called_once()
    app.window.restore.assert_called_once()
    app.window.evaluate_js.assert_not_called()
    app.loaded_url = True
    bridge.expand()
    app.window.evaluate_js.assert_called_once_with("window.location.hash = 'chat'")
    assert app.mini.hide.call_count == 2
