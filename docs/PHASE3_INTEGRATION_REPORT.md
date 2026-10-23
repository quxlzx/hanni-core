# Phase 3 integration candidate — 2026-10-12

**NOT ACCEPTED for autonomous deployment.** Both projects are updated source candidates. No production defaults, protected services, models, listeners or private authorizations were changed. Nothing was pushed or published. The resident default remains Qwen3.5-4B-Q4_K_M.gguf. Phase 2's independently verified completion gate remains failed (2/30 positive goals; two false completion statuses). Background workflow execution remains disabled. This report preserves failures rather than replacing them with later passing results.

## What changed

HANNI's original inference boundary and Control Center lifecycle controller remain separate authorities. A byte-identical, standard-library endpoint contract lives in `src/hanni/models/endpoint_contract.py` and Control Center's `backend/endpoint_contract.py`. It validates stable identities, configuration bindings, symbolic authentication references, advertised versus verified features, configured/reported versus measured context, timestamp freshness, concurrency, resources, cancellation semantics and nullable performance receipts. Healthy endpoints do not acquire capability proofs. No secrets are copied into source. Model names do not determine quality.

Control Center caches existing health snapshots for ten seconds with single-flight locks, configuration binding and lifecycle invalidation. Busy status incorporates current activity. HANNI accepts validated optional contract frames, checks enclosing identity, and still accepts the legacy deployed API. Existing HANNI health admission/cache rules remain in force. **The updated Control Center wire contract has not been deployed or tested against a newly deployed server.** The existing private UI proxy remains intact; this does not prove the screenshot's historical `Not found` condition is resolved in the running application.

An optional SSH stdio relay in the original InferenceTransport connects already-running registered endpoints without creating listeners or competing model managers. Fixed routes, identity, protected source, authorization, payload/response limits and cancellation guards remain enforced. Remote protected-file credentials are read on the remote host. Default transport behavior remains unchanged. The relay currently supports bounded nonstreaming chat and discovery requests; it does not add remote streamed speech, vision or a second tool executor. Unique configured NVIDIA device names can resolve resource evidence when UUIDs are absent; ambiguous matches remain unknown.

Two explicit routing policies were added to the existing confirmed/audited configuration flow: `resident_first` and `measured_work`. Everyday interaction stays resident. The latter permits difficult work only through existing feature, context, privacy, evidence, resource and freshness gates. Original remote accuracy/sample requirements remain. No evaluation receipts were silently installed as capability proofs. Every current remote deployment permits **synthetic data only**. Real conversation, memory, project and workflow context therefore remains blocked from remote offload even if the policy is selected. No stronger model was promoted.

The opt-in personal context provider wraps the existing memory store: bounded relevant records, keyed conflicts, provenance, timestamps, confidence, explicit statements versus inferred preferences, temporary conversation and verified recent observations. Project privacy tags propagate through model request scope; credential filtering and deletion/correction revalidation remain authoritative. Calendar observations can be cached only after actual verified reads, with a short lifetime; no calendar integration is simulated. A uniquely keyed, currently readable owner fact can answer ordinary preference questions directly with the qualifier `Your saved memory says`. It clears pending confirmations and never grants action authority. Inferred memories remain excluded by default. Production context remains disabled; LAYA advisory and retrieval remain disabled.

Live cancellation exposed a Windows SSH pipe-drain timeout that hid cancellation and left a tracked request. Cleanup now bounds drain time and removes tracking in a `finally` block. Only the owned SSH helper is closed; upstream inference abortion is best effort and remains unproven. The initial failed receipt and follow-up are both retained.

## Evaluation and evidence

Frozen cases and scoring are in `evals/phase3`; hashes are in `freeze.json`. There were 20 identical synthetic cases per tested endpoint: eight planning proposals, four simple answers, four memory reasoning cases and four arithmetic analysis cases. These were **real inference calls**, not executed workflows. Strict grading compares exact argument dictionaries, including optional fields: harmless `hash:false` additions fail the frozen contract score. Valid refusals with nonempty proposed steps also fail. Scores are not a pure measure of reasoning and were not repaired after observation. Four/eight samples per role are insufficient for promotion under the existing minimum-evidence gates.

| Endpoint/model | Strict accuracy | Simple P50/P95 ms (n=4) | Planning P50/P95 ms (n=8) |
|---|---:|---:|---:|
| Resident Qwen3.5-4B | 14/20 | 334 / 357 | 631 / 956 |
| Nex N2 Mini / athena-p6000 | 11/20 | 559 / 640 | 1297 / 1539 |
| Mellum 2.1 / athena-p40 | 9/20 | 669 / 714 | 1320 / 1424 |
| Flash Next IQ3_S / wonyoung-strata | 14/20 | 3220 / 3232 | 4373 / 4921 |
| Swift 1.5 | NOT TESTED | unknown | unknown |

Durations are whole request times, including SSH for remote models; remote first-token and server queue latency were not measured. Comparison settings: temperature zero, output cap 384, thinking disabled, nonstreaming, 15-second request timeout. No model or server configuration changes were made. Configured remote contexts are Nex 32768, Mellum 65536, Flash 131072, Swift 32768; measured usable capacities remain unknown. The resident context is 16384, one slot, configured ordinary temperature .35/output cap 768/thinking disabled/GPU layers 99. Local hardware: Windows 11 build 26200, Intel family 6 model 183, 24 logical CPUs, 31.61 GiB RAM, RTX 5060 Laptop 8151 MiB. Per-endpoint resource observations are in the synthetic comparison receipt; they are not enduring availability promises.

Mellum again failed the retained ORCHID731 repeated-neutral retrieval fixture in 7166 ms. Its four memory reasoning cases also failed. Control Center's actual read-only Swift device metrics showed RX9060XT VRAM used 57 MiB and GTT about 12999 MiB, with host available RAM about 9086 MiB. These are device totals, not per-process attribution. HANNI's mixed NVIDIA/AMD telemetry cannot provide the required fresh Swift resource evidence, so Swift inference was safely not attempted. Health alone proves neither residency nor correctness.

The first real resident text/memory/tool cohort scored **3/6**. Two natural memory questions entered a computer-tool route and failed. A correction correctly changed stored memory but failed the frozen response wording check. Grounded file read and deletion passed. A generic owner-fact retrieval fix followed; the original failures remain. A newly frozen six-case cohort using different editor values and natural phrasings then scored **6/6**, with independent save/correction/deletion checks, about 3–13 ms per turn. This supports narrow local keyed-fact recall, not general personal-context accuracy. Unit fixtures cover conflicts, stale observations, relevance exclusion, credentials, temporary context and deletion; these are controlled tests, not live provider evidence.

The 13-turn Phase 1 development responsiveness regression used the actual resident model and read tools:

| Metric | Phase 2 baseline P50/P95 ms | Phase 3 P50/P95 ms |
|---|---:|---:|
| Routing | .87 / 10.02 | .89 / 9.83 |
| Tool time | 7.28 / 1649.70 | 5.11 / 1658.68 |
| Nested verification | .038 / .089 | .020 / .110 |
| First visible useful complete answer | 583.08 / 2331.24 | 555.78 / 2402.31 |
| Total response | 584.46 / 2334.59 | 557.51 / 2403.34 |
| Model first content (n=4) | 247.95 / 474.48 | 230.42 / 528.72 |

These are small unpaired runs with different load, not proof of a statistically meaningful improvement. Required-tool recall was 13/13 in this development run; independent simple-task success was 87.5%, below the 90% target. Ordinary brevity was 100%. Original Phase 1 held-out recall 29/30 and simple success 23/27 remain the acceptance evidence. No token throughput is substituted for useful visible or audible latency. **Server queue latency and physical end-of-owner-speech to first audible answer: NOT TESTED.** Saved voice device initialization was unavailable; no voice identity or devices were changed.

The live pure-inference concurrency test reached an owned Flash relay while resident arithmetic succeeded. Initial cancellation left one tracked handle after a five-second drain failure; follow-up after cleanup returned the explicit cancellation error, zero tracked handles and a 1087 ms join, while resident arithmetic took 314 ms. This is not a full background-workflow scheduler or proof that remote compute aborted. No tools or consequential actions ran in these model tests.

## Regression checks and limits

- Final `check_phase3.ps1`: **101 passed** (9.27 s), including contracts, context, existing routing, compute admission, project privacy and a regression reproducing cancellation pipe-drain timeout.
- Phase 1 regression: **359 passed + 13 subtests**. Phase 2 regression: **331 passed + 13 subtests**. Existing owned-process/security/outcome/store integration: **42 passed**. Suites overlap; do not sum them as unique tests. These ran before the final relay cleanup; the final Phase 3 suite and live cancellation check ran after it.
- Control Center offline health/cache and failure-boundary tests: **7 passed**, two warnings. Fixtures use temporary fake model files to reach intended resource/port boundaries, never start real model processes. FastAPI/Starlette test dependencies were isolated under ignored evidence data, not installed into production.
- Frontend type check and build passed. Bundle warning: approximately 502 kB JavaScript. Running app/frontend were not redeployed.
- Revocation, outages, busy models, source changes and restart recovery have controlled regression coverage; destructive/live protected-service outage and restart drills are **NOT TESTED**. Live calendar authorization/provider behavior, physical barge-in/emergency-stop/audio, cross-model private workflows and simultaneous full interactive/background workflows are **NOT TESTED**.
- Zero new consequential effects were performed by Phase 3 inference tests. Existing safety tests pass, but this is not proof of zero risk in untested integrations. Phase 2's false completion statuses remain a failed truthfulness gate, separately from permission safety.

Source stages are explicit: `model-comparison-source-manifest.json` preserves the source snapshot at comparison time; `final-source-manifest.json` reflects subsequent generic memory fixes, privacy/compatibility guards and cancellation cleanup. Original model comparison cases, scoring, model weights, settings and failed receipts were not tuned or replaced. The supplementary memory cohort was frozen before its inference. Raw text responsiveness observations contain owner process information and are excluded from the export; only aggregate projections are shipped.

## Regrade and prioritized handoff

| Dimension | Evidence-supported assessment |
|---|---|
| Fast concise answers | Candidate preserved; subsecond simple median, 100% brevity in small development run; tail latency not improved |
| Task independence | FAIL: inherited 2/30 verified goals and two false completion reports |
| Personal context | Narrow improvement: fresh 6/6 local keyed-fact cohort; initial 3/6 retained; wider accuracy unproven |
| Safety | Tested permission/privacy boundaries preserved; truthfulness gate still failed |
| Operational reliability | Partial: cancellation cleanup verified; deployment/restart/provider/AMD resource gaps remain |
| User experience | Partial: frontend builds and local recall work; live voice and updated deployment untested |

No defensible overall score increase or unattended-family promotion is claimed. Priorities: (1) verify objective completeness against receipts before completion status; (2) expand independently graded fresh multi-step execution cohorts without tuning held-out failures; (3) fix mixed-GPU telemetry and measure usable context/capability evidence; (4) perform owner-authorized private-context routing evaluation with enough samples and genuine outcomes; (5) deploy the candidate through the existing lifecycle procedure and test private UI compatibility; (6) test physical audio and interruption latency, live calendar and recovery; (7) broaden contextual recall/follow-ups and measure relevance independently. Keep LAYA, unattended goals and private remote offload disabled until their actual gates pass.
