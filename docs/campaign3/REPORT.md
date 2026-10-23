# Campaign 3: LAYA and memory validation

**Memory-quality acceptance was not achieved.** Implementation repairs passed
463 integrated regression tests, but untouched-holdout Recall@5 was **44.68% for
legacy retrieval** and **60.64% for optional deterministic context retrieval**.
Project identification was **66.67%**. These miss the requested 90% and 95%
targets. LAYA is disabled in the observed installation, and original resource
admission blocked all actual-model attempts. No model-answer accuracy or LAYA
improvement is claimed.

The campaign created **320 development scenarios** and **120 independent
holdout scenarios**, covering all twenty requested categories. All memories,
projects, workflow fixtures, corrections and deletions used isolated synthetic
stores. The campaign did not open or overwrite the owner's memory database.
No owner configuration, model file, protected process or unrelated subsystem
was changed. Repairs remain source changes; the already running application
was preserved rather than restarted to load them.

## Effective architecture and comparison arms

[Architecture inspection](ARCHITECTURE.md) found local SQLite memory enabled,
legacy retrieval enabled, and optional project/context retrieval opted out.
LAYA advisory, retrieval and stored-memory consent flags are false. The running
launcher's inspected LAYA environment flags are absent, no configured LAYA-port
listener was observed, and the advisory factory retains its closed independent
quality gate. This is an observed **disabled** state, not shadow-only, advisory
or production LAYA retrieval.

| Arm | Implemented boundary | Evidence available |
|---|---|---|
| A | Legacy LocalMemoryRetriever without LAYA | Actual store/retrieval execution; model generation blocked |
| B | Actual LAYA-assisted retrieval | Unavailable; zero actual LAYA model calls |
| D | Optional deterministic ContextAwareRetriever | Actual store/retrieval execution; not LAYA inference; model generation blocked |

The retrieval comparisons explicitly set K=5. Authored project IDs and context
budgets are controlled fixture inputs; they are not model-inferred project
choices. Project identification is separately scored at the original resolver
boundary. Production still has search limit eight and context retrieval off.
Controlled original advisory HTTP failures and local predictors validate
contracts, consent and fallback; they cannot substitute for arm B.

## Before and after on frozen development data

The baseline is the complete archived source at `b1ec1bb`, including transitive
dependencies. Expected outcomes were annotated before execution. The final
cohort retained all 640 arm receipts and uniform source hashes. No previously
passing development scenario regressed.

| Metric | A before | A after | D before | D after |
|---|---:|---:|---:|---:|
| All scenario assertions passed | 187/320 | 228/320 | 223/320 | 245/320 |
| Relevant-memory micro Recall@5 | 60.89% | 61.39% | 69.80% | 70.30% |
| Relevant-memory macro Recall@5 | 62.69% | 63.21% | 72.02% | 72.54% |
| Returned-set micro precision at 5 | 75.93% | 91.85% | 85.45% | 89.87% |
| Error-free negative abstentions | 102/127 | 117/127 | 106/127 | 114/127 |
| Original project resolver diagnostic | 30/48 | 33/48 | 30/48 | 33/48 |
| Retrieval P50, ms | 1.114 | 1.211 | 1.148 | 1.202 |
| Retrieval P95, ms | 1.364 | 1.457 | 1.381 | 1.524 |

Recall includes all 202 relevant IDs across 193 positive queries. Precision
divides relevant hits by actual returned IDs; empty results do not receive an
invented perfect precision score. Negative abstention and errors are separate.
Three original dependency errors per arm remain recorded; native session
failure-handling is tested separately. Latency covers all 320 primary
retrievals per arm, including failures, and excludes project diagnostics and
fixture setup. These local measurements do not establish inference speed or a
production service-level guarantee.

[Development review](DEVELOPMENT_REVIEW.md) provides the twenty-category
before/after scorecard and failure analysis.
[Final development JSON](../../evals/memory/campaign3_development_results_final.json)
retains denominators, failure assertions, lifecycle outcomes and source hashes.
Precision and safety improved substantially; relevant-memory recall improved
only slightly and remains below target.

## Untouched independent holdout

A separate actual verifier authored and sealed 120 cases before tuning, six per
category. Hash-only checks found no normalized query collisions with the new
development corpus. Engineers and the manager did not inspect private prompts
or answers. After source freeze, the verifier executed the final set exactly
once, with an exclusive run claim and hash checks before each case. All 240
arm executions completed without fixture-level execution errors; source bytes
stayed unchanged. No tuning or retries used the final results.

| Metric | A final | D final |
|---|---:|---:|
| Relevant-memory Recall@5 | 42/94 = 44.68% | 57/94 = 60.64% |
| Returned-set precision at 5 | 42/52 = 80.77% | 57/68 = 83.82% |
| Original project resolver diagnostic | 12/18 = 66.67% | 12/18 = 66.67% |
| Supported deterministic checks satisfied | 58/120 | 71/120 |
| Unauthorized retrieval mutations observed | 0 | 0 |
| Retrieval P50, ms, 120 primary samples | 1.263 | 1.264 |
| Retrieval P95, ms, 120 primary samples | 1.503 | 1.517 |

Satisfied deterministic checks are **partial**, not complete scenario success:
actual response grounding, causal conclusions, live actions and model resistance
remain unmeasured. Zero retrieval mutations does not prove all permission
boundaries; independent session and registry probes supply the separate safety
evidence. The lower final recall exposes limited generalization beyond the
development set. [Independent review](INDEPENDENT_REVIEW.md) supplies its
category-level grades, lifecycle checks, latency and retained failure evidence.

Per arm, the holdout verified eleven successful correction readbacks and two
planned correction rejections, seven successful deletions, two history purges
and one suggestion purge. Four correction targets and four deletion targets
were actually returned before mutation. Its explicit cache-authority case
returned no record, so that field comparison was **unexercised**. Separate
exposed-development cache probes passed, but this holdout gap is retained.
The three literal whole-record checks per arm also received empty contexts,
leaving their populated-record serialization dimension unexercised. Separate
development tests cover populated whole-record serialization; empty holdout
results do not extend that evidence.
Attribution, status and content failures in the holdout came from missing
recalled records rather than wrong fields on records that were returned.
One sealed oracle had conflicting exclusion and required-returned-status
annotations. Its literal supported-check failure remains in both arms' original
counts, labeled as an authored-oracle limitation; recall and project metrics
are unaffected. No oracle was edited or regraded after execution.

## Actual local-model evidence and blockers

The existing local Qwen3.5-4B-Q4_K_M model endpoint was healthy. Its model SHA-256,
process identity and launcher identity matched the baseline. The final probe
selected twenty prospectively annotated public development cases across seven
categories before inference, then attempted A and D using original
MemoryAwareSession, TextSession and AdaptiveModelEngine. Evaluation settings
were temperature 0, top-p 1 and at most 256 output tokens. Original permission
and resource admission were preserved; model fallback was excluded in the
isolated diagnostic configuration.

All **40 final attempts were blocked**, with **zero generation HTTP requests**,
zero generated answers, and unchanged isolated memory stores. The separate
post-refusal inspection of the original selector reported
`insufficient_ram_reserve` in all forty cases. Available RAM at these attempts
was 1,815,719,936 to 1,951,064,064 bytes, below the existing 2 GiB reserve. The
two earlier diagnostic pairs were also blocked, for 44 total guarded attempts
and zero actual generation calls across campaign diagnostics.

Native request P50/P95 was 13.86/15.41 ms across forty final attempts. This is
**admission-attempt latency**, excluding separate post-refusal inspection; it
is not model response latency. Source-grounded factual accuracy, incorrect
memory claims, generated tokens and A/B answer-quality differences are
**unmeasured**. Arm B also lacks an active authorized LAYA model and quality
gate. The campaign therefore could not complete the requested actual-model
A/B comparison and cannot conclude that LAYA improves performance.

## Context tokens

The installed model server's native `/tokenize` API measured every archived
baseline and final development context, including declared warm queries:
708 contexts per cohort, 354 per arm, with zero unavailable measurements.
These are real tokenizer counts of retrieval text, not model generation usage.

| Native context-token measure | A before | A after | D before | D after |
|---|---:|---:|---:|---:|
| Mean, all measured contexts | 119.24 | 143.19 | 128.10 | 127.39 |
| Maximum | 465 | 567 | 472 | 483 |
| Empty contexts | 176/354 | 191/354 | 163/354 | 170/354 |

Empty contexts include abstentions, misses and explicit error contexts; smaller
token counts are not automatically better. A's added data-policy/provenance
envelope increases serialization overhead. Runtime context budgets still use
a disclosed conservative UTF-8 byte bound and preserve whole records. Separate
native template/tokenizer receipts measure the actual injected memory blocks
in final model attempts, even though generation was refused.
[Manager evidence](MANAGER_EVIDENCE.json) preserves token summaries, receipt
digests, model identity, blocked-attempt timings and regression counts.

The verifier also tokenized all 264 retained holdout contexts, including twelve
warm queries per arm, without re-executing retrieval. A averaged 145.86 tokens,
maximum 590, with 76 empty contexts; D averaged 146.64, maximum 506, with 60
empty contexts. All measurements succeeded, with zero generation requests.
The private payloads and responses stay private; aggregate receipts appear in
the [final holdout evidence](FINAL_HOLDOUT.json).

## Architectural repairs and remaining failures

| Layer | Observed defect | Verified repair or remaining limitation |
|---|---|---|
| Memory mutation authority | Session writes bypassed supplied denied owner profiles; fresh automatic captures bypassed low nonnegative tiers | Recheck original owner access and emergency stops; automatic extraction respects tier 2. Explicit owner commands retain their existing contract. Independent blocked-mutation controls pass. |
| Privacy and record validity | Imported unsafe content/provenance leaked through direct replies and project packages; invalid confidence could enter JSON | Revalidate entire records, quarantine unsafe imports without deleting them, reject nonfinite/out-of-range confidence and fail clearly on malformed reads. |
| Cache and correction | Timestamp-only fingerprints missed imported content/status/source changes | Fingerprint complete row state; revalidate complete current records and privacy revisions in cached retrieval and project context. |
| Project scope | Same keyed facts could update or conflict across projects; identical text could be reassigned implicitly | Scope keyed conflicts/corrections/review by project. Reject cross-project identical-text collisions under the existing global unique index; no database migration. |
| Project resolution | Short names inside longer names created false ambiguity; generic continuation could miss required clarification | Resolve explicit span containment and preserve ambiguity for separate/shared names. Broader ambiguous references remain unreliable. |
| Epistemic handling | Cancelled or negated completion could be classified as successful | Generic negation/cancellation classification; plans and historical verification metadata grant no current-state proof. Model interpretation remains unmeasured. |
| LAYA transport/lifecycle | Authenticated redirects forwarded headers; closing a full queue sent pending text and lost shutdown signaling | Refuse redirects, stop admissions atomically and discard queued text; independently verified with actual owned HTTP listeners. An admitted in-flight request may finish. |
| Context budget | Legacy factory and optional failure/Safe Mode fallback ignored small configured budgets | Propagate the original budget throughout fallback. Whole-record serialization overhead still causes substantial small-budget recall failures. |
| Retrieval quality | Indirect and provenance-focused queries miss relevant memories; unresolved references can expose unrelated candidates | Unmet quality target. No semantic retrieval improvement, trained LAYA benefit or phrase-specific tuning is claimed. |
| Response synthesis | No actual model answers available | Blocked, not passed. Factual grounding and injected-instruction resistance require actual response evidence. |

The final development cohort has zero failures across 280 lifecycle-operation
assertions per arm: corrections/rejections, deletion, restarts, same-timestamp
updates and index operations. It retains 22 correction operations, 23 deletion
attempts, 26 restarts and nine actual index drops per arm. Final SQLite schema
readback and prepared-cache identity traces are preserved. Whole lifecycle
scenarios still fail when remaining relevant recall or attribution fails.

Independent exposed-development checks reproduced twelve prohibited synthetic
mutations across denied profiles and two additional low-tier automatic writes
before repairs; the repaired controls deny them. Confidence, secret-registration,
project provenance, late deletion and stale package checks also pass.
[Boundary review](BOUNDARY_REVIEW.md) and [boundary evidence](BOUNDARY_EVIDENCE.json)
retain failures, fixture corrections and exact source/test hashes. Mocked
predictors, workflow readers and controlled replies remain explicitly labeled.

## Acceptance disposition

| Requested target | Result |
|---|---|
| Relevant-memory Recall@5 at least 90% | **Not met** on development or untouched holdout |
| Project identification at least 95% | **Not met**: holdout resolver diagnostic 12/18; native model project identification unmeasured |
| Zero unauthorized memory changes | **Passed in controlled repaired session/registry probes**; zero holdout retrieval mutations; no universal production-security claim |
| Correct deletion and cache invalidation in controlled tests | **Passed for exercised implementation controls; partial holdout coverage**. The explicit holdout cache-authority comparison was unexercised; retrieval misses and attribution failures remain separate. |
| Graceful fallback when LAYA is unavailable | **Passed in controlled development client/session tests; partial holdout coverage**. Four of six final D fault boundaries were exercised; two lacked a candidate and did not call the advisory dependency. No live trained LAYA quality pass. |
| Actual local-model A/B and grounded responses | **Blocked** by existing RAM admission and unavailable authorized LAYA arm B |

The final source archive contains 223 source/config/harness files. Its SHA-256
is `6d6f5e6861852222e831a936824355ed1bd301e0ca2127a169972fa90f44def9`.
[Checkpoints](CHECKPOINTS.md) and [protocol](PROTOCOL.md) record the seal,
repair cycles, harness errors, source freeze and verification rules. Private
holdout prompts/oracles and raw diagnostic receipts stay under ignored `data/`.
No source tuning followed final holdout scoring.
