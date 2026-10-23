"""Independent exposed real-service engineering, not model-intelligence tests.

Every step traverses the production scheduler, original MCP host and registry.
Only model responses/resources/clocks and original handler observers are seams.
Temporary local stores and files are independent outcome oracles.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import os
import threading
import time
from uuid import uuid4
import pytest
from scripts.v3_review.fixtures import ControlledClock, fixture_facts
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture
from hanni.workflows.types import WorkflowError, WorkflowLimits

def criterion(operator, path, expected=None):
    return {'operator': operator, 'path': path, 'expected': expected}

def step(identifier, description, *, kind='tool', dependencies=(), criteria=None):
    return {'step_id': identifier, 'description': description, 'kind': kind, 'dependencies': list(dependencies), 'required': True, 'criteria': criteria or [criterion('present', '/data/path')]}

def row(identifier, capability, **arguments):
    return {'step_id': identifier, 'capability_id': capability, 'arguments': arguments}

def ref(identifier, path='/data/text', type='string'):
    return {'$ref': {'step_id': identifier, 'path': path, 'type': type}}

def read_step(identifier, source, *, dependencies=(), expected=None, json_valid=False):
    checks = [criterion('equals', '/data/truncated', False)]
    checks.append(criterion('json_valid', '/data/text') if json_valid else criterion('equals', '/data/text', expected) if expected is not None else criterion('nonempty', '/data/text'))
    return step(identifier, 'Read the text file ' + str(source), dependencies=dependencies, criteria=checks)

def queue_plan(client, steps, rows, *, reports=()):
    client.enqueue({'summary': 'Complete the explicitly requested isolated fixture objective.', 'unsupported_reason': None, 'steps': steps})

    def binding(messages, _kwargs):
        data = json.loads(messages[1]['content'])
        bound = deepcopy(rows)
        for item in bound:
            if item['arguments'].get('path') == '$artifact/report.txt':
                item['arguments']['path'] = str(Path(data['artifact_root']) / 'report.txt')
        return {'unsupported_reason': None, 'steps': bound}
    client.enqueue(binding, *reports)

def drive_reviewed(fixture, key, *, timeout=10):
    """The isolated test owner explicitly reviews every encountered grant."""
    for _ in range(20):
        detail = fixture.service.wait(key, timeout=timeout)
        if detail['status'] == 'awaiting_plan_approval':
            fixture.control(key, 'approve_plan')
            fixture.control(key, 'start')
        elif detail['status'] == 'awaiting_step_approval':
            approval = next((item for item in detail['approvals'] if item['kind'] == 'action' and item['state'] == 'pending'))
            fixture.control(key, 'approve_step', approval=approval)
        else:
            return detail
    raise AssertionError('The service repeatedly requested review without settling.')

def start_reviewed(fixture, key):
    detail = fixture.await_state(key, 'awaiting_plan_approval')
    fixture.control(key, 'approve_plan')
    fixture.control(key, 'start')
    return detail

def artifact_plan(client, source, *, expected=None, mode='assisted', extra_steps=(), extra_rows=(), reports=()):
    steps = [read_step('read', source, expected=expected), *extra_steps, step('save', 'Save the verified source text as a private report.', kind='artifact', dependencies=['read'], criteria=[criterion('present', '/data/path')])]
    rows = [row('read', 'file.read', path=str(source)), *extra_rows, row('save', 'file.write', path='$artifact/report.txt', text=ref('read'))]
    queue_plan(client, steps, rows, reports=reports)

def artifact_path(detail):
    return Path(next((item for item in detail['steps'] if item['step_id'] == 'save'))['resolved_arguments']['path'])

def test_read_typed_reference_artifact_real_bytes_and_gates(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.read', 'file.write')
        key = fixture.submit('Read the text file ' + str(facts['source']) + ' and preserve its verified contents.')
        detail = drive_reviewed(fixture, key)
        assert detail['status'] == 'completed', detail
        assert detail['counts']['verified'] == 2
        assert artifact_path(detail).read_text(encoding='utf-8') == facts['source'].read_text(encoding='utf-8')
        assert fixture.ledger.entries('file.write') == 1
        assert len(detail['invocations']) == 2

@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_copy_or_move_read_report_matches_external_bytes(tmp_path, operation):
    facts = fixture_facts(tmp_path / 'inputs')
    expected = facts['source'].read_bytes()
    destination = tmp_path / 'copied.txt'
    client = QueuedStructuredClient()
    queue_plan(client, [step('transfer', operation.title() + ' the file ' + str(facts['source']) + ' to ' + str(destination), criteria=[criterion('present', '/data/destination')]), read_step('read', destination, dependencies=['transfer']), step('save', 'Save the verified destination contents.', kind='artifact', dependencies=['read'])], [row('transfer', 'file.' + operation, source=str(facts['source']), destination=str(destination)), row('read', 'file.read', path=str(destination)), row('save', 'file.write', path='$artifact/report.txt', text=ref('read'))])
    with ServiceFixture(tmp_path / 'run', client=client, extra_allowed_actions=('file.' + operation,)) as fixture:
        fixture.observe('file.' + operation, 'file.write')
        key = fixture.submit(operation.title() + ' the explicitly supplied local fixture, inspect it and save the contents.')
        detail = drive_reviewed(fixture, key)
        assert detail['status'] == 'completed', detail
        assert destination.read_bytes() == expected
        assert facts['source'].exists() is (operation == 'copy')
        assert artifact_path(detail).read_bytes() == expected.decode('utf-8').replace('\n', os.linesep).encode('utf-8')
        assert fixture.ledger.entries('file.' + operation) == 1
        assert fixture.ledger.entries('file.write') == 1
        assert len(detail['invocations']) == 3

def test_artifact_roundtrip_through_original_file_read(tmp_path):
    client = QueuedStructuredClient()
    text = 'Explicit fixture artifact\nline two\n'
    queue_plan(client, [step('save', 'Save the requested private report.', kind='artifact'), read_step('read', 'report.txt', dependencies=['save'], expected=text)], [row('save', 'file.write', path='$artifact/report.txt', text=text), row('read', 'file.read', path=ref('save', '/data/path'))])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.write')
        key = fixture.submit('Save the requested report and read back its exact text.')
        detail = drive_reviewed(fixture, key)
        assert detail['status'] == 'completed', detail
        assert artifact_path(detail).read_bytes() == text.replace('\n', os.linesep).encode()
        assert fixture.ledger.entries('file.write') == 1

def numeric_plan(client, source, *, malformed=False):
    observations = []
    for index, result in enumerate((60, 90)):
        observations.append({'operation': 'percentage', 'sources': [{'step_id': 'read', 'path': '/data/text', 'json_path': f'/runs/{index}/passed'}, {'step_id': 'read', 'path': '/data/text', 'json_path': f'/runs/{index}/total'}], 'value': result})
    difference = {'observations': [{'operation': 'difference', 'sources': [{'step_id': 'analyze', 'path': '/data/report/observations/1/value', 'json_path': None}, {'step_id': 'analyze', 'path': '/data/report/observations/0/value', 'json_path': None}], 'value': 30}]}
    queue_plan(client, [read_step('read', source, json_valid=True), step('analyze', 'Calculate actual observed percentages.', kind='analysis', dependencies=['read'], criteria=[criterion('evidence_report', '/data/report')]), step('compare', 'Calculate improvement from the checked observations.', kind='analysis', dependencies=['analyze'], criteria=[criterion('evidence_report', '/data/report'), criterion('equals', '/data/report/observations/0/value', 30)]), step('save', 'Save the checked comparison report.', kind='artifact', dependencies=['compare'])], [row('read', 'file.read', path=str(source)), row('analyze', None, sources=['read']), row('compare', None, sources=['analyze']), row('save', 'file.write', path='$artifact/report.txt', text=ref('compare'))], reports=[{'observations': observations}, difference])

def test_numeric_analysis_and_saved_report_correct_from_real_json(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    numeric_plan(client, facts['valid'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        key = fixture.submit('Compare both observed runs, compute pass percentages and their improvement, and save the report.')
        detail = drive_reviewed(fixture, key)
        assert detail['status'] == 'completed', detail
        assert [item['value'] for item in detail['steps'][1]['result']['data']['report']['observations']] == [60, 90]
        saved = json.loads(artifact_path(detail).read_text(encoding='utf-8'))
        assert saved['observations'][0]['value'] == 30
        assert detail['counts']['verified'] == 4

def test_truncated_json_cannot_admit_analysis_or_false_report(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    numeric_plan(client, facts['invalid'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.write')
        key = fixture.submit('Analyze the actual structured report and save supported results.')
        detail = drive_reviewed(fixture, key)
        assert detail['status'] != 'completed', detail
        assert detail['steps'][0]['status'] != 'verified'
        assert fixture.ledger.entries('file.write') == 0
        assert len(client.calls) == 2

@pytest.mark.parametrize('mode', ['assisted', 'background'])
def test_two_step_plan_waits_for_explicit_owner_scope(tmp_path, mode):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.read', 'file.write')
        key = fixture.submit('Read the supplied local evidence and preserve it.', mode)
        detail = fixture.await_state(key, 'awaiting_plan_approval')
        assert detail['scope'] is None
        assert detail['invocations'] == []
        assert fixture.ledger.entries('file.read') == fixture.ledger.entries('file.write') == 0

def test_supervised_reads_progress_but_sensitive_artifact_needs_actual_review(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.write')
        key = fixture.submit('Read the actual supplied text and preserve it.', 'supervised')
        detail = fixture.await_state(key, 'awaiting_step_approval')
        assert detail['steps'][0]['status'] == 'verified'
        assert detail['scope']['provenance'] == 'owner_supervised_submission'
        assert fixture.ledger.entries('file.write') == 0
        assert 'file.write' not in detail['scope']['capabilities']
        final = drive_reviewed(fixture, key)
        assert final['status'] == 'completed', final
        assert fixture.ledger.entries('file.write') == 1

def test_rejected_sensitive_action_never_enters_original_write(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.write')
        key = fixture.submit('Read and save the explicitly supplied fixture.', 'supervised')
        detail = fixture.await_state(key, 'awaiting_step_approval')
        approval = next((item for item in detail['approvals'] if item['kind'] == 'action'))
        fixture.control(key, 'reject', approval=approval)
        final = fixture.detail(key)
        assert final['status'] == 'blocked'
        assert fixture.ledger.entries('file.write') == 0
        assert not artifact_path(final).exists()

def test_expired_exact_review_cannot_dispatch_or_silently_rebind(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    clock = ControlledClock()
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client, clock=clock.wall, monotonic=clock.monotonic) as fixture:
        fixture.observe('file.write')
        key = fixture.submit('Read and save the explicitly supplied fixture.', 'supervised')
        detail = fixture.await_state(key, 'awaiting_step_approval')
        approval = next((item for item in detail['approvals'] if item['kind'] == 'action'))
        captured = fixture.bound_data(detail, approval)
        clock.advance(fixture.service.limits.approval_ttl_seconds + 1)
        with pytest.raises(WorkflowError):
            fixture.mutate('approve_step', captured)
        assert fixture.ledger.entries('file.write') == 0
        assert not artifact_path(fixture.detail(key)).exists()

def test_revoked_plan_requires_new_review_and_does_not_enter_read(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.read', 'file.write')
        key = fixture.submit('Read and preserve the specified source.', 'background')
        fixture.await_state(key, 'awaiting_plan_approval')
        fixture.control(key, 'approve_plan')
        detail = fixture.detail(key)
        grant = next((item for item in detail['approvals'] if item['kind'] == 'plan'))
        fixture.control(key, 'revoke', approval=grant)
        fixture.control(key, 'resume')
        fresh = fixture.await_state(key, 'awaiting_plan_approval')
        assert any((item['kind'] == 'plan' and item['state'] == 'pending' and (item['approval_id'] != grant['approval_id']) for item in fresh['approvals']))
        assert fixture.ledger.entries('file.read') == fixture.ledger.entries('file.write') == 0
        assert fresh['scope'] is None

def test_changed_definition_blocks_current_plan_review(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        key = fixture.submit('Read and preserve actual fixture text.')
        fixture.await_state(key, 'awaiting_plan_approval')
        fixture.observe('file.read')
        with pytest.raises(WorkflowError):
            fixture.control(key, 'approve_plan')
        assert fixture.ledger.entries('file.read') == 0
        assert fixture.detail(key)['invocations'] == []

def test_untrusted_read_text_cannot_add_capabilities_or_consent(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['untrusted'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.read', 'file.write', 'file.delete')
        key = fixture.submit('Preserve the exact quoted fixture log as data.')
        final = drive_reviewed(fixture, key)
        assert final['status'] == 'completed', final
        assert artifact_path(final).read_text() == facts['untrusted'].read_text()
        assert fixture.ledger.entries('file.delete') == 0
        assert {item['capability_id'] for item in final['steps']} == {'file.read', 'file.write'}

def test_unknown_ram_blocks_two_step_plan_without_fabricating_gpu_capacity(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.resources['ram_percent'] = None
        key = fixture.submit('Read and preserve supplied evidence.')
        with pytest.raises(TimeoutError):
            fixture.service.wait(key, timeout=0.25)
        assert fixture.detail(key)['status'] == 'submitted'
        assert client.calls == []
        assert fixture.resources['gpu'] is None

def test_shared_artifact_budget_counts_retained_prior_work(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    limits = replace(WorkflowLimits(), max_artifact_bytes=40)
    with ServiceFixture(tmp_path / 'run', client=client, limits=limits) as fixture:
        fixture.observe('file.write')
        root = fixture.service.artifacts_root / ('wf_' + 'a' * 32)
        root.mkdir(parents=True)
        (root / 'retained.txt').write_bytes(b'x' * 39)
        with fixture.service.store.transaction() as db:
            db.execute('INSERT INTO metadata VALUES(?,?)', ('artifact_gc:' + root.name, json.dumps({'workflow_id': root.name})))
        with fixture.service.store.transaction() as db:
            db.execute('UPDATE metadata SET value=? WHERE key=?', ('{"workflow_id":"unavailable"}', 'artifact_gc:' + root.name))
        key = fixture.submit('Read and preserve supplied evidence.')
        final = drive_reviewed(fixture, key)
        assert final['status'] == 'blocked', final
        assert fixture.ledger.entries('file.write') == 0
        assert (root / 'retained.txt').stat().st_size == 39

def test_actual_managed_artifact_parent_junction_cannot_write_outside(tmp_path):
    if os.name != 'nt':
        pytest.skip('This case specifically verifies the native Windows junction boundary.')
    import _winapi
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    outside = tmp_path / 'outside'
    outside.mkdir()
    marker = outside / 'retain.txt'
    marker.write_bytes(b'Outside fixture marker must survive unchanged.')
    switched = []
    fixture_ref = []
    backup = tmp_path / 'owned-artifact-backup'

    def observer(stage, event):
        if stage == 'before_dispatch' and event.get('step_id') == 'save':
            parent = fixture_ref[0].service.artifacts_root
            assert parent.is_absolute() and parent.parent == fixture_ref[0].service.root / 'workflows'
            parent.rename(backup)
            _winapi.CreateJunction(str(outside), str(parent))
            switched.append(parent)
    with ServiceFixture(tmp_path / 'run', client=client, observer=observer) as fixture:
        fixture_ref.append(fixture)
        fixture.observe('file.write')
        try:
            key = fixture.submit('Read the supplied text and save an owned private report.')
            final = drive_reviewed(fixture, key)
            assert switched, 'The actual committed artifact invocation boundary was not reached.'
            assert final['status'] != 'completed', final
            assert fixture.ledger.entries('file.write') == 0
            assert list(outside.rglob('report.txt')) == []
            assert marker.read_bytes() == b'Outside fixture marker must survive unchanged.'
        finally:
            if switched:
                switched[0].rmdir()
                backup.rename(switched[0])

def test_two_real_reads_form_verified_barrier_before_report(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    observations = {'observations': [{'operation': 'count', 'sources': [{'step_id': identifier, 'path': '/data/text', 'json_path': None}], 'value': len(path.read_text(encoding='utf-8'))} for identifier, path in [('left', facts['source']), ('right', facts['valid'])]]}
    queue_plan(client, [read_step('left', facts['source']), read_step('right', facts['valid']), step('analyze', 'Count both actual source texts.', kind='analysis', dependencies=['left', 'right'], criteria=[criterion('evidence_report', '/data/report')]), step('save', 'Save the checked source count report.', kind='artifact', dependencies=['analyze'])], [row('left', 'file.read', path=str(facts['source'])), row('right', 'file.read', path=str(facts['valid'])), row('analyze', None, sources=['left', 'right']), row('save', 'file.write', path='$artifact/report.txt', text=ref('analyze'))], reports=[observations])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.read', 'file.write')
        key = fixture.submit('Read both actual inputs and save their checked character counts.')
        final = drive_reviewed(fixture, key)
        assert final['status'] == 'completed', final
        assert json.loads(artifact_path(final).read_text()) == observations
        returns = [item['sequence'] for item in fixture.ledger.rows if item['capability_id'] == 'file.read' and item['phase'] == 'returned']
        entered = [item['sequence'] for item in fixture.ledger.rows if item['capability_id'] == 'file.write' and item['phase'] == 'entered']
        assert len(returns) == 2 and len(entered) == 1 and (max(returns) < entered[0])

def test_task_add_original_readback_and_saved_exact_fields(tmp_path):
    from hanni.tools.todos import TodoStore
    client = QueuedStructuredClient()
    title, course, due = ('Independent temporary lab assignment', 'Fixture Course', '2030-06-12T15:00:00-04:00')
    queue_plan(client, [step('add', 'Save a named assignment task with a due date locally.', criteria=[criterion('present', '/data/id')]), step('read', 'Read back one local task by its exact ID.', dependencies=['add'], criteria=[criterion('equals', '/data/task/title', title), criterion('equals', '/data/task/course', course)]), step('save', 'Save the verified task title.', kind='artifact', dependencies=['read'])], [row('add', 'todo.add', title=title, course=course, due=due), row('read', 'todo.get', id=ref('add', '/data/id')), row('save', 'file.write', path='$artifact/report.txt', text=ref('read', '/data/task/title'))])
    with ServiceFixture(tmp_path / 'run', client=client, extra_allowed_actions=('todo.add',)) as fixture:
        fixture.observe('todo.add')
        key = fixture.submit('Save the supplied named local task, read its exact fields and preserve its title.')
        final = drive_reviewed(fixture, key)
        assert final['status'] == 'completed', final
        saved = TodoStore(fixture.config.paths.data_dir).get(final['steps'][0]['result']['data']['id'])
        assert saved['title'] == title and saved['course'] == course
        from datetime import datetime
        assert datetime.fromisoformat(saved['due']) == datetime.fromisoformat(due)
        assert artifact_path(final).read_text() == title
        assert fixture.ledger.entries('todo.add') == 1

def test_failed_prerequisite_never_enters_its_descendant_but_retains_other_branch(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    missing = tmp_path / 'missing.txt'
    client = QueuedStructuredClient()
    queue_plan(client, [read_step('missing', missing), read_step('independent', facts['source']), step('save', 'Save contents only after verified missing-file prerequisite.', kind='artifact', dependencies=['missing'])], [row('missing', 'file.read', path=str(missing)), row('independent', 'file.read', path=str(facts['source'])), row('save', 'file.write', path='$artifact/report.txt', text=ref('missing'))])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        fixture.observe('file.write')
        key = fixture.submit('Read both exact inputs and preserve only verified results.')
        final = drive_reviewed(fixture, key)
        assert final['status'] != 'completed', final
        states = {item['step_id']: item['status'] for item in final['steps']}
        assert states['missing'] == 'failed' and states['independent'] == 'verified'
        assert states['save'] != 'verified' and fixture.ledger.entries('file.write') == 0

def test_original_retry_safe_stat_retries_once_with_durable_backoff(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    queue_plan(client, [step('stat', 'Check whether the local path exists.', criteria=[criterion('equals', '/data/exists', True)]), read_step('read', facts['source'], dependencies=['stat'])], [row('stat', 'file.stat', path=str(facts['source'])), row('read', 'file.read', path=ref('stat', '/data/path'))])
    clock = ControlledClock()
    with ServiceFixture(tmp_path / 'run', client=client, clock=clock.wall, monotonic=clock.monotonic) as fixture:
        attempts = []

        def transient(*_):
            attempts.append(True)
            if len(attempts) == 1:
                raise TimeoutError('Controlled original retry-safe stat fault.')
        fixture.observe('file.stat', before=transient)
        key = fixture.submit('Inspect then read the explicitly supplied local fixture.')
        start_reviewed(fixture, key)
        pending = fixture.service.wait(key, predicate=lambda item: any((checkpoint['kind'] == 'retry_scheduled' for checkpoint in item['checkpoints'])))
        assert len(attempts) == 1 and pending['steps'][0]['attempts'] == 1
        clock.advance(2.1)
        fixture.service.wake.set()
        final = fixture.await_state(key, 'completed')
        assert len(attempts) == final['steps'][0]['attempts'] == 2
        assert len(final['invocations']) == 3
        from hanni.workflows.service import _epoch
        assert _epoch(final['invocations'][1]['started_at']) - _epoch(final['invocations'][0]['started_at']) >= 2

def test_unknown_write_fault_after_real_effect_is_never_replayed(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:

        def after_effect(*_):
            raise TimeoutError('Lost acknowledgement after genuine isolated write.')
        fixture.observe('file.write', after=after_effect)
        key = fixture.submit('Read and preserve actual supplied text.')
        final = drive_reviewed(fixture, key)
        assert final['status'] != 'completed', final
        assert artifact_path(final).read_text() == facts['source'].read_text()
        assert fixture.ledger.entries('file.write') == 1
        with pytest.raises(WorkflowError):
            fixture.control(key, 'retry_safe', step_id='save')
        assert fixture.ledger.entries('file.write') == 1

@pytest.mark.parametrize('operation', ['pause', 'cancel'])
def test_active_sync_call_pause_or_cancel_waits_and_stops_descendant(tmp_path, operation):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    entered, release = (threading.Event(), threading.Event())
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:

        def barrier(*_):
            entered.set()
            assert release.wait(8), 'Owned synchronous fixture barrier not released.'
        fixture.observe('file.read', before=barrier)
        fixture.observe('file.write')
        try:
            key = fixture.submit('Read the supplied text, then save only after verification.')
            start_reviewed(fixture, key)
            assert entered.wait(3)
            fixture.control(key, operation)
            waiting = fixture.detail(key)
            assert waiting[operation + '_requested'] is True
            assert waiting['active_uninterruptible'] is True
            assert waiting['status'] not in {'cancelled', 'paused'}
            assert fixture.ledger.entries('file.write') == 0
            release.set()
            final = fixture.await_state(key, 'cancelled' if operation == 'cancel' else 'paused')
            assert fixture.ledger.entries('file.write') == 0
            if operation == 'pause':
                fixture.control(key, 'resume')
                final = drive_reviewed(fixture, key)
                assert final['status'] == 'completed', final
                assert fixture.ledger.entries('file.read') == 1
                assert fixture.ledger.entries('file.write') == 1
        finally:
            release.set()

def test_active_timeout_reports_pending_then_requires_explicit_resume(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    clock = ControlledClock()
    entered, release = (threading.Event(), threading.Event())
    limits = replace(WorkflowLimits(), step_timeout_seconds=1)
    with ServiceFixture(tmp_path / 'run', client=client, limits=limits, clock=clock.wall, monotonic=clock.monotonic) as fixture:

        def barrier(*_):
            entered.set()
            assert release.wait(8)
        fixture.observe('file.read', before=barrier)
        fixture.observe('file.write')
        try:
            key = fixture.submit('Read then preserve the explicitly supplied fixture.')
            start_reviewed(fixture, key)
            assert entered.wait(3)
            clock.advance(1.1)
            fixture.service.wake.set()
            pending = fixture.service.wait(key, predicate=lambda item: item['pause_requested'])
            assert pending['active_uninterruptible'] is True and pending['status'] != 'paused'
            assert fixture.ledger.entries('file.write') == 0
            release.set()
            fixture.await_state(key, 'paused')
            fixture.control(key, 'resume')
            final = drive_reviewed(fixture, key)
            assert final['status'] == 'completed', final
            assert fixture.ledger.entries('file.read') == 1
        finally:
            release.set()

def test_duration_limit_prevents_next_step_and_is_not_reset_by_resume(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    clock = ControlledClock()
    entered, release = (threading.Event(), threading.Event())
    limits = replace(WorkflowLimits(), max_duration_seconds=1)
    with ServiceFixture(tmp_path / 'run', client=client, limits=limits, clock=clock.wall, monotonic=clock.monotonic) as fixture:

        def barrier(*_):
            entered.set()
            assert release.wait(8)
        fixture.observe('file.read', before=barrier)
        fixture.observe('file.write')
        try:
            key = fixture.submit('Read then preserve exact supplied text.')
            start_reviewed(fixture, key)
            assert entered.wait(3)
            clock.advance(1.1)
            fixture.service.wake.set()
            fixture.service.wait(key, predicate=lambda item: item['pause_requested'])
            release.set()
            final = fixture.await_state(key, 'paused', 'blocked')
            with pytest.raises(WorkflowError):
                fixture.control(key, 'resume')
            assert fixture.ledger.entries('file.write') == 0 and final['status'] != 'completed'
        finally:
            release.set()

def test_older_supervised_work_progresses_after_150_newer_terminal_records(tmp_path):
    facts = fixture_facts(tmp_path / 'inputs')
    client = QueuedStructuredClient()
    artifact_plan(client, facts['source'])
    clock = ControlledClock()
    with ServiceFixture(tmp_path / 'run', client=client, clock=clock.wall, monotonic=clock.monotonic) as fixture:
        fixture.resources['allowed'] = False
        key = fixture.submit('Read and preserve the supplied actual fixture.', 'supervised')
        for index in range(150):
            clock.advance(0.001)
            record = fixture.service.store.create(f'Settled isolated history {index}', 'assisted')
            fixture.service.store.update(record['workflow_id'], record['revision'], {'status': 'cancelled'})
        assert key not in {item['workflow_id'] for item in fixture.service.snapshot(100)}
        fixture.resources['allowed'] = True
        fixture.service.wake.set()
        active = fixture.await_state(key, 'awaiting_step_approval')
        assert active['steps'][0]['status'] == 'verified'
        final = drive_reviewed(fixture, key)
        assert final['status'] == 'completed', final
