# HANNI V4.4 engineering findings

Engineering scope: controlled development tests, original-source diagnosis, and
the smallest repairs. Actual model responses, hardware, native desktop review,
sealed final evaluation, and final acceptance belong to the independent verifier
and Manager. No final holdout answers were opened by engineering.

The tracked starting revision was `80ab843`. This cycle modifies
`src/hanni/compute/scheduler.py` and `src/hanni/models/adaptive.py` in production. It adds no major feature, model
download, service restart, endpoint override, permission bypass, or answer map.

## Source audit and baseline checkpoint

V4.0 `AdaptiveModelEngine` implements measured, identity-bound capability and
context evidence, privacy eligibility, trusted endpoint assignments, bounded
fallbacks, admission callbacks, and local output budgets. The original worker
queue still mediates remote inference. V4.1 `CollaborationEngine` pins distinct
participants and treats review and consensus as advisory; only the supplied
independent outcome verifier can establish a verified result. V4.2 preserves
compatible-worker FIFO, interactive reserves, bounded queues, cancellation,
fresh measured placement history, and explicitly unknown performance metrics.

These are implementation observations supported by fresh focused tests, not a
claim that every live workflow or remote worker succeeds. The initial focused
baseline passed **242 tests**, with no errors or skips, in **71.953 seconds**.
Private evidence: `data/v44-engineering/baseline.xml`.

## Reproduced defects and repair checkpoints

| Defect | Preserved failing evidence | Root cause and repair |
| --- | --- | --- |
| Direct distributed context admission omitted the structured-response schema. | `pre-repair-gpu.xml`, schema case | Include credential-safe, bounded canonical schema bytes with messages and output in conservative context admission. Invalid, oversized, or credential-bearing schemas fail before queue admission. |
| A valid response returned after cancellation could be admitted as completed. | `pre-repair-gpu.xml`, cancellation case | Check cancellation and scheduler closure before result admission. Cancellation retains healthy worker status and never triggers reassignment. |
| Unknown remote RAM and GPU VRAM were accepted as available reserves. | `pre-repair-gpu.xml`, two memory cases | Require known finite remote RAM; require GPU reserve when a GPU is configured or measured. CPU-only remote workers can have unknown VRAM; local workers retain original system admission. |
| GPU startup configuration without a display label evaded the new VRAM guard. | `pre-startup-gpu-repair.xml` | Read original worker `startup.gpu_device` as well as the displayed/measured GPU. |
| Protected authorization revoked during transport still admitted the result. | `pre-result-authority-repair.xml`; independently reproduced by verifier | Recheck deployment, worker fingerprint, permitted categories, capabilities, observed model, and verified context before returning. Withdrawn authority becomes `BLOCKED`, without declaring the endpoint unhealthy or retrying. |
| Admission-time removal of protected context permissions still dispatched one request. | `pre-permission-race-repair.xml` | Reload protected authorization before obtaining the worker copy; recheck fingerprint/capabilities and current capacity before dispatch. The previous fetch-before-reload order retained stale permissions. |
| Admission callbacks setting cancellation could dispatch or admit output anyway. | `pre-callback-cancel-repair.xml`, two cases | Recheck the cancellation/closure flag immediately after both original admission callbacks. Initial cancellation causes zero transport calls; final cancellation discards the already returned result. |
| Slow failed remote discovery expired healthy local heartbeat before a synchronous refresh returned. | `pre-slow-refresh-repair.xml`; actual independent first final pair safely blocked without inference | Perform remote discovery before the genuine local health probe. Do not rewrite timestamps or extend the original 30-second trust interval. A controlled 35-second remote delay remains eligible locally after the new probe; a later 31-second expiry still blocks it. |
| Failed remote resource sampling aborted synchronous refresh or the health monitor. | `pre-resource-refresh-repair.xml`, three cases | Skip resource connections after unhealthy health. A bounded resource connection error clears stale RAM, VRAM, GPU, hardware, and sample-time observations without ending discovery. Unknown remote capacity remains ineligible. |

All reproductions used owned synthetic fixtures and injected transports. No
actual private context crossed an unauthorized endpoint. The discovered
permission race is a real security defect in the earlier direct-scheduler path;
the pre-fix synthetic failure must not be represented as a passing baseline.

Regression tests also cover loss of context proof, health, or RAM during original
admission; lease withdrawal after transport; result cleanup and released active
reservations; and CPU-only compatibility. Existing final source instructions and
guards remain intact. The engineer does not alter expected answers to obtain a
pass.

The initial broad repair verification passed **335 tests**, with no failures, errors, or
skips, in **91.664 seconds**. This includes **18 new engineer regression cases**,
22 independently authored V4.4 security cases available at collection, and the
original V4.0/V4.1/V4.2 routing, collaboration, compute, and workflow tests.
Private evidence: `data/v44-engineering/repair-final.xml`.

The initial scheduler-only freeze was superseded after actual integration exposed
the slow-refresh defect. Initial production scheduler SHA256:
`035da86edc0b0068ffd0d26c39d22fb64ec4bc371a70dd3dded4a51e833cc96a`.

The second broad verification after the integration repairs passed **342 tests**,
with no failures, errors, or skips, in **97.739 seconds**. It includes **22 engineer
regression cases** and **25 independent V4.4 security cases** available at
collection. Evidence: `data/v44-engineering/repair-refresh-complete.xml`.
The source ordering change and resource-failure handling do not change scoring,
expected responses, prompts, model identity, capabilities, or context limits.
The verifier preserves actual blocked final attempts separately; those attempts
must not disappear because later source is repaired.

Second production freeze:

| File | SHA256 |
| --- | --- |
| `src/hanni/compute/scheduler.py` | `cc3d5afc20d3f8261b5e551532d21f424c4dac242956152b1378f5b4fee6dd6d` |
| `src/hanni/models/adaptive.py` | `4489ba3b691970bd25728fd27ec909baf3c1e06fe66348e162d5ccde0f240370` |

## Predefined controlled routing evaluation

The campaign manifest records the oracle, request classes, policies, privacy
classes, output budget, fixture context proof, synthetic runtime identity, source
hashes, Python/OS, date, seed, and sample counts before executing any case.

**432/432 eligibility outcomes were valid**: nine request classes, four routing
policies, six privacy categories, and both local-only settings. The classes are
simple conversation, complex analysis, tools, multi-step planning, context
overflow, memory, ambiguity, specialized vision, and requests without tools.
Correctly blocked requests count as valid eligibility outcomes, not completed
tasks. No model inference or tool action occurs in this matrix.

The independent declarative fixture oracle checks registered endpoint identity,
known capacity, capability restrictions, private-context authorization, and
manual/local-only constraints. It does not reuse the router's eligibility helper.
This meets the 95% controlled eligibility target for the stated fixture matrix.
It does not prove factual response quality or correctly generated tool arguments.

## Fixed versus adaptive recovery objective

Before execution the campaign defines this objective: complete more available,
authorized tasks during a primary outage while forwarding no private context.
Six paired conditions combine healthy/outage primary status with synthetic,
memory, and sensitive context. Both modes receive identical messages, output
budgets, endpoint fixtures, validators, and resource conditions. The fixed mode
pins the supervisor with no alternative endpoint; adaptive mode uses its original
bounded fallback policy. These are scripted controller tests.

| Mode | Verified fixture completion | Meaning |
| --- | --- | --- |
| Fixed primary | 3/6 | Completes the three healthy-primary conditions. |
| Adaptive | 4/6 | Also recovers the synthetic-context condition using the authorized worker. |

Both modes correctly fail private-context outage conditions when no authorized
alternative exists. Unauthorized remote dispatches: **0**. The one additional
completed condition demonstrates bounded authorized recovery in this fixture;
it is not evidence that adaptive models reason better. All six conditions are
predetermined, so statistical confidence intervals are not meaningful here.

## Controlled collaboration evaluation

Seven original-engine scenarios preserve responses and evidence independently:

| Scenario | Expected final verification | Observed invariant |
| --- | --- | --- |
| Correct agreement | `VERIFIED` | Pass |
| Incorrect agreement | `FAILED` | Pass: matching wrong answers do not become proof. |
| Disagreement | `VERIFIED` | Pass: source-verified output selected, conflict preserved. |
| Incomplete primary | `VERIFIED` | Pass: source-verified secondary selected. |
| Conflicting interpretations | `VERIFIED` | Pass: unsupported alternative preserved as conflict. |
| Missing evidence | `UNVERIFIED` | Pass: agreement alone remains unverified. |
| Secondary endpoint failure | `FAILED` | Pass: no invented recovery/proof or duplicate opinion. |

**7/7 guard invariants passed; only 4/7 selected outputs were independently
verified.** These two numbers describe different objectives and are not merged
into a model task-success percentage. Each scenario records participant
identity, actual original control-path latency, outputs, assigned endpoint,
resource observations, generated-token observations when available, verification,
conflicts, and failure state. Synthetic source value checks belong only to the
evaluation harness, never production response generation.

## Distributed stress and recovery

The broad final suite freshly passed all **41 original V3.7 independent compute
cases** and **29 original V4.2 independent performance cases**. Relevant
controlled tests include distinct-worker overlapping requests and association,
bounded queue overflow without lost work, compatible-worker FIFO, interactive
reserved capacity, cancelled older tickets, late-result withdrawal, exact cited
workflow results, receipt persistence across interruption without replay, and
safe reassignment that retains the interrupted worker's durable history.

These tests use original adapters/controllers with owned loopback HTTP or
scripted transport seams. They establish guarded queue/recovery behavior under
those conditions, not remote GPU speed, real multi-node resilience, or a live
production stress result. No live service is terminated or disconnected.

## Actual planning failure assessment

The verifier's exposed-development real-model workflow failed before tool
dispatch because the model omitted the complete owner-provided source path in
its file-read step description. `WorkflowPlanner` already explicitly requires
that path verbatim and forbids guessed replacements. Original step discovery
correctly rejected the incomplete proposal. Zero verified workflow steps is the
actual outcome; a fluent final answer cannot replace it.

No general safe production repair was established for this instruction-following
failure. Engineering did not insert the omitted path, broaden the menu from the
whole goal, inject a canned plan, or tune a final holdout. Further independent
planning evaluation is warranted before claiming verified end-to-end improvement.

## Reproduction and evidence

Run the controlled campaign into a fresh ignored directory:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/v44_verification/controlled_campaign.py --output data/v44-engineering/controlled-campaign-review
.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_v44_controlled_regressions.py tests/integration/test_v44_independent_security.py -q
```

The initial executed campaign artifacts are under
`data/v44-engineering/controlled-campaign-20261009-b`. Their Python control-path
timings are descriptive development measurements; they must not be shown as
P40/P6000/Strata/HANNI hardware benchmarks. No endpoint is enabled or granted
capability/quality evidence in the user's actual routing database by this script.

The campaign was rerun against the second production freeze into
`data/v44-engineering/controlled-campaign-20261009-c`, with the same frozen
objectives, expected outcomes, request classes, and source-value checks. Results
remain 432 valid eligibility outcomes, seven passing collaboration invariants,
and fixed 3/6 versus adaptive 4/6 recovery completion. Its manifest SHA256 is
`d2b9fb218c830f0cd55f870e56798f49fd452682a419de199bdbd8696e538277`.
The harness now correctly reports no confidence interval for exhaustive fixed
conditions; prior artifact files are retained unchanged.

Final full-regression, live-response grades, available-worker measurements,
native screenshots, visual score, package verification, and acceptance are
reported separately by the Manager and independent verifier.
