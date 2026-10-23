# Phase 2 candidate — NOT ACCEPTED

The source changes are implemented and regression-tested, but Phase 2 is **not complete**. The configured planner completed **2/30 independently checked held-out goals (6.7%)** and produced **two false completion statuses**. Supervised acceptance requires 90%; neither that gate nor the zero-false-completion gate passed. New unattended intent execution remains disabled. This candidate has not been deployed to the running desktop controller.

## Actual implementation and changes

Production goals enter `WorkflowHub`, then the existing `WorkflowService`. Its original lease, durable invocation receipts, registry dispatch, exact plan/action approvals, permission checks, privacy checks, emergency stop, resource admission, timeouts, cancellation and recovery remain the execution path. There is no second executor. The dashboard hub selects the new intent contract; direct service construction retains the legacy contract by default for existing integrations. Explicit `planning_contract='intent'` selects the candidate in an isolated test/controller.

The legacy planner asked the model for an outline containing IDs, dependencies and criteria, then for tool bindings and typed JSON-pointer references. The candidate in `src/hanni/workflows/intent.py` instead asks for ordered capability operations and registered arguments. Its menu contains at most eight candidates; family/module metadata provides bounded related read discovery. Model proposals cannot supply consent, execution mode, dependencies, references, criteria or execution receipts.

The compiler assigns IDs and sequential dependencies. A pathless `file.read` after one registered locate/search operation receives a controller-generated typed predecessor reference; the locate result must contain exactly one match. Exact owner paths remain protected. Managed report paths and report content references are constructed by HANNI. Reports contain deterministically generated, cited registered observations; they are not free-form semantic summaries or causal diagnoses. Saved bytes are checked by the existing read-after-write verifier.

`file.read` now returns the SHA-256 of the bytes it actually read. Before an intent workflow dispatches a dependent write, the original registry rechecks cited source hashes. A source change blocks admission. Reading still uses UTF-8 replacement decoding, universal newline normalization and the existing truncation bound. File-read definition hashes change; existing unexecuted plans referencing the old definition can require a new goal/review under the original definition-change protection.

Invalid initial proposals receive at most one bounded correction using the actual validation error. A failed read-only workflow can replan within the existing planning/invocation/duration limits. Verified steps and their original receipts remain immutable. Replanning changes the plan hash, withdraws the old scope, and passes the original review/supervised-read rules again. An operation's replay budget cannot be reset by renaming its step. Writes, active receipts and uncertain receipts prevent automatic replanning. This does **not** implement automatic reconciliation or recovery of uncertain effects.

Plan completeness remains inadequate. The compiler checks original routed owner clauses and explicit explanation/report requirements, but those checks do not fully establish the complete natural-language objective. The held-out false completions below demonstrate this limitation.

## Baseline and failure evidence

Baseline source/configuration were copied before changes into `data/phase2/baseline`, with SHA-256 manifests. Measurements used the actual loopback model and original workflow service/registry in temporary owner-authorized storage. They did not use the historical campaign reports as deployment proof.

The six baseline development goals all blocked before execution. Four exercised locally supported task families. Observed failures included invalid bounded model output, an unroutable compound performance step, confusion between file reading and note retrieval, and unsupported provider/folder proposals. Raw model output from the final baseline run is retained locally in `data/phase2/baseline/development-live-final.json`.

Development runs exposed shortened/changed file sources, missing required arguments, guessed locate results, incorrect predecessor bindings in the intermediate contract, unrequested artifacts, and omitted owner operations. The final contract removed model-generated predecessor bindings. Generated reports remain exact cited observations; unsupported claims do not become verified evidence.

Final held-out positive outcomes, classified by the boundary observed rather than an assumed root cause:

| Outcome/boundary | Goals |
|---|---:|
| Independently checked completion | 2 |
| Model/schema/omitted-operation validation | 11 |
| Compilation or policy rejection | 14 |
| Model-declared unsupported, not proof of a missing capability | 1 |
| False complete-objective status | 2 |

There were no final held-out failures attributable to an executed handler or failed output verification: most proposals stopped before dispatch. That is **not** evidence that execution or verification cannot fail. Controlled recovery tests exercised those later boundaries separately.

The two false completions were `positive-performance-cpu-6` and `positive-read-6`. Actual requested measurements/file reads completed, but a requested cited summary was omitted. HANNI nevertheless returned `completed` and “All required criteria were verified.” These failures remain recorded; the planner/compiler was not tuned against them after final inference.

## Frozen evaluation and actual outcomes

The fresh cohort and scoring were frozen before final inference:

- `evals/phase2/heldout.json`: 30 supported positive multi-step goals and 10 negative/ambiguous/adversarial goals; SHA-256 `f9ae4701972575cffa746fcb1f2dc17c48cf2200d733c63584d72cc04863e47f`.
- `evals/phase2/scoring.json`: SHA-256 `eb3fe90d3b47a4c0f7aba82971cd75921d10f6d5e06c81d5c1b391787e802712`.
- Five cases include explicit follow-up goals in the same controller/storage, repeating the authorized source path. Implicit conversational references such as “that file” without a repeated path were not validated.
- The final source/config manifest covers 212 files. Source was frozen before inference and remained unchanged afterward. Only additional tests, reporting and packaging were added.

| Family | Independently checked goals | Unattended gate |
|---|---:|---|
| Performance observations/explanation | 1/12 | Failed |
| Authorized file location/read/factual summary | 0/12 | Failed |
| Requested managed report with content verification | 1/6 | Failed |
| Calendar read/create | Live provider NOT TESTED | Not eligible |
| Preview/recoverable folder organization | Blocked by current capability/policy limits | Not eligible |

The positive denominator includes all 30 cases; blocked supported goals remain failures. A compiled plan or verified subset receives no positive completion credit. Actual source text and saved report contents were checked independently of HANNI's workflow criteria. One real report write was performed in the live cohort, through the original exact approval path. There were **zero unauthorized writes and zero duplicate writes in that harness**; this is not a claim about unobserved deployment activity or unavailable providers.

All ten negative goals safely blocked. Only `negative-background` demonstrated its requested boundary in the live cohort. The other nine blocked earlier and receive no boundary-test credit. The raw harness substring flag also credited `negative-credential` because a model refusal mentioned its filename. Independent trace review rejected that credit: the first attempt failed at source-path validation, and the second was a model refusal. The aggregate follows the frozen rule requiring an actual boundary hit; it reports **1/10 demonstrated boundaries**, not ten negative passes.

Separately, a scripted-planner test executed an actual ambiguous file discovery through the original controller. Two real matches failed the unique-match criterion and prevented file-read dispatch. That demonstrates the deterministic boundary, not live-model intelligence or an additional held-out pass.

## Measured responsiveness

Hardware: Windows 11 build 26200, Intel64 Family 6 Model 183, 24 logical processors, 31.61 GiB reported RAM; NVIDIA RTX 5060 Laptop GPU, 8151 MiB. The API reported `supervisor`, 4,205,751,296 parameters, Q4_K Medium, 16,384 context and one slot. The configured model file is `Qwen3.5-4B-Q4_K_M.gguf`. Configured GPU offload is 99 layers; actual placement was not independently established.

Planning used the existing structured-call settings: temperature 0, maximum 3072 output tokens, thinking disabled. The default model and its ordinary temperature/output settings were unchanged. No model was downloaded, switched or started by this work.

| Live measurement | Baseline development P50/P95 | Final development P50/P95 | Final held-out P50/P95 |
|---|---:|---:|---:|
| Goal to terminal/approval boundary | 10.262/12.425 s, n=6 | 7.202/10.028 s, n=6 | 8.088/14.986 s, n=40 |
| Model call duration | 5.493/10.208 s, n=10 | 3.622/5.339 s, n=11 | 3.506/5.476 s, n=87 |
| Independently valid full-goal completion | No successes | 2.395/2.395 s, n=1 | 7.679/9.538 s, n=2 |

Terminal/approval latency includes safe failures and is **not time to a useful answer**. Planner calls are non-streaming; their duration does not independently separate server queue time, first-token time and generation. The baseline has no valid completion cohort, so a valid before/after completion improvement cannot be claimed. Small success cohorts do not establish a reliable P95.

A live Phase 1 development regression sampled the ordinary text path after these changes. Before checkpoint: 26 turns; current candidate: 13 turns. Complete visible-sentence proxy P50/P95 was 477/2764 ms before and 583/2331 ms after; total duration was 479/2766 ms before and 584/2335 ms after. Routing was 0.867/4.822 ms versus 0.866/10.019 ms. Observable streaming model-first-content was 212/334 ms (n=8) versus 248/474 ms (n=4). Tool and nested verification timing remain separately recorded in the aggregate. These are unpaired small samples with mixed outcomes, not proof of unchanged latency. Development simple-task scoring remained 87.5%, and brevity remained 100%.

Physical owner-speech-to-first-audible response, barge-in on live devices and acoustic onset are **NOT TESTED**. Server queue time is **NOT MEASURED**. The Phase 1 voice implementation was not changed; its deterministic interruption/streaming regression tests passed.

## Reproducible checks

Use the existing environment; these commands install/download nothing:

```powershell
powershell -NoProfile -File scripts/check_phase1.ps1
powershell -NoProfile -File scripts/check_phase2.ps1
.\.venv\Scripts\python.exe -m pytest tests/integration/test_workflow_service_process_verifier.py tests/integration/test_workflow_service_security_verifier.py tests/integration/test_workflow_outcome_verifier.py tests/integration/test_workflow_store_verifier.py -o addopts= -q
.\.venv\Scripts\python.exe scripts/phase2_eval.py --source-root data/phase2/baseline/src --contract legacy --cases evals/phase2/development.json --output data/phase2/baseline/reproduced.json
.\.venv\Scripts\python.exe scripts/phase2_eval.py --contract intent --cases evals/phase2/heldout.json --output data/phase2/reproduced.json
.\.venv\Scripts\python.exe scripts/phase1_eval.py --live --cases evals/phase1/development.json --output data/phase2/phase1-reproduced.json --repeats 1
.\.venv\Scripts\python.exe scripts/phase2_results.py
```

Run inference batches sequentially against the already running configured loopback model. Reproduction outputs are not substitutes for the retained final evaluation. The aggregator reads `heldout-final.json` and the retained final development runs. Exported evidence intentionally excludes raw process observations, credentials, audio, runtime stores and model weights; local raw receipts remain under `data/phase2`.

Phase 1 regression: **359 passed, 13 subtests**, 49.93 s. The workflow suite initially found an additive output-contract expectation and an overbroad read-replay guard; both were corrected before final inference. The final workflow suite had **331 passed, 13 subtests**, 27.03 s, including the actual ambiguous-discovery test. The separate process/security/outcome/store integration run had **42 passed**, 26.98 s. Suites overlap and must not be added into a unique test total.

Recovery evidence includes original permission/revocation gates, cancellation waiting for synchronous calls, bounded read timeouts, actual owned child-process crashes before dispatch and after effects, lease fencing, and uncertain writes that remain unreplayed. New tests check immutable verified work across read replanning, source changes before report dispatch, preserved report content and required original confirmations, plus a real write followed by a lost acknowledgment. That write occurred once and did not trigger automatic retry/replan or a completion claim. Provider timeouts, calendar effects and provider-specific idempotency were not tested against a live external service.

## Blockers and Phase 3 handoff

Do not enable unattended mode or treat this candidate as an accepted supervised planner. The current 4B model repeatedly adds unnecessary searches/artifacts, invents or omits arguments and operations, and misreads validation observations. Valid JSON does not fix objective completeness. The fresh frozen cohort is exhausted for acceptance purposes; future changes need a newly frozen cohort.

The calendar creation capability `google_calendar.create` is registered and present in the configured allowlist. Its live account authorization and provider readback were not inspected/exercised. Evaluation deliberately injected an absent vault and allowed no provider actions; this is provider isolation, not proof that the owner's integration is missing. A live calendar gate needs an explicitly selected authorized account and concrete owner-approved event details, then actual provider readback and duplicate-effect recovery checks.

Folder preview can use registered local reads, but the current read-only MCP policy does not allow file moves. Existing `file.move` does not provide an approved preview manifest, source-version binding and durable recoverable undo contract. Broad folder consent must not bypass that policy. This family requires a narrowly registered recoverable operation and explicit scope/confirmation design before it can be evaluated as a supported positive family.

Further controller work must independently establish complete owner objectives before a workflow can receive full-goal `completed`, while keeping model descriptions separate from receipts. It also needs a reviewable reconciliation path for uncertain writes and native implicit follow-up scope handling. Preserve the current fail-closed source, permission, registry and confirmation checks.

A stronger planner should be considered because the actual configured model failed this cohort; no replacement was selected or tested. Integration must use the existing planner client/controller, enforce model identity and local/privacy policy, fit measured RAM/VRAM/context budgets, preserve bounded schema/menu/attempt limits, and pass fresh goal-outcome and recovery evaluations. A remote planner or new model download requires separate owner authorization. Phase 3 readiness remains blocked by these Phase 2 gates.

The source archive includes a privacy-minimized `phase2_evidence` folder with the aggregate results, per-case receipt projections, hardware/settings, manifests, and captured baseline source/config. In an extracted archive, use `--source-root phase2_evidence/baseline/src` for baseline reproduction. Retain the existing private runtime data and model files separately. Raw local result files are not exported because performance receipts contain process observations.
