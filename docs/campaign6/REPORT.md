# Campaign 6: distributed cluster and GPU validation

The controlled implementation audit found and repaired cluster authority,
resource validation, stale telemetry, context-admission and credential-source
defects. The held source passes 522/522 affected regressions and 46/46 independent
exposed checks. Controlled scheduling scores 69/79, separate controls 10/10,
and the untouched once-only independent final 19/22. Three final nonpasses are
retained without regrading or tuning. Live GPU
validation is incomplete: eight active nodes are online and TCP-reachable in
Tailscale, but both bounded discovery rounds required a fresh Tailscale SSH
authentication check. There were zero authenticated hardware measurements and
zero actual model-generation requests. No 27B model, Strata runtime, GPU
assignment or large-context serving result is certified by this campaign.

Two actual engineering agents and an independent verifier inspected and tested
the original HANNI components. The verifier independently reproduced important
failures before repairs and sealed 22 private scheduling cases before tuning.
The once-only holdout ran after a verified 489-file source freeze. Controlled
provider replies are implementation fixtures, never substitutes for real model
answers. The [protocol](PROTOCOL.md) defines the isolated stores, connection
rules, resource budgets, evidence separation and stop conditions.

## Actual configuration and network evidence

Discovery read the existing protected connection configuration and exact
isolated copies of the deployment/context evidence. It did not hardcode an
expected registry count. Nine nodes and three enabled compute workers were
found. Eight nodes are active; Yunjin remains under repair and was skipped.

| Node | Tailscale peer / SSH TCP | LAN SSH TCP | Authenticated SSH / host verification | Registered workers |
| --- | --- | --- | --- | --- |
| HANNI / Athena | Online / reachable, both rounds | Timed out | Not completed; fresh check required | Athena P40, Athena P6000 |
| Wonyoung | Online / reachable, both rounds | Timed out | Not completed; fresh check required | Wonyoung Strata |
| Haerin | Online / reachable, both rounds | Timed out | Not completed; fresh check required | None |
| Chaewon | Online / reachable, both rounds | Timed out | Not completed; fresh check required | None |
| Minju | Online / reachable, both rounds | Timed out | Not completed; fresh check required | None |
| Wonhee | Online / reachable, both rounds | Timed out | Not completed; fresh check required | None |
| Jeongyeon | Online / reachable, both rounds | Timed out | Not completed; fresh check required | None |
| Karina | Online / reachable, both rounds | Timed out | Not completed; fresh check required | None |
| Yunjin | Maintenance; no connection addresses | Skipped | Skipped | None |

Tailscale reports Linux peers with SSH enabled. These roster properties do not
verify CPU, RAM, GPU hardware or host authentication. The original native
endpoint discovery marked all three workers unhealthy. Its generic SSH error
does not distinguish fresh authentication denial from network failure; the
separate original strict-SSH probes do. The independent verifier repeated the
HANNI and Wonyoung connection checks and confirmed the same access blocker.
Sanitized status flags and stderr hashes are retained; raw login URLs and
credentials are excluded from reports.

| Worker | Configured hardware / endpoint | Registered model | Configured allocation | Current measured hardware / loaded model |
| --- | --- | --- | ---: | --- |
| athena-p40 | Tesla P40, explicit GPU UUID, port 18081, llama.cpp | Qwen3.8-27B-Q4_K_S.gguf | 32,768 | Unavailable |
| athena-p6000 | Quadro P6000, explicit GPU UUID, port 18080, llama.cpp | Qwen3.8-27B-Q4_K_S.gguf | 32,768 | Unavailable |
| wonyoung-strata | GPU device unspecified, port 18082, Strata OpenAI protocol | qwen3.8-flash-next-iq3_s | 8,192 | Unavailable |

The Athena registrations name Q4_K_S, whereas the intended campaign deployments
were IQ3_S. Authenticated filesystem/runtime inspection was unavailable, so
this discrepancy does not prove whether separate IQ3_S deployments exist or
what is currently loaded. Strata's existing deployment and authentication source
were preserved. All three workers allow synthetic analysis and structured JSON;
each has configured concurrency one and interactive reserve zero.

## Per-worker live measurements

| Metric | Athena P40 | Athena P6000 | Wonyoung Strata |
| --- | --- | --- | --- |
| CPU, RAM, physical GPU and current assignment | Unmeasured | Unmeasured | Unmeasured |
| Actual loaded model identity | Unmeasured | Unmeasured | Unmeasured |
| Currently verified context | None | None | None |
| Prompt processing tokens/second | Unmeasured | Unmeasured | Unmeasured |
| Generation tokens/second | Unmeasured | Unmeasured | Unmeasured |
| P50 / P95 inference latency | Unmeasured | Unmeasured | Unmeasured |
| Peak inference VRAM | Unmeasured | Unmeasured | Unmeasured |
| Inference error rate | Undefined: zero inference requests | Undefined: zero inference requests | Undefined: zero inference requests |
| Bounded native health observations | 0 healthy / 2 observations | 0 healthy / 2 observations | 0 healthy / 2 observations |
| Steady-state availability | Unmeasured | Unmeasured | Unmeasured |
| Live distributed workflow success | Unmeasured | Unmeasured | Unmeasured |

The initial snapshot exposed historical prompt proof values of 32,768, 32,768
and 8,192. They were not fresh runtime evidence. Strengthened node/account
binding safely excludes legacy source-unbound proofs from admission. The proof
files remain unchanged; the final isolated snapshot reports no current model
or compatible context proof. Fresh authenticated certification is needed before
these historical records can authorize the current remote source.

All fifteen progressive stages (8K, 16K, 32K, 64K and 128K for each worker) are
recorded as **not executed**, with authentication/current identity unavailable.
Athena stages above 32K and Strata stages above 8K also exceed their existing
allocations. Configuration limits are neither actual token-accounting results
nor evidence that the underlying models cannot support larger contexts.
No 128K pass is claimed. Live model loading, generation, context retrieval,
cancellation, concurrent serving, VRAM pressure, queues, endpoint failure and
reconnection could not be exercised through authenticated endpoints.

The machine-readable [live scorecard](LIVE_SCORECARD.json) retains null
performance metrics and all per-stage stop reasons. Initial and final native
receipts are in `data/campaign6-manager/discovery-initial` and
`data/campaign6-manager/discovery-final`.
That second roster round preceded the last credential-race repair. Its exact
observed source hashes remain attached to the live scorecard; later source
changes are disclosed. The two-round live budget is exhausted, and controlled
revalidation of later code does not create another live hardware/inference pass.

## Controlled scheduling results

The prospective primary set has 79 scenarios: six in each of the eleven
requested scheduling families (66), plus thirteen cancellation, authority,
restart and Strata protocol controls. Ten separate prospective supplemental
controls use adequate budgets and exact partial-completion expectations. They
do not regrade or replace the original cases.

| Cohort | Strict result | Evidence scope |
| --- | --- | --- |
| First archived-original primary run | 67/79 | Preserved original run; earlier fixture behavior |
| Archived-original primary, same final harness | 66/79 | Comparable before arm; 78 complete receipts and one preserved harness error |
| Repaired primary before credential repair | 68/79 | Preserved intermediate arm; 78 complete receipts and one harness error |
| Held final primary, same final harness | 69/79 | Final-source arm; 79 complete receipts, zero harness errors |
| Separate supplemental controls | 10/10 in both arms | Separate denominator and adequate-budget/status checks |
| Focused scheduling contracts | 56/56 | Original scheduler/transport/workflow components with isolated providers |
| Untouched independent final | 19/22 | Once only after source freeze; zero harness errors |

Exactly two admission cases improve in the comparable arms: stale remote
capacity despite a fresh health observation, and context exceeding a smaller
configured allocation despite a larger historical proof. The final candidate's
additional pass is the earlier controlled-overlap fixture: observed overlap
changed from one to two and both deliveries completed. This timing/admission
variance is not attributed to the credential repair. The remaining ten strict
nonpasses are unchanged: two parallel-delivery deadlines, one FIFO deadline,
four reassignment deadlines and three blocked-versus-partially-completed status
expectations. Their frozen
0.15-second budgets and oracles were not changed. A correctly rejected result
with no write is still a strict nonpass when its frozen status expectation
differs. The earlier overlap harness error is excluded from metrics requiring
a complete receipt in its own cohort; its diagnostics remain preserved. The
held final cohort has complete receipts for all 79 cases.

The final candidate primary records 77 controlled HTTP POSTs and the separate
supplement 20. The preceding primary's 76 requests, including one in error
diagnostics, are retained in that earlier cohort. Observed cleanup leaks are
zero. These are
loopback protocol requests and have zero real model responses. The six original
workflow-verification cases establish one expected isolated positive artifact
completion and five negative cases with zero artifact writes. That narrower
1/1 positive and 5/5 negative-write result is separate from strict status scores.

Category scores, failing identifiers, corpus hashes, source identities and
commands are in the [scheduling review](SCHEDULING_REVIEW.md) and
[derived scheduling results](scheduling_results.json). Corrected original and
candidate arms import exact archived/current dependencies, retain actual raw
controlled dispatches, and check per-case source stability. The untouched final
22-case result is a separate denominator, described below.

## Independent once-only final

The verifier executed all 22 sealed cases once against the exact frozen source
with no competing campaign test/model load. Collection closed before reference
grading. All 22 cases have receipts, zero harness errors and complete owned
cleanup/reservation release. There are ten controlled HTTP requests, zero real
model inference calls and zero measured hardware observations. The set contains
twelve metadata-selection controls and ten original chat/queue/parallel/result
controls; it cannot certify GPU pressure, server assignment or throughput.

The strict outcome is **19/22**, retained exactly. Independent manual failure
classification is separate from grading:

| Final case | Strict failure | Independent diagnosis |
| --- | --- | --- |
| C6F-02, correct selection | Ordered choices | Authored expected ordering conflicts with the original scheduler's active-slot penalty. This remains a failed oracle, without promotion. |
| C6F-14, parallel tasks | Completed deliveries/request count | The second serial delivery was blocked by the unchanged 0.2-second total queue budget. |
| C6F-17, safe reassignment | Attempt/worker/request count | Reassignment was blocked by the same unchanged 0.2-second total queue budget. |

No unauthorized dispatch or source-admission failure was observed in these
final cases. The two queue-budget misses remain measured failures; they do not
certify successful retry/parallel delivery under those budgets. No tuning,
case replacement, budget change, grade promotion or retry follows from this
holdout. The [oracle-free final summary](FINAL_HOLDOUT.json) and
[independent report](INDEPENDENT_REVIEW.md) preserve category outcomes and raw,
grade, closeout and seal digests. The manager did not open private inputs,
oracles, author code or raw graded case evidence.

## Repairs and regression verification

The original 69 cluster controls produced 26 passes and 43 failures. Independent
original exposed controls produced four passes and twenty failures. Follow-on
GPU-index and authority-restoration defects were independently reproduced
before their repairs. Architectural fixes were limited to four production files:

- `compute/transport.py` validates resource response shapes, finite consistent
  RAM/VRAM capacities and utilization; invalid measurements stay unknown. It
  binds address, tunnel, resource, authentication and runtime-file caches to the
  protected node/account and relevant port/authentication source. Explicit GPU
  index zero remains unknown when the sampler supplies no ordinal evidence;
  exact UUID matching and the original unconfigured single-GPU Strata path remain.
- `compute/registry.py` binds remote runtime/context identity to protected
  addresses/account/authentication source. Changed, missing or invalid authority
  withdraws current observations, including removal-and-restoration paths.
  Durable evidence is preserved. It exposes sampling time and rejects invalid
  heartbeat types. Display-only changes preserve valid identity.
- `compute/scheduler.py` requires remote resource timestamps aged zero to thirty
  seconds. Known configured/reported bounds constrain context at selection,
  queue admission, dispatch and result acceptance. Optional unknown local CPU
  measurements retain their original compatibility.
- `dashboard/cluster.py` clears current CPU/RAM, uptime and process claims after
  the existing six-second telemetry stall bound, while retaining graph history.
  Interrupted streams use network evidence for availability; process RAM is
  bounded to 0 through 100 percent and multicore process CPU may exceed 100.

The earlier source passed 81 cluster development controls and 38 independent
exposed checks. Current post-credential-repair source passes all 97 cluster
development controls and all 46 independent exposed checks. The independent
46-case retake passed in 6.944 seconds (`independent-final-development-cycle3.xml`).
The 61-check existing Campaign 5 verifier module also passed at its distinct
earlier timestamp-fixture checkpoint. These suites overlap broader regressions;
their totals must not be added as unique tests.

The independent last pre-freeze review then reproduced two credential-binding
races: a protected node change after endpoint selection mixed the replacement
credential with the old endpoint, and a change during authentication still
allowed dispatch after authority withdrawal. Both controlled failures are
preserved with zero errors and no actual credentials or network requests.
The repair captures one immutable protected worker/node binding, reads
authentication through that captured node, checks known owned-tunnel URL/binding,
and rejects changed authority after resolution/authentication, before dispatch
and before returning a result. Network work is not serialized under a global
lock. Local synthesized original-supervisor workers retain their loopback path.
The final private set remained unclaimed until after this fix and the whole
source freeze; it never guided engineering.

That candidate passed both races and independent stable/return controls. Two
additional exposed failures showed that a global/worker enabled true-to-false
transition during preparation still permitted dispatch; two already-disabled
passive-health positive controls passed. The repaired guard compares captured
global/worker flags and rejects transitions without banning existing passive
health or duplicating scheduler privacy/model policies. All four independently
reproduced failures and stable, return-boundary and disabled-health controls
pass on the held final transport. Cancellation/concurrent request behavior is
retained. A focused combined 143-case run passes; broader final regression
passes 522/522 with zero failures/errors/skips in 71.737 seconds
(`data/campaign6-cluster/credential-final-relevant.xml`). This final-source
checkpoint supersedes the earlier 506-case result as current implementation
evidence without replacing its artifacts.

Earlier regression evidence remains intact: 204/206 before the empty-observation
compatibility repair, then 206/206; 471/504 when older fixtures omitted resource
sampling timestamps; and 505/506 when an explicit CPU-only re-observation still
omitted its timestamp. The manager approved timestamp metadata corrections only
in four existing public fixture modules, using their existing logical clocks.
Assertions, explicit withdrawal cases and frozen oracles were preserved; exact
before bytes and AST checks document this exception. The final clean affected
pre-credential regression run passed 506/506 with zero failures, errors or skips in 71.731
seconds (`data/campaign6-cluster/final-relevant-clean.xml`). See the [cluster boundary review](CLUSTER_BOUNDARIES.md)
and [independent review](INDEPENDENT_REVIEW.md) for reproduction evidence.

## Remaining capability limits

The original context-growth preflight has a unit mismatch: growth from an 8,192
total allocation requires an 8,192 prompt-token proof, while verification must
reserve at least one output token within that total. A maximum 8,191-token
prompt proof cannot satisfy the next-stage prerequisite. The independent
verifier reproduced this controlled rejection with zero launches. The campaign
does not lower thresholds, relabel proofs, grow allocations or claim that
progressive context serving works. Repair requires a separately verified proof
design and eligible authenticated serving evidence.

Controlled queues, cancellation and recovery do not certify real GPU contention,
server-side cancellation, sustained pressure, network reconnect behavior or
quality of actual model answers. Retained deadline/status-oracle failures and
observed overlap variability prevent a claim of 100% scheduling acceptance.
The final holdout preserves its original private budgets and three nonpasses,
without further tuning or a second attempt.

## Preservation and evidence

Protected deployment/context files, SSH configuration/known-host identities,
owner model settings and unrelated files remain unchanged. The earlier 97-file
campaign/owner catalog has only the documented timestamp-fixture exceptions and
two appended Campaign 6 Git attribute rules; existing attribute bytes are
preserved. Earlier Campaign 4/5 reports, final cases, archives and seals retain
their original bytes. Campaign 6 changes exactly four production files compared
with its initial 200-file archive; earlier uncommitted workflow and adaptive
model source is preserved. [Preservation evidence](PRESERVATION.json) records
these comparisons rather than claiming every prior public fixture is unchanged.

The existing local HANNI and resident-model process identities, listeners and
health were independently confirmed. No resident reload or restart occurred;
fresh test processes use the repaired source. No packages, drivers, model files,
remote launches, power operations or independently managed processes were
changed. Only campaign-owned local helpers/tunnels were closed. No real memory
or owner workflow database was overwritten, and no sensitive operation or
external consequential write was dispatched.

Final post-holdout readback confirms the original process creation/command/parent
identities, listeners, models.yaml and healthy resident status
(`data/campaign6-verifier/runtime-manager-final-readback/RESULT.json`). Protected
deployment/context and SSH identity files still match the baseline. HEAD and
the empty Git index are preserved; `git diff --check` is clean.

Source archives, checks and checkpoints are retained under
`data/campaign6-manager`, `data/campaign6-cluster`,
`data/campaign6-scheduling` and `data/campaign6-verifier`; public audit reports
are under `docs/campaign6`. [Checkpoints](CHECKPOINTS.md) retain before/after
cycles and prospective seals. The final freeze at
2026-10-10T11:19:01.586113+00:00 contains 489 exact files. Manifest SHA256 is
`bf6b2d88f3cf4c3454291090870f009916c90e0bd3307ec4f1b0013da6041316`;
archive SHA256 is
`41fbbdcdadca66ada33569431eb85f1b2d25395cf17b16dcfcd8aeb1a0e37579`.
Both independent and final manager checks verify every member, membership,
protected owner hash and current source byte; all mismatch lists are empty.
Derived report publication does not alter frozen source. The private final seal
is unchanged and its exclusive once-only claim remains intact.

Changes are uncommitted. The incomplete hardware/inference portion is an actual
authentication blocker, and no user action is required to read or review the
completed controlled audit.
