# HANNI V4.1 implementation checkpoints

Request: multi-model collaboration through the authoritative V3 workflow engine.
Source baseline: `9cebd2b` on `codex/hanni-v3.7-distributed`.

Exactly three actual agents are assigned: manager, backend engineer, and
independent verifier. The verifier owns live inference sessions and outcome
oracles; it does not edit production code. No model downloads, primary-model
replacement, or GitHub push are authorized by this implementation.

## M0: architecture and baseline

The repository audit confirmed that `WorkflowService` owns workflow admission,
dependencies, leases, durable invocations, recovery, and outcome verification.
`AdaptiveModelEngine` selects measured endpoints and uses the existing
`ComputeScheduler` for remote inference. The MCP host remains the only tool
execution path. LAYA and recalled context retain their existing privacy scopes.

Workflows already have an authenticated dashboard interface and persisted
checkpoints. Collaboration will extend those interfaces, rather than add a
workflow controller or a scheduler.

Focused baseline: 132 tests passed, no failures/errors/skips, in 9.361 seconds.
Evidence: private `data/v41-manager/baseline.xml`. This covers existing adaptive
routing, workflow service/store, and outcome verification. The independent
verifier will separately establish endpoint availability and seal fresh paired
benchmark tasks before inspecting their model responses.

Independent M0 routing/adversarial regression: 130 tests passed, recorded in
private `data/v41-verification/m0-routing.xml`. The verifier sealed a new protocol
with 16 synthetic cases across the eight requested categories before inference;
SHA-256 `95969febedfa24233c4dc23cd454658c03354c11bf98910b3756f1cd18f54818`.
The fixed original 4B baseline passed 7/16 exact outcome oracles, with 313 reported
generated tokens across 16 actual endpoint calls. This is the fixed-primary
baseline, not a claim about V4 sequential fallback or broader task accuracy.

Existing remote workers permit synthetic context only. Ordinary workflow
descriptions, criteria, and source results retain conversation/sensitive and
source-specific privacy categories; a comparison preference cannot loosen them.
Unrelated untracked user reports and the patch ZIP remain untouched.

## Milestone disposition

| Milestone | State |
| --- | --- |
| M1 bounded parallel inference | Implemented and verified |
| M2 structured result aggregation | Implemented and verified |
| M3 measured specialist assignment | Implemented and controlled verification complete |
| M4 independent review and conflicts | Implemented and verified |
| M5 V3 invocation/checkpoint integration | Implemented and controlled verification complete |
| M6 existing Workflows interface | Final browser review passed; manual score 8.8/10 |
| M7 independent single-versus-multi evaluation | Real baseline/routine complete; paired benefit acceptance blocked |

Each milestone requires implementation evidence and verification before its
checkpoint is marked complete. Acceptance requires a measured benefit on at
least one predefined complex task category; model agreement is not proof.

## M1, M2, and M4: implementation cycle 1

The backend engineer's dedicated collaboration suite passed 21 tests. A two-party
barrier proves overlapping inference on distinct pinned endpoints. Original
router eligibility, compute admission, fixed output budgets, cancellation, and
lease errors remain in the path. Participant results preserve endpoint identity,
input/context references, outputs, original evidence checks, measured timing,
reported usage, and available resource observations.

Aggregation selects independently checked evidence without treating agreement
as proof. Tests retain disagreements, reject unauthorized private sharing, and
preserve a primary when a secondary fails. Review uses one additional bounded
round and remains advisory; malformed review recovers safely. Persistence errors
are not hidden as endpoint failures. Single/default-auto dispatch no extra model.
These are controlled adapter tests, not real performance claims.

Actual dashboard HTTP integration passed two further tests covering all five
preferences, token/Origin enforcement, durable identical-request replay, rejection
of a changed preference with the same request ID, invalid JSON preference types,
and rejected attempts to inject sharing categories or tool authority. Planning
and RAM are disclosed fixture seams; routing, hub, service, and SQLite are real.
Evidence: private `data/v41-manager/dashboard-integration.xml`.

M3 tests demonstrate that distinct specialist assignments require graded category
evidence, without inventing expertise from model labels. Authoritative source
partition integration and persistence envelope checks remain under implementation.

## M3 and M5: implementation cycle 2

The final engineer batch passed 133 tests: 24 dedicated inference collaboration
checks, 10 authoritative workflow collaboration checks, and existing adaptive,
store, and service regressions. Production code was frozen before the manager's
full regression and package build.

Specialist analysis partitions already-declared verified source IDs into distinct
bounded assignments. Endpoint choice requires sufficient graded category evidence
and the original privacy/context/resource checks. Per-group evidence is checked,
then merged observations cross the original whole-step acceptance verifier.
Cross-source calculations that the partition cannot establish remain unverified.
The V3 dependency graph owns decomposition and prerequisite execution.

Actual original-controller tests exercise isolated real file reads, three
comparison preferences falling back for synthetic-only remote workers, original
report verification, durable progress/source references/reported usage, unchanged
ordinary-auto dispatch, invalid preferences, immutable preferences, and fenced
restart recovery of interrupted partial results without replay. Current real
category profiles do not justify specialist expertise, and private remote sharing
remains unauthorized; the UI therefore records the fallback honestly.

Persistence reserves space inside the existing result envelope and bounds each
serialized participant's output, evidence, and metadata. Saved telemetry retains
raw output once per participant and references the selected result. Oversized
secondary output/evidence tests preserve a usable primary. Actual review input
hashes and specialist source references survive aggregation.

## Independent backend cycle

Independent adversarial checks passed 29/29: private scopes across requested
patterns, unknown resources, response identity mismatch, advisory-only agreement
and review, revoked admission/cancellation, bounded secondary recovery, routing
database privacy, token bounds and unknown usage, and inherited specialist privacy.
These tests use controlled adapters; they do not establish real model gains.

Five sealed routine lookups, each run fixed-primary and auto, passed 10/10 exact
checks with one participant and zero remote inference calls. Median response time
was 251.65 ms fixed versus 212.85 ms auto. Fixed-first ordering warms caches, so
this is no evidence of a speedup; it shows no additional model dispatch on those
routine requests.

Package `hanni-0.11.0-py3-none-any.whl` built without downloads. Archive imports of
collaboration, adaptive, workflows, and compute passed, every packaged runtime
and static file matched the workspace, private data/config were excluded, and
the local inline Geist font/license remained present. Initial release SHA-256:
`4ba343f05fab5a7a8aa0eda25ab0e93a5ca7799ef40a2339e0f3d891258ce56d`.

## M7: live evaluation status

The fixed-primary baseline is complete. The verifier loaded existing P40/P6000
helpers, then a fresh supplemental preflight encountered failed authorized SSH
connections over both configured LAN and Tailscale paths. Fresh worker resource
telemetry was unavailable, so dispatch stayed blocked. The original Strata
service remains untouched. The verifier is continuing bounded reconnection and
independent controlled checks without requesting user action or weakening
authentication/resource/sharing guards. No collaboration benefit is claimed at
this checkpoint.

## M6: Workflows presentation cycle 1

The existing goal form accepts the fixed model analysis preferences without
changing autonomy or tool approvals. Workflow details show real backend receipts
with assignments, state, timing, output, checks, disagreements, and final evidence.
Optional input/source SHA-256 receipts can be inspected without duplicating
private source results. Unknown tokens and duration remain explicitly unmeasured.

TypeScript and Vite build passed; 35 existing frontend behavior tests passed.
Independent Edge browser review passed 12/12 checks at 1440×900, 900×650, and
640×700. The verifier inspected screenshots and scored the design 8.8/10.
No document overflow, JavaScript errors, or external requests were observed.
Empty, running, failed-secondary, missing-usage, full-output, and stale-transport
states were checked. These screenshots use an explicitly disclosed synthetic
display fixture; they are not live inference or native desktop evidence.
Evidence: private `data/v41-verification/browser-cycle3`. Source receipt details
were added after that first build and require the final browser recheck.

## Final implementation and verification checkpoint

The full repository suite passed **1908 tests, with 2 skips and 25 passing
subtests**, in 290.02 seconds. Private JUnit evidence:
`data/v41-manager/final-regression.xml`. A narrow recovery metadata correction
was made after this suite loaded its modules: abandoned invocation telemetry now
matches the interrupted step telemetry. The final focused run passed **104
tests**, including the corrected store/recovery paths, independent security,
dashboard HTTP integration, and all 35 dedicated collaboration/workflow checks.
It also includes one genuine specialist-source integration test added after full
suite collection. Evidence: `data/v41-manager/final-focused.xml`.

All 35 frontend behavior tests passed. TypeScript/Vite, compile checks, and
`git diff --check` passed. Final independent browser recheck again passed 12/12
checks, with manual visual score 8.8/10. Final static SHA-256:

- `app.js`: `934e5f966cd4fb2f8778165dbf529b547a4677280d15ec66aa4ccf4a56fd5bba`
- `style.css`: `71d94d84d0fd31c0cd50c293c30cd30d50a08ed95d272a26741c16577f255d58`

The final wheel was rebuilt after the recovery correction. All ten package
checks passed, including archive imports and exact packaged-source/static match.
Artifact: private `data/v41-manager/release-final/hanni-0.11.0-py3-none-any.whl`,
867951 bytes, SHA-256
`b94cbf4ad8fb0521c4f39d3aa6a98a98bfc643b6504598e3756ac93490847f23`.
Evidence: `data/v41-manager/package-final-verification.json`.

## M7: final blocked disposition and cleanup

The primary baseline, live routine checks, independent security checks, and
fair three-mode comparator protocol are complete. Fresh authorized Athena SSH
and resource sampling failed before any paired complex-model calls. Therefore
the requested measurable benefit in a predefined complex category is **not
demonstrated**. Automatic collaboration remains disabled; the primary and
sharing policies were preserved. See the [benchmark comparison](HANNI_V4_1_BENCHMARK_COMPARISON.md)
and [independent review](v41-reviews/INDEPENDENT_REVIEW.md).

The local benchmark helper exited and its shutdown was verified. Nonce-checked
stop attempts for the two owned GPU helpers could not authenticate. Their
existing owned HTTP tunnels still returned readiness after that attempt, so the
remote helpers may remain running. Local helper/tunnel cleanup finished; remote
shutdown is unverified. Private PID/nonce receipts are retained for safe later
reconciliation with `scripts/v41_verification/cleanup_owned.py`. No unrelated
server was targeted; original Strata was preserved.

The future GPU helper attempts a finite PID/nonce expiry guardian, but installing
it requires a separate authenticated call after startup. That installation gap
remains and no expiry guarantee is claimed; no guardian was installed
retroactively on the current helpers. Further hardware calls stopped after the
bounded diagnosis/cleanup attempts, honoring the user's preference to continue
without requiring additional user action.

Implementation is ready for review. Performance acceptance remains blocked by
external access and missing paired evidence, not fulfilled by scripted tests.
The user subsequently authorized a local commit. No push was requested or
performed. Unrelated user files remain untouched, and private evidence remains
ignored.
