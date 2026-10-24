"""Voice safety/lifecycle checks without downloading models or opening audio."""
import json
import subprocess
import sys
from dataclasses import replace
from unittest.mock import ANY, Mock, patch
import pytest
from hanni.config.schema import TtsConfig, ConfigError, parse_hanni
from hanni.core.activity import activity
from hanni.core.interaction import interaction
from hanni.speech.neural import KokoroTts, NeuralPlayback
from hanni.speech.neural_worker import play, render_chunks, main
from hanni.speech.tts import TtsError, WindowsSapiTts, create_tts

def config(**kwargs):
    return replace(TtsConfig(backend='kokoro', voice='hanni'), **kwargs)

def test_factory_keeps_legacy_backend_and_resolves_neural_data_directory(tmp_path):
    assert isinstance(create_tts(TtsConfig()), WindowsSapiTts)
    engine = create_tts(config(), data_dir=tmp_path)
    assert engine.directory == tmp_path / 'voice'

def test_missing_assets_use_sapi_once_warned_and_can_fail_closed(tmp_path, caplog):
    engine = KokoroTts(config(), data_dir=tmp_path)
    engine.fallback = Mock()
    engine.start('hello')
    engine.start('again')
    assert engine.fallback.start.call_count == 2
    assert caplog.text.count('using Windows SAPI') == 1
    strict = KokoroTts(config(sapi_fallback=False), data_dir=tmp_path)
    with pytest.raises(TtsError, match=r'python scripts/setup_hanni_voice\.py'):
        strict.start('hello')
    assert not strict.start('  ').active

def test_neural_text_is_stdin_data_and_start_is_cancellable(tmp_path):
    engine = KokoroTts(config(), data_dir=tmp_path)
    proc = Mock()
    proc.poll.return_value = None
    text = 'Hello "there"; $(Write-Host injected)'
    with patch.object(engine, 'unavailable_reason', return_value=None), patch('hanni.speech.neural.subprocess.Popen', return_value=proc) as popen:
        playback = engine.start(text)
        payload = json.loads(proc.stdin.write.call_args.args[0])
        assert payload['chunks'] == [text]
        assert text not in ' '.join(popen.call_args.args[0])
        assert popen.call_args.kwargs.get('shell', False) is False
        assert interaction.playback is playback
        playback.stop()
        proc.terminate.assert_called_once()
        proc.stdin.close.assert_called_once()

def test_deadline_kills_worker_without_polling_and_reports_timeout():
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    playback = NeuralPlayback(proc, 0.15)
    try:
        with pytest.raises(TtsError, match='timed out'):
            playback.wait(5)
        assert proc.poll() is not None
    finally:
        playback.stop()

def test_cancellation_is_not_an_error_and_clears_orb():
    proc = Mock()
    proc.poll.return_value = None
    proc.terminate.side_effect = lambda: setattr(proc.poll, 'return_value', 1)
    proc.wait.return_value = 1
    was_enabled = activity.enabled
    activity.enabled = True
    try:
        playback = NeuralPlayback(proc, 30)
        assert activity.snapshot()['speaking']
        playback.stop()
        playback.wait()
        assert not playback.active
        assert not activity.snapshot()['speaking']
    finally:
        activity.enabled = was_enabled

def test_worker_volume_is_bounded_and_invalid_audio_rejected():
    import numpy as np
    engine = Mock()
    engine.create.return_value = (np.array([2.0, -3.0, 0.4]), 24000)
    payload = dict(chunks=['hello'], speed=0.97, language='en-gb', volume=50)
    with patch('hanni.speech.neural_worker.synthesizer', return_value=(engine, 'blend')):
        samples, rate = next(render_chunks(payload))
        np.testing.assert_allclose(samples, [1, -1, 0.2])
        assert rate == 24000
        engine.create.return_value = (np.array([np.nan]), 24000)
        with pytest.raises(ValueError, match='invalid synthesis'):
            next(render_chunks(payload))

def test_audio_output_failure_stops_device():
    device = Mock()
    device.play.side_effect = RuntimeError('device removed')
    with patch.dict(sys.modules, sounddevice=device), patch('hanni.speech.neural_worker.render_chunks', return_value=iter([(object(), 24000)])):
        with pytest.raises(RuntimeError):
            play({})
        device.stop.assert_called_once()

def test_selected_virtual_cable_uses_host_api_that_supports_voice_rate():
    device = Mock()
    device.query_hostapis.return_value = [{'name': 'Windows DirectSound'}, {'name': 'Windows WASAPI'}]
    device.query_devices.return_value = [{'name': 'CABLE Input', 'hostapi': 0, 'max_output_channels': 2}, {'name': 'CABLE Input', 'hostapi': 1, 'max_output_channels': 2}]

    def check(**kwargs):
        if kwargs['device'] == 1:
            raise RuntimeError('WASAPI needs 48 kHz')
    device.check_output_settings.side_effect = check
    with patch.dict(sys.modules, {'sounddevice': device}), patch('hanni.speech.neural_worker.render_chunks', return_value=iter([(object(), 24000)])):
        play({'output_name': 'CABLE Input'})
    device.play.assert_called_once_with(ANY, 24000, device=0, blocking=True)

def test_worker_does_not_log_private_exception_text(capsys):
    import io
    with patch('sys.stdin', io.StringIO('{}')), patch('hanni.speech.neural_worker.play', side_effect=ValueError('PRIVATE CALENDAR TEXT')):
        assert main() == 1
    assert 'PRIVATE' not in capsys.readouterr().err

@pytest.mark.parametrize('setting,value', [('speed', 0), ('cpu_threads', 0), ('language', 'xx-xx'), ('pitch_semitones', 5), ('sapi_fallback', 'true')])
def test_invalid_neural_settings_rejected(setting, value):
    with pytest.raises(ConfigError):
        parse_hanni({'speech': {'tts': {setting: value}}})
