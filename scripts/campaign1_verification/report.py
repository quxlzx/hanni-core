"""Durable redacted aggregates and capability accounting, no model dispatch."""
import argparse, collections, hashlib, json
from pathlib import Path

def load(path):
    return json.loads(path.read_text(encoding='utf8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def report(run, corpus, fixture_source, output):
    run = run.resolve()
    document = load(corpus) if corpus.suffix == '.json' else None
    cases = document['cases'] if document else [json.loads(x) for x in corpus.read_text(encoding='utf8').splitlines() if x.strip()]
    byid = {c['id']: c for c in cases}
    grades = load(run / 'grades-screen.json')
    semantic = load(run / 'semantic-review.json')
    aggregate = load(run / 'aggregate.json')
    graded = {(g['case_id'], g['turn']): g for g in grades['results']}
    review = {(r['case_id'], r['turn']): r for r in semantic['results']}
    paths = sorted((run / 'cases').glob('*/turn-*.json'))
    raw = {(load(p)['case_id'], load(p)['turn']): (p, load(p)) for p in paths}
    assert set(raw) == set(graded) == set(review)
    for key, (path, row) in raw.items():
        assert sha(path) == review[key]['raw_sha256']
    base = set(load(fixture_source)['tools'])
    matrix = {name: collections.Counter() for name in base}
    events = {}
    case_contracts = {}

    def add(name, field, n=1):
        if name not in matrix:
            matrix[name] = collections.Counter()
        matrix[name][field] += n
    for case in cases:
        for name in set(case.get('targeted_tools', [])):
            add(name, 'case_level_targeted_cases')
    for key, (path, row) in raw.items():
        case = byid[key[0]]
        oracle = (case['expected'].get('turns') or [case['expected']])[key[1]]
        g = graded[key]
        s = review[key]
        essential = {name for group in oracle.get('menu', {}).get('essential_groups', []) for name in group} | set(oracle.get('required_tools', []))
        for name in essential:
            add(name, 'required_or_alternative_annotation_turns')
        if oracle['disposition'] == 'blocked':
            for name in set(case.get('targeted_tools', [])):
                add(name, 'blocked_intended_turns')
        for name in set(oracle.get('forbidden_tools', [])):
            add(name, 'prohibited_annotation_turns')
        for name in set(g['executed']):
            add(name, 'host_call_turns')
        for name in {t['capability_id'] for t in (row.get('primary_original_menu') or {}).get('tools', [])}:
            add(name, 'original_primary_menu_offered_turns')
        for proposal in g['actual_tool_proposals']:
            if proposal.get('globally_registered_tool'):
                add(proposal['globally_registered_tool'], 'native_canonical_or_alias_proposals')
                add(proposal['globally_registered_tool'], 'native_in_sent_menu_proposals' if proposal['classification'] == 'in_sent_menu_canonical_wire' else 'native_wrong_wire_or_outside_menu_proposals')
        for dispatch in row.get('authorized_handler_dispatches', []):
            add(dispatch['tool'], 'post_original_gate_dispatches')
        for call in row['tool_calls']:
            name = call['tool']
            result = call.get('result', {})
            add(name, 'successful_returns' if result.get('ok') else 'failed_returns_or_calls')
            if result.get('verification'):
                add(name, 'return_verification_' + result['verification'].get('status', 'UNKNOWN'))
        for name in {t['tool'] for t in row['tool_calls'] if t.get('result', {}).get('ok')}:
            if s['grounding'] == 'PASS':
                add(name, 'successful_receipt_turns_with_fully_grounded_response')
            if s['accurate_complete_response']:
                add(name, 'successful_receipt_turns_with_accurate_complete_response')
        if path.parent not in events:
            events[path.parent] = [json.loads(x) for x in (path.parent / 'events.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    for case_events in events.values():
        for event in case_events:
            if event.get('kind') == 'fixture_handler':
                add(event['tool'], 'handler_evidence_' + event.get('evidence_kind', 'unknown'))
    capability_rows = []
    for name, counts in sorted(matrix.items()):
        if counts['post_original_gate_dispatches']:
            status = 'bounded_handler_dispatch_observed'
        elif counts['native_in_sent_menu_proposals']:
            status = 'native_proposal_without_authorized_dispatch'
        elif counts['original_primary_menu_offered_turns']:
            status = 'offered_without_native_proposal_or_dispatch'
        elif counts['blocked_intended_turns']:
            status = 'intended_policy_blocked_not_executed'
        elif counts['case_level_targeted_cases'] or counts['required_or_alternative_annotation_turns']:
            status = 'intended_not_retrieved_or_inferred'
        else:
            status = 'inventoried_only_not_intended_in_this_corpus'
        capability_rows.append({'capability': name, 'base_inventory': name in base, 'status': status, **dict(counts)})
    failure_rows = [{k: r.get(k) for k in ['case_id', 'turn', 'family', 'difficulty', 'execution_profile', 'linguistic_tags', 'grounding', 'task_coverage_complete', 'accurate_complete_response', 'primary_failure_category', 'secondary_failure_category', 'reason', 'raw_sha256', 'native_http_attempts', 'diagnostic_http_attempts', 'reference_source_limitation']} for r in semantic['results'] if not r['accurate_complete_response']]
    output.mkdir(parents=True, exist_ok=True)
    result = {'scope': 'Fixed authored corpus and actual original-controller receipts; no query/answer/oracle content. Whole-response success with a tool receipt is not per-tool causal attribution or proof of foreign physical execution.', 'corpus_sha256': sha(corpus), 'fixture_source_sha256': sha(fixture_source), 'graded_receipts': len(raw), 'planned_owner_turns': sum((len(c.get('turns') or [c['query']]) for c in cases)), 'all_graded_review_receipt_hashes_match': True, 'base_inventory': len(base), 'runtime_additional_contracts_observed': len(set(matrix) - base), 'capability_matrix_scope': 'Required alternatives are annotations, not a demand to execute every equivalent. Prohibitions differ from blocked intended tasks. Module-local controlled-clock/process handlers are original semantics over controlled observations, not real host facts. Untested/policy-ineligible capabilities stay explicit.', 'capabilities': capability_rows, 'actual_inference': aggregate['all'], 'graded_metrics': aggregate['metrics'], 'full_response_review': {k: v for k, v in semantic.items() if k != 'results'}, 'failure_turns': len(failure_rows), 'case_preparation_failures': aggregate.get('case_preparation_failures', [])}
    (output / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    (output / 'failures.jsonl').write_text(''.join((json.dumps(r, ensure_ascii=False) + '\n' for r in failure_rows)), encoding='utf8')
    print(json.dumps({'graded_receipts': len(raw), 'base_inventory': len(base), 'required_annotated_capabilities': sum((bool(x.get('required_or_alternative_annotation_turns')) for x in capability_rows)), 'native_proposed_capabilities': sum((bool(x.get('native_in_sent_menu_proposals')) for x in capability_rows)), 'dispatched_capabilities': sum((bool(x.get('post_original_gate_dispatches')) for x in capability_rows)), 'failure_turns': len(failure_rows), 'review_integrity': True, 'output': str(output)}))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('run', 'corpus', 'fixture-source', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    report(a.run, a.corpus, a.fixture_source, a.output)
if __name__ == '__main__':
    main()
