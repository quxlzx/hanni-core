from __future__ import annotations
import http.client
import json
import struct
import subprocess
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from hanni.config.loader import load_config
from hanni.core.activity import Activity
from hanni.dashboard import launcher
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.server import DashboardServer, Telemetry, Handler
ROOT = Path(__file__).resolve().parents[2]

def test_activity_is_opt_in_scalar_only_and_expires():
    now = [0.0]
    observer = Activity(clock=lambda: now[0])
    sound = struct.pack('<hhhh', 8192, -8192, 8192, -8192)
    observer.microphone(sound)
    assert observer.snapshot()['input_level'] == 0
    observer.enabled = True
    observer.microphone(sound)
    assert observer.snapshot() == {'microphone_active': True, 'input_level': 1.0, 'speaking': False}
    assert not any((isinstance(value, bytes) for value in vars(observer).values()))
    now[0] = 1
    assert observer.snapshot()['input_level'] == 0
    assert not observer.snapshot()['microphone_active']

def test_activity_follows_playback_stop_and_synthesis_failure():
    observer = Activity()
    observer.enabled = True
    process = Mock()
    process.poll.return_value = None
    observer.playback(process)
    assert observer.snapshot()['speaking']
    process.poll.return_value = 0
    assert not observer.snapshot()['speaking']
    with pytest.raises(RuntimeError):
        with observer.speaking():
            assert observer.snapshot()['speaking']
            raise RuntimeError('synthesis failed')
    assert not observer.snapshot()['speaking']

@pytest.mark.parametrize('failure_stage', ['headers', 'body'])
@pytest.mark.parametrize('error', [ConnectionAbortedError, ConnectionResetError, BrokenPipeError])
def test_dashboard_browser_disconnect_never_sends_second_response(failure_stage, error):
    handler = object.__new__(Handler)
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    handler.wfile = Mock()
    handler.close_connection = False
    if failure_stage == 'headers':
        handler.end_headers.side_effect = error('browser disconnected')
    else:
        handler.wfile.write.side_effect = error('browser disconnected')
    handler._send(200, b'{}')
    handler.send_response.assert_called_once_with(200)
    assert handler.close_connection

@pytest.fixture
def server():
    telemetry = SimpleNamespace(snapshot=lambda: {'activity': {'input_level': 0.25}})
    server = DashboardServer(0, telemetry)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()

def request(server, path, method='GET', headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return (response.status, dict(response.getheaders()), response.read())
    finally:
        connection.close()

def test_dashboard_serves_packaged_assets_and_readonly_state(server):
    for route in ['/', '/app.js', '/style.css', '/api/state']:
        status, headers, body = request(server, route)
        assert status == 200 and body
        assert headers['Cache-Control'] == 'no-store'
        assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
        assert 'Access-Control-Allow-Origin' not in headers
        if route == '/':
            assert b'id="app-root"' in body
        if route == '/app.js':
            assert b'/api/shutdown' in body
    assert json.loads(request(server, '/api/state')[2]) == {'activity': {'input_level': 0.25}}
    assert request(server, '/api/state', method='POST')[0] == 403
    assert request(server, '/api/command')[0] == 404
    assert request(server, '/../config/permissions.yaml')[0] == 404
    assert request(server, '/%2e%2e/.env')[0] == 404

@pytest.mark.parametrize('headers', [{'Host': 'evil.example'}, {'Origin': 'https://evil.example'}, {'Sec-Fetch-Site': 'cross-site'}, {'Origin': 'null'}])
def test_dashboard_rejects_rebinding_and_cross_origin_reads(server, headers):
    assert request(server, '/api/state', headers=headers)[0] == 403

def test_model_command_uses_configured_qwen_and_loopback():
    config = load_config(ROOT / 'config', env={})
    with patch.object(launcher.shutil, 'which', return_value='C:/Program Files/llama-server.exe'), patch.object(launcher.subprocess, 'run', return_value=SimpleNamespace(stdout='Vulkan7: AMD Radeon RX 9060 XT (16304 MiB, 15000 MiB free)', stderr='', returncode=0)):
        command = launcher.model_command(replace(config.models.supervisor, vision_projector=None))
    assert command[0] == 'C:/Program Files/llama-server.exe'
    assert command[command.index('-hf') + 1] == 'lmstudio-community/Qwen3.5-4B-GGUF:Q4_K_M'
    assert command[command.index('--host') + 1] == '127.0.0.1'
    assert command[command.index('-ngl') + 1] == '99'
    assert command[command.index('--device') + 1] == 'Vulkan7'
    assert '--no-jinja' not in command

def test_existing_weight_path_is_one_argument_and_must_match_model(tmp_path):
    spec = replace(load_config(ROOT / 'config', env={}).models.supervisor, vision_projector=None)
    path = tmp_path / 'directory with spaces' / spec.model_file
    path.parent.mkdir()
    path.write_bytes(b'test fixture')
    with patch.object(launcher.shutil, 'which', return_value='llama-server'), patch.object(launcher.subprocess, 'run', return_value=SimpleNamespace(stdout='Vulkan7: AMD Radeon RX 9060 XT (16304 MiB, 15000 MiB free)', stderr='', returncode=0)):
        command = launcher.model_command(spec, path)
        assert command[command.index('-m') + 1] == str(path.resolve())
        assert '-hf' not in command
        with pytest.raises(ValueError, match='Local model'):
            launcher.model_command(spec, tmp_path / 'wrong.gguf')

def test_start_model_refuses_existing_listener(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    with patch.object(launcher.socket, 'create_connection'), patch.object(launcher.subprocess, 'Popen') as spawn:
        with pytest.raises(RuntimeError, match='occupied'):
            launcher.start_model(config)
        spawn.assert_not_called()

def test_start_model_failure_cleans_up_owned_process(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    process = Mock()
    process.poll.return_value = None
    with patch.object(launcher.socket, 'create_connection', side_effect=OSError), patch.object(launcher, 'model_command', return_value=['llama-server']), patch.object(launcher.subprocess, 'Popen', return_value=process), patch.object(launcher, 'create_client') as client:
        client.return_value.health.side_effect = KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            launcher.start_model(config)
        process.terminate.assert_called_once()
        process.wait.assert_called_once()

def test_model_startup_cancel_stops_owned_process(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    shutdown = threading.Event()
    process = Mock()
    process.poll.return_value = None

    def spawn(*args, **kwargs):
        shutdown.set()
        return process
    with patch.object(launcher.socket, 'create_connection', side_effect=OSError), patch.object(launcher, 'model_command', return_value=['llama-server']), patch.object(launcher.subprocess, 'Popen', side_effect=spawn), patch.object(launcher, 'create_client') as client:
        with pytest.raises(RuntimeError, match='Shutdown requested'):
            launcher.start_model(config, shutdown_event=shutdown)
        process.terminate.assert_called_once()
        client.return_value.health.assert_not_called()

def test_owned_process_cleanup_escalates_only_after_timeout():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired('llama', 10), 0]
    launcher.stop_owned(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    process.reset_mock()
    process.poll.return_value = 0
    launcher.stop_owned(process)
    process.terminate.assert_not_called()

def test_launcher_reuses_model_and_finds_free_dashboard_port(server, tmp_path):
    with patch.object(launcher, 'Telemetry') as telemetry, patch.object(launcher, 'create_client') as client, patch('hanni.cli.run', return_value=0) as cli, patch.object(launcher.subprocess, 'Popen') as spawn:
        client.return_value.health.return_value.ok = True
        code = launcher.main(['--port', str(server.server_port), '--reuse-model', '--no-browser', '--text', '--config-dir', str(ROOT / 'config'), '--data-dir', str(tmp_path)])
        assert code == 0
        assert cli.call_args.args[0][:3] == ['text', '--model-id', 'supervisor']
        assert hasattr(cli.call_args.kwargs['shutdown_event'], 'is_set')
        spawn.assert_not_called()
        telemetry.return_value.close.assert_called_once()

def test_dashboard_shutdown_requires_local_token_and_signals_launcher():
    hub = ChatHub()
    shutdown = threading.Event()
    dashboard = DashboardServer(0, SimpleNamespace(), hub, shutdown_event=shutdown)
    thread = threading.Thread(target=dashboard.serve_forever, daemon=True)
    thread.start()
    host = f'127.0.0.1:{dashboard.server_port}'

    def post(headers=None, body='{}'):
        connection = http.client.HTTPConnection('127.0.0.1', dashboard.server_port, timeout=3)
        try:
            request_headers = {'Host': host, 'Origin': f'http://{host}', 'X-Hanni-Token': hub.token, 'Content-Type': 'application/json'}
            request_headers.update(headers or {})
            connection.request('POST', '/api/shutdown', body=body, headers=request_headers)
            response = connection.getresponse()
            return (response.status, json.loads(response.read()))
        finally:
            connection.close()
    try:
        assert post({'X-Hanni-Token': 'wrong'})[0] == 403
        assert post({'Origin': 'https://evil.example'})[0] == 403
        assert post(body='{"unexpected":true}')[0] == 400
        assert not shutdown.is_set()
        assert post() == (202, {'stopping': True})
        assert shutdown.wait(1)
    finally:
        dashboard.shutdown()
        dashboard.server_close()
        thread.join()
        hub.close()
        hub.db.close()

def test_dashboard_only_exits_after_browser_stop(tmp_path):
    created = []
    original = DashboardServer

    def make_server(port, telemetry, chat, *, shutdown_event, restart_event):
        dashboard = original(0, telemetry, chat, shutdown_event=shutdown_event, restart_event=restart_event)
        created.append(dashboard)
        return dashboard
    results = []
    with patch.object(launcher, 'DashboardServer', side_effect=make_server):
        thread = threading.Thread(target=lambda: results.append(launcher.main(['--dashboard-only', '--no-browser', '--config-dir', str(ROOT / 'config'), '--data-dir', str(tmp_path)])), daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if created:
                    break
                time.sleep(0.1)
            assert created
            dashboard = created[0]
            host = f'127.0.0.1:{dashboard.server_port}'
            connection = http.client.HTTPConnection('127.0.0.1', dashboard.server_port, timeout=3)
            try:
                connection.request('POST', '/api/shutdown', body='{}', headers={'Host': host, 'Origin': f'http://{host}', 'X-Hanni-Token': dashboard.chat.token, 'Content-Type': 'application/json'})
                response = connection.getresponse()
                assert response.status == 202
                response.read()
            finally:
                connection.close()
            thread.join(timeout=25)
            assert not thread.is_alive()
            assert results == [0]
        finally:
            if created:
                created[0].shutdown_event.set()
            thread.join(timeout=25)

def test_telemetry_worker_reports_sample_and_corrupt_stop_fails_safe(tmp_path):
    (tmp_path / 'emergency_stop.json').write_text('corrupt')
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    telemetry = Telemetry(config)
    resources = SimpleNamespace(to_dict=lambda: {'cpu_percent': 12.5, 'gpus': []})
    telemetry.stop = Mock()
    telemetry.stop.is_set.side_effect = [False, True]
    with patch('hanni.dashboard.server.snapshot_resources', return_value=resources), patch('hanni.dashboard.server.create_client') as client:
        client.return_value.health.return_value = SimpleNamespace(state='ready')
        telemetry._run()
    result = telemetry.snapshot()
    assert result['sampled_at'] is not None and result['error'] is None
    assert result['safe_mode'] is True and result['model_status'] == 'ready'
    assert result['resources']['cpu_percent'] == 12.5
    assert result['network']['receive_bps'] is None
    assert result['disk']['total_gb'] > 0

def test_dashboard_gpu_route_can_persist_manual_override(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    telemetry = SimpleNamespace(config=config)
    hub = ChatHub()
    hub.ready = True
    dashboard = DashboardServer(0, telemetry, hub)
    thread = threading.Thread(target=dashboard.serve_forever, daemon=True)
    thread.start()
    devices = [('Vulkan0', 'AMD Radeon RX 6600 XT (8176 MiB, 7600 MiB free)'), ('Vulkan1', 'AMD Radeon RX 9060 XT (16304 MiB, 15000 MiB free)')]
    try:
        with patch('hanni.models.runtime.list_devices', return_value=devices):
            status, _, body = request(dashboard, '/api/gpu-routing')
            assert status == 200
            state = json.loads(body)
            assert state['mode'] == 'auto' and state['selected_device_id'] == 'Vulkan0'
            host = f'127.0.0.1:{dashboard.server_port}'
            conn = http.client.HTTPConnection('127.0.0.1', dashboard.server_port, timeout=3)
            try:
                payload = json.dumps({'mode': 'manual', 'device_id': 'Vulkan1'})
                conn.request('POST', '/api/gpu-routing', body=payload, headers={'Host': host, 'Origin': f'http://{host}', 'X-Hanni-Token': hub.token, 'Content-Type': 'application/json', 'Content-Length': str(len(payload))})
                response = conn.getresponse()
                body = response.read()
                assert response.status == 200
                assert json.loads(body)['mode'] == 'manual'
            finally:
                conn.close()
        saved = json.loads((tmp_path / 'gpu-routing.json').read_text())
        assert saved['mode'] == 'manual' and saved['device_name'] == 'AMD Radeon RX 9060 XT'
    finally:
        dashboard.shutdown()
        dashboard.server_close()
        thread.join()
        hub.close()
        hub.db.close()
