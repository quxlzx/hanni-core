# HANNI V4.2 implementation checkpoints

Source baseline: `500e366` on `codex/hanni-v3.7-distributed`.
Exactly three actual agents: manager, implementation engineer, independent
verifier. The verifier does not edit production code. Private benchmark state
stays under ignored `data/v42-verification` and `data/v42-manager`.

## M0 — sealed performance baseline

Production code remained unchanged until the independent verifier completed and
persisted the baseline. Manager regression: **221 tests passed in 58.87 seconds**,
private JUnit `data/v42-manager/m0-regression.xml`. Engineer audit regression:
75 tests passed. These runs overlap and are not additive coverage counts.

Protocol SHA-256:
`e4c2fa0ac95af1c6095fc0be6201ec56a0229ce8be2777bb53ebd7d970c80872`.
The independently sealed supplementary memory protocol SHA-256:
`da07997eec67270551783f29e3fd09b353257fa4844bcb1f642450536a2b4a4d`.

The unchanged real primary passed **30/30** exact or original MCP outcome checks:
five short, five long, five memory-assisted, six concurrent, three tool-assisted,
and three each at 8K and 16K context. Model loading took 7.768 seconds; the first
short response took 483.742 ms. First-request and repeated warm measurements
remain separately labeled. The original 16K context, one slot, q8_0 KV and
Qwen3.5-4B-Q4_K_M weights were preserved.

Predefined controlled objectives use the real existing scheduler/profile code
with disclosed synthetic endpoint/history fixtures, not simulated GPU speed:

| Objective | Runs | Baseline P50 | Baseline P95 |
| --- | ---: | ---: | ---: |
| Idle worker behind a request pinned to busy worker | 7 | 939.601 ms | 1034.855 ms |
| Complete profile read over 5,000 graded history rows | 15 | 19.387 ms | 25.110 ms |
| Exact context recall over 2,000 synthetic records | 25 | 54.306 ms | 68.578 ms |

Acceptance requires at least 50% reduction for the predefined queue or profile
objective, unchanged exact outputs/aggregate and verified invalidation. The
memory objective separately requires identical selected context, provenance and
privacy. No implementation changes preceded these recorded baselines.

Fresh authorized Athena SSH and nonce-checked cleanup remain unavailable.
The two previously owned GPU helpers may still run; no additional remote helper
was started. Remote resource or performance claims require fresh evidence.
Existing Strata ownership, model configurations and sharing permissions remain
authoritative. Independent before/after inference and context checks continue
using the owned local helper without starting full HANNI.

## Milestone state

| Milestone | State |
| --- | --- |
| M0 performance baseline | Complete; independent implementation gate opened |
| M1 profiling and bottlenecks | Complete; independently measured objectives |
| M2 inference and queue | Independently replayed; original queue/quality checks preserved |
| M3 context and memory | Independently replayed; exact context and privacy checks preserved |
| M4 resource-aware scheduling | Frozen 190-check suite and three live telemetry probes passed |
| M5 existing performance interface | Complete; 16/16 final checks and 8.8/10 review |
| M6 comprehensive comparison | Complete for local application objectives; remote hardware/context limits recorded |

Checkpoints will be updated only after implementation and verification evidence.
No model downloads, speculative KV/concurrency changes, primary replacement,
automatic commit, publication or GitHub push are part of this implementation.

## M1 — profiling and bottleneck checkpoint

The measured Python bottlenecks were complete profile deserialization on every
read, repeated connection/pagination/privacy/term work for memory recall, and
global queue ordering across disjoint worker assignments. The original compute
queue already owns concurrency and interactive reserves; no second scheduler
or increase in worker capacity is needed. Adaptive workflow dispatch also used
the interactive class irrespective of its background origin. Trusted request
classification must preserve the existing reserves.

Selected changes are indexed, invalidated profile aggregation; current-snapshot
memory iteration with bounded content-bound term reuse; and FIFO within actual
compatible worker capacity. Quality, fresh authorization, identity, health,
context, resource and privacy checks remain outside cached profile evidence.
Recent latency may affect placement only within the original quality tier.

Inference backend batching, Pascal cache changes, extra warm servers, broader
contexts and concurrency increases lack fresh authorized hardware evidence.
They are not enabled as speculative optimizations. Original 4B, GPU worker and
Strata runtime configurations remain unchanged.

## M5 — interface verification cycle 1

The existing Model routing endpoint rows now contain recent response P50/P95,
client-observed first visible token, server-reported processing rates, HANNI
queue wait, available GPU measurements, sample counts and recent failures.
Latency history is bounded to 32 recorded slots in sample order; unavailable
times break the line instead of becoming zero or connecting across gaps.
Unknown observations, empty history and resource sample age are explicit.
Existing active/queued counts, routing decisions, policy controls and Geist
typography remain in place.

TypeScript/Vite build passed and all **35 existing frontend behavior tests**
passed. Independent browser cycle 2 passed **14/14 checks** at 1440×900,
900×650 and 640×700; directly reviewed screenshots scored **8.8/10**.
No document overflow, browser errors or external requests were observed.
These are disclosed display fixtures, not live model benchmark evidence.

The reviewer requested a stale-data notice within each endpoint when API
refresh fails. That correction was applied and rebuilt: the endpoint also
labels retained health as last recorded.
Private evidence: `data/v42-verification/browser-cycle2`.
Final corrected cycle 3 passed **16/16 checks**, retaining score **8.8/10**.
Each retained endpoint now carries its own refresh-failure notice and last
recorded health label. Response and GPU sample ages were checked independently.
Private final evidence: `data/v42-verification/browser-cycle3`. Final static SHA-256:
`app.js` = `1e56a863d4fab5cc8a9fd7378ca975095155b7b2d4c93b97c7c9c52cda2f4928`;
`style.css` = `4be06aadcda4e3d6c3e1f72639146bf8a479e8e0b476bb611cdbe8cc23c51858`.

## M2 — inference and queue implementation checkpoint

The cycle 3 backend passed a fresh-process **169/169** focused run,
zero skips or failures, in **42.582 seconds**. Evidence:
`data/v42-verification/engineer-focused-cycle3.xml`. This freeze was superseded
by the final integrity corrections below. Tests include same-clock
FIFO, compatibility-aware independent worker dispatch, bounded queue and
cancellation, original admissions, numeric metric validation, and background
classification through planning, analysis and specialist calls.

Independent earlier cycles exposed FIFO inversion and stale same-connection
cache writes. The implemented queue sequence removes random UUID tie-breaking;
temporary SQLite measurement triggers provide explicit same-connection
invalidation. External commits and changed quality sample settings also
invalidate cached aggregates. The full historical aggregate digest is preserved.

Engineer replay of the sealed controlled protocol measured idle-worker
P50/P95 at **214.919/228.018 ms**, compared with **939.601/1034.855 ms** at M0.
All responses and receipts passed their original checks. Profile warm P50 was
**1.362 ms** versus baseline **19.387 ms**, while cold-inclusive P95 worsened
to **30.192 ms** versus **25.110 ms**. Cold and warm behavior must be reported
separately. These are engineer results. The final independent quiet replay
measured queue P50/P95 **213.155/221.802 ms** and profile P50/P95
**1.271/19.670 ms**, preserving every original response/receipt and aggregate
digest. The predefined P50 objectives passed; the queue P95 objective also passed.

## M3 — memory efficiency implementation checkpoint

The exact fixed-timestamp memory protocol returned the same full context SHA-256:
`44f4ff062ebc8dcf80c0d88e7df989df013bef1834f8c0a3cd0b8a7528c9194e`.
Engineer P50/P95 was **18.318/26.154 ms**, compared with **54.306/68.578 ms**
at M0. Tests verify immediate corrections with unchanged timestamps, deletion,
semantic-state changes, project exclusions, privacy validation and bounded
context. Current records are read on each recall; cached prepared terms cannot
grant authority. After the final dynamic privacy correction, the independent
quiet replay measured **17.138/21.727 ms** over the same 25 recalls and retained
the exact context digest: **68.442%/68.317%** lower P50/P95.

## M4 — bounded placement verification checkpoint

Placement is restricted to the original quality tier, exact endpoint identity
and trusted request requirements. The last five minutes of same-category
observations are capped at 100. A speed change requires three successful fresh
samples, at least 20% gain after a failure penalty and a 30-second hold.
Three consecutive measured failures can choose a qualified healthy peer within
that same quality tier; stale evidence returns to original ordering. Manual
overrides, insufficient graded quality, clock rollback, expiry and fresh
eligibility were checked again in the final 190-test frozen cycle.

Successful local/remote resource capture timestamps accompany reused samples.
Exact single-device matching is required for GPU telemetry. Ambiguous or failed
observations remain unknown. Original concurrency, reserve limits, model/cache
configuration and external process ownership were preserved. Fresh remote
hardware verification remains unavailable; no hardware gain is claimed.

## Final integrity audit cycle

The manager stopped its in-progress full regression before accepting a late
cache-transaction correction. No result from that aborted run is a passing full
suite. Final performance replay also waits for a quiet host; post-change
measurements overlapping that test load were retained as a contention cohort
and excluded from the paired performance claim.

The audit found two further requirements beyond ordinary cache writes: no
uncommitted profile aggregate may survive a rollback/generation collision, and
stream instrumentation must explicitly close a retained underlying transport
generator before releasing its inference lease/active slot. Exact rollback and
held-generator cancellation regressions passed in the corrected freeze.

Memory validation depends on the dynamically registered secret values as well
as current content and its validation function. A warmed term cache must reject
a value registered as a secret after the earlier recall. The corrected cache is
bound to that privacy revision and fails closed on a mid-recall policy change.
Registration, rotation, clear/re-register and mid-recall policy-change tests
passed. The privacy-safe performance replay preserved the same context digest.

The final backend freeze, cycle 6, passed **190/190** coherent focused checks,
zero skips, errors or failures in **45.677 seconds**. Private evidence:
`data/v42-verification/engineer-focused-cycle6.xml`. The independent quiet
replay then passed **30/30** real primary-model cases and **3/3** live adaptive
telemetry probes. Runtime samples remained unscored for correctness and did
not create new quality or capability proofs.

## M6 — independent comparison and release checks

The final comparison is `data/v42-verification/comparison-20261009-c.json`.
It excludes the earlier contended arm and pairs the sealed baseline with the
quiet `20261009-b` replay. All three predefined P50 objectives passed, with
byte-identical profile/context evidence and unchanged task outcomes.

The original primary runtime was reused. The optimized arm has no repeated
cold-load observation; its startup time is unknown, with the inherited initial
receipt labeled separately. Cached prompt prefixes account for large reductions
in the first long/context requests, so no model inference-speed gain is claimed.
The model's sampled RSS increased from 4,496,539,648 to 5,185,134,592 bytes over
the resident runtime; this campaign demonstrates no memory-allocation reduction.
Only the configured 16K allocation was tested through real 8K/16K inference.
32K/64K/128K and fresh remote GPU performance remain unverified.

The `0.12.0` wheel built with existing local build dependencies. All **194**
packaged HANNI files match current source/static bytes, and **ten** runtime
modules import directly from the archive. Private deployment data and weights
are excluded; the local Geist font and license are retained. Wheel SHA-256:
`487b2bfb92531f4918aa27b0da7dda9ed9549f9c660fd3b9a112e7ee600ee97d`.
Private final evidence: `data/v42-manager/package-verification-final.json`.
This final 874,640-byte build includes the README's V4.2 links; its release
metadata was compared with the current UTF-8 README. The first package report
is retained as an earlier artifact and does not identify this final wheel.

Independent cycle 6 passed **29/29** safety and actual private-HTTP checks in
**22.132 seconds**, including rollback, queue/FIFO, token gating, current
identity, bounded metrics, dynamic privacy and retained-stream cancellation.
The local owned model PID **28396** is absent and the operating system reports
no listener on port 8080. The manager separately confirmed both observations.
Private receipt: `data/v42-verification/local-owned-20261009-a/cleanup-reconciled-os-table.json`.

The old running helper's reporter exited with an error after `ModelManager.close`
cleared its process entry. That failed reporter result is retained; the
independent PID/listener reconciliation establishes actual local shutdown.
The helper script now preserves the entry before closing for future campaigns.
Previously owned remote-helper shutdown is still unknown because authenticated
ownership checks could not complete.

The final full repository regression passed **1,963 tests**, with **two skips**
and **25 passing subtests**, zero failures or errors, in **320.92 seconds**.
JUnit records 1,990 cases including skips/subtests; these are not additional
independent passes. Private evidence: `data/v42-manager/final-regression.xml`.
The skips concern an absent historical private inference report and a console
command not installed on PATH. They do not represent skipped V4.2 behavior;
direct wheel imports were checked separately. Source/verifier compilation and
`git diff --check` passed.

Recent placement is functionally verified with trusted fixture histories;
it has no separately paired end-to-end performance gain. Accepted measured
objectives are queue ordering, repeated profile reads and privacy-safe recall.
The independent report passes those local application objectives and tested
correctness. Remote KV/concurrency/network tuning, broader context allocation,
true peak VRAM and old remote-helper cleanup remain explicit evidence limits.
No model/configuration was replaced, and no commit or push was made.
