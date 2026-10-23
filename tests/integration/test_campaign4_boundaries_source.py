"""Owner-requested source identity, independent from controlled planner proposals."""
import os
from pathlib import Path
import pytest
from hanni.workflows.planner import WorkflowPlanner
from hanni.workflows.types import resource_identity
from scripts.campaign4_boundaries.harness import ServiceFixture, plan_client, reviewed_start, step
from tests.unit.test_workflow_planner import host

def test_generated_outline_cannot_substitute_a_different_static_read_source(tmp_path):
    requested = tmp_path / 'owner-source.txt'
    substituted = tmp_path / 'substituted-source.txt'
    requested.write_text('Original requested source evidence.', encoding='utf-8')
    substituted.write_text('Different synthetic source, outside requested objective.', encoding='utf-8')
    with ServiceFixture(tmp_path / 'run', client=plan_client(step('read', substituted))) as box:
        key = box.submit('Read the text file ' + str(requested))
        initial = box.await_state(key, 'blocked', 'awaiting_plan_approval')
        if initial['status'] == 'awaiting_plan_approval':
            reviewed_start(box, key)
        final = box.await_state(key, 'blocked', 'completed')
        assert final['status'] == 'blocked' and (not final['invocations']), final

def test_static_binding_cannot_override_literal_owner_requested_read_source(tmp_path):
    requested = tmp_path / 'owner-source.txt'
    other = tmp_path / 'other-source.txt'
    requested.write_text('Owner source is the only actual data.', encoding='utf-8')
    other.write_text('Other source is a controlled distraction.', encoding='utf-8')
    proposed, bound = step('read', requested)
    bound['arguments']['path'] = str(other)
    with ServiceFixture(tmp_path / 'run', client=plan_client((proposed, bound))) as box:
        key = box.submit('Read the text file ' + str(requested))
        initial = box.await_state(key, 'blocked', 'awaiting_plan_approval')
        if initial['status'] == 'awaiting_plan_approval':
            reviewed_start(box, key)
        final = box.await_state(key, 'completed', 'blocked')
        if final['status'] == 'blocked':
            assert not final['invocations']
        else:
            assert final['steps'][0]['resolved_arguments']['path'] == str(requested)
            assert final['steps'][0]['result']['data']['text'] == requested.read_text(encoding='utf-8')

def test_second_explicitly_requested_source_remains_authorized(tmp_path):
    first, second = (tmp_path / 'first-source.txt', tmp_path / 'second-source.txt')
    first.write_text('First explicitly requested source.', encoding='utf-8')
    second.write_text('Second explicitly requested source.', encoding='utf-8')
    client = plan_client(step('first', first), step('second', second, dependencies=('first',)))
    with ServiceFixture(tmp_path / 'run', client=client) as box:
        key = box.submit('Read the text file ' + str(first) + ', then read the text file ' + str(second))
        reviewed_start(box, key)
        final = box.await_state(key, 'completed', 'blocked')
        assert final['status'] == 'completed' and final['counts']['verified'] == 2
        assert {item['resolved_arguments']['path'] for item in final['steps']} == {str(first), str(second)}

@pytest.mark.parametrize('quoting', ['', '"', "'"])
def test_complete_owner_source_with_spaces_remains_a_literal_path(host, tmp_path, quoting):
    source = tmp_path / 'complete owner directory' / 'ordinary source.txt'
    goal = 'Read the text file ' + quoting + str(source) + quoting
    plan = WorkflowPlanner(host, plan_client(step('read', source))).plan(goal, mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert resource_identity(plan['steps'][0]['arguments']['path']) == resource_identity(source)

def test_normalized_source_spelling_and_explicit_relative_path_remain_valid(host, tmp_path):
    source = tmp_path / 'data' / 'original.txt'
    requested = os.path.relpath(source, Path.cwd())
    alias = source.parent / 'subdirectory' / '..' / source.name
    plan = WorkflowPlanner(host, plan_client(step('read', alias))).plan('Read the text file ' + requested, mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert resource_identity(plan['steps'][0]['arguments']['path']) == resource_identity(source)

def test_quoted_unc_literal_preserved_without_touching_a_network_share(host, tmp_path, monkeypatch):
    source = Path('\\\\campaign4-isolated-unc\\owned share\\original.txt')
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if str(path).startswith('\\\\campaign4-isolated-unc\\'):
            return path
        return original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolve)
    plan = WorkflowPlanner(host, plan_client(step('read', source))).plan('Read the text file "' + str(source) + '"', mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert plan['steps'][0]['arguments']['path'] == str(source)

def test_source_after_an_unrelated_registered_calculation_remains_valid(host, tmp_path):
    source = tmp_path / 'full owner directory' / 'after-calculation.txt'
    calculation = dict(step_id='calculate', kind='tool', description='Calculate 14 plus 9.', dependencies=[], required=True, criteria=[dict(operator='present', path='/data/value', expected=None)])
    binding = dict(step_id='calculate', capability_id='calc.evaluate', arguments={'expression': '14+9'})
    read = step('read', source, dependencies=('calculate',))
    plan = WorkflowPlanner(host, plan_client((calculation, binding), read)).plan('Calculate 14 plus 9, then read the text file ' + str(source), mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert plan['steps'][1]['arguments']['path'] == str(source)

def test_path_free_objective_keeps_original_reviewed_source_binding(host, tmp_path):
    source = tmp_path / 'fixture-source.txt'
    plan = WorkflowPlanner(host, plan_client(step('read', source))).plan('Read the supplied text source.', mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert plan['steps'][0]['arguments']['path'] == str(source)

def test_verified_generated_artifact_path_reference_survives_explicit_owner_source(tmp_path):
    from scripts.campaign4_boundaries.harness import QueuedStructuredClient, artifact
    import json
    source = tmp_path / 'original-source.txt'
    source.write_text('Owner source for report round trip.', encoding='utf-8')
    read = step('read', source)
    save, bind_save = artifact()
    back = step('readback', source, dependencies=('save',))
    back[0]['description'] = 'Read the text file generated by the verified report predecessor.'
    back[1]['arguments']['path'] = {'$ref': dict(step_id='save', path='/data/path', type='string')}

    def bind(messages, _options):
        root = json.loads(messages[1]['content'])['artifact_root']
        return dict(unsupported_reason=None, steps=[read[1], bind_save(root), back[1]])
    client = QueuedStructuredClient(dict(summary='Read, save, read back.', unsupported_reason=None, steps=[read[0], save, back[0]]), bind)
    with ServiceFixture(tmp_path / 'run', client=client) as box:
        key = box.submit('Read the text file ' + str(source) + ', save the contents and read back the verified report.')
        reviewed_start(box, key)
        final = box.await_state(key, 'completed', 'blocked')
        assert final['status'] == 'completed' and final['counts']['verified'] == 3, final
        assert final['steps'][-1]['result']['data']['text'] == source.read_text(encoding='utf-8')

def test_unquoted_source_prefix_is_not_a_complete_path(host, tmp_path):
    requested = tmp_path / 'owner full directory' / 'source.txt'
    truncated = Path(str(requested).split(' ', 1)[0])
    from hanni.workflows.types import WorkflowError
    with pytest.raises(WorkflowError, match='source'):
        WorkflowPlanner(host, plan_client(step('read', truncated))).plan('Read the text file ' + str(requested), mode='assisted', artifact_root=tmp_path / 'artifacts')

@pytest.mark.parametrize('continuation', ['and preserve its verified contents.', 'then retain the observed material.', 'and produce a digest from its contents.'])
def test_complete_literal_file_path_does_not_absorb_following_prose(host, tmp_path, continuation):
    source = tmp_path / 'owner source directory' / 'sample.txt'
    plan = WorkflowPlanner(host, plan_client(step('read', source))).plan('Read the exact text file ' + str(source) + ' ' + continuation, mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert plan['steps'][0]['arguments']['path'] == str(source)

@pytest.mark.parametrize('directory,filename', [('owner and source directory', 'literal.txt'), ('version.v1 and source', 'full and actual.txt')])
def test_unquoted_path_component_conjunction_is_not_a_request_boundary(host, tmp_path, directory, filename):
    source = tmp_path / directory / filename
    plan = WorkflowPlanner(host, plan_client(step('read', source))).plan('Read the text file ' + str(source) + ' and retain the observed content.', mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert plan['steps'][0]['arguments']['path'] == str(source)

def test_plural_explicit_file_sources_with_following_adverb_preserve_both_paths(host, tmp_path):
    first, second = (tmp_path / 'first.txt', tmp_path / 'second.txt')
    plan = WorkflowPlanner(host, plan_client(step('first', first), step('second', second))).plan('Read local files ' + str(first) + ' and ' + str(second) + ' independently.', mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert {resource_identity(row['arguments']['path']) for row in plan['steps']} == {resource_identity(first), resource_identity(second)}

def test_unquoted_file_basename_spaces_do_not_authorize_a_shorter_dotted_prefix(host, tmp_path):
    from hanni.workflows.types import WorkflowError
    requested = tmp_path / 'original.v1 source.txt'
    prefix = tmp_path / 'original.v1'
    with pytest.raises(WorkflowError, match='source'):
        WorkflowPlanner(host, plan_client(step('read', prefix))).plan('Read the text file ' + str(requested), mode='assisted', artifact_root=tmp_path / 'artifacts')
    plan = WorkflowPlanner(host, plan_client(step('read', requested))).plan('Read the text file ' + str(requested), mode='assisted', artifact_root=tmp_path / 'artifacts')
    assert plan['steps'][0]['arguments']['path'] == str(requested)
