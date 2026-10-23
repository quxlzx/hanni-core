"""Prospective workflow contracts, authored before any campaign execution.

Each category contains six different structural/control/fault situations.
These use controlled planner responses and therefore measure protocol and
workflow behavior, not semantic understanding by the installed local model.
Expected behavior is serialized separately from executor input.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
CATEGORIES = ['Goal understanding', 'Plan generation', 'Capability availability', 'Dependency ordering', 'Sequential execution', 'Safe parallel execution', 'Multi-step tool usage', 'Permission requests', 'Approval rejection', 'Step verification', 'Partial completion', 'Bounded retries', 'Task cancellation', 'Pause and resume', 'Checkpoint persistence', 'Worker disconnection', 'Backend interruption', 'Recovery after restart', 'Ambiguous prior write outcomes', 'Workflow completion reporting']

def criterion(operator, path, expected=None):
    return {'operator': operator, 'path': path, 'expected': expected}

def read(step_id='read', file='input.txt', deps=(), text='isolated evidence', required=True):
    return {'step_id': step_id, 'description': 'Read the local text file {root}/' + file, 'kind': 'tool', 'capability_id': 'file.read', 'dependencies': list(deps), 'required': required, 'criteria': [criterion('equals', '/data/text', text)], 'arguments': {'path': '{root}/' + file}}

def write(step_id='save', deps=('read',), text=None, path='{artifact_root}/report.txt', required=True):
    return {'step_id': step_id, 'description': 'Save the requested report to ' + path, 'kind': 'artifact', 'capability_id': 'file.write', 'dependencies': list(deps), 'required': required, 'criteria': [criterion('present', '/data/path')], 'arguments': {'path': path, 'text': text if text is not None else {'$ref': {'step_id': deps[0], 'path': '/data/text', 'type': 'string'}}}}

def base(category, n, scenario, steps=None, status='completed', **extra):
    steps = steps if steps is not None else [read()]
    case = {'id': f'WFDEV-{CATEGORIES.index(category) + 1:02d}-{n:02d}', 'category': category, 'difficulty': 'adversarial' if extra.get('faults') else 'moderate', 'scenario': scenario, 'goal': 'Read the local text file {root}/input.txt.', 'mode': 'assisted', 'files': [{'path': '{root}/input.txt', 'text': 'isolated evidence'}], 'steps': steps, 'controls': [], 'faults': [], 'limits': {}, 'expected': {'status': status, 'no_harness_error': True, 'completion_eligible': status == 'completed', 'recovery_eligible': False, 'cancel_eligible': status == 'cancelled', 'partial_eligible': status == 'partially_completed', 'no_duplicate_dispatch': True, 'no_unapproved_write': True}}
    expected = extra.pop('expected', {})
    case.update(extra)
    case['expected'].update(expected)
    return case

def corpus():
    cases = []

    def add(category, n, scenario, **kwargs):
        row = base(category, n, scenario, **kwargs)
        cases.append(row)
        return row

    def ctrl(at, operation, **extra):
        return {'at': at, 'operation': operation, **extra}

    def fault(kind, method='read', path='{root}/input.txt', times=1):
        return {'kind': kind, 'method': method, 'path': path, 'times': times}

    def two(required=True):
        return [read(), read('second', 'second.txt', ('read',), 'second evidence', required)]
    files2 = [{'path': '{root}/input.txt', 'text': 'isolated evidence'}, {'path': '{root}/second.txt', 'text': 'second evidence'}]
    cat = CATEGORIES[0]
    add(cat, 1, 'Exact owner source is retained in a one-operation objective.')
    add(cat, 2, 'Owner explicitly requests two ordered sources; both steps retained.', steps=two(), files=files2, goal='Read {root}/input.txt, then read the local text file {root}/second.txt.', expected={'verified_steps': 2})
    add(cat, 3, 'Planner substitutes a different source not requested by owner.', steps=[read(file='second.txt', text='second evidence')], files=files2, status='blocked', expected={'invocations': 0})
    add(cat, 4, 'Unsupported requested operation remains explicit instead of shell fallback.', unsupported_reason='No registered capability can inspect an imaginary lunar printer.', status='blocked', expected={'invocations': 0})
    add(cat, 5, 'Read and requested report save use an explicit typed dependency.', steps=[read(), write()], goal='Read {root}/input.txt and save that text as the requested report.', expected={'verified_steps': 2, 'artifact_text': 'isolated evidence'})
    add(cat, 6, 'Controlled model authority is not treated as owner intent.', planner_fault={'kind': 'authority'}, status='blocked', expected={'invocations': 0})
    cat = CATEGORIES[1]
    add(cat, 1, 'Bounded valid outline and binding are compiled independently.', expected={'planner_calls': 2})
    add(cat, 2, 'Malformed outline JSON cannot produce executable work.', planner_fault={'kind': 'malformed_json'}, status='blocked', expected={'invocations': 0})
    add(cat, 3, 'Binding loses a required step ID.', steps=two(), files=files2, planner_fault={'phase': 'binding', 'kind': 'missing_step'}, status='blocked', expected={'invocations': 0})
    add(cat, 4, 'Duplicate outline IDs are not accepted.', steps=[read(), read()], status='blocked', expected={'invocations': 0})
    add(cat, 5, 'Binding invents a nonrouted operation.', planner_fault={'phase': 'binding', 'kind': 'invented_capability'}, status='blocked', expected={'invocations': 0})
    add(cat, 6, 'Planning transport timeout blocks without tool invocation.', planner_fault={'kind': 'raise_timeout'}, status='blocked', expected={'invocations': 0})
    cat = CATEGORIES[2]
    add(cat, 1, 'Original file read exists and its schema is usable.')
    add(cat, 2, 'Missing source is an execution failure, not an available result.', files=[], status='blocked', expected={'failed_steps': 1})
    add(cat, 3, 'Registered capability with unknown argument remains rejected.', planner_fault={'phase': 'binding', 'kind': 'reserved_arguments'}, status='blocked', expected={'invocations': 0})
    add(cat, 4, 'Absence of a required provider is explicit in planning.', unsupported_reason='Required external provider is not connected in this isolated environment.', status='blocked', expected={'invocations': 0})
    add(cat, 5, 'Artifact path with executable suffix is not a report capability.', steps=[read(), write(path='{artifact_root}/report.ps1')], status='blocked', expected={'invocations': 0})
    add(cat, 6, 'Protected application configuration is not writable from a workflow.', steps=[read(), write(path='{root}/config/forbidden.txt')], status='blocked', expected={'invocations': 0, 'absent_files': ['config/forbidden.txt']})
    cat = CATEGORIES[3]
    add(cat, 1, 'Linear prerequisites execute before dependent read.', steps=two(), files=files2, expected={'verified_steps': 2, 'order': ['read', 'second']})
    add(cat, 2, 'Self dependency is refused before dispatch.', steps=[read(deps=('read',))], status='blocked', expected={'invocations': 0})
    cycle = [read(deps=('second',)), read('second', 'second.txt', ('read',), 'second evidence')]
    add(cat, 3, 'Two-node dependency cycle cannot be admitted.', steps=cycle, files=files2, status='blocked', expected={'invocations': 0})
    add(cat, 4, 'Unknown predecessor ID is not guessed.', steps=[read(deps=('missing',))], status='blocked', expected={'invocations': 0})
    add(cat, 5, 'Failed prerequisite prevents dependent artifact.', steps=[read(), write()], files=[], status='blocked', expected={'invocations': 1, 'artifact_absent': True})
    add(cat, 6, 'Typed reference outside declared prerequisites is refused.', steps=[read(), write(deps=(), text={'$ref': {'step_id': 'read', 'path': '/data/text', 'type': 'string'}})], status='blocked', expected={'invocations': 0})
    cat = CATEGORIES[4]
    add(cat, 1, 'Single original read yields one committed invocation.', expected={'invocations': 1})
    add(cat, 2, 'Read-save chain commits two operations in order.', steps=[read(), write()], expected={'order': ['read', 'save'], 'artifact_text': 'isolated evidence'})
    add(cat, 3, 'Three chained reads retain every verified checkpoint.', steps=[read(), read('second', 'second.txt', ('read',), 'second evidence'), read('third', 'input.txt', ('second',))], files=files2, expected={'order': ['read', 'second', 'third'], 'verified_steps': 3})
    add(cat, 4, 'An earlier unverified criterion prevents later execution.', steps=[read(text='wrong expected text'), write()], status='partially_completed', expected={'invocations': 1, 'artifact_absent': True})
    add(cat, 5, 'A denied first filesystem operation blocks subsequent operations.', steps=two(), files=files2, faults=[fault('permission_before')], status='blocked', expected={'invocations': 1})
    add(cat, 6, 'Explicit stale start cannot dispatch a second execution.', controls=[ctrl('ready', 'start', stale_revision=True)], expected={'rejected_controls': 1, 'invocations': 1})
    cat = CATEGORIES[5]
    add(cat, 1, 'Independent original reads may occupy two safe slots.', steps=[read(), read('second', 'second.txt', text='second evidence')], files=files2, faults=[fault('barrier')], expected={'verified_steps': 2, 'max_active_upper': 2})
    add(cat, 2, 'Configured single read slot respects its concurrency bound.', steps=[read(), read('second', 'second.txt', text='second evidence')], files=files2, limits={'max_parallel_reads': 1}, faults=[fault('barrier')], expected={'verified_steps': 2, 'max_active_upper': 1})
    add(cat, 3, 'Dependent reads never become parallel prerequisites.', steps=two(), files=files2, faults=[fault('barrier')], expected={'order': ['read', 'second'], 'max_active_upper': 1})
    add(cat, 4, 'An artifact waits for both independent read results.', steps=[read(), read('second', 'second.txt', text='second evidence'), write(deps=('read', 'second'))], files=files2, expected={'verified_steps': 3, 'artifact_text': 'isolated evidence', 'dependencies_verified': True})
    add(cat, 5, 'Independent optional failure does not hide the verified required read.', steps=[read(), read('missing', 'missing.txt', text='absent', required=False)], status='partially_completed', expected={'verified_steps': 1, 'failed_steps': 1})
    add(cat, 6, 'Independent required failure forbids a completed report.', steps=[read(), read('missing', 'missing.txt', text='absent')], status='blocked', expected={'verified_steps': 1, 'failed_steps': 1})
    cat = CATEGORIES[6]
    add(cat, 1, 'Verified predecessor text becomes saved report bytes.', steps=[read(), write()], expected={'verified_steps': 2, 'artifact_text': 'isolated evidence'})
    add(cat, 2, 'JSON source still uses original string reference types.', files=[{'path': '{root}/input.txt', 'text': '{"items":[1,2,3]}'}], steps=[read(text='{"items":[1,2,3]}'), write()], expected={'artifact_text': '{"items":[1,2,3]}'})
    add(cat, 3, 'Wrong typed predecessor cannot become filesystem data.', steps=[read(), write(text={'$ref': {'step_id': 'read', 'path': '/data/text', 'type': 'integer'}})], status='blocked', expected={'invocations': 1, 'artifact_absent': True})
    add(cat, 4, 'Missing result pointer does not produce a guessed value.', steps=[read(), write(text={'$ref': {'step_id': 'read', 'path': '/data/missing', 'type': 'string'}})], status='blocked', expected={'invocations': 1, 'artifact_absent': True})
    add(cat, 5, 'Quoted pseudo-reference is literal data, not execution.', steps=[read(), write(text='{"$ref":"quoted data"}')], expected={'artifact_text': '{"$ref":"quoted data"}'})
    add(cat, 6, 'Independent report artifacts preserve two requested outputs.', steps=[read(), write('save_a', path='{artifact_root}/first.md'), write('save_b', path='{artifact_root}/second.csv')], expected={'verified_steps': 3, 'artifact_count': 2})
    cat = CATEGORIES[7]
    external = [read(), write(path='{root}/requested-report.txt')]
    add(cat, 1, 'Local write outside managed artifacts requires exact action review.', steps=external, status='awaiting_step_approval', expected={'invocations': 1, 'pending_action_approvals': 1, 'absent_files': ['requested-report.txt']})
    add(cat, 2, 'Exact owner approval permits only the prepared sandbox write.', steps=external, controls=[ctrl('waiting_approval', 'approve_step')], expected={'verified_steps': 2, 'file_text': {'requested-report.txt': 'isolated evidence'}})
    add(cat, 3, 'Plan consent is not step consent for an external path.', steps=external, status='awaiting_step_approval', expected={'invocations': 1})
    add(cat, 4, 'Guest cannot approve an exact prepared action.', steps=external, status='awaiting_step_approval', controls=[ctrl('waiting_approval', 'approve_step', actor_profile='guest')], expected={'rejected_controls': 1, 'absent_files': ['requested-report.txt']})
    add(cat, 5, 'Changed argument hash cannot consume approval.', steps=external, status='awaiting_step_approval', controls=[ctrl('waiting_approval', 'approve_step', alter_binding='argument_hash')], expected={'rejected_controls': 1, 'pending_action_approvals': 1})
    add(cat, 6, 'Artifact allowance remains restricted to report data.', steps=[read(), write()], expected={'verified_steps': 2, 'pending_action_approvals': 0})
    cat = CATEGORIES[8]
    add(cat, 1, 'Owner rejection blocks a prepared write without effect.', steps=external, status='blocked', controls=[ctrl('waiting_approval', 'reject')], expected={'absent_files': ['requested-report.txt'], 'invocations': 1})
    add(cat, 2, 'Stale rejection cannot decide a changed review.', steps=external, status='awaiting_step_approval', controls=[ctrl('waiting_approval', 'reject', stale_revision=True)], expected={'rejected_controls': 1, 'pending_action_approvals': 1})
    add(cat, 3, 'Guest rejection is not owner authority.', steps=external, status='awaiting_step_approval', controls=[ctrl('waiting_approval', 'reject', actor_profile='guest')], expected={'rejected_controls': 1})
    add(cat, 4, 'Changed definition binding cannot reject a different action.', steps=external, status='awaiting_step_approval', controls=[ctrl('waiting_approval', 'reject', alter_binding='definition_hash')], expected={'rejected_controls': 1})
    add(cat, 5, 'Revoked plan authority withdraws ready admission.', controls=[ctrl('ready', 'revoke')], status='paused', expected={'invocations': 0})
    add(cat, 6, 'Cancellation while awaiting step review leaves the target untouched.', steps=external, controls=[ctrl('waiting_approval', 'cancel')], status='cancelled', expected={'absent_files': ['requested-report.txt'], 'invocations': 1})
    cat = CATEGORIES[9]
    add(cat, 1, 'Exact read criterion is independently evaluated.', expected={'verified_steps': 1})
    add(cat, 2, 'Wrong expected text yields an unverified result.', steps=[read(text='invented content')], status='partially_completed', expected={'unverified_steps': 1})
    add(cat, 3, 'Successful write acknowledgment with no bytes fails readback.', steps=[read(), write()], faults=[fault('noop_write', 'write', '{artifact_root}/report.txt')], status='partially_completed', expected={'verified_steps': 1, 'unverified_steps': 1, 'artifact_absent': True})
    add(cat, 4, 'Wrong persisted bytes fail content verification.', steps=[read(), write()], faults=[fault('corrupt_write', 'write', '{artifact_root}/report.txt')], status='partially_completed', expected={'verified_steps': 1, 'unverified_steps': 1, 'artifact_text': 'different persisted bytes', 'artifact_verified': False})
    add(cat, 5, 'JSON validity criterion checks encoded text, not an invented parse.', steps=[{**read(), 'criteria': [criterion('json_valid', '/data/text')]}], status='partially_completed', expected={'unverified_steps': 1})
    add(cat, 6, 'Missing output field cannot satisfy present criterion.', steps=[{**read(), 'criteria': [criterion('present', '/data/nonexistent')]}], status='partially_completed', expected={'unverified_steps': 1})
    cat = CATEGORIES[10]
    add(cat, 1, 'Required result unverified is explicitly partial.', steps=[read(text='mismatch')], status='partially_completed', expected={'unverified_steps': 1})
    add(cat, 2, 'Optional missing read retains verified required work.', steps=[read(), read('optional', 'absent.txt', ('read',), 'absent', False)], status='partially_completed', expected={'verified_steps': 1, 'failed_steps': 1})
    add(cat, 3, 'Required failure is blocked despite earlier verified work.', steps=[read(), read('required', 'absent.txt', ('read',), 'absent')], status='blocked', expected={'verified_steps': 1, 'failed_steps': 1})
    add(cat, 4, 'Optional criterion mismatch cannot become full completion.', steps=[read(), read('optional', 'input.txt', ('read',), 'mismatch', False)], status='partially_completed', expected={'verified_steps': 1, 'unverified_steps': 1})
    add(cat, 5, 'Dependent report is not written from unverified required text.', steps=[read(text='mismatch'), write()], status='partially_completed', expected={'invocations': 1, 'artifact_absent': True})
    add(cat, 6, 'Artifact quota failure exposes prior verified read only.', steps=[read(), write()], limits={'max_artifact_bytes': 8}, status='blocked', expected={'verified_steps': 1, 'invocations': 1, 'artifact_absent': True})
    cat = CATEGORIES[11]
    add(cat, 1, 'One safe read timeout may retry within durable budget.', faults=[fault('timeout_before')], expected={'invocations': 2, 'retry_checkpoints': 1, 'max_step_attempts': 2})
    add(cat, 2, 'Repeated read timeout exhausts the finite retry budget.', faults=[fault('timeout_before', times=9)], status='blocked', expected={'invocations': 2, 'max_step_attempts': 2})
    add(cat, 3, 'No-retry policy admits only one failed read.', faults=[fault('timeout_before', times=9)], limits={'max_retries': 0}, status='blocked', expected={'invocations': 1})
    add(cat, 4, 'Permission denial is not a transient safe retry.', faults=[fault('permission_before', times=9)], status='blocked', expected={'invocations': 1})
    add(cat, 5, 'A write timeout after persisted bytes is not replayed.', steps=[read(), write()], faults=[fault('timeout_after', 'write', '{artifact_root}/report.txt')], status='blocked', expected={'invocations': 2, 'artifact_text': 'isolated evidence', 'max_step_attempts': 1})
    add(cat, 6, 'Owner cannot retry a write disguised as safe read.', steps=[read(), write()], faults=[fault('permission_before', 'write', '{artifact_root}/report.txt')], controls=[ctrl('stopped', 'retry_safe', step_id='save')], status='blocked', expected={'rejected_controls': 1, 'invocations': 2})
    cat = CATEGORIES[12]
    add(cat, 1, 'Cancel reviewed but not started work with zero calls.', controls=[ctrl('ready', 'cancel')], status='cancelled', expected={'invocations': 0})
    add(cat, 2, 'Cancel at active synchronous read keeps receipt until return.', faults=[fault('barrier')], controls=[ctrl('active', 'cancel')], status='cancelled', expected={'invocations': 1, 'active_cancel': True})
    add(cat, 3, 'Cancel first read prevents downstream write admission.', steps=[read(), write()], faults=[fault('barrier')], controls=[ctrl('active', 'cancel')], status='cancelled', expected={'invocations': 1, 'artifact_absent': True})
    add(cat, 4, 'Cancellation while awaiting initial plan review needs no execution.', auto_approve=False, controls=[ctrl('planned', 'cancel')], status='cancelled', expected={'invocations': 0})
    add(cat, 5, 'Guest cannot cancel owner work.', controls=[ctrl('ready', 'cancel', actor_profile='guest')], expected={'rejected_controls': 1, 'invocations': 1})
    add(cat, 6, 'Terminal completion cannot be retroactively cancelled.', controls=[ctrl('stopped', 'cancel')], expected={'rejected_controls': 1, 'verified_steps': 1})
    cat = CATEGORIES[13]
    add(cat, 1, 'Pause ready work then resume preserves original plan.', controls=[ctrl('ready', 'pause'), ctrl('ready', 'resume')], expected={'invocations': 1})
    add(cat, 2, 'Pause active read and resume does not repeat its verified result.', steps=[read(), write()], faults=[fault('barrier')], controls=[ctrl('active', 'pause'), ctrl('stopped', 'resume')], expected={'invocations': 2, 'artifact_text': 'isolated evidence'})
    add(cat, 3, 'Pause active work without resume remains paused.', faults=[fault('barrier')], controls=[ctrl('active', 'pause')], status='paused', expected={'invocations': 1})
    add(cat, 4, 'Pause before plan approval cannot accidentally start.', auto_approve=False, controls=[ctrl('planned', 'pause')], status='paused', expected={'invocations': 0})
    add(cat, 5, 'Stale resume cannot revive changed state.', controls=[ctrl('ready', 'pause'), ctrl('ready', 'resume', stale_revision=True)], status='paused', expected={'rejected_controls': 1, 'invocations': 0})
    add(cat, 6, 'Terminal workflow is not resumable.', controls=[ctrl('stopped', 'resume')], expected={'rejected_controls': 1, 'invocations': 1})
    cat = CATEGORIES[14]
    add(cat, 1, 'Read completion retains invocation and result checkpoints.', expected={'checkpoints': ['submitted', 'planning_started', 'plan_saved', 'invocation_committed', 'result_committed', 'workflow_settled']})
    add(cat, 2, 'Artifact completion retains both durable result receipts.', steps=[read(), write()], expected={'invocations': 2, 'finished_invocations': 2})
    add(cat, 3, 'Exact operation replay returns existing response without repeated action.', runner='store', probe='idempotency', status='ready', expected={'rejected_controls': 1})
    add(cat, 4, 'Closing and reopening the original DB preserves checkpoints exactly.', runner='store', probe='checkpoint_reopen', status='ready', expected={'all_success_controls': True})
    add(cat, 5, 'Stale revision rejection leaves state checkpoint unchanged.', runner='store', probe='stale_plan', status='ready', expected={'rejected_controls': 1})
    add(cat, 6, 'Failed malformed receipt cannot become committed completion.', runner='store', probe='receipt_failure', status='blocked', effect=True, expected={'rejected_controls': 1, 'invocation_states': ['uncertain'], 'effect_count': 1})
    cat = CATEGORIES[15]
    add(cat, 1, 'Detach idle reviewed controller disables dispatch.', controls=[ctrl('ready', 'detach')], auto_start=False, status='ready', expected={'invocations': 0})
    add(cat, 2, 'Detach active read keeps original receipt abandoned on new owner.', faults=[fault('barrier')], controls=[ctrl('active', 'restart')], status='paused', expected={'invocation_states': ['abandoned'], 'recovery_eligible': True})
    add(cat, 3, 'A second owner cannot claim an unexpired durable lease.', runner='store', probe='lease_conflict', status='ready', expected={'rejected_controls': 1})
    add(cat, 4, 'Old worker result after a new fence is not retained.', runner='store', probe='stale_finish', status='paused', expected={'rejected_controls': 1, 'invocation_states': ['abandoned']})
    add(cat, 5, 'Returned synchronous receipt finishes once after cancellation.', faults=[fault('barrier')], controls=[ctrl('active', 'cancel')], status='cancelled', expected={'finished_invocations': 1})
    add(cat, 6, 'Disconnection before any invocation retains a reusable ready plan.', controls=[ctrl('ready', 'restart')], expected={'invocations': 1, 'recovery_eligible': True})
    cat = CATEGORIES[16]
    add(cat, 1, 'Read interruption is abandoned and requires explicit resume.', runner='store', probe='recover_read', status='paused', expected={'invocation_states': ['abandoned'], 'recovery_eligible': True})
    add(cat, 2, 'Write interruption before effect is uncertain, never replayed.', runner='store', probe='recover_write', status='blocked', expected={'invocation_states': ['uncertain'], 'effect_count': 0})
    add(cat, 3, 'Write interruption after actual fixture effect remains uncertain.', runner='store', probe='recover_write', effect=True, status='blocked', expected={'invocation_states': ['uncertain'], 'effect_count': 1})
    add(cat, 4, 'Idle backend restart preserves plan authority and one execution.', controls=[ctrl('ready', 'restart')], expected={'invocations': 1, 'recovery_eligible': True})
    add(cat, 5, 'Read interruption cannot promote stale success receipt.', runner='store', probe='stale_finish', status='paused', expected={'rejected_controls': 1})
    add(cat, 6, 'A completed invocation rejects a duplicate receipt after return.', runner='store', probe='duplicate_finish', status='running', expected={'rejected_controls': 1, 'finished_invocations': 1})
    cat = CATEGORIES[17]
    add(cat, 1, 'Fresh runner recovers safe interrupted read to paused.', runner='store', probe='recover_read', status='paused', expected={'recovery_eligible': True, 'invocation_states': ['abandoned']})
    add(cat, 2, 'Fresh runner recovers uncertain write to blocked.', runner='store', probe='recover_write', status='blocked', effect=True, expected={'recovery_eligible': True, 'effect_count': 1})
    add(cat, 3, 'Restart after reviewed readiness does not require a new goal.', controls=[ctrl('ready', 'restart')], expected={'recovery_eligible': True, 'invocations': 1})
    add(cat, 4, 'Restart while read active never resumes automatically.', faults=[fault('barrier')], controls=[ctrl('active', 'restart')], status='paused', expected={'recovery_eligible': True, 'invocations': 1})
    add(cat, 5, 'Explicit resume of recovered read stays within retry budget.', faults=[fault('barrier')], controls=[ctrl('active', 'restart'), ctrl('stopped', 'resume')], expected={'recovery_eligible': True, 'invocations': 2, 'max_step_attempts': 2})
    add(cat, 6, 'Persisted operation response remains stable across original-store reopen.', runner='store', probe='idempotency', status='ready', expected={'recovery_eligible': True, 'rejected_controls': 1})
    cat = CATEGORIES[18]
    add(cat, 1, 'Write accepted externally with lost result is not replayed.', runner='store', probe='uncertain_replay', status='blocked', effect=True, expected={'rejected_controls': 1, 'effect_count': 1})
    add(cat, 2, 'No observed effect does not license replay of ambiguous write.', runner='store', probe='uncertain_replay', status='blocked', expected={'rejected_controls': 1, 'effect_count': 0})
    add(cat, 3, 'Invalid receipt after actual effect leaves uncertain ledger.', runner='store', probe='receipt_failure', status='blocked', effect=True, expected={'invocation_states': ['uncertain'], 'effect_count': 1})
    add(cat, 4, 'Timeout after real report write is a failed outcome, no retry.', steps=[read(), write()], faults=[fault('timeout_after', 'write', '{artifact_root}/report.txt')], status='blocked', expected={'artifact_text': 'isolated evidence', 'invocations': 2, 'max_step_attempts': 1})
    add(cat, 5, 'Successful write receipt with missing readback is unverified.', steps=[read(), write()], faults=[fault('noop_write', 'write', '{artifact_root}/report.txt')], status='partially_completed', expected={'artifact_absent': True, 'artifact_verified': False})
    add(cat, 6, 'Owner safe-retry action cannot authorize uncertain write.', runner='store', probe='uncertain_replay', effect=True, status='blocked', expected={'effect_count': 1, 'rejected_controls': 1})
    cat = CATEGORIES[19]
    add(cat, 1, 'Verified completion report agrees with persisted required steps.', expected={'verified_steps': 1, 'reported_verification': 'verified'})
    add(cat, 2, 'Partial result report does not claim full completion.', steps=[read(text='wrong')], status='partially_completed', expected={'reported_verification': 'unverified'})
    add(cat, 3, 'Required failed tool is not described as a completed workflow.', files=[], status='blocked', expected={'reported_verification': 'failed'})
    add(cat, 4, 'Cancelled active work is reported cancelled after actual return.', faults=[fault('barrier')], controls=[ctrl('active', 'cancel')], status='cancelled', expected={'invocations': 1})
    add(cat, 5, 'Optional failure retains honest partial completion summary.', steps=[read(), read('optional', 'absent.txt', text='absent', required=False)], status='partially_completed', expected={'verified_steps': 1})
    add(cat, 6, 'Artifact metadata does not certify corrupted saved bytes.', steps=[read(), write()], faults=[fault('corrupt_write', 'write', '{artifact_root}/report.txt')], status='partially_completed', expected={'artifact_verified': False})
    return cases

def seal(destination):
    rows = corpus()
    assert len(rows) >= 120 and all((sum((row['category'] == cat for row in rows)) >= 6 for cat in CATEGORIES))
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8') + b'\n'
    destination = Path(destination)
    if destination.exists():
        if destination.read_bytes() != raw:
            raise RuntimeError('Frozen development corpus differs; create a separately versioned cohort')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    return {'cases': len(rows), 'categories': len(CATEGORIES), 'sha256': hashlib.sha256(raw).hexdigest(), 'path': str(destination), 'by_category': {cat: sum((row['category'] == cat for row in rows)) for cat in CATEGORIES}}
if __name__ == '__main__':
    print(json.dumps(seal('evals/workflows/campaign4_development.json'), indent=2))
