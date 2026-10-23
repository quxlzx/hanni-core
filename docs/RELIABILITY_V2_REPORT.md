# HANNI Reliability & Intelligence V2

**Overall: PARTIAL.** Execution reliability and native observability passed their controlled checks. The untouched language evaluation did not establish a retrieval or model-selection improvement and missed the 95% required-tool recall target. No implementation was tuned or rerun against final failures.

The original Python controller, registry, MCP approval/schema boundaries, default permissions, configured model, memory, voice and screen architecture remain authoritative. Three genuine agents handled retrieval, reliability/UI and independent verification; root integrated, tested and checkpointed the result. Production source froze at `741a776` after backend `c4b8f26` and Activity `bd10e72`.

The completion/recovery rows below measure controlled independent fixture outcomes. Latency measures configured-model request completion, rather than time to an independently verified user objective.

```text
HANNI RELIABILITY & INTELLIGENCE V2

METRIC                         BEFORE              AFTER
--------------------------------------------------------------
Tool retrieval recall@K        66.7% (32/48)        66.7% (32/48)
Menu sufficiency               63.6% (28/44)        63.6% (28/44)
Model tool selection*          100% (28/28)         100% (28/28)
Argument correctness**         100% (2/2)           100% (2/2)
Verified task completion***    77.8% (14/18)        100% (18/18)
Recovery success***            0% (0/2)             100% (2/2)
Permission violations****      0                    0
P50 task latency               1280.39 ms           1350.58 ms
P95 task latency               2666.75 ms           2727.85 ms

EVALUATION
--------------------------------------------------------------
Existing regression tests:     PASS
Untouched holdout:             FAIL (recall target missed)
Workflow test suite:           PASS (controlled expectations)
Backend compatibility:         PASS (tested boundaries)
Security verification:         PASS (observed gates/privacy)
HANNI OS observability:        PASS

OVERALL STATUS:                PARTIAL
```

\* Actual configured-model selection **when a complete menu is available**. Across all 44 tool requests, selection remains 28/44. A sufficient menu, correct model call and completed user objective are distinct measurements.

\** Independently checked semantic arguments cover only two file-search cases per version. Structural schema validity is 50/50 before and 55/55 after; this does not establish semantic correctness for every argument. The initial baseline's broader 48/48 semantic label was too strong and is corrected in the independent final audit.

\*** Independent assertions on eighteen positive **exposed controlled development fixtures**, using isolated local state, controlled OS/provider evidence and a real local SDK fixture. They do not measure local-model language understanding or real external-provider/application success. The forty-case suite separately contains eight safe refusals, ten expected failures and four unverified receipts. Scripted intent is unmeasured. Original HANNI-recorded verification is absent for all eighteen cases; current HANNI-recorded VERIFIED scopes are 16/18, with external MCP outcome unverified and the memory wrapper lacking a task trace. Missing original records are not counted as failed outcomes.

\**** Zero forbidden adapter entries across 60 held-out requests per version, observing 48 before and 52 after controlled adapter executions. Separate original-gate adversarial tests pass. The workflow runner does not measure an aggregate unauthorized-sensitive-execution count; it cannot supply forty additional observed zeroes.

## What changed

Tool discovery adds revision-cached, weighted BM25 and bounded vocabulary-derived typo correction over registered metadata, with relevance/margin-based candidate counts and eligible-read filtering. Generic framing-word and argument-path normalization preserve original menu/argument contracts. Approved imported operation names remain discoverable without granting authority. No phrase-to-tool table, benchmark-ID dispatch, embedding download or second executor was added.

The original registry/session now records actual lifecycle events and separates execution from outcome evidence. Supported checks include authorized filesystem read-after-write, saved task/note state, process existence and calendar resource identity/title/schedule. Unknown writes and external self-assertions remain unverified; external read text is explicitly attributed. Followup checks retain original permissions, actor and emergency stop. Explicitly safe transient builtin reads receive at most one extra retry per effective call per turn. Random retry groups prevent unrelated later calls from erasing failures. Failed or ambiguous writes are not automatically replayed. Deduplication is turn-local, not cross-process exactly-once delivery.

Activity displays actual compact expandable traces through the original authenticated read-only API. Metadata-only bounded SQLite history excludes raw prompts, arguments, results, private paths, credentials and hidden reasoning. Unavailable/corrupt storage is preserved; observer failure does not replay an action. Historical approval cannot authorize a fresh session. CLI cleanup releases observational connections. Trace overflow retains incomplete/failing status.

Trace storage uses the current account's filesystem access; it does not provide encryption or tamper protection. Existing chat and audit stores remain separate.

## Final language/model evidence

The independent verifier sealed 60 cases before development: 44 tool requests and 16 negative, ambiguous, forbidden or unavailable requests. Required recall uses 48 required slots; complete-menu sufficiency requires all slots in a request. Mean exposed candidate count increases from 1.383 to 1.433, and conservative irrelevant exposure from 49 to 52. Correct metadata no-tool decisions remain 11/16. The four remaining unfamiliar development failures and the final holdout misses show that literal metadata does not reliably handle arbitrary indirect wording or synonyms.

Actual inference used the same cached Qwen3.5-4B-Q4_K_M, original client/session/registry, context 16384, max tokens 768, temperature 0.35, top-p 0.9, single slot, quantized KV and verified Vulkan1 33/33 offload. Provider/OS results are immutable controlled read-only adapters. Startup and neutral warmup are excluded. Both owned model processes were closed; no model download or cloud inference occurred.

Correct no-tool execution declines from 13/16 to 12/16. Controlled selection plus lexical evidence-answer checks decline from 41/60 to 38/60; this is **not independently verified user-task completion**. One apparent loss is a frozen lexical oracle rejecting correctly formatted thousands separators. Another reply omits expected diagnostic measurements, and an unapproved archive request makes an unrelated permitted read. Raw failures and oracles are retained. One sampled pass at temperature 0.35 does not establish a causal or statistically robust model-behavior regression.

Wilson 95% intervals (before to after):

| Measure | Before | After |
|---|---|---|
| Required-slot recall | 52.5-78.3% | 52.5-78.3% |
| Complete menu / all positive selections | 48.9-76.2% | 48.9-76.2% |
| Selection given complete menu | 87.9-100% | 87.9-100% |
| Semantic file-search arguments | 34.2-100% | 34.2-100% |
| Positive independent fixture outcomes | 54.8-91.0% | 82.4-100% |
| Two injected recoveries | 0-65.8% | 34.2-100% |
| Controlled selection plus lexical answers | 55.8-78.7% | 50.7-74.4% |
| No-tool execution | 57.0-93.4% | 50.5-89.8% |

The immutable set was published **after** final evaluation at [the final evaluation bundle](../evals/reliability/v2_final_holdout/README.md). Its original pinned SHA `b1ccb0aa512a95f418582d7bc7814f096af6788be7da7f13e3bbd686ae433d25` covers LF-normalized generated text; unchanged Windows CRLF file bytes have SHA `84e492db6d9dcaa66023c100af6637f1b67dc47ecbd585384993b19d541784b9`. Oracle SHA remains `378f369023c0af6f289123fdbdbb3189b5ac43b66e4f774bae4c6306f81b61e2`. All original case fields match baseline. Exact inputs/evaluators have text normalization disabled. Publication makes this set unsuitable for future unseen evaluation; a fresh sealed set is required.

## Workflow, latency and coverage evidence

The same forty fixtures ran once through original `791bdab` and frozen current source during a reserved quiet interval. All case/runner/runtime hashes stayed stable. Strict pipeline expectations improve from 29/40 to 40/40 (Wilson 57.2-83.9% to 91.2-100%). Two original conservative application answers were lexical false negatives; improved error specificity is not an original safety failure. The positive gains are file-path read retrieval, approved MCP operation retrieval and two transient-read recoveries. The ambiguous-action fixture drops from four attempts to one: three observed duplicates become zero.

Setup plus controlled pipeline latency rises from P50 14.070 to 33.192 ms and P95 751.395 to 783.586 ms; paired deltas are +17.307/+34.004 ms. This includes local stores, evidence/traces and SDK startup, excluding model inference. Actual-model task P50 rises 5.5%, P95 2.3%; mean latency is 1332.951 to 1330.857 ms across sixty tasks per version. Final host load includes 92.4% RAM use; equivalent baseline load was not sampled, so timing comparisons remain descriptive. Tool-model-round inference sums cover different subsets, 43 before and 44 after: P50 1523.26 to 1479.12 ms, P95 2605.08 to 2364.97 ms. They exclude plain/fallback turns and do not establish an all-task inference speedup. Independent time to verified user outcome is unmeasured by the language fixture.

The [172-capability evidence matrix](reliability-reviews/observed-capability-coverage.csv) separates static references, retrieval, model selection, handler entry and verification. The retained failed profiled development run observes 25 default registry handlers, leaving 147 without that evidence; direct-handler tests and dynamic MCP entries are separate. Final controlled workflow/model and genuine read columns retain their own scopes. Four original Windows clock/system/process reads pass without handler replacement or private-result output. Most capabilities still lack real OS/provider outcome evidence; unobserved does not mean broken.

## Acceptance and resumption

The complete corrected suite passes **1,057 tests, two existing skips and 17 passing subtests**, versus the original 964 passes/two skips/17 subtests. All 27 independent adversarial cases pass, including verification-gate, failed-write non-replay, bounded retry, wrong calendar title, malformed diagnostics, trace overflow, corrupt/future storage, privacy and historical approval cases. Full historical audits pass 194/194 model scenarios and 264/264 capability probes; strict routing remains 1,129/1,131 with its original two failures. Development unfamiliar recall improves 23/35 to 31/35; the rejected earlier 32/35 candidate is not the final result.

Native Activity passes 95/95 assertions. All 42 actual framed screenshots were independently inspected at four window sizes and 125% DPI, scoring 8.82/10 visually and 1.0/10 for template appearance. The 171-file runtime/config manifest remains `534e106c1d8971235a281c18d6ceebf5b0f45cad56a0b09371cb46d0f66dde32`, with frontend/native hashes separately stable. Offline wheel build and included-source equality checks pass. Earlier failing cycles remain documented.

Resume from [milestone checkpoints](RELIABILITY_V2_CHECKPOINTS.md). Keep this source/evaluation freeze and failed artifacts. Next work should use new development examples and a fresh sealed holdout to evaluate semantic retrieval alternatives, reduce irrelevant menus, strengthen independent semantic argument/clock oracles, cover the memory fast path and add safe real provider/application verification. Broader capability execution and additional DPI coverage remain outstanding. Final scores must not be used to tune and then claim this same holdout is unseen.

Detailed evidence: [independent final evaluation](reliability-reviews/m5-final-evaluation.md), [controlled workflow comparison](RELIABILITY_WORKFLOW_DEVELOPMENT.md), [security/failure history](reliability-reviews/adversarial-development.md), [native acceptance](reliability-reviews/m4-native-cycle-3.md) and [coverage methodology](reliability-reviews/observed-coverage.md).
