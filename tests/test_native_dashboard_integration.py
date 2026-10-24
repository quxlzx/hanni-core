"""Native launch, model identity, chat and approval regressions; no model needed."""
import json
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from hanni.config.loader import load_config
from hanni.dashboard.bridge_panel import bridge_decision, cron_root
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.native_chat import NativeChat
from hanni.hermes.state import TaskStore
from hanni.native.local_tools import await_local, local_tool_specs, execute_local, _http_get
from hanni.native.loop import run_loop
from hanni.native.provider import NativeClient, normalize_endpoint, load_model
from tests.test_native_loop import FakeClient, spec
from tests.test_stick import firstboot
from tests.unit.test_dashboard_chat import chat_server, send

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def boot(monkeypatch, tmp_path):
    monkeypatch.setattr(firstboot, 'STICK', tmp_path)
    monkeypatch.setattr(firstboot, 'CORE', ROOT)
    return firstboot


def test_remote_launch_discovers_real_model_without_formatting_none(boot, tmp_path):
    with patch.object(boot, 'get_json', return_value={'data': [{'id': 'actual-model'}]}):
        assert boot.main(['--brain-url', 'http://localhost:9999']) == 0
    config = json.loads(json.dumps(__import__('yaml').safe_load((tmp_path/'state/models.native.yaml').read_text())))
    assert config['models'][0]['api_model'] == 'actual-model'
    assert config['models'][0]['endpoint'] == 'http://localhost:9999/v1'
    assert not (ROOT / 'config/models.native.yaml').exists()


def test_remote_requires_explicit_choice_when_multiple_models(boot, tmp_path):
    with patch.object(boot, 'get_json', return_value={'data': [{'id': 'a'}, {'id': 'b'}]}):
        assert boot.main(['--brain-url', 'http://localhost:9999']) == 1
    assert not (tmp_path/'state').exists()


def test_wrong_remote_model_cannot_silently_fall_back(boot):
    with patch.object(boot, 'get_json', return_value={'data': [{'id': 'actual'}]}):
        assert boot.main(['--brain-url', 'http://localhost:9999', '--brain-model', 'wrong']) == 1


def test_startup_failure_cleans_up_every_owned_service(boot):
    bridge, cron, dashboard = Mock(), Mock(), Mock()
    with patch.object(boot, 'ensure_deps'), patch.object(boot, 'port_in_use', return_value=False), \
         patch.object(boot, 'get_json', return_value={'data': [{'id': 'actual'}]}), \
         patch('hanni.native.provider.NativeClient.status', return_value={'ready': True}), \
         patch.object(boot, 'spawn', side_effect=[bridge, cron, dashboard]), \
         patch.object(boot, 'wait_ready', side_effect=[None, RuntimeError('dashboard failed')]), \
         patch.object(boot, 'stop_owned') as stop:
        assert boot.main(['--serve', '--ui', '--wait', '--no-browser', '--brain-url', 'http://localhost:9999']) == 1
    assert [call.args[0] for call in stop.call_args_list] == [dashboard, cron, bridge]


def test_existing_dashboard_opens_without_starting_a_second_stack(boot):
    with patch.object(boot, 'ensure_deps'), patch.object(boot, 'port_in_use', return_value=True), \
         patch.object(boot, 'get_json', return_value={'epoch': 'existing', 'ready': True}), \
         patch.object(boot, 'spawn') as spawn:
        assert boot.main(['--serve', '--ui', '--no-browser']) == 0
    spawn.assert_not_called()


def test_dashboard_stop_exits_supervisor_instead_of_spinning(boot):
    model, dashboard = Mock(), Mock()
    model.poll.return_value = None
    dashboard.poll.return_value = 0
    dashboard.returncode = 0
    assert boot.supervise({'model': model, 'dashboard': dashboard}) == 0


def test_model_restart_budget_is_bounded(boot):
    dead = Mock(returncode=2)
    dead.poll.return_value = 2
    restart = Mock(return_value=dead)
    with patch('time.sleep'):
        with pytest.raises(RuntimeError, match='model exited'):
            boot.supervise({'model': dead}, restart)
    assert restart.call_count == 3


def test_generated_dashboard_config_is_strict_and_matches_selected_model(boot, tmp_path):
    state, native_path, dashboard_path, _ = boot.write_configs('http://127.0.0.1:8411/v1', 'actual',
        Path('chosen-Q4_K_M.gguf'), 8311)
    cfg = load_config(ROOT/'config', data_dir=state, env={'HANNI_MODEL_CONFIG': str(dashboard_path)})
    assert cfg.models.supervisor.api_model == 'actual'
    assert cfg.models.supervisor.endpoint == 'http://127.0.0.1:8411/v1'
    assert cfg.models.supervisor.quantization == 'Q4_K_M'
    assert load_model(native_path)['native_max_tokens'] == 1200


def test_explicit_environment_is_not_overridden_by_process_environment(monkeypatch):
    monkeypatch.setenv('HANNI_MODEL_CONFIG', 'missing-file.yaml')
    assert load_config(ROOT/'config', env={}).models.supervisor.id == 'supervisor'


@pytest.mark.parametrize('url,expected', [('http://localhost:99', 'http://localhost:99/v1'),
    ('http://localhost:99/v1/', 'http://localhost:99/v1'),
    ('http://localhost:99/v1/chat/completions', 'http://localhost:99/v1')])
def test_endpoint_normalization(url, expected):
    assert normalize_endpoint(url) == expected


@pytest.mark.parametrize('url', ['file:///tmp/model', 'http://user:password@api.example.invalid/v1',
                                'http://localhost/v1?api_key=secret'])
def test_bad_or_credential_bearing_endpoints_are_rejected(url):
    with pytest.raises(ValueError):
        normalize_endpoint(url)


def test_model_status_distinguishes_wrong_identity_from_ready():
    import httpx
    original = httpx.Client
    def response(request):
        return httpx.Response(200, json={'data': [{'id': 'actual', 'aliases': ['alias']}]})
    transport = httpx.MockTransport(response)
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=transport, **kwargs)):
        assert NativeClient({'id': 'a', 'api_model': 'actual', 'endpoint': 'http://localhost/v1'}).status()['ready']
        wrong = NativeClient({'id': 'a', 'api_model': 'wrong', 'endpoint': 'http://localhost/v1'}).status()
    assert wrong['state'] == 'model-not-found' and not wrong['ready']


def test_native_chat_consumes_inbox_and_preserves_recent_context():
    hub = ChatHub()
    hub.activate()
    hub.note('Earlier question', 'Earlier answer')
    calls = []
    def proxy(method, path, body=None):
        calls.append((method, path, body))
        if path == '/model': return {'ready': True}
        if method == 'POST': return {'id': 'task'}
        return {'state': 'review_required', 'result': {'model_claims': 'Native answer'}}
    runner = NativeChat(hub, threading.Event(), proxy=proxy)
    runner.start()
    try:
        hub.submit(str(uuid.uuid4()), 'Current question')
        for _ in range(200):
            if hub.snapshot()['messages'][-1]['content'] == 'Native answer': break
            time.sleep(.01)
        assert hub.snapshot()['messages'][-1]['content'] == 'Native answer'
        assert not hub.snapshot()['busy']
        task = next(body['task'] for method, path, body in calls if path == '/tasks')
        assert task['context']['conversation'][-1]['text'] == 'Earlier answer'
        assert 'local_runtime' not in task['context']
    finally:
        runner.close(); hub.close(); hub.db.close()


def test_approval_authorizes_real_worker_execution_instead_of_faking_receipt(tmp_path):
    store = TaskStore(tmp_path/'tasks.sqlite3')
    try:
        task = store.submit('approval', {'prompt': 'write', 'origin': 'hanni', 'windows_tools': [], 'context': {}})
        tool = next(s for s in local_tool_specs() if s['name'] == 'local_write_file')
        action = store.request_action(task['id'], 'call', tool, {'path': 'note.txt', 'content': 'héllo'})
        def proxy(method, path, body=None):
            return store.action(action['id']) if method == 'GET' else store.settle(action['id'], body['state'])
        with patch('hanni.dashboard.bridge_panel.bridge_proxy', side_effect=proxy):
            decision = bridge_decision(action['id'], {'state': 'dispatching'})
        assert decision['receipt'] is None
        assert not (tmp_path/'workspace/note.txt').exists()
        receipt = await_local(store, task['id'], action, tmp_path/'workspace')
        assert receipt['ok']
        assert (tmp_path/'workspace/note.txt').read_text(encoding='utf-8') == 'héllo'
        assert receipt['data']['bytes'] == len('héllo'.encode())
    finally:
        store.close()


def test_browser_cannot_submit_its_own_success_receipt(chat_server):
    status, _ = send(chat_server, path='/api/bridge/action/a', body={'state': 'fulfilled', 'receipt': {'ok': True}})
    assert status == 400


def test_proxy_outage_is_an_http_failure(chat_server):
    with patch('hanni.dashboard.bridge_panel.bridge_proxy', return_value={'error': 'bridge unreachable'}):
        status, body = send(chat_server, path='/api/bridge/submit', body={'key': 'one', 'task': {}})
    assert status == 502 and body['error'] == 'bridge unreachable'


def test_cron_button_addresses_correct_job(chat_server, monkeypatch, tmp_path):
    monkeypatch.delenv('HANNI_CRON_ROOT', raising=False)
    monkeypatch.setenv('HANNI_BRIDGE_TOKEN_FILE', str(tmp_path/'bridge.token'))
    assert cron_root() == tmp_path
    with patch('hanni.dashboard.bridge_panel.cron_set', return_value={'updated': 1}) as update:
        assert send(chat_server, path='/api/cron/job/job123/enable', body={})[0] == 200
    update.assert_called_once_with('job123', True)


@pytest.mark.parametrize('arguments', ['null', '[]', '17', 'broken'])
def test_invalid_model_arguments_are_recoverable(arguments):
    client = FakeClient([{'message': {'tool_calls': [{'function': {'name': 'read', 'arguments': arguments}}]}},
                         {'message': {'content': 'Please provide valid arguments.'}}])
    execute = Mock()
    result = run_loop(client, system_prompt='s', user_message='u', tool_specs=[spec('read')], execute=execute)
    execute.assert_not_called()
    assert result['claims'] == 'Please provide valid arguments.'
    messages = client.calls[-1]['messages']
    assert messages[-2]['tool_calls'][0]['id'] == messages[-1]['tool_call_id']


def test_thinking_is_not_exposed_as_final_answer():
    client = FakeClient([{'message': {'reasoning_content': 'private thinking'}}, {'message': {'content': 'Public answer'}}])
    assert run_loop(client, system_prompt='s', user_message='u', tool_specs=[], execute=Mock())['claims'] == 'Public answer'


def test_private_redirect_is_blocked_before_connecting():
    public = (2,1,6,'',('93.184.216.34',80))
    private = (2,1,6,'',('127.0.0.1',80))
    response = Mock(status=302)
    response.getheader.return_value = 'http://127.0.0.1/private'
    with patch('socket.getaddrinfo', side_effect=[[public],[private]]), \
         patch('socket.create_connection', return_value=Mock()) as connect, \
         patch('http.client.HTTPConnection.request', autospec=True, side_effect=lambda connection,*a,**k:connection.connect()), \
         patch('http.client.HTTPConnection.getresponse', return_value=response):
        with pytest.raises(ValueError, match='internal'):
            _http_get('http://public.example/start')
    connect.assert_called_once()
    assert connect.call_args.args[0] == ('93.184.216.34',80)


def test_file_error_is_an_observation_and_utf8_is_preserved(tmp_path):
    (tmp_path/'folder').mkdir()
    assert not execute_local('local_write_file', {'path': 'folder', 'content': 'x'}, tmp_path)['ok']
    execute_local('local_write_file', {'path': 'note.txt', 'content': '한니'}, tmp_path)
    assert execute_local('local_read_file', {'path': 'note.txt'}, tmp_path)['data']['content'] == '한니'


def test_yaml_skills_support_folded_descriptions_and_trigger_lists(tmp_path):
    from hanni.native.skills import load_skills, match_skills
    (tmp_path/'SKILL.md').write_text('---\nname: watch\ndescription: >\n  Watch GPU temperature\ntriggers:\n  - gpu\n  - heat\n---\nRead real telemetry.\n')
    skills = load_skills(str(tmp_path))
    assert skills[0]['description'].strip() == 'Watch GPU temperature'
    assert 'Read real telemetry.' in match_skills(skills, 'check gpu heat')


def test_standalone_bridge_javascript_has_no_python_escape_corruption():
    from hanni.hermes.service import INDEX_HTML
    if not shutil.which('node'): pytest.skip('Node needed for browser script syntax check')
    script = INDEX_HTML.split('<script>',1)[1].split('</script>',1)[0]
    result = subprocess.run(['node','--check'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows process ownership')
def test_windows_job_terminates_owned_process_on_close():
    import sys
    from hanni.native.lifecycle import WindowsJob
    job = WindowsJob()
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        job.assign(child)
        assert child.poll() is None
        job.close()
        child.wait(timeout=5)
        assert child.returncode is not None
    finally:
        job.close()
        if child.poll() is None:
            child.kill(); child.wait(timeout=5)
