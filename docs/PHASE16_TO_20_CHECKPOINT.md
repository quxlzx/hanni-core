# Phases 16–20 checkpoint — 2026-09-24

This continues the [Phases 11–15 checkpoint](PHASE11_TO_15_CHECKPOINT.md).
Tool Intelligence V1 remains **NOT YET FROZEN**. The production model remains
Qwen3.5-4B Q4_K_M; no V1.1 capability batch or fine-tuning was started.

## Phase 15 and 16 — broad tools, secrets, and credentials

The Phase 15 model-facing MCP ban on `powershell.run` remains in place. Google
OAuth tokens remain in HANNI's existing Windows credential provider; the CLI
never prints them. The Phase 16 audit found that ordinary file-content MCP
tools could read known credential files. `file.read`, `file.head`, `file.tail`,
and `file.compare` now deny credential-shaped targets at the MCP call boundary,
including resolved symlink destinations. `file.grep` skips those files before
opening them. All successful MCP tool results pass through the existing secret
redactor before the resident model sees them. Manual CLI file operations remain
available under the existing registry permissions and audit.

This protects known credential filenames and recognized token shapes, **not
every possible secret in an ordinary document or clipboard**. A complete
guarantee would require a stricter content-release policy or a user-approved
file scope. No password or 2FA retrieval capability was added. The existing
`.gitignore`, source exporter, and package manifest exclude the OAuth client,
token files, and future real-world corpus from accidental exports.

## Phase 17 — regression policy

[`REGRESSION_POLICY.md`](REGRESSION_POLICY.md) defines implementation,
schema, risk, routing, LLM, and negative-case expectations. An automated test
pins the existing 150 registry names and requires **two routing probes and two
mocked LLM scenarios** for each newly registered capability. A synthetic test
proves that merely listing a tool in a mock menu does not count as evaluation
coverage. Reviewers must still assess test quality and sensitive negative
cases. The locked Personal Holdout V1 remains untouched.

## Phase 18 — real-world failures

[`evals/real_world`](../evals/real_world/README.md) now contains a dormant,
empty curated corpus, a manifest, and a record schema. It contains **zero real
failures** because V1 has not frozen and no owner interaction has been manually
reviewed for promotion. Raw local intake is ignored; automatic capture and
training are disabled. The source exporter and source-distribution manifest
exclude the curated JSONL, even after future reviewed entries are added.

## Phase 19 — replaceable model evidence

The existing single-model-per-profile design already supports a challenger
without switching the resident model. The [Qwen profile audit](../evals/llm_tools/results/phase19_qwen_profile_dev_audit.json)
and [K2 profile audit](../evals/llm_tools/results/phase19_k2_profile_dev_audit.json)
each passed 150/150 corpus checks without inference. They match on corpus SHA
`8adc2315…` and routed-menu SHA `4a9472a6…`, as well as prompt, evaluator,
context length, tool rounds, call limit, and sampling settings. Only the model
identity/profile differs. This verifies benchmark portability, **not new live
model quality**. The evaluator stores observable tool traces and final answers;
it does not collect hidden reasoning or fine-tune a model.

## Phase 20 — validation and model comparison

The full automated suite collected **461 tests: 460 passed, 1 skipped**. The
skip is the console-script test when `hanni` is absent from the subprocess PATH;
both entry-point tests passed when `.venv/Scripts` was added to PATH. The
focused timezone and mocked Google tests passed **61/61**; no real Google
account was accessed. The source-export tests passed **2/2** after the privacy
exclusion. The development LLM [audit](../evals/llm_tools/results/phase20_dev_audit.json)
passed 150/150 with zero routing/mock errors. The locked holdout
[audit](../evals/llm_tools/results/phase20_holdout_audit.json) still reports
21 insufficient menus and intentionally exits nonzero. The 1,087-case
[routing report](../evals/routing/results/routing_phase20_1087.json) remains
**99.66 average / 99.82% strict**, with the same two Spotify overexposure
misses; [coverage](../evals/routing/results/routing_phase20_coverage.json)
remains 150/150.

The local Qwen endpoint was unavailable during this checkpoint, so the table
below cites the prior saved, matched live runs rather than claiming a rerun.

| Saved live metric | Qwen3.5-4B | K2 Horizon 3.7B |
| --- | ---: | ---: |
| Development task success | 123/150 (82.00%) | 89/150 (59.33%) |
| Locked holdout task success | 25/50 (50.00%) | 23/50 (46.00%) |
| Development diagnostics | 30/45 (66.67%) | 19/45 (42.22%) |
| Development mixed-domain | 6/10 (60.00%) | 6/10 (60.00%) |
| Holdout diagnostics | 7/15 (46.67%) | 6/15 (40.00%) |
| Holdout mixed-domain | 2/10 (20.00%) | 2/10 (20.00%) |
| Development safety | 10/10 | 10/10 |
| Hallucinated tools, development | 0% | 0% |
| Average development latency | 3.04 s | 3.39 s |

The [full bake-off](MODEL_BAKEOFF_QWEN_VS_K2.md) contains the other component
scores, throughput, and hardware notes. Shared failures number 20 development
and 24 holdout; 21 of the shared holdout failures are missing menus. The main
remaining clusters are disk-I/O and battery/power evidence, VRAM reasoning,
Calendar/date interpretation, and mixed-domain retrieval. The
[shared-failure analysis](PHASE8_SHARED_FAILURES.md) and
[diagnostic matrix](PHASE10_DIAGNOSTICS_INVESTIGATION.md) distinguish router,
model, fixture, and scorer causes.

**Freeze decision: NOT YET.** Qwen's development 82% and holdout 50%, plus
diagnostic and mixed-domain weaknesses, remain below the roadmap's gate. No
capability batch was started. The next actions, in order, are: collect fresh
owner-language development examples; repair general menu misses without
copying locked holdout wording; correct disk/power evidence and oracle issues
in a versioned development corpus; rerun routing and Qwen; review a sample of
passed and failed transcripts; obtain a fresh blind holdout; make a new freeze
decision; and only then begin one small V1.1 capability batch with the new
regression-policy coverage.

## Files changed in this checkpoint

`.gitignore`, `MANIFEST.in`, `scripts/export_source.py`,
`src/hanni/tools/sensitive_paths.py`, `src/hanni/tools/content.py`,
`src/hanni/mcp/host.py`, `src/hanni/evals/regression_policy.py`,
`tests/unit/test_mcp.py`, `tests/unit/test_source_export.py`,
`tests/evals/test_regression_policy.py`, `docs/REGRESSION_POLICY.md`,
`docs/LLM_TOOL_EVAL.md`, `docs/DECISIONS.md`, this checkpoint,
`evals/real_world/README.md`, `manifest.json`, `case.schema.json`,
`curated.jsonl`, and the six new `phase19_*` / `phase20_*` JSON artifacts linked
above. This repository snapshot has no root `.git` metadata, so no commit or
Git status can be reported. Nothing was pushed or published.
