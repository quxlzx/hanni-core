"""Architectural workflow regressions and genuine original-engine receipts."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from hanni.workflows.references import matches_type, resolve
from hanni.workflows.types import WorkflowError
from scripts.campaign4.run_cohort import evaluate
from scripts.campaign4.workflow_harness import ControlledPlannerClient, run_case, transition_atomicity

def completed(value):
    return {'source': {'status': 'verified', 'verification': {'status': 'VERIFIED'}, 'result': {'ok': True, 'data': {'value': value}}}}

@pytest.mark.parametrize('value', [10 ** 401, -(3 * 10 ** 399)])
def test_large_bounded_json_integer_reference_keeps_exact_value(value):
    assert resolve({'$ref': {'step_id': 'source', 'path': '/data/value', 'type': 'integer'}}, ['source'], completed(value)) == value

@pytest.mark.parametrize('kind', ['number', 'string', 'boolean', 'object', 'array', 'null'])
def test_large_integer_incompatible_reference_is_bounded_workflow_error(kind):
    with pytest.raises(WorkflowError):
        resolve({'$ref': {'step_id': 'source', 'path': '/data/value', 'type': kind}}, ['source'], completed(9 * 10 ** 390))

@pytest.mark.parametrize('value,kind,expected', [(False, 'integer', False), (True, 'number', False), (True, 'boolean', True), (15, 'number', True), (3.25, 'number', True), (float('nan'), 'number', False), (float('inf'), 'number', False), ('text', 'string', True), ({}, 'object', True), ([], 'array', True), (None, 'null', True)])
def test_type_boundaries_remain_strict(value, kind, expected):
    assert matches_type(value, kind) is expected

def test_every_declared_transition_has_actual_store_rollback_readback(tmp_path):
    from hanni.workflows.types import TRANSITIONS
    rows = transition_atomicity(tmp_path / 'edges')
    assert {(row['source'], row['target']) for row in rows} == {(source, target) for source, targets in TRANSITIONS.items() for target in targets}
    assert all((row['passed'] and row['before_hash'] == row['after_rejection_hash'] for row in rows))

def test_every_declared_transition_rolls_back_after_projection_checkpoint_fault(tmp_path):
    from hanni.workflows.types import TRANSITIONS
    from scripts.campaign4.transition_faults import run
    result = run(tmp_path / 'faults', sealed=tmp_path / 'prospective-transitions.json')
    assert {(row['source'], row['target']) for row in result['receipts']} == {(source, target) for source, targets in TRANSITIONS.items() for target in targets}
    assert all((row['passed'] and row['before_hash'] == row['after_hash'] == row['reopened_hash'] for row in result['receipts']))

def test_controlled_planner_returns_original_text_interface_without_authority(tmp_path):
    from scripts.campaign4.development_corpus import corpus
    case = deepcopy(corpus()[0])
    case.pop('expected')
    client = ControlledPlannerClient(case, tmp_path)
    text = client.chat([{'role': 'user', 'content': json.dumps({'artifact_root': str(tmp_path / 'artifacts')})}])
    assert isinstance(text, str)
    parsed = json.loads(text)
    assert set(parsed) == {'summary', 'unsupported_reason', 'steps'}
    assert client.responses[0]['raw'] == text

def test_actual_postwrite_timeout_ledger_keeps_effect_and_exact_authority(tmp_path):
    from scripts.campaign4.development_corpus import corpus
    case = next((row for row in corpus() if row['id'] == 'WFDEV-12-05'))
    input_case = {key: deepcopy(value) for key, value in case.items() if key != 'expected'}
    receipt = run_case(input_case, tmp_path / 'workflow')
    assert evaluate(receipt, case['expected'])['passed']
    writes = receipt['effect_ledger']
    assert len(writes) == 1
    assert writes[0]['actual_effect'] and writes[0]['authorized']
    assert writes[0]['error'] == 'timeout_after' and (not writes[0]['returned'])
    invocation = next((item for item in receipt['workflow']['invocations'] if item['invocation_id'] == writes[0]['invocation_id']))
    assert invocation['correlation_id'] == writes[0]['correlation_id']
    assert writes[0]['scope_provenance'] == 'owner_plan_review'
    assert writes[0]['scope_expires'] > writes[0]['authority_time']

def test_actual_parallel_reads_have_two_concurrent_original_entries(tmp_path):
    from scripts.campaign4.supplemental_corpus import corpus
    case = next((row for row in corpus() if row['id'] == 'WFSUP-PARALLEL-1'))
    receipt = run_case({key: deepcopy(value) for key, value in case.items() if key != 'expected'}, tmp_path / 'parallel')
    assert evaluate(receipt, case['expected'])['passed']
    entries = [row for row in receipt['leaf_calls'] if row.get('fault') == 'barrier']
    assert len(entries) == 2
    assert all((row['caller_module'] == 'hanni.tools.files' and row['caller_function'] == '_read' for row in entries))

def test_unapproved_external_path_has_no_original_handler_entry(tmp_path):
    from scripts.campaign4.development_corpus import corpus
    case = next((row for row in corpus() if row['id'] == 'WFDEV-08-01'))
    receipt = run_case({key: deepcopy(value) for key, value in case.items() if key != 'expected'}, tmp_path / 'approval')
    assert evaluate(receipt, case['expected'])['passed']
    assert receipt['effect_ledger'] == []
    assert not (tmp_path / 'approval' / 'requested-report.txt').exists()

@pytest.mark.parametrize('case_id', ['WFEX-04-01', 'WFEX-06-04', 'WFEX-11-02'])
def test_explicit_multisource_objective_executes_original_dependency_graph(tmp_path, case_id):
    from scripts.campaign4.explicit_goal_corpus import corpus
    case = next((row for row in corpus() if row['id'] == case_id))
    receipt = run_case({key: deepcopy(value) for key, value in case.items() if key != 'expected'}, tmp_path / case_id)
    assert evaluate(receipt, case['expected'])['passed'], evaluate(receipt, case['expected'])['errors']

def test_explicit_multisource_supplement_preserves_original_oracles():
    from scripts.campaign4.development_corpus import corpus as original_corpus
    from scripts.campaign4.explicit_goal_corpus import corpus as supplement_corpus
    originals = {row['id']: row for row in original_corpus()}
    for row in supplement_corpus():
        original = originals[row['original_graph_id']]
        assert row['expected'] == original['expected']
        assert row['steps'] == original['steps']
        assert row['faults'] == original['faults']
        assert row['controls'] == original['controls']
        assert row['goal'] != original['goal']
