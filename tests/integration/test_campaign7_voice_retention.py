"""Original owned pipeline lifecycle cleanup; no personal audio or real model."""
import threading
from types import SimpleNamespace
import pytest
from hanni.speech.types import Transcription
from hanni.speech.vad import VadDecision
from scripts.campaign7_voice.controls import chunk, pipeline

@pytest.mark.parametrize('ending', ['complete', 'once', 'error', 'stop', 'pre_stopped'])
def test_owned_pipeline_end_releases_its_ephemeral_perception(ending):
    stop = threading.Event()
    reset = []
    events = iter([VadDecision(started=True), VadDecision(ended=True), VadDecision(started=True)])
    vad = SimpleNamespace(process=lambda item: next(events), reset=lambda: reset.append(True))
    pipe = pipeline(vad)
    if ending == 'pre_stopped':
        pipe.process_chunk(chunk(0))
        pipe.process_chunk(chunk(1))
        stop.set()

    class Input:

        def chunks(self, *, stop_event):
            if stop_event.is_set():
                return
            yield chunk(0)
            yield chunk(1)
            if ending in {'error', 'stop'}:
                yield chunk(2)
                if ending == 'error':
                    raise OSError('controlled capture disconnected')
                stop_event.set()
    pipe.microphone = Input()
    if ending == 'error':
        with pytest.raises(OSError, match='disconnected'):
            list(pipe.run(stop_event=stop))
    else:
        records = list(pipe.run(stop_event=stop, once=ending == 'once'))
        if ending != 'pre_stopped':
            assert records[0].text == 'controlled transcript'
    assert len(pipe.audio_buffer) == len(pipe.transcript_buffer) == 0
    assert not pipe.segmenter.active and (not pipe.segmenter._recent)
    assert reset == [True]

def test_diagnostic_process_chunk_retains_its_existing_buffer_contract():
    events = iter([VadDecision(started=True), VadDecision(ended=True)])
    pipe = pipeline(SimpleNamespace(process=lambda item: next(events)))
    pipe.process_chunk(chunk(0))
    record = pipe.process_chunk(chunk(1))
    assert record.text == 'controlled transcript'
    assert len(pipe.audio_buffer) == 2 and len(pipe.transcript_buffer) == 1

def test_older_injected_vad_without_reset_still_releases_owned_buffers():
    events = iter([VadDecision(started=True), VadDecision(ended=True)])
    pipe = pipeline(SimpleNamespace(process=lambda item: next(events)))
    pipe.microphone = SimpleNamespace(chunks=lambda **kwargs: iter([chunk(0), chunk(1)]))
    assert len(list(pipe.run())) == 1
    assert len(pipe.audio_buffer) == len(pipe.transcript_buffer) == 0
