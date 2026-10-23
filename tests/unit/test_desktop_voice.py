import queue
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.core.activity import Activity
from hanni.core.interaction import InteractionState
from hanni.dashboard import voice as voice_module
from hanni.dashboard.voice import ManagedTranscriptPump, VoiceControl
from hanni.speech.live import TranscriptPump
from hanni.speech.relevance import SpeechRelevanceClassifier

@pytest.fixture(autouse=True)
def voice_state(monkeypatch):
    state = InteractionState()
    monkeypatch.setattr(voice_module, 'interaction', state)
    monkeypatch.setattr(voice_module, 'activity', Activity())
    return state

class Pipeline:

    def __init__(self):
        self.started = threading.Event()
        self.closed = threading.Event()

    def run(self, *, stop_event):
        self.started.set()
        try:
            while not stop_event.wait(0.01):
                if False:
                    yield None
        finally:
            self.closed.set()

def test_mute_closes_owned_capture_and_resume_uses_a_fresh_pipeline():
    initial = Pipeline()
    fresh = Pipeline()
    managed = ManagedTranscriptPump(lambda: TranscriptPump(fresh), TranscriptPump(initial))
    managed.start()
    assert initial.started.wait(2)
    managed.pause()
    assert initial.closed.is_set() and (not managed.running())
    with pytest.raises(queue.Empty):
        managed.get(timeout=0.01)
    managed.resume()
    assert fresh.started.wait(2) and (not managed.paused)
    managed.stop()
    assert fresh.closed.is_set()

def test_resume_cannot_overlap_a_transcription_still_stopping():
    managed = ManagedTranscriptPump(lambda: pytest.fail('No second capture may start'), SimpleNamespace(stop=lambda: None, thread=SimpleNamespace(is_alive=lambda: True)))
    managed.pause()
    with pytest.raises(RuntimeError, match='still stopping'):
        managed.resume()
    assert managed.paused

def test_muted_consumer_retains_queue_wait_instead_of_busy_spinning():
    managed = ManagedTranscriptPump(lambda: None, SimpleNamespace(stop=lambda: None, thread=None))
    managed.pause()
    started = time.monotonic()
    with pytest.raises(queue.Empty):
        managed.get(timeout=0.04)
    assert time.monotonic() - started >= 0.03

def test_inflight_old_pump_result_is_discarded_after_mute_resume():
    entered, release = (threading.Event(), threading.Event())

    def old_get(timeout):
        entered.set()
        assert release.wait(2)
        return 'stale pre-mute transcript'
    old = SimpleNamespace(get=old_get, stop=lambda: None, thread=None)
    new = SimpleNamespace(start=lambda: None)
    managed = ManagedTranscriptPump(lambda: new, old)
    result = []

    def read():
        try:
            result.append(managed.get(timeout=0.01))
        except queue.Empty:
            result.append('discarded')
    reader = threading.Thread(target=read)
    reader.start()
    assert entered.wait(2)
    managed.pause()
    managed.resume()
    release.set()
    reader.join(2)
    assert result == ['discarded']

def test_dashboard_voice_controls_do_not_start_a_missing_session():
    voice = VoiceControl()
    assert voice.snapshot()['state'] == 'disabled'
    assert not any(voice.snapshot()['actions'].values())
    with pytest.raises(RuntimeError, match='not running'):
        voice.execute({'id': str(uuid4()), 'action': 'unmute'})

def test_manual_listen_uses_original_classifier_and_safe_mode_gate(voice_state):
    voice = VoiceControl()
    classifier = SpeechRelevanceClassifier()
    guarded = []
    registry = SimpleNamespace(context=SimpleNamespace(emergency_stop=SimpleNamespace(guard=guarded.append)))
    pump = SimpleNamespace(closed=False, paused=False, running=lambda: True)
    voice.bind(pump, classifier, registry, 'hanni')
    try:
        request = {'id': str(uuid4()), 'action': 'listen'}
        assert voice.execute(request)['state'] == 'listening'
        assert classifier.is_engaged() and len(guarded) == 1
        voice.execute(request)
        assert len(guarded) == 1
        with pytest.raises(ValueError, match='different action'):
            voice.execute({**request, 'action': 'mute'})
    finally:
        voice.unbind(pump)
        voice_state.engaged(False)

def test_muting_is_not_reported_as_muted_before_capture_has_stopped():
    voice = VoiceControl()
    pump = SimpleNamespace(closed=False, paused=True, running=lambda: True)
    voice.bind(pump, None, None, None)
    try:
        state = voice.snapshot()
        assert state['state'] == 'muting' and (not state['muted'])
        assert not state['actions']['unmute']
        pump.running = lambda: False
        assert voice.snapshot()['muted'] and voice.snapshot()['actions']['unmute']
    finally:
        voice.unbind(pump)

def test_interrupt_stops_existing_playback_without_creating_speech(voice_state):
    voice = VoiceControl()
    stopped = []
    playback = SimpleNamespace(active=True, stop=lambda: stopped.append(True))
    pump = SimpleNamespace(closed=False, paused=False, running=lambda: True)
    voice.bind(pump, None, None, None)
    with voice_state.condition:
        previous = voice_state.playback
        voice_state.playback = playback
    try:
        request = {'id': str(uuid4()), 'action': 'interrupt'}
        voice.execute(request)
        voice.execute(request)
        assert stopped == [True]
        assert voice.metrics['interrupt_ms'] is not None
        assert voice.metrics['first_audible_ms'] is None
    finally:
        with voice_state.condition:
            voice_state.playback = previous
        voice.unbind(pump)

def test_observed_timings_require_audio_timestamps_and_do_not_invent_audibility():
    now = [10.0]
    voice = VoiceControl(clock=lambda: now[0])
    voice.transcript_observed(SimpleNamespace(ended_at=0), True)
    assert voice.metrics['wake_to_listening_ms'] is None
    voice.transcript_observed(SimpleNamespace(ended_at=9.75), True)
    assert voice.metrics['wake_to_listening_ms'] == 250
    now[0] = 10.1
    voice.response_observed()
    assert voice.metrics['end_to_response_ms'] == 350
    assert voice.metrics['first_audible_ms'] is None
    voice.audio_failure()
    assert voice.metrics['audio_failures'] == 1
