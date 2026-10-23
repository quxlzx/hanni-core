import http.client
import json
import threading
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.server import DashboardServer
from hanni.tools.base import ToolPermissionError
from tests.helpers import REPO_ROOT

def config_for(path):
    return load_config(REPO_ROOT / 'config', data_dir=path, env={})

def mutation(operation, data=None, *, key=None):
    return {'id': key or str(uuid4()), 'operation': operation, 'data': data or {}, 'confirmed': True}

def test_workspace_writes_use_shared_tasks_and_do_not_log_personal_text(tmp_path):
    feature = DesktopFeatures(config_for(tmp_path))
    request = mutation('task.create', {'title': 'Owner private design deadline'})
    created = feature.mutate('productivity', request)
    assert feature.mutate('productivity', request) == created
    from hanni.tools.todos import TodoStore
    assert TodoStore(tmp_path).get(created['task']['id'])['title'] == 'Owner private design deadline'
    log = (tmp_path / 'logs/tool_audit.jsonl').read_text()
    assert 'Owner private design deadline' not in log
    assert '[PRIVATE WORKSPACE DATA]' in log
    changed = {**request, 'data': {'title': 'Different task'}}
    with pytest.raises(ValueError, match='different action'):
        feature.mutate('productivity', changed)

@pytest.mark.parametrize('change', [{'confirmed': False}, {'operation': 'powershell.run'}, {'operation': 'task.create', 'data': []}, {'id': 'not-a-uuid'}, {'arbitrary_path': 'C:/outside'}])
def test_fixed_write_contract_rejects_untrusted_shapes(tmp_path, change):
    feature = DesktopFeatures(config_for(tmp_path))
    with pytest.raises(ValueError):
        feature.mutate('productivity', {**mutation('task.create', {'title': 'Test'}), **change})
    assert not (tmp_path / 'todos.sqlite3').exists()

def test_chat_only_profile_cannot_write_workspace(tmp_path):
    config = config_for(tmp_path)
    owner = replace(config.permissions.profiles['owner'], chat_only=True)
    config = replace(config, permissions=replace(config.permissions, profiles={**config.permissions.profiles, 'owner': owner}))
    with pytest.raises(ToolPermissionError):
        DesktopFeatures(config).mutate('productivity', mutation('task.create', {'title': 'Blocked'}))
    assert not (tmp_path / 'todos.sqlite3').exists()

def test_safe_mode_blocks_record_mutations_before_storage(tmp_path):
    feature = DesktopFeatures(config_for(tmp_path))
    from hanni.core.shutdown import Actor, StopSource
    feature.registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('test'), reason='test')
    with pytest.raises(RuntimeError):
        feature.mutate('productivity', mutation('task.create', {'title': 'Blocked'}))
    assert not (tmp_path / 'todos.sqlite3').exists()

def test_memory_ui_reuses_store_and_rejects_changed_deletion(tmp_path):
    feature = DesktopFeatures(config_for(tmp_path))
    store = feature.memory_store()
    record, _ = store.remember('I prefer short status reports', source='owner_explicit.test')
    assert feature.memories('status')['records'][0]['id'] == record.id
    request = mutation('forget', {'memory_id': record.id, 'expected_updated_at': 'old'})
    with pytest.raises(ValueError, match='changed'):
        feature.mutate('memory', request)
    assert store.get(record.id) is not None
    request = mutation('forget', {'memory_id': record.id, 'expected_updated_at': record.updated_at.isoformat()})
    assert feature.mutate('memory', request) == {'deleted': True}
    assert feature.mutate('memory', request) == {'deleted': True}
    assert store.get(record.id) is None

def test_screen_status_does_not_capture_or_claim_vision(tmp_path):
    status = DesktopFeatures(config_for(tmp_path)).awareness()
    assert not status['available'] and (not status['capture_active']) and (not status['context_available'])
    assert all((not supported for supported in status['actions'].values()))
    assert not list(tmp_path.iterdir())

def test_memory_delete_detects_cross_process_change_atomically(tmp_path):
    feature = DesktopFeatures(config_for(tmp_path))
    store = feature.memory_store()
    record, _ = store.remember('I prefer concise summaries', source='owner_explicit.test')
    with store._connect() as db:
        db.execute('UPDATE memories SET updated_at=? WHERE id=?', ('2099-01-01T00:00:00+00:00', record.id))
    from hanni.memory.store import MemoryConflictError
    with pytest.raises(MemoryConflictError, match='changed'):
        store.delete(record.id, expected_updated_at=record.updated_at.isoformat())
    assert store.get(record.id) is not None

def test_calendar_cache_is_local_until_explicit_refresh(tmp_path, monkeypatch):
    feature = DesktopFeatures(config_for(tmp_path))
    feature.registry.google_access = SimpleNamespace(accounts=lambda: [{'account': 'personal', 'connected': True}])
    feature.store.save_calendar_cache('2026-10-09:7', {'events': [{'title': 'Cached event'}], 'cached_at': '2026-10-08T10:00:00Z'})

    def forbidden(*args, **kwargs):
        raise AssertionError('Calendar page must not read remote services without Refresh')
    monkeypatch.setattr(feature.registry, 'execute', forbidden)
    result = feature.calendar({'start_date': '2026-10-09', 'days': '7'})
    assert result['stale'] and result['events'][0]['title'] == 'Cached event'
    assert result['connected']

@pytest.fixture
def server(tmp_path):
    telemetry = SimpleNamespace(config=config_for(tmp_path), snapshot=lambda: {})
    service = DashboardServer(0, telemetry)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    yield service
    service.shutdown()
    service.server_close()

def call(server, path, *, method='GET', headers=None, data=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    try:
        connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers or {})
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

@pytest.mark.parametrize('path', ['productivity', 'memory', 'calendar', 'agents', 'awareness', 'voice', 'notifications'])
def test_private_projections_require_token_and_origin_guards(server, path, tmp_path):
    assert call(server, '/api/' + path)[0] == 403
    headers = {'X-Hanni-Token': server.chat.token, 'Origin': 'http://foreign.invalid'}
    assert call(server, '/api/' + path, headers=headers)[0] == 403
    assert not (tmp_path / 'todos.sqlite3').exists()

def test_http_record_write_requires_token_origin_and_no_generic_execution(server):
    body = mutation('task.create', {'title': 'HTTP saved task'})
    origin = f'http://127.0.0.1:{server.server_port}'
    headers = {'Origin': origin, 'Content-Type': 'application/json'}
    assert call(server, '/api/productivity', method='POST', headers=headers, data=body)[0] == 403
    headers['X-Hanni-Token'] = server.chat.token
    status, created = call(server, '/api/productivity', method='POST', headers=headers, data=body)
    assert status == 200 and created['task']['title'] == 'HTTP saved task'
    assert call(server, '/api/productivity', headers=headers)[1]['tasks'][0]['id'] == created['task']['id']
    assert call(server, '/api/productivity', method='POST', headers=headers, data=mutation('powershell.run', {'script': 'bad'}))[0] == 400
    assert call(server, '/api/voice', method='POST', headers=headers, data={'id': str(uuid4()), 'action': 'run-command'})[0] == 400

def test_agents_read_observable_status_without_fictional_workers(server):
    headers = {'X-Hanni-Token': server.chat.token}
    status, result = call(server, '/api/agents', headers=headers)
    assert status == 200
    assert result['agents'][0]['kind'] == 'controller'
    assert result['agents'][0]['status'] == 'unavailable'
    assert not result['awaiting_approvals'] and (not result['approvals_available'])
    assert not result['cancellation_supported']

def test_repeated_model_failure_transitions_are_rate_limited(tmp_path):
    feature = DesktopFeatures(config_for(tmp_path))

    def sample(status):
        return feature.notifications(telemetry={'sampled_at': 1, 'model_status': status}, cluster={'nodes': []}, contract={})
    sample('unavailable')
    sample('ready')
    result = sample('unavailable')
    critical = [item for item in result['items'] if item['priority'] == 'critical']
    assert len(critical) == 1
    assert len(result['items']) == 2

def test_due_reminders_include_all_tasks_across_ingestion_batches(tmp_path):
    from datetime import date, datetime, timezone
    feature = DesktopFeatures(config_for(tmp_path))
    with feature.store.connect() as db:
        db.executemany('INSERT INTO todos VALUES (?,?,?,?,?,?,?,?)', [(str(index), 'due-review-' + str(index), f'Due review task {index}', '', date.today().isoformat(), 1, 'open', datetime.now(timezone.utc).isoformat()) for index in range(101)])
    result = feature.notifications(telemetry={}, cluster={'nodes': []}, contract={})
    assert len(result['items']) == 101
    assert len(feature.notifications(telemetry={}, cluster={'nodes': []}, contract={})['items']) == 101
