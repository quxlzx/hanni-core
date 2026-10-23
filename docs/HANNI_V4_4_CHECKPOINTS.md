# HANNI V4.4 validation checkpoints

Baseline: `80ab843` on `codex/hanni-v3.7-distributed`, package `0.13.0`.
Exactly three actual agents participate: Manager, Engineer and Independent
Verifier. The verifier does not edit production code. This milestone validates
and repairs the existing system; it adds no major feature. No commit or GitHub
publication is automatic.

Private artifacts stay under ignored `data/v44-manager`,
`data/v44-engineering` and `data/v44-verification`. Native PNGs remain local
ignored artifacts. Five pre-existing unrelated untracked root files are outside
this task. External assistant/model processes remain independently owned.

| Milestone | Current state |
| --- | --- |
| M0 inventory and baseline | Complete; current source/configuration and endpoint inventory, 127 fresh focused baseline tests |
| M1 model routing evaluation | Complete evaluation; 432/432 controlled eligibility outcomes, actual fixed/adaptive 2/8 each; no live correctness gain |
| M2 collaboration evaluation | Complete bounded evaluation; seven guard invariants pass, four verified outputs; live collaboration blocked |
| M3 distributed inference stress | Complete controlled evaluation; 29 independent safety cases pass; physical remote stress blocked |
| M4 workflow integration | Complete evaluation; controlled core passes, actual original-planner objectives 0/2, zero verified steps |
| M5 Model Lab and desktop review | 26 native checks pass; visual 8.7/10, template 1.2/10; six real development Lab responses and export/comparison verified |
| M6 defect repair | Second production freeze verified by 342 relevant tests; nine reproduced defect families repaired |
| M7 independent full regression | Complete; 2,086 passed, 25 subtests passed, two documented skips; source-matched 0.14.0 wheel verified |
| M8 final acceptance and documentation | Complete assessment/documentation; final status PARTIAL with actual blocked and failed objectives retained |

## M0: inventory and initial evidence

The tracked repository starts clean at V4.3 commit `80ab843`. The preceding
source-matched V4.3 full regression passed 2,035 tests and 25 subtests with two
documented skips. That is historical baseline evidence, not a new V4.4 test.
The manager executed a fresh focused original workflow, memory, LAYA and
MCP baseline: **127 tests passed in 50.96 seconds**, with no failures or errors.
Its separate XML record is `data/v44-manager/core-baseline.xml`. These exercise
the real isolated service and handlers with controlled model/provider seams;
they are not live model intelligence or deployed external-provider evidence.

Source inspection confirms the original V3 workflow service binds the original
MCP host and registry, durably fences invocations and review grants, and attaches
the adaptive model client and collaboration engine. Dashboard workflow resource
admission requires recent actual RAM telemetry. Memory context and advisory
data do not grant tool authority.

Fresh deployment configuration requests assisted workflows, two parallel reads,
two active workflows and at most one safe retry. Memory is enabled; enhanced
context is disabled. LAYA advisory and retrieval are disabled, and remote text
and stored-memory sharing are disallowed. MCP is enabled and read-only, with
three bounded model tool rounds. Adaptive policy is balanced with at least 20
graded category samples and a 0.7 Wilson lower-bound threshold. Requested
configuration alone is not evidence of active LAYA model quality.

The verifier's fresh original protected inventory reports the configured local
supervisor healthy and all three Athena/Strata remote workers unhealthy. Fresh
private provenance confirms the existing original local model and launcher
identities; protected properties report 16,384 allocated context. The initial
host sample reports 75.3% RAM usage and an 8,151 MB RTX 5060 Laptop GPU. Live
dispatch must preserve original resource guards and its one serving slot.
No remote service is started, authentication policy changed or process stopped.
Unavailable remote endpoints block live multi-model and remote stress evidence;
controlled transports cannot substitute for that evidence.

Acceptance objectives are predefined: correct eligibility/selection in at least
95% of controlled cases, zero unauthorized remote dispatch, no duplicated
consequential actions, authoritative workflow outcome verification, bounded
cancellation/recovery, accurate metadata and native visual quality above 8.5
with template appearance at most 2. Fixed/adaptive/collaboration correctness
and timings retain separate denominators and scopes. Live superiority must be
measured on equivalent independently frozen cases; no aggregate fixture pass
rate or single available model can establish it.

The independent verifier owns a privately frozen final set and its oracles.
Development repair uses separate cases. Existing final holdout corpora are not
opened or tuned against. Critical safety failures override all quality scores.

## M6: pre-repair reproduction checkpoint

The engineer retained four failing isolated regressions before production edits:
structured-output schema bytes were omitted from direct scheduler context
admission; a late transport response after cancellation could be admitted; and
unknown remote RAM/VRAM did not prevent dispatch. Evidence is in
`data/v44-engineering/pre-repair.xml`. Production ownership is initially limited
to `src/hanni/compute/scheduler.py`, with smallest safe repairs and independent
re-verification required. CPU-only workers must not require GPU telemetry.

## M1: controlled routing checkpoint

The engineer froze the controlled campaign manifest before execution. Its
eligibility grid passed **432/432** cases: nine request classes, four policies,
six privacy classes and two local-only states. This is a deterministic controlled
grid, not 432 independent real-model accuracy samples. Predefined isolated
recovery tasks succeeded **3/6 with fixed placement** and **4/6 with adaptive
placement**. The sole gain is authorized fallback during a scripted primary
outage. There were zero unauthorized remote calls in this campaign. No live
intelligence, GPU throughput or speed improvement follows from these fixtures.
Private records are under `data/v44-engineering/controlled-campaign-20261009-a`.

The independently frozen final live protocol contains eight model-only paired
cases with alternating fixed/adaptive order, exact JSON criteria and no retry
for final scoring. Protocol SHA256 is
`ffd28d3c7ecdde3b0efc7a117b534582751c9ede8d9e8162468591432c322241`.
Its private oracles are not available for production tuning. Execution waits
for the final source freeze and a quiet validation interval.

## M2: controlled collaboration checkpoint

Seven controlled scenarios passed: correct agreement, incorrect agreement,
disagreement, incomplete output, conflicting interpretations, missing evidence
and endpoint failure. Consensus did not replace source verification. These
scripted participant responses establish guard behavior, not live multi-model
quality or a measured collaboration benefit. Actual secondary endpoints remain
unavailable, so live collaboration acceptance is blocked.

## M3: controlled failure and security checkpoint

Fresh independent probes reproduced a result admitted after protected compute
authorization was withdrawn during transport. The engineer repaired that
boundary without reclassifying authorization withdrawal as worker failure.
An expanded independent matrix subsequently passed **22/22** cases, including
protected worker categories, model identity and enablement revoked on disk
before dispatch or during transport. Pre-dispatch cases require zero transport
calls; returned output cannot restore permission. Separate engineer regressions
also reproduced and repaired cancellation at admission and GPU startup identity
without a human-readable GPU label. All resulting fixes require final focused
and independent re-verification. No actual private context was transmitted by
the controlled reproduction; no real remote worker was contacted.

## M4: actual workflow development checkpoint

The first real original-planner task asked for an owned private JSON read,
evidence analysis, managed report and readback. It **blocked before any tool
action**, with zero verified steps: the model omitted the explicit source path
from its file-read step description despite the existing verbatim-path prompt
instruction. The original capability resolver safely refused the incomplete
step. No canned plan substituted for this failure and no permission was widened.
This is an actual planning limitation; the original controlled workflow passes
do not make it a successful autonomous task.

## M6: repaired production freeze checkpoint

Engineer production changes are limited to the original scheduler. They count
bounded, credential-safe response schemas in context admission; refuse unknown
remote resource reserves while permitting genuine CPU-only workers; recheck
protected authorization, worker identity and capacity at dispatch and returned
result boundaries; and withdraw further admission after cancellation at either
original controller callback. Cancellation and authorization withdrawal do not
falsely make a healthy worker unhealthy or authorize fallback/replay.

The final relevant regression passed **335 tests**, with zero failures, errors
or skips, in **91.664 seconds**. Eighteen dedicated engineer cases cover the
reproduced defects and callback boundaries. XML evidence is private at
`data/v44-engineering/repair-final.xml`. The controlled campaign reran against
the frozen source with the same objectives and outcomes; its final artifacts
are under `data/v44-engineering/controlled-campaign-20261009-b`.

Frozen scheduler SHA256:
`035da86edc0b0068ffd0d26c39d22fb64ec4bc371a70dd3dded4a51e833cc96a`.
Manager release version is `0.14.0`; frontend production source/assets are
unchanged. All **41 frontend tests** passed and TypeScript checking passed.
No final holdout oracle was used to produce these repairs. The verifier will
reopen its current-source bounded helper before final live cases. Full regression
is deferred until the quiet timed live interval finishes.

## M1/M6: actual refresh defect and second repair cycle

The first final campaign exposed a separate original refresh/freshness defect:
synchronous adaptive refresh sampled local health before long failed remote
health/resource checks. Those checks outlasted the unchanged 30-second local
heartbeat lease. The first two captured arms were safely blocked with no model
dispatch, even though an original direct protected health check showed the
primary healthy. These are admission failures, not incorrect model answers.
The verifier preserves the interrupted attempt and marks unexecuted cases
NOT TESTED; it does not silently retry the original one-shot final protocol.

The engineer independently reproduced the general defect with a controlled
35-second remote delay. The repair genuinely probes local health after remote
refresh, without rewriting sample times or increasing the 30-second trust lease.
The regression also advances another 31 seconds and requires refusal again.
Failing evidence is private at
`data/v44-engineering/pre-slow-refresh-repair.xml`. Production repair ownership
now includes `src/hanni/models/adaptive.py` as well as the scheduler. The first
freeze remains historical evidence; a new independent source freeze and live
campaign are required for final acceptance. No final expected answer was used
to diagnose or repair this infrastructure defect.

## M6: second repaired production freeze

The independent verifier reconciled the interrupted first final campaign:
**seven arms BLOCKED, nine arms NOT TESTED, zero actual model responses or
model telemetry**. It preserved every captured result. The validation helper
had no per-case cancellation hook, so cleanup required abrupt termination of
only that receipt-verified owned helper. Its listener and two receipt-verified
transient SSH CLI processes are gone. The external model and original assistant
launcher retain their original process identities. The next harness checks stop
markers at safe case boundaries. A distinct sealed postrepair set will be scored
separately rather than silently retrying the first protocol.

Further controlled reproduction found remote resource connection failures could
abort synchronous discovery or the original health monitor. The scheduler now
skips resource connections after unhealthy health observations; a bounded
resource error clears stale capacity, GPU, hardware and sample-time fields
without ending discovery. Unknown remote capacity remains inadmissible.
The refresh-order repair obtains genuine local health after slow remote checks
and preserves the original 30-second trust interval.

The current-source relevant suite passed **342 tests**, no failures, errors or
skips, in **97.739 seconds**. It includes 22 engineer regression cases and 25
independent security cases. Evidence is
`data/v44-engineering/repair-refresh-complete.xml`. Current-source controlled
campaign `controlled-campaign-20261009-c` retains 432 valid eligibility outcomes,
seven collaboration guard passes, four verified collaboration outputs and fixed
3/6 versus adaptive 4/6 scripted recovery. Fixed exhaustive fixtures do not have
a meaningful statistical confidence interval.

| Final repaired source | SHA256 |
| --- | --- |
| `src/hanni/compute/scheduler.py` | `cc3d5afc20d3f8261b5e551532d21f424c4dac242956152b1378f5b4fee6dd6d` |
| `src/hanni/models/adaptive.py` | `4489ba3b691970bd25728fd27ec909baf3c1e06fe66348e162d5ccde0f240370` |

Production is frozen for independent live evaluation. Version is 0.14.0;
frontend source and assets remain unchanged and their 41 tests and TypeScript
check already passed. No oracle, final answer, permission, model or serving
configuration was changed by either repair cycle.

## M1/M3: independent second-cycle checkpoint

The independent repaired matrix passed **29/29 checks**. Additional cases
verify a genuine local health sample after a 35-second remote delay, renewed
refusal after another 31 seconds, no resource reconnection after failed health,
clearing stale capacity after a resource connection fault, and the original
monitor surviving the fault and reaching a later real observation without an
artificial halt. Evidence: `data/v44-verification/security-monitor-final.xml`.

A distinct postrepair final set contains eight new paired cases, 16 arms. Its
privately frozen protocol SHA256 is
`f675c0442b3d420739b51958cd1f7cb46a2f14e2039db0e2ac07af9cc91a95d9`.
No original final case is reused and no model oracle was exposed to engineering.
The current-source owned helper started a quiet one-shot execution interval;
the manager defers full regression and package work until timed inference ends.

## M1: final live response checkpoint

The distinct postrepair quiet interval completed all **16 genuine dispatches**.
Fixed and adaptive each passed **2/8 exact tasks**, with five original
structured-verification rejections and one accessible incorrect coding answer
per mode. There are six accessible actual answers, four exact passes and ten
rejected outputs. Raw rejected text is unavailable from the original engine's
error return; original error/decision/identity/usage/performance evidence is
retained, while factual accuracy of those missing texts is unknown. No final
retry, oracle edit, parser relaxation or production tuning occurred.

There are no discordant paired outcomes and no demonstrated adaptive correctness
gain. Execute-only fixed P50/P95 are 685.84/1,332.73 ms; adaptive P50/P95 are
614.15/792.06 ms. These descriptive shared-endpoint measurements exclude prior
remote discovery and do not establish a causal speed improvement. The original
seven blocked arms and nine untested arms remain separate infrastructure-cycle
evidence. Full regression started only after this competitive timing interval.

## M7: release package checkpoint

The 0.14.0 wheel built without dependency downloads. Its 196 HANNI source/static
files match current source byte for byte, 12 runtime modules import directly
from the archive, and current UTF-8 README/version, Model Lab assets and the
local Geist font/license are present. Deployment data/configuration, model
weights and keys are excluded. Size: 898,967 bytes. SHA256:
`78f24f47dae4d3bddbb41227dfd7f0b812570f715ce81a4dfbf0e9da45fc66f4`.
Evidence: `data/v44-manager/package-verification.json`.
Native review and full regression are still in progress at this checkpoint.

## M4/M5: actual workflow and native checkpoint

The second original-planner development task returned the correct first source
path but malformed literal `$ref` strings for content and the resulting read
path. Predeclared review rejected the resulting unrelated path and cancelled
the plan before tools. Both development objectives are incomplete, **0/2**, with
zero verified steps and original plans/review/cancellation evidence preserved.

The actual native client passed **26 checks** across Model Lab, Cluster,
Workflows, Model Routing, Home, Conversation and Settings, at 1366×768 and
900×650. Fifteen fresh screenshots are under
`data/v44-verification/native-20261009-e`; the earlier genuine runner screenshot
is retained separately. Independent visual score **8.7/10** and template score
**1.2/10** meet the requested thresholds. The manager separately inspected all
seven large-window screens and the narrow Model Lab view and agrees. No
frontend production change was needed.

Original native conversation processing stored a private owner-explicit
preference and the model recalled it; an irrelevant verification caveat is a
disclosed response-quality limitation. The private memory fact survives original
store reopening with its provenance. Conversation history persistence is NOT
TESTED because the helper ChatHub is intentionally ephemeral. Two actual Lab
development runs produce six responses; inspection, actual disk export checksum
and matching-run comparison pass. They are not the sealed final 16-arm suite.
The initial comparison request and read-only supplement attempts exposed harness
mistakes; their records remain separate and no rejected request is a production
pass or hidden model retry. The completed supplement projects unavailable-node
controls without actual reboot, sleep or SSH dispatch.

## M7: final full regression checkpoint

Fresh full regression passed **2,086 tests and 25 subtests**, with **two skips**,
in **360.15 seconds**. There are zero failures/errors. Skips: historical local
inference ledger not included; installed `hanni` command absent from PATH.
Evidence: `data/v44-manager/final-regression.xml` and
`final-regression-summary.json`. Compilation and `git diff --check` pass.
The manager rechecked all 196 source/static files against the built wheel and
its SHA256 after testing; neither production source nor archive changed.

## M8: independent cleanup checkpoint

The manager independently verified exact identities of all **five** owned
validation backends are gone and none of their HTTP ports has a TCP listener.
All **six** native-window process receipts are closed. Original local model and
assistant launcher retain PID/create-time identities and the original model
command hash. Receipt-verified transient CLI children from the interrupted
campaign are absent. The initial helper's abrupt termination remains disclosed.
Evidence: `data/v44-manager/independent-cleanup.json` and
`independent-native-cleanup.json`; no unowned service or process was stopped.

The final status is PARTIAL: repairs, controlled regression and native visual
targets pass, while actual remote comparison and successful multi-step planning
remain unproven. The [final validation](HANNI_V4_4_FINAL_VALIDATION.md),
[independent acceptance review](v44-reviews/INDEPENDENT_REVIEW.md),
[benchmark report](v44-reviews/BENCHMARK_REPORT.md),
[native UI review](v44-reviews/UI_REVIEW.md) and
[live results ledger](v44-reviews/LIVE_RESULTS.md) are complete and reconciled.
No stage, commit or publication is automatic.
