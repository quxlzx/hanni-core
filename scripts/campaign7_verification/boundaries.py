"""Independent exposed-development boundaries; no device or model startup."""
from __future__ import annotations
import hashlib
import json
import struct
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hanni.speech.microphone import MicrophoneCapture
from hanni.speech.stt import FasterWhisperTranscriber
from hanni.speech.vad import Utterance
from hanni.speech.live import TranscriptPump
from hanni.dashboard.voice import ManagedTranscriptPump, VoiceControl
from hanni.config.schema import SpeechConfig
from hanni.speech.pipeline import SpeechToTextPipeline
from hanni.speech.types import AudioChunk, TranscriptRecord, Transcription
from hanni.speech.vad import VadDecision
from dataclasses import replace
import queue
import uuid
from hanni.core.activity import Activity
from hanni.core.interaction import InteractionState
SOURCE_PATHS = ['src/hanni/speech/microphone.py', 'src/hanni/speech/stt.py', 'src/hanni/speech/live.py', 'src/hanni/dashboard/voice.py', 'src/hanni/core/interaction.py', 'src/hanni/speech/pipeline.py']

def source_hashes(root):
    return {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest() for name in SOURCE_PATHS}

class ControlledStream:

    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        self.owner.entered += 1
        return self

    def __exit__(self, *args):
        self.owner.closed += 1

class ControlledInputBackend:
    """Records the original device leaf without ever opening PortAudio."""

    def __init__(self):
        self.constructed = self.entered = self.closed = 0

    def RawInputStream(self, **kwargs):
        self.constructed += 1
        return ControlledStream(self)

def capture_pre_stopped(sample_rate=16000, block_samples=512):
    leaf = ControlledInputBackend()
    stop = threading.Event()
    stop.set()
    capture = MicrophoneCapture(sample_rate=sample_rate, block_samples=block_samples, backend=leaf)
    chunks = list(capture.chunks(stop_event=stop))
    return {'chunks': len(chunks), 'stream_constructed': leaf.constructed, 'stream_entered': leaf.entered, 'stream_closed': leaf.closed, 'scope': 'original MicrophoneCapture; controlled device leaf; no microphone'}

class ControlledDecoder:

    def __init__(self, text='controlled protocol response', error=None):
        self.calls = 0
        self.text = text
        self.error = error

    def transcribe(self, audio, **kwargs):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return ([SimpleNamespace(text=self.text)], SimpleNamespace(language='en', language_probability=1))

def stt_contract(sample_rate=16000, channels=1, samples=(11, -11, 8, -8), model_text='controlled protocol response', model_error=None):
    decoder = ControlledDecoder(model_text, model_error)
    transcriber = FasterWhisperTranscriber(model=decoder)
    utterance = Utterance(struct.pack('<' + 'h' * len(samples), *samples), 10, 10.01, sample_rate, channels)
    text = None
    error = None
    try:
        text = transcriber.transcribe(utterance).text
    except Exception as exc:
        error = type(exc).__name__
    return {'rejected': error is not None, 'typed_error': error, 'text': text, 'model_calls': decoder.calls, 'scope': 'original FasterWhisperTranscriber; controlled decoder; no ASR model'}

class FailingPipeline:

    def run(self, **kwargs):
        raise RuntimeError('owned test pipeline disconnected')

def failed_pump_snapshot():
    actual = TranscriptPump(FailingPipeline())
    managed = ManagedTranscriptPump(lambda: TranscriptPump(FailingPipeline()), actual)
    managed.start()
    actual.thread.join(timeout=1)
    if actual.thread.is_alive():
        raise RuntimeError('owned failure thread did not settle')
    controller = VoiceControl()
    controller.bind(managed, SimpleNamespace(), SimpleNamespace(), 'hanni')
    try:
        observed = controller.snapshot()
        observed['pump_running'] = managed.running()
        observed['scope'] = 'original failed TranscriptPump and VoiceControl; no device'
        return observed
    finally:
        controller.unbind(managed)
        managed.stop()

def synthesis_only_snapshot():
    measured, state = (Activity(), InteractionState())
    original_pump = SimpleNamespace(closed=False, paused=False, failed=False, running=lambda: True)
    controller = VoiceControl()
    controller.bind(original_pump, SimpleNamespace(), SimpleNamespace(), 'hanni')
    try:
        with patch('hanni.dashboard.voice.activity', measured), patch('hanni.dashboard.voice.interaction', state), state.synthesis():
            result = controller.snapshot()
            result.update(actual_playback_created=state.playback is not None, interaction_state=state.snapshot(), scope='original InteractionState.synthesis and VoiceControl; no playback/device/model')
            return result
    finally:
        controller.unbind(original_pump)

def continuous_segment_boundary():

    class StatefulVad:
        active = False
        resets = 0

        def process(self, chunk):
            started = not self.active
            self.active = True
            return VadDecision(started=started)

        def reset(self):
            self.active = False
            self.resets += 1
    base = SpeechConfig()
    speech = replace(base, block_samples=500, vad=replace(base.vad, max_utterance_seconds=0.0625, pre_roll_ms=0))
    vad = StatefulVad()
    pipe = SpeechToTextPipeline(speech=speech, raw_audio_retention_seconds=10, transcript_retention_seconds=10, microphone=object(), vad=vad, transcriber=SimpleNamespace(transcribe=lambda u: Transcription('controlled segment')), clock=lambda: 1.0)
    records = []
    for index in range(8):
        records.append(pipe.process_chunk(AudioChunk(b'\x01\x00' * 500, 16000, 1, index / 32)))
    return {'record_count': sum((x is not None for x in records)), 'vad_resets': vad.resets, 'scope': 'original pipeline and segmenter; controlled VAD/decoder; no model'}

def completed_pump_restart(first_record='owned-cycle-1', second_record='owned-cycle-2'):

    class FinitePipeline:
        runs = 0

        def run(self, **kwargs):
            self.runs += 1
            yield TranscriptRecord(first_record if self.runs == 1 else second_record, 5.0, 6.0)
    pipeline = FinitePipeline()
    pump = TranscriptPump(pipeline)
    pump.start()
    pump.thread.join(1)
    first = pump.get(timeout=0.1)
    pump.start()
    pump.thread.join(1)
    second = pump.get(timeout=0.1)
    pump.stop()
    return {'first': getattr(first, 'text', None), 'second': getattr(second, 'text', None), 'second_type': type(second).__name__, 'pipeline_runs': pipeline.runs, 'thread_closed': not pump.thread.is_alive()}

def stopped_pump_start():
    entries = []

    class ControlledPipeline:

        def run(self, **kwargs):
            entries.append(True)
            return iter(())
    pump = TranscriptPump(ControlledPipeline())
    pump.stop()
    pump.start()
    pump.thread.join(1)
    return {'pipeline_entries': len(entries), 'thread_closed': not pump.thread.is_alive()}

def managed_start_failure():
    old = SimpleNamespace(stop=lambda: None, thread=None)

    def failed_start():
        raise RuntimeError('owned reconnect startup failed')
    managed = ManagedTranscriptPump(lambda: SimpleNamespace(start=failed_start, stop=lambda: None, thread=None), old)
    managed.pause()
    try:
        managed.resume()
    except RuntimeError:
        pass
    result = {'paused': managed.paused, 'running': managed.running()}
    managed.stop()
    return result

def managed_closed_inflight():
    entered, release = (threading.Event(), threading.Event())

    def original_leaf_get(timeout=None):
        entered.set()
        if not release.wait(1):
            raise RuntimeError('owned barrier timed out')
        return 'owned stale queued record'
    pump = ManagedTranscriptPump(lambda: None, SimpleNamespace(get=original_leaf_get, stop=lambda: None, thread=None))
    observed = []

    def read():
        try:
            observed.append(pump.get(timeout=0.05))
        except queue.Empty:
            observed.append('discarded')
    thread = threading.Thread(target=read)
    thread.start()
    if not entered.wait(1):
        release.set()
        thread.join(1)
        raise RuntimeError('owned read did not enter')
    pump.stop()
    release.set()
    thread.join(1)
    return {'closed': pump.closed, 'outcome': observed, 'thread_closed': not thread.is_alive()}

def failed_voice_action(action):
    from hanni.speech.relevance import SpeechRelevanceClassifier
    from hanni.core.shutdown import EmergencyStop
    entries = []

    class FreshPipeline:

        def run(self, **kwargs):
            entries.append(True)
            return iter(())
    actual = TranscriptPump(FailingPipeline())
    managed = ManagedTranscriptPump(lambda: TranscriptPump(FreshPipeline()), actual)
    managed.start()
    actual.thread.join(1)
    if action == 'unmute':
        managed.pause()
    state, measured = (InteractionState(), Activity())
    playback = SimpleNamespace(active=True, stops=0)

    def stop_playback():
        playback.active = False
        playback.stops += 1
    playback.stop = stop_playback
    if action == 'interrupt':
        state.playback = playback
    classifier = SpeechRelevanceClassifier()
    controller = VoiceControl()
    controller.bind(managed, classifier, SimpleNamespace(context=SimpleNamespace(emergency_stop=EmergencyStop())), 'hanni')
    with patch('hanni.dashboard.voice.interaction', state), patch('hanni.dashboard.voice.activity', measured):
        before = controller.snapshot()
        error = None
        try:
            controller.execute({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'campaign7-independent-{action}')), 'action': action})
        except Exception as exc:
            error = type(exc).__name__
        after = controller.snapshot()
    controller.unbind(managed)
    managed.stop()
    return {'action': action, 'rejected': error is not None, 'error_class': error, 'before': before, 'after': after, 'fresh_pipeline_entries': len(entries), 'engaged_after': state.voice_engaged, 'playback_stops': playback.stops, 'scope': 'original failed pump/voice action/EmergencyStop; controlled pipeline/playback leaves'}

def pipeline_retention_end(mode):
    stop = threading.Event()
    now = [0.2]

    class ControlledMicrophone:

        def chunks(self, stop_event=None):
            for index in range(2 if mode == 'complete' else 3):
                yield AudioChunk(b'\t\x00' * 512, 16000, 1, index * 0.032)
            if mode == 'error':
                raise RuntimeError('owned source disconnected')
            if mode == 'cancel':
                stop_event.set()

    class ControlledVad:
        resets = 0

        def __init__(self):
            self.events = iter([VadDecision(started=True), VadDecision(ended=True), VadDecision(started=True)])

        def process(self, chunk):
            return next(self.events)

        def reset(self):
            self.resets += 1
    vad = ControlledVad()
    pipeline = SpeechToTextPipeline(speech=SpeechConfig(), raw_audio_retention_seconds=120, transcript_retention_seconds=120, microphone=ControlledMicrophone(), vad=vad, transcriber=SimpleNamespace(transcribe=lambda u: Transcription('owned synthetic utterance')), clock=lambda: now[0])
    error = None
    try:
        records = list(pipeline.run(stop_event=stop))
    except RuntimeError as exc:
        records = []
        error = type(exc).__name__
    now[0] = 180.0
    return dict(mode=mode, raw_audio_records=len(pipeline.audio_buffer), transcript_records=len(pipeline.transcript_buffer), segment_active=pipeline.segmenter.active, segment_recent_chunks=len(pipeline.segmenter._recent), vad_resets=vad.resets, cancelled=stop.is_set(), original_error=error, scope='original pipeline lifecycle; controlled PCM/VAD/decoder/device; ended references not owner audio')

def run_development(root, destination):
    root, destination = (Path(root), Path(destination))
    destination.mkdir(parents=True, exist_ok=False)
    before = source_hashes(root)
    probes = [('pre-stopped-256', capture_pre_stopped(16000, 256), {'stream_constructed': 0, 'stream_entered': 0}), ('pre-stopped-1024', capture_pre_stopped(16000, 1024), {'stream_constructed': 0, 'stream_entered': 0}), ('rate-11025', stt_contract(11025), {'rejected': True, 'model_calls': 0}), ('rate-44100', stt_contract(44100), {'rejected': True, 'model_calls': 0}), ('mono-positive', stt_contract(), {'rejected': False, 'model_calls': 1}), ('silence-positive', stt_contract(samples=(0, 0, 0, 0)), {'rejected': False, 'model_calls': 0, 'text': ''}), ('channel-negative', stt_contract(channels=3), {'rejected': True, 'model_calls': 0}), ('failed-pump', failed_pump_snapshot(), {'available': False, 'microphone_active': False}), ('continuous-cutoff', continuous_segment_boundary(), {'record_count': 4}), ('finished-pump-restart', completed_pump_restart(), {'second': 'owned-cycle-2', 'pipeline_runs': 2}), ('stopped-pump-start', stopped_pump_start(), {'pipeline_entries': 0}), ('failed-managed-start', managed_start_failure(), {'paused': True, 'running': False}), ('closed-inflight-record', managed_closed_inflight(), {'outcome': ['discarded'], 'thread_closed': True})]
    rows = []
    for cid, observed, expected in probes:
        checks = {key: observed.get(key) == value for key, value in expected.items()}
        rows.append(dict(id=cid, expected=expected, observed=observed, checks=checks, passed=all(checks.values())))
    receipt = dict(scope='independent controlled development, original implementations', source_before=before, source_after=source_hashes(root), cases=rows, passed=sum((x['passed'] for x in rows)), count=len(rows), physical_capture_calls=0, actual_asr_calls=0)
    (destination / 'RESULTS.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = run_development(Path(__file__).resolve().parents[2], args.out)
    print(json.dumps({key: result[key] for key in ('count', 'passed', 'physical_capture_calls', 'actual_asr_calls')}))
