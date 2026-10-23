"""The personal-language holdout is immutable after its pre-inference lock."""
import json
from collections import Counter
from pathlib import Path
from hanni.evals.llm_tools import audit_scenarios, corpus_sha256, load_scenarios
from hanni.evals.routing import build_default_host

def test_personal_holdout_lock_and_separation():
    root = Path(__file__).resolve().parents[2] / 'evals' / 'llm_tools'
    holdout = load_scenarios(root / 'holdout_v1.jsonl')
    manifest = json.loads((root / 'holdout_v1.lock.json').read_text(encoding='utf-8'))
    development = load_scenarios(root / 'cases.jsonl')
    assert manifest['scenario_count'] == len(holdout) == 50
    assert corpus_sha256(holdout) == manifest['corpus_sha256']
    assert dict(sorted(Counter((row['family'] for row in holdout)).items())) == manifest['family_counts']
    assert len({row['id'] for row in holdout}) == 50
    assert not {row['query'].casefold() for row in holdout} & {row['query'].casefold() for row in development}
    assert all(('results' in row and 'claims' in row for row in holdout))

def test_holdout_routing_misses_still_have_safe_mock_coverage():
    root = Path(__file__).resolve().parents[2]
    cases = load_scenarios(root / 'evals' / 'llm_tools' / 'holdout_v1.jsonl')
    audit = audit_scenarios(build_default_host(config_dir=root / 'config'), cases)
    assert audit['total_scenarios'] == 50
    assert all((not item['unknown_capabilities'] and (not item['unmocked']) and (not item['routing_context_errors']) for item in audit['corpus_failures']))
