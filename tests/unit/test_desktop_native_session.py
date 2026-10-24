import json
from unittest.mock import Mock

import pytest

from tests.unit.test_desktop import desktop
from tests.test_stick import firstboot


def test_native_session_captures_child_identity_and_pins_only_its_token(tmp_path):
    child = Mock(pid=123)
    request = Mock(return_value={'epoch': 'owned', 'token': 'ephemeral-secret'})
    session = desktop.BackendSession(desktop.DEFAULT_URL, tmp_path, request=request)
    session.process = child
    session.ready_path = tmp_path / 'ready.json'
    session.ready_path.write_text(json.dumps({'pid': 456, 'parent_pid': 123, 'url': desktop.DEFAULT_URL, 'epoch': 'owned'}))
    assert session.capture_ready()
    assert session.owned_epoch == 'owned' and session.owned_token == 'ephemeral-secret'
    assert 'ephemeral-secret' not in session.ready_path.read_text()
    session.ready_path.write_text(json.dumps({'pid': 999, 'parent_pid': 888, 'url': desktop.DEFAULT_URL, 'epoch': 'owned'}))
    with pytest.raises(RuntimeError, match='ownership'): session.capture_ready()
    session.ready_path.write_text(json.dumps({'pid': 123, 'url': desktop.DEFAULT_URL, 'epoch': 'foreign'}))
    with pytest.raises(RuntimeError, match='identity'): session.capture_ready()


def test_closed_owner_blocks_spawn_and_stops_supervisor(monkeypatch):
    monkeypatch.setattr(firstboot, '_desktop_alive', lambda: False)
    spawn = Mock()
    monkeypatch.setattr(firstboot.subprocess, 'Popen', spawn)
    with pytest.raises(RuntimeError, match='owner application closed'):
        firstboot.spawn(['not-started'], 'not-created.log', {})
    spawn.assert_not_called()
    assert firstboot.supervise({'model': Mock()}) == 0


def test_native_application_defaults_and_saved_opt_out(tmp_path):
    path = tmp_path / 'window.json'
    defaults = desktop.load_preferences(path)
    assert defaults['close_to_tray'] and defaults['notifications']
    desktop.save_preferences(path, {**defaults, 'notifications': False, 'close_to_tray': False})
    restored = desktop.load_preferences(path)
    assert not restored['notifications'] and not restored['close_to_tray']
