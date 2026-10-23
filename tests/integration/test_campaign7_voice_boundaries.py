"""Prospective original voice boundary controls; no devices or actual models."""
from dataclasses import replace
import json
from pathlib import Path
import queue
import threading
from types import SimpleNamespace
import pytest
from hanni.config.schema import SpeechConfig
from hanni.core.activity import Activity
from hanni.core.interaction import InteractionState
from hanni.dashboard import voice as voice_module
from hanni.dashboard.voice import ManagedTranscriptPump, VoiceControl
from hanni.speech import microphone as microphone_module
from hanni.speech.live import PUMP_FINISHED, PumpFailure, TranscriptPump
from hanni.speech.microphone import MicrophoneCapture, MicrophoneError
from hanni.speech.relevance import SpeechRelevanceClassifier
from hanni.speech.stt import FasterWhisperTranscriber, SttError
from hanni.speech.tts import SubprocessTtsPlayback, TtsError
from hanni.speech.types import TranscriptRecord
from hanni.speech.vad import Utterance, VadDecision
from scripts.campaign7_voice.controls import CaptureBackend, Decoder, chunk, pipeline

@pytest.fixture(autouse=True)
def isolated_voice_state(monkeypatch):
    state, observed = (InteractionState(), Activity())
    monkeypatch.setattr(voice_module, 'interaction', state)
    monkeypatch.setattr(voice_module, 'activity', observed)
    monkeypatch.setattr(microphone_module, 'activity', observed)
    monkeypatch.setattr('hanni.speech.tts.interaction', state)
    monkeypatch.setattr('hanni.speech.tts.activity', observed)
    return state

@pytest.mark.parametrize('pre_stopped', [True, False])
def test_original_capture_stop_before_open_and_healthy_control(pre_stopped):
    stop = threading.Event()
    if pre_stopped:
        stop.set()
    backend = CaptureBackend()
    capture = MicrophoneCapture(backend=backend)
    items = list(capture.chunks(stop_event=stop, max_chunks=1))
    if pre_stopped:
        assert items == [] and backend.created == 0 and (backend.entered == 0)
    else:
        assert len(items) == 1 and backend.created == backend.entered == backend.exited == 1

def test_stop_during_open_closes_controlled_capture_without_forwarding():
    stop = threading.Event()
    backend = CaptureBackend(stop_on_enter=stop)
    assert list(MicrophoneCapture(backend=backend).chunks(stop_event=stop, max_chunks=1)) == []
    assert backend.entered == backend.exited == 1

def test_missing_capture_dependency_propagates_as_honest_device_failure():
    backend = CaptureBackend(fail_open=True)
    with pytest.raises(MicrophoneError, match='unavailable'):
        list(MicrophoneCapture(backend=backend).chunks(max_chunks=1))
    assert backend.created == 1 and backend.entered == 0

@pytest.mark.parametrize('rate', [8000, 22050, 44100, 16000])
def test_stt_original_pcm16_sample_rate_contract(rate):
    decoder = Decoder()
    transcriber = FasterWhisperTranscriber(model=decoder)
    utterance = Utterance(b'\x01\x00' * 1600, 0.0, 0.1, rate, 1)
    if rate == 16000:
        assert transcriber.transcribe(utterance).text == 'controlled transcript'
        assert len(decoder.calls) == 1
    else:
        with pytest.raises(ValueError, match='16000|16.?k|sample.rate'):
            transcriber.transcribe(utterance)
        assert decoder.calls == []

@pytest.mark.parametrize('pcm', [b'', b'\x00\x00' * 1600])
def test_digital_silence_has_no_decoder_call(pcm):
    decoder = Decoder()
    result = FasterWhisperTranscriber(model=decoder).transcribe(Utterance(pcm, 0.0, 0.1, 16000, 1))
    assert result.text == '' and decoder.calls == []

def test_decoder_failure_never_creates_successful_transcript():
    decoder = Decoder(error=RuntimeError('controlled decoder disconnected'))
    with pytest.raises(SttError, match='disconnected'):
        FasterWhisperTranscriber(model=decoder).transcribe(Utterance(b'\x01\x00' * 1600, 0.0, 0.1, 16000, 1))
    assert len(decoder.calls) == 1

def test_pipeline_after_decoder_failure_can_process_a_new_complete_utterance():
    events = iter([VadDecision(started=True), VadDecision(ended=True)] * 2)
    calls = []

    def transcribe(utterance):
        calls.append(True)
        if len(calls) == 1:
            raise SttError('controlled first decoding failure')
        return SimpleNamespace(text='new utterance', language='en', language_probability=0.99)
    pipe = pipeline(SimpleNamespace(process=lambda item: next(events)), transcriber=SimpleNamespace(transcribe=transcribe))
    assert pipe.process_chunk(chunk(0)) is None
    with pytest.raises(SttError):
        pipe.process_chunk(chunk(1))
    assert pipe.process_chunk(chunk(2)) is None
    record = pipe.process_chunk(chunk(3))
    assert record.text == 'new utterance' and len(pipe.transcript_buffer) == 1

def test_maximum_segment_cutoff_preserves_following_continuous_speech():

    class ContinuousVad:

        def __init__(self):
            self.active = False

        def process(self, item):
            decision = VadDecision(started=not self.active)
            self.active = True
            return decision

        def reset(self):
            self.active = False
    speech = SpeechConfig()
    speech = replace(speech, vad=replace(speech.vad, max_utterance_seconds=0.064, pre_roll_ms=0))
    pipe = pipeline(ContinuousVad(), speech=speech)
    records = [pipe.process_chunk(chunk(i)) for i in range(8)]
    assert sum((r is not None for r in records)) == 4

def test_completed_pump_reconnect_does_not_forward_the_previous_terminal():

    class Finite:

        def __init__(self):
            self.runs = 0

        def run(self, **kwargs):
            self.runs += 1
            yield TranscriptRecord(f'cycle-{self.runs}', 0.0, 1.0)
    original = Finite()
    pump = TranscriptPump(original)
    pump.start()
    pump.thread.join(1)
    assert not pump.thread.is_alive()
    assert pump.get(timeout=0.1).text == 'cycle-1'
    pump.start()
    pump.thread.join(1)
    assert not pump.thread.is_alive()
    assert pump.get(timeout=0.1).text == 'cycle-2'

def test_stopped_pump_start_does_not_enter_a_pipeline_with_cancelled_token():
    entries = []

    class Pipeline:

        def run(self, **kwargs):
            entries.append(True)
            return iter(())
    pump = TranscriptPump(Pipeline())
    pump.stop()
    pump.start()
    pump.thread.join(1)
    assert entries == []

@pytest.mark.parametrize('failure', ['factory', 'start'])
def test_failed_managed_reconnect_remains_muted(failure):
    old = SimpleNamespace(stop=lambda: None, thread=None)

    def factory():
        if failure == 'factory':
            raise RuntimeError('controlled factory failure')
        return SimpleNamespace(start=lambda: (_ for _ in ()).throw(RuntimeError('controlled start failure')), thread=None, stop=lambda: None)
    managed = ManagedTranscriptPump(factory, old)
    managed.pause()
    with pytest.raises(RuntimeError, match='controlled'):
        managed.resume()
    assert managed.paused and (not managed.running())

def test_closed_managed_pump_discards_an_inflight_transcript():
    entered, release = (threading.Event(), threading.Event())

    def get(timeout=None):
        entered.set()
        assert release.wait(1)
        return 'controlled stale transcript'
    managed = ManagedTranscriptPump(lambda: None, SimpleNamespace(get=get, stop=lambda: None, thread=None))
    observed = []

    def read():
        try:
            managed.get(timeout=0.01)
            observed.append('forwarded')
        except queue.Empty:
            observed.append('discarded')
    worker = threading.Thread(target=read)
    worker.start()
    assert entered.wait(1)
    managed.stop()
    release.set()
    worker.join(1)
    assert not worker.is_alive() and observed == ['discarded']

def test_managed_fresh_reconnect_drops_previous_state():
    initial = SimpleNamespace(stop=lambda: None, thread=None)
    fresh = SimpleNamespace(start=lambda: None, thread=None, get=lambda timeout=None: 'fresh')
    managed = ManagedTranscriptPump(lambda: fresh, initial)
    managed.pause()
    managed.resume()
    assert managed.get(timeout=0.01) == 'fresh' and (not managed.paused)

def test_failed_pipeline_is_reported_as_failure_before_terminal():

    class Failed:

        def run(self, **kwargs):
            raise SttError('controlled original failure')
    pump = TranscriptPump(Failed())
    pump.start()
    pump.thread.join(1)
    assert isinstance(pump.get(timeout=0.1), PumpFailure)
    assert pump.get(timeout=0.1) is PUMP_FINISHED

def test_voice_controller_unbound_never_claims_listening_or_audible():
    state = VoiceControl().snapshot()
    assert state['state'] == 'disabled' and (not state['microphone_active'])
    assert state['metrics']['first_audible_ms'] is None
    assert not any(state['actions'].values())

def test_voice_controller_current_source_metrics_are_not_acoustic_latency():
    controller = VoiceControl(clock=lambda: 5.0)
    controller.transcript_observed(TranscriptRecord('Hanni', 1.0, 2.0), True)
    assert controller.snapshot()['metrics']['wake_to_listening_ms'] == 3000.0
    assert controller.snapshot()['metrics']['first_audible_ms'] is None

def test_failed_playback_reports_failure_not_audible_success():
    process = SimpleNamespace(poll=lambda: 4, wait=lambda timeout=None: 4, stderr=None)
    playback = SubprocessTtsPlayback(process)
    with pytest.raises(TtsError, match='exit code4|exit code 4'):
        playback.wait(timeout=0.01)
    assert not playback.active
