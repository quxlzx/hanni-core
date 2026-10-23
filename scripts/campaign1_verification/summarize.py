"""Aggregate durable actual receipts, explicit missing usage and denominators."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import math

def quantile(values, q):
    values = sorted((v for v in values if isinstance(v, (int, float)) and math.isfinite(v)))
    if not values:
        return None
    position = (len(values) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)

def distribution(values):
    clean = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return {'n': len(clean), 'p50': quantile(clean, 0.5), 'p95': quantile(clean, 0.95), 'min': min(clean) if clean else None, 'max': max(clean) if clean else None}

def usage_for(call):
    raw = [t.get('usage') for t in call.get('raw_response_telemetry', []) if isinstance(t.get('usage'), dict)]
    return raw[-1] if raw else call.get('usage') or call.get('parsed', {}).get('usage') or None

def perf_for(call):
    raw = [t.get('performance') for t in call.get('raw_response_telemetry', []) if isinstance(t.get('performance'), dict)]
    return raw[-1] if raw else call.get('performance', {})

def group(records):
    native = [c for r in records for c in r.get('model_calls', [])]
    diagnostic = [c for r in records for c in r.get('diagnostic_model_calls', [])]
    output = {'owner_turns': len(records), 'cases': len({r['case_id'] for r in records}), 'controller_error_turns': sum((bool(r.get('controller_error')) for r in records)), 'actual_model_evaluated_cases': len({r['case_id'] for r in records if any((c.get('http_attempts') for c in r.get('model_calls', []) + r.get('diagnostic_model_calls', [])))}), 'native_menu_available_turns': sum((r.get('native_menu_available', bool(r.get('original_routes'))) for r in records)), 'controller_latency_ms': distribution([r.get('controller_elapsed_ms') for r in records]), 'diagnostic_latency_ms': distribution([r.get('diagnostic_elapsed_ms') for r in records]), 'controller_plus_diagnostic_ms': distribution([r.get('elapsed_ms') for r in records]), 'handler_dispatches': sum((len(r.get('authorized_handler_dispatches', [])) for r in records))}
    for label, calls in [('native', native), ('diagnostic', diagnostic)]:
        usages = [usage_for(c) for c in calls]
        perfs = [perf_for(c) for c in calls]
        output[label] = {'client_calls': len(calls), 'http_attempts': sum((len(c.get('http_attempts', [])) for c in calls)), 'raw_nonstream_responses': sum((len(c.get('raw_responses', [])) for c in calls)), 'errors': sum((bool(c.get('error')) for c in calls)), 'usage_present_calls': sum((u is not None for u in usages)), 'usage_missing_calls': sum((u is None for u in usages)), 'latency_ms': distribution([c.get('duration_ms') for c in calls]), 'ttft_ms': distribution([p.get('ttft_ms') for p in perfs]), 'generation_tps': distribution([p.get('generation_tps') for p in perfs]), 'prompt_tps': distribution([p.get('prompt_tps') for p in perfs]), 'reported_tokens': {field: {'n': sum((isinstance(u, dict) and field in u for u in usages)), 'total': sum((u[field] for u in usages if isinstance(u, dict) and isinstance(u.get(field), int))) if any((isinstance(u, dict) and isinstance(u.get(field), int) for u in usages)) else None} for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')}}
    return output

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    a = p.parse_args()
    records = [json.loads(p.read_text(encoding='utf8')) for p in sorted((a.run / 'cases').glob('*/turn-*.json'))]
    protocol = json.loads((a.run / 'protocol.json').read_text(encoding='utf8'))
    result = {'scope': 'descriptive fixed-corpus counts; shared existing endpoint, sequential caches; no population confidence interval', 'planned_cases': protocol['case_count'], 'planned_owner_turns': protocol['planned_owner_turns'], 'generation_profile': protocol['model_profile'], 'all': group(records), 'by_family': {}, 'by_difficulty': {}, 'by_profile': {}}
    for field, key in [('family', 'by_family'), ('difficulty', 'by_difficulty')]:
        buckets = defaultdict(list)
        for r in records:
            buckets[r[field]].append(r)
        result[key] = {k: group(v) for k, v in buckets.items()}
    profiles = defaultdict(list)
    for r in records:
        configuration = json.loads((a.run / 'cases' / r['case_id'] / 'configuration.json').read_text(encoding='utf8'))
        profiles[configuration['profile']].append(r)
    result['by_profile'] = {k: group(v) for k, v in profiles.items()}
    grade_path = a.run / 'grades-screen.json'
    if grade_path.exists():
        grades = json.loads(grade_path.read_text(encoding='utf8'))['results']
        n = len(grades)
        eligible = [g for g in grades if g['proposal_selection_eligible']]
        arguments = [a for g in grades for a in g['argument_checks']]
        admitted_arguments = [a for a in arguments if a.get('admitted_calls', 0)]
        effective_checks = [c for a in arguments for c in a.get('effective_checks', [])]
        raw_checks = [c for a in arguments for c in a.get('raw_semantic_checks', [])]
        result['metrics'] = {'graded_owner_turns': n, 'conditional_selection': {'denominator': len(eligible), 'correct': sum((g['proposal_selection_correct'] is True for g in eligible))}, 'raw_schema': {'denominator': sum((g['raw_schema_eligible'] for g in grades)), 'valid': sum((g['raw_schema_valid'] for g in grades))}, 'required_execution_coverage_or_disposition': {'denominator': n, 'passed': sum((g['tool_choice_pass'] for g in grades)), 'limitation': 'successful ToolResult/authority disposition does not alone prove complete task or grounded response'}, 'conditional_name_selection': {'denominator': len(eligible), 'correct': sum((g.get('proposal_name_selection_correct') is True for g in eligible))}, 'semantic_argument_annotations': {'frozen_predicates': len(arguments), 'admitted_predicates': len(admitted_arguments), 'missing_expected_tool_predicates': sum((a.get('missing_or_denied') == 'missing_expected_tool' for a in arguments)), 'preparation_denied_predicates': sum((a.get('missing_or_denied') == 'original_preparation_denied' for a in arguments)), 'literal_predicate_passes': sum((a['passed'] for a in arguments)), 'admitted_field_checks': len(effective_checks), 'admitted_literal_passes': sum((c['literal_pass'] for c in effective_checks)), 'admitted_identity_equivalent_passes': sum((c['identity_equivalent'] for c in effective_checks)), 'annotation_limitation_checks': sum((c.get('annotation_limitation') is not None for c in effective_checks)), 'raw_explicit_field_checks': len(raw_checks), 'raw_literal_passes': sum((c['literal_pass'] for c in raw_checks)), 'raw_identity_equivalent_passes': sum((c['identity_equivalent'] for c in raw_checks)), 'scope': 'Annotated fields only; raw generated arguments and original admitted/defaulted fields have distinct denominators. No blanket semantic validity claim for unannotated arguments.'}, 'critical_safety_failures': sum((g['critical_safety_fail'] for g in grades)), 'failure_categories': dict(Counter((c for g in grades for c in g['failure_categories']))), 'full_grounded_response_accuracy': 'PENDING independent semantic review; automatic screen is not entailment accuracy', 'menu': {str(k): {'eligible': sum((g['menu'][str(k)]['recall'] is not None for g in grades)), 'group_hits': sum((g['menu'][str(k)]['covered_groups'] for g in grades)), 'group_requirements': sum((g['menu'][str(k)]['essential_groups'] for g in grades)), 'sufficient': sum((g['menu'][str(k)]['sufficient'] for g in grades)), 'annotated_sufficient': sum((g['menu'][str(k)]['sufficient'] for g in grades if g['menu'][str(k)]['recall'] is not None)), 'scope': 'sufficient includes cases with no essential groups; annotated_sufficient restricts to authored nonempty essential groups'} for k in (1, 3, 5, 8)}}
        semantic_path = a.run / 'semantic-review.json'
        if semantic_path.exists():
            semantic = json.loads(semantic_path.read_text(encoding='utf8'))
            assert {(r['case_id'], r['turn']) for r in semantic['results']} == {(g['case_id'], g['turn']) for g in grades}
            result['independent_semantic_review'] = {k: v for k, v in semantic.items() if k != 'results'}
            result['metrics']['full_grounded_response_accuracy'] = {'eligible': semantic['all']['grounded_eligible'], 'passed': semantic['all']['grounded_pass'], 'failed': semantic['all']['grounded_fail'], 'not_applicable': semantic['all']['grounding_not_applicable'], 'accurate_complete_responses': semantic['all']['accurate_complete_response'], 'unconditional_owner_turns': n, 'reference_source_limitation_turns': semantic['all']['reference_source_limitations'], 'scope': 'All actual controller responses independently reviewed; correct partial grounding does not imply complete task. Controlled source failures retained.'}
    failures = a.run / 'failures.json'
    result['case_preparation_failures'] = json.loads(failures.read_text(encoding='utf8')) if failures.exists() else []
    result['unrecorded_planned_owner_turns'] = protocol['planned_owner_turns'] - len(records)
    (a.run / 'aggregate.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf8')
    print(json.dumps({'planned_cases': result['planned_cases'], 'all': result['all'], 'metrics': result.get('metrics')}, indent=2))
if __name__ == '__main__':
    main()
