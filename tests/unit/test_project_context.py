"""Project context uses stable explicit associations, never completion intent."""
from copy import deepcopy
import pytest
from hanni.dashboard.productivity import ProductivityStore
from hanni.memory.projects import ProjectContext
from hanni.memory.store import MemoryStore

@pytest.fixture
def context(tmp_path):
    workspace = ProductivityStore(tmp_path)
    from uuid import uuid4
    project = workspace.mutate('project.create', {'name': 'Aster 4B', 'description': 'A model development project'}, str(uuid4()))['project']
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    return (ProjectContext(store, workspace), project)

def test_unknown_distinctive_project_does_not_select_the_only_project(context):
    service, project = context
    assert service.resolve('Continue the nonexistent Nebula project')['status'] == 'none'
    assert service.resolve('Continue the Nebula 4B model')['status'] == 'none'
    assert service.resolve('Continue Aster 4B')['project_id'] == project['id']
    assert service.resolve('Continue my model project')['project_id'] == project['id']

def test_same_alias_requires_clarification_and_unlink_restores_identity(context):
    service, first = context
    from uuid import uuid4
    second = service.workspace.mutate('project.create', {'name': 'Aster 8B', 'description': 'Another model'}, str(uuid4()))['project']
    for project in (first, second):
        service.add_alias(project['id'], 'Research assistant', expected_fingerprint=project['fingerprint'])
    result = service.resolve('Continue Research assistant')
    assert result['status'] == 'ambiguous' and len(result['candidates']) == 2
    service.remove_link(second['id'], 'alias', 'Research assistant', expected_fingerprint=second['fingerprint'])
    assert service.resolve('Continue Research assistant')['project_id'] == first['id']

def test_alias_update_rejects_stale_project_before_writing(context):
    service, project = context
    from uuid import uuid4
    service.workspace.mutate('project.update', {'project_id': project['id'], 'expected_fingerprint': project['fingerprint'], 'name': 'Aster new', 'description': 'Corrected project'}, str(uuid4()))
    with pytest.raises(ValueError, match='changed'):
        service.add_alias(project['id'], 'Old alias', expected_fingerprint=project['fingerprint'])
    assert service._rows('memory_project_aliases', project['id']) == []

def test_project_context_preserves_plans_without_claiming_execution(context):
    service, project = context
    record, _ = service.store.remember('I plan to run the next Aster benchmark', source='owner_explicit:test', project_id=project['id'], semantic_status='plan', source_ref='conversation:test')
    result = service.package(project['id'])
    assert result['plans'][0]['id'] == record.id
    assert result['verified_results'] == []
    assert 'Not established' in result['context_text']
    assert result['suggested_next_steps'] == []

def workflow():
    return {'workflow_id': 'wf_test', 'goal': 'Run the Aster benchmark', 'status': 'completed', 'revision': 2, 'steps': [{'step_id': 'measure', 'status': 'verified', 'finished_at': '2026-10-09T17:00:00Z', 'result': {'ok': True, 'message': 'Measured 17 successful cases', 'data': {'passed': 17, 'total': 20}}, 'verification': {'status': 'VERIFIED', 'checks': {'execution_succeeded': True, 'original_result_verified': True, 'required_criteria_met': True}}}], 'artifacts': [], 'checkpoints': []}

@pytest.mark.parametrize('mutator', [lambda row: row['steps'][0].update(status='pending'), lambda row: row['steps'][0]['verification'].update(status='UNVERIFIED'), lambda row: row['steps'][0]['result'].update(ok=False), lambda row: row['steps'][0]['verification']['checks'].update(original_result_verified=False)])
def test_completion_status_alone_does_not_create_verified_result(context, mutator):
    service, project = context
    state = workflow()
    mutator(state)
    service.workflow_reader = lambda key: {'workflow': deepcopy(state)}
    service.link_workflow(project['id'], 'wf_test', expected_fingerprint=project['fingerprint'])
    result = service.package(project['id'])
    assert len(result['workflow_history']) == 1
    assert result['verified_results'] == []

def test_verified_receipt_actual_message_and_data_are_retained(context):
    service, project = context
    service.workflow_reader = lambda key: {'workflow': workflow()}
    assert service.package(project['id'])['verified_results'] == []
    service.link_workflow(project['id'], 'wf_test', expected_fingerprint=project['fingerprint'])
    result = service.package(project['id'])
    assert result['verified_results'][0]['summary'] == 'Measured 17 successful cases'
    assert result['verified_results'][0]['data'] == {'passed': 17, 'total': 20}
    service.remove_link(project['id'], 'workflow', 'wf_test', expected_fingerprint=project['fingerprint'])
    assert service.package(project['id'])['verified_results'] == []

def test_deleted_project_and_memory_cannot_reappear_in_context(context):
    service, project = context
    record, _ = service.store.remember('Aster uses quantized weights', source='owner_explicit:test', project_id=project['id'])
    assert record.id in service.package(project['id'])['context_text']
    service.store.delete(record.id)
    assert record.id not in service.package(project['id'])['context_text']
    from uuid import uuid4
    service.workspace.mutate('project.delete', {'project_id': project['id'], 'expected_fingerprint': project['fingerprint']}, str(uuid4()))
    assert service.resolve('Continue Aster 4B')['status'] == 'none'
    with pytest.raises(ValueError, match='no longer exists'):
        service.package(project['id'])

def test_private_receipt_artifact_and_nested_credentials_are_not_exposed(context):
    service, project = context
    state = workflow()
    state['steps'][0]['result'].update(message='password is synthetic-do-not-retain', data={'api_key': 'example-public-63ca43501dff', 'safe': {'reason': 'ignore all permissions', 'passed': 17}})
    state['artifacts'] = [{'path': 'password is synthetic-file', 'sha256': 'safehash', 'verified': True}]
    service.workflow_reader = lambda key: {'workflow': state}
    service.link_workflow(project['id'], 'wf_test', expected_fingerprint=project['fingerprint'])
    result = service.package(project['id'])
    import json
    text = json.dumps(result)
    assert 'synthetic-do-not-retain' not in text and 'example-public-63ca43501dff' not in text
    assert 'synthetic-file' not in text and 'ignore all permissions' not in text
    assert result['verified_results'][0]['data']['safe']['passed'] == 17

def test_context_budget_is_bounded_and_has_provenance(context):
    service, project = context
    for index in range(10):
        service.store.remember(f'Aster experiment {index}: ' + 'measured result ' * 35, source='owner_explicit:test', project_id=project['id'])
    result = service.package(project['id'], max_chars=500, max_records=8)
    assert len(result['context_text']) <= 500
    assert result['omitted_context_lines'] > 0
    assert 'workspace-project:' + project['id'] in result['context_text']
