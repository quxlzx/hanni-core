"""Saved browser audio choices must reach the real speech factories."""
from __future__ import annotations
import http.client
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hanni.config.loader import load_config
from hanni.config.schema import TtsConfig
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.server import DashboardServer
from hanni.speech.audio_devices import AudioDeviceError, DESKTOP_INPUT, InputDevice, OutputDevice, load_selection, routing_path, routing_state, save_selection, selected_input, selected_output
from hanni.speech.pipeline import create_pipeline
from hanni.speech.microphone import MicrophoneError
from hanni.speech.tts import WindowsSapiTts, _SPEAK_SELECTED_SCRIPT, create_tts
ROOT = Path(__file__).resolve().parents[2]
MICS = (InputDevice(1, 'Desk Mic', 'Windows WASAPI'), InputDevice(4, 'Webcam Mic', 'Windows WASAPI'))
SPEAKERS = (OutputDevice('speaker-token', 'Desk Speakers'),)

def test_desktop_loopback_selection_reaches_speech_factory(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    with patch('hanni.speech.audio_devices.list_inputs', return_value=MICS + (DESKTOP_INPUT,)), patch('hanni.speech.audio_devices.list_outputs', return_value=SPEAKERS):
        save_selection(routing_path(tmp_path), input_id='-1', output_id='speaker-token')
        assert selected_input(tmp_path) == 'desktop'
        assert routing_state(tmp_path)['input_id'] == '-1'
        with patch('hanni.speech.pipeline.MicrophoneCapture') as capture:
            create_pipeline(config, vad=object(), transcriber=object())
            assert capture.call_args.kwargs['device'] == 'desktop'
    with patch('hanni.speech.audio_devices.list_inputs', side_effect=MicrophoneError('audio devices busy')):
        assert selected_input(tmp_path) == 'desktop'

def test_selection_survives_restart_and_mic_index_change(tmp_path):
    path = routing_path(tmp_path)
    with patch('hanni.speech.audio_devices.list_inputs', return_value=MICS), patch('hanni.speech.audio_devices.list_outputs', return_value=SPEAKERS):
        save_selection(path, input_id='1', output_id='speaker-token')
        assert selected_input(tmp_path) == 1
        assert selected_output(tmp_path) == SPEAKERS[0]
        assert load_selection(path)['input']['name'] == 'Desk Mic'
    shifted = (InputDevice(9, 'Desk Mic', 'Windows WASAPI'), MICS[1])
    with patch('hanni.speech.audio_devices.list_inputs', return_value=shifted), patch('hanni.speech.audio_devices.list_outputs', return_value=SPEAKERS):
        assert selected_input(tmp_path) == 9
        state = routing_state(tmp_path)
        assert state['input_id'] == '9'
        assert state['input_error'] is None

def test_selection_rejects_stale_devices_without_replacing_saved_choice(tmp_path):
    path = routing_path(tmp_path)
    with patch('hanni.speech.audio_devices.list_inputs', return_value=MICS), patch('hanni.speech.audio_devices.list_outputs', return_value=SPEAKERS):
        save_selection(path, input_id='1', output_id='speaker-token')
        original = path.read_bytes()
        try:
            save_selection(path, input_id='999', output_id='speaker-token')
        except AudioDeviceError as exc:
            assert 'microphone' in str(exc)
        else:
            raise AssertionError('stale microphone was accepted')
        assert path.read_bytes() == original
        save_selection(path, input_id='default', output_id='default')
        assert selected_input(tmp_path) is None
        assert selected_output(tmp_path) is None

def test_saved_choices_reach_microphone_and_sapi_factory(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    with patch('hanni.speech.audio_devices.list_inputs', return_value=MICS), patch('hanni.speech.audio_devices.list_outputs', return_value=SPEAKERS):
        save_selection(routing_path(tmp_path), input_id='1', output_id='speaker-token')
        with patch('hanni.speech.pipeline.MicrophoneCapture') as capture:
            create_pipeline(config, vad=object(), transcriber=object())
            assert capture.call_args.kwargs['device'] == 1
        engine = create_tts(TtsConfig(backend='windows_sapi'), data_dir=tmp_path)
        assert isinstance(engine, WindowsSapiTts)
        assert engine.output_device == SPEAKERS[0]
        australian = create_tts(TtsConfig(backend='windows_australian'), data_dir=tmp_path)
        assert australian.fallback.fallback.output_device == SPEAKERS[0]
        with patch('hanni.speech.tts.subprocess.Popen') as spawn:
            engine.start('Audio route check')
            assert spawn.call_args.args[0][-1] == _SPEAK_SELECTED_SCRIPT
            payload = json.loads(spawn.return_value.stdin.write.call_args.args[0])
            assert payload['output_token'] == 'speaker-token'

def test_dashboard_audio_selection_requires_token_and_persists(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    hub = ChatHub()
    server = DashboardServer(0, SimpleNamespace(config=config), hub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = f'127.0.0.1:{server.server_port}'

    def call(method, *, token='', body=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            headers = {'Host': host, 'Origin': f'http://{host}', 'X-Hanni-Token': token, 'Content-Type': 'application/json'}
            connection.request(method, '/api/audio-devices', body=json.dumps(body) if body is not None else None, headers=headers)
            response = connection.getresponse()
            return (response.status, json.loads(response.read()))
        finally:
            connection.close()
    try:
        with patch('hanni.speech.audio_devices.list_inputs', return_value=MICS), patch('hanni.speech.audio_devices.list_outputs', return_value=SPEAKERS):
            status, state = call('GET')
            assert status == 200 and state['inputs'][0]['name'] == 'Desk Mic'
            selection = {'input_id': '1', 'output_id': 'speaker-token'}
            assert call('POST', body=selection)[0] == 403
            assert call('POST', token=hub.token, body={'input_id': '999', 'output_id': 'speaker-token'})[0] == 400
            status, state = call('POST', token=hub.token, body=selection)
            assert status == 200 and state['input_id'] == '1' and (state['output_id'] == 'speaker-token')
            assert load_selection(routing_path(tmp_path))['output']['name'] == 'Desk Speakers'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        hub.close()
        hub.db.close()
