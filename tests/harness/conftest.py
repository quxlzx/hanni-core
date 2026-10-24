from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from hanni.hermes.client import Client, HermesControl
from hanni.hermes.service import Bridge, Handler
from hanni.native.local_tools import local_tool_specs
from hanni.tools.google_identity import scopes_for
from tests.unit.test_chat_commands import commands, command, exchange
from tests.unit.test_google_access import Vault
from .fakes import CalendarService, ManualTicks, ModelService


@pytest.fixture
def harness(commands, tmp_path, monkeypatch):
    model = ModelService()
    state = commands.server.model_settings.root
    state.mkdir(parents=True, exist_ok=True)
    (state / 'models.native.yaml').write_text(yaml.safe_dump({'models': [{'id': 'fixture', 'role': 'supervisor',
        'source': 'local', 'api_model': 'fixture', 'endpoint': model.endpoint, 'context_length': 65536}]}))
    monkeypatch.setenv('HANNI_MODEL_CONFIG', str(state / 'models.native.yaml'))
    monkeypatch.setenv('HANNI_MODEL_STATE', str(state))
    monkeypatch.delenv('HANNI_AUTO_APPROVE', raising=False)
    token = tmp_path / 'bridge.token'
    token.write_text('synthetic-' + 'a' * 48)
    config = tmp_path / 'hermes.yaml'
    config.write_text('model: fixture\n')
    bridge = Bridge(tmp_path / 'fake-hermes', config, token)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.bridge = bridge
    serving = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
    serving.start()
    client_config = {'endpoint': f'http://127.0.0.1:{server.server_port}', 'token_file': str(token),
                     'enabled': True, 'connection_only': True, 'windows_capabilities': []}
    client = Client(client_config)
    commands.proxy = client.request
    registry = commands.server.features.registry
    calendar = CalendarService()
    credentials = {'token': 'fixture-google-access', 'refresh_token': 'fixture-google-refresh',
        'token_uri': 'https://oauth2.googleapis.com/token', 'client_id': 'fixture.apps.googleusercontent.com',
        'client_secret': 'fixture-client-secret', 'scopes': scopes_for(('calendar.read', 'calendar.write', 'gmail.read'))}
    registry.google_access._vault = Vault({'personal': {'email': 'employee@fixture.invalid', 'calendar_ids': ['primary'], 'credentials': credentials}})
    registry.google_access.transport = calendar
    # Only the OS/HTTP boundaries are synthetic. Actual permission checks,
    # command dispatch, model adapters, stores and Google adapters all run.
    from hanni.tools import workplace, content
    from hanni.native import local_tools
    monkeypatch.setattr(workplace, 'run_powershell_json', lambda *a, **k: {'text': 'Synthetic screen: review quarterly report.'})
    monkeypatch.setattr(content, 'run_powershell', lambda *a, **k: 'Synthetic clipboard: draft report.')
    search_html = b'<a class="result__a" href="https://source.fixture.invalid/report">Fixture report</a><a class="result__snippet">Synthetic evidence</a>'
    monkeypatch.setattr(local_tools, '_http_get', lambda *a, **k: ('https://search.fixture.invalid/', search_html))
    from hanni.dashboard.voice import voice_control
    pump = SimpleNamespace(pause=lambda: None, resume=lambda: None, running=lambda: True,
                           paused=False, failed=False, closed=False)
    classifier = SimpleNamespace(clear_engagement=lambda: None, classify=lambda text: True)
    voice_control.bind(pump, classifier, registry, 'Hanni')
    # Observe real command threads and join them rather than polling with sleeps.
    threads = []
    def thread_factory(*args, **kwargs):
        thread = threading.Thread(*args, **kwargs)
        threads.append(thread)
        return thread
    import hanni.dashboard.commands as command_module
    monkeypatch.setattr(command_module, 'threading', SimpleNamespace(Thread=thread_factory, RLock=threading.RLock, Event=threading.Event))
    def invoke(text, *, conversation='default', key=None, wait=True):
        before = len(threads)
        result = command(commands, text, conversation=conversation, key=key)
        if result.get('pending') and wait:
            for thread in threads[before:]:
                thread.join(timeout=10)
                assert not thread.is_alive(), 'Controlled command did not finish.'
            result = commands.result(result['id'])
            assert not result.get('pending')
        return result
    exchange(commands.hub, 'Saved session fixture', 'Inspect report; do not send it.')
    remembered = invoke('/remember I prefer concise report summaries')
    assert remembered['ok']
    memory_id = commands.server.features.memory_store().list()[0].id
    todo = invoke('/tasks add Review report')
    assert todo['ok']
    todo_id = commands.server.features.productivity()['tasks'][0]['id']
    task = bridge.store.submit('controlled-job', {'prompt': 'Write the reviewed report', 'origin': 'hanni', 'windows_tools': [], 'context': {}})
    spec = next(s for s in local_tool_specs() if s['name'] == 'local_write_file')
    action = bridge.store.request_action(task['id'], 'controlled-action', spec, {'path': 'reviewed.txt', 'content': 'Reviewed text'})
    commands.work.save_job(task['id'], 'native', 'default', 'fixture')
    reviewed = invoke('/jobs status ' + task['id'])
    assert reviewed['ok'], reviewed
    # A real HermesControl/client talks to the controlled bridge. Manual ticks
    # keep monitor tests deterministic; ordinary command tests do not tick it.
    root = commands.server.features.root
    (root / 'hermes').mkdir(exist_ok=True)
    (root / 'hermes/config.json').write_text(json.dumps(client_config))
    with monkeypatch.context() as scoped:
        scoped.setattr('hanni.hermes.client.threading.Thread.start', lambda self: None)
        control = HermesControl(root, SimpleNamespace(controller_registry=registry, features=commands.server.features))
    control.monitor = None
    control.stop = ManualTicks()
    control.bind(registry)
    commands.server.hermes = control
    args = {'resume': 'default', 'forget': memory_id, 'reasoning': 'high', 'voice': 'on', 'wake': 'off', 'mute': 'on',
            'remember': 'I prefer Unicode caf\u00e9 summaries', 'remind': 'in 10 minutes Review report',
            'tasks': 'list', 'search': 'report evidence', 'hermes': 'Inspect the report; do not send it',
            'jobs': 'status ' + task['id'], 'approve': action['id'], 'deny': action['id'], 'calendar': 'day'}
    value = SimpleNamespace(service=commands, invoke=invoke, args=args, model=model, calendar=calendar,
        bridge=bridge, control=control, task=task, action=action, memory_id=memory_id, todo_id=todo_id,
        threads=threads, state=state, voice=voice_control)
    try:
        yield value
    finally:
        model.release.set()
        commands.close()
        for thread in threads:
            thread.join(timeout=10)
        control.close()
        voice_control.unbind(pump)
        server.shutdown()
        server.server_close()
        serving.join(timeout=5)
        bridge.close()
        model.close()
        registry.context.reliability.close()
