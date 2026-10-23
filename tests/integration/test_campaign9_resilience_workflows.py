"""Original native workflow authority and durable fault controls, no real model."""
from copy import deepcopy
import errno
import json
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4
import pytest
from hanni.core.identity import Actor
from hanni.core.shutdown import StopSource
from hanni.workflows.types import WorkflowError
from hanni.workflows.store import WorkflowStore
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture
from tests.integration.test_workflow_service_verifier import artifact_plan, artifact_path, criterion, drive_reviewed, queue_plan, read_step, row, step

def source(tmp_path):
    path = tmp_path / 'authorized-source.txt'
    path.write_text('Controlled original source evidence.', encoding='utf-8')
    return path

def write_goal(path):
    return 'Read ' + str(path) + ' and save its verified contents as a managed report.'

@pytest.mark.parametrize('extra', [{'actor_profile': 'owner'}, {'confirmed': True}, {'mode': 'background'}, {'permissions': {'max_auto_approve_level': 99}}])
def test_model_plan_cannot_supply_execution_authority(tmp_path, extra, record_property):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    outline = {'summary': 'An injected instruction tries to grant authority.', 'unsupported_reason': None, 'steps': [read_step('read', path)], **extra}
    client.enqueue(outline)
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        key = box.submit(write_goal(path))
        result = box.await_state(key, 'blocked')
        record_property('observed', json.dumps({'status': result['status'], 'invocations': len(result['invocations']), 'read_entries': box.ledger.entries('file.read'), 'write_entries': box.ledger.entries('file.write')}))
        assert not result['invocations'] and box.ledger.entries('file.read') == box.ledger.entries('file.write') == 0

@pytest.mark.parametrize('capability', ['terminal.run', 'power.shutdown', 'compute.start_worker'])
def test_injected_binding_cannot_add_unsafe_or_remote_capability(tmp_path, capability):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    queue_plan(client, [read_step('read', path)], [row('read', capability, command='synthetic do not execute')])
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        key = box.submit('Read ' + str(path))
        detail = box.await_state(key, 'blocked')
        assert len(detail['invocations']) == 0
        assert box.ledger.entries('file.read') == box.ledger.entries('file.write') == 0

@pytest.mark.parametrize('suffix', ['../escape.txt', 'nested/../../escape.txt'])
def test_injected_managed_write_traversal_is_rejected_before_handler(tmp_path, suffix):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    save = step('save', 'Save the requested source as a managed report.', kind='artifact', dependencies=['read'])

    def binding(messages, _):
        data = json.loads(messages[1]['content'])
        return {'unsupported_reason': None, 'steps': [row('read', 'file.read', path=str(path)), row('save', 'file.write', path=str(Path(data['artifact_root']) / suffix), text='Untrusted proposed data.')]}
    client.enqueue({'summary': 'Controlled malformed report proposal.', 'unsupported_reason': None, 'steps': [read_step('read', path), save]}, binding)
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        detail = box.await_state(box.submit(write_goal(path)), 'blocked')
        assert not detail['invocations'] and box.ledger.entries('file.write') == 0
        assert not (box.service.artifacts_root / 'escape.txt').exists()

def test_actual_review_rejection_blocks_managed_write(tmp_path, record_property):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    artifact_plan(client, path)
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        key = box.submit(write_goal(path), mode='supervised')
        detail = box.await_state(key, 'awaiting_step_approval')
        approval = next((item for item in detail['approvals'] if item['kind'] == 'action' and item['state'] == 'pending'))
        box.control(key, 'reject', approval=approval)
        detail = box.await_state(key, 'blocked')
        record_property('observed', json.dumps({'status': detail['status'], 'reads': box.ledger.entries('file.read'), 'write_entries': box.ledger.entries('file.write'), 'approval': 'rejected'}))
        assert box.ledger.entries('file.read') == 1 and box.ledger.entries('file.write') == 0

def test_revoked_review_cannot_be_started_or_implicitly_reapproved(tmp_path):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    artifact_plan(client, path)
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        key = box.submit(write_goal(path))
        box.await_state(key, 'awaiting_plan_approval')
        box.control(key, 'approve_plan')
        grant = next((a for a in box.detail(key)['approvals'] if a['state'] == 'approved'))
        box.control(key, 'revoke', approval=grant)
        for _ in range(3):
            with pytest.raises(WorkflowError):
                box.control(key, 'start')
        assert box.detail(key)['status'] == 'paused'
        assert box.ledger.entries('file.read') == box.ledger.entries('file.write') == 0

def test_request_replay_returns_same_workflow_without_duplicate_effect(tmp_path, record_property):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    artifact_plan(client, path)
    request_id = str(uuid4())
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        key = box.submit(write_goal(path), request_id=request_id)
        assert box.submit(write_goal(path), request_id=request_id) == key
        detail = drive_reviewed(box, key)
        assert box.submit(write_goal(path), request_id=request_id) == key
        with pytest.raises(WorkflowError):
            box.submit('A changed objective.', request_id=request_id)
        record_property('observed', json.dumps({'status': detail['status'], 'invocations': len(detail['invocations']), 'actual_writes': box.ledger.entries('file.write'), 'model_contract_calls': len(client.calls)}))
        assert detail['status'] == 'completed' and box.ledger.entries('file.write') == 1
        assert artifact_path(detail).read_text(encoding='utf-8') == path.read_text(encoding='utf-8')

@pytest.mark.parametrize('control', ['cancel', 'pause', 'emergency_stop'])
def test_withdrawal_at_committed_dispatch_boundary_has_zero_handler_effects(tmp_path, control, record_property):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    artifact_plan(client, path)
    holder = {}

    def observe(event, payload):
        if event != 'before_dispatch':
            return
        box = holder['box']
        if control == 'emergency_stop':
            box.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.owner())
        else:
            box.control(payload['workflow_id'], control)
    with ServiceFixture(tmp_path / 'state', client=client, observer=observe) as box:
        holder['box'] = box
        box.observe('file.read', 'file.write')
        key = box.submit(write_goal(path))
        box.await_state(key, 'awaiting_plan_approval')
        box.control(key, 'approve_plan')
        box.control(key, 'start')
        detail = box.await_state(key, 'cancelled' if control == 'cancel' else 'paused')
        record_property('observed', json.dumps({'status': detail['status'], 'handler_reads': box.ledger.entries('file.read'), 'handler_writes': box.ledger.entries('file.write'), 'invocation_states': [i['state'] for i in detail['invocations']]}))
        assert box.ledger.entries('file.read') == box.ledger.entries('file.write') == 0

@pytest.mark.parametrize('fault', ['disk_full', 'malformed_receipt', 'lost_after_write'])
def test_consequential_fault_never_claims_completion_or_automatically_replays(tmp_path, monkeypatch, fault, record_property):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    artifact_plan(client, path)
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        if fault == 'disk_full':
            original = Path.write_text

            def full(target, *args, **kwargs):
                if target.is_relative_to(box.service.artifacts_root):
                    raise OSError(errno.ENOSPC, 'Controlled disk-full error.')
                return original(target, *args, **kwargs)
            monkeypatch.setattr(Path, 'write_text', full)
        else:
            from scripts.campaign4_boundaries.harness import install

            def after(*args):
                if fault == 'malformed_receipt':
                    return {'unexpected': 'not an original ToolResult'}
                raise OSError('Controlled result disconnection after the original write.')
            install(box, 'file.write', after=after)
        detail = drive_reviewed(box, box.submit(write_goal(path)))
        write_invocations = [i for i in detail['invocations'] if i['step_id'] == 'save']
        existing_files = [p for p in box.service.artifacts_root.rglob('report.txt') if p.is_file()]
        record_property('observed', json.dumps({'status': detail['status'], 'write_invocations': len(write_invocations), 'invocation_states': [i['state'] for i in write_invocations], 'actual_report_files': len(existing_files)}))
        assert detail['status'] != 'completed' and len(write_invocations) == 1
        assert len(existing_files) == (0 if fault == 'disk_full' else 1)
        with pytest.raises(WorkflowError):
            box.control(detail['workflow_id'], 'retry_safe', step_id='save')

@pytest.mark.parametrize('fault', ['timeout', 'invalid_json', 'gpu_oom'])
def test_planner_dependency_failure_blocks_without_dispatch(tmp_path, fault, record_property):

    class BrokenModel:
        calls = 0

        def chat(self, *args, **kwargs):
            self.calls += 1
            if fault == 'invalid_json':
                return '{malformed controlled reply'
            if fault == 'timeout':
                raise TimeoutError('Controlled model timeout.')
            raise RuntimeError('Controlled GPU out-of-memory leaf; no GPU allocation.')
    client = BrokenModel()
    with ServiceFixture(tmp_path / 'state', client=client) as box:
        box.observe('file.read', 'file.write')
        key = box.submit('Read ' + str(source(tmp_path)))
        detail = box.await_state(key, 'blocked')
        record_property('observed', json.dumps({'status': detail['status'], 'contract_calls': client.calls, 'handler_entries': box.ledger.entries('file.read') + box.ledger.entries('file.write')}))
        assert not detail['invocations'] and client.calls == 1

def test_store_temporarily_unavailable_has_no_partial_request_then_recovers(tmp_path, monkeypatch):
    store = WorkflowStore(tmp_path)
    original = store._connect

    def unavailable():
        raise sqlite3.OperationalError('Controlled unavailable SQLite leaf.')
    monkeypatch.setattr(store, '_connect', unavailable)
    try:
        with pytest.raises(sqlite3.OperationalError):
            store.create('Controlled request.', 'assisted')
        monkeypatch.setattr(store, '_connect', original)
        assert store.list() == []
        created = store.create('A new explicit controlled request after storage recovers.', 'assisted')
        assert store.get(created['workflow_id'])['status'] == 'submitted'
    finally:
        store.close()

def test_corrupt_checkpoint_is_not_silently_repaired_or_replayed(tmp_path):
    store = WorkflowStore(tmp_path)
    try:
        key = store.create('Controlled original checkpoint.', 'assisted')['workflow_id']
        with store.transaction() as db:
            db.execute('UPDATE checkpoints SET payload=? WHERE workflow_id=?', ('{corrupt', key))
        with pytest.raises(ValueError):
            store.history(key)
        assert store.get(key)['status'] == 'submitted'
        with store.transaction() as db:
            assert db.execute('SELECT COUNT(*) FROM invocations').fetchone()[0] == 0
            assert db.execute('SELECT payload FROM checkpoints').fetchone()[0] == '{corrupt'
    finally:
        store.close()

@pytest.mark.parametrize('outcome', ['completed', 'uncertain_write'])
def test_original_service_restart_preserves_completed_effect_or_unresolved_write(tmp_path, outcome, record_property):
    path = source(tmp_path)
    client = QueuedStructuredClient()
    artifact_plan(client, path)
    state = tmp_path / 'state'
    with ServiceFixture(state, client=client) as first:
        first.observe('file.read', 'file.write')
        if outcome == 'uncertain_write':
            from scripts.campaign4_boundaries.harness import install

            def lost(*args):
                raise OSError('Controlled lost receipt after original report write.')
            install(first, 'file.write', after=lost)
        key = first.submit(write_goal(path))
        prior = drive_reviewed(first, key)
        effects = [p.read_bytes() for p in first.service.artifacts_root.rglob('report.txt')]
        assert len(effects) == 1
        invocation_ids = [item['invocation_id'] for item in prior['invocations']]
        writes = first.ledger.entries('file.write')
    with ServiceFixture(state, client=QueuedStructuredClient()) as second:
        second.observe('file.read', 'file.write')
        current = second.detail(key)
        assert [item['invocation_id'] for item in current['invocations']] == invocation_ids
        assert [p.read_bytes() for p in second.service.artifacts_root.rglob('report.txt')] == effects
        assert writes == 1 and second.ledger.entries('file.write') == 0
        if outcome == 'completed':
            assert current['status'] == 'completed'
        else:
            assert current['status'] == 'blocked'
            with pytest.raises(WorkflowError):
                second.control(key, 'resume')
            with pytest.raises(WorkflowError):
                second.control(key, 'retry_safe', step_id='save')
        record_property('observed', json.dumps({'before_status': prior['status'], 'after_status': current['status'], 'original_write_entries': writes, 'restart_model_contract_calls': len(second.client.calls), 'same_invocation_ids': [item['invocation_id'] for item in current['invocations']] == invocation_ids}))
        assert second.client.calls == []
