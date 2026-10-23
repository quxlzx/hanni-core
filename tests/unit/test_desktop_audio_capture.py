"""The desktop loopback produces the PCM format consumed by VAD and STT."""
from __future__ import annotations
import sys
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from hanni.speech.microphone import MicrophoneCapture

def test_desktop_loopback_downmixes_stereo_to_mono_pcm16():

    class Recorder:

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def record(self, *, numframes):
            assert numframes == 2
            return np.array([[0.5, -0.5], [1.0, 1.0]], dtype=np.float32)
    loopback = SimpleNamespace(isloopback=True, recorder=lambda **kwargs: Recorder())
    speaker = SimpleNamespace(id='speaker-id')
    fake_soundcard = SimpleNamespace(default_speaker=lambda: speaker, get_microphone=lambda id, include_loopback: loopback)
    with patch.dict(sys.modules, {'soundcard': fake_soundcard}):
        chunk = next(MicrophoneCapture(device='desktop', block_samples=2).chunks(max_chunks=1))
    assert chunk.sample_rate == 16000
    assert chunk.channels == 1
    assert np.frombuffer(chunk.pcm16, dtype='<i2').tolist() == [0, 32767]
