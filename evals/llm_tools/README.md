# HANNI LLM Tool Eval V1

Run an already-serving local Qwen model through the production router and tool
schemas, returning only synthetic results. No real capability handler is available.

```powershell
hanni eval llm-tools --json data\llm-tool-eval.json
```

The versioned built-in catalog contains 150 scenarios spanning diagnostics, direct
system questions, Calendar, apps/Spotify, files, model state, mixed-domain requests,
conversation, and safety. Reports separate routing, selection, argument, sequencing,
reasoning, hallucination, safety, mock, and stopping failures.

The current production-prompt Qwen3.5-4B development report is
`results/final_generalization_qwen_production_v2.json`: **139/150 (92.67%)**.
The single locked `holdout_v2.jsonl` run is
`results/qwen_holdout_v2_locked_once.json`: **45/72 (62.50%)**, with 24 routing
failures. The holdout and development-freeze hashes are recorded in
`holdout_v2.lock.json` and `evals/checkpoints/pre_holdout_v2.json`. Tool
Intelligence V1 is not frozen.

`capability_coverage_v1.jsonl` is a separate 228-probe schema/menu corpus with
two curated requests for each model-facing capability. Run
`hanni eval llm-coverage --strict` to fail on missing probes, fixture/schema or
risk drift, poor descriptions, or routing misses. This audit does not establish
LLM task success for those 114 capabilities; use the 150-case live benchmark for
that question.

Final-answer checks are heuristic, with explicit evidence and unsupported-claim rules;
manual transcript review is required before judging model suitability. Scripted-client
unit tests validate the harness only and are never included as a Qwen baseline.

Use `--model` for another configured model, or a loopback `--endpoint` plus
`--api-model`, without changing production configuration. Compare two complete
reports with `hanni eval compare FIRST.json SECOND.json`; the command rejects
different corpora, menus, prompts, evaluators, timezones, or round limits.

`BASELINE_QWEN35_4B_FINAL.json` is the sanitized summary of the completed
September 23 owner-local 150-case Qwen run: **82.67%** strict task success.
The full checkpoint and transcripts are in ignored
`data/qwen-4b-tool-eval-final.json`. The two earlier
`BASELINE_QWEN35_4B_BEFORE.json` and `BASELINE_QWEN35_4B_AFTER.json` are
sanitized summaries extracted from two completed historical Qwen runs (51.33%
and 82.00% strict task success). The old `BASELINE.json` was a stale
`model_unavailable` report and has been removed. Historical run protocols differ,
so the two summaries are directional before/after evidence, not a controlled
model comparison. The final run also changed the answer-check oracle for a
thousands separator and fixed a false unsupported-claim match; its corpus and
evaluator hashes record those changes. This historical run was below the
later target; current development reports use separate corpus and prompt hashes.
Architecture, limitations and commands are in
[the full evaluator documentation](../../docs/LLM_TOOL_EVAL.md).
