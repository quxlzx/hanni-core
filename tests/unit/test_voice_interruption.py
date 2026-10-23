"""Original HTTP/voice loop and owned Windows workers; no physical audio."""
import http.client
import json
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import psutil
import pytest
from hanni.cli import run
from hanni.config.loader import load_config
from hanni.core.activity import activity
from hanni.dashboard.chat import ChatHub, install
from hanni.dashboard.server import DashboardServer
from hanni.dashboard.voice import voice_control
from hanni.models.client import ModelUnavailableError
from hanni.speech.neural import NeuralPlayback
from hanni.speech.types import TranscriptRecord
ROOT = Path(__file__).resolve().parents[2]

def silent_worker(*, fails=False):
    return subprocess.Popen([sys.executable, '-c', 'raise SystemExit(1)' if fails else 'import time; time.sleep(60)'], stderr=subprocess.PIPE, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

def test_cancellation_stops_owned_redirected_python_children_and_preserves_other_worker():
    owned, other = (silent_worker(), silent_worker())
    playback, other_playback = (NeuralPlayback(owned, 30), NeuralPlayback(other, 30))
    try:
        deadline = time.monotonic() + 3
        children = []
        while time.monotonic() < deadline:
            children = psutil.Process(owned.pid).children(recursive=True)
            if children or sys.platform != 'win32':
                break
            time.sleep(0.02)
        assert children or sys.platform != 'win32'
        playback.stop()
        playback.wait(2)
        assert playback.cancelled and (not playback.active)
        assert all((not child.is_running() for child in children))
        assert other.poll() is None
    finally:
        playback.stop()
        other_playback.stop()

def test_late_deadline_callback_cannot_turn_explicit_cancel_into_timeout():
    process = Mock()
    process.poll.return_value = None
    playback = NeuralPlayback(process, 30)
    playback.stop()
    playback._expire()
    playback.wait(1)
    assert playback.cancelled and (not playback._timed_out)
    process.poll.return_value = 0

@pytest.mark.parametrize('mode', ['spoken', 'button', 'playback_failure', 'model_failure'])
def test_original_voice_loop_keeps_http_session_and_handles_next_turn(tmp_path, mode):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    hub = ChatHub(tmp_path / 'chat.sqlite3')
    stop, restart = (threading.Event(), threading.Event())
    server = DashboardServer(0, SimpleNamespace(config=config), hub, shutdown_event=stop, restart_event=restart)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    initial_epoch = hub.epoch
    calls, playbacks, survived = ([], [], [])
    interrupted = [False]
    client = Mock()
    client.health.return_value = SimpleNamespace(ok=True)
    session = Mock()
    session.fallback_session = None

    def response(prompt):
        calls.append(prompt)
        if mode == 'model_failure' and len(calls) == 1:
            raise ModelUnavailableError('Controlled temporary endpoint failure')
        yield 'A synthetic response for this controlled test.'
    session.stream_response.side_effect = response
    engine = Mock()

    def start(text):
        playback = NeuralPlayback(silent_worker(fails=mode == 'playback_failure' and (not playbacks)), 30)
        playbacks.append(playback)
        return playback
    engine.start.side_effect = start
    pump = Mock()
    pump.failed = False
    pump.thread = None
    pump_count = [0]

    def request(path, *, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            if body is None:
                conn.request('GET', path)
            else:
                conn.request('POST', path, json.dumps(body), {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{server.server_port}', 'X-Hanni-Token': hub.token})
            reply = conn.getresponse()
            return (reply.status, json.loads(reply.read()))
        finally:
            conn.close()

    def get(timeout=None):
        if pump_count[0] == 0:
            pump_count[0] += 1
            return TranscriptRecord(text='Hanni first request', started_at=1, ended_at=2)
        if len(calls) == 1 and playbacks and playbacks[0].active and (not interrupted[0]):
            interrupted[0] = True
            if mode == 'button':
                assert request('/api/voice', body={'id': str(uuid.uuid4()), 'action': 'interrupt'})[0] == 200
                raise queue.Empty()
            if mode == 'spoken':
                return TranscriptRecord(text='wait', started_at=3, ended_at=4)
            playbacks[0].process.wait(timeout=3)
            raise queue.Empty()
        if len(calls) == 1:
            pump.stop.assert_not_called()
            snapshot = voice_control.snapshot()
            assert snapshot['available'] and (not snapshot['muted'])
            assert not voice_control.pump.closed and (not voice_control.pump.paused)
            status, chat = request('/api/chat')
            assert status == 200 and chat['epoch'] == initial_epoch and chat['ready']
            assert not stop.is_set() and (not restart.is_set())
            survived.append(True)
            return TranscriptRecord(text='Hanni second request', started_at=5, ended_at=6)
        stop.set()
        raise queue.Empty()
    pump.get.side_effect = get
    was_enabled = activity.enabled
    activity.enabled = True
    install(hub)
    try:
        with patch('hanni.cli.create_client', return_value=client), patch('hanni.speech.create_pipeline'), patch('hanni.speech.create_tts', return_value=engine), patch('hanni.speech.TranscriptPump', return_value=pump), patch('hanni.cli._wrap_mcp_session', return_value=session), patch('hanni.cli._wrap_memory_session', return_value=session):
            result = run(['attend', '--config-dir', str(ROOT / 'config'), '--data-dir', str(tmp_path), '--env-file', str(tmp_path / 'absent.env'), '--no-file-log'], shutdown_event=stop)
        assert result == 0 and survived == [True]
        assert calls == ['first request', 'second request']
        assistant_rows = [r for r in hub.snapshot()['messages'] if r['role'] == 'assistant']
        assert assistant_rows[-1]['status'] == 'complete'
        if mode == 'model_failure':
            assert assistant_rows[0]['status'] == 'interrupted'
        assert all((not p.active for p in playbacks))
        pump.start.assert_called_once()
        pump.stop.assert_called_once()
    finally:
        for playback in playbacks:
            playback.stop()
        install(None)
        activity.enabled = was_enabled
        server.shutdown()
        server.server_close()
        thread.join(3)
        hub.close()
        hub.db.close()
