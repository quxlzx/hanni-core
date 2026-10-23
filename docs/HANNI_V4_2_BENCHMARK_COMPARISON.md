# V4.2 independent performance comparison

## Protocol and scope

The baseline was measured before production edits at commit `500e3669766c87a2303890a7937bd893344efba4`. Independent verifier scripts seal datasets and objectives before changes and preserve raw measurements under the ignored `data/v42-verification/` directory. The primary protocol SHA256 is `e4c2fa0ac95af1c6095fc0be6201ec56a0229ce8be2777bb53ebd7d970c80872`. Fixed-timestamp recall protocol SHA256 is `da07997eec67270551783f29e3fd09b353257fa4844bcb1f642450536a2b4a4d`.

Predefined objectives require at least a 50% P50 reduction in independently measured worker-queue, historical profile aggregation, or repeated memory-retrieval overhead, while retaining exact outcomes and provenance. The queue objective also requires a 50% P95 reduction. The queue fixture runs the original scheduler and HTTP transport against disclosed controlled endpoints; it cannot establish Pascal GPU or model throughput improvements. Recall/profile fixtures are explicitly synthetic and do not read the owner's memories.

Timing summaries use median P50 and nearest-rank P95. Small cohorts have P95 equal to the maximum and do not establish a population tail or confidence interval. The production panel explicitly uses nearest-rank percentiles; for an even cohort, its P50 convention can differ from the benchmark median. Model quality is exact expected JSON or an original MCP `VERIFIED` receipt. No model agreement, confidence, successful transport, or speed alone counts as correctness.

## Fresh inventory

| Endpoint | Current observation | Configuration and evidence scope |
| --- | --- | --- |
| Original local 4B | Live owned llama.cpp runtime; 30/30 baseline exact/receipt checks | Existing `Qwen3.5-4B-Q4_K_M.gguf`, Vulkan1, 33/33 offloaded layers, one slot, q8_0 K/V cache, 16,384 configured context |
| P40 | Protected authenticated inspection unavailable; current resources/model unknown | Deployment points to `Qwen3.8-27B-Q4_K_S.gguf`, one slot, 32K/f16 cache; an IQ3_S deployment is not newly verified |
| P6000 | Protected authenticated inspection unavailable; current resources/model unknown | Same configured Q4_K_S file, separate configured GPU UUID, one slot, 32K/f16 cache |
| Wonyoung Strata | Protected authenticated inspection unavailable; current resources/model unknown | Existing configured `qwen3.8-flash-next-iq3_s`, 8K, one slot; external service not stopped or adopted |

The actual local vendor inventory reports NVIDIA GeForce RTX 5060 Laptop GPU, 8,151 MiB, and 31.612 GiB host RAM. Full primary weights SHA256 is `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c` (2,707,513,696 bytes). No weights were downloaded, replaced, or moved. Fresh remote health checks each took approximately 5.6 seconds and failed through the original protected LAN/Tailscale SSH path. Historical remote probes do not become current resource observations. No trust or resource gate was weakened to benchmark a raw tunnel.

The two previously owned Athena helper PIDs, 149344 and 149663, still have **unknown cleanup state** after the nonce-checked protected stop could not authenticate. Original ownership receipts are retained for reconciliation. This campaign starts no additional remote model helper. No command targets the externally owned original Strata process.

## Real primary baseline

Owned model load took 7.768 seconds. This is one observed startup, not repeated cold-start P50/P95. The first short request was 483.742 ms, with first content at 342.545 ms. Temperature is zero, top_p is one, thinking is disabled, and generated output is bounded to 192 tokens. Server properties and exact request settings are saved privately.

| Workload | Requests | Exact/authoritative success | Baseline P50 total ms | Baseline P95 total ms |
| --- | ---: | ---: | ---: | ---: |
| Short JSON lookup | 5 | 5/5 | 190.051 | 483.742 |
| Long synthetic document lookup | 5 | 5/5 | 209.907 | 1835.577 |
| Memory model call | 5 | 5/5 | 203.525 | 390.528 |
| Memory plus live retrieval | 5 | 5/5 | 259.291 | 450.476 |
| Two concurrent clients, unchanged one-slot backend | 6 | 6/6 | 317.164 | 439.234 |
| Original MCP read-only file request | 3 | 3/3 | 2074.216 | 2598.242 |

These baseline category rows include the first prompt of each workload. Raw evidence distinguishes the first request and repetitions; the final paired comparison must separately report prompt-first and cache-warm cohorts. Prefix reuse explains the large difference between first long/context prompts and repeats. Server-reported prompt processing on a cached call measures newly evaluated work, not processing the entire original prompt again. Concurrent clients are not extra model slots; their increased observed delay includes backend contention.

Memory-assisted calls assemble context through the existing `ContextAwareRetriever`, with 2,000 synthetic noise records and a relevant exact fact. Original MCP calls invoke the real read-only file capability, observe the host call duration, and require the original verification receipt. Fresh isolated memory IDs, timestamps, and file paths can differ between arms; they contain equivalent authorized information and exact expected answers. The separate fixed-timestamp/ID recall fixture has byte-identical context and provenance digests across arms.

## Progressive context verification

| Primary allocation | Actual prompt tokens | Repetitions | Retrieval outcome | Prompt-first total ms | Repeated warm total ms |
| --- | ---: | ---: | --- | ---: | --- |
| 8,192 target within original 16K server | 7,573 | 3 | Exact head/middle/tail all passed | 3151.963 | 436.541, 442.919 |
| 16,384 target within original 16K server | 15,478 | 3 | Exact head/middle/tail all passed | 6371.297 | 460.427, 469.219 |
| 32K | — | 0 | Not allocated/tested in this configuration | — | — |
| 64K | — | 0 | Not allocated/tested in this configuration | — | — |
| 128K | — | 0 | Not allocated/tested in this configuration | — | — |

Actual usage for warm context calls reports 7,569 and 15,474 cached prompt tokens respectively. This campaign verifies the current 16K primary allocation, rather than claiming the GGUF's architectural maximum or a historical alternate allocation. Remote progressive measurements are blocked by current authenticated resource access. No 128K capability is registered or advertised.

The model process sampled RSS peak was 4,496,539,648 bytes, sampled every 100 ms over the baseline cohort. This is a sampled peak, not an isolated minimum requirement. Host-wide pre/post GPU readings were 3,031 and 3,039 MiB used, with utilization 0% and 93% at those instants. True peak VRAM, per-request GPU utilization, energy, separately measured network-only overhead, and backend queue waiting are unknown. TTFT records first visible content at the client boundary; original MCP first visible output includes model/tool/verification stages and is not the inference server's first token. Stages overlap and should not be summed blindly.

## Controlled queue, profile, and recovery baseline

| Objective or scenario | Runs | Baseline P50 ms | Baseline P95 ms | Required correctness |
| --- | ---: | ---: | ---: | --- |
| Idle B queued after busy/pinned A | 7 | 939.601 | 1034.855 | Each result/receipt stays attached to its original invocation |
| Profile aggregation of 5,000 fixture rows | 15 | 19.387 | 25.110 | Complete all-time aggregate digest identical |
| Recall from 2,000 fixed fixture records | 25 | 54.306 | 68.578 | Complete selected context/provenance digest identical |
| Interactive request with reserved slot | 7 | 254.393 | 281.114 | Queued background cannot occupy the interactive reserve |
| Controlled endpoint incomplete output, bounded reassignment | 1 | 488.441 | 488.441 | Invalid response never verifies; second registered worker retains same invocation and original history |

Independent safety cases require same-worker FIFO, queue-full refusal without dropping existing work, cancellation dropping obsolete tickets/output, unchanged privacy admission, immediate corrections/deletion/semantic-status changes, and cache invalidation across both same and different SQLite connections. Initial verification exposed and reported FIFO timestamp ties and stale same-connection profile writes. Later integrity checks found transactional rollback generation reuse, retained streaming-generator closure, and dynamic secret-registry cache invalidation. All were corrected before the coherent cycle 6 freeze and the final independent replay.

## Reproducible commands

Run the seal script before production changes, then run baseline and optimized arms with the same original model settings and helper receipt. All scripts reject overwriting raw evidence. Fresh campaigns need fresh output paths; the historical commands below identify this campaign exactly. To reproduce baseline source after a later commit, use an isolated checkout of `500e366` with these verifier scripts copied into it; preserve the existing binary/weights configuration and original request protocol. Do not reset the shared working tree.

```powershell
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/seal_protocol.py
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/local_session.py --output data/v42-verification/local-owned-20261009-a --weights <existing-configured-GGUF-path> --seconds 7200
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/controlled_benchmark.py --output data/v42-verification/controlled-baseline-20261009-a
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/memory_benchmark.py --output data/v42-verification/memory-baseline-20261009-a
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/local_benchmark.py --output data/v42-verification/local-baseline-20261009-a --session data/v42-verification/local-owned-20261009-a --context
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/resource_inventory.py --output data/v42-verification/resource-inventory-20261009-a.json
```

Only the verifier-owned local helper responds to its session `stop` file and closes its original `ModelManager` owner. A failed remote cleanup is unknown, not successful termination.

## Frozen before-and-after result

The final independent run used the coherent cycle 6 source, after the engineer's 190 focused checks passed. The manager kept the host free of concurrent builds/tests throughout the paired replay. Raw optimized evidence is `controlled-optimized-20261009-b`, `memory-optimized-20261009-b`, and `local-optimized-20261009-b`. The final derived report is `comparison-20261009-c.json`; it corrects an inherited startup receipt that the earlier derived report repeated as an optimized load observation. No new server load occurred in the optimized arm, so optimized load time is **unknown/not repeated**, represented as null. The original baseline startup receipt remains 7,768.174 ms.

The earlier `controlled-optimized-20261009-a` and `memory-optimized-20261009-a` measurements overlapped a full regression process. They are retained with `pairing_eligible=false` and excluded from before-and-after gains. The comparison script refuses to accept those receipts as paired evidence.

| Sealed objective | Baseline P50/P95 ms | Frozen optimized P50/P95 ms | P50 reduction | P95 reduction | Predefined result |
| --- | ---: | ---: | ---: | ---: | --- |
| Idle B behind busy/pinned A, 7 runs | 939.601 / 1034.855 | 213.155 / 221.802 | 77.314% | 78.567% | Pass, both exceed 50% |
| Unchanged 5,000-row profile, 15 reads | 19.387 / 25.110 | 1.271 / 19.670 | 93.442% | 21.665% | Pass, P50 exceeds 50% |
| Fixed 2,000-record recall, 25 reads | 54.306 / 68.578 | 17.138 / 21.727 | 68.442% | 68.317% | Pass, P50 exceeds 50% |

The full aggregate digest is unchanged: `d354fcdb2327bf11c205d6a5751b755c04844ce39478ee316ef6142cf9651098`. The entire fixed recall context/provenance digest is unchanged: `44f4ff062ebc8dcf80c0d88e7df989df013bef1834f8c0a3cd0b8a7528c9194e`. Controlled result association, authoritative receipt status, disconnection/fallback, and interactive-reserve checks also passed. Interactive contention P50/P95 was 254.393/281.114 ms before and 211.272/222.087 ms after; this is a controlled scheduler workload, not a GPU load measurement.

All **30/30 real baseline and 30/30 real optimized responses** passed their independent exact-answer or original MCP receipt checks. The same weights, binary, one-slot 16K allocation, sampling settings, and bounded output were retained. Three additional real requests through `AdaptiveModelEngine.execute` produced actual first-content/server-phase telemetry and kept the synthetic private context local. Their runtime measurements remained unscored: `correctness_sample_count=0`, confidence insufficient. Telemetry is evidence of observed timing, not a correctness or capability upgrade.

## First-request and warm-primary comparison

The following repeat cohorts exclude iteration zero. Each latency entry is P50/P95; TTFT is the client-observed first visible content. Original tool output includes verification and is not server TTFT. These small cohorts describe this run and do not establish significant changes in model inference speed.

| Warm workload | Runs per arm | Baseline total ms | Optimized total ms | Baseline first-content ms | Optimized first-content ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Short | 4 | 188.150 / 213.978 | 201.613 / 203.875 | 46.650 / 72.317 | 58.885 / 63.478 |
| Long | 4 | 207.883 / 230.529 | 188.903 / 207.368 | 73.202 / 79.518 | 52.770 / 70.815 |
| Memory model call | 4 | 201.931 / 222.718 | 200.206 / 212.640 | 68.593 / 73.362 | 68.954 / 74.519 |
| Two clients, one backend slot | 4 | 288.393 / 388.591 | 285.367 / 382.046 | 145.569 / 244.927 | 142.473 / 239.503 |
| Original MCP file request | 2 | 2054.902 / 2074.216 | 2042.571 / 2105.857 | 2053.217 / 2072.631 | 2041.281 / 2104.376 |
| 8K target, 7,573 actual tokens | 2 | 439.730 / 442.919 | 433.654 / 433.849 | 77.150 / 80.078 | 69.153 / 70.480 |
| 16K target, 15,478 actual tokens | 2 | 464.823 / 469.219 | 461.214 / 466.516 | 75.450 / 80.934 | 72.784 / 77.843 |

Warm memory-assisted total including retrieval changed from 258.210/278.736 ms to 216.435/229.008 ms. Warm retrieval itself changed from 56.406/57.609 ms to 16.228/16.368 ms. The model-call latency remained similar, so the observed reduction is consistent with removing repeated local memory work. The real memory fixture is information-equivalent; the separate fixed recall oracle proves byte-identical selected context/provenance.

First-per-workload totals are observations, not independent server cold starts:

| First workload request | Baseline total ms | Optimized total ms | Baseline/optimized cached prompt tokens |
| --- | ---: | ---: | ---: |
| Short | 483.742 | 502.594 | 0 / 24 |
| Long, 4,843 prompt tokens | 1835.577 | 263.643 | 0 / 4,839 |
| 8K target | 3151.963 | 528.837 | 0 / 7,569 |
| 16K target | 6371.297 | 593.349 | 0 / 15,474 |
| Memory model call | 390.528 | 371.093 | Isolated fixture context can differ |
| Original MCP file request | 2598.242 | 2388.868 | Isolated file path can differ |

The resident server retained prefixes from the baseline. The large first long/context reductions therefore **cannot be attributed to V4.2**. No repeated cold-start percentile or startup improvement is claimed.

| Warm server phase rates | Baseline prompt/generation P50 tokens/s | Optimized prompt/generation P50 tokens/s |
| --- | ---: | ---: |
| Short | 89.686 / 85.240 | 89.957 / 84.957 |
| Long | 83.951 / 81.530 | 84.445 / 80.598 |
| Memory | 88.749 / 82.604 | 86.547 / 83.273 |
| Two concurrent clients | 84.012 / 83.844 | 89.442 / 84.295 |
| 8K target | 82.521 / 80.035 | 80.562 / 79.612 |
| 16K target | 73.960 / 74.538 | 74.276 / 74.708 |

Prompt rates on cached calls cover only newly evaluated server work. Original tool-assisted server rates are unknown in this receipt; actual warm host-tool call duration was 6.726/7.404 ms before and 8.519/9.323 ms after. Network-only timing, backend queue timing, and request-specific GPU utilization are still unknown.

Sampled model RSS increased from **4,496,539,648 to 5,185,134,592 bytes**. Both observations belong to the retained server, whose cache state changed across workloads. This is not a memory reduction, isolated per-request requirement, or true peak VRAM measurement. Optimized post-run host-wide GPU usage was 3,039 MiB and utilization 94% at that instant. No GPU-capacity or serving-concurrency increase was introduced.

## Failed or deferred optimization dispositions

| Candidate | Evidence and disposition |
| --- | --- |
| Cold aggregate/profile speed | First read was 21.470 ms before and 19.670 ms after, far below a 50% reduction. Retain the cache for proven repeated-read gain; writes, changed identity/settings, external commits, and transactions invalidate/bypass it. Do not claim cold aggregation or frequent-write workloads improve by the warm percentage. |
| Raw model/token speed | Warm short P50 rose and generation rates did not consistently improve. No kernel, model, or sampling change is retained or credited with the application-overhead gains. |
| Tool execution speed | Warm host-tool latency increased in this small cohort. No tool-speed optimization or transport claim is made. Original receipts remain required. |
| Batching/more slots | No measured interactive benefit supports changing the one-slot primary or one-slot configured Pascal workers. No batching layer or extra inference helpers were added. |
| Pascal KV-cache changes | Fresh protected remote inspection is blocked. Retain the configured f16 cache; do not enable unmeasured attention kernels or cache quantizations. |
| 32K/64K/128K primary allocation | Outside this runtime's configured 16K allocation; not tested. This says nothing about an inherent model architectural limit. Only actual 8K/16K checks support this campaign's context claims. |
| Remote network/resource tuning | Fresh authenticated resources are unavailable and separate network-only latency is unknown. No raw tunnel, authorization bypass, speculative transfer layer, or GPU-throughput benefit is accepted. |
| Preload/startup policy | Only one baseline startup was measured; optimized startup was not repeated. Preserve the original manager lifecycle and external process ownership. |

Bounded recent placement is a required V4.2 function, separately verified by controlled policy cases: same trusted category and quality/default tier, three fresh successful observations, at least 20% latency threshold, a 30-second placement hold, current privacy/manual eligibility, and repeated-failure recovery. Those tests demonstrate policy behavior using disclosed fixture timings; they are not an independent paired end-to-end throughput experiment. No separate adaptation, remote GPU, or model-speed gain is accepted in the objective table.

## Final regression, display, and cleanup evidence

The independent frozen safety/HTTP suite passed **29/29**, zero skips, failures, or errors, in **22.132 s** (`verifier-final-cycle6.xml`). It covers same-worker FIFO and free-worker progress, queue-full refusal, cancellation, privacy admission, same/cross-connection profile invalidation, rollback generation reuse, immediate memory corrections/deletion/status changes, dynamic registered secrets and a mid-recall policy change, invalid/unknown numeric metrics, retained stream closure before lease release, and the actual original token-gated `/api/model-routing` route. Numeric HTTP fixtures verify only current identity, at most 100 samples/32 history slots, no raw fixture environment leakage, and null unknown TTFT/rates.

Headless Edge screenshot/interaction review of the final built UI passed **16/16** at 1440x900, 900x650, and 640x700, with direct visual score **8.8/10**. The display uses explicit telemetry fixtures, preserves Geist, shows null/empty/one-sample states, breaks history at unknown samples, retains failure markers, distinguishes response and GPU observation ages, and labels retained data stale after refresh failure. No JavaScript errors or external font requests were observed. It is not a native Windows GUI review or live remote GPU measurement.

The owned primary helper was stopped through its session stop file. The already-running helper used an earlier verifier cleanup reporter that dereferenced an entry cleared by the original `ModelManager.close`, so it exited 1 after stopping the owned server and did not write its planned closed receipt. Independent reconciliation confirms **PID 28396 absent and no loopback/wildcard port-8080 listener** (`local-owned-20261009-a/cleanup-reconciled-os-table.json`). The socket probe returned Windows would-block, so socket refusal is explicitly not claimed; the OS listener table is the endpoint evidence. The helper reporter is fixed for future runs. No arbitrary or external process was killed. Previously owned remote Athena helpers still have unknown cleanup state.

The manager's final full regression completed after the independent quiet replay: **1,963 passed, 2 skipped, and 25 subtests passed in 320.92 s**, recorded in `data/v42-manager/final-regression.xml`. The XML records skips for a historical local-inference report absent from this checkout and the console-script check because `hanni` is not on PATH. This does not convert the earlier interrupted full-suite run into a pass. Package-wide verification belongs to the manager's integration checkpoint. Independent acceptance is **pass for measured local application/scheduler objectives with preserved tested correctness**, with remote hardware optimization and higher allocated contexts explicitly unverified.

```powershell
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/controlled_benchmark.py --output data/v42-verification/controlled-optimized-20261009-b
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/memory_benchmark.py --output data/v42-verification/memory-optimized-20261009-b
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/local_benchmark.py --output data/v42-verification/local-optimized-20261009-b --session data/v42-verification/local-owned-20261009-a --context
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/adaptive_telemetry_probe.py --output data/v42-verification/adaptive-telemetry-20261009-b
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/compare_benchmarks.py --baseline-suffix 20261009-a --optimized-suffix 20261009-b --output-suffix 20261009-c
.venv\Scripts\python.exe -X utf8 -m pytest tests/integration/test_performance_v42_verifier.py -q --junitxml=data/v42-verification/verifier-final-cycle6.xml
.venv\Scripts\python.exe -X utf8 scripts/v42_verification/reconcile_local_cleanup.py --session data/v42-verification/local-owned-20261009-a --output-name cleanup-reconciled-os-table.json
```
