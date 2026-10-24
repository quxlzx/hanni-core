"""Real command mutations, isolation, cancellation, and browser authorization."""
import http.client
import json
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import pytest

from hanni.dashboard.chat import ChatHub
from hanni.dashboard.commands import CATALOG, ChatCommands
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.native_chat import NativeChat
from hanni.native.model_settings import ModelSettings, atomic_json
from tests.unit.test_dashboard_chat import chat_server, send
from tests.unit.test_desktop_features import config_for


@pytest.fixture
def commands(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_CRON_ROOT', str(tmp_path / 'state'))
    from hanni.core.interaction import InteractionState
    import hanni.core.interaction as interaction_module
    from hanni.dashboard import voice
    state = InteractionState()
    monkeypatch.setattr(interaction_module, 'interaction', state)
    monkeypatch.setattr(voice, 'interaction', state)
    monkeypatch.setattr(voice, 'voice_control', voice.VoiceControl())
    hub = ChatHub(tmp_path / 'chat.sqlite3')
    hub.ready = True
    hub.native_mode = True
    settings = ModelSettings(tmp_path / 'state', tmp_path / 'models')
    cfg = config_for(tmp_path / 'workspace')
    server = SimpleNamespace(chat=hub, features=DesktopFeatures(cfg), model_settings=settings,
                             lifecycle_lock=threading.Lock(), lifecycle_action=None,
                             mcp=SimpleNamespace(snapshot=lambda: {'available': True, 'servers': []}),
                             hermes=SimpleNamespace(snapshot=lambda: {'configured': False}))
    proxy = Mock(side_effect=lambda method, path, body=None: {
        '/activity': {'tasks': [], 'worker_running': False}, '/health': {'ready': True},
        '/model': {'ready': True, 'state': 'ready', 'api_model': 'test-model'},
        '/tools': {'tools': [{'name': 'local_test', 'description': 'Example'}]},
    }.get(path, {'state': 'cancelled'}))
    service = ChatCommands(server, proxy=proxy)
    service.interaction = state
    yield service
    hub.close()
    hub.db.close()


def command(service, text, conversation='default', key=None):
    return service.execute({'id': key or str(uuid4()), 'command': text, 'conversation': conversation})


def exchange(hub, text='Question', answer='Answer', conversation='default', task_id=None):
    hub.submit(str(uuid4()), text, conversation)
    hub.take()
    row = hub.begin(text, 'browser')
    if task_id:
        hub.bind_task(row, task_id)
    hub.update(row, answer, 'complete')
    return row


def test_catalog_has_all_commands_and_help_is_not_truncated(commands):
    assert len(CATALOG) == 36
    result = command(commands, '/help')
    assert all(c['name'] in result['message'] for c in CATALOG)
    assert all(c['description'] in result['message'] and c['example'] in result['message'] for c in CATALOG)
    assert not commands.hub.queue and not commands.hub.snapshot()['messages']


def test_new_preserves_memory_and_history_searches_full_message_text(commands):
    saved = command(commands, '/remember I prefer concise status reports')
    assert saved['ok'], saved
    store = commands.server.features.memory_store()
    assert store.count() == 1
    exchange(commands.hub, 'Project kickoff', 'The secret project code is TURTLE')
    result = command(commands, '/new')
    assert result['conversation'] != 'default' and store.count() == 1
    assert not commands.hub.snapshot(conversation=result['conversation'])['messages']
    history = command(commands, '/history turtle')
    assert history['sessions'][0]['id'] == 'default'
    assert command(commands, '/resume default')['conversation'] == 'default'
    assert command(commands, '/resume missing')['sessions'] == []


def test_resume_ambiguity_returns_choices(commands):
    for _ in range(2):
        conversation = commands.hub.create_conversation(str(uuid4()))
        exchange(commands.hub, 'Duplicate title', conversation=conversation)
    result = command(commands, '/resume Duplicate title')
    assert len(result['sessions']) == 2 and 'conversation' not in result


def test_search_and_resume_reach_history_older_than_the_sidebar_limit(commands):
    exchange(commands.hub, 'Oldest project', 'Unique old project detail')
    for _ in range(502):
        commands.hub.create_conversation(str(uuid4()))
    assert 'default' not in {c['id'] for c in commands.hub.conversations()}
    assert command(commands, '/history Unique old project')['sessions'][0]['id'] == 'default'
    assert command(commands, '/resume default')['conversation'] == 'default'


def test_undo_is_durable_idempotent_and_does_not_call_tool_undo(commands):
    exchange(commands.hub, 'First')
    exchange(commands.hub, 'Second', task_id='retained-task')
    key = str(uuid4())
    result = command(commands, '/undo', key=key)
    assert result['ok'] and 'NOT reversed' in result['message']
    assert command(commands, '/undo', key=key) == result
    restarted = ChatCommands(commands.server, proxy=commands.proxy)
    assert command(restarted, '/undo', key=key) == result
    assert commands.hub.snapshot()['messages'][0]['content'] == 'First'
    assert len(commands.hub.snapshot()['messages']) == 2
    commands.proxy.assert_not_called()
    with pytest.raises(ValueError, match='different command'):
        command(commands, '/new', key=key)


def test_retry_queues_final_only_context_and_previous_observations(commands):
    exchange(commands.hub, 'Make a file', 'Created file; receipt says success.', task_id='prior-task')
    assert command(commands, '/retry')['ok']
    assert commands.hub.take() == 'Make a file'
    turn = commands.hub.current[0]
    context = commands.hub.native_context('default', exclude_turn=turn)
    assert context['regenerate_only'] and context['previous_task_id'] == 'prior-task'
    assert 'receipt says success' in context['previous_answer']
    assert len(commands.hub.snapshot()['messages']) == 1


def test_legacy_voice_runtime_cannot_repeat_tool_actions_through_retry(commands):
    exchange(commands.hub, 'Send a message', 'Sent successfully.')
    commands.hub.native_mode = False
    result = command(commands, '/retry')
    assert not result['ok'] and 'native chat dashboard' in result['message']
    assert len(commands.hub.snapshot()['messages']) == 2 and not commands.hub.queue


def test_undo_busy_is_blocked_and_stop_cancels_bound_and_unbound_turns(commands):
    commands.hub.submit(str(uuid4()), 'Slow')
    commands.hub.take()
    row = commands.hub.begin('Slow', 'browser')
    commands.hub.bind_task(row, 'task-live')
    commands.hub.submit(str(uuid4()), 'Queued')
    assert not command(commands, '/undo')['ok']
    result = command(commands, '/stop')
    assert result['ok'] and '2 active or queued' in result['message']
    commands.proxy.assert_any_call('POST', '/tasks/task-live/cancel', {})
    commands.hub.update(row, 'Late update cannot restart cancellation')
    assert not commands.hub.queue and commands.hub.current is None
    assert all(m['status'] != 'working' for m in commands.hub.snapshot()['messages'])


def test_stop_before_native_task_binding_cancels_after_submission(commands):
    hub = commands.hub
    hub.submit(str(uuid4()), 'Race')
    hub.take()
    seen = []
    def proxy(method, path, body=None):
        seen.append((method, path))
        if path == '/tasks':
            hub.stop_pending()
            return {'id': 'racing-task'}
        return {'state': 'cancelled'}
    native = NativeChat(hub, threading.Event(), proxy=proxy)
    native.respond('Race')
    assert ('POST', '/tasks/racing-task/cancel') in seen
    assert hub.snapshot()['messages'][-1]['status'] == 'interrupted'


def test_voice_mute_does_not_pause_microphone_or_cancel_generation(commands, monkeypatch):
    from hanni.dashboard import voice
    state = commands.interaction
    state.response_cancel_event = threading.Event()
    state.playback = Mock(active=True)
    pump = SimpleNamespace(closed=False, paused=False, running=lambda: True, pause=Mock(), resume=Mock())
    classifier = Mock()
    voice.voice_control.bind(pump, classifier, SimpleNamespace(context=SimpleNamespace(emergency_stop=Mock())), 'Hanni')
    assert command(commands, '/mute on')['ok']
    assert state.speech_muted and not state.response_cancel_event.is_set()
    pump.pause.assert_not_called()
    state.playback.stop.assert_called_once()
    assert command(commands, '/mute off')['ok'] and not state.speech_muted
    assert command(commands, '/wake off')['ok'] and not state.wake_enabled
    assert command(commands, '/wake on')['ok'] and state.wake_enabled
    assert command(commands, '/voice on')['ok']
    assert command(commands, '/voice off')['ok']
    pump.pause.assert_called_once()


def test_missing_voice_and_invalid_switch_values_are_honest(commands):
    assert not command(commands, '/voice on')['ok']
    assert command(commands, '/voice off')['ok']
    assert not command(commands, '/mute maybe')['ok']
    for text in ('/status', '/tools', '/connections'):
        assert command(commands, text)['ok']
    assert 'Honcho' in command(commands, '/connections')['message']


def test_memory_save_search_and_verified_exact_deletion(commands):
    saved = command(commands, '/remember I prefer Monday planning meetings')
    assert saved['ok'] and 'Saved and verified' in saved['message'], saved
    assert 'Already saved' in command(commands, '/remember I prefer Monday planning meetings')['message']
    found = command(commands, '/memory Monday')
    assert 'Monday' in found['message']
    record = commands.server.features.memory_store().list()[0]
    assert not command(commands, '/forget ' + record.id[:5])['ok']
    forgotten = command(commands, '/forget ' + record.id)
    assert forgotten['ok'], forgotten
    assert commands.server.features.memory_store().get(record.id) is None
    assert not command(commands, '/forget ' + record.id)['ok']


def wait_command(service, result):
    deadline = time.monotonic() + 5
    while result.get('pending') and time.monotonic() < deadline:
        time.sleep(.01)
        result = service.result(result['id'])
    assert not result.get('pending'), result
    return result


def test_compress_preserves_browsable_history_and_feeds_next_response(commands, monkeypatch):
    from hanni.native.provider import NativeClient
    monkeypatch.setattr('hanni.native.provider.load_model', lambda: {'id': 'test', 'endpoint': 'http://localhost:1/v1', 'context_length': 65536})
    calls = []
    def summarize(self, messages, tools=None):
        calls.append(messages)
        return {'message': {'content': 'Preserve the budget of $300 and owner Alice.'}}
    monkeypatch.setattr(NativeClient, 'chat', summarize)
    exchange(commands.hub, 'Budget $300', 'Owner Alice')
    result = wait_command(commands, command(commands, '/compress budget'))
    assert result['ok'], result
    assert '"focus": "budget"' in calls[0][1]['content']
    assert len(commands.hub.snapshot()['messages']) == 2
    context = commands.hub.native_context('default')
    assert '$300' in context['conversation_summary'] and context['conversation'] == []
    assert '61,988' in command(commands, '/context')['message']  # provider default reserves 1500 output
    exchange(commands.hub, 'New question', 'New answer')
    assert len(commands.hub.native_context('default')['conversation']) == 2
    command(commands, '/undo')
    assert commands.hub.native_context('default')['conversation_summary']
    command(commands, '/undo')
    assert not commands.hub.native_context('default')['conversation_summary']


def test_stop_is_not_blocked_by_summarization_and_discards_cancelled_summary(commands, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr('hanni.native.provider.load_model', lambda: {'id': 'test', 'endpoint': 'http://localhost:1/v1'})
    def summarize(self, messages, tools=None):
        entered.set()
        assert release.wait(4)
        return {'message': {'content': 'Must not save'}}
    monkeypatch.setattr('hanni.native.provider.NativeClient.chat', summarize)
    exchange(commands.hub)
    pending = command(commands, '/compress')
    assert entered.wait(2)
    stopped = command(commands, '/stop')
    assert stopped['ok'] and 'winding down' in stopped['message']
    release.set()
    assert not wait_command(commands, pending)['ok']
    assert not commands.hub.native_context('default')['conversation_summary']


def test_reasoning_requires_advertised_support_and_applies_per_model(commands, monkeypatch):
    root = commands.server.model_settings.root
    root.mkdir(parents=True)
    monkeypatch.setenv('HANNI_MODEL_STATE', str(root))
    cfg = {'id': 'test', 'source': 'local', 'model_file': 'local.gguf', 'endpoint': 'http://localhost:1/v1'}
    monkeypatch.setattr('hanni.native.provider.load_model', lambda: cfg)
    monkeypatch.setattr('hanni.native.provider.NativeClient.status', lambda self: {'ready': True})
    assert not command(commands, '/reasoning high')['ok']
    assert not (root / 'reasoning-settings.json').exists()
    monkeypatch.setattr('hanni.native.provider.NativeClient.status', lambda self: {'ready': True, 'reasoning_levels': ['low', 'medium', 'high']})
    assert command(commands, '/reasoning high')['ok']
    from hanni.native.provider import NativeClient
    payload = NativeClient(cfg)._payload([{'role': 'user', 'content': 'Hi'}], None)
    assert payload['reasoning_effort'] == 'high' and payload['reasoning_budget_tokens'] == 1024
    assert 'reasoning_effort' not in NativeClient({**cfg, 'model_file': 'other.gguf'})._payload([], None)
    assert not command(commands, '/reasoning extreme')['ok']


def test_commands_use_worker_config_not_the_stripped_dashboard_config(commands, monkeypatch):
    import yaml
    settings = commands.server.model_settings
    settings.root.mkdir(parents=True)
    worker = {'id': 'test', 'source': 'local', 'endpoint': 'http://localhost:1/v1',
              'context_length': 65536, 'native_max_tokens': 1200, 'native_reasoning_budget': 512}
    (settings.root / 'models.native.yaml').write_text(yaml.safe_dump({'models': [worker]}))
    dashboard = settings.root / 'models.dashboard.yaml'
    dashboard.write_text(yaml.safe_dump({'models': [{k: v for k, v in worker.items() if not k.startswith('native_') and k != 'source'}]}))
    monkeypatch.setenv('HANNI_MODEL_CONFIG', str(dashboard))
    assert '62,288' in command(commands, '/context')['message']
    monkeypatch.setattr('hanni.native.provider.NativeClient.status', lambda self: {
        'ready': True, 'reasoning_levels': ['high'] if self.config.get('source') == 'local' else []})
    assert command(commands, '/reasoning high')['ok']


def test_model_selects_saved_api_server_using_owning_launcher(commands, monkeypatch):
    settings = commands.server.model_settings
    settings.remember_profile({'source': 'api', 'context': 65536, 'endpoint': 'https://model.example/v1', 'api_model': 'work-model'})
    applied = []
    monkeypatch.setattr(settings, 'execute', lambda body: applied.append(body))
    assert 'work-model@https://model.example/v1' in command(commands, '/model')['message']
    assert command(commands, '/model work-model')['ok']
    assert applied[0]['endpoint'] == 'https://model.example/v1' and not commands.hub.ready
    assert not command(commands, '/model nonexistent')['ok']


def test_retry_worker_has_no_executable_tools_even_if_model_invents_call(tmp_path):
    from unittest.mock import patch
    from hanni.hermes.state import TaskStore
    from hanni.native import worker
    from tests.test_native_loop import FakeClient
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('retry-test', {'prompt': 'Create a file', 'windows_tools': [], 'origin': 'hanni',
                                     'context': {'regenerate_only': True, 'previous_answer': 'File was created.'}})
    client = FakeClient([
        {'message': {'tool_calls': [{'id': 'fake-call', 'function': {'name': 'local_write_file', 'arguments': '{}'}}]}},
        {'message': {'content': 'The previous file creation remains in effect.'}}])
    client.max_tokens = 1200
    try:
        with patch.object(worker, 'NativeClient', return_value=client), \
             patch.object(worker, 'load_model', return_value={'context_length': 65536}), \
             patch('hanni.native.mcp_client.discover', return_value=[]), \
             patch.object(worker, 'execute_local') as execute:
            worker.run(store.path, task['id'], {'entries': []})
        execute.assert_not_called()
        assert all(not call['tools'] for call in client.calls)
        result = store.get(task['id'])
        assert result['state'] == 'review_required' and not result['actions']
    finally:
        store.close()


def test_muting_then_unmuting_speech_does_not_cancel_answer_generation(monkeypatch):
    from hanni.core.interaction import InteractionState
    from hanni.core.response_stream import FinalSentence
    from hanni.speech import response
    state = InteractionState()
    monkeypatch.setattr(response, 'interaction', state)
    first_started, released = threading.Event(), threading.Event()
    playbacks, text = [], []
    class Playback:
        def __init__(self, active):
            self.active, self.cancelled = active, False
        def stop(self):
            self.active, self.cancelled = False, True
        def wait(self, timeout):
            return None
    class Speaker:
        def start(self, sentence):
            playback = Playback(not playbacks)
            playbacks.append(playback)
            if len(playbacks) == 1:
                first_started.set()
            return playback
    def chunks():
        yield FinalSentence('First sentence.')
        assert released.wait(3)
        yield FinalSentence('Second sentence.')
    def mute():
        assert first_started.wait(3)
        state.mute_speech(True)
        state.mute_speech(False)
        released.set()
    thread = threading.Thread(target=mute)
    thread.start()
    try:
        result = response.deliver_response(chunks(), tts=Speaker(), on_text=text.append, poll_seconds=.001)
        assert not result.interrupted
        assert 'Second sentence.' in ''.join(text)
        assert playbacks[0].cancelled
    finally:
        released.set()
        thread.join(3)


@pytest.mark.parametrize('headers', [{'X-Hanni-Token': 'wrong'}, {'Origin': 'https://evil.example'}, {'Origin': ''}])
def test_command_writes_require_origin_and_session_token(chat_server, headers):
    status, _ = send(chat_server, path='/api/chat/command', body={'id': str(uuid4()), 'command': '/new', 'conversation': 'default'}, headers=headers)
    assert status == 403
    assert len(chat_server.chat.conversations()) == 1


def test_commands_work_when_model_is_unavailable_and_private_catalog_requires_token(chat_server):
    chat_server.chat.ready = False
    status, result = send(chat_server, path='/api/chat/command', body={'id': str(uuid4()), 'command': '/help', 'conversation': 'default'})
    assert status == 200 and result['ok']
    assert not chat_server.chat.queue
    for path in ('/api/chat/commands', '/api/chat/command?id=' + str(uuid4())):
        connection = http.client.HTTPConnection('127.0.0.1', chat_server.server_port)
        connection.request('GET', path)
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.close()
