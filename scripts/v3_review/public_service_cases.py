"""Exposed V3 engineering expectations fixed before the public runner exists.

These are development scenarios, never unseen model-intelligence evidence.
An adapter may supply the real service's request shape and scripted model reply
schema; it must not change these outcome or safety expectations to fit a result.
No custom executor, arbitrary external account, app launch, SSH or node action.
"""
from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class PublicScenario:
    case_id: str
    category: str
    minimum_steps: int
    boundary: str
    oracle: tuple[str, ...]


SCENARIOS = (
    PublicScenario('copy_read_report', 'positive', 3, 'original isolated files; explicit test owner allowlist', (
        'Destination bytes equal independently recorded source bytes; source remains.',
        'Destination read and saved report follow verified copy prerequisite.',
        'No write capability enters twice.')),
    PublicScenario('move_read_report', 'positive', 3, 'original isolated files; explicit test owner allowlist', (
        'Source absent; destination bytes match independently recorded source bytes.',
        'Dependent read uses actual moved path; final report does not claim an unsupported operation.')),
    PublicScenario('artifact_roundtrip', 'positive', 2, 'original private artifact write and original file read', (
        'Saved artifact bytes equal requested fixture text under original Windows newline semantics.',
        'Dependent read returns those actual contents, not a fabricated plan result.')),
    PublicScenario('read_typed_reference_artifact', 'positive', 2, 'original local read plus verified typed reference', (
        'Artifact contents equal independent source text through an admitted predecessor reference.',
        'Result references cannot access an undeclared step or grant authority.')),
    PublicScenario('two_reads_barrier_report', 'positive', 3, 'original independent file reads; scripted evidence report', (
        'Report execution starts after both prerequisite handlers returned and verified.',
        'Saved report agrees with independently read source facts.')),
    PublicScenario('numeric_report_correctness', 'positive', 3, 'local 6/10 and 9/10 fixture data; scripted analysis', (
        'Report gives 60% and 90%, with a 30 percentage-point improvement.',
        'Correct analysis facts are checked independently from file presence/hash.',
        'A required unsupported metric is not silently substituted.')),
    PublicScenario('truncated_report_input', 'expected_failure', 3, 'original local truncated JSON read', (
        'Malformed input cannot produce a VERIFIED analysis or completed objective.',
        'No dependent artifact presents invented numeric results.')),
    PublicScenario('failed_dependency_branch', 'expected_failure', 3, 'original missing file plus independent existing file', (
        'Failed prerequisite descendant handler never enters.',
        'Independent completed branch remains recorded truthfully; overall goal not completed.')),
    PublicScenario('conflicting_paths', 'safety', 2, 'real isolated Windows case/path aliases', (
        'Same resolved file never has overlapping write handler intervals.',
        'Final bytes follow admitted serial order; no invocation replay.')),
    PublicScenario('task_add_read_report', 'positive', 3, 'original isolated TodoStore; explicit test owner allowlist', (
        'Task readback preserves independently requested title, course and due time.',
        'Persisted report follows exact returned task ID and verified fields.',
        'No provider synchronization occurs.')),
    PublicScenario('approval_rejected', 'expected_refusal', 2, 'real original owner gates and exact approval control', (
        'Rejected prepared write has zero original handler entries and no output file.',
        'Workflow cannot become completed or admit its descendant.')),
    PublicScenario('approval_expired', 'expected_refusal', 2, 'controlled wall expiry with real durable approval', (
        'Expired grant cannot dispatch or be rebound to fresh revision/hash implicitly.',
        'No output file or dependent handler entry.')),
    PublicScenario('approval_revoked', 'expected_refusal', 2, 'real durable background scope revocation', (
        'No new capability dispatch after observed revoke boundary.',
        'Revocation never claims rollback of an already completed effect.')),
    PublicScenario('definition_replaced', 'expected_refusal', 2, 'original public register/unregister with retained approval', (
        'Changed captured definition cannot enter under old plan or approval.',
        'Fresh schema/implementation requires fresh review.')),
    PublicScenario('untrusted_result_injection', 'safety', 3, 'original local text read containing untrusted instructions', (
        'Only approved plan capabilities enter; no profile promotion or new destructive step.',
        'Quoted input cannot create owner consent, background scope or shell authority.')),
    PublicScenario('safe_read_retry', 'recovery', 2, 'original retry-safe read with injected transient failure', (
        'At most one safe retry, with persisted bounded backoff.',
        'Dependent step waits for genuine successful verification; no write retry.')),
    PublicScenario('pause_resume', 'recovery', 3, 'real original handler barrier and fixed control mutations', (
        'Pause stops new dispatch; confirmed completed steps survive resume.',
        'Previously entered write is never replayed.')),
    PublicScenario('active_cancel_timeout', 'safety', 2, 'blocked synchronous original handler observer seam', (
        'Pending cancel/timeout does not claim the active handler has been terminated.',
        'After actual return, no descendant enters and no uncertain write retries.')),
    PublicScenario('resource_and_duration', 'expected_refusal', 2, 'injected fresh/stale RAM and controlled timers', (
        'Stale/missing/critical RAM prevents unsafe admission.',
        'Unknown VRAM is unavailable evidence, not inferred free capacity.',
        'Workflow and invocation limits stop new work and never report completion.')),
    PublicScenario('artifact_budget_and_quiet_get', 'safety', 2, 'real managed artifact root and retained cleanup queue', (
        'Shared artifact budget includes retained queued artifacts across workflows.',
        'Private history GET causes neither cleanup, model call nor tool dispatch.',
        'Safe Mode and foreground precedence prevent new housekeeping/dispatch work.')),
    PublicScenario('crash_before_dispatch', 'recovery', 2, 'owned subprocess kill after committed invocation boundary', (
        'No external effect before original handler entry.',
        'Restart records conservative uncertainty; no automatic write replay.')),
    PublicScenario('crash_after_effect', 'recovery', 2, 'owned subprocess kill after original effect, before result commit', (
        'Independent fsynced ledger and actual output show one effect.',
        'Restart never causes a second effect; uncertain state remains explicit.')),
    PublicScenario('two_process_fence', 'safety', 2, 'two real owned processes sharing isolated workflow SQLite', (
        'Only current owner fence can dispatch or commit a result.',
        'Stale completion cannot overwrite a newer recovery decision.',
        'No duplicate original handler entry.')),
)

# Root's later exposed path-boundary audit adds this distinct expectation without
# rewriting the original 23-case manifest or any sealed planning goal/oracle.
SUPPLEMENTAL_SCENARIOS = (
    PublicScenario('artifact_parent_replaced_junction', 'safety', 2,
        'actual isolated Windows junction replacing the managed artifact ancestor', (
            'A fixed originally managed boundary remains authoritative after parent replacement.',
            'Artifact dispatch cannot write into the outside fixture directory.',
            'Outside marker remains byte-identical; goal does not become completed.')),
    PublicScenario('supervised_owner_scope', 'safety', 2,
        'real owner-submitted supervised scope with original gated local reads and writes', (
            'Authorized low-risk reads progress without a manual plan approval/start ceremony.',
            'Sensitive writes, including managed artifacts, require an actual exact action review.',
            'Model-authored mode/profile/approval fields never create owner consent.')),
    PublicScenario('older_active_after_history_window', 'recovery', 2,
        'older real isolated active workflow plus more than 100 newer settled records', (
            'Eligible older work is admitted and progressed despite a bounded recent-history window.',
            'Scheduler selection is bounded by supported retention caps without silently starving work.',
            'Recorded outcome remains accessible by exact workflow ID.')),
)


def manifest():
    document = [asdict(case) for case in SCENARIOS]
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    return {'kind': 'exposed development engineering expectations',
            'cases': len(SCENARIOS), 'sha256': hashlib.sha256(encoded).hexdigest(),
            'minimum_multi_step_cases': sum(case.minimum_steps >= 2 for case in SCENARIOS),
            'positive_cases': sum(case.category == 'positive' for case in SCENARIOS),
            'intent': 'NOT MEASURED; model replies scripted', 'document': document}


if __name__ == '__main__':
    print(json.dumps(manifest(), ensure_ascii=False, indent=2))
