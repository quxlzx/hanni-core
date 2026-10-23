from dataclasses import replace
import json
from unittest.mock import Mock, patch
import numpy as np
import pytest
from hanni.config.schema import TtsConfig
from hanni.speech.australian import WindowsAustralianTts, _SCRIPT
from hanni.speech.neural_worker import render_chunks
from hanni.speech.tts import TtsError, create_tts

def test_pitch_shift_changes_frequency_and_compensates_generation_speed():
    sample_rate = 24000
    source = np.sin(2 * np.pi * 440 * np.arange(sample_rate) / sample_rate)
    engine = Mock()
    engine.create.return_value = (source, sample_rate)
    payload = dict(chunks=['hello'], speed=1.0, language='en-gb', volume=100, pitch_semitones=2.0)
    with patch('hanni.speech.neural_worker.synthesizer', return_value=(engine, 'voice')):
        samples, rate = next(render_chunks(payload))
    spectrum = np.abs(np.fft.rfft(samples))
    peak = np.fft.rfftfreq(len(samples), 1 / rate)[np.argmax(spectrum)]
    factor = 2 ** (2 / 12)
    assert abs(peak - 440 * factor) < 2
    assert engine.create.call_args.kwargs['speed'] == pytest.approx(1 / factor)
    assert np.isfinite(samples).all()

def test_missing_australian_pack_preserves_working_voice_then_detects_install(tmp_path, caplog):
    config = TtsConfig(backend='windows_australian', voice='Catherine', language='en-au', pitch_semitones=2)
    engine = create_tts(config, data_dir=tmp_path)
    assert isinstance(engine, WindowsAustralianTts)
    assert engine.fallback.config.language == 'en-gb'
    assert engine.fallback.config.voice == 'hanni'
    assert engine.fallback.config.pitch_semitones == 2
    engine.fallback = Mock()
    proc = Mock()
    proc.poll.return_value = None
    proc.terminate.side_effect = lambda: setattr(proc.poll, 'return_value', 1)
    with patch('hanni.speech.australian.australian_voice', side_effect=[None, 'installed-token']), patch('hanni.speech.australian._powershell_executable', return_value='powershell.exe'), patch('hanni.speech.australian.subprocess.Popen', return_value=proc):
        engine.start('before install')
        engine.fallback.start.assert_called_once_with('before install')
        playback = engine.start('after install')
        assert json.loads(proc.stdin.write.call_args.args[0])['token'] == 'installed-token'
        playback.stop()
    assert 'British' in caplog.text

def test_missing_pack_strict_mode_reports_install_step(tmp_path):
    engine = WindowsAustralianTts(replace(TtsConfig(), sapi_fallback=False), data_dir=tmp_path)
    with patch('hanni.speech.australian.australian_voice', return_value=None):
        with pytest.raises(TtsError, match='Add voices'):
            engine.start('hello')

def test_australian_speech_keeps_text_out_of_script_and_escapes_markup(tmp_path):
    engine = WindowsAustralianTts(TtsConfig(pitch_semitones=2), data_dir=tmp_path)
    proc = Mock()
    proc.poll.return_value = None
    proc.terminate.side_effect = lambda: setattr(proc.poll, 'return_value', 1)
    text = '<voice name="another">hello</voice> $(Write-Host bad) & friends'
    with patch('hanni.speech.australian.australian_voice', return_value='installed-token'), patch('hanni.speech.australian._powershell_executable', return_value='powershell.exe'), patch('hanni.speech.australian.subprocess.Popen', return_value=proc) as popen:
        playback = engine.start(text)
        payload = json.loads(proc.stdin.write.call_args.args[0])
        assert payload['chunks'] == [text]
        assert payload['pitch'] == 2
        assert payload['output'] is None
        assert text not in ' '.join(popen.call_args.args[0])
        assert 'SecurityElement]::Escape' in _SCRIPT
        playback.stop()
