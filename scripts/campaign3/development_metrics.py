"""Derive deterministic retrieval metrics from immutable synthetic receipts."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
ROOT = Path(__file__).resolve().parents[2]

def quantile(values, p):
    if not values:
        return None
    rows = sorted(values)
    index = (len(rows) - 1) * p
    low = int(index)
    high = min(low + 1, len(rows) - 1)
    return round(rows[low] + (rows[high] - rows[low]) * (index - low), 4)

def summarize(directory, kind):
    paths = sorted((Path(directory) / 'receipts' / kind).glob('*.json'))
    receipts = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
    primary = [row['contexts'][-1] for row in receipts if row.get('contexts')]
    positive = [row for row in primary if row['scores']['relevant_count']]
    negative = [row for row in primary if not row['scores']['relevant_count']]
    source_variants = defaultdict(set)
    for row in receipts:
        for module, digest in row.get('source_hashes', {}).items():
            source_variants[module].add(digest)
    latency = [row['retrieval_ms'] for row in primary]
    lifecycle_rows = [row for row in receipts if any((action['op'] in {'correct', 'delete', 'restart', 'external_update', 'tamper', 'drop_index', 'corrupt_database'} for action in row.get('actions', [])))]
    contexts = [len(row.get('context_text', '').encode('utf-8')) for row in primary]
    checks = Counter((check['check'].split(' for ')[0] for row in primary for check in row['scores']['checks'] if not check['passed']))
    action_failures = Counter((key for row in receipts for action in row.get('actions', []) for key, value in action.items() if key.startswith('assertion_') and (not value)))
    project_rows = [row for row in primary if 'project_status' in row['expected']]
    project_correct = sum((all((check['passed'] for check in row['scores']['checks'] if check['check'] in {'project_status', 'project_id'})) for row in project_rows))
    relevant_total = sum((row['scores']['relevant_count'] for row in positive))
    hits = sum((row['scores']['hits'] for row in primary))
    returned = sum((row['scores']['returned_count'] for row in primary))
    returning = [row for row in primary if row['scores']['returned_count']]
    out = {'cases': len(receipts), 'case_passed': sum((row['passed'] for row in receipts)), 'case_failed': sum((not row['passed'] for row in receipts)), 'primary_retrievals': len(primary), 'warm_retrievals': sum((len(row.get('contexts', [])) - 1 for row in receipts if row.get('contexts'))), 'positive_queries': len(positive), 'negative_queries': len(negative), 'relevant_memory_ids': relevant_total, 'relevant_hits_at_5': hits, 'recall_at_5_micro': hits / relevant_total if relevant_total else None, 'recall_at_5_macro_positive_queries': statistics.mean((row['scores']['recall_at_5'] for row in positive)) if positive else None, 'precision_returned_at_5_micro': hits / returned if returned else None, 'returned_memory_ids_at_5': returned, 'precision_returned_at_5_macro_nonempty_queries': statistics.mean((row['scores']['precision_returned_at_5'] for row in returning)) if returning else None, 'nonempty_precision_queries': len(returning), 'precision_fixed_5_all_queries': hits / (5 * len(primary)) if primary else None, 'negative_abstention_error_free': sum((not row.get('logical_ids') and (not row.get('error')) for row in negative)), 'negative_query_errors': sum((bool(row.get('error')) for row in negative)), 'retrieval_errors': sum((bool(row.get('error')) for row in primary)), 'harness_errors': sum(('harness_error' in row for row in receipts)), 'forbidden_memory_occurrences': sum((len(row['scores']['forbidden_ids']) for row in primary)), 'unrelated_memory_occurrences': sum((len(row['scores']['irrelevant_ids']) for row in primary)), 'original_project_resolver_diagnostic': {'correct': project_correct, 'queries': len(project_rows), 'accuracy': project_correct / len(project_rows) if project_rows else None, 'provenance': 'separate original workspace resolver; explicit retriever scope is NOT native project selection'}, 'retrieval_latency_ms': {'p50': quantile(latency, 0.5), 'p95': quantile(latency, 0.95), 'samples': len(latency), 'includes_errors': True, 'quantile_method': 'linear interpolation'}, 'context_utf8_byte_upper_bound': {'mean': statistics.mean(contexts) if contexts else None, 'max': max(contexts, default=0), 'samples': len(contexts), 'tokenizer': 'no exact token measurement'}, 'failed_primary_assertions': dict(checks), 'failed_action_assertions': dict(action_failures), 'lifecycle': {'scenarios': len(lifecycle_rows), 'whole_scenario_passed': sum((row['passed'] for row in lifecycle_rows)), 'operation_counts': dict(Counter((action['op'] for row in receipts for action in row.get('actions', []) if action['op'] != 'remember'))), 'operation_assertions': sum((sum((key.startswith('assertion_') for key in action)) for row in receipts for action in row.get('actions', []))), 'failed_operation_assertions': sum(action_failures.values())}, 'source_hash_variants': {name: sorted(hashes) for name, hashes in source_variants.items()}, 'advisory_provenance': {'arms': 'legacy has no advisory ranking path; context uses controlled original-client faults only', 'cases_with_original_http_boundary_calls': sum((bool(row.get('advisory', {}).get('calls')) for row in receipts)), 'recorded_boundary_calls': sum((len(row.get('advisory', {}).get('calls', [])) for row in receipts))}, 'model_claim_metrics': {'source_grounded_factual_accuracy': None, 'incorrect_memory_claims': None, 'reason': 'not measured by deterministic retrieval; manager owns actual model A/B'}}
    for category in dict.fromkeys((row['category'] for row in receipts)):
        rows = [row for row in receipts if row['category'] == category]
        final = [row['contexts'][-1] for row in rows if row.get('contexts')]
        relevant = sum((row['scores']['relevant_count'] for row in final))
        correct = sum((row['scores']['hits'] for row in final))
        returned = sum((row['scores']['returned_count'] for row in final))
        out.setdefault('categories', {})[category] = {'cases': len(rows), 'passed': sum((row['passed'] for row in rows)), 'positive_queries': sum((bool(row['scores']['relevant_count']) for row in final)), 'negative_queries': sum((not row['scores']['relevant_count'] for row in final)), 'relevant_memory_ids': relevant, 'hits_at_5': correct, 'returned_memory_ids': returned, 'recall_micro': correct / relevant if relevant else None, 'returned_precision_micro': correct / returned if returned else None}
    return (out, receipts)

def compare(baseline, candidate):
    result = {'corpus_sha256': hashlib.sha256((ROOT / 'evals/memory/campaign3_development.jsonl').read_bytes()).hexdigest(), 'metric_scope': 'primary final retrieval per case; warm calls separately retained; errors never treated as correct negative abstention', 'baseline_revision': 'b1ec1bb archived complete src', 'candidate_directory': str(candidate)}
    for kind in ('legacy', 'context'):
        before, before_raw = summarize(baseline, kind)
        after, after_raw = summarize(candidate, kind)
        old = {row['id']: row for row in before_raw}
        new = {row['id']: row for row in after_raw}
        result[kind] = {'baseline': before, 'candidate': after, 'new_case_regressions': [identity for identity, row in old.items() if row['passed'] and (not new[identity]['passed'])], 'repaired_cases': [identity for identity, row in old.items() if not row['passed'] and new[identity]['passed']], 'still_failing_cases': [identity for identity, row in new.items() if not row['passed']]}
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = compare(args.baseline, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    for kind in ('legacy', 'context'):
        print(json.dumps({'kind': kind, **{stage: {key: data[kind][stage][key] for key in ('case_passed', 'recall_at_5_micro', 'recall_at_5_macro_positive_queries', 'precision_returned_at_5_micro', 'negative_abstention_error_free', 'original_project_resolver_diagnostic', 'retrieval_latency_ms')} for stage in ('baseline', 'candidate')}, 'regressions': data[kind]['new_case_regressions']}, ensure_ascii=False), flush=True)
