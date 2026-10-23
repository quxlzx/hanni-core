"""Supplemental requested voice scenarios through original controlled APIs."""
from dataclasses import replace
import queue
import threading
from types import SimpleNamespace
import pytest
from hanni.config.schema import SpeechConfig
from hanni.dashboard.voice import ManagedTranscriptPump, VoiceControl
from hanni.speech.attention import AttentiveTextBridge, SpeechAttentionRouter
from hanni.speech.barge_in import BargeInClassifier
from hanni.speech.live import TranscriptPump
from hanni.speech.microphone import MicrophoneCapture
from hanni.speech.relevance import SpeechRelevanceClassifier
from hanni.speech.stt import FasterWhisperTranscriber, SttError
from hanni.speech.tts import SubprocessTtsPlayback
from hanni.speech.types import TranscriptRecord, Transcription
from hanni.speech.vad import Utterance, VadDecision
from scripts.campaign7_voice.controls import Decoder, chunk, pipeline

def test_pre_stopped_desktop_source_never_imports_or_captures_loopback(monkeypatch):
    capture = MicrophoneCapture(device='desktop')
    monkeypatch.setattr(capture, '_desktop_chunks', lambda **kwargs: pytest.fail('Stopped capture entered the desktop leaf.'))
    stop = threading.Event()
    stop.set()
    assert list(capture.chunks(stop_event=stop)) == []

def test_original_attentive_bridge_routes_multiple_turns_and_disengages(monkeypatch):
    from hanni.core.interaction import InteractionState
    monkeypatch.setattr('hanni.core.interaction.interaction', InteractionState())
    calls = []
    session = SimpleNamespace(stream_response=lambda prompt, **kwargs: (calls.append(prompt), iter(['controlled assistant response']))[1])
    bridge = AttentiveTextBridge(SpeechAttentionRouter(SpeechRelevanceClassifier()), session)
    phrases = ['Background conversation about the garden.', 'Hanni, explain available memory.', 'Could you give an example?', 'Thanks.', 'That is all.', 'The garden needs water.']
    outputs = []
    for index, text in enumerate(phrases):
        routed, stream = bridge.handle(TranscriptRecord(text, index, index + 0.5))
        outputs.append((routed.decision.relevant, ''.join(stream)))
        if routed.event is not None:
            assert text not in str(routed.event.payload)
    assert len(calls) == 2
    assert [row[0] for row in outputs] == [False, True, True, False, False, False]

def test_actual_configured_thirty_second_cutoff_retains_next_segment():

    class Continuous:
        active = False

        def process(self, item):
            result = VadDecision(started=not self.active)
            self.active = True
            return result

        def reset(self):
            self.active = False
    lengths = []

    def transcribe(utterance):
        lengths.append(len(utterance.pcm16) / 32000)
        return Transcription('controlled long segment')
    pipe = pipeline(Continuous(), transcriber=SimpleNamespace(transcribe=transcribe))
    for index in range(1876):
        pipe.process_chunk(chunk(index))
    assert len(lengths) == 2 and all((30 <= seconds < 30.033 for seconds in lengths))

def test_controlled_model_timeout_is_a_typed_failure_not_transcription():
    decoder = Decoder(error=TimeoutError('controlled model timeout'))
    with pytest.raises(SttError, match='timeout'):
        FasterWhisperTranscriber(model=decoder).transcribe(Utterance(b'\x01\x00' * 512, 0.0, 0.032, 16000, 1))
    assert len(decoder.calls) == 1

def test_muting_waits_for_inflight_decoder_and_refuses_overlapping_reconnect():
    started, release, exited = (threading.Event(), threading.Event(), threading.Event())

    class Input:

        def chunks(self, *, stop_event):
            try:
                for index in range(3):
                    if stop_event.is_set():
                        return
                    yield chunk(index)
            finally:
                exited.set()
    events = iter([VadDecision(started=True), VadDecision(ended=True)])

    def decode(utterance):
        started.set()
        assert release.wait(2)
        return Transcription('controlled late transcript')
    original = pipeline(SimpleNamespace(process=lambda item: next(events)), transcriber=SimpleNamespace(transcribe=decode))
    original.microphone = Input()
    pump = TranscriptPump(original)
    managed = ManagedTranscriptPump(lambda: pytest.fail('Capture overlap'), pump)
    managed.start()
    try:
        assert started.wait(1)
        managed.pause()
        assert managed.paused and managed.running() and (not exited.is_set())
        with pytest.raises(RuntimeError, match='still stopping'):
            managed.resume()
    finally:
        release.set()
        pump.thread.join(1)
        managed.stop()
    assert exited.is_set() and (not managed.running())

def test_managed_start_failure_cleans_up_the_new_owned_candidate():
    cleaned = []

    def fail():
        raise RuntimeError('controlled start rejected')
    fresh = SimpleNamespace(start=fail, stop=lambda: cleaned.append(True), thread=None)
    old = SimpleNamespace(stop=lambda: None, thread=None)
    managed = ManagedTranscriptPump(lambda: fresh, old)
    managed.pause()
    with pytest.raises(RuntimeError):
        managed.resume()
    assert cleaned == [True] and managed.paused and (managed.pump is old)

def test_failure_marker_has_no_transcript_or_backend_error_content():

    class Failed:

        def run(self, **kwargs):
            raise RuntimeError('controlled private-looking error text')
    pump = TranscriptPump(Failed())
    managed = ManagedTranscriptPump(lambda: None, pump)
    managed.start()
    pump.thread.join(1)
    controller = VoiceControl()
    controller.bind(managed, None, None, 'hanni')
    try:
        state = controller.snapshot()
        assert pump.failed is True and (not state['available'])
        assert 'private-looking' not in str(state)
        assert state['metrics']['first_audible_ms'] is None
    finally:
        controller.unbind(managed)
        managed.stop()

@pytest.mark.parametrize('text,spoken,interrupt', [('Stop.', 'Stop.', True), ('The result contains three observations.', 'The result contains three observations.', False), ('Wait, Hanni, make it shorter.', 'The result contains three observations.', True)])
def test_original_barge_decision_controls_only_an_owned_playback_leaf(monkeypatch, text, spoken, interrupt):
    from hanni.core.activity import Activity
    from hanni.core.interaction import InteractionState
    monkeypatch.setattr('hanni.speech.tts.interaction', InteractionState())
    monkeypatch.setattr('hanni.speech.tts.activity', Activity())
    leaf = SimpleNamespace(code=None, terminated=0, stderr=None)
    leaf.poll = lambda: leaf.code

    def terminate():
        leaf.terminated += 1
        leaf.code = -15
    leaf.terminate = terminate
    leaf.wait = lambda timeout=None: leaf.code
    playback = SubprocessTtsPlayback(leaf)
    decision = BargeInClassifier().classify(text, spoken_text=spoken)
    assert decision.interrupt is interrupt
    if decision.interrupt:
        playback.stop()
    assert leaf.terminated == int(interrupt)
    if interrupt:
        assert not playback.active
    else:
        playback.stop()
