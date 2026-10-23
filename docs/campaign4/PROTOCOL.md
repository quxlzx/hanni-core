# Campaign 4: autonomous workflow stress test

Baseline: `0aede83`, branch `codex/hanni-v3.7-distributed`.

No separate common campaign instruction document was located. The recorded
isolation, evidence, independent verification and checkpoint rules from
Campaigns 1 through 3 apply alongside the user's Campaign 4 requirements.

The manager coordinates two actual engineering agents and an independent
verification agent. Development prospectively annotates at least 120 new
controlled scenarios, with at least six in each of the twenty requested
categories. Before production repairs, the verifier privately authors and
seals at least forty separate scenarios, at least two per category. Engineers
and the manager do not inspect their inputs or oracles. The final evaluation
runs once after an explicit whole-source freeze. Exposed development failures
may guide architectural repairs; held-out answers may not.

## Isolation and execution boundaries

Tests use original WorkflowService, WorkflowStore, WorkflowPlanner, permission
guards and verification code with disposable databases, synthetic requests,
and campaign-owned directories. Actual safe local implementations run where
possible. Controlled model replies and leaf dependency failures establish
protocol and execution behavior, never actual model goal understanding or
planning quality. Those semantic claims require separate native, guarded
model inference and reference evaluation. Resource admission refusals are
reported as blocked, not successful model responses.

No campaign code opens or changes the owner's workflow or memory database,
configuration, secrets, default model, external approvals, or remote nodes.
The actual Windows computer and unrelated processes must not be interrupted.
Subprocess crash/restart tests control only children created by their runner.
Prior private holdouts and unrelated untracked files remain untouched.

The special challenge must use a real process boundary: persist progress,
experience a controlled worker failure, exit an owned test-runner child, start
another child against the same isolated database, inspect recovered state,
explicitly resume under existing approval rules, finish remaining work, and
read back the report. A durable invocation and side-effect ledger must show
that verified steps were not repeated. An uncertain prior write must remain
blocked from automatic replay.

## Coverage and measurements

Scenario categories are the twenty named in the user request. Inventory is
derived from the current transition map and actual planner, scheduler,
approval, lease, dispatch, result persistence, verification, control and
recovery boundaries. Direct-store atomicity/state-transition probes are
reported separately from transitions reached through the native scheduler.
Merely enumerating an edge does not establish tested coverage. Before/after
fault probes must retain receipts, expected outcomes, actual outcomes and
unreached boundaries. Exceptions must not manufacture a false success.

Verified completion rate uses only workflows prospectively expected to
complete with verified steps and evidence. Correct planned refusals,
cancellations, pauses, partial outcomes and uncertain writes are separate
outcome metrics. Recovery success uses the annotated recoverable subset;
intentional uncertain-write blocking is separately measured. Checkpoint
correctness compares persistent records, invocation identities, step status,
approvals and artifacts across interruption. Cancellation correctness requires
no new dispatch after admission withdrawal; synchronous calls already in
progress may return and remain explicitly visible until then.

Duplicate consequential writes count repeat implementation side effects for
the same logical operation, using stable operation IDs and durable audit
readback. Unauthorized sensitive operations count actual dispatch and effects,
not simply refused requests. Partial completion accuracy compares reported
state and verified evidence against the annotated achieved/unfinished work.
Workflow P50/P95 duration includes each recorded outcome, with sample counts
and separate completion/recovery subsets; injected waits are disclosed.

Acceptance requires at least 100 reproducible scenarios, documented outcomes
for all categories, zero unauthorized sensitive operations, zero duplicate
consequential writes, independently reproduced repairs, and a verified real
test-runner restart challenge. Model-quality and unreached-transition
limitations remain explicit. No critical existing workflow regression may be
hidden by the new suite.

Completed implementation/verification cycles record source and corpus hashes,
commands, results and unresolved limitations. Final reports distinguish
baseline from repairs, controlled dependencies from live implementations, and
development outcomes from untouched independent verification.
