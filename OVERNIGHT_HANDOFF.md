# HANNI overnight handoff — 2026-09-24

**Status: development checkpoint; Tool Intelligence V1 is not frozen.** The roadmap's Phase 34 gate failed on fresh-language routing and Qwen diagnostics. No blind Holdout V2 was created or run. No post-freeze V1.1 capabilities were added. Production remains Qwen3.5-4B; nothing was pushed or published.

## What changed

HANNI now has a structured dev150 failure ledger, a traceable mocked-tool evaluator, stronger evidence/action-completion checks, sensitive-file blocking, pinned timezone handling, Language V3 and mutation probes, capability/context/artifact audits, and a launcher that probes its editable install and speech dependencies before installing. App launch now reports an accepted request without pretending that a process is verified running. Google login/status/logout remain available through the existing CLI, with mocked OAuth tests; no real login was attempted.

## What passed and failed

| Check | Result |
| --- | --- |
| Full pytest | **503 passed, 1 skipped, 17 subtests passed**, 36.18s |
| Frozen routing | **99.82%** strict, 1,087 cases |
| Language V2 | **100%** strict, 200 cases |
| Fresh Language V3 | **63.33%** strict, 150 cases; **fails >=90% gate** |
| Multi-turn routing | **100%**, 50 dialogues/108 turns |
| Voice routing | **100%**, 15 cases |
| Qwen live dev150 | **132/150 = 88.00%** |
| Qwen diagnostics | **34/45 = 75.56%; fails >=80% gate** |
| Qwen mixed domain / safety | **90% / 100%** |
| Historical Holdout V1 | **26/50 = 52.00%**, development regression only |
| Model hallucinated tools | **0%** in the live dev150 |

The old matched-protocol K2 result was 89/150 and 23/50; K2 was **not rerun** on this changed Qwen protocol/corpus, so there is no new controlled comparison. The local Qwen endpoint completed its runs without a server crash. No real capability handlers, Google account, process-control action, or external account action were used by the evaluator. Safety-family success includes deterministic router/policy refusals, not independent model refusal proof.

Source export succeeded to a temporary ZIP outside the repository (406 files); the archive contained the handoff and new evaluation corpus and no credential, token, or private real-world corpus entries. The archive was not published. Final focused tests passed (45 source/export/evaluator/session checks and 25 mocked Google tests). The Google CLI `login/status/logout --help` commands all exited successfully.

## Files to open first

- [Detailed development report](docs/TOOL_INTELLIGENCE_FINAL_PUSH_REPORT.md)
- [Qwen dev150 live artifact](evals/llm_tools/results/overnight_qwen_dev150_outcomes_v2.json)
- [Historical Holdout V1 artifact](evals/llm_tools/results/overnight_historical_holdout_v1.json)
- [Fresh Language V3 routing result](evals/routing/results/overnight_final_language_v3.json)
- [Full test timings](evals/checkpoints/overnight_pytest_durations_final.txt)
- [Before checkpoint](evals/checkpoints/tool_intelligence_final_push_before.json) and [final hash/file checkpoint](evals/checkpoints/tool_intelligence_final_push_after.json)

The separate ~300-case capability coverage corpus, Personality V2 live A/B, full microphone/barge-in stress, complete error-recovery matrix, dialogue compaction, exhaustive startup/shutdown/GPU matrix, and blind Holdout V2 remain unfinished or gated. The model-facing capability audit identifies 73 currently unrepresented model-facing tools. There is no `.git` directory in this workspace, so `git status`/commits cannot establish the delta; checkpoint hashes and file lists are used instead.

**Exact next step:** review the 11 Qwen diagnostic failures and the fresh V3 routing misses, make generalizable diagnostic/language fixes while preserving frozen-router safety, then rerun all Phase 34 development checks. Create and seal blind Holdout V2 only after the development thresholds pass.
