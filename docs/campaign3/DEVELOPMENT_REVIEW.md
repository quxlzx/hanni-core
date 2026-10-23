# Campaign 3 development review

This report covers 320 prospectively annotated synthetic scenarios across all twenty requested categories. Every scenario runs against a fresh original SQLite store in each arm. The corpus is frozen at SHA `4d0b33856ea6f406b673458c9c72b1185cd4a1794d391abddfb00e77746fcece`; its 193 positive queries contain 202 relevant logical memory IDs, and its 127 negative queries retain explicit excluded IDs. Expected records, provenance and action assertions were authored before outputs. No independent holdout inputs or answers were opened.

The baseline uses the full archived `b1ec1bb` source tree, including transitive privacy, project, advisory and workspace dependencies. The candidate is the final source-uniform development cohort. Independent holdout and actual-model acceptance remain separate. Original and candidate receipts and source hashes remain in `data/campaign3-development`; public aggregates can be reproduced with `scripts/campaign3/development_metrics.py`.

| Metric | Legacy baseline | Legacy candidate | Context baseline | Context candidate |
|---|---:|---:|---:|---:|
| Case assertions passed | 187/320 | 228/320 | 223/320 | 245/320 |
| Relevant-memory micro Recall@5 | 60.89% | 61.39% | 69.80% | 70.30% |
| Positive-query macro Recall@5 | 62.69% | 63.21% | 72.02% | 72.54% |
| Returned-set micro precision at 5 | 75.93% | 91.85% | 85.45% | 89.87% |
| Error-free negative abstentions | 102/127 | 117/127 | 106/127 | 114/127 |
| Dependency errors | 3 | 3 | 3 | 3 |

Recall denominators include all positive-query relevant IDs, including misses. Returned-set precision divides relevant hits by returned IDs; a separate fixed-five-slot precision is retained in the JSON with 320 x 5 slots. Empty contexts are not given invented precision. Three original corrupt-database/malformed-date dependency errors per arm are retained and never counted as correct negative abstention. Action failures are checked separately from retrieval; the initial pytest collection error was retained before correcting the test signature.

The separate original workspace project resolver diagnostic improves from 30/48 to 33/48. Explicit project IDs supplied to a retriever are fixture scope, not automatic project identification. Legacy has no advisory ranking path: its optional-fault case results establish deterministic continuity only. Context exercised the original advisory HTTP leaf in thirteen cases, with sixteen bounded failed calls; these are controlled faults, not real LAYA model inference or quality acceptance.

Retrieval-only latency includes errors and excludes project diagnostic/package time. The 320-sample p95 changes from 1.364 to 1.457 ms in legacy and from 1.381 to 1.524 ms in context. UTF-8 bytes are a conservative token upper bound, not exact tokenizer usage. Actual-model factual claims and incorrect-memory-claim rates are not measured by this deterministic harness; the manager owns actual-model A/B evidence.

The source repairs also reject cross-project normalized-content collisions before keyed replacement and keep owner-reviewed add conflicts project-scoped. They revalidate full imported records and changed metadata; apply exclusion, privacy and epistemic eligibility before final legacy ranking; detect corrections when timestamps are unchanged; scope keyed updates, corrections and relationship proposals by project; preserve globally unique identical text by explicitly rejecting implicit cross-project reassignment; and classify negated/cancelled completion without turning it into success. Historical workflow verification metadata never establishes current file or system state. No owner data, settings, runtime or model was changed.

Fifty-four new development boundary regressions and thirty-three existing memory/LAYA tests pass in `data/campaign3-development/focused-final.xml` (87 total). Independent control reproduction is retained by the verifier. The final candidate has no previously passing scenario regressions in either arm. The retrieval target is unmet: long indirect/provenance queries, unresolved personal references and whole-record small budgets retain failures. A general auto-approval imperative text-gate observation was reported to the boundary worker; the specific frozen queries abstain and do not demonstrate a permission grant. Original runtime authority remains separate from any stored wording.

Checkpoint scenarios preserve synthetic memory tags and separately inspect the original project package using a controlled workflow-reader dependency. Their sixteen passing retrieval cases do not establish execution of live workflows or automatic resume. Imported unsafe content is fixture SQL data, never an authorized production write.

| Category | Legacy before/after | Context before/after |
|---|---:|---:|
| explicit user preferences | 12/16 -> 12/16 | 15/16 -> 15/16 |
| temporary preferences | 14/16 -> 16/16 | 16/16 -> 16/16 |
| important project decisions | 13/16 -> 13/16 | 15/16 -> 15/16 |
| tentative plans versus confirmed actions | 7/16 -> 14/16 | 10/16 -> 14/16 |
| project identification | 9/16 -> 9/16 | 9/16 -> 9/16 |
| multiple similarly named projects | 1/16 -> 12/16 | 10/16 -> 12/16 |
| contradictory information | 10/16 -> 12/16 | 13/16 -> 14/16 |
| outdated information | 10/16 -> 14/16 | 11/16 -> 14/16 |
| corrections | 11/16 -> 12/16 | 12/16 -> 13/16 |
| memory deletion | 16/16 -> 16/16 | 16/16 -> 16/16 |
| cross-session continuity | 11/16 -> 11/16 | 13/16 -> 13/16 |
| source attribution | 2/16 -> 2/16 | 2/16 -> 2/16 |
| unrelated memory exclusion | 14/16 -> 14/16 | 14/16 -> 14/16 |
| ambiguous personal references | 0/16 -> 1/16 | 0/16 -> 1/16 |
| privacy and sensitivity handling | 11/16 -> 14/16 | 13/16 -> 14/16 |
| LAYA timeout and disconnection | 14/16 -> 15/16 | 16/16 -> 16/16 |
| corrupted or missing index data | 5/16 -> 8/16 | 11/16 -> 14/16 |
| memory retrieval with small context budgets | 2/16 -> 3/16 | 3/16 -> 3/16 |
| workflow checkpoint retrieval | 16/16 -> 16/16 | 16/16 -> 16/16 |
| resistance to malicious instructions embedded in stored content | 9/16 -> 14/16 | 8/16 -> 14/16 |

The detailed JSON retains every still-failing case ID, repaired case ID, failed assertion, source hash and denominator. The frozen development corpus and baseline outcomes remain unchanged.

Final artifacts are `evals/memory/campaign3_development_results_final.json`, `data/campaign3-development/final-source-readiness.json`, and `data/campaign3-development/final-lifecycle-cache-audit.json`. All 640 receipts have uniform loaded dependency hashes, and all sixteen snapshotted production/harness/test files remained unchanged during the run. The corpus byte digest is unchanged. The baseline and interim candidate receipts remain preserved.

There are 78 lifecycle scenarios in each arm: 56/78 legacy and 65/78 context pass the whole scenario, including final recall and provenance. Final operation assertions have zero failures; these do not override remaining retrieval misses. Each arm retains 22 correction operations (including expected rejections), 23 deletion attempts, 26 restarts, nine external metadata/content updates, three tamper fixtures, nine actual index drops and two deliberate invalid SQLite files. The latter remain explicit errors, with no automatic data repair claim. Index schema state and original prepared-cache IDs are recorded only in the final instrumentation addendum; original baseline diagnostic fields were not invented retroactively.
