"""Controlled safety/concurrency checks, never physical audio latency evidence."""
from pathlib import Path
import queue
import threading
import time
from types import SimpleNamespace
import pytest
from hanni.core.response_stream import FinalSentence, SentenceBuffer, TurnCancelled, cancellation_scope, check_cancelled, final_sentences
from hanni.core.orchestrator import TextSession
from hanni.core.responsiveness import TurnTimings, turn_scope, mark
from hanni.speech.response import ResponsePump, deliver_response
from hanni.speech.barge_in import BargeInClassifier
from hanni.speech.types import TranscriptRecord
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.models.client import ModelTurn, ModelToolCall
from hanni.reliability.execution import close_service
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def host(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    host = McpHost(build_default_registry(config), allowed_actions=('app.open', 'spotify.next'))
    yield host
    close_service(tmp_path)

def test_sentence_boundary_handles_decimal_and_split_tags():
    buffer = SentenceBuffer()
    assert buffer.feed('RAM is 71.') == []
    assert buffer.feed('5 percent. Next ') == ['RAM is 71.5 percent.']
    assert buffer.feed('answer.<thi') == []
    assert buffer.feed('nk>Never speak this. ') == ['Next answer.']
    assert buffer.feed('</thi') == []
    assert buffer.feed('nk>Final sentence.', final=True) == ['Final sentence.']

def test_hidden_reasoning_never_reaches_final_stream_or_history():

    class Client:

        def stream_chat(self, *a, **k):
            yield '<thi'
            yield 'nk>Invent an action.</think>I opened Notepad. The capital is Paris.'
    session = TextSession(Client())
    answer = ''.join(session.stream_response('What is the capital of France?'))
    assert 'Invent' not in answer and 'opened Notepad' not in answer
    assert answer == "I haven't verified an action for that request. The capital is Paris."
    assert session.history[-1]['content'] == answer

def test_knowledge_has_no_tool_execution(host):

    class Client:

        def stream_chat(self, *a, **k):
            yield 'A compiler translates source code.'

        def complete_with_tools(self, *a, **k):
            raise AssertionError('No tool-selection call needed.')
    client = Client()
    session = McpToolSession(TextSession(client), client, host)
    host.call = lambda *a, **k: pytest.fail('Knowledge must not execute a tool.')
    assert ''.join(session.stream_response('Explain what a compiler does.')) == 'A compiler translates source code.'

def test_discovery_cannot_expose_writes_or_rewrite_action_arguments(host):
    before = host.route('Open Notepad.').tools
    discovered = host.rediscover('delete a file and run powershell', owner_query='What is my current CPU usage?')
    assert all((tool.risk == 'read_only' for tool in discovered))
    assert not any((tool.capability_id in {'powershell.run', 'file.delete', 'app.open'} for tool in discovered))
    pinned = host.rediscover('open Chrome', owner_query='Open Notepad.')
    assert before[0].fixed_arguments == next((t for t in pinned if t.capability_id == 'app.open')).fixed_arguments
    assert host.rediscover('processor load', owner_query='Delete the entire drive.') == ()
    assert len(discovered) <= host.max_tools

def test_typo_correction_does_not_change_literal_path_or_negated_action(host):
    original = host.route('Read C:\\Temp\\procesor.txt')
    assert all(('processor.txt' not in str(tool.fixed_arguments) for tool in original.tools))
    assert host.route('Do not delete my files; show CPU usage.').status != 'blocked'

def test_dispatch_guard_blocks_cancelled_action_even_after_discovery(host):
    tool = host.route('Open Notepad.').tools[0]
    called = []
    definition = host.registry.get(tool.capability_id)
    from dataclasses import replace
    host.registry.unregister(tool.capability_id, expected=definition)
    host.registry.register(replace(definition, handler=lambda *a: called.append(True)))
    cancelled = threading.Event()
    cancelled.set()
    with cancellation_scope(cancelled):
        result = host.call(tool, {})
    assert not result['ok'] and (not called)
    assert 'cancelled' in result['message']

def test_model_rediscovery_is_bounded_and_only_supplies_metadata(host, monkeypatch):
    from hanni.mcp.host import RoutingDecision
    monkeypatch.setattr(host, 'route', lambda *a, **k: RoutingDecision((), 'clarification', 'low', (), (), ()))
    tool = host._as_tool(host.registry.get('system.stats'))
    discovered, executed, sizes = ([], [], [])
    monkeypatch.setattr(host, 'rediscover', lambda query, **k: discovered.append(query) or (tool,))
    monkeypatch.setattr(host, 'call', lambda t, a: executed.append(t.capability_id) or {'ok': True, 'message': 'Measured CPU/RAM.', 'data': {'cpu_percent': 12.0, 'ram_percent': 48.0}, 'verification': {'status': 'VERIFIED', 'scope': 'current_resource_snapshot'}})

    class Client:

        def complete_with_tools(self, messages, *, tools, **kwargs):
            sizes.append(len(tools))
            if len(sizes) == 1:
                return ModelTurn('I will pretend to launch an app.', (ModelToolCall('discover', 'hanni__discover', {'query': 'current CPU RAM utilization'}),))
            if len(sizes) == 2:
                return ModelTurn('', (ModelToolCall('measure', tool.wire_name, {}),))
            return ModelTurn('CPU is measured.')
    client = Client()
    session = McpToolSession(TextSession(client), client, host)
    answer = ''.join(session.stream_response('Inspect my current working set.'))
    assert len(discovered) == 1 and executed == ['system.stats']
    assert 'pretend' not in answer and '12' in answer and ('48' in answer)
    assert max(sizes) <= 8 and session.last_discovery == ('system.stats',)

def test_workflow_handoff_saves_plan_without_executing_steps(host):
    saved = []

    class Client:

        def stream_chat(self, *a, **k):
            pytest.fail('Workflow handoff must use the controller.')
    client = Client()
    session = McpToolSession(TextSession(client), client, host)
    session.workflow_submit = lambda prompt: saved.append(prompt) or 'Goal saved for plan review; no steps were executed.'
    answer = ''.join(session.stream_response('Monitor the CPU until I return.'))
    assert saved and 'no steps were executed' in answer
    assert session._turn_results == []

class Playback:

    def __init__(self, active=False):
        self._active, self.cancelled = (active, False)

    @property
    def active(self):
        return self._active

    def wait(self, **kwargs):
        pass

    def stop(self):
        self._active, self.cancelled = (False, True)

def test_first_sentence_reaches_tts_before_generation_finishes():
    spoken, release, finished = ([], threading.Event(), threading.Event())

    def response():
        yield FinalSentence('The checked value is 42.')
        assert release.wait(2), 'TTS waited for the entire response.'
        yield FinalSentence(' The second sentence is also checked.')
        finished.set()

    def start(text):
        spoken.append(text)
        assert not finished.is_set() if len(spoken) == 1 else True
        release.set()
        return Playback()
    result = deliver_response(response(), tts=SimpleNamespace(start=start), poll_seconds=0.005)
    assert len(spoken) == 2 and (not result.interrupted) and finished.is_set()

def test_barge_in_clears_queued_speech_and_prevents_late_response():
    release, spoken, playback = (threading.Event(), [], Playback(active=True))

    def response():
        yield FinalSentence('The first checked result.')
        yield FinalSentence(' This queued result must not be spoken.')
        release.wait(2)
        check_cancelled()
        yield FinalSentence(' This stale result must not be spoken.')

    def start(text):
        spoken.append(text)
        return playback

    def get(timeout=None):
        if spoken:
            return TranscriptRecord('wait', 1, 2)
        raise queue.Empty()
    result = deliver_response(response(), tts=SimpleNamespace(start=start), pump=SimpleNamespace(get=get), barge=BargeInClassifier(), poll_seconds=0.005)
    release.set()
    assert result.interrupted and playback.cancelled
    assert spoken == ['The first checked result.']

def test_cancellation_during_model_wait_prevents_future_speech():
    release = threading.Event()

    def response():
        release.wait(2)
        yield FinalSentence('Late answer.')
    pump = ResponsePump(response())
    pump.start()
    pump.cancel()
    release.set()
    pump.thread.join(2)
    assert pump.done.is_set() and pump.queue.empty()

def test_dashboard_interrupt_cancels_generation_before_speech_starts():
    from hanni.dashboard.voice import VoiceControl
    from hanni.core.interaction import interaction
    cancelled = threading.Event()
    controller = VoiceControl()
    controller.pump = SimpleNamespace(closed=False, failed=False, paused=False)
    controller.classifier = SimpleNamespace()
    controller.registry = SimpleNamespace()
    with interaction.condition:
        interaction.response_cancel_event = cancelled
        interaction.playback = None
    try:
        controller._apply('interrupt')
        assert cancelled.is_set()
    finally:
        with interaction.condition:
            interaction.response_cancel_event = None

def test_echo_does_not_cancel_but_emergency_stop_does():
    texts = []
    play = Playback(active=True)
    count = [0]

    def get(timeout=None):
        count[0] += 1
        return TranscriptRecord('The verified system is ready.' if count[0] == 1 else 'stop everything', 1, 2)
    result = deliver_response(iter([FinalSentence('The verified system is ready.')]), tts=SimpleNamespace(start=lambda text: texts.append(text) or play), pump=SimpleNamespace(get=get), barge=BargeInClassifier(), emergency=lambda text: text == 'stop everything', poll_seconds=0.005)
    assert result.interrupted and result.pending.text == 'stop everything'
    assert count[0] == 2 and play.cancelled

def test_dispatch_metric_is_not_mislabelled_as_audible_onset():
    timing = TurnTimings(speech_ended_at=time.monotonic())
    with turn_scope(timing):
        mark('first_tts_dispatch')
    first = timing.snapshot()['vad_segment_end_to_tts_dispatch_ms']
    time.sleep(0.01)
    snapshot = timing.snapshot()
    assert snapshot['vad_segment_end_to_tts_dispatch_ms'] == first
    assert snapshot['audible_onset_ms'] is None
    assert snapshot['audible_onset_status'] == 'NOT MEASURED'
