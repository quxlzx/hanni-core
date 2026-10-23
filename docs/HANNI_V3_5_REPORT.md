# HANNI V3.5 — LAYA personal intelligence

Implementation date: 2026-10-09. **Final status: PARTIAL.** The engineering implementation and independent verification are delivered, but the sealed quality gates were not met and an installed LAYA predictor is unavailable. The evaluated implementation is frozen at `eb41f42`. Experimental context, advisory and reranking remain disabled by default. Production HANNI was kept stopped and Qwen remains the main model.

## Delivered behavior

The existing authoritative MemoryStore migrates additively to schema v3 with stable identity, project association, source references, semantic distinctions, correction history and separate review suggestions. Original record IDs/content/source/raw timestamps survive migration; optimistic checks accept equivalent UTC timestamp representations. Deletion purges associated history and suggestion copies, and subsequent context reads use current records.

Conservative local rules distinguish statements, plans, decisions, questions, hypotheticals, inferences, historical information and unverified completion/failure claims. Their importance labels and lexical relevance scores are heuristics, not calibrated probabilities. They create relationship/conflict/staleness proposals without choosing the newest statement as truth. Local owner-requested analysis and consolidation explicitly identify their rule-based origin. Model-generated suggestions cannot approve themselves, verify outcomes or execute tools.

Memory Explorer adds browsing/filtering, source/history details, exact-version correction/deletion, suggestion approval with optional owner edits, rejection/dismissal, project context and explicit aliases/workflow links. Mutations use the original authenticated registry, permission/profile, confirmation, Safe Mode, audit and idempotency boundaries. Sensitive imported content/history/source fields are withheld. Missing projects and sources are described explicitly.

Optional deterministic context combines selected project packages and distinct general memories under one bounded budget. Existing workspace project IDs and explicitly linked original workflow receipts are reused. Verified outcomes require original execution, result/evidence and required-criteria verification. Context inspection cannot resume or execute a workflow. Ambiguous continuation asks for project selection before generation; current instructions take precedence over untrusted memories in the original model pipeline. Context text is rebuilt per request and memory-derived response turns are not retained in conversation history.

The separate versioned advisory endpoint preserves legacy shadow acknowledgements. Its asynchronous client validates exact response types, operation/version, record IDs/revisions and authority fields, with bounded payloads/queue/cache/concurrency, timeout fallback and invalidation. It has no authoritative database writer. Stored-memory consent is separate from remote owner-text consent and remote-memory consent. Controller admission is rechecked before transmission. The default factory cannot open the independent model gate; configuration flags alone never prove model quality or activate it.

## Component acceptance

Engineering PASS means tested implementation behavior, not successful trained LAYA inference or general model quality.

| Component | Status | Evidence or limit |
|---|---|---|
| Existing LAYA contract compatibility | PASS engineering; actual inference BLOCKED | Legacy question/ACK contract preserved; local `laya` runtime/checkpoint unavailable |
| Memory extraction | PASS controlled rules; trained quality NOT TESTED | Conservative explicit-owner proposals; no automatic inferred-fact save |
| Importance and relevance scoring | PARTIAL | Uncalibrated rules/lexical weighting; trained calibration and semantic quality unavailable |
| Context retrieval | PASS engineering; quality FAIL | Bounded live provenance; sealed holdout recall misses 90% target |
| Project identification | PASS engineering; quality FAIL | Persisted IDs/aliases and ambiguity handling; holdout 5/6 misses 95% |
| Temporal distinctions | FAIL quality | Sealed validation/holdout 3/6 each; 95% target unmet |
| Relationship and conflict analysis | PASS controlled tests | Proposals use explicit keys/associations; no automatic truth resolution |
| Memory consolidation | PASS engineering | Bounded local proposals; no automatic merging/deletion/archive |
| Owner approval workflow | PASS | Original authorization, explicit confirmation and revision binding |
| HANNI OS Memory Explorer | PASS | Independent native 8.7/10 visual, 1/10 template; final message spot check passed |
| V3 workflow context integration | PASS engineering | Existing explicit links/history and verified receipts; no new executor |
| Privacy/deletion/remote-consent enforcement | PASS controlled tests | Independent HTTP/SQLite/advisory regressions; no genuine remote inference attempted |
| Offline fallback | PASS | Original deterministic reads survive optional service failure and Safe Mode |
| Backend regression | PASS | 1,518 tests plus 25 subtests passed; two existing skips |
| Generated source grounding | FAIL quality | Actual Qwen literal success 2/12 per arm; semantic task success 4/12 per arm, two unsupported assertions in D |

## Independent benchmark protocol

Exactly three real Codex subagents were used: two implementation workers with separate ownership and one independent verifier. The verifier archived 28 original files from `f19dd00` before edits, manifest SHA-256 `2de6e76ccc5c43f803cbc831cd0f5f26bded0d622632e4b6fa01dbc28c79c43d`. Original memory/shadow/M9 tests passed 24/24. The full pre-implementation run passed 1,396 tests and 25 subtests with two existing skips.

The independent synthetic suite has **240 distinct scenarios**, 15 families ×16 cases, sealed prospectively as **60 development, 90 validation and 90 untouched holdout**. Development inputs could guide implementation. Candidate source and adapter were frozen before once-only validation and holdout; failures are retained and no production tuning followed them. Baseline source was evaluated separately. Candidate source SHA-256 is `3f5720b48d7d31b87597074725bed128f1e38677634b8eaf47fe72a6668dd6d0`; evaluator SHA-256 is `04f83e0eaba6c0cf1e63484b64da4eec333225ba533ea9b57fe53cb417fae4f0`.

Baseline A covers the original APIs: 128 supported cases and 112 NOT AVAILABLE feature cases. B uses deterministic contextual retrieval; D uses full explicitly enabled context integration. C requires actual LAYA and is **BLOCKED**, with no generated predictor results substituted. Baseline aggregate Recall@5 is **63.75% across 16 queries**, with 10/16 meeting the full-case oracle. This all-split aggregate must not be compared directly with the six-query candidate holdout as though they were identical partitions.

The comparable partition-level recall results are:

| Recall@5, same sealed split | A original | B retrieval | D full context |
|---|---:|---:|---:|
| Development, four queries | 75% | 100% | 100% |
| Validation, six queries | 100% | 83.33% | 83.33% |
| Holdout, six queries | 20% | 20% | 33.33% |

B has no demonstrated holdout recall improvement over A; both candidates perform worse on validation. D's small holdout improvement does not meet the target. Baseline precision was not recorded in its original raw output and is NOT MEASURED rather than reconstructed silently.

Before candidate validation, the adapter documented vocabulary mappings `statement → fact`, `completed_claim → completed`, and `failed_claim → failed`. It does not grant semantic credit to hypothetical/conditional claims. Original inputs and answers were unchanged. The original baseline summary accidentally emitted zero security counters outside exercised authorization/remote paths; a reporting erratum marks these **NOT MEASURED** and retains raw output. The separate actual security regressions provide those measurements.

| Frozen candidate measurement | B validation | D validation | B holdout | D holdout |
|---|---:|---:|---:|---:|
| Full-case pass count | 84/90 | 84/90 | 80/90 | 81/90 |
| Relevant memory Recall@5, six queries per split | 83.33% | 83.33% | 20.00% | 33.33% |
| Project identification | 6/6 | 6/6 | 5/6 | 5/6 |
| Temporal distinction | 3/6 | 3/6 | 3/6 | 3/6 |
| Preference cases | 5/6 | 5/6 | 5/6 | 5/6 |
| Actual trained LAYA inference | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |

The holdout privacy, injection, deletion, conflict, relationship, consolidation, workflow and unavailable/fallback families each passed 6/6. The independently frozen HTTP/SQLite/advisory security suite passed **40/40**; it separately measures authorization and consent paths that the quality suite does not exercise. Six cases per family are a small sample; these results are controlled evidence, not a general safety or accuracy guarantee. Workflow scores concern context recovery/verification distinctions, not autonomous goal execution. Existing V3 planning's earlier 0/15 fresh-goal result remains unchanged.

The 90% recall and 95% project/temporal targets are **not met on holdout**. A high count of passing deterministic cases does not establish trained semantic capability. The lexical strategy generalizes poorly to unseen wording. Production LAYA retrieval stays blocked, and the original retrieval path remains the shipped default.

## Performance and actual-model grounding

The coordinator reproduced the separate visible **20-case public development** comparison, with 16 positive and four negative cases. Both arms share today's v3 store: A is original lexical retrieval and B is deterministic weighted retrieval. This is not the independent original-source baseline or held-out acceptance suite. Timings exclude fixture creation and alternate arm order, with 60 same-process samples per arm.

| Public development measurement | A | B |
|---|---:|---:|
| Macro Recall@5, 16 positive scenarios | 68.75% | 100% |
| Mean relevance precision, 20 scenarios | 65% | 90% |
| Correct empty retrieval, four negative scenarios | 4/4 | 4/4 |
| P50 retrieval | 0.966 ms | 1.024 ms |
| P95 retrieval | 1.258 ms | 1.368 ms |
| Mean injected characters/UTF-8 byte bound | 457 | 874.1 |
| Authoritative memory mutations | 0 | 0 |

Source-ID grounding passed 20/20 per arm but checks identity only, **not generated factual accuracy**. Byte bounds are not model token counts. These small-store development timings do not measure production load or end-to-end response overhead. The independent 240-case timing records fixture-inclusive timing separately from an operation-boundary timer. On six holdout retrieval queries, B boundary P50/nearest-rank P95 was 2.18/2.66 ms and D was 4.03/17.83 ms; D includes original session forwarding. Original A did not record that boundary timer. The independent report corrects the raw summaries' floor-rank P95 method without overwriting them. These small samples are descriptive rather than population latency estimates. Actual LAYA inference latency/calibration is NOT TESTED.

The independent verifier sealed a separate prospective **12-case actual cached-Qwen A/D cohort** and generated each response once, using the same existing Qwen3.5-4B-Q4_K_M weights/settings and original model/session pipeline, fresh sessions and synthetic source records. All 24 responses and failures were retained, without retries, prompt edits or production tuning. No tools, OS/provider actions or production stores were used. Both arms share the current store to isolate context selection rather than migration.

| Actual Qwen measurement, 12 cases per arm | A original retrieval | D full context |
|---|---:|---:|
| Frozen literal answer oracle | 2/12 | 2/12 |
| Independent semantic task review | 4/12 | 4/12 |
| Responses with unsupported memory assertions | 0/12 | 2/12 |
| Total measured SSE prompt tokens | 5,033 | 5,291 |
| Total measured generated tokens | 103 | 107 |
| Mean measured prompt tokens | 419.42 | 440.92 |
| Extra prompt tokens versus empty-context template | 0 total | 258 total; 21.5 mean |
| Response P50/nearest-rank P95 | 206.58/447.79 ms | 179.86/661.28 ms |
| First content P50/nearest-rank P95 | 114.64/249.00 ms | 84.86/391.78 ms |
| Authoritative source-store changes | 0 | 0 |

Semantic review is a separate inspection of generated meaning against the frozen sources, not a replacement or modification of the literal oracle. Correct absence/clarification accounts for the semantic passes. Eleven D prompts injected no context: longer task/output instructions diluted lexical relevance. The one injected continuation named the documented model decision and issue but upgraded the decision to operational state; another response invented an editor preference without supporting context. This demonstrates neither answer-quality improvement nor the requested 98% grounding target. Task success is distinct from per-claim factual accuracy; the latter is not inferred from record-ID tests or absence of a claim.

All 24 SSE prompt counts were measured. One empty-context full-template tokenization per case, without extra generation, agreed with actual full SSE counts. D increased total input tokens by **5.13%**; token reduction is not demonstrated. A preceded D in each pair; caching and stochastic sampling were not controlled. D has a lower median but a higher observed P95, and no causal speed improvement is established. The independent report supplies tokenization scope and context-construction details. Owned server startup took 10,806.96 ms; its process was closed and production model selection was unchanged.

## Native review and corrections

Independent native Win32/WebView2 review initially scored 8.35/10, below the required greater-than-8.5 gate. Status/header/filter density and wrapped controls were corrected. Native cycle 6 then passed 10 checks and 18 physical frames across four sizes; actual correction, approval and deletion used the original controller against synthetic stores. Visual quality reached **8.7/10** and template appearance **1/10**. Cycle 7 checked the final history-withholding message in an imported-private-history scenario: **11 checks and 19 frames**, accepted score retained, no JavaScript errors/external requests, unchanged final bundle hashes, and owned app closed.

Earlier harness discovery/label locator failures are retained separately and not misrepresented as product failures or successful checks. At 900 pixels wide, scrolling is required; an empty search may retain the previously selected detail. These minor clarity limits do not change the controller checks. The coordinator independently built TypeScript/Vite and passed all four typed-control Node tests.

The clean full regression passed **1,518 tests plus 25 subtests**, two existing skips, zero failures/errors, in **219.132 seconds** (`data/v35-review/final-clean-regression.xml`; JUnit includes 1,545 outcomes). The first final run had one mirrored K2-profile defaults mismatch, no other failures and two existing skips. The selected profile was synchronized without changing model identity/settings; its compatibility test plus 12 project tests passed. The failed run artifact is retained rather than overwritten.

## Deployment and remaining limitations

See [configuration and operation](HANNI_V3_5_SETUP.md), [milestone checkpoints](HANNI_V3_5_CHECKPOINTS.md), and [the independent review](v35-reviews/HANNI_V3_5_INDEPENDENT_REVIEW.md). No production service was started, main model switched, private memory migrated by the tests, model downloaded, credential added to source, unrelated training artifact changed, or repository pushed/published. All implementation/verification stores and native windows were isolated and owned. The coordinator confirmed no live HANNI or llama-server process and no source diff in the original Core, tool router, MCP, workflows, voice or model/permission/privacy configurations.

The exact 240-case corpus, protocol, manifests and five minimal original memory modules are exported under [evals/memory_intelligence_v35](../evals/memory_intelligence_v35/README.md); `scripts/eval_memory_intelligence_v35.py` reproduces A/B/D without trained inference. An additional 12-case prospective Qwen corpus and `scripts/eval_memory_grounding_v35.py` preserve actual-model reproduction with explicit matching existing weights. All original case/oracle hashes remain identical. Scoped Git attributes preserve evaluated bytes across newline conversions. The coordinator checked frozen hashes in the Git index and ran exported development A/B/D successfully with no evaluation errors; expected failures remain. Validation/holdout were not rerun for the export. The scored holdout is now public and cannot serve as a future untouched holdout. Raw transcripts, private baseline archive, synthetic databases and native screenshots remain local ignored artifacts; only sanitized aggregate outcomes and review hashes are committed.

Leave `memory.context_enabled`, LAYA advisory and LAYA retrieval disabled for production. The Explorer and explicit owner review work with existing local records. A separately verified installed predictor and fresh unseen evaluation are required before assessing semantic reranking or calibrated importance. Configuration consent alone cannot open the trusted quality gate. Historical draft LAYA scores are not reused as results or promotion authority.

Future improvements should target unseen paraphrases, unknown project references and temporal ambiguity, then use newly sealed evaluation data. The original holdout is now scored and must not be reused as untouched validation after tuning. Actual remote checkpoint health, trained extraction/relevance/calibration, semantic/vector search, live-provider behavior and autonomous benchmark execution remain unavailable or unverified. Existing controller/workflow safeguards and documented V3 planning limitations remain in force.

**LAYA deployment:** legacy shadow contract PASS; actual shadow inference NOT TESTED. Advisory engineering PASS; actual model deployment BLOCKED. Production LAYA retrieval DISABLED/BLOCKED. **Final status: PARTIAL**: engineering implemented and independently checked; quality targets fail and actual LAYA promotion is blocked.
