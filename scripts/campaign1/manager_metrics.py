"""Independent aggregate cross-check of private receipts; emits no query/oracle.

Grades are consumed, not reinterpreted here. Semantic review and failure causes
remain the independent verifier's responsibility. Partial runs stay labelled.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

def fraction(passed, eligible):
    return {'passed': passed, 'eligible': eligible, 'percent': 100 * passed / eligible if eligible else None}

def distribution(values):
    values = sorted(values)

    def percentile(q):
        if not values:
            return None
        index = (len(values) - 1) * q
        left, right = (math.floor(index), math.ceil(index))
        return values[left] + (values[right] - values[left]) * (index - left)
    return {'n': len(values), 'mean': mean(values) if values else None, 'p50': percentile(0.5), 'p95': percentile(0.95)}

def usages(call):
    """Retain usage from raw replies even when the original parser rejected them."""
    found = []
    for raw in call.get('raw_responses', []):
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        usage = payload.get('usage')
        if isinstance(usage, dict) and all((isinstance(usage.get(key), int) and (not isinstance(usage[key], bool)) for key in ('prompt_tokens', 'completion_tokens'))):
            found.append(usage)
    if found:
        return found
    usage = call.get('usage') or call.get('parsed', {}).get('usage')
    if isinstance(usage, dict) and all((isinstance(usage.get(key), int) and (not isinstance(usage[key], bool)) for key in ('prompt_tokens', 'completion_tokens'))):
        return [usage]
    return []

def model_totals(records, key):
    calls = [call for record in records for call in record.get(key, [])]
    observed_usage = [item for call in calls for item in usages(call)]
    turn_tokens, missing_turns = ([], 0)
    for record in records:
        turn_calls = record.get(key, [])
        if not turn_calls:
            continue
        if any((not usages(call) for call in turn_calls)):
            missing_turns += 1
            continue
        turn_tokens.append(sum((item.get('total_tokens', item['prompt_tokens'] + item['completion_tokens']) for call in turn_calls for item in usages(call))))
    return {'recorded_client_invocations': len(calls), 'http_attempts': sum((len(call.get('http_attempts', [])) for call in calls)), 'raw_tool_response_bodies': sum((len(call.get('raw_responses', [])) for call in calls)), 'calls_with_usage': sum((bool(usages(call)) for call in calls)), 'calls_missing_usage': sum((not usages(call) for call in calls)), 'usage_records': len(observed_usage), 'prompt_tokens_observed': sum((item['prompt_tokens'] for item in observed_usage)), 'completion_tokens_observed': sum((item['completion_tokens'] for item in observed_usage)), 'total_tokens_observed': sum((item.get('total_tokens', item['prompt_tokens'] + item['completion_tokens']) for item in observed_usage)), 'tokens_per_inference_owner_turn_fully_observed': distribution(turn_tokens), 'inference_owner_turns_missing_complete_usage': missing_turns, 'model_invocation_latency_ms_errors_included': distribution([call['duration_ms'] for call in calls if 'duration_ms' in call]), 'scope': 'Recorded underlying-client invocations; pre-client adaptive admission failures are separate. HTTP/raw/usage evidence independently counted. Prompt totals include repeated context.'}

def grade_totals(rows):
    recall = {}
    for k in ('1', '3', '5', '8'):
        menus = [row['menu'][k] for row in rows]
        recall[k] = fraction(sum((item['covered_groups'] for item in menus)), sum((item['essential_groups'] for item in menus)))
    selection = [row for row in rows if row['proposal_selection_eligible']]
    no_tool = [row for row in rows if row['disposition'] == 'no_tool']
    tool_rows = [row for row in rows if row['disposition'] == 'tool']
    predicates = [check for row in rows for check in row['argument_checks']]
    admitted_fields = [check for predicate in predicates for check in predicate.get('effective_checks', [])]
    raw_fields = [check for predicate in predicates for check in predicate.get('raw_semantic_checks', [])]

    def semantic_fraction(checks):
        return fraction(sum((bool(check.get('literal_pass') or check.get('identity_equivalent')) for check in checks)), len(checks))
    return {'owner_turns': len(rows), 'required_tool_recall_at_k': recall, 'menu_sufficiency_all_turns': fraction(sum((row['menu']['8']['sufficient'] for row in rows)), len(rows)), 'menu_sufficiency_tool_turns': fraction(sum((row['menu']['8']['sufficient'] for row in tool_rows)), len(tool_rows)), 'native_model_selection_when_menu_sufficient': fraction(sum((row['proposal_selection_correct'] is True for row in selection)), len(selection)), 'native_name_selection_when_menu_sufficient': fraction(sum((row.get('proposal_name_selection_correct', row['proposal_selection_correct']) is True for row in selection)), len(selection)), 'raw_proposal_sent_schema_validity': fraction(sum((row['raw_schema_valid'] for row in rows)), sum((row['raw_schema_eligible'] for row in rows))), 'controller_tool_or_disposition_success': fraction(sum((row['tool_choice_pass'] for row in rows)), len(rows)), 'correct_native_no_tool_decisions': fraction(sum((row['tool_choice_pass'] for row in no_tool)), len(no_tool)), 'annotated_effective_argument_checks': fraction(sum((check['passed'] for row in rows for check in row['argument_checks'])), sum((len(row['argument_checks']) for row in rows))), 'annotated_admitted_field_semantics': semantic_fraction(admitted_fields), 'annotated_raw_explicit_field_semantics': semantic_fraction(raw_fields), 'annotated_argument_predicates_missing_expected_tool': sum((check.get('missing_or_denied') == 'missing_expected_tool' for check in predicates)), 'argument_annotation_limitations': sum((bool(check.get('annotation_limitation')) for check in admitted_fields)), 'capability_hallucinated_proposals': fraction(sum((row['unknown_tool_proposals'] for row in rows)), sum((len(row['actual_tool_proposals']) for row in rows))), 'out_of_menu_or_unusable_proposals': sum((row['out_of_menu_or_unusable_proposals'] for row in rows)), 'critical_unauthorized_dispatch_turns': sum((row['critical_safety_fail'] for row in rows)), 'inappropriate_actual_proposals': sum((len(row['annotation_based_inappropriate_proposals']) for row in rows)), 'irrelevant_menu_exposures': sum((len(row['annotation_based_irrelevant_menu_tools']) for row in rows)), 'fixed_argument_conflicts': sum((len(row['fixed_argument_conflicts']) for row in rows)), 'parallel_call_protocol_violations': sum((row['single_call_protocol_violations'] for row in rows)), 'semantic_grounding': 'Independent entailment review required; numeric field matching is not semantic accuracy.'}

def collect(run: Path):
    record_paths = sorted((run / 'cases').glob('*/turn-*.json'))
    records = [json.loads(path.read_text(encoding='utf-8')) for path in record_paths]
    protocol = json.loads((run / 'protocol.json').read_text(encoding='utf-8'))
    summary_path = run / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else None
    result = {'scope': 'Independent manager aggregate; native controller and diagnostic evidence separate', 'planned_cases': protocol['case_count'], 'planned_owner_turns': protocol['planned_owner_turns'], 'recorded_cases': len({record['case_id'] for record in records}), 'recorded_owner_turns': len(records), 'run_finished': summary is not None, 'run_summary': summary, 'controller_errors': sum((bool(record['controller_error']) for record in records)), 'owner_turn_latency_ms_errors_included': distribution([record['controller_elapsed_ms'] for record in records]), 'native_controller': model_totals(records, 'model_calls'), 'separate_diagnostic': model_totals(records, 'diagnostic_model_calls'), 'native_zero_model_invocation_turns': sum((not record['model_calls'] for record in records)), 'diagnostic_probe_errors_by_type': dict(Counter((record['diagnostic_probe']['error']['type'] for record in records if record.get('diagnostic_probe') and record['diagnostic_probe'].get('error')))), 'diagnostic_probe_error_turns_with_zero_recorded_http': sum((bool(record.get('diagnostic_probe') and record['diagnostic_probe'].get('error')) and (not any((call.get('http_attempts') for call in record.get('diagnostic_model_calls', [])))) for record in records))}
    grades_path = run / 'grades-screen.json'
    if grades_path.exists():
        grades = json.loads(grades_path.read_text(encoding='utf-8'))['results']
        result['grades'] = grade_totals(grades)
        index = {(record['case_id'], record['turn']): record for record in records}
        for field in ('family', 'difficulty'):
            values = sorted({record[field] for record in records})
            result['by_' + field] = {value: grade_totals([row for row in grades if index[row['case_id'], row['turn']][field] == value]) for value in values}
        if grades and all(('execution_profile' in row for row in grades)):
            result['by_execution_profile'] = {value: grade_totals([row for row in grades if row['execution_profile'] == value]) for value in sorted({row['execution_profile'] for row in grades})}
        if grades and all(('linguistic_tags' in row for row in grades)):
            result['by_overlapping_linguistic_form'] = {value: grade_totals([row for row in grades if value in row['linguistic_tags']]) for value in sorted({tag for row in grades for tag in row['linguistic_tags']})}
    result['authorized_dispatch_count'] = sum((len(record.get('authorized_handler_dispatches', [])) for record in records))
    preserved = [json.loads(path.read_text(encoding='utf-8')) for path in (run / 'cases').glob('*/closed.json')]
    result['external_identity_checks'] = fraction(sum((row.get('external_original_preserved') is True for row in preserved)), len(preserved))
    semantic_path = run / 'semantic-review.json'
    if semantic_path.exists():
        semantic = json.loads(semantic_path.read_text(encoding='utf-8'))
        reviewed = semantic.get('results', [])
        raw_keys = {(record['case_id'], record['turn']) for record in records}
        review_keys = {(row['case_id'], row['turn']) for row in reviewed}
        raw_hashes = {(record['case_id'], record['turn']): hashlib.sha256(path.read_bytes()).hexdigest() for record, path in zip(records, record_paths)}
        coverage = {'raw_turns': len(records), 'review_rows': len(reviewed), 'unique_review_rows': len(review_keys), 'missing_review_rows': len(raw_keys - review_keys), 'unexpected_review_rows': len(review_keys - raw_keys), 'matching_raw_receipt_hashes': sum((row.get('raw_sha256') == raw_hashes.get((row['case_id'], row['turn'])) for row in reviewed))}
        coverage['complete_review_of_recorded_receipts'] = len(reviewed) == len(records) == len(review_keys) and raw_keys == review_keys and (coverage['matching_raw_receipt_hashes'] == len(records))
        result['independent_semantic_review'] = {'scope': semantic.get('scope'), 'all': semantic.get('all'), 'manager_coverage_and_integrity_check': coverage, 'note': "Verifier's independent full-text entailment review; consumed, not regraded by manager."}
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if not k.startswith('by_')}))
