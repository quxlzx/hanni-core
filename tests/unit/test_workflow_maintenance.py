"""Age-based private context expiry preserves uncertainty and replay consent."""
from uuid import uuid4
import sqlite3
import pytest
from hanni.workflows.maintenance import prune_terminal, cleanup_artifacts, GC_PREFIX
from hanni.workflows.store import WorkflowStore
from hanni.workflows.types import WorkflowError, fingerprint

@pytest.fixture
def context(tmp_path):
    now = [1800000000.0]
    store = WorkflowStore(tmp_path, clock=lambda: now[0])
    yield (store, now)
    store.close()

def _cancelled(store, goal='Old private context'):
    record = store.create(goal, 'assisted')
    return store.update(record['workflow_id'], record['revision'], {'status': 'cancelled'})

def test_expiry_removes_private_context_but_never_replays_an_old_submit(context):
    store, now = context
    request_id = str(uuid4())
    body = {'operation': 'goal.submit', 'data': {'goal': 'Private retired goal'}}
    calls = []

    def create():
        calls.append(True)
        return {'workflow_id': _cancelled(store, body['data']['goal'])['workflow_id']}
    first = store.execute_request(request_id, body, {'actor': 'owner'}, create)
    now[0] += store.limits.retention_days * 86400
    assert prune_terminal(store) == [first['workflow_id']]
    assert store.list() == []
    with pytest.raises(WorkflowError, match='not found'):
        store.get(first['workflow_id'])
    replay = store.execute_request(request_id, body, {'actor': 'owner'}, create)
    assert replay == {**first, 'expired': True}
    assert len(calls) == 1
    with pytest.raises(WorkflowError, match='different operation'):
        store.execute_request(request_id, {'operation': 'goal.submit', 'data': {'goal': 'Replacement'}}, {'actor': 'owner'}, create)
    assert store.db.execute('SELECT COUNT(*) FROM checkpoints').fetchone()[0] == 0

def test_retention_does_not_delete_active_or_uncertain_work(context):
    store, now = context
    active = store.create('Unfinished context', 'assisted')
    lease = store.claim(str(uuid4()))
    record = store.create('Ambiguous prior effect', 'assisted')
    step = {'step_id': 'write', 'dependencies': [], 'definition_hash': 'fixed', 'arguments': {}, 'criteria': [], 'capability_id': 'fixture.write'}
    record = store.save_plan(record['workflow_id'], 1, {'steps': [step]}, [step], lease=lease)
    record = store.update(record['workflow_id'], record['revision'], {'status': 'ready'})
    invocation, record = store.begin_invocation(record['workflow_id'], record['revision'], 'write', lease=lease, arguments={}, definition_hash='fixed', write=True)
    record = store.update(record['workflow_id'], record['revision'], {'status': 'cancelled'})
    settled = _cancelled(store)
    now[0] += 31 * 86400
    assert prune_terminal(store) == [settled['workflow_id']]
    assert store.get(active['workflow_id'])['status'] == 'submitted'
    assert store.get(record['workflow_id'])['status'] == 'cancelled'
    assert store.history(record['workflow_id'])['invocations'][0]['state'] == 'dispatched'

def test_live_authority_is_retained_until_expiry(context):
    store, now = context
    record = store.create('Do not erase a live grant', 'assisted')
    approval, record = store.add_approval(record['workflow_id'], record['revision'], {'kind': 'plan', 'step_id': None, 'plan_hash': None, 'argument_hash': fingerprint({}), 'definition_hash': None})
    record = store.update(record['workflow_id'], record['revision'], {'status': 'cancelled'})
    with store.transaction() as db:
        db.execute('UPDATE workflows SET updated=? WHERE id=?', (now[0] - 31 * 86400, record['workflow_id']))
    assert prune_terminal(store) == []
    now[0] += store.limits.approval_ttl_seconds + 1
    assert prune_terminal(store) == [record['workflow_id']]

def test_maintenance_is_bounded_and_atomic_when_schema_data_is_invalid(context):
    store, now = context
    records = [_cancelled(store, f'Private {index}') for index in range(3)]
    now[0] += 31 * 86400
    assert len(prune_terminal(store, limit=2)) == 2
    assert len(store.list()) == 1
    for value in (0, 33, True):
        with pytest.raises(WorkflowError, match='maintenance limit'):
            prune_terminal(store, limit=value)
    with store.transaction() as db:
        db.execute('INSERT INTO operations VALUES(?,?,?,?)', (str(uuid4()), 'opaque-hash', now[0], 'corrupted JSON'))
    with pytest.raises(sqlite3.OperationalError):
        prune_terminal(store)
    assert len(store.list()) == 1

def test_artifact_queue_survives_restart_then_only_removes_expired_owned_folder(context):
    store, now = context
    expired = _cancelled(store)
    current = store.create('Keep current output', 'assisted')
    managed = store.root / 'workflows' / 'artifacts'
    target = managed / expired['workflow_id']
    target.mkdir(parents=True)
    (target / 'report.md').write_text('Private old report', encoding='utf-8')
    sibling = managed / current['workflow_id']
    sibling.mkdir()
    (sibling / 'report.md').write_text('Keep this report', encoding='utf-8')
    now[0] += 31 * 86400
    assert prune_terminal(store) == [expired['workflow_id']]
    store.close()
    result = cleanup_artifacts(store)
    assert result['completed'] == [expired['workflow_id']]
    assert not target.exists()
    assert (sibling / 'report.md').read_text() == 'Keep this report'
    assert store.db.execute('SELECT count(*) FROM metadata WHERE key GLOB ?', (GC_PREFIX + '*',)).fetchone()[0] == 0

def test_partial_cleanup_is_bounded_and_queue_is_not_lost(context):
    store, now = context
    expired = _cancelled(store)
    target = store.root / 'workflows' / 'artifacts' / expired['workflow_id']
    target.mkdir(parents=True)
    for index in range(6):
        (target / f'{index}.txt').write_text('private', encoding='utf-8')
    now[0] += 31 * 86400
    prune_terminal(store)
    result = cleanup_artifacts(store, max_entries=3)
    assert result['retained'] == [expired['workflow_id']]
    assert result['removed_files'] <= 3
    assert store.db.execute('SELECT count(*) FROM metadata WHERE key GLOB ?', (GC_PREFIX + '*',)).fetchone()[0] == 1
    for _ in range(4):
        cleanup_artifacts(store, max_entries=3)
    assert not target.exists()

def test_queue_cannot_choose_a_foreign_or_noncanonical_path(context):
    store, _ = context
    outside = store.root.parent / ('keep-' + uuid4().hex + '.txt')
    outside.write_text('outside', encoding='utf-8')
    try:
        with store.transaction() as db:
            db.execute('INSERT INTO metadata VALUES(?,?)', (GC_PREFIX + '../../' + outside.name, '{"workflow_id":"foreign"}'))
        result = cleanup_artifacts(store)
        assert not result['completed']
        assert result['retained']
        assert outside.read_text() == 'outside'
    finally:
        outside.unlink()
