import socket
import subprocess
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
import pytest
from hanni.dashboard import launcher

def make_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fixture; never executed')
    return path

def test_desktop_receives_actual_fallback_port_and_remains_independent(tmp_path, monkeypatch):
    executable = make_file(tmp_path / 'dist' / 'HANNI OS' / 'HANNI OS.exe')
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    child = launcher.launch_desktop('http://127.0.0.1:49153', repo_root=tmp_path, env={})
    assert child is spawn.return_value
    command = spawn.call_args.args[0]
    assert command == [str(executable.resolve()), '--url', 'http://127.0.0.1:49153', '--attach-only', '--repo-root', str(tmp_path.resolve())]
    assert spawn.call_args.kwargs['stdin'] == subprocess.DEVNULL
    child.terminate.assert_not_called()
    child.kill.assert_not_called()

def test_source_desktop_fallback_and_explicit_installed_executable(tmp_path, monkeypatch):
    python = make_file(tmp_path / 'build' / 'desktop-venv' / 'Scripts' / 'pythonw.exe')
    main = make_file(tmp_path / 'desktop' / 'main.py')
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    launcher.launch_desktop('http://127.0.0.1:8765', repo_root=tmp_path, env={})
    assert spawn.call_args.args[0][:2] == [str(python), str(main)]
    installed = make_file(tmp_path / 'installed directory' / 'HANNI OS.exe')
    launcher.launch_desktop('http://127.0.0.1:8765', repo_root=tmp_path, env={'HANNI_DESKTOP_EXE': str(installed)})
    assert spawn.call_args.args[0][0] == str(installed.resolve())
    with pytest.raises(RuntimeError, match='unavailable'):
        launcher.launch_desktop('http://127.0.0.1:8765', repo_root=tmp_path, env={'HANNI_DESKTOP_EXE': str(tmp_path / 'missing.exe')})

@pytest.mark.parametrize('url', ['https://127.0.0.1:8765', 'http://evil.example:8765', 'http://127.0.0.1', 'http://user@127.0.0.1:8765', 'http://127.0.0.1:8765/api/chat', 'http://127.0.0.1:8765?command=whoami', 'http://127.0.0.1:8765#chat'])
def test_native_launcher_rejects_foreign_origins_or_extra_input(url, tmp_path, monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    with pytest.raises(ValueError):
        launcher.launch_desktop(url, repo_root=tmp_path, env={})
    spawn.assert_not_called()

def test_native_launcher_missing_build_does_not_open_browser_or_spawn(tmp_path, monkeypatch):
    spawn, browser = (Mock(), Mock())
    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    monkeypatch.setattr(launcher.webbrowser, 'open', browser)
    with pytest.raises(RuntimeError, match='build_desktop'):
        launcher.launch_desktop('http://127.0.0.1:8765', repo_root=tmp_path, env={})
    spawn.assert_not_called()
    browser.assert_not_called()

def test_foreground_launcher_opens_native_client_on_actual_port_and_preserves_cli(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen(1)
        port = occupied.getsockname()[1]
        with patch.object(launcher, 'Telemetry'), patch.object(launcher, 'create_client') as client, patch.object(launcher, 'launch_desktop') as desktop, patch.object(launcher.webbrowser, 'open') as browser, patch('hanni.models.manager.ModelManager') as manager, patch('hanni.laya.manager.start_shadow_from_env', return_value=None), patch('hanni.laya.manager.stop_shadow'), patch('hanni.cli.run', return_value=0) as cli:
            client.return_value.health.return_value.ok = True
            desktop.return_value.poll.return_value = None
            result = launcher.main(['--port', str(port), '--desktop', '--reuse-model', '--text', '--data-dir', str(tmp_path)])
            assert result == 0
            desktop.assert_called_once()
            origin = urlsplit(desktop.call_args.args[0])
            assert origin.hostname == '127.0.0.1' and origin.port != port
            browser.assert_not_called()
            assert cli.call_args.args[0][:3] == ['text', '--model-id', 'supervisor']
            assert 'shutdown_event' in cli.call_args.kwargs
            manager.return_value.close.assert_called_once()

def test_monitor_readiness_contains_only_nonsecret_process_origin_and_epoch(tmp_path):
    path = tmp_path / 'client state' / 'owned-monitor.json'
    launcher.write_desktop_ready(path, 'http://127.0.0.1:49154', SimpleNamespace(epoch='test-epoch', token='NEVER-WRITE-THIS'))
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data == {'pid': os.getpid(), 'parent_pid': os.getppid(), 'url': 'http://127.0.0.1:49154', 'epoch': 'test-epoch'}
    assert 'NEVER-WRITE-THIS' not in path.read_text(encoding='utf-8')
    assert not path.with_suffix('.json.tmp').exists()

def test_monitor_readiness_is_not_available_for_live_assistant_sessions(tmp_path, monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    with pytest.raises(SystemExit):
        launcher.main(['--ready-file', str(tmp_path / 'monitor.json')])
    spawn.assert_not_called()

def test_desktop_exit_fences_admissions_and_signals_existing_cleanup():
    import threading
    event = threading.Event()
    chat = Mock()
    states = iter([True, True, False])
    launcher.watch_desktop_exit(lambda: next(states), event, chat, interval=0.001)
    assert event.is_set()
    chat.request_shutdown.assert_called_once()

def test_shutdown_already_requested_does_not_repeat_desktop_cleanup():
    import threading
    event = threading.Event()
    event.set()
    chat, alive = (Mock(), Mock())
    launcher.watch_desktop_exit(alive, event, chat)
    alive.assert_not_called()
    chat.request_shutdown.assert_not_called()

def test_dead_desktop_owner_cannot_leave_session_running():
    import psutil
    with patch.object(psutil, 'Process', side_effect=psutil.NoSuchProcess(123)):
        assert launcher.desktop_owner_alive(123)() is False

def test_desktop_close_reaches_manager_cleanup_through_production_launcher(tmp_path):
    with patch.object(launcher, 'Telemetry'), patch.object(launcher, 'create_client') as client, patch.object(launcher, 'launch_desktop') as desktop, patch('hanni.models.manager.ModelManager') as manager, patch('hanni.laya.manager.start_shadow_from_env', return_value=None), patch('hanni.laya.manager.stop_shadow'), patch('hanni.cli.run') as cli:
        client.return_value.health.return_value.ok = True
        desktop.return_value.poll.return_value = 0
        cli.side_effect = lambda command, shutdown_event: shutdown_event.wait(2) and 0
        assert launcher.main(['--desktop', '--text', '--data-dir', str(tmp_path)]) == 0
        manager.return_value.close.assert_called_once()

def test_desktop_exit_releases_owned_process_and_preserves_external_process(tmp_path):
    """Real OS processes; fixtures are sleepers, not live inference servers."""
    import sys
    import threading
    from hanni.config.loader import load_config
    from hanni.models.manager import ModelManager
    command = [sys.executable, '-c', 'import time; time.sleep(30)']
    owned = subprocess.Popen(command)
    external = subprocess.Popen(command)
    manager = ModelManager(load_config(data_dir=tmp_path), health=lambda spec: True)
    entry = manager.entries[manager.config.models.supervisor.id]
    entry.process, entry.state = (owned, 'READY')
    try:
        shutdown = threading.Event()
        launcher.watch_desktop_exit(lambda: False, shutdown, Mock())
        assert shutdown.is_set()
        manager.close()
        assert owned.poll() is not None
        assert external.poll() is None
    finally:
        manager.close()
        launcher.stop_owned(owned)
        launcher.stop_owned(external)
