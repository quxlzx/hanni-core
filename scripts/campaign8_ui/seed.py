"""Populate disposable original stores; seeded history is not autonomous success."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import uuid4

def _local(backend, operation, data):
    return backend.features.mutate('productivity', {'id': str(uuid4()), 'operation': operation, 'data': data, 'confirmed': True})

def populate(backend):
    """Only the supplied original backend's fresh root is used; no model is called.

    Workflow history is assembled with original fenced store APIs and an actual
    registered file write/readback. This deliberately seeded receipt exercises
    history projection, not goal understanding, planning, or scheduler admission.
    """
    if (backend.root / 'SEEDED.json').exists():
        raise ValueError('Do not silently seed the same disposable stores twice.')
    project = _local(backend, 'project.create', {'name': 'Controlled QA observatory', 'description': 'Disposable desktop controls. No owner project is copied.'})['project']
    task = _local(backend, 'task.create', {'title': 'Controlled QA inspect retained report', 'course': 'Desktop QA', 'due': '2026-10-10', 'priority': 'high', 'project_id': project['id']})['task']
    note = _local(backend, 'note.create', {'project_id': project['id'], 'title': 'Controlled QA fixture note', 'body': 'Synthetic local note for edit and deletion readback.'})['note']
    store = backend.features.memory_store()
    memory, _ = store.remember('For the controlled observatory, use concise status notes.', source='owner_explicit:campaign8-fixture', source_ref='controlled-seed', project_id=project['id'], semantic_status='statement')
    suggestion = store.propose('add', 'Controlled observatory reviews happen on Friday.', source='owner_requested:campaign8-fixture', source_ref='controlled-seed', project_id=project['id'], semantic_status='plan', reason='Synthetic suggestion for explicit review controls.', uncertainty='Seeded fixture; not extracted by a model.')
    backend.features.store.ingest([{'key': 'campaign8-controlled-fixture', 'category': 'application', 'priority': 'action_required', 'title': 'Controlled QA record available', 'message': 'This synthetic notification points to a disposable project.', 'target': {'screen': 'projects', 'id': project['id']}}])
    workflow = _workflow_history(backend)
    link = _local(backend, 'link.create', {'project_id': project['id'], 'label': 'Controlled QA report', 'kind': 'file', 'target': workflow['artifact_path']})['link']
    return {'evidence_class': 'CONTROLLED', 'scope': 'Original local persistence and actual isolated file receipt; manually seeded workflow history, no model/planner/scheduler success.', 'project_id': project['id'], 'task_id': task['id'], 'note_id': note['id'], 'memory_id': memory.id, 'suggestion_id': suggestion.id, 'link_id': link['id'], 'workflow': workflow, 'controller_attached': False, 'model_requests': 0}

def populate_dense(backend):
    """Original synthetic records to reach real pagination/approval branches.

    These are UI fixtures, never model-derived memories or benchmark answers.
    Owner databases are not read. Every mutation uses the original MemoryStore.
    """
    seeded = populate(backend)
    store = backend.features.memory_store()
    records, proposals = ([], [])
    for index in range(35):
        row, _ = store.remember(f'Controlled pagination fixture station {index} has an explicit synthetic inspection note.', source='owner_explicit:campaign8-pagination-fixture', source_ref='controlled-ui-pagination', project_id=seeded['project_id'], semantic_status='statement')
        records.append(row.id)
    for index in range(25):
        row = store.propose('add', f'Controlled review fixture {index} records a synthetic reusable inspection statement.', source='owner_requested:campaign8-review-fixture', source_ref='controlled-ui-pagination', project_id=seeded['project_id'], semantic_status='statement', reason='Explicit synthetic native review/pagination fixture, not inference.', uncertainty='No model extraction or owner memory is represented.')
        proposals.append(row.id)
    record = store.get(seeded['memory_id'])
    for index in range(52):
        record = store.correct(record.id, f'Controlled correction history revision {index}: retain clear local inspection notes.', expected_updated_at=record.updated_at.isoformat(), source='owner_explicit:campaign8-history-fixture', project_id=seeded['project_id'], semantic_status='statement', source_ref='controlled-ui-history')
    return dict(seeded, dense_fixture={'original_record_ids': records, 'original_suggestion_ids': proposals, 'correction_revisions': 52, 'scope': 'Manually authored original isolated store records; no persistent intelligence or autonomous-memory success.'})

def populate_task_fidelity(backend):
    seeded = populate(backend)
    rows = []
    for title, due in [('Controlled all-day fidelity', '2026-11-03'), ('Controlled timed fidelity', '2026-11-03T14:25:00-05:00'), ('Controlled editable-date fidelity', '2026-11-05')]:
        rows.append(_local(backend, 'task.create', {'title': title, 'due': due, 'priority': 'normal', 'course': 'Original date fidelity controls'})['task'])
    return dict(seeded, task_fidelity={'records': rows, 'scope': 'Original explicit date-only/timed tasks for native field preservation; no model extraction.'})

def populate_safe_gaps(backend):
    from .inert_mcp import configure
    return dict(populate_dense(backend), inert_mcp=configure(backend))

def _workflow_history(backend):
    from hanni.reliability.verification import verify_action
    from hanni.tools.base import ToolRequest
    from hanni.workflows.policy import definition_fingerprint
    from hanni.workflows.verification import evaluate_step
    service = backend.server.workflows.require()
    store = service.store
    lease = store.claim(str(uuid4()))
    try:
        record = store.create('Controlled fixture: retain a verified local QA report.', 'assisted')
        key = record['workflow_id']
        folder = (service.artifacts_root / key).resolve()
        if not folder.is_relative_to(backend.root):
            raise ValueError('Artifact must stay in the exact disposable root.')
        folder.mkdir(parents=True)
        path = folder / 'controlled-report.txt'
        arguments = {'path': str(path), 'text': 'Controlled QA report. Original local file readback only.\n'}
        definition = backend.registry.get('file.write')
        definition_hash = definition_fingerprint(definition)
        step = {'step_id': 'retained_report', 'kind': 'artifact', 'description': 'Manually seeded original file receipt, not model planning.', 'capability_id': 'file.write', 'dependencies': [], 'required': True, 'arguments': arguments, 'definition_hash': definition_hash, 'permission_level': definition.permission_level, 'risk_level': definition.risk_level, 'side_effect': definition.side_effect, 'criteria': [{'operator': 'equals', 'path': '/data/path', 'expected': str(path)}]}
        plan = {'summary': 'Manually seeded CONTROLLED display fixture.', 'steps': [step]}
        record = store.save_plan(key, record['revision'], plan, [step], lease=lease)
        record = store.update(key, record['revision'], {'status': 'ready'}, kind='controlled_fixture_ready', lease=lease)
        record = store.edit_step(key, record['revision'], step['step_id'], {'resolved_arguments': arguments}, lease=lease, kind='controlled_fixture_binding')
        invocation, record = store.begin_invocation(key, record['revision'], step['step_id'], lease=lease, arguments=arguments, definition_hash=definition_hash, write=True, resource_keys=(str(path),))
        request = ToolRequest('file.write', arguments, confirmed=True, source='campaign8-controlled-fixture', correlation_id=invocation['correlation_id'])
        result = backend.registry.execute(request)
        payload = result.to_dict()
        payload['verification'] = verify_action(backend.registry, definition, request, arguments, result)
        evidence = evaluate_step(dict(step, resolved_arguments=arguments), payload, {})
        if not result.ok or evidence['status'] != 'VERIFIED':
            raise ValueError('Seeded report lacks genuine original isolated file verification.')
        record = store.finish_invocation(invocation['invocation_id'], lease=lease, result=payload, step_status='verified', verification=evidence)
        stamp = datetime.now(timezone.utc).isoformat()
        record = store.update(key, record['revision'], {'status': 'completed', 'started_at': invocation['started_at'], 'finished_at': stamp, 'result_summary': 'Manually seeded original isolated write and readback; no autonomous planning.'}, kind='controlled_fixture_history_complete', lease=lease)
        pending = store.create('Controlled fixture: inspect a local report after owner review.', 'assisted')
        read_definition = backend.registry.get('file.stat')
        read_step = dict(step, step_id='inspect_report', kind='tool', capability_id='file.stat', arguments={'path': str(path), 'hash': True}, definition_hash=definition_fingerprint(read_definition), permission_level=read_definition.permission_level, risk_level=read_definition.risk_level, side_effect=read_definition.side_effect, criteria=[{'operator': 'present', 'path': '/data/sha256', 'expected': None}])
        pending = store.save_plan(pending['workflow_id'], pending['revision'], {'summary': 'Seeded pending plan; actual controller remains unattached.', 'steps': [read_step]}, [read_step], lease=lease)
        approval, pending = store.add_approval(pending['workflow_id'], pending['revision'], {'kind': 'plan', 'plan_hash': pending['plan_hash'], 'step_id': None, 'argument_hash': None, 'definition_hash': None}, lease=lease)
        data = path.read_bytes()
        return {'completed_id': key, 'pending_id': pending['workflow_id'], 'approval_id': approval['approval_id'], 'artifact_path': str(path), 'artifact_sha256': hashlib.sha256(data).hexdigest(), 'artifact_size_bytes': len(data), 'original_result_verification': payload['verification'], 'workflow_step_verification': evidence, 'model_requests': 0, 'origin': 'MANUALLY_SEEDED_ORIGINAL_STORE_AND_REGISTERED_TOOL_RECEIPT'}
    finally:
        store.release(lease)
