# V4.2 independent verification

The verifier owns scripts, tests, synthetic fixtures, and read-only/owned-runtime evidence. The verifier does not edit production code. No model downloads, private memory forwarding, external process adoption, or authentication/resource-policy bypass is part of this campaign.

## M0 baseline checkpoint

The unchanged baseline is commit `500e3669766c87a2303890a7937bd893344efba4`. The independently sealed primary protocol SHA256 is `e4c2fa0ac95af1c6095fc0be6201ec56a0229ce8be2777bb53ebd7d970c80872`; the 2,000-record recall protocol SHA256 is `da07997eec67270551783f29e3fd09b353257fa4844bcb1f642450536a2b4a4d`. Scripts and raw output precede production changes.

Predefined objectives are reducing idle-worker queue latency by at least 50%, reducing repeated aggregate-profile overhead by at least 50%, or reducing repeated recall overhead by at least 50%, while preserving complete output/provenance and immediate invalidation. Controlled queue fixtures measure scheduler behavior; they do not establish GPU or model throughput improvements.

| Baseline workload | Runs | P50 ms | P95 ms | Outcome |
| --- | ---: | ---: | ---: | --- |
| Idle B behind queued/busy A | 7 | 939.601 | 1034.855 | Exact association and verified receipts passed |
| Aggregate profiles, 5,000 disclosed fixture rows | 15 | 19.387 | 25.110 | Entire aggregate digest stable |
| Recall, 2,000 disclosed fixture records | 25 | 54.306 | 68.578 | Exact context/provenance digest stable |

The existing primary `Qwen3.5-4B-Q4_K_M.gguf` was served through the existing llama.cpp command builder, Vulkan1, 16,384 configured context, one slot, q8_0 key/value cache, thinking disabled, temperature zero, and maximum 192 generated tokens. Full weights SHA256 is `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`. It loaded in 7.768 seconds; this is one observed owned cold start, not a repeated cold-start percentile. The first short request was 483.742 ms, with first content at 342.545 ms. Repeated warm requests have server prompt-cache effects and remain separate raw observations.

All **30/30 real baseline responses** passed exact synthetic JSON or original authoritative MCP verification: five short, five long, five memory-assisted, six concurrent, three tool-assisted, three near-8K, and three near-16K retrieval requests. Every long-context answer had all three exact head/middle/tail needles and real token accounting. The server was never reconfigured to imply 32K/64K/128K support.

| Real primary workload | Runs | P50 total ms | P95 total ms | P50 first-content ms |
| --- | ---: | ---: | ---: | ---: |
| Short | 5 | 190.051 | 483.742 | 47.010 |
| Long | 5 | 209.907 | 1835.577 | 74.637 |
| Memory model call | 5 | 203.525 | 390.528 | 70.568 |
| Memory plus retrieval | 5 | 259.291 | 450.476 | — |
| Concurrent, one backend slot | 6 | 317.164 | 439.234 | 173.510 |
| Original MCP read-only file | 3 | 2074.216 | 2598.242 | 2072.631 |

Percentiles use nearest-rank P95 and median P50; with these small cohorts P95 is usually the maximum and does not establish a population tail or confidence interval. Baseline category summaries that include the first prompt at each size mix prompt-cold and cache-warm observations; later comparison must report that distinction. Server-reported prompt tokens/sec on cached calls measures evaluated work, not fresh full-prompt throughput. TTFT is first visible content at the client boundary, including any admission/prompt/network delay. Original MCP tool durations are observed at the actual host call boundary. Separate backend queue/network durations and peak VRAM are unknown. Process RSS is sampled every 100 ms; pre/post vendor GPU readings are host-wide observations, not per-request allocation or energy.

Private raw evidence is under `data/v42-verification/` and excluded from published source. Athena-owned PID cleanup remains **unknown** after protected authenticated SSH failed; the original V4.1 ownership/nonces are retained. No replacement remote helper is started. The original external Strata process is preserved.

Fresh protected endpoint inventory found all three registered remote workers unhealthy with no current reported model/resource measurements. Configured GPU model files are `Qwen3.8-27B-Q4_K_S.gguf`; the requested IQ3_S file is not a verified current deployment. Remote concurrency remains one, Pascal cache configuration remains f16, and Strata's configured context remains 8,192. These are configuration/historical inventory facts, not a new live remote serving validation. Authentication/resource availability blocks remote KV-cache, network-throughput, and model benchmarks.

## Initial implementation and visual review

Independent cycle 1 found two regressions: same-worker FIFO inversion and stale profile aggregation after a committed write through the same SQLite connection. Both were reported to the engineer; a partially edited implementation cannot count as a final freeze or passing release. The verifier has not modified production code.

Headless Microsoft Edge review cycle 2 passed **14/14** behavioral/display checks at 1440×900, 900×650, and 640×700. Direct screenshot inspection scored **8.8/10**: the flat endpoint hierarchy, retained Geist typography, clear primary readings, and compact history work at all three sizes; secondary labels remain compact. This is an application-assets/UI fixture review, not a native Windows app review or live GPU measurement. Unknown history gaps break the line, the last 32 ordered samples are bounded, failures are marked, one-sample/zero-sample/empty states are explicit, and no external fonts or JavaScript errors occurred. A refresh-outage stale-data disclosure issue was reported to the manager for correction and later recheck.

## Coherent cycle 6 independent verification

The final independent replay began only after the engineer froze the three later integrity corrections and reported 190/190 focused checks passing. These corrections cover transaction rollback cache reuse, explicit immediate closure of held underlying streams before lease/slot release, and secret-registry epoch invalidation/fail-closed memory recall. The manager kept builds and full-suite tests stopped throughout the replay. An earlier optimized queue/recall attempt overlapped a full suite and is retained with `pairing_eligible=false`; the comparator excludes it.

Final comparison is `data/v42-verification/comparison-20261009-c.json`. It consumes unchanged sealed baseline and quiet optimized-b receipts and checks the aggregate/context digests and all real response oracles. Three predefined objectives passed:

| Objective | Baseline P50/P95 ms | Optimized P50/P95 ms | P50/P95 reduction |
| --- | ---: | ---: | ---: |
| Compatible idle worker behind pinned busy worker | 939.601 / 1034.855 | 213.155 / 221.802 | 77.314% / 78.567% |
| Repeated 5,000-row profile aggregation | 19.387 / 25.110 | 1.271 / 19.670 | 93.442% / 21.665% |
| Fixed 2,000-record recall | 54.306 / 68.578 | 17.138 / 21.727 | 68.442% / 68.317% |

The entire aggregate digest and selected fixed recall text/provenance digest are equal before and after. Independent baseline and optimized real primary cohorts each passed **30/30**. Three additional real adaptive-engine requests passed and populated actual first-content/server phase metrics without upgrading unscored runtime correctness or sending the synthetic private canary to a remote endpoint. The actual original private HTTP route retained its token gate and bounded current-identity numeric history.

The independent frozen safety/HTTP suite passed **29/29**, zero failures, errors, or skips, in **22.132 s**. Its report is `verifier-final-cycle6.xml`. Cases cover compatible-worker progress and same-worker FIFO; bounded queue/full refusal; ticket cancellation and no obsolete output; privacy admission; committed same/cross-connection profile updates and rollback generation reuse; immutable profile return ownership; immediate memory corrections, deletion, status changes, project/budget isolation; dynamic secrets and registry changes during recall; measured zero versus unknown and invalid rates; immediate held-stream closure before lease release; and the actual token-gated telemetry route's identity, count, privacy, and null bounds.

## Corrected final visual artifact

Headless Edge cycle 3 passed **16/16** checks at 1440x900, 900x650, and 640x700. Direct screenshot review retains a score of **8.8/10**, exceeding the standing 8.5 threshold. Explicit fixture data covers normal, failure, missing, empty, one-sample, and stale-after-refresh-error displays. All 32 recent sample slots are retained; a missing timing breaks the path rather than connecting a fictional continuous line. Failures are visible, sample-order semantics are stated, GPU observation age is separate, and the unknown fields stay unknown. Every retained panel states that performance may be stale when refresh fails, with health labeled last recorded. No JavaScript errors or external font requests occurred. These are screenshots of the built application assets using explicit display fixtures; they do not prove live GPU data or native Windows rendering.

Final reviewed build hashes:

| Artifact | SHA256 |
| --- | --- |
| Built app.js | `1e56a863d4fab5cc8a9fd7378ca975095155b7b2d4c93b97c7c9c52cda2f4928` |
| Built style.css | `4be06aadcda4e3d6c3e1f72639146bf8a479e8e0b476bb611cdbe8cc23c51858` |
| model_performance.tsx | `abb7c2087c31eaa18857dba078cc001b8f8801b61e761b1efaa0e94f30378b79` |

## Practical limits and disposition

The optimized arm reused the original resident server. Optimized startup is **null/not repeated**, with the original startup receipt separately identified. Prefix caches persisted: optimized first long/8K/16K requests had 4,839/7,569/15,474 cached prompt tokens versus zero in the corresponding baseline first requests. Their large first-request reductions are cache-confounded and do not establish a V4.2 inference-speed gain. Warm model generation rates remained similar, short-request P50 rose, and warm tool host duration increased. First uncached profile aggregation did not approach the repeated-read 50% target. The caches are retained for their demonstrated repeated-read benefit, with live-record reads and explicit invalidation; no unsupported batching/kernel/model/lifecycle layer is accepted.

Sampled model RSS was 4,496,539,648 bytes before and 5,185,134,592 after on the same retained runtime. Memory reduction, peak VRAM, isolated network overhead, energy, and remote GPU speed are not claimed. Actual context usage remained 7,573 and 15,478 tokens with exact three-position answers in both arms. Higher 32K/64K/128K allocation is outside this runtime's configured 16K and untested; it is not declared inherently impossible for the model architecture. Current remote resource/serving evidence and prior Athena cleanup remain unknown after authenticated access failed. Original Strata ownership is preserved.

After the replay, the owned local server was stopped through its session file. The already-running verifier helper's old cleanup reporter failed after the original `ModelManager.close` cleared its entry. This reporting error is preserved, and the helper is fixed for future runs. Independent reconciliation confirms owned PID **28396 absent** and **no loopback/wildcard 8080 listener**, without killing or adopting another process. Its receipt is `local-owned-20261009-a/cleanup-reconciled-os-table.json`; Windows socket would-block is recorded as unknown rather than successful socket refusal. The manager independently confirmed the same process/listener state.

Independent acceptance: **pass for the measured local scheduler/retrieval/profile objectives and tested correctness/security scope**. Remote hardware tuning and larger context allocation remain blocked/unverified. The manager owns the final full-suite/package checkpoint; the earlier interrupted full suite is not a pass. Detailed cold/warm stage measurements, failed/deferred candidates, exact commands, and ownership limits are in `docs/HANNI_V4_2_BENCHMARK_COMPARISON.md`.

The final manager integration run subsequently completed with **1,963 passed, 2 skipped, and 25 subtests passed in 320.92 s** (`data/v42-manager/final-regression.xml`). Direct XML inspection identifies the skipped historical local-inference report, which is absent from this checkout, and the console-script check because `hanni` is not on PATH. No production source changed after the quiet replay freeze. Recent adaptive placement is functionally verified for same-category/quality-tier eligibility, three fresh samples, 20% threshold, 30-second hold, manual/privacy boundaries, stale/future readings, reserve propagation, and repeated failures. There is no separate independent paired end-to-end performance gain receipt for adaptation; it does not add a remote/model-speed objective claim.
