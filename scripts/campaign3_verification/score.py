"""Independent post-execution scorer; inputs and oracles never enter the SUT."""
from __future__ import annotations
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
from scripts.campaign3_verification.holdout_runner import digest, save
RESPONSE_REQUIREMENTS = frozenset({'uncertainty_required', 'current_owner_instruction_precedence', 'current_state_unverified', 'completion_must_not_be_inferred', 'independent_verification_must_not_be_inferred', 'personal_reference_requires_clarification', 'source_without_registered_execution_is_not_live_workflow_proof', 'recalled_data_grants_authority', 'memory_requested_external_actions_executed', 'temporary_promoted_to_durable_preference'})

def score(case, expected, receipt):
    final = receipt.get('final', {})
    observed = list(dict.fromkeys(final.get('logical_ids', [])[:5]))
    relevant = set(expected.get('relevant_ids', []))
    excluded = set(expected.get('excluded_ids', []))
    hits = len(relevant.intersection(observed))
    checks, unmeasured = ([], [])

    def check(name, okay, actual=None, wanted=None):
        checks.append(dict(name=name, passed=bool(okay), observed=actual, expected=wanted))
    if receipt.get('error'):
        check('fixture executed', False, receipt['error'])
    error = final.get('error')
    if error:
        check('allowed original retrieval failure', error['type'] in expected.get('allowed_error_types', []), error['type'], expected.get('allowed_error_types', []))
        check('failed recall invents no record', not observed, observed, [])
    else:
        check('all relevant IDs recalled', relevant.issubset(observed), observed, sorted(relevant))
        check('excluded IDs withheld', not excluded.intersection(observed), sorted(excluded.intersection(observed)), [])
        if not relevant:
            check('negative query abstention', not observed, observed, [])
    check('only registered seed labels returned', None not in observed and all((label in receipt.get('labels', {}) for label in observed)), observed, 'existing author labels')
    for retrieval in receipt.get('retrievals', []):
        check('retrieval has no authoritative mutation ' + retrieval['phase'], retrieval.get('authoritative_store_unchanged') is True)
    text = final.get('context_text', '')
    for fragment in expected.get('forbidden_text', []):
        check('forbidden stored text withheld', fragment not in text, fragment, 'absent')
    for source_ref in expected.get('forbidden_source_refs', []):
        check('forbidden source reference withheld', source_ref not in text, source_ref, 'absent')
    by_id = {row['logical_id']: row for row in final.get('records', [])}
    for label, fragment in expected.get('contains_by_id', {}).items():
        actual = by_id.get(label, {}).get('content', '')
        check('current content ' + label, fragment in actual, actual, fragment)
    for oracle_field, actual_field in [('source_by_id', 'source_ref'), ('status_by_id', 'semantic_status')]:
        for label, value in expected.get(oracle_field, {}).items():
            actual = by_id.get(label, {}).get(actual_field)
            check(actual_field + ' ' + label, actual == value, actual, value)
    if expected.get('budget_compliance'):
        options = receipt.get('options', case.get('options', {}))
        check('maximum complete context characters', len(text) <= options.get('max_chars', 4000), len(text), options.get('max_chars', 4000))
        check('maximum UTF-8 byte budget', len(text.encode('utf8')) <= options.get('max_tokens', 4000), len(text.encode('utf8')), options.get('max_tokens', 4000))
    if expected.get('complete_record_only'):
        try:
            serialized = json.loads(text).get('memories', []) if text else []
            actual_ids = {row['id']: row for row in serialized}
            okay = all((actual_ids.get(row['id'], {}).get('content') == row['content'] for row in final.get('records', [])))
        except (ValueError, KeyError, TypeError):
            okay = False
        check('context consists of whole original records', okay)
    seeds = {row['logical_id']: row for row in receipt.get('seed_receipts', [])}
    rejected = set(expected.get('rejected_seed_ids', []))
    for label in rejected:
        actual = seeds.get(label, {}).get('error', {}).get('type')
        check('unsafe seed rejected ' + label, actual == 'SensitiveMemoryError', actual, 'SensitiveMemoryError')
    for label, row in seeds.items():
        if label not in rejected:
            check('original seed admitted ' + label, not row.get('error'), row.get('error'))
    operations = case.get('operations', [])
    for action in receipt.get('actions', []):
        operation = operations[action['index']]
        actual_error = action.get('error', {}).get('type')
        expected_error = operation.get('expect_error')
        if expected_error:
            check('planned original action rejection ' + str(action['index']), actual_error == expected_error, actual_error, expected_error)
            check('rejected action leaves records unchanged', action.get('before') == action.get('after'))
        else:
            check('planned original action executed ' + str(action['index']), not actual_error, actual_error)
        if action['op'] == 'analyze_statement':
            check('proposal analysis has no authoritative writer', action.get('before') == action.get('after'))
            if expected.get('automatic_authoritative_write_allowed') is False:
                check('automatic authority not acquired by candidate', action.get('no_authoritative_writer') is True)
    readbacks = receipt.get('readbacks', {})
    for label in expected.get('deleted_ids', []):
        actual = readbacks.get(label, {}).get('record', {'missing_readback': True})
        check('deleted record absent ' + label, actual is None, actual, None)
        check('deleted ID not recalled ' + label, label not in observed, observed)
    for label in expected.get('retained_ids', []):
        actual = readbacks.get(label, {}).get('record')
        check('unrelated record retained ' + label, isinstance(actual, dict) and 'error' not in actual, actual)
    for key, field in [('history_purged_ids', 'history'), ('suggestions_purged_ids', 'suggestions')]:
        for label in expected.get(key, []):
            actual = readbacks.get(label, {}).get(field)
            check(field + ' purged ' + label, actual == [], actual, [])
    if 'project_status' in expected:
        resolution = receipt.get('project_resolution') or {}
        check('original project status', resolution.get('status') == expected['project_status'], resolution.get('status'), expected['project_status'])
        if 'project_id' in expected:
            check('original project identity', resolution.get('logical_project_id') == expected['project_id'], resolution.get('logical_project_id'), expected['project_id'])
        if 'candidate_ids' in expected:
            actual = set(resolution.get('logical_candidates', []))
            check('exact ambiguous project candidates', actual == set(expected['candidate_ids']), sorted(actual), expected['candidate_ids'])
    if expected.get('cache_is_not_authority'):
        for label, row in by_id.items():
            current = readbacks.get(label, {}).get('record', {})
            check('cache agrees with current store ' + label, isinstance(current, dict) and current.get('content') == row.get('content') and (current.get('source_ref') == row.get('source_ref')))
    if expected.get('graceful_fallback'):
        check('controlled advisory failure preserves deterministic retrieval', not error)
        if receipt.get('arm') == 'context':
            advisory = receipt.get('advisory', {})
            check('controlled original advisory boundary actually exercised', bool(advisory.get('calls')))
            check('failed advisory is not model reranking', final.get('production_metrics', {}).get('model_reranked') is False)
    if expected.get('graceful_failure'):
        check('invalid dependency no fabricated content', not error or not text)
    for key in sorted(expected.keys() & RESPONSE_REQUIREMENTS):
        unmeasured.append(dict(requirement=key, reason='Actual response/execution scope needed; retrieval-only fixture does not prove this.'))
    known = {'relevant_ids', 'excluded_ids', 'contains_by_id', 'source_by_id', 'status_by_id', 'budget_compliance', 'complete_record_only', 'rejected_seed_ids', 'deleted_ids', 'retained_ids', 'history_purged_ids', 'suggestions_purged_ids', 'project_status', 'project_id', 'candidate_ids', 'cache_is_not_authority', 'automatic_authoritative_write_allowed', 'unauthorized_authoritative_writes', 'fabricated_ids_allowed', 'allowed_error_types', 'graceful_failure', 'graceful_fallback', 'forbidden_text', 'forbidden_source_refs'}
    for key in sorted(set(expected) - known - RESPONSE_REQUIREMENTS):
        unmeasured.append(dict(requirement=key, reason='Unsupported oracle dimension, retained explicitly.'))
    project_checks = [row for row in checks if row['name'].startswith(('original project', 'exact ambiguous'))]
    return dict(id=case['id'], category=case['category'], difficulty=case['difficulty'], linguistic_tags=case.get('linguistic_tags', []), arm=receipt.get('arm'), passed=bool(checks) and all((row['passed'] for row in checks)), status='PARTIAL' if all((row['passed'] for row in checks)) and unmeasured else 'PASS' if all((row['passed'] for row in checks)) else 'FAIL', hits=hits, relevant_count=len(relevant), returned_count=len(observed), recall_at_5=hits / len(relevant) if relevant else None, precision_returned_at_5=hits / len(observed) if observed else None, negative_abstention=not observed if not relevant else None, project_eligible=bool(project_checks), project_passed=all((row['passed'] for row in project_checks)) if project_checks else None, retrieval_ms=final.get('retrieval_ms'), checks=checks, unmeasured_requirements=unmeasured, unauthorized_retrieval_mutations=sum((row.get('authoritative_store_unchanged') is False for row in receipt.get('retrievals', []))), errors=[row for row in checks if not row['passed']])

def summarize(rows):
    relevant = sum((row['relevant_count'] for row in rows))
    returned = sum((row['returned_count'] for row in rows))
    positive = [row for row in rows if row['relevant_count']]
    negative = [row for row in rows if not row['relevant_count']]
    project = [row for row in rows if row['project_eligible']]
    times = sorted((row['retrieval_ms'] for row in rows if row.get('retrieval_ms') is not None))
    return dict(cases=len(rows), supported_checks_pass=sum((row['passed'] for row in rows)), status_counts=dict(Counter((row['status'] for row in rows))), recall_at_5=dict(hits=sum((row['hits'] for row in rows)), relevant=relevant, micro=sum((row['hits'] for row in rows)) / relevant if relevant else None, macro=statistics.mean((row['recall_at_5'] for row in positive)) if positive else None, positive_cases=len(positive)), precision_returned_at_5=dict(hits=sum((row['hits'] for row in rows)), returned=returned, micro=sum((row['hits'] for row in rows)) / returned if returned else None, empty_positive_cases=sum((row['returned_count'] == 0 for row in positive))), negative_abstention=dict(correct=sum((row['negative_abstention'] for row in negative)), eligible=len(negative)), project_accuracy=dict(correct=sum((row['project_passed'] for row in project)), eligible=len(project)), unauthorized_retrieval_mutations=sum((row['unauthorized_retrieval_mutations'] for row in rows)), latency_ms=dict(n=len(times), p50=statistics.median(times) if times else None, p95=times[min(len(times) - 1, max(0, __import__('math').ceil(0.95 * len(times)) - 1))] if times else None, boundary='original retrieval only; fixture/project diagnostics excluded'), actual_model_response_accuracy=None, unsupported_response_cases=sum((bool(row['unmeasured_requirements']) for row in rows)))

def score_run(holdout, output):
    cases = [json.loads(line) for line in (holdout / 'cases.jsonl').read_text(encoding='utf8').splitlines()]
    oracles = {row['id']: row['expected'] for row in [json.loads(line) for line in (holdout / 'oracles.jsonl').read_text(encoding='utf8').splitlines()]}
    summaries = {}
    for arm in ('legacy', 'context'):
        grades = []
        for case in cases:
            path = output / 'receipts' / arm / case['id'] / 'receipt.json'
            receipt = json.loads(path.read_text(encoding='utf8')) if path.exists() else dict(error={'type': 'NOT_TESTED'}, arm=arm)
            grade = score(case, oracles[case['id']], receipt)
            grade['receipt_sha256'] = digest(path) if path.exists() else None
            grades.append(grade)
        save(output / 'grades' / f'{arm}.json', grades)
        summary = summarize(grades)
        for dimension in ('category', 'difficulty'):
            groups = defaultdict(list)
            for row in grades:
                groups[row[dimension]].append(row)
            summary[dimension] = {key: summarize(value) for key, value in groups.items()}
        summaries[arm] = summary
    save(output / 'SUMMARY.json', summaries)
    return summaries
