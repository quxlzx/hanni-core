"""Independent exposed M1 persistence tests; no WorkflowService exists yet.

Subprocess effects below are an isolated fsynced ledger at the store boundary,
not production workflow execution, model inference or an external operation.
"""
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
from uuid import uuid4
import pytest
from hanni.workflows.store import SCHEMA, WorkflowStore
from hanni.workflows.types import WorkflowError, LeaseLost, canonical_json, fingerprint
from scripts.v3_review.fixtures import ControlledClock
ROOT = Path(__file__).resolve().parents[2]

def prepared(store, lease, steps=None):
    steps = steps or [{'step_id': 'action', 'dependencies': [], 'capability_id': 'fixture.action', 'definition_hash': 'definition-v1', 'arguments': {}, 'criteria': []}]
    record = store.create('Independent persistence fixture', 'assisted')
    record = store.save_plan(record['workflow_id'], record['revision'], {'steps': steps}, steps, lease=lease)
    return store.update(record['workflow_id'], record['revision'], {'status': 'ready'}, lease=lease)

def invoke(store, record, lease, step='action', *, write=True, retry_safe=False):
    return store.begin_invocation(record['workflow_id'], record['revision'], step, lease=lease, arguments={}, definition_hash='definition-v1', write=write, retry_safe=retry_safe, resource_keys=('isolated-fixture',))

@pytest.mark.parametrize('field', ['password', 'access_token', 'client_secret', 'token'])
def test_nested_short_credential_fields_are_not_persistable(field):
    with pytest.raises(WorkflowError):
        canonical_json({'nested': [{'metadata': {field: 'abcd'}}]})

@pytest.mark.parametrize('kind', ['list', 'dict'])
def test_deep_finite_json_is_rejected_with_safe_workflow_error(kind):
    payload = 'value'
    for _ in range(650):
        payload = [payload] if kind == 'list' else {'value': payload}
    with pytest.raises(WorkflowError):
        canonical_json(payload)

def test_mixed_abandoned_write_and_read_cannot_hide_write_uncertainty(tmp_path):
    clock = ControlledClock()
    store = WorkflowStore(tmp_path, clock=clock.wall)
    try:
        first = store.claim(str(uuid4()))
        steps = [{'step_id': name, 'dependencies': [], 'capability_id': 'fixture.' + name, 'definition_hash': 'definition-v1', 'arguments': {}, 'criteria': []} for name in ('write', 'read')]
        record = prepared(store, first, steps)
        _, record = invoke(store, record, first, 'write', write=True)
        _, record = invoke(store, record, first, 'read', write=False, retry_safe=True)
        clock.advance(11)
        second = store.claim(str(uuid4()))
        store.recover(second)
        recovered = store.get(record['workflow_id'])
        assert recovered['status'] == 'blocked', 'A later safe read must not overwrite uncertain-write recovery status'
        states = {row['step_id']: row['status'] for row in store.steps(record['workflow_id'])}
        assert states == {'write': 'blocked', 'read': 'pending'}
        assert any((row['state'] == 'uncertain' for row in store.history(record['workflow_id'])['invocations']))
    finally:
        store.close()

def test_failed_approval_cas_does_not_consume_or_dispatch(tmp_path):
    clock = ControlledClock()
    store = WorkflowStore(tmp_path, clock=clock.wall)
    try:
        lease = store.claim(str(uuid4()))
        record = prepared(store, lease)
        binding = {'step_id': 'action', 'kind': 'action', 'plan_hash': record['plan_hash'], 'argument_hash': fingerprint({}), 'definition_hash': 'definition-v1'}
        approval, record = store.add_approval(record['workflow_id'], record['revision'], binding)
        approval, record = store.decide_approval(record['workflow_id'], record['revision'], approval['approval_id'], 'approved', binding)
        with pytest.raises(WorkflowError):
            store.begin_invocation(record['workflow_id'], record['revision'] - 1, 'action', lease=lease, arguments={}, definition_hash='definition-v1', write=True, approval_id=approval['approval_id'])
        history = store.history(record['workflow_id'])
        assert history['approvals'][0]['state'] == 'approved'
        assert history['invocations'] == []
        assert store.steps(record['workflow_id'])[0]['status'] == 'pending'
    finally:
        store.close()

def test_unrecognized_version_one_schema_preserves_database_bytes(tmp_path):
    path = tmp_path / 'workflows' / 'workflows.sqlite3'
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute('ALTER TABLE workflows RENAME COLUMN payload TO unexpected_payload')
        db.execute('PRAGMA user_version=1')
    before = path.read_bytes()
    store = WorkflowStore(tmp_path)
    try:
        with pytest.raises((WorkflowError, sqlite3.DatabaseError)):
            store.list()
    finally:
        store.close()
    assert path.read_bytes() == before, 'Unknown schema must be rejected before changing journal mode/header'
    assert not path.with_name(path.name + '-wal').exists()

@pytest.mark.parametrize('phase', ['before_dispatch', 'after_result'])
def test_real_subprocess_crash_leaves_uncertain_write_without_replay(tmp_path, phase):
    child = "\nimport json,os,sys\nfrom pathlib import Path\nfrom uuid import uuid4\nfrom hanni.workflows.store import WorkflowStore\nroot=Path(sys.argv[1]); phase=sys.argv[2]\ndef observer(stage,event):\n if stage==phase: os._exit(97)\nstore=WorkflowStore(root,clock=lambda:1893456000.0,observer=observer)\nlease=store.claim(str(uuid4())); r=store.create('Owned crash fixture','assisted')\nstep={'step_id':'action','dependencies':[],'capability_id':'fixture.action','definition_hash':'definition-v1','arguments':{},'criteria':[]}\nr=store.save_plan(r['workflow_id'],r['revision'],{'steps':[step]},[step],lease=lease)\nr=store.update(r['workflow_id'],r['revision'],{'status':'ready'},lease=lease)\n(root/'identity.json').write_text(json.dumps({'workflow_id':r['workflow_id']}),encoding='utf8')\ninv,r=store.begin_invocation(r['workflow_id'],r['revision'],'action',lease=lease,arguments={},definition_hash='definition-v1',write=True,resource_keys=('isolated-fixture',))\nwith (root/'external-effect.txt').open('a',encoding='utf8') as f:\n f.write('one-effect\\n');f.flush();os.fsync(f.fileno())\nstore.finish_invocation(inv['invocation_id'],lease=lease,result={'ok':True},step_status='unverified')\nraise AssertionError('Crash observer did not terminate owned child')\n"
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    result = subprocess.run([sys.executable, '-c', child, str(tmp_path), phase], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == 97, result.stderr
    key = json.loads((tmp_path / 'identity.json').read_text())['workflow_id']
    effect = tmp_path / 'external-effect.txt'
    expected = '' if phase == 'before_dispatch' else 'one-effect\n'
    assert (effect.read_text() if effect.exists() else '') == expected
    store = WorkflowStore(tmp_path, clock=lambda: 1893456011.0)
    try:
        lease = store.claim(str(uuid4()))
        assert store.recover(lease) == [key]
        record = store.get(key)
        assert record['status'] == 'blocked'
        assert store.history(key)['invocations'][0]['state'] == 'uncertain'
        with pytest.raises(WorkflowError):
            invoke(store, record, lease)
        assert (effect.read_text() if effect.exists() else '') == expected
        assert len(store.history(key)['invocations']) == 1
    finally:
        store.close()

def test_two_real_processes_cannot_both_claim_live_owner(tmp_path):
    store = WorkflowStore(tmp_path, clock=lambda: 1893456000.0)
    store.create('Two owned child processes', 'assisted')
    store.close()
    child = "\nimport json,sys\nfrom uuid import uuid4\nfrom hanni.workflows.store import WorkflowStore\nfrom hanni.workflows.types import LeaseLost\ns=WorkflowStore(sys.argv[1],clock=lambda:1893456000.0)\ntry:\n try: lease=s.claim(str(uuid4()));print(json.dumps({'claimed':True,'fence':lease['fence']}))\n except LeaseLost: print(json.dumps({'claimed':False}))\nfinally:s.close()\n"
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    processes = [subprocess.Popen([sys.executable, '-c', child, str(tmp_path)], cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    answers = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, stderr
            answers.append(json.loads(stdout))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert sum((row['claimed'] for row in answers)) == 1
