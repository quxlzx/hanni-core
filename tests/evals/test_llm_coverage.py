from copy import deepcopy
from hanni.evals.llm_coverage import DEFAULT_COVERAGE_CASES, audit_coverage
from hanni.evals.llm_tools import audit_scenarios, load_scenarios
from hanni.evals.routing import build_default_host

def test_capability_coverage_does_not_count_blocked_tools_as_missing():
    report = audit_coverage(build_default_host(), load_scenarios())
    assert report['registered'] == len(report['rows'])
    assert report['model_facing'] + report['intentionally_not_model_facing'] == report['registered']
    by_name = {row['capability']: row for row in report['rows']}
    assert by_name['powershell.run']['status'] == 'not_model_facing'
    assert by_name['system.stats']['model_facing']
    assert report['model_facing_with_no_required_scenarios'] > 0

def test_separate_coverage_corpus_probes_every_model_facing_capability_twice():
    host = build_default_host()
    cases = load_scenarios(DEFAULT_COVERAGE_CASES)
    report = audit_coverage(host, cases)
    routing = audit_scenarios(host, cases)
    assert len(cases) == 2 * report['model_facing']
    assert report['model_facing_with_two_required_scenarios'] == report['model_facing']
    assert report['model_facing_with_one_required_scenario'] == 0
    assert report['model_facing_with_no_required_scenarios'] == 0
    assert report['coverage_errors'] == []
    assert report['description_quality_warnings'] == []
    assert routing['corpus_failures'] == []

def test_coverage_audit_catches_schema_and_risk_drift():
    case = deepcopy(load_scenarios(DEFAULT_COVERAGE_CASES)[0])
    case['expected_schema'] = {}
    case['risk_level'] = -1
    report = audit_coverage(build_default_host(), [case])
    assert any(('argument schema drift' in error for error in report['coverage_errors']))
    assert any(('risk metadata drift' in error for error in report['coverage_errors']))
