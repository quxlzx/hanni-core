# Tool Intelligence V1 final-push development report

Date: 2026-09-24. This is a **development checkpoint**, not a release or freeze. The repository has no `.git` directory, so local hash manifests replace commit IDs. Nothing was pushed or published.

## Development gate

| Measure | Roadmap gate | Observed | Result |
| --- | ---: | ---: | --- |
| Frozen router | >=99% | 99.82% strict, 1,087 cases | Pass |
| Language V2 | preserved | 100%, 200 cases | Pass |
| Language V3 | >=90% | 63.33%, 150 fresh cases | **Fail** |
| Multi-turn router | >=95% | 100%, 50 dialogues/108 turns | Pass |
| Voice routing | >=95% | 100%, 15 cases | Pass |
| Qwen development | >=85% | 88.00%, 132/150 | Pass |
| Qwen diagnostics | >=80% | 75.56%, 34/45 | **Fail** |
| Qwen mixed domain | >=75% | 90%, 9/10 | Pass |
| Safety | 100% | 100%, 10/10 | Pass on this corpus |
| Hallucinated tools | 0% | 0% | Pass on this corpus |

The Phase 34 gate is not credible: Language V3 misses by 26.67 percentage points, and diagnostics misses by 4.44 points. The 50-case historical Holdout V1 regression is only 52% (26/50), with 46.67% diagnostics and 10% mixed domain. It is a development regression, not blind V2 evidence. **Do not create or open a new blind Holdout V2, write a freeze seal, start post-freeze V1.1 capability batches, or call this a release candidate yet.**

## Live model results

The configured Qwen3.5-4B-Q4_K_M ran through the real bounded model/tool loop against synthetic MCP results. The final [150-case report](../evals/llm_tools/results/overnight_qwen_dev150_outcomes_v2.json) is complete and passed `hanni eval artifact-check`: 88.00% task success, 94.33 weighted score, 96.67% tool selection, 98.67% argument accuracy, 92.67% reasoning accuracy, 0% hallucinated tools, 3.33% unsupported claims, 1.54 average tool calls, and 3.245 seconds average case latency. The family scores are diagnostics 75.56%, direct system 90%, Calendar 85%, app/Spotify 93.33%, files 100%, HANNI/model 100%, mixed domain 90%, conversation 100%, safety 100%. The [single-case trace](../evals/llm_tools/results/overnight_trace_diag001.txt) demonstrates observable calls and results without hidden reasoning.

The [historical Holdout V1 report](../evals/llm_tools/results/overnight_historical_holdout_v1.json) is 26/50. Its older fixture and oracle lineage make it a regression signal, not a current blind gate. Both saved reports have completed status and passed `hanni eval artifact-check`.

Earlier K2 Horizon 3.7B results exist: 89/150 (59.33%) development and 23/50 historical holdout in the [matched-protocol bake-off](MODEL_BAKEOFF_QWEN_VS_K2.md). **K2 was not rerun under this checkpoint's changed prompt, evaluator, mock, and corpus hashes.** Do not subtract its earlier percentage from the current Qwen 88% as a controlled model comparison. The production model remains Qwen.

## Routing, coverage, and safety

The [final frozen routing report](../evals/routing/results/overnight_final_frozen.json) is 99.82% strict and 99.63 average score. [V2](../evals/routing/results/overnight_final_language_v2.json) is 100% strict, [V3](../evals/routing/results/overnight_final_language_v3.json) is 63.33% strict with 65.45% required-tool recall and 50% mixed-domain family recall, [multi-turn](../evals/routing/results/overnight_final_multiturn.json) is 100% dialogue/turn success, and [voice](../evals/routing/results/overnight_final_voice_language.json) is 100% strict. V3 is inspectable development data; it is not blind generalization evidence. The 600-case deterministic mutation probe is 61.83% strict, and the 200 mutated follow-up turns have 86.5% dialogue success. No blocked-action mutation exposed a tool.

The [LLM corpus audit](../evals/llm_tools/results/overnight_final_audit.json) found 150 scenarios and zero routing/mock errors. The [capability coverage audit](../evals/llm_tools/results/overnight_final_coverage.json) found 150 registered capabilities, 114 model-facing and 36 intentionally unavailable. Only 17 model-facing capabilities have two or more required-tool LLM scenarios, 24 have one, and 73 have none. Phase 29's separate ~300-case coverage corpus has **not** been built; audit coverage is not scenario coverage. The evaluator uses synthetic outcomes only. Production sensitive-path blocking was strengthened for exact sensitive directories, and app launch acknowledgement now accurately says the request was accepted without claiming the app is verified running.

## Implementation and test state

Changes include pinned production New York timezone and isolated historical fixture timezones; a structured 25-failure review ledger; trace output; runaway-output guard; grounded tool-result fields; completion/duplicate-call ledger; diagnostic and Calendar answer-grading fixes; sensitive-path protection; action verification; fresh Language V3 and mutation probes; capability/context/artifact audits; and a launcher dependency probe that avoids reinstalling on every normal start. These do not replace the frozen router or configured production model. See [action outcomes](ACTION_OUTCOMES_V1.md), [Language V3](LANGUAGE_V3_DEVELOPMENT.md), [failure audit](DEV150_FAILURE_AUDIT.md), and [context budget](CONTEXT_BUDGET_V1.md).

Full pytest: **503 passed, 1 skipped, 17 subtests passed in 36.18s**; [durations](../evals/checkpoints/overnight_pytest_durations_final.txt). The final focused smoke was 45 passed, and the separate mocked Google CLI/OAuth test file was 25 passed. The Qwen live development and historical runs completed without a model-server crash. Google `login`, `status`, and `logout` CLI help each exited successfully. No real Google account was accessed. PowerShell launcher syntax and the installed editable HANNI/speech dependency probe passed. The source export and final checkpoint are recorded in the [handoff](../OVERNIGHT_HANDOFF.md).

## Phase disposition

Phases 1–28 were addressed through implementation, audits, tests, and regressions, with active-target/multi-turn model semantics still needing deeper live history tests. Phase 29 has an audit but lacks the requested separate breadth corpus. Phases 30–32 (Personality V2 and its 40–60-case live A/B) are incomplete; Personality V1 remains the current behavior. Phase 33 has a measured context budget, not a completed prompt optimization proof. Phase 34 failed as above. Phases 35–39 and release-candidate Phase 77 are conditional on that gate and were deliberately not performed. Phase 40's report/export/checkpoint work is represented here and in the handoff.

Phases 41–45 have router property/mutation tests and reports. Phases 46–48 have voice routing and existing boundary coverage but no full microphone/wake/barge-in stress campaign. Phases 49–51 have action semantics and completion tests. Phases 52–53 have partial error handling but no complete ten-class taxonomy/recovery matrix. Phases 54–57 have description/schema/context audits but no proven full result-compression pass. Phase 58 dialogue compaction is incomplete. Phases 59–62 have existing runtime/GPU tests and placement grounding, but no exhaustive server restart/GPU matrix. Phases 63–69 have dashboard/privacy/network/offline audits with some runtime cases still untested. Phases 70–74 have partial startup/shutdown/logging coverage and launcher improvement, not a complete cold-start or repeated process-lifecycle matrix. Phases 75–76 artifact integrity/resume are implemented and tested. Phases 78–80 are documented in `FUTURE_FEATURES.md`, this handoff, and the final integrity sweep. No new V1.1 capability batch was added.

## Exact next development step

Inspect the 11 failed diagnostic cases in the [Qwen report](../evals/llm_tools/results/overnight_qwen_dev150_outcomes_v2.json) alongside the [V3 routing misses](../evals/routing/results/overnight_final_language_v3.json). Fix broad, evidence-based language/diagnostic behavior without memorizing test phrases or redesigning routing; then rerun the full frozen/V2/V3/multi-turn/voice suites, mocked safety tests, and all 150 live Qwen development cases. Only if Phase 34 thresholds pass should a new blind Holdout V2 be constructed and sealed.
