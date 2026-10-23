"""Development persistence tests, not the independent sealed planning evaluation."""
import json
import sqlite3
from uuid import uuid4
import pytest
from hanni.workflows.store import SCHEMA, WorkflowStore
from hanni.workflows.types import LeaseLost, StaleWorkflow, WorkflowError, WorkflowLimits, fingerprint, resource_identity, within_root

class Clock:

    def __init__(self):
        self.now = 1800000000.0

    def __call__(self):
        return self.now

@pytest.fixture
def durable(tmp_path):
    clock = Clock()
    store = WorkflowStore(tmp_path, clock=clock)
    yield (store, clock)
    store.close()

def prepared(store, *, write=False, retry_safe=True):
    lease = store.claim(str(uuid4()))
    record = store.create('Use an isolated development fixture.', 'assisted')
    step = {'step_id': 'measure', 'description': 'Measure fixture', 'dependencies': [], 'capability_id': 'fixture.write' if write else 'fixture.read', 'definition_hash': 'definition-a', 'arguments': {}, 'criteria': []}
    record = store.save_plan(record['workflow_id'], record['revision'], {'steps': [step]}, [step], lease=lease)
    record = store.update(record['workflow_id'], record['revision'], {'status': 'ready'})
    return (record, lease)

def invoke(store, record, lease, *, write=False, retry_safe=True, **kwargs):
    return store.begin_invocation(record['workflow_id'], record['revision'], 'measure', lease=lease, arguments={'value': 4}, definition_hash='definition-a', write=write, retry_safe=retry_safe, **kwargs)

def test_discovery_does_not_create_database(tmp_path):
    store = WorkflowStore(tmp_path)
    assert store.list() == []
    assert not store.path.exists()

def test_limits_are_strict_and_bounded():
    for kwargs in ({'max_retries': 2}, {'max_parallel_reads': True}, {'max_duration_seconds': 999999}, {'lease_seconds': 0}):
        with pytest.raises(WorkflowError):
            WorkflowLimits(**kwargs)

def test_future_database_is_preserved(tmp_path):
    path = tmp_path / 'workflows' / 'workflows.sqlite3'
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=99')
        db.execute('CREATE TABLE future(payload TEXT)')
        db.execute("INSERT INTO future VALUES('retained')")
    before = path.read_bytes()
    store = WorkflowStore(tmp_path)
    with pytest.raises(WorkflowError, match='version'):
        store.list()
    assert path.read_bytes() == before
    assert not path.with_name(path.name + '-wal').exists()

def test_corrupt_database_is_preserved(tmp_path):
    path = tmp_path / 'workflows' / 'workflows.sqlite3'
    path.parent.mkdir()
    path.write_bytes(b'not a database; preserve this')
    before = path.read_bytes()
    with pytest.raises(sqlite3.DatabaseError):
        WorkflowStore(tmp_path).list()
    assert path.read_bytes() == before

def test_operation_replay_is_atomic_and_bound_across_workflows(durable):
    store, _ = durable
    key = str(uuid4())
    body = {'operation': 'goal.submit', 'data': {'goal': 'Fixture', 'mode': 'assisted'}}
    calls = []

    def action():
        calls.append(1)
        return {'workflow_id': store.create('Fixture', 'assisted')['workflow_id']}
    first = store.execute_request(key, body, {'actor': 'owner'}, action)
    assert store.execute_request(key, body, {'actor': 'owner'}, action) == first
    assert len(calls) == 1
    for altered, authority in ((dict(body, data={'goal': 'Other'}), {'actor': 'owner'}), (body, {'actor': 'guest'})):
        with pytest.raises(WorkflowError, match='different operation'):
            store.execute_request(key, altered, authority, action)
    assert len(store.list()) == 1

def test_failed_operation_rolls_back_created_workflow(durable):
    store, _ = durable

    def action():
        store.create('Rollback fixture', 'assisted')
        raise RuntimeError('injected failure')
    with pytest.raises(RuntimeError):
        store.execute_request(str(uuid4()), {}, {}, action)
    assert store.list() == []

def test_revision_compare_and_swap(durable):
    store, _ = durable
    record = store.create('CAS fixture', 'assisted')
    store.update(record['workflow_id'], 1, {'status': 'planning'})
    with pytest.raises(StaleWorkflow):
        store.update(record['workflow_id'], 1, {'status': 'cancelled'})
    assert store.get(record['workflow_id'])['status'] == 'planning'

def test_two_connections_owner_fencing_and_stale_result(durable):
    store, clock = durable
    record, first = prepared(store)
    invocation, _ = invoke(store, record, first)
    second_store = WorkflowStore(store.root, clock=clock)
    try:
        with pytest.raises(LeaseLost):
            second_store.claim(str(uuid4()))
        clock.now += 11
        second = second_store.claim(str(uuid4()))
        assert second['fence'] > first['fence']
        with pytest.raises(LeaseLost):
            store.finish_invocation(invocation['invocation_id'], lease=first, result={'ok': True}, step_status='verified')
        assert second_store.recover(second) == [record['workflow_id']]
        assert second_store.get(record['workflow_id'])['status'] == 'paused'
        assert second_store.steps(record['workflow_id'])[0]['status'] == 'pending'
    finally:
        second_store.close()

def test_invocation_observer_sees_committed_state_in_independent_connection(durable):
    store, _ = durable
    record, lease = prepared(store)
    seen = []

    def observe(stage, event):
        with sqlite3.connect(store.path) as db:
            row = db.execute('SELECT state FROM invocations WHERE id=?', (event['invocation_id'],)).fetchone()
        seen.append((stage, row[0]))
    store.observer = observe
    invocation, _ = invoke(store, record, lease)
    store.finish_invocation(invocation['invocation_id'], lease=lease, result={'ok': True, 'data': {'measurement': 4}}, step_status='verified', verification={'scope': 'fixture_measurement'})
    assert seen == [('before_dispatch', 'dispatched'), ('after_result', 'dispatched')]
    assert store.steps(record['workflow_id'])[0]['status'] == 'verified'

def test_uncertain_write_is_never_replayed_and_blocks_conflicting_write(durable):
    store, clock = durable
    record, lease = prepared(store, write=True)
    invocation, running = invoke(store, record, lease, write=True, retry_safe=False, resource_keys=('same-resource',))
    clock.now += 11
    replacement = store.claim(str(uuid4()))
    store.recover(replacement)
    assert store.get(record['workflow_id'])['status'] == 'blocked'
    assert store.history(record['workflow_id'])['invocations'][0]['state'] == 'uncertain'
    blocked = store.get(record['workflow_id'])
    with pytest.raises(WorkflowError):
        invoke(store, blocked, replacement, write=True)
    other = store.create('Second write fixture', 'assisted')
    step = {'step_id': 'measure', 'dependencies': [], 'definition_hash': 'definition-a'}
    other = store.save_plan(other['workflow_id'], other['revision'], {'steps': [step]}, [step], lease=replacement)
    other = store.update(other['workflow_id'], other['revision'], {'status': 'ready'})
    with pytest.raises(WorkflowError, match='conflicting write'):
        invoke(store, other, replacement, write=True, resource_keys=('same-resource',))
    assert len(store.history(record['workflow_id'])['invocations']) == 1

def test_exact_approval_is_consumed_atomically(durable):
    store, _ = durable
    record, lease = prepared(store, write=True)
    binding = {'step_id': 'measure', 'kind': 'action', 'plan_hash': record['plan_hash'], 'argument_hash': fingerprint({'value': 4}), 'definition_hash': 'definition-a'}
    approval, record = store.add_approval(record['workflow_id'], record['revision'], binding)
    _, record = store.decide_approval(record['workflow_id'], record['revision'], approval['approval_id'], 'approved', binding)
    invoke(store, record, lease, write=True, approval_id=approval['approval_id'])
    assert store.history(record['workflow_id'])['approvals'][0]['state'] == 'consumed'

@pytest.mark.parametrize('alteration', ['arguments', 'definition', 'expired', 'revoked'])
def test_stale_approval_cannot_dispatch(durable, alteration):
    store, clock = durable
    record, lease = prepared(store, write=True)
    binding = {'step_id': 'measure', 'kind': 'action', 'plan_hash': record['plan_hash'], 'argument_hash': fingerprint({'value': 9 if alteration == 'arguments' else 4}), 'definition_hash': 'other' if alteration == 'definition' else 'definition-a'}
    approval, record = store.add_approval(record['workflow_id'], record['revision'], binding)
    _, record = store.decide_approval(record['workflow_id'], record['revision'], approval['approval_id'], 'approved', binding)
    if alteration == 'expired':
        clock.now += 301
        lease = store.claim(lease['token'])
    if alteration == 'revoked':
        _, record = store.decide_approval(record['workflow_id'], record['revision'], approval['approval_id'], 'revoked', {})
    with pytest.raises(WorkflowError):
        invoke(store, record, lease, write=True, approval_id=approval['approval_id'])
    assert store.history(record['workflow_id'])['invocations'] == []

def test_clock_rollback_fails_closed(durable):
    store, clock = durable
    lease = store.claim(str(uuid4()))
    clock.now -= 1
    with pytest.raises(WorkflowError, match='backwards'):
        store.heartbeat(lease)
    with pytest.raises(WorkflowError, match='backwards'):
        store.create('Clock fixture', 'assisted')

def test_cycles_and_payload_limits_are_rejected(durable):
    store, _ = durable
    lease = store.claim(str(uuid4()))
    record = store.create('Cycle fixture', 'assisted')
    steps = [{'step_id': 'a', 'dependencies': ['b']}, {'step_id': 'b', 'dependencies': ['a']}]
    with pytest.raises(WorkflowError, match='cycle'):
        store.save_plan(record['workflow_id'], 1, {'steps': steps}, steps, lease=lease)
    assert store.steps(record['workflow_id']) == []
    with pytest.raises(WorkflowError, match='size limit'):
        store.update(record['workflow_id'], 1, {'private': 'x' * 70000})

def test_path_aliases_have_one_resource_identity(tmp_path):
    target = tmp_path / 'folder' / 'fixture.txt'
    assert resource_identity(target) == resource_identity(tmp_path / 'folder' / '..' / 'folder' / 'fixture.txt')
    assert within_root(target, tmp_path)
    assert not within_root(tmp_path.parent / 'outside.txt', tmp_path)

@pytest.mark.parametrize('payload', [{'password': 'four'}, {'nested': [{'api_key': 'opaque'}]}, {'auth': {'refresh_token': 'abc'}}, {'private-key': 'x'}, {'nested': {'token': 'four'}}])
def test_opaque_short_credentials_are_never_persisted(durable, payload):
    store, _ = durable
    record = store.create('Privacy fixture', 'assisted')
    with pytest.raises(WorkflowError, match='Credential'):
        store.update(record['workflow_id'], 1, {'private': payload})
    assert 'private' not in store.get(record['workflow_id'])

def test_terminal_state_is_immutable_and_illegal_transition_rejected(durable):
    store, _ = durable
    record = store.create('Transition fixture', 'assisted')
    with pytest.raises(WorkflowError, match='transition'):
        store.update(record['workflow_id'], 1, {'status': 'completed'})
    terminal = store.update(record['workflow_id'], 1, {'status': 'cancelled'})
    with pytest.raises(WorkflowError, match='immutable'):
        store.update(record['workflow_id'], terminal['revision'], {'status': 'running'})
    with pytest.raises(WorkflowError, match='immutable'):
        store.update(record['workflow_id'], terminal['revision'], {'error': 'changed'})

def test_plan_hash_binds_steps_and_never_trusts_supplied_verification(durable):
    store, _ = durable
    lease = store.claim(str(uuid4()))
    record = store.create('Exact executable plan fixture', 'assisted')
    steps = [{'step_id': 'read', 'dependencies': [], 'status': 'verified', 'verification': {'status': 'VERIFIED'}, 'arguments': {'value': 4}}]
    with pytest.raises(WorkflowError, match='exact executable'):
        store.save_plan(record['workflow_id'], 1, {'steps': []}, steps, lease=lease)
    record = store.save_plan(record['workflow_id'], 1, {'steps': steps}, steps, lease=lease)
    saved = store.steps(record['workflow_id'])[0]
    assert saved['status'] == 'pending' and saved['verification'] is None
    record = store.update(record['workflow_id'], record['revision'], {'status': 'cancelled'})
    with pytest.raises(WorkflowError, match='cannot be replaced'):
        store.save_plan(record['workflow_id'], record['revision'], {'steps': steps}, steps, lease=lease)

def test_unrecognized_extra_index_is_preserved_before_wal(tmp_path):
    path = tmp_path / 'workflows' / 'workflows.sqlite3'
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute('CREATE INDEX unexpected_index ON workflows(status)')
        db.execute('PRAGMA user_version=1')
    before = path.read_bytes()
    store = WorkflowStore(tmp_path)
    try:
        with pytest.raises(WorkflowError, match='schema'):
            store.list()
    finally:
        store.close()
    assert path.read_bytes() == before
    assert not path.with_name(path.name + '-wal').exists()
