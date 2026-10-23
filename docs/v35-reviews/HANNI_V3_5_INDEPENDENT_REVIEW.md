# HANNI V3.5 independent verification

The deterministic implementation and Memory Explorer pass the tested safety and native UI checks. **The requested intelligence quality gates are not met. Genuine trained LAYA quality is NOT TESTED and production admission remains blocked.** The untouched holdout exposes substantial lexical recall and temporal-classification limitations. The separate real-Qwen cohort does not demonstrate reliable factual personalization or token savings. No result was rerun or tuned to improve these failed acceptance scores.

## Freeze and prospective protocol

M0 was frozen before implementation at `f19dd00aef5e7b0d2dd318e7eb48c720411e3242`. The original 28-file manifest SHA-256 is `2de6e76ccc5c43f803cbc831cd0f5f26bded0d622632e4b6fa01dbc28c79c43d`; independent original memory/shadow/session regressions passed 24/24. The root full baseline passed 1,396 tests plus 25 subtests with two existing skips.

An independent verifier sealed 240 synthetic cases, 16 for each of 15 families: extraction, importance, retrieval, project resolution, conflicts, temporal status, preferences, workflows, privacy, deletion, negative queries, unavailable transport, injection refusal, relationships and consolidation. Each family has four development, six validation and six holdout cases, totaling **60/90/90**. Expected outcomes were prospectively reviewed by the verifier agent, not an external human panel. The untouched holdout inputs and oracles were withheld from implementation workers until all candidate scoring completed.

Final source was frozen at `eb41f42cc463d2bcd1bee3241beac716ef229ed1`. The production source manifest SHA-256 is `3f5720b48d7d31b87597074725bed128f1e38677634b8eaf47fe72a6668dd6d0`, and the original evaluator SHA-256 is `04f83e0eaba6c0cf1e63484b64da4eec333225ba533ea9b57fe53cb417fae4f0`. Source hashes were checked after once-only validation and holdout, with zero drift. Case files were not edited after scoring. Literal adapter spellings were frozen before validation: `statement` → `fact`, `completed_claim` → `completed`, and `failed_claim` → `failed`. No broader hypothetical/conditional interpretation received artificial credit. Earlier development scores retain their original raw adapter behavior and are not silently replaced.

Original case seals, preserved byte for byte in the repository:

| File | SHA-256 |
| --- | --- |
| Development | `6091fe59739f21483e62bd8f1f5f473f521ba6bc5be364cb2f007bc1e646615e` |
| Validation | `81015837e992ae8913b38a901dea66fa0bed521a63d5b6f83dadc73c811f7571` |
| Holdout | `1c1ebffd22c8e3d099ebf4c25fe26b563fd49bbdc1d9885b00052fc69a0d2b87` |
| Protocol | `cae9739a0212514b57c379a494b678d54f7139af60096ff8842e528d6dcaa503` |

The arms must not be conflated:

- **A:** Original five memory modules and schema-v2 store. Seven new-feature families are NOT AVAILABLE, not model failures. Original A ran on all 240 sealed cases before implementation.
- **B:** Actual candidate store and deterministic proposal/status rules plus weighted lexical retrieval. This is not trained LAYA. Importance is an uncalibrated heuristic, not a correctness probability.
- **C:** Genuine LAYA advisory extraction/reranking quality is NOT TESTED. No safe authenticated installed inference target was available. Controlled transport openers are explicitly contract/fallback fixtures, never substituted for model inference.
- **D:** Actual opted project/general context provider and original `MemoryAwareSession` forwarding boundary. The large synthetic suite forwards to an identified controlled sink without inference. Its source-ID checks cannot establish generated-answer factual accuracy.

## Results retained after freeze

Validation and holdout B/D were each scored exactly once. Public development reproduction later checked export portability without changing code, cases or gates.

| Arm | Development | Validation | Untouched holdout |
| --- | ---: | ---: | ---: |
| A, supported features only | 30/32; 28 absent | 47/48; 42 absent | 42/48; 42 absent |
| B, all candidate families | 58/60 | 84/90 | 80/90 |
| D, all candidate families | 58/60 | 84/90 | 81/90 |

There were zero evaluator errors. The A/B/D pooled totals have different supported-feature denominators and cannot be treated as a model-quality improvement statistic. A overall supported-feature score is 119/128, with 112 NOT AVAILABLE. Earlier B development cycles retain harness faults and a 57/60 pre-final result; the final 58/60 reproduction includes the already frozen literal status mapping and later development fixes, not holdout tuning.

Same-split retrieval comparisons are particularly important:

| Metric | A validation | B validation | D validation | A holdout | B holdout | D holdout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Macro Recall@5, six queries/split | 100% | 83.33% | 83.33% | 20% | 20% | 33.33% |
| All relevant IDs returned, six queries | 6/6 | 5/6 | 5/6 | 1/6 | 1/6 | 2/6 |
| Preference case accuracy, six cases | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 |
| No irrelevant recall, six negatives | 6/6 | 5/6 | 5/6 | 6/6 | 6/6 | 6/6 |

B/D validation and holdout each have temporal accuracy 3/6. Project resolution is 6/6 validation and 5/6 holdout. Extraction, importance utility bands, conflict refusal, consolidation review, relationship review, deletion, privacy refusal, injection refusal, unavailable-advisory fallback and controlled workflow receipt interpretation each pass 12/12 across validation and holdout per candidate arm. These small hand-controlled samples do not justify calibrated or general semantic claims.

All returned record IDs and exact live content matched the fixtures: nine returned records in B and 18 in D across their 24 retrieval/negative queries. Sixteen queries per arm returned nothing; vacuous empty checks are not counted as evidence of generated factual accuracy. No generated answers were produced in this 240-case suite.

The requested Recall@5 ≥90%, project ≥95% and temporal ≥95% targets fail on the untouched holdout. Controlled workflow/source and deletion checks pass, but do not override these failures or substitute for unavailable LAYA quality. The trained-model production gate remains closed.

Retrieval timing was measured separately from fixture setup. The table uses nearest-rank P95; original raw summaries retain their floor-rank statistic and are not overwritten. With six observations, nearest-rank P95 is the observed maximum.

| Arm/split, six retrieval queries | Retrieval boundary P50/P95 | Fixture plus operation P50 | Mean context UTF-8 bytes |
| --- | ---: | ---: | ---: |
| B validation | 1.63 / 2.03 ms | 56.54 ms | 598.83 |
| B holdout | 2.18 / 2.66 ms | 93.41 ms | 329.83 |
| D validation | 4.09 / 14.45 ms | 149.37 ms | 718.17 |
| D holdout | 4.03 / 17.83 ms | 149.00 ms | 664.67 |

B measures actual retrieval; D includes actual session forwarding and context assembly. Store seeding is excluded from those boundary timings. Some arms ran concurrently and the samples are tiny, so these values are descriptive rather than causal performance estimates. Characters and UTF-8 bytes are measured; chars/4 in older summaries is only an estimate. The UTF-8 budget is conservative, not exact tokenizer accounting.

## Independent safety and backend preservation

The final independent verifier regressions pass **40/40** on frozen source. They exercise the actual private HTTP server, ToolRegistry, MemoryStore and original session boundary with isolated synthetic data. Tested paths include authentication, same-origin writes, explicit owner confirmation, Safe Mode, source-bound approved/rejected/dismissed/pending proposal deletion, correction-history removal, exact version checks, source authenticity, cross-process correction/deletion, secret filtering, Unicode package bounds, advisory gates, bad schemas, unknown/stale IDs, invalidation of queued raw requests, in-flight late callbacks and consent revocation. No unauthorized authoritative write or unapproved remote transmission occurred on those exercised paths. The controlled opener never sends to a real remote model.

The original quality baseline initially reported zero critical writes/sends without exercising those paths. That reporting error is preserved and corrected explicitly in `results/baseline-A-reporting-erratum.json`: these fields were **NOT MEASURED by the quality suite**. Separate 40-test safety evidence supplies the scoped conclusion; absence of observed failures is not an exhaustive security proof.

The root final regression passed 1,518 tests plus 25 subtests, two existing skips, zero failures/errors, in 219.132 seconds. Frontend build and four typed frontend controls passed. Existing core/model/permissions/privacy/router/voice/workflow source was preserved. Production HANNI remained stopped; no user store, vault, real SSH, power or provider action was used. New remote stored-memory consent was not granted or inferred. Default context remains legacy and enhanced context/advisory admission remains off.

## Actual main-Qwen cohort, 24 responses once

A separate 12-case prospective synthetic cohort was sealed before generation, covering preferences, paraphrased results, decision versus plan versus claim, controlled verified source metadata, correction, deletion, irrelevant memory, contradiction, project continuity and privacy-gated legacy injection. Case SHA-256 is `f372f6e51a032a359b5eb37301749673b530af314840530fe2d5a9d5193f52f9`; protocol SHA-256 is `a2d3cc64a149b8a7840431e6e6e6538290bcd49d8e3f06470445cbf2450aea3b`.

The actual existing Qwen3.5-4B-Q4_K_M.gguf weights were used, SHA-256 `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`, 2,707,513,696 bytes. No model download or replacement occurred. An owned isolated loopback ModelManager loaded the existing runtime with 33/33 layers offloaded. Fresh original TextSession/MemoryAwareSession instances used the same original system prompt, temperature 0.35, top-p 0.9, max output 768 and thinking disabled. No tools were registered, extraction was disabled, each arm/case generated once with no retries, and every synthetic store was unchanged afterward.

This A/D cohort isolates retriever/context packaging over a **common current-schema store**: its A uses the frozen original retriever class but is not the full schema-v2 M0 arm above. D uses explicitly opted project/general context. Controlled verified record metadata is a fixture, not a newly executed workflow. The legacy injection case is excluded by the store privacy gate before generation and cannot establish model-level injection resistance.

| Measured real-Qwen outcome, 12 cases/arm | A | D |
| --- | ---: | ---: |
| Frozen literal oracle passes | 2/12 | 2/12 |
| Independent semantic task passes | 4/12 | 4/12 |
| Inference errors | 0 | 0 |
| Actual SSE prompt tokens, total | 5,033 | 5,291 |
| Actual generated tokens, total | 103 | 107 |
| Actual extra prompt tokens versus empty context, total | 0 | 258 |
| End-to-end response P50 / nearest-rank P95 | 206.58 / 447.79 ms | 179.86 / 661.28 ms |
| First content P50 / nearest-rank P95 | 114.64 / 249.00 ms | 84.86 / 391.78 ms |

Every server usage count was captured from the actual streaming response. An additional non-generating original empty-context message construction was formatted and tokenized once per case. Each full formatted tokenizer count agreed exactly with its actual SSE prompt usage; the extra-versus-empty counts are therefore measured. These read-only formatting/tokenizer endpoints perform no additional generation. Their behavior is documented in the [llama.cpp server reference](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

The full natural task prompts include output instructions. Lexical retrieval supplied no context for 11/12 D requests and all A requests. D only supplied the Cedar project package, costing 258 additional input tokens. D named the documented Qwen decision and export metadata issue but asserted “currently using” where the source only recorded a decision; independent review rejected that operational overstatement despite a literal pass. D also asserted an unsupported editor preference. Most other missing-fact answers remained conservative but failed the requested factual task. Absence, irrelevant-memory, conflict clarification and privacy-gated absence cases received four semantic passes per arm even when they omitted the exact requested literal label. Literal and semantic scores remain separate.

Total D input tokens increased 5.13%. **No token reduction or reliable factual personalization improvement was demonstrated.** A precedes D for each pair, server caching and stochastic sampling were not controlled, and no latency improvement is inferred from the smaller median. These outcomes do not change the main model recommendation or establish autonomous-workflow quality. Genuine LAYA remains NOT TESTED.

Owned runtime PID 33956 closed in `finally`; process polling verified termination, root independently found no live HANNI/llama process afterward, and source manifests were unchanged. Startup took 10,806.96 ms. Raw 24 transcripts, usage, model runtime metadata, semantic reviews, hashes and errors remain local and ignored; sanitized outcomes are in `results/main-model-Qwen-review.json`.

## Native visual acceptance and durable artifacts

The actual Win32/WebView2 Memory Explorer scored **8.7/10 visual**, **1/10 template**, after cycle 4 failed at 8.35/10. All 18 cycle-6 physical frames were independently inspected across three tabs at four physical sizes (1920×1080, 1440×900, 1366×768, 900×650) at 125% scaling. Ten real functional checks included exact cancellation, saved correction/history, actual approval and actual deletion through original registry/CAS.

Final bundle cycle 7 repeated those controls and added actual sensitive-history withholding: 11 checks, 19 frames, zero JavaScript errors/external requests, owned review window closed. The changed withheld-history copy was inspected directly. Final `app.js` SHA-256 is `7eaede8ff987b5e1a8b233aa0e0c7382e9a9586fca9618aee33b39d998dce9d2`, `style.css` is `d021496f25414013738661a07111fc8008a596c803ad56f0202cfb3edea31e1b`, unchanged during review. Narrow windows require vertical scrolling; empty search retains prior selected detail. Scores are one reviewer's subjective assessment, not a user study.

Earlier cycles remain recorded: wrong mini-page selection, asynchronous target discovery not pumped, a tab locator omitting its count, and an exact correction-label locator that included textarea content. These were harness defects; no product score was fabricated from them. Cycle 6 used the real scoped dialog textarea. Density issues identified in cycle 4 were product findings and drove the accepted visual revision. Details are in [native-memory-cycle6.md](native-memory-cycle6.md), with final bundle follow-up recorded here.

The reproducible export is [evals/memory_intelligence_v35](../../evals/memory_intelligence_v35/README.md), with unchanged 240 cases/oracles, seals, source freeze, five minimal original baseline modules and sanitized summaries. Run [scripts/eval_memory_intelligence_v35.py](../../scripts/eval_memory_intelligence_v35.py) for A/B/D deterministic reproduction. Its hash is recorded in `export-manifest.json`; changes from the frozen private evaluator only relocate fixture paths, add the repository src import path and validate original baseline hashes. A/B/D development export checks passed with identical counts and zero errors. The formerly untouched holdout is now public and must not be reused as a fresh future acceptance set.

The additional `main-grounding/` export preserves the 12 original synthetic Qwen cohort cases and seals. [scripts/eval_memory_grounding_v35.py](../../scripts/eval_memory_grounding_v35.py) requires the matching existing local weights explicitly and uses an isolated owned runtime. New executions are reproductions, not replacements for the retained once-only acceptance failure. Raw native frames, model transcripts and private runtime paths are not committed.
