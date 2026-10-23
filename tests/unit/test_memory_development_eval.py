from __future__ import annotations
import json
import pytest
from hanni.evals.memory_intelligence import development_cases, evaluate, main, validate_cases

def test_development_case_contract_rejects_holdout_and_missing_provenance():
    cases = development_cases()
    assert len(validate_cases(cases)) == 20
    cases[0]['partition'] = 'holdout'
    with pytest.raises(ValueError, match='holdout'):
        validate_cases(cases)
    cases[0]['partition'] = 'development'
    cases[0]['expected_ids'] = ['fabricated-source-id']
    with pytest.raises(ValueError, match='exist'):
        validate_cases(cases)

def test_eval_reports_honest_scope_no_model_attempt_or_memory_mutation():
    report = evaluate(development_cases(), repeats=1)
    assert report['partition'] == 'development'
    assert report['unauthorized_memory_changes'] == 0
    assert report['C_actual_laya_advisory']['status'] == 'BLOCKED'
    assert report['D_full_context']['status'] == 'NOT_EVALUATED'
    for summary in report['summary'].values():
        assert summary['scenarios'] == summary['timed_samples'] == 20
        assert summary['grounded_id_count'] == 20
        assert 0 <= summary['mean_recall_at_5'] <= 1
        assert summary['p95_retrieval_ms'] >= summary['p50_retrieval_ms'] >= 0

def test_cli_never_overwrites_existing_review_artifacts(tmp_path):
    target = tmp_path / 'development.json'
    assert main(['--output', str(target), '--repeats', '1']) == 0
    first = target.read_bytes()
    assert json.loads(first)['partition'] == 'development'
    with pytest.raises(FileExistsError):
        main(['--output', str(target), '--repeats', '1'])
    assert target.read_bytes() == first
