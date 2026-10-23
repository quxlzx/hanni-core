"""Public adapter contracts; no model, hardware, owner configuration or oracle."""
import ast
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.campaign10_systems.author import corpus, DIMENSIONS
from scripts.campaign10_systems.grade import evaluate
from scripts.campaign10_systems.runner import run_case

def test_prospective_sixty_inputs_have_distinct_objectives_and_separate_oracles():
    inputs, oracles = corpus()
    assert len(inputs) == len(oracles) == 60
    assert len({row['user_turns'][0]['prompt'].casefold() for row in inputs}) == 60
    assert {row['id'] for row in inputs} == {row['id'] for row in oracles}
    assert all(('checks' not in row and 'expected' not in row for row in inputs))
    assert all((set(row['dimensions']) == set(DIMENSIONS) for row in oracles))
    assert len({row['family'] for row in inputs}) >= 10

def test_executor_has_no_oracle_or_case_identity_dispatch():
    path = Path('scripts/campaign10_systems/runner.py')
    tree = ast.parse(path.read_text(encoding='utf8'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert 'author' not in str(ast.dump(node)) and 'grade' not in str(ast.dump(node))
        if isinstance(node, ast.Compare):
            assert not any((isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value.startswith('C10-SYS-') for item in [node.left, *node.comparators]))

def test_unsupported_operation_cannot_substitute_a_default_action(tmp_path):
    case = {'id': 'public-unsupported', 'family': 'public', 'fixtures': {'adapter': 'memory'}, 'actions': [{'operation': 'memory.invented', 'args': {}}]}
    receipt = run_case(case, tmp_path / 'fresh')
    assert receipt['harness_error']['type'] == 'NotImplementedError'
    assert receipt['observations'] == [] and receipt['real_model_requests'] == 0

def test_missing_query_is_not_derived_from_an_oracle_or_owner_prompt(tmp_path):
    case = {'id': 'public-missing', 'family': 'public', 'fixtures': {'adapter': 'memory'}, 'user_turns': [{'prompt': 'Find my preference'}], 'actions': [{'operation': 'memory.retrieve', 'args': {}}]}
    receipt = run_case(case, tmp_path / 'fresh')
    assert receipt['harness_error']['type'] == 'KeyError'
    assert receipt['observations'] == []

def test_two_disposable_memory_roots_do_not_share_records(tmp_path):
    base = {'id': 'public-isolation', 'family': 'public', 'fixtures': {'adapter': 'memory'}, 'actions': [{'operation': 'memory.retrieve', 'args': {'query': 'orange testing summary'}}]}
    first = deepcopy(base)
    first['fixtures']['memories'] = [{'content': 'Orange testing summary is reviewed weekly.'}]
    one = run_case(first, tmp_path / 'one')
    two = run_case(base, tmp_path / 'two')
    assert one['memory_count'] == 1 and two['memory_count'] == 0
    assert two['observations'][0]['data']['contents'] == []

def test_reusing_an_existing_state_directory_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='fresh disposable'):
        run_case({'id': 'public', 'family': 'public'}, tmp_path)

def test_grader_does_not_promote_controlled_data_to_model_response_pass():
    receipt = {'id': 'public', 'family': 'public', 'evidence_categories': ['ISOLATED_IMPLEMENTATION'], 'elapsed_seconds': 0.2, 'harness_error': None, 'value': 'saved bytes'}
    result = evaluate(receipt, {'checks': [{'path': '/value', 'value': 'saved bytes', 'op': 'eq', 'dimension': 'final_response'}]})
    assert result['contract_verdict'] == 'PASS'
    assert result['dimensions']['final_response']['status'] == 'NOT_MEASURED'
    assert result['model_task_completion'] == 'NOT_MEASURED'

def test_missing_readback_fails_prospective_verification_instead_of_success():
    receipt = {'id': 'public', 'family': 'public', 'evidence_categories': ['ISOLATED_IMPLEMENTATION'], 'elapsed_seconds': 0.2, 'harness_error': None}
    result = evaluate(receipt, {'checks': [{'path': '/verified/report', 'value': True, 'op': 'eq', 'dimension': 'outcome_verification'}]})
    assert result['contract_verdict'] == 'FAIL'
    assert result['checks'][0]['lookup_error'] == 'KeyError'

def test_schema_amendment_changes_only_missing_nulls_and_keeps_oracle_objects(tmp_path):
    import json
    from scripts.campaign10_systems.amend import correction
    inputs, oracles = corpus()
    source, answers = (tmp_path / 'inputs.jsonl', tmp_path / 'oracles.jsonl')
    source.write_text(''.join((json.dumps(row) + '\n' for row in inputs)), encoding='utf8')
    answers.write_text(''.join((json.dumps(row) + '\n' for row in oracles)), encoding='utf8')
    before = (source.read_bytes(), answers.read_bytes())
    result = correction(source, answers, tmp_path / 'amended')
    amended = [json.loads(x) for x in (tmp_path / 'amended/inputs.jsonl').read_text().splitlines()]
    kept_oracles = [json.loads(x) for x in (tmp_path / 'amended/oracles.jsonl').read_text().splitlines()]
    original = {row['id']: row for row in inputs}
    for row in amended:
        reverted = deepcopy(row)
        for step in reverted['fixtures']['steps']:
            for criterion in step['criteria']:
                if criterion.get('operator') == 'present':
                    assert criterion.pop('expected') is None
        assert reverted == original[row['id']]
    assert kept_oracles == [row for row in oracles if row['id'] in {r['id'] for r in amended}]
    assert before == (source.read_bytes(), answers.read_bytes())
    assert result['tasks'] == 12

@pytest.mark.parametrize('first_state,first_text,expected', [('finished', 'verified bytes', 1), ('finished', 'contradictory bytes', 0), ('abandoned', 'verified bytes', 0), ('uncertain', 'verified bytes', 0)])
def test_replay_audit_requires_an_actual_native_verified_finished_result(first_state, first_text, expected):
    from scripts.campaign10_systems.runner import audit_replays
    step = {'step_id': 'source', 'kind': 'tool', 'capability_id': 'file.read', 'dependencies': [], 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'verified bytes'}]}
    result = {'ok': True, 'data': {'text': first_text}, 'verification': {'status': 'VERIFIED'}}
    detail = {'steps': [step], 'invocations': [{'step_id': 'source', 'invocation_id': 'earlier', 'state': first_state, 'started_at': '1', 'result': result}, {'step_id': 'source', 'invocation_id': 'later', 'state': 'dispatched', 'started_at': '2'}]}
    assert audit_replays(detail)['count'] == expected

def _public_shared_case(key):
    from scripts.campaign10_systems.smoke import public_cases
    return next((row for row in public_cases() if row['id'] == 'PUBLIC-SYSTEMS-' + key))

def _shared_receipt(case, root):
    from scripts.campaign10_systems.shared import execute_input
    from scripts.campaign10_verification.adapter import run_input
    return run_input(case, root, execute_input)

def test_shared_precreated_root_and_alias_use_original_retrieval_without_model_claim(tmp_path):
    row = _shared_receipt(_public_shared_case('MEMORY'), tmp_path / 'case')
    assert 'adapter_error' not in row and row['harness_error'] is None
    assert row['observations'][0]['operation'] == 'memory.retrieve'
    assert row['observations'][0]['data']['contents'] == ['Archived build summaries include test counts.']
    assert row['real_model_requests'] == 0 and row['request_path_original'] is False
    assert row['dimensions']['final_response']['status'] == 'NOT_MEASURED'

def test_shared_confirmed_turn_does_not_supply_missing_plan_review_or_start(tmp_path):
    row = _shared_receipt(_public_shared_case('UNREVIEWED'), tmp_path / 'case')
    assert row['harness_error'] is None and row['status'] == 'awaiting_plan_approval'
    assert row['invocation_count'] == row['write_effect_count'] == 0
    assert row['raw_workflow']['controls'] == []

def test_shared_explicit_review_retains_native_order_verification_and_file_receipts(tmp_path):
    row = _shared_receipt(_public_shared_case('REVIEWED'), tmp_path / 'case')
    assert row['harness_error'] is None and row['status'] == 'completed'
    assert row['verified_steps'] == row['invocation_count'] == 2
    steps = row['raw_workflow']['workflow']['steps']
    assert steps[1]['dependencies'] == ['first']
    assert [step['result']['data']['text'] for step in steps] == ['First synthetic source.', 'Second synthetic source.']
    assert row['unauthorized_effects'] == row['duplicate_effects'] == 0
    assert row['model_intent'] == 'NOT_MEASURED'

def test_shared_failed_prerequisite_never_dispatches_dependent_read(tmp_path):
    row = _shared_receipt(_public_shared_case('PREREQUISITE'), tmp_path / 'case')
    assert row['harness_error'] is None and row['status'] == 'blocked'
    assert row['verified_steps'] == 0 and row['max_attempt'] == 2
    assert {call['step_id'] for call in row['raw_workflow']['workflow']['invocations']} == {'first'}
    assert row['raw_workflow']['workflow']['steps'][1].get('result') is None

@pytest.mark.parametrize('confirmed', [False, True])
def test_shared_nonowner_submission_reaches_original_gate_without_controller_or_dispatch(tmp_path, confirmed):
    case = _public_shared_case('NONOWNER')
    case['user_turns'][0]['confirmed'] = confirmed
    row = _shared_receipt(case, tmp_path / 'case')
    assert row['observations'][0]['data']['accepted'] is False
    assert 'trusted owner interface' in row['observations'][0]['data']['reason']
    assert row['actor_path_original'] is True and row['original_service_calls'] == 1
    assert row['workflow_count_before'] == row['workflow_count_after'] == 0
    assert row['planner_calls'] == row['tool_dispatches'] == 0

@pytest.mark.parametrize('key', ['MISSINGPLAN', 'MISSINGARG', 'MIXEDACTORS'])
def test_shared_missing_explicit_authority_or_arguments_do_not_seed_or_execute(tmp_path, key):
    root = tmp_path / 'case'
    row = _shared_receipt(_public_shared_case(key), root)
    assert row['evidence_categories'] == ['NOT_IMPLEMENTED']
    assert row['original_service_calls'] == 0 and row['actions'] == []
    assert not (root / 'services').exists()

def test_shared_text_only_scope_is_separate_from_valid_evidence_category(tmp_path):
    row = _shared_receipt(_public_shared_case('TEXT'), tmp_path / 'case')
    assert 'adapter_error' not in row
    assert row['evidence_categories'] == ['ISOLATED_IMPLEMENTATION']
    assert row['observations'][0]['data']['wake_word_detected'] is True
    assert row['audio_measurement_scope'].startswith('TEXT_ONLY')
    assert row['physical_audio_calls'] == 0

@pytest.mark.parametrize('replacement', ['{root}/../outside.txt', 'C:/not-owned/input.txt'])
def test_shared_workflow_literal_sources_cannot_escape_disposable_state(tmp_path, replacement):
    case = _public_shared_case('REVIEWED')
    case['fixtures']['steps'][0]['arguments']['path'] = replacement
    row = _shared_receipt(case, tmp_path / 'case')
    assert row['original_service_calls'] == 0 and row['actions'] == []
    assert not (tmp_path / 'case/services').exists()

def test_shared_goal_substitution_and_role_elevation_are_not_silently_corrected(tmp_path):
    case = _public_shared_case('REVIEWED')
    case['fixtures']['goal'] = 'Read a different source.'
    row = _shared_receipt(case, tmp_path / 'case')
    assert row['original_service_calls'] == 0
    legacy = _public_shared_case('MEMORY')
    legacy['user_turns'][0]['actor_profile'] = 'default'
    with pytest.raises(ValueError, match='Actor'):
        _shared_receipt(legacy, tmp_path / 'invalid-role')
    assert not (tmp_path / 'invalid-role').exists()

def test_shared_adapter_never_reuses_preexisting_service_state(tmp_path):
    from scripts.campaign10_systems.shared import execute_input
    state = tmp_path / 'services'
    state.mkdir()
    marker = state / 'preserve.txt'
    marker.write_text('existing synthetic state', encoding='utf-8')
    with pytest.raises(ValueError, match='fresh'):
        execute_input(_public_shared_case('MEMORY'), tmp_path)
    assert marker.read_text() == 'existing synthetic state'

@pytest.mark.parametrize('field,value', [('bind', 'later-source'), ('actor_profile', 'owner'), ('confirmed', True), ('scope', {'allowed': True})])
def test_shared_unimplemented_bindings_and_action_authority_overrides_are_explicitly_refused(tmp_path, field, value):
    case = _public_shared_case('MEMORY')
    if field == 'bind':
        case['actions'][0][field] = value
    else:
        case['actions'][0]['args'][field] = value
    row = _shared_receipt(case, tmp_path / 'case')
    assert row['original_service_calls'] == row['original_adapter_invocations'] == 0
    assert row['actions'] == [] and (not (tmp_path / 'case/services').exists())

def test_shared_path_reference_cannot_reinterpret_file_content_as_an_outside_filename(tmp_path):
    case = _public_shared_case('REVIEWED')
    victim = tmp_path / 'outside-case.txt'
    victim.write_text('Owned sibling marker, not an owner file.', encoding='utf-8')
    case['fixtures']['files']['a.txt'] = str(victim)
    case['fixtures']['steps'][1]['arguments']['path'] = {'$ref': {'step_id': 'first', 'path': '/data/text', 'type': 'string'}}
    row = _shared_receipt(case, tmp_path / 'case')
    assert row['original_service_calls'] == row['original_adapter_invocations'] == 0
    assert row['actions'] == [] and (not (tmp_path / 'case/services').exists())
    assert victim.read_text() == 'Owned sibling marker, not an owner file.'

def test_shared_managed_artifact_path_reference_keeps_native_prerequisite_and_readback(tmp_path):
    case = _public_shared_case('REVIEWED')
    goal = 'Read {root}/a.txt, save that verified text as a report, then read the saved report.'
    case['user_turns'][0]['prompt'] = case['fixtures']['goal'] = goal
    case['fixtures']['steps'] = [case['fixtures']['steps'][0], {'step_id': 'save', 'description': 'Save the requested report to {artifact_root}/handoff.md', 'kind': 'artifact', 'capability_id': 'file.write', 'dependencies': ['first'], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/path', 'expected': None}], 'arguments': {'path': '{artifact_root}/handoff.md', 'text': {'$ref': {'step_id': 'first', 'path': '/data/text', 'type': 'string'}}}}, {'step_id': 'readback', 'description': 'Read the saved report file {artifact_root}/handoff.md', 'kind': 'tool', 'capability_id': 'file.read', 'dependencies': ['save'], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/text', 'expected': None}], 'arguments': {'path': {'$ref': {'step_id': 'save', 'path': '/data/path', 'type': 'string'}}}}]
    row = _shared_receipt(case, tmp_path / 'case')
    assert row['harness_error'] is None and row['status'] == 'completed'
    assert row['verified_steps'] == row['invocation_count'] == 3
    assert row['write_effect_count'] == 1 and row['report_texts'] == ['First synthetic source.']
    assert row['raw_workflow']['workflow']['steps'][2]['result']['data']['text'] == 'First synthetic source.'
    assert row['completed_replayed'] == row['duplicate_effects'] == row['unauthorized_effects'] == 0
