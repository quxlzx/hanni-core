# Campaign 5: adaptive model intelligence

The implementation audit found and repaired reproducible eligibility,
cancellation, context-proof and model-identity failures. The live comparison
is **blocked**, not a demonstrated adaptive-routing improvement. All 1,200
development and 600 independent final attempts were refused before model
generation. No default model,
deployment, owner database or running service was changed.

The independent once-only final run is complete. Its untouched 100-task corpus
was sealed before any production repair. There were zero genuine generated
answers in either cohort, so model quality, inference cost and adaptive benefit
remain unmeasured. The configured resident baseline is preserved. The
[independent review](INDEPENDENT_REVIEW.md) and
[oracle-free final aggregate](FINAL_HOLDOUT.json) document partial acceptance;
no private answer guided tuning.

**Actual inventory.** Original native discovery enumerated four configured
endpoints without hardcoding an expected count. The resident model-list API
advertises one ID, `supervisor`. Process/model-file evidence identifies the
resident weights below. Remote models could not be inspected because their
original SSH connections failed over both configured LAN and Tailscale paths.
Their registered names must not be presented as confirmed loaded identities.

| Endpoint | Configured/observed model | Actual health/admission | Context evidence |
|---|---|---|---|
| Resident 4B | Observed `Qwen3.5-4B-Q4_K_M.gguf`; API alias `supervisor` | Healthy; original 2 GiB RAM reserve refuses inference | Reported/configured 16,384; no fresh near-limit proof |
| Athena P6000 | Registered `Qwen3.8-27B-Q4_K_S.gguf`; loaded identity unknown | SSH unreachable; unknown resources; ineligible | Configured 32,768; no current runtime-bound proof |
| Athena P40 | Registered `Qwen3.8-27B-Q4_K_S.gguf`; loaded identity unknown | SSH unreachable; unknown resources; ineligible | Configured 32,768; no current runtime-bound proof |
| Wonyoung Strata | Registered `qwen3.8-flash-next-iq3_s`; loaded identity unknown | SSH unreachable; unknown resources; ineligible | Configured 8,192; no current runtime-bound proof |

The Athena registrations differ from the intended 27B IQ3_S targets. This
campaign neither relabels them nor replaces their deployment. The resident
GGUF SHA256 is
`25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`.
Initial measured available RAM was 1,833,373,696 bytes, below the original
2,147,483,648-byte reserve. Reported context ceilings and historical
measurements do not substitute for current identity-bound retrieval evidence.

**Prospective benchmark.** The public development corpus contains 200 unique
requests, exactly 20 in each of the ten requested families. Difficulty is
20 easy, 55 normal and 125 hard. A separate verifier authored 100 final tasks,
ten per family, with 10 easy, 60 medium and 30 hard cases. Independent hash
comparison found zero normalized final/development user-message collisions.
Inputs and deterministic oracles are separate; no teacher-generated model
answer is used. The manager and engineers never inspect private final prompts,
oracles or author code.

| Family | Development cases per arm | Independent final cases per arm | Prospective checker scope |
|---|---:|---:|---|
| Simple commands | 20 | 10 | Bounded transformations/calculations |
| Tool selection | 20 | 10 | Development: original registry menu recommendations; final: native tool-turn requirements |
| Planning | 20 | 10 | Dependency/order/finish constraints |
| Coding | 20 | 10 | Development: bounded pure-Python execution; final: canonical AST-equivalent replacement references, no model code execution |
| Analytical reasoning | 20 | 10 | Deterministic numerical/reference checks |
| Long-context retrieval | 20 | 10 | Supplied multi-record evidence; not a near-limit context certification |
| Structured output | 20 | 10 | Typed JSON and external schema/value checks |
| Memory-assisted questions | 20 | 10 | Supplied synthetic memory facts; no production memory-store retrieval |
| Workflow reasoning | 20 | 10 | Synthetic checkpoint/receipt evidence; no real workflow execution |
| Complex multi-step analysis | 20 | 10 | Independently enumerated constraints/outcomes |

Settings are prospectively bounded: temperature 0, top_p 1 and output budgets
256 tokens, up to 512 for selected families. The native engine conservatively
accounts for payload/schema bytes. Development ledgers have 24–62 records and
at most 7,311 serialized UTF-8 bytes; they cannot establish a 16K-token context
limit. No inference or new context/capability proof was fabricated to make a
model eligible.

**Development comparisons and metrics.** Individual modes are pinned with no
fallback. Adaptive and selective collaboration retain native policies. The
six arms use separate isolated native state, authentic health/resource probes,
protected transports and actual wire capture. Offline expected answers never
enter selection, admission or fallback. No reference-backed collaboration was
used in the completed collection.

| Mode | Attempt records | Actual generation requests | Semantic answers | Success, P50/P95 latency, tokens and inference cost |
|---|---:|---:|---:|---|
| Resident 4B alone | 200 | 0 | 0 | Unmeasured |
| P6000 individually | 200 | 0 | 0 | Unmeasured |
| P40 individually | 200 | 0 | 0 | Unmeasured |
| Strata individually | 200 | 0 | 0 | Unmeasured |
| Adaptive routing | 200 | 0 | 0 | Unmeasured |
| Selective collaboration | 200 | 0 | 0 | Unmeasured |

Every record is `BLOCKED_NO_INFERENCE`; no arm was quarantined, skipped by the
request budget or silently replaced with a fixture answer. Each family has
20 blocked requests per arm. The manager independently checked all 1,200
receipt IDs/order, assignment modes, HTTP counts, no-answer/null-grade
semantics, declared scope and source/config freeze. The verifier independently
crosschecked the same totals. The separate six-attempt pilot also had zero
generation HTTP; it is not added to the 200-task comparison denominator.

Task success/structured-output accuracy, P50/P95 inference latency, generated
and prompt tokens, incremental/peak resource cost and collaboration/workflow
overhead are **null/unmeasured**, not zero-percent scores or zero-token model
answers. Available RAM and health diagnostics are outside-inference admission
observations. The harness's wall time outside its observed HTTP envelope is a
bounded orchestration measure, not a claim about complete autonomous-workflow
duration; without HTTP there is no such measured envelope here.

**Architecture repairs and independent verification.** The original relevant
285-test baseline passed. New exposed controls independently reproduced the
following causes before the corresponding repair:

| Cause | Resulting repair |
|---|---|
| Cancellation during admission/result verification could dispatch or publish a result | Recheck original cancellation/closed boundaries, suppress cancelled results and avoid fallback/profile pollution |
| Local result accepted after identity, health or reserve withdrawal | Recheck result authorization and resources; authentically probe expired health; distinguish new-dispatch occupancy |
| Malformed/nonfinite/bool resource samples could remain selectable | Reject invalid observed values while preserving conservative unknown-resource behavior |
| Collaboration dropped declared context/schema reservation | Preserve trusted requirements through assigned native dispatch |
| Context engineering probe bypassed enabled/privacy/resource/context/queue gates | Enforce protected synthetic authorization, real reserves, bounded allocation and own-slot reservation; release on every exit |
| Numeric GPU index zero treated as CPU-only | Require measured VRAM for configured device zero |
| Local SSE/tool responses could explicitly name a different model | Reject present mismatch without replay; retain omitted-field compatibility |
| Wrong-model rejection counted as configured-model incorrectness | Record identity failure with correctness unknown |
| Context proof could outlive cancellation/runtime replacement | Bind transport cancellation and proof publication to unchanged current authority/runtime evidence |

The broad repaired regression suite passed **356/356**. After the final narrow
identity-attribution change, the focused/affected suite passed **235/235**;
these suites share 76 node IDs. The original 285 are a subset of the 356.
Independent implementation review passed **53/53**. Later finalized independent
measurement/runner contracts passed **61/61**, including those implementation
controls. Benchmark checker/capture/budget contracts passed **31/31**. Counts
overlap and are not summed as unique scenarios or real model answers.

Controlled tests cover native eligibility, identity changes, context accounting,
privacy gates, endpoint failure/fallback, bounded budgets, cancellation,
structured verification and disagreement/verification semantics. Owned HTTP
listeners exercise the actual client/transport protocol. Fixture agreement is
never a correctness proof and these tests do not establish live multi-model
quality. Failed first runs, a zero-test collection error and documented
prospective-oracle/fixture corrections are retained. The Anthropic cached-token
fixture only gains truthful gate metadata; its existing assertions remain.

**Final execution contract.** Final inputs have stricter prospective proof
requirements than the development legacy-resident path: no case enables the
unverified legacy exception; 80 require text, ten native tool calling and ten
text plus structured JSON. Sealed mode metadata is retained, while pinned
fallback zero applies only to pinned arms and native adaptive policy remains
native. Requested timeout metadata and original transport timeouts are recorded.
The inputs/oracles were not changed to relax admission. Final 120-second
timeout metadata creates no additional cancellation timer; the original
native client timeouts remain authoritative. Final coding references can miss
unannotated equivalent patches; this limitation does not become a factual
model-failure claim.

The immutable genuine development SQLite checkpoint has settings 1, decisions
200, proofs 0, measurements 0 and identity sources 0. SHA256:
`0e49eb250a3a1be09076632185b8e661263063e07f6203e802b4a3eda70518d5`.
Each final case/mode starts from its own fresh clone, preventing final accuracy
or timing feedback from altering the next placement. No holdout oracle enters
the model, verifier callback or routing profiles. An exclusive once-only claim
prevents silent retries. Model agreement cannot upgrade an unverified answer.

**Independent final outcome.** All six modes retained their full 100-task
denominators, ten in every family. All 600 records are
`BLOCKED_NO_INFERENCE`, with zero actual generation HTTP requests and zero
observable answers eligible for independent semantic grading. There was no
final retry, tuning, policy feedback or model replacement.

For all 500 persisted individual/adaptive decisions, the original engine
explicitly lacked genuine capability/context proof. The resident additionally
lacked its RAM reserve on all 100 individual tasks. Each remote also had
unhealthy endpoint and unknown resources. Native tool-call and structured-format
proofs were absent, and the current remote transport does not support native
tool turns. The 100 selective records stop before a persisted selection
decision; exact per-case exclusion reasons are not inferred from snapshots.

The final collection took 115.406 seconds for guarded admission, isolated state
copies, discovery and source checks. This is not model inference latency or
total autonomous-workflow overhead. Paired accuracy gains, structured success,
latency distributions, inference tokens and peak/incremental resource cost
remain null. Neither adaptive routing nor selective collaboration demonstrates
superiority over any individual model. No unavailable response is counted as a
correct answer, a tie or a model-factual error.

The independent post-run health check found the same resident process and
parent identities as initial discovery, with 2,042,404,864 available RAM bytes,
still below the original reserve. The final raw receipt SHA256 is
`e841249e32a94489fa5d8454161692c4a0b8f2526df8d6d5aa0ac6dc62b72b79`.
[VERIFICATION.json](VERIFICATION.json) binds the independent controls, final
aggregate, private evidence hashes and runtime preservation without publishing
private tasks or reference answers.

**Decision and remaining blocker.** Adaptive routing and collaboration have no
independently measured benefit over the baseline in this campaign. No model
ranking, speed recommendation or main-model replacement is justified. Preserve
the configured resident baseline. Completing the real quality comparison needs
reachable configured workers, adequate actual resident RAM and fresh genuine
capability/context evidence under the original gates. The campaign did not
weaken authentication/reserves or restart owner services to work around this.

The repairs are tested from fresh Python processes. The running controller and
resident service are preserved; their already-loaded modules are not reloaded
by editing source. Owner memories/workflow databases are not opened for this
benchmark. Prior Campaign 4 changes remain intact and uncommitted. This
campaign does not modify unrelated subsystems or create a commit.

The whole final freeze includes 427 production/config/helper/test/public-input
files; manifest SHA256
`10c73380215acfe307906da905daab58570eea5e7e9b7a53ca3938d66ff85e62`,
archive SHA256
`a822b91e45e6e9a62e090eab737fbeb78d7594049df3e2ea780438452c58d466`.
The independent verifier confirmed every member and current byte. Public
corpus/measurement seals, checkpoints, boundary analysis and development scopes
are documented in this directory. Raw provenance is retained under
`data/campaign5-{manager,intelligence,development,verifier}`; private final
materials remain verifier-only.

The manager's final readback separately matched all 18 independent evidence
hashes, checked the public final per-family/null-metric contract, and parsed the
356-, 235-, 61- and 31-test XML reports with zero failures/errors/skips.
[MANAGER_CLOSEOUT.json](MANAGER_CLOSEOUT.json) records this audit. The final
427-file freeze check and `git diff --check` passed; the Git index is unchanged.
