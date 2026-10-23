"""Preserve historical corpus/oracles while moving intentional schema metadata."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from hanni.evals.llm_coverage import DEFAULT_COVERAGE_CASES, audit_coverage
from hanni.evals.llm_tools import load_scenarios
from hanni.evals.routing import build_default_host
ROOT = Path(__file__).resolve().parents[2]

def test_raw_digest_contract_migration_changes_only_synthetic_metadata():
    source = ROOT / 'evals/llm_tools/capability_coverage_v2.jsonl'
    target = ROOT / DEFAULT_COVERAGE_CASES
    manifest = json.loads((target.parent / 'capability_coverage_v3_migration.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_sha256']
    assert hashlib.sha256(target.read_bytes()).hexdigest() == manifest['target_sha256']
    before, after = (load_scenarios(source), load_scenarios(target))
    restored = deepcopy(after)
    supplements = {}
    for event in manifest['supplemental_schema_events']:
        supplements.setdefault(event['case_id'], []).append(event['capability_id'])
    changed = []
    for row in restored:
        for capability in supplements.get(row['id'], []):
            assert row['results'].pop(capability)['message'] == 'Synthetic schema probe; no capability was executed.'
        if 'file.read' in row['results']:
            assert row['results']['file.read']['data'].pop('sha256') == ''
            changed.append(row['id'])
    assert restored == before
    assert changed == manifest['changed_cases']

def without_metadata(case, supplements=()):
    value = deepcopy(case)
    value.pop('expected_schema')
    for name in supplements:
        value['results'].pop(name, None)
    for result in value['results'].values():
        result.pop('data')
    return value

def test_versioned_contract_migration_preserves_all_behavioral_oracles_and_v1_bytes():
    old = ROOT / 'evals/llm_tools/capability_coverage_v1.jsonl'
    new = ROOT / 'evals/llm_tools/capability_coverage_v2.jsonl'
    manifest = json.loads((ROOT / 'evals/llm_tools/capability_coverage_v2_migration.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(old.read_bytes()).hexdigest() == manifest['source_sha256']
    assert hashlib.sha256(new.read_bytes()).hexdigest() == manifest['target_sha256']
    before, after = (load_scenarios(old), load_scenarios(new))
    assert len(before) == len(after) == manifest['case_count']
    supplements = {e['case_id']: [e['capability_id']] for e in manifest.get('supplemental_schema_events', [])}
    assert [without_metadata(c) for c in before] == [without_metadata(c, supplements.get(c['id'], ())) for c in after]
    assert all((c['claims'] == [] and c['fixture_scope'] == 'schema_and_menu_only' for c in after))
    assert {c['id'] for c in before if c != next((n for n in after if n['id'] == c['id']))} == {c['case_id'] for c in manifest['changes']}
    assert [(e['case_id'], e['capability_id']) for e in manifest['supplemental_schema_events']] == [('COV-FILE-SEARCH-01', 'file.grep')]
    host = build_default_host()
    try:
        for event in manifest['supplemental_schema_events']:
            row = next((c for c in after if c['id'] == event['case_id']))
            old_row = next((c for c in before if c['id'] == event['case_id']))
            assert set(row['results']) - set(old_row['results']) == {event['capability_id']}
            assert row['results'][event['capability_id']] == event['fixture']
            assert set(event['fixture']['data']) == set(host.registry.get(event['capability_id']).output_schema)
            assert event['fixture']['message'] == 'Synthetic schema probe; no capability was executed.'
            assert row['required_tools'] == ['file.search'] and row['claims'] == []
            assert event['behavioral_expectations_unchanged'] is True
    finally:
        if host.registry.context.reliability:
            host.registry.context.reliability.close()

def test_current_coverage_remains_strict_about_unplanned_schema_drift():
    host = build_default_host()
    try:
        cases = load_scenarios(DEFAULT_COVERAGE_CASES)
        assert audit_coverage(host, cases)['coverage_errors'] == []
        modified = deepcopy(cases[0])
        modified['expected_schema'] = {}
        assert any(('argument schema drift' in e for e in audit_coverage(host, [modified])['coverage_errors']))
        modified = deepcopy(cases[0])
        modified['results'][modified['required_tools'][0]]['data'] = {}
        assert any(('result schema drift' in e for e in audit_coverage(host, [modified])['coverage_errors']))
        assert audit_coverage(host, load_scenarios(ROOT / 'evals/llm_tools/capability_coverage_v1.jsonl'))['coverage_errors']
    finally:
        if host.registry.context.reliability:
            host.registry.context.reliability.close()
