import http.client
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading
import uuid
import pytest
from hanni.dashboard.chat import ChatHub, ChatSession
from hanni.dashboard.server import DashboardServer

def test_shutdown_rejects_queue_but_preserves_current_response():
    hub = ChatHub()
    hub.ready = True
    first = str(uuid.uuid4())
    second = str(uuid.uuid4())
    hub.submit(first, 'first request')
    assert hub.take() == 'first request'
    response_row = hub.begin('first request', 'browser')
    hub.submit(second, 'second request')
    hub.request_shutdown()
    hub.activate()
    rows = hub.snapshot()['messages']
    assert not hub.snapshot()['ready'] and (not hub.queue)
    assert next((row for row in rows if row['id'] == response_row))['status'] == 'working'
    assert next((row for row in rows if row['turn'] == second))['status'] == 'interrupted'
    hub.update(response_row, 'finished response', 'complete')
    assert next((row for row in hub.snapshot()['messages'] if row['id'] == response_row))['content'] == 'finished response'
    hub.close()
    hub.db.close()

def test_history_persists_but_pending_requests_never_replay(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    hub = ChatHub(path)
    hub.ready = True
    key = str(uuid.uuid4())
    hub.submit(key, 'hello')
    assert hub.submit(key, 'hello') == key
    assert len(hub.queue) == 1
    hub.close()
    hub.db.close()
    again = ChatHub(path)
    again.ready = True
    try:
        assert again.snapshot()['messages'][0]['status'] == 'interrupted'
        again.submit(key, 'hello')
        assert again.take() is None
    finally:
        again.close()
        again.db.close()

def test_voice_and_browser_share_session_and_only_accepted_turns_are_saved():
    hub = ChatHub()
    hub.ready = True
    base = Mock()
    base.stream_response.side_effect = [iter(['Hello', ' there']), iter(['It is noon.'])]
    session = ChatSession(base, hub, 'voice')
    assert ''.join(session.stream_response('Hi')) == 'Hello there'
    hub.submit(str(uuid.uuid4()), 'What time is it?')
    assert hub.take() == 'What time is it?'
    assert ''.join(session.stream_response('What time is it?')) == 'It is noon.'
    messages = hub.snapshot()['messages']
    assert [m['channel'] for m in messages] == ['voice', 'voice', 'browser', 'browser']
    assert [m['content'] for m in messages] == ['Hi', 'Hello there', 'What time is it?', 'It is noon.']
    assert all((m['status'] == 'complete' for m in messages))
    hub.close()
    hub.db.close()

def test_history_clear_is_blocked_during_pending_actions_and_rotates_token():
    hub = ChatHub()
    hub.ready = True
    key = str(uuid.uuid4())
    token = hub.token
    hub.submit(key, 'hello')
    with pytest.raises(RuntimeError):
        hub.clear()
    hub.take()
    hub.note('hello', 'hi')
    hub.clear()
    assert hub.token != token and (not hub.snapshot()['messages'])
    hub.submit(key, 'hello')
    assert hub.take() is None
    hub.close()
    hub.db.close()

def test_history_paginates_without_replaying_to_model():
    hub = ChatHub()
    for i in range(60):
        hub.note(str(i), 'reply', 'terminal')
    recent = hub.snapshot()
    assert len(recent['messages']) == 100 and recent['has_more']
    older = hub.snapshot(recent['messages'][0]['id'])
    assert len(older['messages']) == 20 and (not older['has_more'])
    assert not hub.queue
    hub.close()
    hub.db.close()

@pytest.fixture
def chat_server():
    hub = ChatHub()
    hub.ready = True
    server = DashboardServer(0, SimpleNamespace(), hub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()
    hub.close()
    hub.db.close()

def send(server, *, body=None, headers=None, path='/api/chat'):
    host = f'127.0.0.1:{server.server_port}'
    default = {'Origin': f'http://{host}', 'X-Hanni-Token': server.chat.token, 'Content-Type': 'application/json'}
    default.update(headers or {})
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        conn.request('POST', path, body=json.dumps(body or {'id': str(uuid.uuid4()), 'message': 'hello'}), headers=default)
        response = conn.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        conn.close()

@pytest.mark.parametrize('headers', [{'Origin': 'https://evil.example'}, {'Host': 'evil.example'}, {'X-Hanni-Token': 'wrong'}, {'Origin': ''}, {'Sec-Fetch-Site': 'cross-site'}, {'Content-Type': 'text/plain'}])
def test_browser_write_protection(chat_server, headers):
    status, _ = send(chat_server, headers=headers)
    assert status in {403, 415}
    assert not chat_server.chat.queue

def test_browser_enqueue_only_and_duplicate_click_runs_once(chat_server):
    body = {'id': str(uuid.uuid4()), 'message': '<script>alert(1)</script>'}
    assert send(chat_server, body=body)[0] == 202
    assert send(chat_server, body=body)[0] == 202
    assert len(chat_server.chat.queue) == 1
    assert chat_server.chat.take() == body['message']

def test_browser_rejects_overlarge_and_unready_requests(chat_server):
    assert send(chat_server, body={'id': str(uuid.uuid4()), 'message': 'x' * 4001})[0] == 400
    chat_server.chat.ready = False
    assert send(chat_server)[0] == 409
    assert not chat_server.chat.queue

def test_browser_text_runs_in_voice_loop_without_wake_word_or_tts(tmp_path):
    from hanni.cli import run
    from hanni.dashboard.chat import install
    from tests.helpers import write_config_dir
    cfg = tmp_path / 'config'
    write_config_dir(cfg)
    hub = ChatHub()
    hub.ready = True
    hub.submit(str(uuid.uuid4()), 'What time is it?')
    base = Mock()
    base.fallback_session = None
    base.stream_response.return_value = iter(['A response through the existing session.'])
    client = Mock()
    client.health.return_value = SimpleNamespace(ok=True)
    pump = Mock()
    pump.get.side_effect = AssertionError('Browser text should be consumed before waiting for audio')
    tts = Mock()
    install(hub)
    try:
        with patch('hanni.cli.create_client', return_value=client), patch('hanni.speech.create_tts', return_value=tts), patch('hanni.speech.create_pipeline'), patch('hanni.speech.TranscriptPump', return_value=pump), patch('hanni.cli._wrap_mcp_session', return_value=base), patch('hanni.cli._wrap_memory_session', return_value=base):
            code = run(['attend', '--once', '--config-dir', str(cfg), '--data-dir', str(tmp_path / 'data'), '--env-file', str(tmp_path / 'missing.env'), '--no-file-log'])
        assert code == 0
        base.stream_response.assert_called_once_with('What time is it?')
        assert hub.snapshot()['messages'][-1]['content'] == 'A response through the existing session.'
        assert hub.snapshot()['messages'][-1]['channel'] == 'browser'
        tts.start.assert_not_called()
        tts.speak.assert_not_called()
        pump.stop.assert_called_once()
    finally:
        install(None)
        hub.close()
        hub.db.close()

def test_browser_shutdown_event_exits_voice_loop_and_stops_pump(tmp_path):
    from hanni.cli import run
    from hanni.dashboard.chat import install
    from tests.helpers import write_config_dir
    cfg = tmp_path / 'config'
    write_config_dir(cfg)
    hub = ChatHub()
    client = Mock()
    client.health.return_value = SimpleNamespace(ok=True)
    pump = Mock()
    shutdown = threading.Event()
    shutdown.set()
    install(hub)
    try:
        with patch('hanni.cli.create_client', return_value=client), patch('hanni.speech.create_pipeline'), patch('hanni.speech.TranscriptPump', return_value=pump), patch('hanni.cli._wrap_mcp_session', return_value=Mock(fallback_session=None)), patch('hanni.cli._wrap_memory_session', return_value=Mock(fallback_session=None)):
            code = run(['attend', '--no-tts', '--config-dir', str(cfg), '--data-dir', str(tmp_path / 'data'), '--env-file', str(tmp_path / 'missing.env'), '--no-file-log'], shutdown_event=shutdown)
        assert code == 0
        pump.get.assert_not_called()
        pump.stop.assert_called_once()
    finally:
        install(None)
        hub.close()
        hub.db.close()
