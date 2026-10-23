# HANNI V3.5 independent synthetic evaluation

This corpus contains 240 original verifier-reviewed synthetic cases and literal oracles across 15 families: extraction, importance, retrieval, project resolution, conflict handling, temporal status, preferences, workflow receipts, privacy, deletion, negative queries, unavailable advisory transport, injection refusal, relationships, and consolidation.

The prospective split is 60 development, 90 validation, and 90 holdout cases, stratified equally per family. Every case and oracle was sealed before candidate scoring. Candidate validation and holdout were run exactly once after source and adapter freeze; failures were retained without tuning. The originally untouched holdout is now published for reproducibility and **cannot be described as an untouched future holdout**. A future release needs a newly independent sealed suite.

Input files under `cases/` are byte-identical to their original seals, verified by `cases/manifest.json`. `candidate-freeze.json` records the production source, original private evaluator hash and adapter mapping. `export-manifest.json` records the public runner hash and portability-only changes. Only literal schema spellings were mapped: `statement` to `fact`, `completed_claim` to `completed`, and `failed_claim` to `failed`; hypothetical/conditional meanings were not generalized to obtain credit. The reviewer is an independent Codex agent, not an external human panel.

The quality arms are distinct:

- **A:** Original memory code frozen at `f19dd00aef5e7b0d2dd318e7eb48c720411e3242`. Five minimal public source modules are preserved in `baseline_f19dd00/` with independent hashes. Newly requested features absent from that implementation are marked NOT AVAILABLE rather than scored as model failures.
- **B:** Candidate deterministic extraction/proposals/status rules and weighted lexical retrieval against the actual candidate store. Importance is an uncalibrated utility heuristic. There is no trained LAYA inference.
- **C:** Genuine LAYA advisory quality is NOT TESTED: no safely configured installed LAYA inference target was available. Controlled opener fault tests establish contracts and fallback behavior only.
- **D:** Candidate project/general context assembly forwarded through the actual `MemoryAwareSession` boundary to a clearly identified controlled input sink. The sink makes no model calls and cannot establish generated factual accuracy.

Run from a repository checkout with its Python dependencies installed:

```powershell
python scripts/eval_memory_intelligence_v35.py --configuration B --split development --output data/v35-reproduction-B-development
python scripts/eval_memory_intelligence_v35.py --configuration D --split validation --output data/v35-reproduction-D-validation
python scripts/eval_memory_intelligence_v35.py --configuration A --split all --output data/v35-reproduction-A
```

Use a new output path for every run. The runner refuses existing directories, validates case hashes and original baseline hashes, creates isolated temporary stores, and does not call real models or external tools. It imports controlled transport helpers from the independent integration tests for unavailable cases. Published holdout reruns are reproductions, not new acceptance results.

`results/` contains sanitized aggregate summaries, including the baseline reporting erratum. Initial baseline critical-write and remote-send fields mistakenly used zero although those paths had not been exercised by the quality suite. That artifact remains preserved; the erratum states NOT MEASURED. Independent HTTP/registry, source-version, deletion, Safe Mode and advisory-consent tests provide separate safety evidence.

Recall@5 measures seeded relevant record IDs, and source grounding checks those IDs and exact live stored content. Neither measures generated-answer correctness. Fixture-plus-operation latency includes SQLite fixture creation; retrieval-boundary latency excludes fixture creation and includes session forwarding in D. UTF-8 bytes and characters are measured directly, while the chars/4 field is only an estimate. Small synthetic samples do not establish population performance or statistical significance. Workflow receipt fixtures explicitly identify controlled verified metadata and are not new live workflow executions.

The final independent review is [HANNI_V3_5_INDEPENDENT_REVIEW.md](../../docs/v35-reviews/HANNI_V3_5_INDEPENDENT_REVIEW.md). Native screenshots, raw model transcripts and owned runtime artifacts remain local and ignored; this export contains no user memory or secrets.

The additional `main-grounding/` directory preserves a separate 12-case prospective actual-Qwen cohort and its original seals. It is not a LAYA evaluation. Its runner requires explicitly supplied matching already-installed Qwen weights and never downloads replacements:

```powershell
python scripts/eval_memory_grounding_v35.py --model-file C:/path/to/Qwen3.5-4B-Q4_K_M.gguf --output data/v35-qwen-grounding-reproduction
```

It starts and closes only its own isolated loopback runtime, disables extraction, registers no tools, and uses fresh original TextSession/MemoryAwareSession instances. It preserves one generation per arm/case without retries. The main cohort A uses original retrieval on a common current-schema store, unlike the five-module schema-v2 A above. Published results include separate literal and semantic scores, real SSE tokens and measured tokenizer differences. Reproductions cannot replace the original once-only failures.
