from concurrent.futures import ThreadPoolExecutor
import sqlite3
from uuid import uuid4
import pytest
from hanni.dashboard.productivity import ProductivityStore, SCHEMA_VERSION
from hanni.tools.todos import TodoStore

def mutate(store, operation, data, request_id=None):
    return store.mutate(operation, data, request_id or str(uuid4()))

def test_existing_todos_survive_migration_and_cli_updates_are_visible(tmp_path):
    original = TodoStore(tmp_path).add({'title': 'Existing assignment', 'due': '2026-10-20', 'course': 'Math'})
    store = ProductivityStore(tmp_path)
    row = store.snapshot()['tasks'][0]
    assert row['id'] == original['id'] and row['due'] == original['due']
    assert row['priority'] == 'normal' and row['project_id'] is None
    assert store.snapshot()['schema_version'] == SCHEMA_VERSION
    assert list((tmp_path / 'workspace-backups').glob('*.sqlite3'))
    TodoStore(tmp_path).complete(original['id'])
    assert store.snapshot()['tasks'][0]['status'] == 'completed'
    with pytest.raises(ValueError, match='changed'):
        mutate(store, 'task.delete', {'task_id': row['id'], 'expected_fingerprint': row['fingerprint']})

def test_task_project_note_link_persistence_and_explicit_delete(tmp_path):
    store = ProductivityStore(tmp_path)
    project = mutate(store, 'project.create', {'name': 'Local project', 'description': 'Personal work'})['project']
    task = mutate(store, 'task.create', {'title': 'Read the guide', 'priority': 'high', 'project_id': project['id']})['task']
    assert task['due'] == ''
    note = mutate(store, 'note.create', {'project_id': project['id'], 'title': 'Notes', 'body': 'First line\nSecond line'})['note']
    link = mutate(store, 'link.create', {'project_id': project['id'], 'label': 'Guide', 'target': 'C:\\Projects\\Guide.md', 'kind': 'file'})['link']
    restored = ProductivityStore(tmp_path).snapshot()
    assert restored['tasks'][0]['id'] == task['id']
    assert restored['notes'][0]['body'] == 'First line\nSecond line'
    assert restored['links'][0]['id'] == link['id']
    changed = mutate(store, 'task.update', {'task_id': task['id'], 'expected_fingerprint': task['fingerprint'], 'title': 'Read the guide', 'course': '', 'due': '2026-10-25', 'priority': 'low', 'project_id': project['id'], 'status': 'completed'})['task']
    assert TodoStore(tmp_path).get(task['id'])['status'] == 'completed'
    assert changed['due'].startswith('2026-10-25')
    mutate(store, 'project.delete', {'project_id': project['id'], 'expected_fingerprint': project['fingerprint']})
    after = store.snapshot()
    assert not after['projects'] and (not after['notes']) and (not after['links'])
    assert after['tasks'][0]['project_id'] is None

def test_atomic_uuid_dedup_is_concurrent_and_payload_bound(tmp_path):
    store = ProductivityStore(tmp_path)
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: mutate(store, 'task.create', {'title': 'One task'}, request_id), range(4)))
    assert len({result['task']['id'] for result in results}) == 1
    assert len(store.snapshot()['tasks']) == 1
    assert mutate(ProductivityStore(tmp_path), 'task.create', {'title': 'One task'}, request_id) == results[0]
    with pytest.raises(ValueError, match='bound'):
        mutate(store, 'task.create', {'title': 'Different task'}, request_id)
    with pytest.raises(ValueError, match='UUID'):
        mutate(store, 'task.create', {'title': 'No task'}, 'not-a-uuid')

def test_file_link_preserves_exact_internal_spaces_and_rejects_control_characters(tmp_path):
    store = ProductivityStore(tmp_path)
    project = mutate(store, 'project.create', {'name': 'Files'})['project']
    target = 'C:\\Projects\\my  report.md'
    link = mutate(store, 'link.create', {'project_id': project['id'], 'label': 'Report', 'target': target, 'kind': 'file'})['link']
    assert link['target'] == target
    with pytest.raises(ValueError, match='control characters'):
        mutate(store, 'link.create', {'project_id': project['id'], 'label': 'Invalid', 'target': 'C:\\Projects\\bad\nname.md', 'kind': 'file'})

def test_failed_mutation_rolls_back_records_and_ledger(tmp_path):
    store = ProductivityStore(tmp_path)
    request_id = str(uuid4())
    with pytest.raises(ValueError):
        mutate(store, 'task.create', {'title': 'Invalid', 'project_id': 'missing'}, request_id)
    assert not store.snapshot()['tasks']
    assert mutate(store, 'task.create', {'title': 'Valid'}, request_id)['task']['title'] == 'Valid'

@pytest.mark.parametrize('operation,data', [('task.create', {'title': 'My password is secret'}), ('task.create', {'title': 'Bad date', 'due': 'tomorrow'}), ('task.create', {'title': 'Bad type', 'due': []}), ('task.create', {'title': 'Bad priority', 'priority': []}), ('task.create', {'title': 'Unknown field', 'command': 'powershell'}), ('not-an-operation', {})])
def test_invalid_inputs_cannot_write(tmp_path, operation, data):
    store = ProductivityStore(tmp_path)
    with pytest.raises(ValueError):
        mutate(store, operation, data)
    assert not store.snapshot()['tasks']

def test_backup_contains_existing_tasks_and_workspace_records(tmp_path):
    store = ProductivityStore(tmp_path)
    task = mutate(store, 'task.create', {'title': 'Backed up'})['task']
    result = mutate(store, 'workspace.backup', {})
    with sqlite3.connect(tmp_path / 'workspace-backups' / result['backup_file']) as backup:
        assert backup.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        assert backup.execute('SELECT title FROM todos WHERE id=?', (task['id'],)).fetchone()[0] == 'Backed up'
        assert backup.execute("SELECT value FROM workspace_meta WHERE key='schema_version'").fetchone()[0] == str(SCHEMA_VERSION)

def test_unknown_schema_refuses_to_overwrite(tmp_path):
    store = ProductivityStore(tmp_path)
    with store.connect() as db:
        db.execute("UPDATE workspace_meta SET value='99'")
    with pytest.raises(RuntimeError, match='Unsupported'):
        ProductivityStore(tmp_path)
    with store.connect() as db:
        assert db.execute('SELECT value FROM workspace_meta').fetchone()[0] == '99'

def test_unknown_future_schema_does_not_add_existing_task_table(tmp_path):
    with sqlite3.connect(tmp_path / 'todos.sqlite3') as db:
        db.execute('CREATE TABLE workspace_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT INTO workspace_meta VALUES ('schema_version','99')")
    with pytest.raises(RuntimeError, match='Unsupported'):
        ProductivityStore(tmp_path)
    with sqlite3.connect(tmp_path / 'todos.sqlite3') as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='todos'").fetchone() is None

def test_calendar_cache_survives_store_restart(tmp_path):
    store = ProductivityStore(tmp_path)
    payload = {'events': [{'title': 'Owner calendar', 'start': '2026-10-20'}]}
    store.save_calendar_cache('2026-10-20:7', payload)
    assert ProductivityStore(tmp_path).get_calendar_cache('2026-10-20:7')['payload'] == payload
    assert store.get_calendar_cache('missing') is None

def test_cli_due_list_excludes_optional_undated_workspace_tasks(tmp_path):
    store = ProductivityStore(tmp_path)
    undated = mutate(store, 'task.create', {'title': 'Unscheduled work'})['task']
    dated = mutate(store, 'task.create', {'title': 'Due assignment', 'due': '2020-01-01'})['task']
    rows = TodoStore(tmp_path).list({'days': 7}, due_only=True)
    assert dated['id'] in {row['id'] for row in rows}
    assert undated['id'] not in {row['id'] for row in rows}

def notification(key, category='tasks', priority='informational'):
    return {'key': key, 'category': category, 'priority': priority, 'title': 'Completed task', 'message': 'Recorded completion.', 'target': {'screen': 'tasks'}}

def test_notification_history_dedup_preferences_and_rate_limit(tmp_path):
    store = ProductivityStore(tmp_path)
    store.ingest([notification('one'), notification('one')])
    first = store.notifications()['items'][0]
    store.notification_mutate('notification.read', {'notification_id': first['id']}, str(uuid4()))
    assert store.notifications()['items'][0]['read']
    store.ingest([notification(str(index)) for index in range(10)])
    assert len(store.notifications()['items']) == 5
    store.ingest([notification('urgent', priority='critical')])
    assert len(store.notifications()['items']) == 6
    store.notification_mutate('notification.clear', {}, str(uuid4()))
    store.ingest([notification('one')])
    assert all((item['dismissed'] for item in store.notifications()['items']))
    store.notification_mutate('notification.preferences', {'categories': {'cluster': False}}, str(uuid4()))
    store.ingest([notification('offline', category='cluster', priority='critical')])
    restarted = ProductivityStore(tmp_path).notifications()
    assert not restarted['preferences']['categories']['cluster']
    assert not any((item['key'] == 'offline' for item in restarted['items']))

def test_notification_mutation_uuid_dedups_without_reclearing_new_events(tmp_path):
    store = ProductivityStore(tmp_path)
    store.ingest([notification('old')])
    request_id = str(uuid4())
    store.notification_mutate('notification.clear', {}, request_id)
    store.ingest([notification('new')])
    store.notification_mutate('notification.clear', {}, request_id)
    assert not next((item for item in store.notifications()['items'] if item['key'] == 'new'))['dismissed']
