"""Native wrapper boundaries/lifecycle without launching models, terminals, or windows."""
from __future__ import annotations
import importlib.util
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hanni_desktop_client', ROOT / 'desktop/main.py')
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)

@pytest.mark.parametrize('url', ['https://127.0.0.1:8765', 'http://example.com:8765', 'http://127.1:8765', 'http://[::1]:8765', 'http://localhost', 'http://localhost:0', 'http://localhost:65536', 'http://user@localhost:8765', 'http://localhost:8765/path', 'http://localhost:8765/?next=http://remote', 'http://localhost:8765/#chat', 'file:///C:/index.html', 'http://localhost:8765.evil.com', 'http://127.0.0.1.evil.com:8765'])
def test_native_destination_rejects_nonlocal_or_ambiguous_urls(url):
    with pytest.raises(ValueError):
        desktop.validate_url(url)

def test_native_destination_canonicalizes_loopback_root():
    assert desktop.validate_url('http://localhost:8765/') == 'http://localhost:8765'
    assert desktop.validate_url('http://127.0.0.1:9123') == 'http://127.0.0.1:9123'

def test_native_attach_checks_existing_contract_not_just_an_open_port():
    contract = {'version': 1, 'transport': 'http-snapshots', 'screens': ['home', 'chat', 'mission', 'cluster', 'settings'], 'features': {}}
    assert desktop.is_hanni(desktop.DEFAULT_URL, request=lambda url, path: contract)
    assert not desktop.is_hanni(desktop.DEFAULT_URL, request=lambda url, path: {'ok': True})
    assert not desktop.is_hanni(desktop.DEFAULT_URL, request=lambda url, path: dict(contract, version=2))

def test_native_preferences_validate_dimensions_and_persist_real_choices(tmp_path):
    path = tmp_path / 'window.json'
    path.write_text(json.dumps({'width': -10, 'height': 100000, 'x': 12, 'y': 0, 'close_to_tray': True, 'minimize_to_tray': 'yes', 'notifications': True, 'maximized': False, 'token': 'must not survive'}))
    prefs = desktop.load_preferences(path)
    assert prefs['width'] == 1366 and prefs['height'] == 860
    assert prefs['close_to_tray'] and prefs['notifications']
    assert prefs['minimize_to_tray'] is False and 'token' not in prefs
    desktop.save_preferences(path, prefs)
    assert desktop.load_preferences(path) == prefs
    assert not path.with_suffix('.tmp').exists()

def test_attached_backend_survives_desktop_close_and_no_duplicate_assistant_launch(tmp_path):
    request, popen = (Mock(), Mock())
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, attach_only=True, verify=lambda url: True, request=request, popen=popen)
    assert session.connect(tmp_path)
    session.stop_owned()
    assert 'already running' in session.start_assistant()
    request.assert_not_called()
    popen.assert_not_called()

def test_attach_only_never_starts_backend_when_disconnected(tmp_path):
    popen = Mock()
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, attach_only=True, verify=lambda url: False, popen=popen)
    assert session.connect(tmp_path) is False
    popen.assert_not_called()

def test_close_during_connection_probe_prevents_late_monitor_start(tmp_path, monkeypatch):
    entered, finish = (threading.Event(), threading.Event())

    def verify(url):
        entered.set()
        assert finish.wait(3)
        return False
    popen = Mock()
    monkeypatch.setattr(desktop.socket, 'create_connection', Mock(side_effect=ConnectionRefusedError()))
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, verify=verify, popen=popen)
    results = []
    worker = threading.Thread(target=lambda: results.append(session.connect(tmp_path)))
    worker.start()
    assert entered.wait(3)
    session.exit_requested.set()
    session.stop_owned()
    finish.set()
    worker.join(timeout=3)
    assert not worker.is_alive() and results == [False]
    popen.assert_not_called()
    assert session.process is None

def test_close_cleans_monitor_published_while_popen_was_in_flight(tmp_path, monkeypatch):
    entered, finish = (threading.Event(), threading.Event())
    process = Mock()
    process.pid = 321
    process.poll.return_value = None

    def launch(*args, **kwargs):
        entered.set()
        assert finish.wait(3)
        return process
    run = Mock()
    monkeypatch.setattr(desktop.socket, 'create_connection', Mock(side_effect=ConnectionRefusedError()))
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, verify=lambda url: False, popen=launch, run=run)
    results = []
    worker = threading.Thread(target=lambda: results.append(session.connect(tmp_path)))
    worker.start()
    assert entered.wait(3)
    session.exit_requested.set()
    cleanup = threading.Thread(target=session.stop_owned)
    cleanup.start()
    finish.set()
    worker.join(timeout=3)
    cleanup.join(timeout=3)
    assert not worker.is_alive() and (not cleanup.is_alive()) and (results == [False])
    assert session.process is None and session.log is None
    if desktop.os.name == 'nt':
        assert run.call_args.args[0][1:] == ['/PID', '321', '/T', '/F']
    else:
        process.terminate.assert_called_once()

def test_unverified_occupied_port_is_never_attached_or_replaced(tmp_path, monkeypatch):
    import socket
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        popen = Mock()
        session = desktop.BackendSession(f'http://127.0.0.1:{listener.getsockname()[1]}', ROOT, autostart_assistant=False, verify=lambda url: False, popen=popen)
        with pytest.raises(RuntimeError, match='unverified'):
            session.connect(tmp_path)
        popen.assert_not_called()

@pytest.mark.parametrize('redirector', [False, True])
def test_owned_monitor_readiness_binds_actual_port_pid_and_epoch(tmp_path, monkeypatch, redirector):
    monkeypatch.setattr(desktop.socket, 'create_connection', Mock(side_effect=ConnectionRefusedError()))
    process = Mock()
    process.pid = 123
    process.poll.return_value = None
    actual = 'http://127.0.0.1:9123'

    def launch(command, **kwargs):
        assert command[3:5] == ['--dashboard-only', '--no-browser']
        assert kwargs['stdin'] is desktop.subprocess.DEVNULL
        Path(command[-1]).write_text(json.dumps({'pid': 456 if redirector else 123, 'parent_pid': 123 if redirector else 999, 'url': actual, 'epoch': 'owned-epoch'}))
        return process
    request = Mock(return_value={'epoch': 'owned-epoch', 'token': 'not-written-to-disk'})
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, popen=launch, verify=lambda url: url == actual, request=request)
    assert session.connect(tmp_path)
    assert session.url == actual and session.owned_epoch == 'owned-epoch'
    assert session.owned_token == 'not-written-to-disk'
    assert 'not-written-to-disk' not in session.ready_path.read_text()
    session.process = None
    session.log.close()

@pytest.mark.parametrize('ownership', ['wrong-pid', 'wrong-epoch'])
def test_owned_monitor_rejects_mismatched_readiness_identity(tmp_path, monkeypatch, ownership):
    monkeypatch.setattr(desktop.socket, 'create_connection', Mock(side_effect=ConnectionRefusedError()))
    process = Mock()
    process.pid = 123
    process.poll.return_value = None
    count = [0]

    def verify(url):
        count[0] += 1
        return count[0] > 1

    def launch(command, **kwargs):
        Path(command[-1]).write_text(json.dumps({'pid': 888 if ownership == 'wrong-pid' else 123, 'url': desktop.DEFAULT_URL, 'epoch': 'owned'}))
        return process
    request = Mock(return_value={'epoch': 'replacement', 'token': 'foreign'})
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, popen=launch, verify=verify, request=request)
    with pytest.raises(RuntimeError, match='ownership|identity'):
        session.connect(tmp_path)
    assert session.owned_token is None
    assert not any((call.args[1] == '/api/shutdown' for call in request.call_args_list))
    session.process = None
    session.log.close()

def test_owned_monitor_uses_pinned_token_and_only_terminates_owned_process():
    request = Mock(side_effect=[{'epoch': 'owned-epoch'}, {'stopping': True}])
    process = Mock()
    process.poll.side_effect = [None, 0]
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, request=request)
    session.process = process
    session.owned_token = 'owned-launch-token'
    session.owned_epoch = 'owned-epoch'
    session.stop_owned()
    assert request.call_count == 2
    request.assert_called_with(desktop.DEFAULT_URL, '/api/shutdown', body={}, token='owned-launch-token', timeout=3)
    process.wait.assert_called_once_with(timeout=8)
    process.terminate.assert_not_called()
    assert session.process is None and session.owned_token is None

def test_foreign_epoch_rejection_only_stops_owned_dashboard_only_child():
    request = Mock(return_value={'epoch': 'replacement-epoch'})
    process = Mock()
    process.pid = 321
    process.poll.side_effect = [None, None]
    run = Mock()
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, request=request, run=run)
    session.process = process
    session.owned_token = 'old-owned-token'
    session.owned_epoch = 'old-owned-epoch'
    session.stop_owned()
    if desktop.os.name == 'nt':
        assert run.call_args.args[0][1:] == ['/PID', '321', '/T', '/F']
        assert 'shell' not in run.call_args.kwargs
    else:
        process.terminate.assert_called_once()
    request.assert_called_once_with(desktop.DEFAULT_URL, '/api/chat?before=1')
    assert session.process is None

def test_start_assistant_uses_hidden_native_stack_once(tmp_path):
    popen = Mock()
    process = Mock()
    process.poll.return_value = None
    popen.return_value = process
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, autostart_assistant=False, verify=lambda url: False, popen=popen)
    assert 'Starting HANNI' in session.start_assistant(tmp_path)
    assert 'already open' in session.start_assistant(tmp_path)
    popen.assert_called_once()
    command = popen.call_args.args[0]
    assert command[:2] == [str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scripts/firstboot.py')]
    assert command[2:6] == ['--serve', '--wait', '--ui', '--no-browser']
    assert command[command.index('--desktop-owner-pid') + 1] == str(desktop.os.getpid())
    assert command[-2:] == ['--port', '8311']
    assert popen.call_args.kwargs['creationflags'] == getattr(desktop.subprocess, 'CREATE_NO_WINDOW', 0)
    assert popen.call_args.kwargs['stdin'] is desktop.subprocess.DEVNULL
    assert 'shell' not in popen.call_args.kwargs
    session.process = None
    session.log.close()

def test_close_to_tray_prevents_close_and_explicit_exit_remains_available(tmp_path):
    app = desktop.DesktopApp(SimpleNamespace(), tmp_path, 'Test', desktop.load_preferences(tmp_path / 'none'))
    app.window = Mock()
    app.window.width = 900
    app.window.height = 650
    app.window.x = 100
    app.window.y = 100
    app.tray = Mock()
    app.preferences['close_to_tray'] = False
    assert app.close_requested() is True
    app.preferences['close_to_tray'] = True
    assert app.close_requested() is False
    app.window.hide.assert_called_once()
    app.exit()
    app.window.destroy.assert_called_once()
    assert app.exiting and app.close_requested() is True

def test_offline_html_escapes_errors_and_has_no_command_bridge():
    page = desktop.offline_html('<script>alert(1)</script>', desktop.DEFAULT_URL)
    assert '<script>' not in page and '&lt;script&gt;' in page
    assert "script-src 'none'" in page
    assert 'pywebview.api' not in page
