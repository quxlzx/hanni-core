"""Independent local retention/cleanup boundaries; no user or repository data.

Prepared against the draft public maintenance API. Execute only after its source
freeze. Filesystem tests use real isolated temporary files, including a Windows
junction when supported, rather than assuming a path-prefix check is sufficient.
"""
from pathlib import Path
import os
import pytest
from hanni.workflows.maintenance import cleanup_artifacts, prune_terminal
from hanni.workflows.store import WorkflowStore

@pytest.fixture
def maintenance(tmp_path):
    now = [1800000000.0]
    store = WorkflowStore(tmp_path / 'managed', clock=lambda: now[0])
    try:
        yield (store, now, tmp_path)
    finally:
        store.close()

def expire(store, now):
    record = store.create('Isolated retention boundary', 'assisted')
    record = store.update(record['workflow_id'], record['revision'], {'status': 'cancelled'})
    now[0] += store.limits.retention_days * 86400 + 1
    assert prune_terminal(store) == [record['workflow_id']]
    return record['workflow_id']

def test_cleanup_deletes_only_exact_expired_id_and_preserves_live_sibling(maintenance):
    store, now, _ = maintenance
    expired = expire(store, now)
    live = store.create('Do not delete this active sibling', 'assisted')['workflow_id']
    artifacts = store.root / 'workflows' / 'artifacts'
    for key in (expired, live):
        (artifacts / key).mkdir(parents=True)
        (artifacts / key / 'report.txt').write_text('Private fixture', encoding='utf-8')
    result = cleanup_artifacts(store)
    assert result['completed'] == [expired]
    assert not (artifacts / expired).exists()
    assert (artifacts / live / 'report.txt').read_text(encoding='utf-8') == 'Private fixture'

def test_bounded_partial_cleanup_keeps_durable_queue_until_files_removed(maintenance):
    store, now, _ = maintenance
    expired = expire(store, now)
    target = store.root / 'workflows' / 'artifacts' / expired
    target.mkdir(parents=True)
    for index in range(6):
        (target / f'{index}.txt').write_text('Fixture', encoding='utf-8')
    first = cleanup_artifacts(store, max_entries=2)
    assert expired in first['retained']
    assert store.db.execute('SELECT count(*) FROM metadata WHERE key=?', ('artifact_gc:' + expired,)).fetchone()[0] == 1
    for _ in range(8):
        cleanup_artifacts(store, max_entries=2)
    assert not target.exists()
    assert store.db.execute('SELECT count(*) FROM metadata WHERE key=?', ('artifact_gc:' + expired,)).fetchone()[0] == 0

def test_mismatched_queue_identity_cannot_remove_any_folder(maintenance):
    store, now, _ = maintenance
    expired = expire(store, now)
    target = store.root / 'workflows' / 'artifacts' / expired
    target.mkdir(parents=True)
    marker = target / 'report.txt'
    marker.write_text('Retain malformed identity', encoding='utf-8')
    with store.transaction() as db:
        db.execute('UPDATE metadata SET value=? WHERE key=?', ('{"workflow_id":"wf_' + 'f' * 32 + '"}', 'artifact_gc:' + expired))
    assert cleanup_artifacts(store)['retained'] == [expired]
    assert marker.read_text(encoding='utf-8') == 'Retain malformed identity'

def test_real_parent_junction_refused_without_touching_outside_files(maintenance):
    store, now, temp_root = maintenance
    expired = expire(store, now)
    outside = temp_root / 'outside'
    target = outside / expired
    target.mkdir(parents=True)
    marker = target / 'retain.txt'
    marker.write_text('Outside boundary', encoding='utf-8')
    parent = store.root / 'workflows' / 'artifacts'
    parent.parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        parent.symlink_to(outside, target_is_directory=True)
        junction = False
    else:
        import _winapi
        _winapi.CreateJunction(str(outside), str(parent))
        junction = True
    try:
        result = cleanup_artifacts(store)
        assert result['retained'] == [expired]
        assert marker.read_text(encoding='utf-8') == 'Outside boundary'
    finally:
        parent.rmdir() if junction else parent.unlink()
