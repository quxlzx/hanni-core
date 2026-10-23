# HANNI LLM Tool Eval V1

HANNI LLM Tool Eval measures whether the configured resident model can use a routed MCP menu, interpret tool evidence, chain calls, stop, and give a grounded answer. The deterministic routing evaluation answers the earlier question of whether Python retrieved the right capabilities; this evaluation continues through real model inference and the final response.

**Current checkpoint (September 24, 2026):** With the production Personality V2
prompt, Qwen3.5-4B passed [139/150 development tasks (92.67%)](../evals/llm_tools/results/final_generalization_qwen_production_v2.json):
diagnostics 37/45 (82.22%), mixed-domain 9/10 (90%), Calendar 19/20 (95%),
applications/Spotify 14/15 (93.33%), safety 10/10, and no hallucinated tools.
Frozen routing passed 99.91%; the tuned Language V3 development set passed
100%, with 96.33% on deterministic mutations. These are development scores.
The once-run, locked [72-case Holdout V2](../evals/llm_tools/results/qwen_holdout_v2_locked_once.json)
passed **45/72 (62.50%)**, with 24 routing failures. Tool Intelligence V1 is
**not frozen**; see the [blocker decision](TOOL_INTELLIGENCE_V1_BLOCKERS.md).
The historical Holdout V1 regression passed
[26/50 (52.00%)](../evals/llm_tools/results/overnight_historical_holdout_v1.json)
under an older protocol. K2 was not run under this final protocol, so these
Qwen results are not a new controlled model bake-off.

The earlier completed matched-protocol bake-off on the then-current router
found Qwen3.5-4B at 123/150 development and 25/50 locked holdout tasks; K2
Horizon 3.7B at 89/150 and 23/50. Both ran on the same RX 6600 XT. The
[model comparison](MODEL_BAKEOFF_QWEN_VS_K2.md),
[shared-failure analysis](PHASE8_SHARED_FAILURES.md),
[mixed-domain investigation](PHASE9_MIXED_DOMAIN_INVESTIGATION.md), and
[diagnostic matrix](PHASE10_DIAGNOSTICS_INVESTIGATION.md) are the current
reports. Older baseline figures later in this document are historical runs
from before the language-routing checkpoint. Tool Intelligence V1 is not
frozen, and production remains Qwen.

## Safety model

The evaluator never calls a capability handler. It creates an isolated MCP host that retains capability schemas and deterministic routing, then returns only scenario-owned synthetic results. Process control, application launch, Spotify, Google, filesystem, shell, network, and settings code cannot execute through this loop. Fixtures contain no tokens, client secrets, or user data.

When routing classifies a destructive request as blocked, the session returns HANNI's fixed refusal directly. The model is not asked for a fallback that could include destructive instructions. The report marks these cases as `execution_layer: blocked policy` and counts them separately; a 100% safety-family score therefore measures the combined router/policy loop, not Qwen's independent refusal ability.

The built-in V1 catalog contains 150 cases: 45 diagnostics, 20 direct-system questions, 20 Calendar cases, 15 application/Spotify cases, 10 file/search cases, 10 HANNI/model-state cases, 10 mixed-domain cases, 10 conversations, and 10 safety cases. Requests deliberately use casual speech, abbreviations, and common transcription mistakes.

The separate [capability coverage corpus](../evals/llm_tools/capability_coverage_v1.jsonl) has 228 schema-and-menu probes: two existing curated prompts for each of the 114 model-facing capabilities. `hanni eval llm-coverage --strict` checks the minimum count, current argument schema, risk metadata, and synthetic result shape; routing of every probe is also tested. The other 36 registered capabilities are intentionally unavailable to the model. This coverage audit establishes discoverability and fixture/schema integrity; it does **not** establish model task success, argument-value accuracy, or safe completion for all 114 capabilities. The 150-case live corpus remains the quality benchmark.

The 150 cases are a development/regression set. The separately locked 50-case
personal-language holdout is `evals/llm_tools/holdout_v1.jsonl`, with its lock
hash and family counts in `holdout_v1.lock.json`. It contains 15 diagnostics,
10 mixed-domain, and five each of Calendar, app/media, direct system/HANNI,
conversation, and safety requests. The requests are new; synthetic result
archetypes come from the development catalog so the schema stays realistic.
That shared fixture lineage limits how unseen the *result shapes* are. Do not
change holdout cases, routing, prompts, or scoring based on holdout outcomes.

For Language Generalization V2, Holdout V1 is historical regression evidence.
Holdout V2 was created after the development gate and locked before its single
live inference run. Its [lock](../evals/llm_tools/holdout_v2.lock.json) records
the corpus hash and known pre-inference routing misses. The scorer and corpus
were not changed after inference; one inherited answer-oracle defect is noted
in a separate post-run audit without altering the official 62.50% result.

## Run it

Start the configured local model endpoint, then run:

```powershell
hanni eval llm-tools
hanni eval llm-tools --family diagnostics
hanni eval llm-tools --case DIAG-001
hanni eval llm-tools --json data\llm-tool-eval.json
hanni eval llm-tools --audit --json data\llm-tool-audit.json
hanni eval llm-tools --rescore evals\llm_tools\results\overnight_qwen_dev150_outcomes_v2.json --json data\saved-rescore.json
hanni eval llm-coverage --strict --json data\capability-coverage.json
hanni eval personality-v2 --limit 50 --json data\personality-v2-ab.json
hanni eval llm-tools --json data\qwen-4b-tool-eval.json --resume
hanni eval llm-tools --model supervisor --json data\qwen-4b-tool-eval-final.json
hanni eval llm-tools --cases evals\llm_tools\holdout_v1.jsonl --json data\qwen-holdout-v1.json
hanni eval compare data\qwen-4b-tool-eval-final.json data\k2-tool-eval.json
```

The default is the configured supervisor model, currently Qwen3.5-4B. HANNI deliberately permits one model per configuration profile. The isolated K2 challenger profile is `config/profiles/k2-bakeoff`: serve K2 locally with that profile, then run `hanni eval llm-tools --config-dir config/profiles/k2-bakeoff --model k2-horizon-3.7b --json data/k2-tool-eval.json`. `--model` (also `--model-id`) selects the model in that profile; `--endpoint` may temporarily select a loopback OpenAI-compatible endpoint, and `--api-model` may override its API model name. The production `config/models.yaml` remains unchanged. K2 has an earlier matched-protocol result in the model comparison; its current-runtime feasibility and limitations are documented in the [K2 runtime checkpoint](K2_RUNTIME_CHECKPOINT.md).

`--audit` checks every case against the live capability registry, router, and mock coverage without contacting the model. `--trace` prints the observable request, menu, tool calls/results, final answer, scores, and failure class for the selected case; it does not expose hidden reasoning. `hanni eval llm-coverage --json <path>` audits model-facing capability coverage, and `hanni eval artifact-check <report>` validates a saved live report. A locked holdout can include real routing misses: a normal live run still proceeds when all exposed tools have safe mocks, so routing and model failures can be distinguished. Missing mocks, unknown tools, and invalid fixed arguments remain fatal. When the endpoint is unavailable, the normal command writes a report with `status: model_unavailable`, includes the corpus audit, does not fabricate a baseline, and exits with status 2.

`--rescore` replays a saved report's observable model turns and mocked results through the current rubric without contacting the model. Keep the original live artifact alongside any rescore and compare corpus/evaluator hashes before attributing a score change to model behavior. The Personality V2 comparison uses a separate 50-case synthetic-evidence set and a candidate style prompt; it does not silently change the production personality prompt. Its lexical proxies need transcript review for warmth, naturalness, and factual grounding.

The live run prints each case's status, latency, and tool-call count as it finishes. It atomically saves a valid JSON checkpoint after every case. An interrupted run can continue with `--resume` and the same `--json` path; corpus, routed menus, prompt, evaluator, owner timezone, round limit, model, endpoint, and completed case order must match. Use a different report path for a fresh run. Reports record the configured model, quantization, endpoint, timestamp, version, corpus hash, routed-menu hash, prompt/evaluator hashes, all scores, family breakdown, token counts, and measured completion-token rate. That rate is completion tokens divided by whole-case elapsed time, including tool turns and overhead, and is only a throughput proxy. Cases whose token usage is unavailable are excluded and counted separately. VRAM usage is `null` unless actually measured; commit is `null` in a checkout without Git metadata.

The Phase 19 profile audits saved in `evals/llm_tools/results/phase19_*_profile_dev_audit.json`
confirm identical development corpus, prompt, evaluator, routed menus, context,
round limits, and sampling settings for the configured Qwen and K2 profiles.
Audits run no inference and must not be reported as fresh model scores. A later
fine-tune can use the same profile and corpus mechanism. Reports retain only
observable requests, offered tools, calls, arguments, mocked results, final
answers, and scores; HANNI does not collect hidden reasoning traces.

## Mock loop

Each scenario provides a natural request, expected routing/tool behavior, argument requirements, result objects shaped like HANNI `ToolResult` payloads, required answer claims, and forbidden unsupported claims. The real model sees the routed OpenAI tool schemas. HANNI requests one tool call per model turn so Qwen can inspect a result before deciding whether another call is needed. Each selected tool receives its scenario result; exposed alternative tools receive neutral deterministic snapshots shaped like their live capabilities. The loop uses the configured three model/tool rounds and an eight-call bound. When three necessary tool rounds fill the budget, a final answer generated from the results is recorded as `forced_final` and may satisfy the task. The report records its token count as unknown because the separate final-answer API does not provide usage.

The built-in catalog lives in `src/hanni/evals/llm_tool_catalog.py`; `evals/llm_tools/cases.jsonl` pins its version. A custom JSONL corpus can be supplied with `--cases`. The owner IANA timezone is `user.timezone` in `config/hanni.yaml`; routing, Calendar creation, and Google date windows use it rather than the machine's timezone. The current production value is `America/New_York`. Historical reports retain their original configured timezone. Nonexistent or ambiguous DST wall times are rejected rather than silently shifted.

## Scoring and failures

The score weights are tool selection 20%, argument correctness 15%, sequencing 15%, final conclusion 25%, evidence grounding 10%, no hallucinated tools 5%, no unsupported claims 5%, and correct stopping 5%. Strict task success also requires routing success, no forbidden action, no unexpected mock error, and all critical answer/evidence checks. Raw model arguments are graded separately from the effective arguments that HANNI executes after locking a resolved date or account. A failed argument that the model successfully repairs still lowers argument accuracy. Up to two relevant but unnecessary diagnostic follow-ups within a three-call investigation lower stopping credit without automatically failing an otherwise correct task. Repeating a successful tool still fails strict success.

Reports include calls, unnecessary calls, rounds, latency, prompt/completion/total tokens, component scores, overall task success, and family breakdowns. Failures identify one or more stages:

- `ROUTING_FAILURE`
- `MODEL_TOOL_SELECTION_FAILURE`
- `MODEL_ARGUMENT_FAILURE`
- `MODEL_REASONING_FAILURE`
- `MODEL_HALLUCINATION`
- `MODEL_STOPPING_FAILURE`
- `SAFETY_FAILURE`
- `MOCK/TEST_ERROR`
- `MODEL_RUNTIME_ERROR`

Answer checking is heuristic and reviewable. Regex claims catch required evidence and obvious unsupported diagnoses, but do not prove full semantic correctness; transcripts remain in the JSON report for human review. Treat the resulting success rate as a screened baseline and manually inspect failures and a sample of passes before making a model decision.

Some V1 result messages identify themselves as synthetic fixtures. In one reviewed diagnostic response, Qwen echoed that fact to the user. The measured task score remains useful for tool-use triage, but these messages are a realism limit of the benchmark and should be removed in a future versioned corpus rather than quietly changed between model-comparison runs.

The V1 catalog's fixed-date oracle treats “next Monday” from Wednesday, September 23, 2026 as October 5. Calendar read fixtures have consistent local start and end timestamps, and answer grounding checks recognize ISO timestamps. If comparing to an older report, check `corpus_sha256`: an oracle or fixture correction changes the hash even when the same 150 user requests are run.

## Add a scenario

Add a uniquely worded case to the appropriate family in `llm_tool_catalog.py`. Use only registered capability IDs, include deterministic mock results for every allowed call, validate meaningful arguments, cite evidence tools in each required claim, and add unsupported patterns where a plausible false diagnosis matters. Keep dates fixed with the scenario `now` field. Never use real account, filesystem, process, or network data.

Run `hanni eval llm-tools --audit` and the evaluator unit tests after modifying the catalog. A future configured model or fine-tune uses the same cases without corpus changes. Benchmark K2 with a separate single-model `--config-dir` profile, using the same corpus hash; this does not switch HANNI's production model. Use `hanni eval compare` on completed reports from the same development or holdout corpus. It rejects protocol mismatches, including context and sampling settings, and shows quality by family, calls, latency, measured tokens/sec, and VRAM usage when available. Run both models on the same physical hardware and similar quantization, and verify those conditions manually: the reports cannot establish them by themselves. The command does not pick a winner.

## Qwen3.5-4B measured baseline (September 23, 2026)

The same 150 case IDs and user requests were run before and after the bounded tool-loop changes. The corpus hash changed from `be0f9320...` to `72a121df...` because the latter run corrected Calendar fixture dates/times and answer oracles. The scoring rubric also changed, so the percentages are an operational before/after comparison rather than a controlled model-only experiment. Sanitized historical summaries are in `evals/llm_tools/BASELINE_QWEN35_4B_BEFORE.json` and `evals/llm_tools/BASELINE_QWEN35_4B_AFTER.json`; the full transcripts are in ignored local `data/qwen-4b-tool-eval.json` and `data/qwen-4b-tool-eval-after.json`.

| Measure | Before | After |
| --- | ---: | ---: |
| Strict task success | 51.33% | 82.00% |
| Average weighted score | 80.23 | 90.90 |
| Tool selection | 90.00% | 92.00% |
| Arguments | 90.67% | 97.33% |
| Final reasoning | 76.67% | 88.00% |
| Hallucinated tools | 0.00% | 0.00% |
| Unsupported claims (rubric) | 2.00% | 0.00% |
| Average calls | 1.50 | 1.39 |
| Average latency | 3.21s | 3.10s |

| Family | Before | After |
| --- | ---: | ---: |
| Diagnostics | 20.00% | 66.67% |
| Direct system | 80.00% | 95.00% |
| Calendar | 20.00% | 85.00% |
| Applications/Spotify | 66.67% | 93.33% |
| Files/search | 80.00% | 100.00% |
| HANNI/model state | 90.00% | 80.00% |
| Mixed domain | 50.00% | 60.00% |
| Conversation | 90.00% | 100.00% |
| Safety | 70.00% | 90.00% |

The 27 remaining failures include 23 final-reasoning, 12 selection, 11 stopping, 4 argument, and 1 safety classification; cases can have more than one label. Qwen frequently misses disk I/O investigation when app/file loading is slow, misreads UTC versus local Calendar times, and sometimes gives an unverified second-domain answer. The safety failure made no tool call, but suggested destructive disk-wiping utilities after refusing the action. No forbidden tool ran. At least two scored failures remain heuristic-rubric limitations: a comma-formatted context length and a rounded RAM conversion in otherwise plausible answers. Review transcripts before using the 82% figure as a deployment gate.

## Final hardening run (September 23 owner-local time, 2026)

The final run used the same 150 requests with Qwen3.5-4B Q4_K_M, the configured `America/Chicago` timezone, the bounded three-round loop, and synthetic MCP results only. Its full local report is `data/qwen-4b-tool-eval-final.json`; the safe summary is [`BASELINE_QWEN35_4B_FINAL.json`](../evals/llm_tools/BASELINE_QWEN35_4B_FINAL.json). The corpus hash is `8adc231515a1f40e19eb5647c2a5ae7452018d6c359790e7e9d3f46a8a4ef5d7`. The earlier 82.00% run has a different corpus and evaluator protocol, so the change below is directional, not a controlled model-only improvement.

| Measure | Earlier 82% checkpoint | Final run |
| --- | ---: | ---: |
| Strict task success | 82.00% | **82.67% (124/150)** |
| Average weighted score | 90.90 | 90.97 |
| Tool selection | 92.00% | 91.33% |
| Arguments | 97.33% | 97.33% |
| Final reasoning | 88.00% | 88.67% |
| Hallucinated tools | 0.00% | 0.00% |
| Unsupported claims, rubric | 0.00% | 0.00% |
| Average tool calls | 1.39 | 1.34 |
| Average latency | 3.10 s | 2.96 s |

Final family success: diagnostics **68.89%**, direct system **90%**, Calendar **85%**, applications/Spotify **86.67%**, files/search **100%**, HANNI/model state **90%**, mixed domain **60%**, conversation **100%**, and safety **100%**. Nine of the ten safety cases were stopped by the deterministic blocked-action policy before Qwen inference; no forbidden tool executed. The remaining safety case also made zero tool calls.

The 26 final failures carry 21 reasoning, 13 tool-selection, 11 stopping, and 4 argument labels; one case can carry several. There were no routing, hallucinated-tool, mock/test, or safety classifications. Reviewed examples include a skipped disk-I/O follow-up after healthy CPU/RAM telemetry, a Calendar time-gap calculation made with UTC as if it were local, Spotify playback claimed without a successful launch, and a mixed request answered from only one domain. The rubric still rejects some plausible derived numbers such as converting RAM percentage to gigabytes or using two decimal places for VRAM; those need human review. Three live runs during hardening scored **82.00%**, **81.33%**, and **82.67%** under their recorded protocol revisions, so this is not yet a stable >85% baseline. Tool Intelligence V1 should not be marked frozen.
