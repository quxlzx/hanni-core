"""Independent frozen-oracle scoring; never imported by the execution boundary."""
from __future__ import annotations
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
from .executor import digest, durable

def concurrency(intervals, kind):
    events = []
    for row in intervals:
        if row['kind'] == kind and row.get('left') is not None:
            events.extend([(row['entered'], 1), (row['left'], -1)])
    count = maximum = 0
    for _, delta in sorted(events, key=lambda row: (row[0], row[1])):
        count += delta
        maximum = max(maximum, count)
    return maximum

def evaluate(receipt, expected):
    """Every authored assertion receives a result; unsupported fields fail closed."""
    workflow = receipt.get('workflow') or {}
    steps = {row['step_id']: row for row in workflow.get('steps', [])}
    invocations = workflow.get('invocations', [])
    controls = receipt.get('controls', [])
    effects = receipt.get('effect_ledger', [])
    writes = [row for row in effects if row.get('actual_effect') is True]
    files = receipt.get('files', {})
    artifact_steps = [row for row in steps.values() if row.get('kind') == 'artifact']
    artifacts = [row for name, row in files.items() if '/artifacts/' in '/' + name]
    checks = {}
    annotations = {}

    def exists_file(name):
        return files.get(name) or next((row for key, row in files.items() if key.endswith('/' + name)), None)

    def text(name):
        value = exists_file(name)
        return value.get('text') if value else None

    def result(key, actual, good):
        checks[key] = {'passed': bool(good), 'observed': actual}
    for key, value in expected.items():
        if key in {'semantic_goal_quality', 'inflight_read_may_finish', 'source_file'}:
            annotations[key] = {'scope': 'authored annotation; not a measured quality guarantee', 'value': value}
        elif key == 'stop_status':
            result(key, workflow.get('status'), workflow.get('status') == value)
        elif key == 'writes':
            result(key, len(writes), len(writes) == value)
        elif key == 'handler_calls':
            result(key, len(receipt.get('handler_entries', [])), len(receipt.get('handler_entries', [])) == value)
        elif key in {'verified_steps', 'failed_steps', 'unverified_steps'}:
            status = key.removesuffix('_steps')
            actual = {name: steps.get(name, {}).get('status') for name in value}
            result(key, actual, all((actual[name] == status for name in value)))
        elif key == 'attempts_by_step':
            actual = {name: steps.get(name, {}).get('attempts') for name in value}
            result(key, actual, actual == value)
        elif key == 'retained_files':
            result(key, {name: exists_file(name) is not None for name in value}, all((exists_file(name) for name in value)))
        elif key == 'artifact_equals_source':
            original = text(value)
            result(key, {'artifacts': len(artifacts), 'source_present': original is not None}, bool(artifacts) and original is not None and all((row['text'] == original for row in artifacts)))
        elif key == 'artifact_files':
            actual = {Path(row.get('resolved_arguments', {}).get('path', '')).name for row in artifact_steps}
            result(key, sorted(actual), set(value).issubset(actual))
        elif key == 'copied_file':
            source = expected.get('source_file')
            result(key, {'source_present': exists_file(source) is not None, 'copy_present': exists_file(value) is not None}, exists_file(source) is not None and exists_file(value) is not None and (text(value) == text(source)))
        elif key == 'dispatch_order':
            actual = [row['step_id'] for row in invocations]
            result(key, actual, actual == value)
        elif key == 'forbidden_capabilities':
            actual = [row['capability_id'] for row in receipt.get('handler_entries', []) if row['capability_id'] in value]
            result(key, actual, not actual)
        elif key == 'unique_invocation_ids':
            actual = [row['invocation_id'] for row in invocations]
            result(key, len(actual), len(actual) == len(set(actual)))
        elif key in {'no_completed_step_replay', 'write_replay_forbidden'}:
            counts = Counter((row['step_id'] for row in invocations if key == 'no_completed_step_replay' or row['write']))
            result(key, dict(counts), all((count <= 1 for count in counts.values())))
        elif key == 'uncertain_invocation_required':
            actual = [row['invocation_id'] for row in invocations if row['state'] == 'uncertain']
            result(key, len(actual), bool(actual))
        elif key == 'control_rejection_required':
            actual = [row for row in controls if row['ok'] is False]
            result(key, len(actual), bool(actual))
        elif key in {'rejected_approval_required', 'revoked_approval_required'}:
            status = 'rejected' if key.startswith('rejected') else 'revoked'
            actual = [row for row in workflow.get('approvals', []) if row['state'] == status]
            result(key, len(actual), bool(actual))
        elif key == 'approval_wait_has_no_effect':
            actual = [row for row in controls if row['operation'] == 'observe_no_dispatch' and row['at'] == 'waiting_approval']
            result(key, len(actual), bool(actual) and all((row.get('observed_effects') == 0 and row.get('no_active_dispatch') for row in actual)))
        elif key == 'persisted_pause_required':
            actual = [row for row in controls if row.get('before_status') == 'paused' or row.get('after_status') == 'paused']
            result(key, len(actual), bool(actual))
        elif key == 'durable_checkpoint_readback_required':
            actual = [row for row in controls if row['operation'] == 'reopen_store_readback' and row.get('readback_equal')]
            recovery = receipt.get('initial_recovery_snapshot')
            result(key, {'reopened_readbacks': len(actual), 'new_process_recovery': bool(recovery)}, bool(actual) or bool(recovery and recovery.get('checkpoints')))
        elif key == 'checkpoint_revision_monotonic':
            actual = [row['sequence'] for row in workflow.get('checkpoints', [])]
            result(key, actual, bool(actual) and actual == sorted(set(actual)))
        elif key == 'durable_request_dedup_required':
            actual = [row for row in controls if row['operation'] == 'replay_submit_same_id']
            result(key, len(actual), bool(actual) and all((row.get('same_workflow') and row['ok'] for row in actual)))
        elif key == 'workflow_count':
            result(key, receipt.get('workflow_count'), receipt.get('workflow_count') == value)
        elif key in {'owned_process_failure_required', 'new_process_identity_required'}:
            processes = receipt.get('processes', [])
            observed = len(processes) == 2 and processes[0]['exit_code'] == 83 and (processes[1]['exit_code'] == 0)
            if key == 'new_process_identity_required':
                observed = observed and processes[0]['identity']['pid'] != processes[1]['identity']['pid']
            result(key, len(processes), observed and all((row['parent_verified'] for row in processes)) and (receipt.get('owned_children_closed') is True))
        elif key == 'no_automatic_resume':
            actual = (receipt.get('initial_recovery_snapshot') or {}).get('status')
            result(key, actual, actual in {'paused', 'blocked'})
        elif key in {'max_concurrent_reads', 'max_concurrent_writes', 'observed_read_overlap_required'}:
            kind = 'write' if key == 'max_concurrent_writes' else 'read'
            actual = concurrency(receipt.get('io_intervals', []), kind)
            good = actual >= 2 if key == 'observed_read_overlap_required' else actual == value if kind == 'read' else actual <= value
            result(key, actual, good)
        elif key == 'all_required_steps_verified':
            actual = bool(steps) and all((row['status'] == 'verified' for row in steps.values() if row['required']))
            result(key, actual, actual == value)
        elif key == 'artifact_verified_required':
            actual = bool(artifact_steps) and all((row.get('status') == 'verified' and (row.get('verification') or {}).get('status') == 'VERIFIED' for row in artifact_steps))
            result(key, actual, actual == value)
        elif key in {'no_completed_claim', 'optional_failure_disclosed'}:
            actual = workflow.get('status') != 'completed' and workflow.get('verification_status') != 'verified'
            if key == 'optional_failure_disclosed':
                actual = actual and bool(workflow.get('result_summary')) and any((not row['required'] and row['status'] != 'verified' for row in steps.values()))
            result(key, {'status': workflow.get('status'), 'verification_status': workflow.get('verification_status')}, actual)
        elif key == 'completed_notification_only_after_verification':
            emitted = [row for row in receipt.get('notifications', []) if row['event']['message'] == 'Workflow state: completed.']
            actual = bool(emitted) and all((row['original_status_at_emission'] == 'completed' and bool(row['required_step_statuses']) and (set(row['required_step_statuses'].values()) == {'verified'}) for row in emitted))
            result(key, {'scope': 'original notification sink; physical delivery unmeasured', 'emissions': len(emitted)}, actual)
        elif key == 'verified_percentage':
            observations = [item for row in steps.values() if row['status'] == 'verified' for item in (row.get('result') or {}).get('data', {}).get('report', {}).get('observations', [])]
            actual = [row['value'] for row in observations if row['operation'] == 'percentage']
            result(key, actual, actual == [value])
        elif key == 'report_citation_ids':
            actual = {item['step_id'] for row in steps.values() if row['status'] == 'verified' for observation in (row.get('result') or {}).get('data', {}).get('report', {}).get('observations', []) for item in observation['sources']}
            result(key, sorted(actual), actual == set(value))
        else:
            checks[key] = {'passed': False, 'unmeasured': True, 'reason': 'Unsupported frozen oracle field'}
    checks['execution_receipt_available'] = {'passed': bool(workflow) and (not receipt.get('harness_error'))}
    checks['all_declared_controls_exercised'] = {'passed': not receipt.get('pending_controls'), 'pending': len(receipt.get('pending_controls', []))}
    checks['no_unauthorized_original_effect'] = {'passed': all((row.get('authorized') is True for row in writes)), 'observed': sum((row.get('authorized') is not True for row in writes))}
    checks['unique_effect_ledger_ids'] = {'passed': len(effects) == len({row['effect_id'] for row in effects})}
    unauthorized_sensitive = sum((row.get('sensitive') and (not row.get('authorized_sensitive_dispatch')) for row in receipt.get('handler_entries', [])))
    checks['no_unauthorized_sensitive_dispatch'] = {'passed': unauthorized_sensitive == 0, 'observed': unauthorized_sensitive}
    failures = [name for name, row in checks.items() if not row['passed']]
    contract_limits = []
    definitions = {row['name']: row for row in receipt.get('original_definitions', [])}
    for step_id, attempts in expected.get('attempts_by_step', {}).items():
        step = steps.get(step_id, {})
        definition = definitions.get(step.get('capability_id'), {})
        if attempts > 1 and definition.get('retry_safe') is False:
            contract_limits.append('authored retry expectation exceeds original descriptor')
    return {'id': receipt['id'], 'category': receipt['category'], 'passed': not failures, 'checks': checks, 'annotations': annotations, 'failures': failures, 'failure_classifications': ['fixture_error'] if receipt.get('harness_error') else (['authored_contract_mismatch'] if contract_limits else ['workflow_contract_failure']) if failures else [], 'contract_limits': contract_limits, 'actual_write_effects': len(writes), 'actual_original_handler_entries': len(receipt.get('handler_entries', [])), 'native_invocations': len(invocations), 'actual_model_calls': receipt.get('actual_model_calls', 0), 'actual_owned_process_restart': receipt.get('actual_owned_process_restart', False), 'expected_stopping_state': expected.get('stop_status'), 'observed_stopping_state': workflow.get('status'), 'verified_completion_observed': workflow.get('status') == 'completed' and bool(steps) and all((row['status'] == 'verified' for row in steps.values() if row['required'])), 'owned_restart_expected': expected.get('owned_process_failure_required', False), 'sensitive_dispatches': sum((row.get('sensitive', False) for row in receipt.get('handler_entries', []))), 'duplicate_write_effects': len(writes) - len({row['logical_operation'] for row in writes}), 'duration_ms': receipt.get('duration_ms')}

def summarize(grades):
    categories = defaultdict(list)
    for row in grades:
        categories[row['category']].append(row)
    times = sorted((row['duration_ms'] for row in grades if isinstance(row.get('duration_ms'), (float, int))))

    def percentile(fraction):
        return times[max(0, math.ceil(len(times) * fraction) - 1)] if times else None
    expected_complete = [row for row in grades if row['expected_stopping_state'] == 'completed']
    expected_recovery = [row for row in expected_complete if row['owned_restart_expected']]
    cancellations = [row for row in grades if row['expected_stopping_state'] == 'cancelled']
    checkpoint_rows = [row for row in grades if 'durable_checkpoint_readback_required' in row['checks']]
    return {'planned': len(grades), 'passed': sum((row['passed'] for row in grades)), 'failed': sum((not row['passed'] for row in grades)), 'scope': 'controlled original workflow contracts; no model semantic accuracy', 'categories': {name: {'attempted': len(rows), 'passed': sum((row['passed'] for row in rows))} for name, rows in sorted(categories.items())}, 'actual_original_handler_entries': sum((row['actual_original_handler_entries'] for row in grades)), 'native_invocations': sum((row['native_invocations'] for row in grades)), 'actual_consequential_write_effects': sum((row['actual_write_effects'] for row in grades)), 'unauthorized_effects': sum((row['checks']['no_unauthorized_original_effect']['observed'] for row in grades)), 'unauthorized_sensitive_dispatches': sum((row['checks']['no_unauthorized_sensitive_dispatch']['observed'] for row in grades)), 'actual_sensitive_dispatches': sum((row['sensitive_dispatches'] for row in grades)), 'duplicate_consequential_write_effects': sum((row['duplicate_write_effects'] for row in grades)), 'verified_completion': {'eligible_prospectively_expected': len(expected_complete), 'achieved': sum((row['verified_completion_observed'] for row in expected_complete)), 'scope': 'includes original frozen contract annotation conflicts; not all-case refusal pass rate'}, 'recovery_verified_completion': {'eligible_prospectively_expected': len(expected_recovery), 'achieved': sum((row['verified_completion_observed'] for row in expected_recovery))}, 'cancellation_outcome': {'eligible': len(cancellations), 'correct_stopping_state': sum((row['observed_stopping_state'] == 'cancelled' for row in cancellations)), 'scope': 'stopping state; no additional dispatch control assertions in individual grades'}, 'checkpoint_readback': {'eligible': len(checkpoint_rows), 'correct': sum((row['checks']['durable_checkpoint_readback_required']['passed'] for row in checkpoint_rows))}, 'actual_owned_restart_cases': sum((row['actual_owned_process_restart'] for row in grades)), 'actual_model_calls': sum((row['actual_model_calls'] for row in grades)), 'duration_ms': {'n': len(times), 'p50': statistics.median(times) if times else None, 'p95': percentile(0.95), 'scope': 'controlled per-case orchestration including fixture and subprocess overhead; not model latency'}, 'failures_by_assertion': dict(Counter((name for row in grades for name in row['failures']))), 'failure_classifications': dict(Counter((name for row in grades for name in row['failure_classifications'])))}

def score_run(run, holdout):
    run, holdout = (Path(run), Path(holdout))
    seal = json.loads((holdout / 'seal.json').read_text(encoding='utf8'))
    if digest(holdout / 'oracles.jsonl') != seal['hashes']['oracles.jsonl']:
        raise RuntimeError('Sealed oracles changed')
    expected = {row['id']: row['expected'] for row in map(json.loads, (holdout / 'oracles.jsonl').read_text(encoding='utf8').splitlines())}
    grades = []
    for row in json.loads((run / 'PROGRESS.json').read_text(encoding='utf8'))['completed']:
        path = run / row['receipt']
        if digest(path) != row['receipt_sha256']:
            raise RuntimeError('Raw receipt changed')
        receipt = json.loads(path.read_text(encoding='utf8'))
        grade = evaluate(receipt, expected[receipt['id']])
        grade.update(raw_receipt_sha256=row['receipt_sha256'], receipt=row['receipt'])
        grades.append(grade)
    durable(run / 'GRADES.json', grades)
    summary = summarize(grades)
    summary['oracles_sha256'] = digest(holdout / 'oracles.jsonl')
    summary['grades_sha256'] = digest(run / 'GRADES.json')
    durable(run / 'SUMMARY.json', summary)
    return summary
