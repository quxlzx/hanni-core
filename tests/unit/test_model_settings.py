import json
import struct
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from hanni.native.model_settings import ModelSettings, LOCAL_MODELS, atomic_json, context_size, model_config
from hanni.native.provider import NativeClient
from tests.test_stick import firstboot
from tests.unit.test_dashboard_chat import chat_server, send


@pytest.fixture
def settings(tmp_path, monkeypatch):
    root, models = tmp_path / 'state', tmp_path / 'models'
    models.mkdir()
    for _, file in LOCAL_MODELS:
        (models / file).write_bytes(b'fixture')
    control = ModelSettings(root, models)
    monkeypatch.setenv('HANNI_MODEL_CONTROL', '1')
    monkeypatch.setenv('HANNI_MODEL_STATE', str(root))
    monkeypatch.setenv('HANNI_MODELS_DIR', str(models))
    atomic_json(root / 'model-selection.json', {'source': 'local', 'context': 65536,
        'local_model': LOCAL_MODELS[2][1], 'endpoint': 'http://127.0.0.1:8411/v1', 'api_model': 'stick-brain'})
    (root / 'bridge.token').write_text('fixture-token')
    return control


def local_body(**values):
    return {'operation': 'apply', 'id': str(uuid.uuid4()), 'source': 'local',
            'local_model': LOCAL_MODELS[0][1], 'context': 65536, **values}


def api_body(**values):
    return {'operation': 'apply', 'id': str(uuid.uuid4()), 'source': 'api', 'endpoint': 'https://models.example/v1',
            'api_model': 'test-model', 'context': 65536, **values}


@pytest.mark.parametrize('value', [0, 16384, 65535, 262145, 65537, True, '65536', None])
def test_context_rejects_out_of_range_and_non_integer_values(value):
    with pytest.raises(ValueError):
        context_size(value)


@pytest.mark.parametrize('value', [65536, 98304, 131072, 196608, 262144])
def test_context_allows_the_full_requested_range(value):
    assert context_size(value) == value


def test_installed_models_are_present_and_path_traversal_is_rejected(settings):
    assert [(m['name'], m['installed']) for m in settings.inventory()] == [('MiniCPM 2B', True), ('K2 3.7B', True), ('K2 7B', True), ('Qwen 3.5 4B', True), ('Qwen 3.5 9B', True)]
    for file in ['../outside.gguf', '/tmp/outside.gguf', 'missing.gguf', []]:
        with pytest.raises(ValueError):
            settings.validate(local_body(local_model=file))


@pytest.mark.parametrize('endpoint', ['http://models.example/v1', 'https://user:secret@models.example/v1', 'https://models.example/v1?key=secret', 'file:///model'])
def test_remote_credentials_require_secure_transport_and_separate_key(settings, endpoint):
    with pytest.raises(ValueError):
        settings.validate(api_body(endpoint=endpoint))


def test_api_key_goes_only_to_the_vault_and_exact_retries_do_not_restart(settings):
    vault = Mock()
    body = api_body(api_key='fixture-secret-long-value')
    with patch('hanni.native.model_settings.credential_vault', return_value=vault), \
         patch.object(NativeClient, 'status', return_value={'ready': True, 'context_verified': False}):
        result = settings.execute(body)
        assert result['change']['status'] == 'pending'
        assert settings.execute(body)['change']['id'] == body['id']
        assert vault.set_password.call_count == 1
        reference = settings.change()['selection']['api_key_ref']
        vault.set_password.assert_called_once_with('HANNI.Models.v1', reference, body['api_key'])
        assert body['api_key'] not in json.dumps(result)
        assert all(body['api_key'] not in file.read_text() for file in settings.root.glob('*.json'))
        with pytest.raises(ValueError):
            settings.execute({**body, 'context': 262144})
        with pytest.raises(RuntimeError):
            settings.execute({**body, 'id': str(uuid.uuid4())})


def test_test_connection_does_not_save_key_or_change_active_model(settings):
    before = settings.active()
    with patch.object(NativeClient, 'status', return_value={'ready': True}), \
         patch('hanni.native.model_settings.credential_vault') as vault:
        assert settings.execute(api_body(operation='test', api_key='fixture-secret'))['connected']
    vault.assert_not_called()
    assert settings.change() is None and settings.active() == before


def test_wrong_model_or_insufficient_reported_api_context_does_not_save(settings):
    with patch.object(NativeClient, 'status', return_value={'ready': False, 'detail': 'Wrong model'}):
        with pytest.raises(ValueError, match='Wrong model'):
            settings.execute(api_body())
    with patch.object(NativeClient, 'status', return_value={'ready': True, 'context_verified': True, 'context': 32768}):
        with pytest.raises(ValueError, match='below the requested'):
            settings.execute(api_body())
    assert settings.change() is None


def test_saved_key_is_not_reused_for_a_different_endpoint(settings):
    atomic_json(settings.root / 'model-selection.json', {**api_body(), 'api_key_ref': 'stored-reference'})
    assert settings.validate(api_body())['api_key_ref'] == 'stored-reference'
    assert not settings.validate(api_body(endpoint='https://other.example/v1')).get('api_key_ref')


def test_local_provider_does_not_receive_the_cloud_environment_key(monkeypatch):
    monkeypatch.setenv('HANNI_MODEL_API_KEY', 'cloud-secret')
    client = NativeClient({'id': 'stick-brain', 'endpoint': 'http://localhost:8411', 'source': 'local'})
    assert client.api_key == 'local'


def test_local_status_reports_actual_server_context_not_a_configured_claim():
    original = httpx.Client
    def respond(request):
        return httpx.Response(200, json={'data': [{'id': 'stick-brain'}]} if request.url.path == '/v1/models'
                              else {'default_generation_settings': {'n_ctx': 98304}})
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        status = NativeClient({'id': 'stick-brain', 'endpoint': 'http://localhost:8411', 'source': 'local', 'context_length': 262144}).status()
    assert status['context'] == 98304 and status['context_verified']


def test_cloud_requests_do_not_receive_llama_specific_reasoning_options():
    original = httpx.Client
    payloads = []
    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Connected'}}]})
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        client = NativeClient({'id': 'remote', 'endpoint': 'https://models.example/v1', 'source': 'api', 'native_reasoning_budget': 512})
        assert client.chat([{'role': 'user', 'content': 'Hello'}])['message']['content'] == 'Connected'
    assert 'reasoning_budget_tokens' not in payloads[0]


def setup_switch(settings, monkeypatch):
    monkeypatch.setattr(firstboot, 'STICK', settings.root.parent)
    firstboot.write_configs('http://127.0.0.1:8411/v1', 'stick-brain', settings.models_dir / LOCAL_MODELS[2][1], 8311)
    old = Mock(pid=1)
    children, runtime = {'model': old}, {'command': ['old-model-command']}
    return old, children, runtime


@pytest.mark.parametrize('model_file', ['K2-Horizon-4B-Q4_K_M.gguf', 'Qwen3.5-4B-Q4_K_M.gguf', 'Qwen3.5-9B-Q4_K_M.gguf'])
def test_launcher_changes_the_actual_process_and_both_configs(settings, monkeypatch, model_file):
    old, children, runtime = setup_switch(settings, monkeypatch)
    settings.execute(local_body(local_model=model_file, context=262144))
    new = Mock(pid=2)
    with patch.object(firstboot, 'get_json', return_value={'tasks': []}), \
         patch.object(firstboot, 'pick_binary', return_value=Path('/fixture')), \
         patch('hanni.native.acceleration.flags', return_value=['-ngl', 'auto', '-ctk', 'q8_0', '-ctv', 'q8_0']), \
         patch.object(firstboot, 'probe'), patch.object(firstboot, 'spawn', return_value=new) as spawn, \
         patch.object(firstboot, 'stop_owned') as stop, patch.object(firstboot, 'wait_ready'), \
         patch.object(NativeClient, 'status', return_value={'ready': True, 'context_verified': True, 'context': 262144}):
        firstboot.apply_model_change(settings, children, runtime, port=8311, timeout=3, base_env={})
    stop.assert_called_once_with(old)
    command = spawn.call_args.args[0]
    assert command[command.index('-c')+1] == '262144'
    assert command[command.index('-m')+1].endswith(model_file)
    assert children['model'] is new
    assert settings.active()['context'] == 262144
    assert settings.change()['status'] == 'ready'
    from hanni.native.provider import load_model
    assert load_model(settings.root / 'models.native.yaml')['context_length'] == 262144
    assert load_model(settings.root / 'models.dashboard.yaml')['context_length'] == 262144


def test_failed_model_load_restores_previous_process_and_settings(settings, monkeypatch):
    old, children, runtime = setup_switch(settings, monkeypatch)
    before = (settings.root / 'models.native.yaml').read_bytes()
    settings.execute(local_body(context=262144))
    failed, restored = Mock(pid=2), Mock(pid=3)
    with patch.object(firstboot, 'get_json', return_value={'tasks': []}), \
         patch.object(firstboot, 'pick_binary', return_value=Path('/fixture')), \
         patch('hanni.native.acceleration.flags', return_value=['-ngl', 'auto', '-ctk', 'q8_0', '-ctv', 'q8_0']), \
         patch.object(firstboot, 'probe'), patch.object(firstboot, 'spawn', side_effect=[failed, restored]), \
         patch.object(firstboot, 'stop_owned'), patch.object(firstboot, 'wait_ready', side_effect=[RuntimeError('oom'), None]):
        firstboot.apply_model_change(settings, children, runtime, port=8311, timeout=3, base_env={})
    assert children['model'] is restored and runtime['command'] == ['old-model-command']
    assert (settings.root / 'models.native.yaml').read_bytes() == before
    assert settings.active()['local_model'] == LOCAL_MODELS[2][1]
    assert settings.change()['status'] == 'failed'


def test_a_task_accepted_before_the_switch_boundary_keeps_its_model(settings, monkeypatch):
    old, children, runtime = setup_switch(settings, monkeypatch)
    settings.execute(local_body())
    with patch.object(firstboot, 'get_json', return_value={'tasks': [{'state': 'running'}]}), patch.object(firstboot, 'stop_owned') as stop:
        firstboot.apply_model_change(settings, children, runtime, port=8311, timeout=3, base_env={})
    stop.assert_not_called()
    assert children['model'] is old and settings.change()['status'] == 'failed'


def test_dashboard_protects_settings_and_blocks_switches_during_work(chat_server, settings):
    chat_server.model_settings = settings
    assert send(chat_server, path='/api/model-settings', body=local_body(), headers={'X-Hanni-Token': 'wrong'})[0] == 403
    chat_server.chat.submit(str(uuid.uuid4()), 'busy')
    assert send(chat_server, path='/api/model-settings', body=local_body())[0] == 409
    assert settings.change() is None
    chat_server.chat.take(); chat_server.chat.note('busy', 'finished')
    with patch('hanni.dashboard.bridge_panel.bridge_proxy', return_value={'tasks': []}):
        assert send(chat_server, path='/api/model-settings', body=local_body())[0] == 200
    assert not chat_server.chat.ready


def test_restart_loads_saved_api_key_for_authenticated_model_discovery(settings, monkeypatch):
    atomic_json(settings.root / 'model-selection.json', {'source': 'api', 'context': 131072,
                'endpoint': 'https://models.example/v1', 'api_model': 'test-model', 'api_key_ref': 'saved-key'})
    monkeypatch.setattr(firstboot, 'STICK', settings.root.parent)
    with patch('hanni.native.model_settings.stored_api_key', return_value='fixture-secret'), \
         patch.object(firstboot, 'get_json', return_value={'data': [{'id': 'test-model'}]}) as get:
        assert firstboot.main([]) == 0
    get.assert_called_once_with('https://models.example/v1/models', token='fixture-secret')
    from hanni.native.provider import load_model
    assert load_model(settings.root / 'models.native.yaml')['context_length'] == 131072


def gguf_metadata(context):
    def text(value):
        encoded = value.encode()
        return struct.pack('<Q', len(encoded)) + encoded
    return (b'GGUF' + struct.pack('<IQQ', 3, 0, 2) + text('general.fixture') +
            struct.pack('<IIQ', 9, 8, 2) + text('one') + text('two') +
            text('llama.context_length') + struct.pack('<II', 4, context))


def test_context_limits_come_from_gguf_metadata_and_excess_is_rejected(settings):
    path = settings.models_dir / LOCAL_MODELS[0][1]
    path.write_bytes(gguf_metadata(131072))
    from hanni.native.gguf_context import context_limit
    assert context_limit(path) == 131072
    assert settings.inventory()[0]['max_context'] == 131072
    with pytest.raises(ValueError, match='up to 128K'):
        settings.execute(local_body(context=262144))
    assert settings.change() is None
    path.write_bytes(gguf_metadata(524288))
    assert context_limit(path) == 524288
    assert settings.inventory()[0]['max_context'] == 262144


@pytest.mark.parametrize('content', [b'', b'not-gguf', b'GGUF', b'GGUF'+struct.pack('<IQQ', 3, 0, 999999999)])
def test_invalid_gguf_metadata_never_breaks_the_model_listing(settings, content):
    path = settings.models_dir / LOCAL_MODELS[0][1]
    path.write_bytes(content)
    from hanni.native.gguf_context import context_limit
    assert context_limit(path) is None
    assert settings.inventory()[0]['installed']


def test_below_minimum_context_is_rejected_by_launcher_before_loading(settings, monkeypatch):
    monkeypatch.setattr(firstboot, 'STICK', settings.root.parent)
    with patch.object(firstboot, 'spawn') as spawn, pytest.raises(SystemExit):
        firstboot.main(['--context', '16384'])
    spawn.assert_not_called()


def test_missing_qwen_weights_remain_visible_and_projectors_are_not_model_choices(tmp_path):
    models = tmp_path / 'models'; models.mkdir()
    settings = ModelSettings(tmp_path / 'state', models)
    rows = {row['name']: row for row in settings.inventory()}
    for name in ('Qwen 3.5 4B', 'Qwen 3.5 9B'):
        assert not rows[name]['installed']
        with pytest.raises(ValueError, match='installed'):
            settings.validate(local_body(local_model=rows[name]['id']))
    (models / rows['Qwen 3.5 4B']['id']).write_bytes(gguf_metadata(131072))
    (models / 'mmproj-Qwen3.5-4B-BF16.gguf').write_bytes(b'projector fixture')
    refreshed = settings.inventory()
    assert len(refreshed) == len(LOCAL_MODELS)
    installed = next(row for row in refreshed if row['name'] == 'Qwen 3.5 4B')
    assert installed['installed'] and installed['max_context'] == 131072
    assert settings.validate(local_body(local_model=installed['id'], context=131072))['local_model'] == installed['id']
