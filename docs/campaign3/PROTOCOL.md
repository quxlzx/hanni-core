# Campaign 3: LAYA and memory validation

Baseline: `b1ec1bb`, branch `codex/hanni-v3.7-distributed`.

No separate common campaign instruction document was located in Campaigns 1
and 2. Their recorded evidence, isolation, independent verification and
checkpoint rules apply alongside the user's Campaign 3 requirements.

The manager coordinates two actual engineering agents and an independent
verification agent. Development uses at least 320 new synthetic scenarios;
the verifier privately authors and seals at least 120 separate scenarios before
production repairs. Private holdout prompts and answers are not inspected by
the engineers or manager. The untouched final evaluation runs after a source
freeze. Any later fixes require a separately labeled development evaluation;
the same holdout cannot become untouched again.

Only synthetic memories in campaign-owned, disposable SQLite databases may be
created, corrected or deleted. No owner memory database is opened by a campaign
script. Owner projects, workflows, secrets, model defaults, application state,
remote consent and background services are not modified. Existing unrelated
files and Campaign 1's private holdout remain untouched.

## Arms and boundaries

A is the actual configured legacy LocalMemoryRetriever without LAYA. D is the
implemented optional deterministic project/context retrieval, reported
separately because it is not LAYA inference. B requires actual LAYA model
assistance through the implemented advisory/ranking contract. A requested flag,
an acknowledgement-only shadow observer, a deterministic ranker, or a controlled
predictor does not qualify as B. Production quality gates remain closed unless
existing independently verified evidence authorizes them. This campaign does
not manufacture that evidence or change owner configuration to enable B.

Boundary tests may attach a controlled predictor/HTTP service to isolated
clients. These prove contracts, timeout recovery, consent and invalidation,
never actual LAYA model quality. Existing local model responses use the original
MemoryAwareSession and TextSession through AdaptiveModelEngine, with original
resource admission and permissions. Inference is serial and local, with no
model launch, replacement or fallback. Evaluation requests use temperature 0,
top-p 1 and a 256-token output cap, separately from production defaults.
Transparent telemetry records payloads, raw replies, reported usage and timing
before parsing. Admission refusal is blocked evidence, not a model answer.

## Measurements

Synthetic retrieval comparisons set K=5 explicitly; the owner's configured
search limit remains eight. Scenario scope and budget inputs are controlled
fixtures, not inferred production choices.

Recall@5 is relevant returned IDs divided by annotated relevant IDs for
eligible nonempty-oracle retrievals; macro and micro denominators are retained.
Precision@5 is relevant returned IDs divided by returned IDs, with empty
retrievals and no-relevant-memory cases reported separately. Neither metric
credits a synthetic canned response. Project identification includes explicit
matches, unknown projects and correct clarification for ambiguous references;
its denominator is the independently annotated project-eligible subset.

Source-grounded factual accuracy and incorrect memory claims require actual
model responses compared with frozen evidence. Deterministic retrieval/status
checks are separate. Exact context tokens require server/tokenizer evidence;
UTF-8 bytes are labeled conservative upper bounds, never measured token counts.
Retrieval latency includes failures and records P50/P95 and sample counts.
Correction, deletion and cache invalidation use current-store readback and
repeated retrieval. Permission tests record attempted changes and actual
mutations, including zero unauthorized mutations. Corruption and unavailable
services must fail clearly or fall back without inventing memory.

Targets are Recall@5 at least 90%, project identification at least 95%, zero
unauthorized changes, correct deletion/invalidation in all controlled tests,
and graceful unavailable-LAYA fallback. Empty or blocked denominators cannot
satisfy a target. Baseline and final results retain every failure and scope
limitation. Repairs address architecture rather than scenario phrases.

Completed implementation and verification cycles record source/corpus hashes,
commands, outcomes and unresolved issues. Relevant existing memory, LAYA,
workflow-context and controller regression tests remain part of final checks.
