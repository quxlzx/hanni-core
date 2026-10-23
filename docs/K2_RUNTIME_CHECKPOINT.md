# K2 challenger runtime: local GPU bake-off completed

The earlier runtime blocker is resolved for this local checkpoint. The
[official IFM llama.cpp K2 fork](https://github.com/ifm-ai/llama.cpp/tree/model/K2Horizon)
was cloned at `42adf019f76013dac873b5b43950d54d5ab27216` into ignored
`data/k2-runtime-source/`. A CMake-only `BINARY_DIR` change in that ignored
clone shortened the Vulkan shader-generator path for Windows; no model or
inference code was changed. The local GPU server is
`data/k2-runtime-build-vulkan/bin/llama-server.exe`. The publisher's
`K2-Horizon-4B-Q4_K_M.gguf` remains SHA-256
`07773aed93890d4f5d08b421430000d5c8d73cefc74fbdc32e67d820f23207b2`.
The official portable compiler and Vulkan SDK downloads were hash-verified
before use and remain in ignored `data/k2-build-tools/` for reproducibility.

The server loaded the model with a 16,384-token context, q8_0 KV cache,
Flash Attention, `--reasoning off`, and 37/37 layers offloaded to Vulkan3:
AMD Radeon RX 6600 XT. It exposed the local OpenAI-compatible tool-call API.
The [GPU smoke case](../data/k2_smoke_diag_gpu.json) passed before the full
runs. Both completed K2 reports are
[development 150](../evals/llm_tools/results/k2_horizon_37b_dev150_current_router.json)
and [locked holdout 50](../evals/llm_tools/results/k2_horizon_37b_holdout50_current_router.json).
The K2 profile in `config/profiles/k2-bakeoff` did not replace production
Qwen. A 14-case interrupted CPU run remains at
`evals/llm_tools/results/k2_cpu_partial14.json` and is **not** part of either
official score. The server is stopped at this checkpoint.

The [completed comparison](MODEL_BAKEOFF_QWEN_VS_K2.md) retains Qwen as
production: K2 passed 89/150 development and 23/50 holdout tasks, versus
Qwen's 123/150 and 25/50 on the same current router. The server projected
3,970 MiB of device allocation at startup; peak VRAM was not measured.

## Historical pre-build checkpoint

The unavailable-runtime status below records the earlier checkpoint and is
superseded by the completed GPU runs above.

K2 Horizon 3.7B Q4_K_M is now present locally at
`models/K2-Horizon-4B-Q4_K_M.gguf`. It is an ignored model artifact, not a
change to HANNI's production Qwen configuration. Its 3,156,598,144-byte
SHA-256 is
`07773aed93890d4f5d08b421430000d5c8d73cefc74fbdc32e67d820f23207b2`,
matching the publisher's linked digest for the [official GGUF](https://huggingface.co/IFM/K2-Horizon-3.7B-GGUF/tree/main).
The reusable challenger profile is in `config/profiles/k2-bakeoff`; an identical
working copy was used from `data/k2-bakeoff-config` during preflight. It copies
HANNI's four YAML files and changes only the model identity, repository, and
filename. The 150-case audit found zero corpus failures. Both challenger
preflight reports have the same corpus, routed-menu, prompt, and evaluator
hashes as their Qwen counterparts.

The installed llama.cpp build 10901 exits before inference with
`unknown model architecture: 'k2-horizon'`. Its normal `-hf` download path
also failed Windows TLS verification, so the model was fetched separately
over verified HTTPS and then checked against the publisher's SHA-256. Neither
issue was bypassed by disabling certificate checks. The [llama.cpp K2 support
discussion](https://github.com/ggml-org/llama.cpp/discussions/28308) describes
architecture support as pre-release work in an IFM fork; that fork has [no
packaged releases](https://github.com/ifm-ai/llama.cpp/releases). The current
machine has no CMake/compiler toolchain available on PATH. Installing or
building an experimental runtime was not done as part of this checkpoint.

The [preflight record](../evals/llm_tools/results/k2_runtime_preflight.json)
and both `model_unavailable` reports are saved. **There are no K2 task scores.**
To resume the bake-off, use a verified Windows runtime that can load the
`k2-horizon` architecture and expose the same local OpenAI-compatible tool
API. Run the unchanged development and locked holdout corpora on the same
16,384-token context, Q4_K_M quantization, three-round/eight-call limit, and
host. Save both completed reports, then use HANNI's comparison command.
Qwen remains the production model until that evidence exists.

The profile is selected with `hanni eval llm-tools --config-dir
config/profiles/k2-bakeoff --model k2-horizon-3.7b`. For the local model server,
set `HANNI_CONFIG_DIR` to that profile and pass the verified GGUF path to
`python -m hanni.models.serve --model-file`. This is an alternative runtime
configuration; it does not select K2 in `config/models.yaml`.

Separately, `evals/routing/phrase_probe_v2.jsonl` is a new 30-case,
pre-locked **development probe** with fresh owner-style wording. It is not
the original 50-case LLM holdout. The frozen router scored 53.33% strict on
it. Its [baseline report](../evals/routing/results/phrase_probe_v2_baseline.json)
shows fresh mixed-domain and safety-boundary misses, including an "end all
running python processes" request that surfaced `process.list` instead of
being classified as blocked. No real capability was executed; the probe only
routed text. No router patch was made at that checkpoint. The subsequent
[language and safety checkpoint](ROUTING_LANGUAGE_CHECKPOINT_2026_09_24.md)
used the locked development probe for narrow routing changes and reached
93.33% strict without changing the original holdout or production model.
