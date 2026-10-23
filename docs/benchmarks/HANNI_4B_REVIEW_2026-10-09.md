# HANNI 4B benchmark review

Prepared 2026-10-09 15:44 EDT for review on **October 10, 2026**.

**Result: 113/194 passed (58.25%) under the unchanged heuristic strict rubric; 81 failed.** The original 150-case core passed 95/150 (63.33%); the 44 extension probes passed 18/44 (40.91%). The original HANNI-4B-v0 export could not load. These quality scores are from a separately preserved metadata-corrected copy with identical tensor bytes. The original file and production Qwen configuration remain unchanged.

This was run directly through the repository evaluator by Codex. HANNI's autonomous workflow registry does not currently contain a benchmark-running capability; this is not a successful native autonomous workflow or a fresh blind evaluation. No real tool/provider action was executed. All tool results are the existing synthetic fixtures, including historical pinned dates. The corpus currently contains 194 cases despite older documentation describing 150.

## Five most significant weaknesses

The ranking prioritizes a deployment blocker, then widespread behavioral failures, then measurement limitations. Items 2–4 concern model behavior in this pipeline. Items 1 and 5 concern its export and evaluation stack. Counts overlap and must not be added.

| Rank | Weakness | Evidence | Why it matters / next step |
|---|---|---|---|
| 1 | Export metadata prevents a normal launch | Original declares 33 blocks and one prediction block; inventory has only blocks 0–31. Runtime aborts at missing blk.32.attn_norm.weight. | The original artifact cannot be deployed or benchmarked as supplied. Correct the exporter metadata and require a real load/smoke check before releasing a GGUF. |
| 2 | Repeats successful calls and fails to stop | 62/81 failed cases contain actual DUPLICATE_SUCCESSFUL_CALL receipts; 61 carry the official stopping label. DIAG-001 retrieves sufficient CPU evidence, then repeats system.performance. | Wastes the bounded call budget and prevents strict completion even with a correct final answer. Train/evaluate transitions from sufficient evidence to answering, and progress toward an unmet subtask after a rejected duplicate. Keep execution duplicate guards intact. |
| 3 | Drops the second part of mixed requests | Mixed-domain: 1/10 passed. Nine failures omit the required second-domain answer. MIX-001 repeats Calendar instead of reading RAM; MIX-005 opens Discord in the mock but never checks CPU. | Multi-step requests remain incomplete despite available routed tools. Check coverage of every requested clause before finishing and evaluate with new independently written mixed requests. |
| 4 | Does not consistently turn evidence into the correct conclusion | 30 failed cases carry reasoning labels; diagnostics pass 18/45. DIAG-002 reads python.exe at 88% CPU but omits the contributor. CAL-005 says the user is free after 6 despite a 19:00–20:00 event. MIX-004 mentions a RAM check that never occurred. | Correct retrieval alone does not produce a reliable answer. Preserve explicit source attribution, check interval arithmetic, and reject statements about observations that were never obtained. |
| 5 | Benchmark labels and answer heuristics need review before they can support a release decision | Five failed cases have an empty failure_classification despite unexpected execution failures. CAL-013's successful mock creation and “dentist is on Monday at 9” confirmation fail the lexical creation check; DIAG-043 uses a plausible GPU-specific alternative but misses a required broad-system tool. | The official score mixes genuine defects and arguable oracle/coverage choices. Preserve this run; separately adjudicate disputed transcripts and classify effective-argument duplicate failures explicitly. Do not silently rescore or treat this proxy as validated real-world accuracy. |

## Measurements

| Metric | Value / scope |
|---|---|
| Official screened strict pass rate | 113/194, 58.25%; illustrative Wilson 95% interval 51.21–64.96% |
| Average weighted score | 86.55/100; high partial credit does not imply whole-task completion |
| Tool-selection accuracy proxy | 92.78% |
| Argument accuracy proxy | 99.48%; fixed server arguments and narrow fixture expectations limit interpretation |
| Reasoning accuracy proxy | 85.57% |
| Hallucinated-tool / unsupported-claim proxies | 0.00% / 0.52%; lexical checks are not independent semantic verification |
| Mean / P50 / P95 whole-case latency | 1.581 / 1.763 / 2.596 s; all 194 cases, linear interpolation |
| Startup | 10.655 s, excluded from whole-case timers |
| Mean tool calls | 1.80 |
| Completion throughput proxy | 46.74 tokens/s over 86 cases with reported usage; includes case overhead |
| Routing failures / inference runtime errors | 0 / 0 in the successful copy run |
| Forbidden calls | 0 observed in the synthetic loop; no real sensitive operation was attempted |
| Policy-blocked cases | 17/17 pass before model inference; excluding them gives 96/177 (54.24%) |
| Peak VRAM / first-token latency | NOT MEASURED |

The interval describes this finite scored cohort under a binomial model; the curated, correlated development cases are not a random population sample. It does not establish unseen success, training independence or real provider/action reliability. No previously sealed private workflow cases were read or rerun. Historical runs use different corpora/protocols, so this is not a paired quality regression or model bake-off.

### Family results

| Family | Passed / assessed | Strict pass rate |
|---|---:|---:|
| applications_spotify | 10/15 | 66.67% |
| calendar | 15/20 | 75.00% |
| conversation | 10/10 | 100.00% |
| diagnostics | 18/45 | 40.00% |
| direct_system | 14/20 | 70.00% |
| email | 0/4 | 0.00% |
| files_search | 9/10 | 90.00% |
| google | 18/40 | 45.00% |
| hanni_model | 8/10 | 80.00% |
| mixed_domain | 1/10 | 10.00% |
| safety | 10/10 | 100.00% |

### Original failure labels

| Label among failed cases | Cases |
|---|---:|
| MODEL_STOPPING_FAILURE | 61 |
| MODEL_REASONING_FAILURE | 30 |
| MODEL_TOOL_SELECTION_FAILURE | 14 |

Five additional failed cases have no class: EMAIL-CAPABILITY-002, EMAIL-CAPABILITY-003, EMAIL-CAPABILITY-004, GOOGLE-LAYER-GOOGLE-CALENDAR-AVAILABILITY-1, GOOGLE-LAYER-GOOGLE-DOCS-READ-2. Original aggregate labels are retained exactly. FILE-002 carries an argument-error label but eventually passes; it is excluded from the failed-case label table. Its initial “budget spreadsheet” query is rejected by the narrow fixture expectation, then repaired to “budget”; this does not demonstrate general inability to form real search arguments.

The qualitative review inspected 19 representative transcripts, listed in analysis.json. It is a coordinator review, not an independent human adjudication of every case. CAL-013 and GPU-alternative observations are flagged for owner review; the official result remains 113/194 and was never rescored. All model replies, calls, arguments, receipts and original checks remain in results.json.

## Metadata correction and runtime

The original runtime expects tensors for declared MTP blocks, consistent with its [Qwen3.5 loader source](https://github.com/ggml-org/llama.cpp/blob/50f068fff/src/models/qwen35.cpp). Inspection found no block-32 tensors. An isolated copy changes qwen35.block_count from 33 to 32 and removes the incorrect nextn_predict_layers and recurrent_layers declarations. The retained full_attention_interval is four; runtime uses its standard attention-pattern derivation. This avoids claiming missing weights exist.

Every tensor-directory byte and the complete tensor payload match the original. Payload SHA256: 15a750fd4941fae94fb8cbc36e6a442c88e70ab9c9bc8e35a3ab4333dedd79dd. Original file SHA256: 4a7b0aa6a874cad28c0870ea11b5c0cad82330dd9ffbd7cb0327bee8a58a66f9. Benchmarked copy SHA256: df56ee88d7e8e0b5c39363208e9e2dcc1c0388f9ff4ac3a3f076367a0c5eaa27. The original failed-load log remains under data/benchmarks/2026-10-09-4b-review/state/dashboard-supervisor.log; metadata-correction.json and both inventories are under data/benchmarks/2026-10-09-4b-export-check/.

The original ModelManager/LlamaCppClient loaded the existing copy using llama.cpp build 10679 (50f068fff), Vulkan1 on the NVIDIA RTX 5060 Laptop GPU with observed 33/33 offloaded layers, 16,384 context, one parallel slot and q8 KV cache. Tool turns use original temperature 0; final chat temperature 0.35/top_p 0.9/max_tokens 768. Original three tool rounds/eight-call ceiling apply. An isolated profile changes only the model filename and owned loopback endpoint; production configuration and permissions do not change. No model or runtime download was required. The metadata copy is not automatically installed or promoted to production.

## Saved evidence and review handoff

- [Original results and transcripts](../../data/benchmarks/2026-10-09-4b-review-fixed-metadata/results.json)
- [Report-only analysis](../../data/benchmarks/2026-10-09-4b-review-fixed-metadata/analysis.json)
- [Owned runtime and source metadata](../../data/benchmarks/2026-10-09-4b-review-fixed-metadata/run-metadata.json)
- [Progress and evaluator log](../../data/benchmarks/2026-10-09-4b-review-fixed-metadata/evaluation.log)
- [Metadata-only copy evidence](../../data/benchmarks/2026-10-09-4b-export-check/metadata-correction.json)

Source commit: 7379ae0e99759c1254067ac5f63ad31f35e1b986. Frozen source/config/corpus projection: 9aa4f63399f457120a64be536bb8eea7c4a86686b2ff72c5e91c10a8f3afed45 (180 files), identical after the run. Corpus SHA256: 4ae0cd232c85f3c411b7f54c869f3e405d96e1f54b1367f6c0f4f42aac0c48c7. Evaluator SHA256: 368317fd8a305f674402b1c703902e00f0ffa7d6ed74eccff8780ea73e09ff67. Original result SHA256: a08ec2944741abc5cfa0e5af684e4cfa9a40aff6a7d8b2a5b7d2a58546bf3332.

Artifact integrity check passed all 194 completed cases. The owned model PID 13020 closed; the final process query found no llama-server/HANNI desktop/production assistant running. Originals and previous benchmark results remain intact. Raw results, transcripts and model files remain in ignored local data; this sanitized report is saved in Git. No push occurred; no publication, notification or scheduled job was created. The report is ready now for tomorrow's review, with no user action pending.

Prioritize the export release check, stopping behavior and complete request coverage before changing production. For a future candidate, retain this development run as regression evidence and use a new sealed evaluation with richer outcome fixtures and separately adjudicated semantic criteria. Do not tune oracles to make the current answers pass.
