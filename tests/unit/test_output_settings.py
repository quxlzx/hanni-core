import http.client
import json
import uuid
from unittest.mock import patch

import httpx
import pytest
import yaml

from hanni.native.context_budget import compression_threshold
from hanni.native.model_settings import ModelSettings, atomic_json
from hanni.native.output_settings import OutputSettings
from hanni.native.provider import NativeClient, load_model
from tests.unit.test_dashboard_chat import chat_server, send


@pytest.fixture
def output(tmp_path, monkeypatch):
    root = tmp_path / 'state'
    root.mkdir()
    model = {'id': 'brain', 'api_model': 'actual-model', 'endpoint': 'http://localhost:8411/v1',
             'source': 'local', 'model_file': 'fixture.gguf', 'context_length': 65536, 'native_max_tokens': 1200}
    path = root / 'models.native.yaml'
    path.write_text(yaml.safe_dump({'models': [model]}))
    monkeypatch.setenv('HANNI_MODEL_CONFIG', str(path))
    monkeypatch.setenv('HANNI_MODEL_STATE', str(root))
    return ModelSettings(root), model


def body(control, value):
    return {'id': str(uuid.uuid4()), 'model_id': control.output_snapshot()['model_id'], 'max_tokens': value}


def test_saved_limit_reaches_real_provider_payload_and_reserves_context(output):
    control, model = output
    running = NativeClient(load_model())
    assert running.max_tokens == 1200
    assert control.save_output(body(control, 8192))['max_tokens'] == 8192
    client = NativeClient(load_model())
    assert running.max_tokens == 1200 and client.max_tokens == 8192
    assert compression_threshold(load_model(), client.max_tokens) == 65536 - 8192 - 2048
    original = httpx.Client
    payloads = []
    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Synthetic response'}}]})
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        client.chat([{'role': 'user', 'content': 'Hello'}])
    assert payloads[0]['max_tokens'] == 8192
    assert NativeClient({**load_model(), 'native_max_tokens': 5000}).max_tokens == 5000
    assert load_model(output_settings=False) == model


@pytest.mark.parametrize('value', [0, -1, True, False, 1.5, '2048', 63489, 65536, [], {}])
def test_bad_or_context_exceeding_limits_never_write(output, value):
    control, _ = output
    with pytest.raises(ValueError, match='whole number'):
        control.save_output(body(control, value))
    assert not (control.root / 'output-settings.json').exists()


def test_preferences_survive_reload_are_model_specific_and_can_reset(output):
    control, model = output
    control.save_output(body(control, 4096))
    assert ModelSettings(control.root).output_snapshot()['max_tokens'] == 4096
    other = {**model, 'api_model': 'different-model', 'source': 'api'}
    settings = OutputSettings(control.root)
    assert settings.snapshot(other)['max_tokens'] == 1200
    wrong_model = {**body(control, 2048), 'model_id': settings.snapshot(other)['model_id']}
    with pytest.raises(ValueError, match='active model changed'):
        control.save_output(wrong_model)
    assert control.output_snapshot()['max_tokens'] == 4096
    reset = control.save_output(body(control, None))
    assert reset['max_tokens'] == 1200 and not reset['customized']
    assert NativeClient(load_model()).max_tokens == 1200


def test_limit_is_clamped_when_same_model_uses_a_smaller_context(output):
    control, model = output
    settings = OutputSettings(control.root)
    large = {**model, 'context_length': 262144}
    settings.save(large, {'id': str(uuid.uuid4()), 'model_id': settings.snapshot(large)['model_id'], 'max_tokens': 65536})
    assert settings.snapshot(large)['max_tokens'] == 65536
    assert settings.apply(model)['native_max_tokens'] == 63488
    assert settings.snapshot(large)['max_tokens'] == 65536


def test_api_requires_token_and_save_does_not_interrupt_work(chat_server, output):
    control, _ = output
    chat_server.model_settings = control
    values = body(control, 2048)
    assert send(chat_server, path='/api/model-output', body=values, headers={'X-Hanni-Token': 'wrong'})[0] == 403
    conn = http.client.HTTPConnection('127.0.0.1', chat_server.server_port)
    try:
        conn.request('GET', '/api/model-output')
        assert conn.getresponse().status == 403
    finally:
        conn.close()
    chat_server.chat.submit(str(uuid.uuid4()), 'Current work')
    before = chat_server.chat.snapshot()
    assert send(chat_server, path='/api/model-output', body=values)[0] == 200
    assert chat_server.chat.snapshot() == before
    assert control.change() is None
    assert send(chat_server, path='/api/model-output', body=body(control, 4096))[0] == 200
    # A completed retry cannot overwrite a later save.
    assert send(chat_server, path='/api/model-output', body=values)[0] == 200
    assert control.output_snapshot()['max_tokens'] == 4096
    atomic_json(control.root / 'model-change.json', {'status': 'pending'})
    assert send(chat_server, path='/api/model-output', body=body(control, 8192))[0] == 409


def test_missing_native_session_reports_unavailable(tmp_path):
    control = ModelSettings(tmp_path)
    assert not control.output_snapshot()['available']
    with pytest.raises(RuntimeError, match='native model session'):
        control.save_output({'id': str(uuid.uuid4()), 'model_id': 'unknown', 'max_tokens': 1024})
