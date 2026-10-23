# HANNI V4.4 — FINAL VALIDATION

Validation date: October 9–10, 2026. Baseline commit: `80ab843`.
Release: `0.14.0`. **Final assessment: PARTIAL.** Controlled regression, the
repaired safety boundaries and native visual review pass. Actual remote
multi-model comparison and successful autonomous planning remain unproven.

Exactly three actual agents participated: Manager, Engineer and Independent
Verifier. The engineer repaired original production paths; the verifier owned
separate security tests, sealed live cases, real-controller workflow checks and
native screenshots. No final oracle was provided for production tuning. No
major feature, model download, endpoint override, permission expansion, service
restart, automatic commit or publication occurred.

**Adaptive Model Routing:** PARTIAL. Controlled eligibility is 432/432 valid
outcomes, exceeding the 95% fixture target. Actual paired task success is 2/8
in each mode, with no demonstrated live improvement.

**Model Collaboration:** PARTIAL. All seven controlled guard invariants pass;
only four selected outputs are independently verified. Actual multi-model
collaboration is BLOCKED by unavailable secondary endpoints.

**Inference Performance:** PARTIAL. Original queue, cancellation, recovery and
resource guards pass controlled regression. Actual local timings are measured;
physical remote stress and model-to-model performance comparisons are BLOCKED.

**Distributed Worker Health:** BLOCKED for actual P40, P6000 and Wonyoung Strata
health/inference evidence. The original local primary is healthy. No services
are started to turn an unavailable endpoint into a test pass.

**Workflow Integration:** PARTIAL. Original isolated controller regression
passes, but both actual original-planner development objectives fail before
consequential tools: one blocked plan and one cancelled plan, zero verified
steps. No end-to-end autonomous success is claimed.

**LAYA Compatibility:** PARTIAL. Isolated compatibility passes. Advisory and
retrieval are disabled in deployment, so actual LAYA intelligence is NOT TESTED.

**MCP Compatibility:** PARTIAL. Original host/registry, permissions, schema and
malicious-description controls pass regression; actual native conversation uses
the original MCP/TextSession pipeline. External account/service integrations
remain NOT TESTED here.

**Model Lab:** PASS for exercised native functionality: two real development
runs/six responses, result inspection, actual disk export checksums and a matching
run comparison. Unavailable remote execution remains BLOCKED. This does not
declare every control or physical node action validated.

**HANNI OS:** PASS for the bounded native review. Twenty-six checks across seven
screens and two window sizes pass; visual quality 8.7/10 exceeds 8.5, template
appearance 1.2/10 is below 2. Existing backend/voice sessions are preserved.

**Security:** PASS for current tested boundaries: 29 independent adversarial
checks, zero unauthorized current dispatches, no duplicated consequential actions
and no critical safety failure in the 16 final arms. A genuine pre-fix permission
race was reproduced using synthetic transport and repaired; it is not erased
from the failure history. This is a scoped test conclusion, not an unbounded
security guarantee.

## Repair evidence

Nine defect families were reproduced before repair:

| Defect | Resulting behavior |
| --- | --- |
| Structured-response schema omitted from distributed context admission | Bounded credential-safe schema bytes count with input and output before dispatch. |
| A late response could survive cancellation | Cancelled output is discarded, receipts remain cancelled and the worker is not falsely marked unhealthy. |
| Unknown remote RAM/VRAM accepted as reserves | Remote dispatch requires known finite RAM and GPU capacity when a GPU is configured or measured; CPU-only workers need no GPU reading. |
| GPU startup identity without a display label evaded VRAM admission | The original startup GPU identity is part of the capacity requirement. |
| Protected scope withdrawn during inference still admitted a result | Deployment, worker identity, categories, capabilities, model and context are rechecked before admitting output. |
| Protected permission revoked inside admission still allowed dispatch | Authorization is reloaded before fetching the worker, then identity and current capacity are rechecked. |
| Admission callbacks could cancel yet dispatch/admit output | Cancellation is rechecked immediately after both original controller callbacks. |
| Slow failed remote discovery expired healthy local evidence before refresh returned | Actual remote checks precede a genuine fresh local probe; the original 30-second expiry remains in force. |
| Resource connection errors stopped discovery or its monitor | Failed sampling clears stale capacity; unhealthy health causes no second resource connection; the monitor survives the fault. |

Production changes are confined to `src/hanni/compute/scheduler.py` and
`src/hanni/models/adaptive.py`, plus release metadata. Frontend source and
compiled assets are unchanged. Every failure and subsequent repair cycle is
preserved separately in private evidence and [durable checkpoints](HANNI_V4_4_CHECKPOINTS.md).
See the [engineering report](v44-reviews/ENGINEERING_FINDINGS.md) for reproductions,
test commands and source hashes.

## Controlled results

| Scope | Current-source result | Interpretation |
| --- | --- | --- |
| Eligibility grid | 432/432 valid outcomes | Nine request classes, four policies, six privacy classes and two local-only states. Correct refusal counts as valid eligibility, never as completed inference. |
| Paired recovery fixtures | Fixed 3/6; adaptive 4/6 | The sole gain is authorized synthetic-context fallback during a scripted primary outage. This measures guarded availability, not live reasoning quality. |
| Collaboration guards | 7/7 invariants; 4/7 independently verified outputs | Wrong agreement remains failed; missing evidence stays unverified; failures and conflicts are retained. These denominators are distinct. |
| Focused repaired suite | 342 passed, no errors/skips; 97.739 seconds | Includes 22 engineer regressions and the then-collected 25 independent security cases. |
| Expanded independent matrix | 29/29 passed | Includes genuine health expiry and a monitor that reaches a later observation after resource failure. |
| Initial core baseline | 127 passed; 50.96 seconds | 64 workflow, 16 memory, 23 LAYA and 24 MCP checks through original isolated controllers with controlled provider seams. |
| Frontend | 41 passed; TypeScript check passed | Existing frontend source and packaged assets did not change during either repair. |

The original distributed/performance checks cover queue bounds, compatible FIFO,
interactive reserves, overlapping result association, cancellation, late output,
reassignment and durable interruption receipts. These are controlled original
adapter/controller tests, not physical remote GPU stress. The exhaustive fixed
fixture grid and six predetermined recovery conditions do not warrant population
confidence intervals. Historical V4.3 passes are not counted as fresh V4.4 passes.

## Deployment provenance and limits

The existing original local model is **Qwen3.5-4B-Q4_K_M.gguf**: SHA256
`25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`,
2,707,513,696 bytes, Vulkan GPU device 1, 16,384 allocated context, q8_0 KV,
one serving slot and thinking disabled. This is the configured HANNI 4B endpoint,
not the previously rejected custom HANNI-4B file. Actual `/props` allocation is
not a context-understanding benchmark. The initial host reading was 75.3% RAM
use and an 8,151 MB RTX 5060 Laptop GPU; this is an observation, not an admission
override or a fixed resource condition for every later case.

Fresh protected access to P40, P6000 and Wonyoung Strata is unavailable.
Installed/loaded remote model identity, quantization, actual capacity, latency
and throughput are therefore unknown in this validation. No remote service was
started and no authentication policy changed. Live collaboration, physical
multi-node stress and a three-worker winner comparison remain blocked.

Durable memory is enabled. Enhanced contextual memory and LAYA advisory/retrieval
are disabled in the actual deployment; their isolated compatibility checks do
not establish deployed personal-intelligence quality. MCP remains enabled,
read-only and bounded to three model tool rounds. No external account integration
is declared working merely because an isolated provider test passes.

The actual first workflow plan was safely blocked before any tool action: the
model omitted the complete explicitly supplied source path from its read step.
There were zero verified steps. The planner already requires verbatim paths;
no canned plan, guessed path or broader permissions were introduced to hide this
instruction-following failure.

The second actual planner task produced the correct first source path but used
literal malformed `$ref` strings in report content and the subsequent read
path. Predeclared scope review rejected that resulting unrelated path and
cancelled the plan before tools. Both objectives remain **0/2 completed** and
**zero verified steps**; original review/cancellation receipts and proposed
plans are preserved. This is a real planning limitation, not a mocked success.

Native conversation passed through the original `ChatSession` →
`MemoryAwareSession` → MCP/TextSession processing. A private explicit preference
was stored and the actual model recalled the correct value. It appended an
irrelevant verification caveat, so recall integration works but the complete
response is not declared a clean quality success. No owner memory or external
account was substituted for the private test record.

The explicit private fact survived original-store reopening with `owner_explicit`
provenance. Conversation history persistence across restart is **NOT TESTED**:
the validation ChatHub is ephemeral, so a functioning conversation is not proof
of durable chat history.

## Independent final protocol accounting

The initial sealed protocol contained eight fixed/adaptive pairs with no retries.
Its SHA256 was `ffd28d3c7ecdde3b0efc7a117b534582751c9ede8d9e8162468591432c322241`.
Seven arms were safely **BLOCKED** by the refresh/freshness defect and the
remaining nine were **NOT TESTED**. There were zero actual model responses or
model telemetry. The results are retained as infrastructure admission failures,
not scored incorrect model answers and not silently retried after repair.

The first helper had no per-case cancellation hook. The verifier preserved the
completed arms, confirmed no active model or consequential actions, then abruptly
terminated only the receipt-verified owned validation helper. Its listener and
two exact receipt-verified transient SSH CLI processes are gone. The external
model and original assistant launcher identities remain unchanged. Later
validation checks safe stop markers before and after each refresh.

A distinct postrepair protocol contains eight new cases/16 arms, SHA256
`f675c0442b3d420739b51958cd1f7cb46a2f14e2039db0e2ac07af9cc91a95d9`.
Original final cases and expected answers are not reused for production repair.
Both arms use the same original local endpoint, settings and independent
criteria, with alternating order and no retries. The independent verifier
records every answer, refusal, model receipt, failure and latency.

All 16 postrepair arms dispatched to the genuine original local primary. Fixed
and adaptive each achieved **2/8 exact task successes (25%)**. Each mode had
five original structured-output verification rejections and one accessible
incorrect coding response. There were **six accessible actual responses,
four exact passes and ten rejected outputs**. Rejected raw text is not returned
by the original engine error path; its error, decision, endpoint identity, token
usage and performance receipt are retained, while factual accuracy of that
unavailable text remains unknown. Those arms are unverified task failures, not
automatically proven factual errors. The limitation is disclosed rather than
inventing missing answers or silently rerunning cases. A future harness raw
capture hook was added after this loaded campaign; it was not exercised here.

No pair had different success outcomes. There is no demonstrated adaptive
correctness improvement, and the small predefined shared-endpoint experiment
does not establish population task accuracy or model superiority.

| Execute-only latency | Fixed primary | Adaptive |
| --- | --- | --- |
| P50 | 685.84 ms | 614.15 ms |
| P95 | 1,332.73 ms | 792.06 ms |

These are descriptive original execute-call measurements, excluding preceding
serial remote discovery. Both arms use the same shared serving process;
alternating order does not remove cache/load effects or create distinct models.
The faster observed adaptive median is not a causal optimization claim.

| Original transport observations | Fixed primary (n=8) | Adaptive (n=8) |
| --- | --- | --- |
| TTFT mean / median | 389.12 / 328.83 ms | 288.62 / 281.93 ms |
| Generation mean / median | 82.24 / 85.44 tokens/s | 83.24 / 84.05 tokens/s |
| Conservative service rubric mean | 4.125/10 | 4.125/10 |

The service rubric uses intent 2, model/tool selection 2, factual accuracy 2,
evidence verification 2, clarity 1 and efficiency 1. Missing rejected answers
receive no unsupported accuracy/evidence/clarity credit. The conservative
service score therefore includes pipeline failures; it is not a fully observed
factual grade of all 16 raw model answers. The full refresh-inclusive campaign
took **556.11 seconds**, distinct from execute-call latency. No critical safety
failures or discordant paired success outcomes occurred. Any automatically
generated Wilson interval does not establish population accuracy for these
purposive deterministic shared-endpoint cases; no such inference is claimed.

## MODEL PERFORMANCE

**HANNI 4B:** PARTIAL. Genuine current Qwen3.5-4B-Q4_K_M endpoint; 16 attempted
final dispatches, six accessible answers, four exact successes, ten rejected
outputs; each mode succeeds 2/8. Native development Model Lab responses are a
separate six-response suite. Two actual workflow objectives remain incomplete.
Available serving is verified; readiness for unattended multi-step work is not.

**P40 27B:** BLOCKED. Protected access unavailable; actual loaded model,
quantization, hardware, answer quality, latency and throughput unknown.

**P6000 27B:** BLOCKED. Protected access unavailable; actual loaded model,
quantization, hardware, answer quality, latency and throughput unknown.

**Wonyoung Strata:** BLOCKED. Protected access unavailable; actual loaded model,
quantization, hardware, answer quality, latency and throughput unknown.

## MEASUREMENTS

**Fixed-Model Task Success:** 2/8 (25%) actual final tasks; separately 3/6
controlled recovery conditions.

**Adaptive Task Success:** 2/8 (25%) actual final tasks; separately 4/6
controlled recovery conditions. No actual correctness gain is demonstrated.

**Multi-Model Task Success:** NOT TESTED live; unavailable secondaries. Controlled
collaboration has four verified outputs out of seven conditions, with all seven
guard invariants passing; it is a different objective and denominator.

**P50 Latency:** Execute-only fixed 685.84 ms; adaptive 614.15 ms, n=8 each.

**P95 Latency:** Execute-only fixed 1,332.73 ms; adaptive 792.06 ms, n=8 each.

**Context-Limit Violations:** Zero admitted in the current tested cases. Schema
budget and missing/revoked proof refusal are covered independently; actual
near-limit understanding of inaccessible remote models is NOT TESTED.

**Unauthorized Executions:** Zero in current controlled and actual validation.
The preserved pre-fix synthetic dispatch race is a failure, not a current pass.

**Recovery Success:** Original controlled queue/recovery tests pass; fixed 3/6
versus adaptive 4/6 exhaustive recovery objectives. No physical remote service
was interrupted, so real multi-node recovery is BLOCKED.

**Visual Quality:** 8.7/10, independent fresh native screenshots.

**AI-Template Score:** 1.2/10; lower is better.

**FINAL STATUS:** PARTIAL. Validation exposes and repairs nine infrastructure/
security defect families, preserves core controlled behavior and meets native
visual targets. Actual remote comparison, live multi-model superiority and
verified autonomous planning success are not achieved. Full regression and
independent owned-session cleanup pass. The existing main model/configuration
is preserved; these results do not support promoting a model for unattended
multi-step workflows or choosing a remote winner.

## Acceptance record

Full regression passed **2,086 tests and 25 subtests**, with **two skips**, in
**360.15 seconds**; zero failures/errors. The skips are the absent historical
local-inference failure ledger and the uninstalled `hanni` console command on
PATH. Direct release-archive imports are separately verified. Evidence:
`data/v44-manager/final-regression.xml` and `final-regression-summary.json`.
Python source and validation scripts also compile successfully.

Native review uses the original Windows Forms/WebView2 client against the bounded
current-source original dashboard/controller. All seven surfaces were captured
at 1366×768 and 900×650: Model Lab, Cluster, Workflows, Model Routing, Home,
Conversation and Settings. Fifteen current screenshots, the earlier actual
runner and two read-only supplement captures total **18 reviewed screenshots**,
retained privately. The manager separately inspected every large-window surface,
the narrow Model Lab view and both supplement captures and agrees with the
independent score. No frontend change is justified by this review.

Local screenshot gallery (artifacts stay ignored and are not published):

- [Model Lab](../data/v44-verification/native-20261009-e/model-lab-1366x768-native.png)
- [Cluster](../data/v44-verification/native-20261009-e/cluster-1366x768-native.png)
- [Workflows](../data/v44-verification/native-20261009-e/workflows-1366x768-native.png)
- [Model selection](../data/v44-verification/native-20261009-e/model-selection-1366x768-native.png)
- [Home](../data/v44-verification/native-20261009-e/home-1366x768-native.png)
- [Conversation](../data/v44-verification/native-20261009-e/conversations-1366x768-native.png)
- [Settings](../data/v44-verification/native-20261009-e/settings-1366x768-native.png)
- [Narrow Model Lab](../data/v44-verification/native-20261009-e/model-lab-900x650-native.png)
- [Actual inventory](../data/v44-verification/native-readonly-20261009-i/actual-inventory-native.png)
- [Unavailable node controls](../data/v44-verification/native-readonly-20261009-i/actual-hanni-controls-native.png)

Reboot, sleep and SSH terminal dispatch are not executed during validation;
physical node actions and cluster live telemetry remain outside this bounded
native pass while authorized connections are unavailable. Unknown measurements
remain visibly unavailable. Voice/acoustic behavior is not tested in this
client-only session. Additional development workflow/native measurements occur
after paired timing, during manager regression load, and are not competitive
performance measurements.

The initial native comparison request and three read-only supplement attempts
contained harness mistakes. Their failed artifacts remain preserved; corrections
changed only harness requests/selectors, never production UI, model answers or
final oracles. Completed first-run proof was reused rather than repeating those
model calls. The read-only node-control projection is not proof of actual power
or terminal dispatch functionality.

The manager independently checked all five owned helper identities are gone,
none of their HTTP ports has a TCP listener, and all six native process receipts
are closed. The original model and HANNI launcher retain their PID/create-time
identities and original model command hash. Receipt-verified transient CLI
children are absent. Evidence: `data/v44-manager/independent-cleanup.json` and
`independent-native-cleanup.json`. Short Windows connection probes returned a
pending status; absence was independently verified through listener inventory,
not inferred from that ambiguous status. No external service was stopped.

See the independent [benchmark report](v44-reviews/BENCHMARK_REPORT.md),
[native UI review](v44-reviews/UI_REVIEW.md) and
[acceptance review](v44-reviews/INDEPENDENT_REVIEW.md) for separate scopes.
The built `hanni-0.14.0-py3-none-any.whl` is **898,967 bytes**, SHA256
`78f24f47dae4d3bddbb41227dfd7f0b812570f715ce81a4dfbf0e9da45fc66f4`.
All **196 packaged source/static files** match the workspace byte for byte;
12 runtime modules import directly from that archive. Current UTF-8 README,
release version, local Geist font/license and Model Lab assets are verified.
Private deployment data/configuration, weights and keys are excluded. Evidence:
`data/v44-manager/package-verification.json`. Existing assistant/model processes
are preserved; they require a normal restart to load new Python backend code.

Future evaluation should restore authorized protected worker access, collect
independent category evidence before ranking models, expand real original-planner
end-to-end tasks, and separately evaluate opt-in LAYA/contextual memory. No local
guard should be weakened to make unavailable workers or incomplete plans pass.
