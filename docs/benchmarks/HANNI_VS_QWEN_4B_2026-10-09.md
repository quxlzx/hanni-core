# HANNI 4B main-model comparison, 2026-10-09

**Recommendation: keep Qwen3.5-4B-Q4_K_M as the main model.** It completed 169/194 cases (87.11%), compared with 113/194 (58.25%) for the HANNI candidate. Qwen completed 56 more cases, handled substantially more requests containing multiple tasks, and repeated fewer successful tool calls. HANNI's lower measured latency and lower unsupported-claim proxy are useful advantages, but they do not outweigh the completion gap and the original export's loading failure.

The production model configuration was left unchanged. HANNI remained stopped; both isolated benchmark model processes were closed after their runs. This report records a relative model recommendation, not approval of autonomous operation.

## What was benchmarked

The requested `HANNI-4B-v0-Q4_K_M.gguf` is the same exact file evaluated for the preceding review. Its original SHA-256 was checked again and is unchanged. This comparison reuses that completed candidate run and adds a fresh Qwen baseline run under the matching protocol. It does not represent a second candidate run.

The original HANNI file fails to load in the installed llama.cpp runtime: its metadata declares 33 blocks, but its tensor inventory contains blocks 0 through 31. The runtime reports `tensor 'blk.32.attn_norm.weight' not found`. A separate metadata-only corrected copy was used to obtain the candidate's inference results. That copy declares 32 blocks and removes the inconsistent next-layer and recurrent-layer declarations. Its tensor directory and complete tensor payload were verified identical to the original. The original file was preserved.

Both completed runs used the repository's unchanged development evaluator, all 194 current cases in the same order, the same routed tool menus, prompt, scoring rules, and settings. The suite contains 150 core cases plus 44 email/Google schema probes. Tool results were synthetic, and real tool execution was disabled. Codex ran the repository evaluator directly; this was not an autonomous HANNI benchmark workflow.

## Results

| Measure | HANNI metadata-corrected copy | Qwen main model |
|---|---:|---:|
| Strict case passes | 113/194 (58.25%) | 169/194 (87.11%) |
| Core cases | 95/150 (63.33%) | 134/150 (89.33%) |
| Email/Google extension | 18/44 (40.91%) | 35/44 (79.55%) |
| Mixed requests | 1/10 | 9/10 |
| Diagnostics | 18/45 | 33/45 |
| Cases with duplicate successful-call receipts | 62 | 11 |
| Mean tool calls per case | 1.80 | 1.44 |
| Mean whole-case latency | 1,580.57 ms | 1,830.27 ms |
| Tool-selection proxy | 92.78% | 98.97% |
| Argument-correctness proxy | 99.48% | 98.45% |
| Reasoning proxy | 85.57% | 93.30% |
| Unsupported-claim proxy, lower is better | 0.52% (1/194 flagged) | 4.64% (9/194 flagged) |

The paired outcomes were 106 cases passed by both models, 63 passed only by Qwen, 7 passed only by HANNI, and 18 failed by both. The exact completion-rate difference is 28.87 percentage points, computed from unrounded counts. All original scores were retained.

HANNI was about 250 ms faster per case in these runs. This is a single-run whole-case mean, includes policy-blocked cases, and excludes model startup. The two runs were sequential, so this does not establish a repeatable speed advantage under controlled load.

| Case family | HANNI passes | Qwen passes |
|---|---:|---:|
| Applications / Spotify | 10/15 | 14/15 |
| Calendar | 15/20 | 18/20 |
| Conversation | 10/10 | 10/10 |
| Diagnostics | 18/45 | 33/45 |
| Direct system | 14/20 | 20/20 |
| Email | 0/4 | 4/4 |
| Files / search | 9/10 | 10/10 |
| Google | 18/40 | 31/40 |
| HANNI / model | 8/10 | 10/10 |
| Mixed domain | 1/10 | 9/10 |
| Safety | 10/10 | 10/10 |

## Why keep Qwen, and what still needs work

HANNI's main deficits are repetition and incomplete requests. Its 62 duplicate-call cases and 1/10 mixed-request result make it a weaker default for an assistant expected to complete several related tasks. The original export also needs a legitimate metadata fix before deployment. The preceding [HANNI review](HANNI_4B_REVIEW_2026-10-09.md) documents five ranked weaknesses and representative transcripts.

Qwen has a material evidence-grounding weakness despite its higher completion rate. Its unsupported-claim proxy was worse, and inspection confirmed substantive examples: `DIAG-029` called Power Saver the direct cause despite a fixture explicitly marking causality as unverified; `DIAG-042` reported used GPU memory exceeding the supplied total; and `APP-006` claimed a track had changed when the tool only confirmed a media key was sent. These findings should remain visible when improving Qwen.

The claim checker is heuristic. For example, `DIAG-040` matches a malware expression while describing the fixture's legitimate Windows Anti-Malware process; that flag alone does not prove a malware hallucination. No flags or scores were removed or rewritten. The proxy is not a measured prevalence of unsupported claims on real user requests.

Neither model met a 95% strict completion target on this suite. Keeping Qwen is the better choice between these two measured candidates, while fixing grounding and stopping behavior remains necessary. HANNI should be reconsidered after its export, duplicate calls, and mixed-request coverage improve, with separate validation on fresh cases. This development comparison does not revise the prior V3 goal-planning failure or establish that HANNI can plan and execute persistent workflows.

## Comparability and limits

The original comparator accepted all 13 required protocol fields: corpus, routed menus, prompt, evaluator, owner timezone, round limit, scenario count, context length, token limit, call ceiling, tool temperature, final temperature, and top-p. The source/configuration projection covers 180 files and matches across both runs. Both recorded source projections were unchanged before and after execution; both artifact validations passed with 194 completed cases.

Both runs used the same installed llama.cpp build and observed Vulkan1 NVIDIA RTX 5060 Laptop GPU placement, a 16,384-token context, q8 KV cache, one parallel slot, disabled thinking, up to 768 generated tokens, three tool rounds, and an eight-call ceiling. Tool temperature was 0; final temperature was 0.35 with top-p 0.9. Peak VRAM and first-token latency were not measured.

This is a correlated, curated development suite, not an independent holdout or a population estimate of real task accuracy. Training overlap is unknown. Synthetic receipts exercise tool selection, arguments, sequencing, and answers; they do not demonstrate real provider reliability. Seventeen cases in each run were blocked by policy before model inference, so their passing results do not demonstrate independent model refusal behavior. Lexical grading can reject semantically valid answers or flag benign wording. There was one completed run per model, without randomized timing repetitions. No production backend changes were made for this comparison.

## Evidence

The aggregate comparison is committed below. Detailed transcripts, runtime metadata, and model files remain in ignored local storage; those evidence links require this workspace.

- [Aggregate comparison and paired counts](HANNI_VS_QWEN_4B_2026-10-09.json)
- [Unmodified repository comparator output](../../data/benchmarks/2026-10-09-4b-main-model-decision/original-comparison.txt)
- [HANNI original results](../../data/benchmarks/2026-10-09-4b-review-fixed-metadata/results.json) and [run metadata](../../data/benchmarks/2026-10-09-4b-review-fixed-metadata/run-metadata.json)
- [Qwen original results](../../data/benchmarks/2026-10-09-qwen-4b-comparison/results.json) and [run metadata](../../data/benchmarks/2026-10-09-qwen-4b-comparison/run-metadata.json)
- [Candidate metadata correction and tensor-payload checks](../../data/benchmarks/2026-10-09-4b-export-check/metadata-correction.json)
- [Original export failure metadata](../../data/benchmarks/2026-10-09-4b-review/run-metadata.json)

| Artifact | SHA-256 |
|---|---|
| Original HANNI GGUF | `4a7b0aa6a874cad28c0870ea11b5c0cad82330dd9ffbd7cb0327bee8a58a66f9` |
| HANNI metadata-corrected GGUF | `df56ee88d7e8e0b5c39363208e9e2dcc1c0388f9ff4ac3a3f076367a0c5eaa27` |
| Original and corrected HANNI tensor payload | `15a750fd4941fae94fb8cbc36e6a442c88e70ab9c9bc8e35a3ab4333dedd79dd` |
| Qwen GGUF | `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c` |
| HANNI results JSON | `a08ec2944741abc5cfa0e5af684e4cfa9a40aff6a7d8b2a5b7d2a58546bf3332` |
| Qwen results JSON | `728586eb32da5360efe565c44a49b81fe1053f865b8e0e0632664c41d9b4848a` |
| Shared 180-file source/configuration projection | `9aa4f63399f457120a64be536bb8eea7c4a86686b2ff72c5e91c10a8f3afed45` |

The HANNI run completed at 19:39:51 UTC and the Qwen run at 19:55:08 UTC on 2026-10-09. Their repository commits differ only by the intervening committed review documentation; the benchmark's source/configuration hashes match. Process ownership and shutdown are recorded in each run's metadata.
