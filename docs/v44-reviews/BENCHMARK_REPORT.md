# V4.4 independent actual-model benchmark

**Status: PARTIAL. Live adaptive superiority was not demonstrated.** Both modes
used the same existing local endpoint and passed 2 of 8 sealed final tasks. This
report separates real responses, unavailable rejected output, original-controller
workflow failures, and scripted engineering tests.

## Frozen protocol and identities

The independent verifier created private cases and typed exact JSON oracles
before execution. Existing final-holdout corpora were never opened. Final answers
were not shared with engineering or used to change production or expected
answers. Private prompt, oracle, and response files remain ignored.

The original protocol hash was
`ffd28d3c7ecdde3b0efc7a117b534582751c9ede8d9e8162468591432c322241`.
Its first attempt exposed an infrastructure defect: slow protected remote
discovery expired the genuine local heartbeat. Seven arms safely blocked with
zero inference calls, and nine were not tested. The owned helper was stopped
after exact receipt checks; this was an abrupt owned-helper interruption, not a
claim of graceful case cancellation. That attempt remains preserved and was not
retried.

After an independently reproduced infrastructure repair, eight distinct new
cases were sealed under protocol
`f675c0442b3d420739b51958cd1f7cb46a2f14e2039db0e2ac07af9cc91a95d9`.
The new campaign attempted all 16 arms once. Fixed/adaptive AB and BA order
alternated, with equivalent bounds: temperature 0, top-p 1, 192 output tokens,
zero fallback, one original serving slot, sequential dispatch, and original
privacy, resource, health, context, and authoritative admission checks. The
fixed arm pinned local supervisor; the adaptive arm used the original balanced
selector. Neither changed global policy or published accuracy proofs.

The actually loaded model was **Qwen3.5-4B-Q4_K_M.gguf**, not the unconfigured
custom HANNI-4B-v0 file. Model SHA256:
`25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`;
size 2,707,513,696 bytes. Runtime: existing llama.cpp, Vulkan1, configured context
16,384, one parallel slot, q8_0 K/V cache, thinking disabled. No model was
downloaded, moved, substituted, or restarted. The observed endpoint identity was
`8230bcbc409ed19dcc992bd67d40aee6e0e29fb47e8447a366e052f83ed48931`.
Configured context and live identity are distinct from independently certified
maximum-context accuracy.

The serving process remained PID 38832, creation time 1791595415.4806464, under
the original dashboard launcher PID 46084, creation time 1791595411.2839503.
The original ModelManager recognized it as external (`process=None`) and did not
adopt or terminate it. Host inventory observed an RTX 5060 Laptop GPU, 8,151 MB
total VRAM, and 31.61 GB host RAM. Initial RAM use was 75.3%; original resource
guards remained active. GPU placement remains unverified by a newly owned load.

Final production hashes:

| Source | SHA256 |
| --- | --- |
| compute/scheduler.py | cc3d5afc20d3f8261b5e551532d21f424c4dac242956152b1378f5b4fee6dd6d |
| models/adaptive.py | 4489ba3b691970bd25728fd27ec909baf3c1e06fe66348e162d5ccde0f240370 |

Version was 0.14.0. Per-file source fingerprints and runtime configuration are
retained with each private final artifact. Evaluation occurred October 9 local
New York time / October 10, 2026 UTC. Manager and Engineer avoided heavy testing
during the paired final campaign. The existing external server, application,
request caches, and other owner activity were not exclusively controlled.

## Actual results and complete rubric accounting

The declared 10-point rubric is intent / model-and-tool selection / factual
accuracy / evidence / clarity / efficiency, with maxima **2/2/2/2/1/1**.
A critical safety violation automatically fails a case regardless of points.
Exact typed JSON equality against frozen private source calculations was the
success oracle. No tools were required in these model-only final cases.

| Sealed case | Fixed outcome | Adaptive outcome | Rubric in each mode | Score in each mode |
| --- | --- | --- | --- | --- |
| postrepair-arithmetic | Exact pass | Exact pass | 2/2/2/2/1/1 | 10 |
| postrepair-analysis | Original structured-output rejection | Same rejection | 0/2/0/0/0/0, limited grading | 2 |
| postrepair-planning | Original structured-output rejection | Same rejection | 0/2/0/0/0/0, limited grading | 2 |
| postrepair-coding | Accessible answer: wrong requested key and value | Same observed failure | 0/2/0/0/0/1 | 3 |
| postrepair-ambiguous | Exact pass | Exact pass | 2/2/2/2/1/1 | 10 |
| postrepair-no-tools | Original structured-output rejection | Same rejection | 0/2/0/0/0/0, limited grading | 2 |
| postrepair-long-context | Original structured-output rejection | Same rejection | 0/2/0/0/0/0, limited grading | 2 |
| postrepair-structured | Original structured-output rejection | Same rejection | 0/2/0/0/0/0, limited grading | 2 |

There were **16 actual model dispatches**, **6 accessible answers**, **4 exact
passes**, **2 accessible wrong answers**, and **10 original output-verification
rejections**. The original engine's exception boundary retained identity,
usage, latency, original error, and performance telemetry but did not expose the
raw rejected text. Those ten responses cannot receive full factual grading.
Their zero evidence/accuracy credits mean *not demonstrated*, not a proven
factual falsehood. The original ModelSelectionError records are preserved.
Prospective private raw-capture support was added only after that function was
already loaded; it was not exercised on this campaign. No parser was relaxed and
no final response was retried.

The conservative end-to-end service rubric average is **4.125/10 in each mode**.
It is not a complete intrinsic model-factual score. Accessible-answer subset
mean is 7.67/10, n=6 combined; selecting that subset would hide the ten service
failures, so it is not the headline score. There were **zero critical safety
failures** and **zero discordant success pairs**.

The harness generated a Wilson interval of 7.15–59.07% for 2/8. **It is unused as
an inferential confidence claim**: eight purposively selected heterogeneous tasks
and a shared deterministic endpoint do not satisfy representative independent
sampling assumptions. No population reliability or adaptive-effect confidence
claim is made. Larger independently sampled campaigns are required.

## Actual timing observations

| Observation | Fixed, n=8 | Adaptive, n=8 |
| --- | --- | --- |
| Exact task success | 2/8, 25% | 2/8, 25% |
| Original execute-call P50 | 685.84 ms | 614.15 ms |
| Original execute-call P95 | 1,332.73 ms | 792.06 ms |
| TTFT mean / median | 389.12 / 328.83 ms | 288.62 / 281.93 ms |
| Generated tokens/s mean / median | 82.24 / 85.44 | 83.24 / 84.05 |
| Prompt tokens/s mean / median | 354.21 / 79.48 | 143.60 / 87.15 |

P50 is the median and P95 is nearest-rank ceil(0.95*n). Execute time begins just
before the original engine executes and ends at the original result/error. It
excludes the preceding protected refresh. TTFT and token rates originate from
actual SDK telemetry, including rejected-output calls; they are not estimated
from prose length. Prompt-rate means are sensitive to the long-context sample
and shared prompt cache.

Refresh-inclusive total campaign wall time was **556.11 seconds for 16 arms**.
Repeated failed authorized remote checks dominate that total. It includes refresh,
original admission, inference, scoring, and harness overhead; per-arm refresh
durations were not separately instrumented. It must not be reported as model
generation latency. Both modes reached the same physical model, so their timing
differences are descriptive observations, not proof of adaptive speed gains.

## Separate development and unavailable hardware

Two actual original-planner workflows failed before execution: the analysis plan
omitted the full required input path, and the mirror plan encoded predecessor
references as malformed literal strings. Independent scoped review cancelled the
second plan. No synthetic plan or result replaced either failure. Verified actual
tool/calculation/artifact/readback objective completion was **0/2**. This is
separate from the sixteen final model-only arms and does not establish a
regression against a paired historical workflow baseline.

The actual native Model Lab ran two exposed-development repetitions of one
structured case, three responses per run: **6/6 exact development passes**. This
checks native execution/export/comparison/persistence and is not held-out
intelligence certification. The original memory-assisted conversation recalled
a genuine private stored preference, but appended an irrelevant verification
caveat; full response quality remains partial.

P40 27B, P6000 27B, and Wonyoung Strata each failed fresh registered-transport
health checks. No private prompts were sent, no remote helper was started, and
no authentication boundary was bypassed. Live cross-model quality, distributed
stress, remote concurrency, and hardware speed ranking are **BLOCKED**.
Engineering's 432 routing outcomes, seven collaboration scenarios, and scripted
outage comparisons are controlled fixtures, not real multi-model responses.
Consensus never substitutes for the original independent verifier's outcome.

## Private evidence

- `data/v44-verification/inventory-20261009-a/inventory.json`
- `data/v44-verification/final-protocol-20261009-a/`
- `data/v44-verification/session-final-20261009-b/final-results.json`
- `data/v44-verification/final-protocol-postrepair-20261009-c/`
- `data/v44-verification/session-postrepair-20261009-c/final-results.json`
- `data/v44-verification/live-workflow-development-a/results.json`
- `data/v44-verification/live-workflow-mirror-c/results.json`
- `data/v44-verification/native-20261009-d/` and `native-20261009-e/`
- `data/v44-verification/session-persistence-20261009-e/persistence-readback.json`

Recommendation: preserve the current main model configuration. Investigate
original rejected-output retention and planner path/typed-reference construction
using new exposed-development cases. Revalidate with larger independently
sampled tasks and genuinely authorized distinct endpoints before selecting a new
main model or claiming V4 multi-model improvement.
