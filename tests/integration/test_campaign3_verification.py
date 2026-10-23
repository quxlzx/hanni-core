"""Independent generic verifier boundaries; never imports private holdouts."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from scripts.campaign3_verification.holdout_runner import run_case
from scripts.campaign3_verification.score import score, summarize

def generic_case(**changes):
    case = dict(id='independent-development', category='development', difficulty='easy', memories=[dict(id='record-a', content='The spectrometer output format is JSONL', source='owner_explicit:fixture', source_ref='controlled:source-a')], operations=[], query='spectrometer output format JSONL', options=dict(limit=5, max_chars=4000, max_tokens=4000, min_score=25.0))
    case.update(changes)
    return case

@pytest.mark.parametrize('arm', ['legacy', 'context'])
def test_runner_original_retrieval_and_provenance(tmp_path, arm):
    case = generic_case()
    receipt = run_case(case, tmp_path / arm, arm)
    assert receipt['final']['logical_ids'] == ['record-a']
    assert receipt['final']['authoritative_store_unchanged'] is True
    assert receipt['final']['records'][0]['source_ref'] == 'controlled:source-a'
    assert receipt['actual_model_calls'] == 0
    assert score(case, dict(relevant_ids=['record-a'], source_by_id={'record-a': 'controlled:source-a'}), receipt)['passed']

def test_runner_never_accepts_oracles(tmp_path):
    case = generic_case(expected={'relevant_ids': ['record-a']})
    with pytest.raises(ValueError, match='Oracles'):
        run_case(case, tmp_path / 'forbidden', 'context')
    assert not (tmp_path / 'forbidden').exists()

@pytest.mark.parametrize('arm', ['legacy', 'context'])
def test_warm_correction_delete_and_original_suggestion_purge(tmp_path, arm):
    case = generic_case(operations=[dict(op='retrieve'), dict(op='propose', kind='correct', target_id='record-a', content='The spectrometer output format is CSV'), dict(op='correct', target_id='record-a', content='The spectrometer output format is CSV', source_ref='controlled:corrected'), dict(op='delete', target_id='record-a')])
    receipt = run_case(case, tmp_path / arm, arm)
    assert receipt['retrievals'][0]['logical_ids'] == ['record-a']
    assert receipt['readbacks']['record-a']['record'] is None
    assert receipt['readbacks']['record-a']['history'] == []
    assert receipt['readbacks']['record-a']['suggestions'] == []
    grade = score(case, dict(relevant_ids=[], deleted_ids=['record-a'], history_purged_ids=['record-a'], suggestions_purged_ids=['record-a']), receipt)
    assert grade['passed'], grade['errors']

def test_stale_revision_rejection_is_not_any_error(tmp_path):
    case = generic_case(operations=[dict(op='correct', target_id='record-a', content='The spectrometer output format is CSV'), dict(op='correct', target_id='record-a', content='The spectrometer output format is XML', revision='original', expect_error='MemoryConflictError')])
    receipt = run_case(case, tmp_path / 'stale', 'context')
    assert receipt['actions'][1]['error']['type'] == 'MemoryConflictError'
    grade = score(case, dict(relevant_ids=['record-a'], contains_by_id={'record-a': 'CSV'}), receipt)
    assert grade['passed'], grade['errors']
    bad = deepcopy(receipt)
    bad['actions'][1]['error']['type'] = 'KeyError'
    assert not score(case, dict(relevant_ids=['record-a']), bad)['passed']

def test_empty_precision_and_failed_positive_recall_keep_denominators():
    case = generic_case()
    receipt = dict(arm='legacy', final={'logical_ids': [], 'context_text': '', 'error': {'type': 'RuntimeError'}}, labels={}, readbacks={})
    grade = score(case, dict(relevant_ids=['record-a']), receipt)
    assert grade['recall_at_5'] == 0
    assert grade['precision_returned_at_5'] is None
    summary = summarize([grade])
    assert summary['recall_at_5']['relevant'] == 1
    assert summary['recall_at_5']['micro'] == 0
    assert summary['precision_returned_at_5']['empty_positive_cases'] == 1

def test_actual_answer_requirement_not_claimed_from_retrieval(tmp_path):
    case = generic_case()
    receipt = run_case(case, tmp_path / 'response', 'context')
    grade = score(case, dict(relevant_ids=['record-a'], uncertainty_required=True), receipt)
    assert grade['status'] == 'PARTIAL'
    assert grade['unmeasured_requirements'][0]['requirement'] == 'uncertainty_required'
    assert summarize([grade])['actual_model_response_accuracy'] is None

def test_context_budget_preserves_whole_records(tmp_path):
    case = generic_case(options=dict(limit=5, max_chars=512, max_tokens=128, min_score=25.0))
    receipt = run_case(case, tmp_path / 'budget', 'context')
    assert receipt['final']['context_text'] == ''
    grade = score(case, dict(relevant_ids=[], budget_compliance=True, complete_record_only=True), receipt)
    assert grade['passed']

def test_same_timestamp_external_content_is_live_authority(tmp_path):
    case = generic_case(operations=[dict(op='retrieve'), dict(op='external_update', target_id='record-a', content='The spectrometer output format is YAML', keep_updated_at=True)])
    receipt = run_case(case, tmp_path / 'external', 'context')
    grade = score(case, dict(relevant_ids=['record-a'], contains_by_id={'record-a': 'YAML'}, cache_is_not_authority=True), receipt)
    assert grade['passed'], grade['errors']

@pytest.mark.parametrize('probe', ['boundary', 'retrieval', 'project', 'tier', 'recovery', 'injection', 'confidence', 'project_metadata', 'project_current'])
def test_independent_exposed_security_and_recovery_probes(tmp_path, probe):
    if probe == 'boundary':
        from scripts.campaign3_verification.boundary_reproduce import execute as run
    elif probe == 'retrieval':
        from scripts.campaign3_verification.retrieval_reproduce import run
    elif probe == 'project':
        from scripts.campaign3_verification.project_reproduce import run
    elif probe == 'tier':
        from scripts.campaign3_verification.tier_reproduce import run
    elif probe == 'recovery':
        from scripts.campaign3_verification.recovery_reproduce import run
    elif probe == 'injection':
        from scripts.campaign3_verification.injection_reproduce import run
    elif probe == 'confidence':
        from scripts.campaign3_verification.confidence_reproduce import run
    elif probe == 'project_metadata':
        from scripts.campaign3_verification.project_metadata_reproduce import run
    else:
        from scripts.campaign3_verification.project_current_reproduce import run
    summary = run(tmp_path / probe)
    assert summary['passed'] == summary['total'], summary
