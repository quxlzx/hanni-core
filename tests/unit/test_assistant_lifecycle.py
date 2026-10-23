"""Original lifecycle boundaries with disposable stores and no physical audio."""
import http.client
import importlib.util
import json
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from hanni.config.loader import load_config
from hanni.config.schema import ConfigError, parse_models
from hanni.dashboard import launcher
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.server import DashboardServer
from hanni.models import runtime
from hanni.speech.relevance import SpeechRelevanceClassifier
ROOT = Path(__file__).resolve().parents[2]

def post(server, path, *, token=None, body=None):
    port = server.server_port
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        conn.request('POST', path, json.dumps({} if body is None else body), {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}', 'X-Hanni-Token': server.chat.token if token is None else token})
        response = conn.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        conn.close()

def test_restart_authorization_validation_and_single_lifecycle_transition(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    stop, restart = (threading.Event(), threading.Event())
    hub = ChatHub()
    server = DashboardServer(0, SimpleNamespace(config=config), hub, shutdown_event=stop, restart_event=restart)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    hub.request_shutdown = Mock(wraps=hub.request_shutdown)
    try:
        assert server.workspace_snapshot()['features']['restart'] is True
        assert post(server, '/api/restart', token='invalid')[0] == 403
        assert post(server, '/api/restart', body={'command': 'ignored'})[0] == 400
        assert not stop.is_set() and (not restart.is_set())
        assert post(server, '/api/restart') == (202, {'restarting': True})
        assert stop.is_set() and restart.is_set()
        assert post(server, '/api/restart') == (202, {'restarting': True})
        assert post(server, '/api/shutdown')[0] == 409
        assert hub.request_shutdown.call_count == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        hub.close()
        hub.db.close()

def test_unmanaged_server_reports_restart_unavailable(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    stop = threading.Event()
    hub = ChatHub()
    server = DashboardServer(0, SimpleNamespace(config=config), hub, shutdown_event=stop)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert server.workspace_snapshot()['features']['restart'] is False
        assert post(server, '/api/restart')[0] == 503
        assert not stop.is_set()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        hub.close()
        hub.db.close()

def test_original_launcher_restarts_same_origin_after_full_cleanup(tmp_path):
    servers, cli_calls, epochs, managers = ([], [], [], [])
    marker = tmp_path / 'preserved.txt'
    marker.write_text('keep')
    real_server = DashboardServer

    def create_server(*args, **kwargs):
        server = real_server(*args, **kwargs)
        servers.append(server)
        return server

    def manager_factory(*args, **kwargs):
        manager = Mock()
        managers.append(manager)
        return manager

    def cli(argv, *, shutdown_event):
        cli_calls.append(list(argv))
        epochs.append(servers[-1].chat.epoch)
        if len(cli_calls) == 2:
            managers[0].close.assert_called_once()
        assert shutdown_event.wait(10)
        return 0
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    telemetry = SimpleNamespace(config=config, start=lambda: None, close=lambda: None)
    result = []
    with patch.object(launcher, 'Telemetry', return_value=telemetry), patch.object(launcher, 'DashboardServer', side_effect=create_server), patch('hanni.models.manager.ModelManager', side_effect=manager_factory), patch.object(launcher, 'launch_desktop') as desktop, patch('hanni.laya.manager.start_shadow_from_env', return_value=None), patch('hanni.laya.manager.stop_shadow'), patch('hanni.cli.run', side_effect=cli):
        desktop.return_value.poll.return_value = None
        import socket
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            thread = threading.Thread(target=lambda: result.append(launcher.main(['--port', str(occupied.getsockname()[1]), '--text', '--desktop', '--config-dir', str(ROOT / 'config'), '--data-dir', str(tmp_path)])))
            thread.start()
            try:
                wait_for(lambda: len(cli_calls) == 1)
                origin = servers[0].server_port
                assert post(servers[0], '/api/restart')[0] == 202
                wait_for(lambda: len(cli_calls) == 2)
                assert servers[1].server_port == origin
                assert epochs[0] != epochs[1]
                assert post(servers[1], '/api/restart', token=servers[0].chat.token)[0] == 403
                assert marker.read_text() == 'keep'
                assert post(servers[1], '/api/shutdown')[0] == 202
                thread.join(10)
                assert not thread.is_alive() and result == [0]
                desktop.assert_called_once()
                assert all((manager.close.call_count == 1 for manager in managers))
            finally:
                for server in servers:
                    server.shutdown_event.set()
                thread.join(15)

def wait_for(check):
    deadline = time.monotonic() + 10
    while not check():
        assert time.monotonic() < deadline
        time.sleep(0.02)

def test_failed_voice_keeps_original_backend_and_model_for_keyboard(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    telemetry = SimpleNamespace(config=config, start=lambda: None, close=lambda: None)
    with patch.object(launcher, 'Telemetry', return_value=telemetry), patch('hanni.models.manager.ModelManager') as manager, patch('hanni.laya.manager.start_shadow_from_env', return_value=None), patch('hanni.laya.manager.stop_shadow'), patch('hanni.cli.run', side_effect=[1, 0]) as cli:
        assert launcher.main(['--no-browser', '--data-dir', str(tmp_path)]) == 0
        assert [call.args[0][0] for call in cli.call_args_list] == ['attend', 'text']
        assert cli.call_args_list[0].kwargs['shutdown_event'] is cli.call_args_list[1].kwargs['shutdown_event']
        manager.return_value.ensure_loaded.assert_called_once_with('supervisor')
        manager.return_value.close.assert_called_once()

@pytest.mark.parametrize('phrase', ["that's all", 'thats all', 'that’s all', 'thanks hanni thats all'])
def test_close_phrase_is_standby_and_can_wake_again(phrase):
    classifier = SpeechRelevanceClassifier()
    assert classifier.classify('Hanni hello').relevant
    assert classifier.classify(phrase).disengaged
    assert not classifier.is_engaged()
    assert not classifier.classify('unrelated conversation').relevant
    assert classifier.classify('Hanni are you there').relevant

def test_standby_keeps_voice_pump_bound_and_wakes_again_in_original_loop(tmp_path):
    from hanni.cli import run
    from hanni.dashboard.voice import voice_control
    from hanni.speech.live import PUMP_FINISHED
    from hanni.speech.types import TranscriptRecord
    events = iter(['Hanni hello', 'thats all', 'background conversation', 'Hanni are you there', None])
    observations = []
    pump = Mock()
    pump.failed = False
    pump.thread = None

    def get(timeout=None):
        item = next(events)
        if item == 'background conversation':
            snapshot = voice_control.snapshot()
            observations.append(snapshot)
            assert snapshot['available'] and snapshot['state'] == 'standby'
            assert not voice_control.pump.closed and (not voice_control.pump.paused)
            pump.stop.assert_not_called()
        return PUMP_FINISHED if item is None else TranscriptRecord(text=item, started_at=1, ended_at=2)
    pump.get.side_effect = get
    session = Mock()
    session.fallback_session = None
    session.stream_response.side_effect = lambda text: iter(['unit test reply'])
    client = Mock()
    client.health.return_value = SimpleNamespace(ok=True)
    with patch('hanni.cli.create_client', return_value=client), patch('hanni.speech.create_pipeline') as pipeline, patch('hanni.speech.TranscriptPump', return_value=pump), patch('hanni.cli._wrap_mcp_session', return_value=session), patch('hanni.cli._wrap_memory_session', return_value=session), patch('hanni.dashboard.chat.current_hub', return_value=None), patch('hanni.dashboard.chat.attach', side_effect=lambda original, source: original):
        assert run(['attend', '--no-tts', '--config-dir', str(ROOT / 'config'), '--data-dir', str(tmp_path), '--env-file', str(tmp_path / 'absent.env'), '--no-file-log']) == 0
    assert [call.args[0] for call in session.stream_response.call_args_list] == ['hello', 'are you there']
    assert len(observations) == 1
    pipeline.return_value.prepare.assert_called_once()
    pump.start.assert_called_once()
    pump.stop.assert_called_once()

def test_vision_projector_uses_same_local_weights_and_cpu_encoding(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    spec = replace(config.models.supervisor, gpu_layers=0, gpu_selection='configured')
    weights = tmp_path / spec.model_file
    weights.write_bytes(b'unexecuted fixture')
    projector = tmp_path / spec.vision_projector
    projector.write_bytes(b'unexecuted fixture')
    with patch.object(runtime, 'executable_prefix', return_value=['llama-server']), patch.object(runtime, 'supported_options', return_value='--mmproj --no-mmproj-offload'), patch('huggingface_hub.try_to_load_from_cache', return_value=None):
        command = runtime.model_command(spec, weights)
        assert command[command.index('-m') + 1] == str(weights.resolve())
        assert command[command.index('--mmproj') + 1] == str(projector.resolve())
        assert '--no-mmproj-offload' in command
        projector.unlink()
        with pytest.raises(RuntimeError, match='missing from the local model cache'):
            runtime.model_command(spec, weights)

@pytest.mark.parametrize('projector', ['../projector.gguf', '..\\projector.gguf', '/tmp/p.gguf', 'p.bin'])
def test_projector_configuration_rejects_paths(projector):
    with pytest.raises(ConfigError, match='GGUF filename'):
        parse_models({'models': [{'id': 'supervisor', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 'weights.gguf', 'endpoint': 'http://127.0.0.1:8080/v1', 'vision_projector': projector}]})

def test_desktop_shortcut_automatically_starts_full_assistant_once(tmp_path):
    spec = importlib.util.spec_from_file_location('startup_desktop', ROOT / 'desktop/main.py')
    desktop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(desktop)
    verified = [False]
    process = Mock()
    process.poll.return_value = None

    def spawn(command, **kwargs):
        assert '--dashboard-only' not in command
        assert 'start_dashboard.ps1' in str(command)
        assert '-NoBrowser' in command
        verified[0] = True
        return process
    popen = Mock(side_effect=spawn)
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, popen=popen, verify=lambda url: verified[0])
    with patch.object(desktop.socket, 'create_connection', side_effect=ConnectionRefusedError()):
        assert session.connect(tmp_path)
        assert session.connect(tmp_path)
    popen.assert_called_once()
    session.stop_owned()
    process.terminate.assert_not_called()
    process.kill.assert_not_called()

def test_terminal_reader_survives_restart_without_duplicate_console_reads():
    import queue
    from hanni.dashboard import chat
    pending = queue.Queue()
    reads = []

    def console(prompt):
        reads.append(prompt)
        result = pending.get(timeout=5)
        if result is None:
            raise EOFError
        return result
    stop = threading.Event()
    hub = Mock()
    hub.take.return_value = None
    with patch.object(chat, '_terminal_source', None), patch('builtins.input', side_effect=console):
        first = chat.keyboard_inputs(hub, stop_event=stop)
        pending.put('first session')
        assert next(first) == ('first session', False)
        stop.set()
        first.close()
        second = chat.keyboard_inputs(hub, stop_event=threading.Event())
        pending.put('after restart')
        assert next(second) == ('after restart', False)
        pending.put(None)
        wait_for(lambda: chat._terminal_source[2].is_set())
        second.close()
    assert len(reads) == 3
