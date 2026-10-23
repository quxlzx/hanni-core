# Language Generalization V2 file checkpoint

This directory has no `.git` metadata, so a Git diff, clean-tree assertion, or
commit is unavailable. The following is the explicit file-level checkpoint for
this milestone. No push or publish was attempted.

## Source, configuration, tests, and documentation changed

- `.gitignore`
- `README.md`
- `config/hanni.yaml`
- `config/profiles/k2-bakeoff/hanni.yaml`
- `docs/LLM_TOOL_EVAL.md`
- `docs/LANGUAGE_GENERALIZATION_V2_REPORT.md`
- `docs/LANGUAGE_GENERALIZATION_V2_CHECKPOINT.md`
- `docs/PERSONALITY_V1.md`
- `docs/POST_FREEZE_DESIGNS.md`
- `evals/real_world/README.md`
- `evals/real_world/voice_routing_v1.jsonl`
- `evals/routing/README.md`
- `evals/routing/language_generalization_v2.jsonl`
- `evals/routing/multiturn_v1.jsonl`
- `evals/personality/personality_v1.jsonl`
- `src/hanni/cli.py`
- `src/hanni/config/loader.py`
- `src/hanni/config/schema.py`
- `src/hanni/core/orchestrator.py`
- `src/hanni/evals/llm_tool_catalog.py`
- `src/hanni/evals/personality.py`
- `src/hanni/evals/routing_debug.py`
- `src/hanni/evals/routing_language.py`
- `src/hanni/evals/routing_multiturn.py`
- `src/hanni/evals/routing_perf.py`
- `src/hanni/mcp/host.py`
- `src/hanni/tools/calendar_routing.py`
- `src/hanni/tools/capabilities.py`
- `src/hanni/tools/language_concepts.py`
- `src/hanni/tools/routing_intents.py`
- `tests/evals/test_language_generalization_v2.py`
- `tests/unit/test_personality_config.py`

## Saved evaluation artifacts

- `evals/routing/results/language_v2_old_coverage.json`
- `evals/routing/results/language_v2_old_regression.json`
- `evals/routing/results/language_generalization_v2.json`
- `evals/routing/results/multiturn_v1.json`
- `evals/routing/results/voice_routing_v1.json`
- `evals/routing/results/language_v2_performance.json`
- `evals/routing/results/language_v2_metadata_audit.json`
- `evals/llm_tools/results/language_v2_capability_coverage.json`
- `evals/llm_tools/results/language_v2_dev_audit_postfix.json`
- `evals/llm_tools/results/language_v2_holdout_v1_routing_audit.json`
- `evals/llm_tools/results/language_v2_qwen_dev150.json`
- `evals/llm_tools/results/language_v2_qwen_dev150_final.json`
- `evals/llm_tools/results/language_v2_qwen_holdout_v1_historical.json`
- `evals/llm_tools/results/language_v2_failure_analysis.json`
- `evals/personality/results/personality_ab.json`

Local `qwen-server.*.log` runtime logs are ignored by `.gitignore`; they are
not benchmark artifacts or source files. The model is an existing local GGUF.

## SHA-256 corpus and model-result hashes

| File | SHA-256 |
|---|---|
| `evals/routing/language_generalization_v2.jsonl` | `4ec6cd5e72843a993949e045304504f1fb858ae54c82b37424e0c0e61723c8c2` |
| `evals/routing/multiturn_v1.jsonl` | `35d7778ca451d01a77270805f063f56c49537191ea34fd9362f2c45918b80384` |
| `evals/real_world/voice_routing_v1.jsonl` | `86d114d9235b50efacb7d525b55c144c6e24ec5ea8950e6ba183a180f5ae0104` |
| `evals/personality/personality_v1.jsonl` | `0872e6ef9e83518c97dd14a5a9aa6f0bb1ae3efd9eb64241e8070a6623e7a3b7` |
| `evals/llm_tools/results/language_v2_qwen_dev150_final.json` | `ea37a5696c0eb6dfc2ef0bb32809f1801c578894a407b9f20290e6d31777173f` |
| `evals/llm_tools/results/language_v2_qwen_holdout_v1_historical.json` | `99701ed0a4b3b54306ed404b07d4cf8347f320f2a0050289e06e0a146a767860` |
| `evals/personality/results/personality_ab.json` | `920b63b6ad20c92b3bda2efdf88f48d83e1d20ec20e9c51947134c413a02e389` |

The 200-case routing and 50-dialogue corpora are **development sets**. No blind
Holdout V2 corpus exists because the Qwen development result did not meet the
freeze gate. The historic 50-case Holdout V1 is regression evidence only.

Full validation: 470/470 tests passed; frozen routing 99.82% on 1,087 cases;
V2 development routing 100% on 200 cases; Qwen tool development 125/150
(83.33%); historical Holdout V1 rerun 21/50 (42.00%). Freeze status:
**TOOL INTELLIGENCE V1 NOT READY TO FREEZE**.
