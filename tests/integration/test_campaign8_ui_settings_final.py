import json
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.settings_final import publish
from scripts.campaign8_ui.plan import validate_input
from hanni.speech.audio_devices import routing_path

def test_default_audio_selection_only_persists_inside_original_owned_root(tmp_path):
    with original_backend(tmp_path / 'owned') as backend:
        path = routing_path(backend.root).resolve()
        assert path.is_relative_to(backend.root)
        status, result = backend.request('/api/audio-devices', method='POST', body={'input_id': 'default', 'output_id': 'default'})
        assert status == 200 and result['input_id'] == 'default'
        assert result['output_id'] == 'default'
        assert path.is_file()
        saved = json.loads(path.read_text())
        assert saved == {'input': None, 'output': None}
        assert backend.chat.ready is False
        assert not any(('InputStream' in str(r) or 'OutputStream' in str(r) for r in backend.calls))

def test_status_and_default_config_inputs_never_request_physical_capture(tmp_path):
    publish(tmp_path / 'seal')
    rows = json.loads((tmp_path / 'seal' / 'inputs.json').read_text())
    assert len(rows) == 3
    for row in rows:
        validate_input(row)
    assert {s['selector'] for r in rows for s in r['steps'] if s.get('action') == 'select'} == {'#microphone-device', '#speaker-device'}
    assert not any((s.get('name') in {'Listen now', 'Analyze current screen', 'Apply GPU routing'} for r in rows for s in r['steps']))
