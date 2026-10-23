from __future__ import annotations
from pathlib import Path
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.models.client import ModelClientError, ModelToolCall, ModelTurn
from hanni.tools.registry import build_default_registry
from tests.helpers import FakeGoogleAccess, write_config_dir

class _Fallback:

    def __init__(self):
        self.history = []
        self.recorded = []

    def build_messages(self, prompt, system_suffix=''):
        return [{'role': 'system', 'content': system_suffix}, {'role': 'user', 'content': prompt}]

    def record_turn(self, prompt, response):
        self.recorded.append((prompt, response))

    def stream_response(self, prompt, **kwargs):
        yield 'fallback'

class _ChoosingClient:

    def __init__(self):
        self.complete_calls = 0
        self.tool_name = None

    def complete_with_tools(self, messages, *, tools, **kwargs):
        self.complete_calls += 1
        if self.complete_calls == 1:
            self.tool_name = tools[0]['function']['name']
            return ModelTurn('', (ModelToolCall('call-1', self.tool_name, {}),))
        return ModelTurn('Added it to your calendar.')

    def chat(self, messages, **kwargs):
        return 'done'

def _host(tmp_path: Path) -> McpHost:
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    registry.google_access = FakeGoogleAccess()
    return McpHost(registry, read_only=True, max_tools=8, allowed_actions=('google_calendar.create',))

def test_clear_calendar_write_executes_once_with_fixed_arguments(tmp_path, monkeypatch):
    host = _host(tmp_path)
    selected = host.select_tools('Schedule dentist tomorrow at 3pm')
    assert len(selected) == 1
    assert selected[0].capability_id == 'google_calendar.create'
    calls = []

    def fake_call(tool, arguments):
        calls.append((tool.capability_id, dict(arguments)))
        return {'ok': True, 'message': 'Added it to your calendar.', 'data': {'created': True}}
    monkeypatch.setattr(host, 'call', fake_call)
    client = _ChoosingClient()
    fallback = _Fallback()
    session = McpToolSession(fallback, client, host)
    answer = ''.join(session.stream_response('Schedule dentist tomorrow at 3pm'))
    assert client.complete_calls == 0
    assert calls and calls[0][0] == 'google_calendar.create'
    assert calls[0][1] == {}
    assert answer == 'The action returned a response, but I could not verify the requested outcome.'

def test_five_and_six_pm_study_requests_share_the_write_path(tmp_path, monkeypatch):
    host = _host(tmp_path)
    calls = []

    def fake_call(tool, args):
        calls.append((tool.capability_id, dict(tool.fixed_arguments), dict(args)))
        return {'ok': True, 'message': "Added 'study session' to Google Calendar.", 'data': {'created': True}}
    monkeypatch.setattr(host, 'call', fake_call)

    class NoModelCalls:

        def complete_with_tools(self, *args, **kwargs):
            raise AssertionError('resolved calendar writes should execute directly')
    session = McpToolSession(_Fallback(), NoModelCalls(), host)
    for clock in ('5pm', '6pm'):
        answer = ''.join(session.stream_response(f'add a 2-hour study session tomorrow at {clock}'))
        assert answer == 'The action returned a response, but I could not verify the requested outcome.'
    assert len(calls) == 2 and all((name == 'google_calendar.create' and args == {} for name, _, args in calls))
    assert all((fixed['summary'] == 'study session' for _, fixed, _ in calls))
    assert all((fixed['end'][:10] == fixed['start'][:10] and int(fixed['end'][11:13]) - int(fixed['start'][11:13]) == 2 for _, fixed, _ in calls))

def test_blocked_action_returns_safe_reply_without_model_or_fallback(tmp_path):
    host = _host(tmp_path)
    client = _ChoosingClient()
    fallback = _Fallback()
    answer = ''.join(McpToolSession(fallback, client, host).stream_response('wipe this drive'))
    assert "can't perform" in answer and 'No action was taken' in answer
    assert client.complete_calls == 0
    assert not fallback.recorded
    assert host.route('is hanni allowed to kill processes').status != 'blocked'

def test_simple_read_is_sampled_once_without_optional_model_calls(tmp_path, monkeypatch):
    host = _host(tmp_path)
    calls = []
    monkeypatch.setattr(host, 'call', lambda tool, args: calls.append(tool.capability_id) or {'ok': True, 'data': {'cpu_percent': 24}, 'message': 'CPU 24%.'})

    class DuplicateClient:

        def __init__(self):
            self.turn = 0
            self.final_messages = None

        def complete_with_tools(self, messages, *, tools, **kwargs):
            self.turn += 1
            if self.turn <= 2:
                name = tools[0]['function']['name']
                return ModelTurn('', (ModelToolCall(f'call-{self.turn}', name, {}),))
            self.final_messages = messages
            return ModelTurn('CPU is 24%.')
    client = DuplicateClient()
    answer = ''.join(McpToolSession(_Fallback(), client, host).stream_response('whats my cpu at'))
    assert answer == 'CPU 24%.'
    assert len(calls) == 1
    assert client.turn == 0

def test_unverified_app_launch_cannot_be_reported_as_opened(tmp_path, monkeypatch):
    base = _host(tmp_path)
    host = McpHost(base.registry, read_only=True, max_tools=8, allowed_actions=('app.open',))
    monkeypatch.setattr(host, 'call', lambda tool, args: {'name': 'app.open', 'ok': True, 'message': 'Launch request sent.', 'data': {'app': 'Discord', 'outcome': 'accepted', 'verified': False}})

    class AppClient:
        calls = 0

        def complete_with_tools(self, messages, *, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                name = next((tool['function']['name'] for tool in tools if tool['function']['name'].endswith('app__open')))
                return ModelTurn('', (ModelToolCall('app-call', name, {'app': 'Discord'}),))
            return ModelTurn('Discord is open.')
    answer = ''.join(McpToolSession(_Fallback(), AppClient(), host).stream_response('open discord'))
    assert 'Launch request sent.' in answer
    assert 'discord is open' not in answer.casefold()
    assert "couldn't confirm its window" not in answer

def test_spotify_resume_runs_status_launch_and_play_without_model_choice(tmp_path, monkeypatch):
    base = _host(tmp_path)
    host = McpHost(base.registry, read_only=True, max_tools=8, allowed_actions=('spotify.launch', 'spotify.play_pause'))
    calls = []

    def fake_call(tool, args):
        calls.append(tool.capability_id)
        if tool.capability_id == 'spotify.status':
            return {'ok': True, 'data': {'running': len(calls) > 2, 'playing': False}}
        if tool.capability_id == 'spotify.launch':
            return {'ok': True, 'data': {'running': True}}
        return {'ok': True, 'data': {'playing': True, 'now_playing': 'aespa - I Love You'}}
    monkeypatch.setattr(host, 'call', fake_call)

    class NoModelCalls:

        def complete_with_tools(self, *args, **kwargs):
            raise AssertionError('Spotify control should use the explicit routed workflow')
    for prompt in ('play my spotify', 'resume my spotify'):
        calls.clear()
        answer = ''.join(McpToolSession(_Fallback(), NoModelCalls(), host).stream_response(prompt))
        assert calls == ['spotify.status', 'spotify.launch', 'spotify.status', 'spotify.play_pause']
        assert 'I Love You' in answer

def test_capability_reply_uses_actual_allowlist(tmp_path):
    base = _host(tmp_path)
    host = McpHost(base.registry, read_only=True, allowed_actions=('app.open',))
    answer = ''.join(McpToolSession(_Fallback(), None, host).stream_response('you can open apps'))
    assert 'Yes.' in answer

def test_active_model_gpu_question_uses_implicit_model_id(tmp_path, monkeypatch):
    host = _host(tmp_path)
    tools = host.select_tools('is llama on the GPU')
    assert [tool.capability_id for tool in tools] == ['model.status']
    assert tools[0].openai_schema()['function']['parameters']['properties'] == {}
    calls = []

    def fake_call(tool, args):
        calls.append((tool.capability_id, dict(args)))
        return {'ok': True, 'message': "Model 'supervisor' is reachable. Verified on AMD Radeon RX 6600 XT.", 'data': {'placement_verified': True, 'selected_device_name': 'AMD Radeon RX 6600 XT'}}
    monkeypatch.setattr(host, 'call', fake_call)

    class NoModelCalls:

        def complete_with_tools(self, *args, **kwargs):
            raise AssertionError('active model status should use the resolved model directly')
    answer = ''.join(McpToolSession(_Fallback(), NoModelCalls(), host).stream_response('is llama on the GPU'))
    assert calls == [('model.status', {})]
    assert 'Verified on AMD Radeon RX 6600 XT' in answer

def test_started_notepad_reply_uses_process_evidence(tmp_path, monkeypatch):
    base = _host(tmp_path)
    host = McpHost(base.registry, read_only=True, allowed_actions=('app.open',))
    monkeypatch.setattr(host, 'call', lambda tool, args: {'name': 'app.open', 'ok': True, 'message': 'Started Notepad.', 'data': {'app': 'Notepad', 'outcome': 'process_started', 'process_id': 123, 'verified': False}})

    class AppClient:
        calls = 0

        def complete_with_tools(self, messages, *, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                name = next((tool['function']['name'] for tool in tools if tool['function']['name'].endswith('app__open')))
                return ModelTurn('', (ModelToolCall('open', name, {'app': 'Notepad'}),))
            return ModelTurn('The Notepad window is open.')
    answer = ''.join(McpToolSession(_Fallback(), AppClient(), host).stream_response('open notepad'))
    assert answer == 'Started Notepad.'

def test_open_and_type_is_blocked_without_partial_launch(tmp_path, monkeypatch):
    base = _host(tmp_path)
    host = McpHost(base.registry, read_only=True, allowed_actions=('app.open',))
    monkeypatch.setattr(host, 'call', lambda *args: (_ for _ in ()).throw(AssertionError('compound request must not launch only the app')))
    answer = ''.join(McpToolSession(_Fallback(), None, host).stream_response('can you open notepad and write hi'))
    assert "can't type" in answer and 'No action was taken' in answer

def test_model_failure_after_launch_keeps_action_evidence(tmp_path, monkeypatch):
    base = _host(tmp_path)
    host = McpHost(base.registry, read_only=True, allowed_actions=('app.open',))
    monkeypatch.setattr(host, 'call', lambda tool, args: {'name': 'app.open', 'ok': True, 'message': 'Launch request sent.', 'data': {'app': 'OneNote', 'outcome': 'accepted', 'verified': False}})

    class FailingFinal:
        calls = 0

        def complete_with_tools(self, messages, *, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn('', (ModelToolCall('open', tools[0]['function']['name'], {'app': 'OneNote'}),))
            raise ModelClientError('model disconnected')
    answer = ''.join(McpToolSession(_Fallback(), FailingFinal(), host).stream_response('open onenote'))
    assert 'Launch request sent.' in answer
    assert 'fallback' not in answer
