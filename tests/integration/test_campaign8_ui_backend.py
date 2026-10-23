"""Original disposable backend contracts; these are not native acceptance tests."""
import json
import http.client
from uuid import uuid4
import pytest
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.inventory import inventory
from scripts.campaign8_ui.plan import validate_input

@pytest.fixture
def backend(tmp_path):
    with original_backend(tmp_path / 'original-runtime') as instance:
        yield instance
    assert instance.closed and (not instance.thread.is_alive())

def payload(operation, data):
    return {'id': str(uuid4()), 'operation': operation, 'data': data, 'confirmed': True}

def test_inventory_counts_dynamic_source_and_never_claims_native_success():
    result = inventory()
    assert result['routes'] and len({r['route'] for r in result['routes']}) == len(result['routes'])
    assert result['counts']['native_observed_controls'] is None
    assert result['counts']['native_passes'] is None
    slots = [c for m in result['modules'] for c in m['controls']]
    assert len(slots) == result['counts']['static_interactive_slots']
    assert all((c['outcome'] == 'NOT_RUN' and c['line'] > 0 for c in slots))

@pytest.mark.parametrize('case', [{'operation': 'measure_layout', 'expected': 'answer'}, {'operation': 'keyboard', 'javascript': 'unsafe'}, {'operation': 'arbitrary-post'}, {'operation': 'native_window', 'action': 'kill'}])
def test_native_input_authority_does_not_accept_oracles_or_generic_execution(case):
    with pytest.raises(ValueError):
        validate_input(case)

def test_original_private_get_and_write_authority_reject_without_storage_change(backend):
    status, _ = backend.request('/api/productivity', authorized=False)
    assert status == 403
    request = payload('task.create', {'title': 'Synthetic blocked task'})
    status, _ = backend.request('/api/productivity', method='POST', body=request, origin='http://foreign.invalid')
    assert status == 403
    assert not (backend.root / 'todos.sqlite3').exists()

def test_task_create_idempotency_update_conflict_and_delete_have_actual_sqlite_readback(backend):
    request = payload('task.create', {'title': 'Synthetic native QA task'})
    status, created = backend.request('/api/productivity', method='POST', body=request)
    assert status == 200
    status, repeated = backend.request('/api/productivity', method='POST', body=request)
    assert status == 200 and repeated == created
    task = created['task']
    from hanni.tools.todos import TodoStore
    assert TodoStore(backend.root).get(task['id'])['title'] == request['data']['title']
    status, data = backend.request('/api/productivity')
    assert status == 200 and len(data['tasks']) == 1
    current = data['tasks'][0]
    stale = payload('task.update', {'task_id': task['id'], 'title': 'Stale mutation', 'expected_fingerprint': 'not-current'})
    status, _ = backend.request('/api/productivity', method='POST', body=stale)
    assert status == 400
    delete = payload('task.delete', {'task_id': task['id'], 'expected_fingerprint': current['fingerprint']})
    status, _ = backend.request('/api/productivity', method='POST', body=delete)
    assert status == 200
    with pytest.raises(ValueError, match='No task with that exact ID'):
        TodoStore(backend.root).get(task['id'])
    status, data = backend.request('/api/productivity')
    assert status == 200 and data['tasks'] == []

def test_calendar_account_discovery_has_explicit_empty_vault_and_no_provider_call(backend):
    status, data = backend.request('/api/calendar?start_date=2026-10-10&days=7&refresh=1')
    assert status == 200 and (not data['connected']) and (not data['events'])
    assert all((not row['connected'] for row in data['accounts']))
    assert backend.registry.google_access.vault.__class__.__name__ == 'EmptyGoogleVault'

def test_original_memory_read_and_deleted_record_are_grounded_in_owned_store(backend):
    store = backend.features.memory_store()
    record, _ = store.remember('Synthetic QA prefers concise notes', source='owner_explicit.campaign8')
    status, data = backend.request('/api/memory/explorer?limit=30')
    assert status == 200 and any((r['id'] == record.id for r in data['records']))
    store.delete(record.id, expected_updated_at=record.updated_at.isoformat())
    status, data = backend.request('/api/memory/record/' + record.id)
    assert status == 200 and data['record'] is None

@pytest.mark.parametrize('path', ['/api/awareness', '/api/voice'])
def test_missing_screen_and_inactive_original_voice_never_become_available(backend, path):
    status, data = backend.request(path)
    assert status == 200 and data['available'] is False
    if path.endswith('awareness'):
        assert not data['capture_active'] and (not data['context_available'])
    else:
        assert not data['active'] and (not data['microphone_active'])

def test_actual_chat_store_has_no_controller_or_fabricated_model_answer(backend):
    status, data = backend.request('/api/chat')
    assert status == 200 and (not data['ready']) and (not data['messages'])
    assert 'token' not in json.dumps(backend.ready())
    status, _ = backend.request('/api/chat', method='POST', body={'id': str(uuid4()), 'message': 'Synthetic unavailable-model probe'})
    assert status == 409
    assert not backend.chat.snapshot()['messages']

def test_owned_shutdown_reaches_original_event_and_chat_lifecycle_only(backend):
    status, data = backend.request('/api/shutdown', method='POST', body={})
    assert status == 202 and data['stopping'] and backend.stop.is_set()
    assert backend.chat.stopping

def test_owned_fixture_rejects_existing_data_directory(tmp_path):
    root = tmp_path / 'existing'
    root.mkdir()
    with pytest.raises(ValueError, match='fresh disposable'):
        with original_backend(root):
            pass

@pytest.mark.parametrize('port', [True, -1, 80, 8080, 8765, 65536, '8766'])
def test_explicit_owned_port_rejects_reserved_or_invalid_targets_before_store_creation(tmp_path, port):
    root = tmp_path / 'not-created'
    with pytest.raises(ValueError):
        with original_backend(root, port=port):
            pass
    assert not root.exists()

def test_signed_owned_shutdown_then_same_port_rebind_refreshes_original_token_and_store(tmp_path):
    with original_backend(tmp_path / 'before-reconnect') as first:
        owned_port = first.server.server_port
        previous_url = first.url
        previous_token = first.chat.token
        status, _ = first.request('/api/productivity', method='POST', body=payload('task.create', {'title': 'Only the old isolated store'}))
        assert status == 200
        status, result = first.request('/api/shutdown', method='POST', body={})
        assert status == 202 and result['stopping'] and first.stop.is_set()
    assert not first.thread.is_alive() and first.chat.closed
    with original_backend(tmp_path / 'after-reconnect', port=owned_port) as second:
        assert second.url == previous_url and second.chat.token != previous_token
        connection = http.client.HTTPConnection('127.0.0.1', owned_port, timeout=5)
        try:
            connection.request('GET', '/api/productivity', headers={'Origin': second.url, 'X-Hanni-Token': previous_token})
            response = connection.getresponse()
            response.read()
            assert response.status == 403
        finally:
            connection.close()
        status, result = second.request('/api/productivity')
        assert status == 200 and result['tasks'] == []
        status, result = second.request('/api/chat')
        assert status == 200 and (not result['ready']) and (not second.chat.stopping)
        assert not result['messages']
        assert all((call['outcome'] == 'CONTROLLED_UNAVAILABLE' for call in second.calls))
    assert not second.thread.is_alive() and second.chat.closed
