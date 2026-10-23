---
name: local-llama-cpp-vulkan
version: 1.0.0
author: Hermes Agent
license: MIT
description: "Build/run llama.cpp Vulkan on AMD for local benchmarks."
metadata:
  hermes:
    tags: [llama.cpp, vulkan, gpu, benchmark, amd]
    related_skills: [hanni-routing-evals, hermes-host-migration]
---

# llama.cpp Vulkan on AMD (local bench work)

## When to Use
Building llama.cpp with Vulkan for local GGUF/vision benchmarks on the fleet GPUs (yunjin RX 6600XT 8GB + Intel Arc A380 6GB, athena, Wonyoung), or picking a tag that supports a given model family. The recipe is vendor-agnostic — verified on AMD (NAVI23) and Intel (DG2).

## Tag selection (do this before building)
- Find the first tag containing a feature: `git fetch --tags --depth 1 origin` (fresh clones are shallow and show ~no tags), then `git log --all --oneline --grep='<feature>' -i` and `git tag --contains <sha> --sort=v:refname | grep '^b' | head -1`. Verified: Qwen3-VL support first lands in **b6887**; Qwen2.5-VL works on much older tags.
- Recent master Vulkan shaders may need a glslang too new for distro packages (OCP FP4/e2m1 features — `GL_EXT_float_e2m1` unsupported by Ubuntu glslang 16.2). Prefer the OLDEST tag that has the needed feature — b6887 builds clean where master failed.
- If the oldest feature-tag STILL fails shader compile, find the WINDOW: grep the offending shader feature scoped to the vulkan dir (`git log --all --oneline --grep='<feature>' -i -- ggml/src/ggml-vulkan` → `git tag --contains`), then build the oldest feature-tag that PREDATES the first tag containing the bad shader (e.g. MiniCPM5 from b9354, OCP-FP4 shaders from b9992 → build b9354).

## Build recipe (verified on Ubuntu, RX 6600 XT)
```bash
PATH=$HOME/bin:$PATH cmake -B build-<tag> -DGGML_VULKAN=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release
PATH=$HOME/bin:$PATH cmake --build build-<tag> -j6
```
- `-DLLAMA_CURL=OFF` when libcurl-dev is absent (b6887's common/ hard-requires CURL otherwise configure dies).
- Distro glslang has no `glslc`: keep the `~/bin/glslc` shim (wraps glslangValidator; adds `-l`, `-P#extension GL_GOOGLE_include_directive : enable`, `-I` dirs, `-MF` depfile passthrough). Older tags compile their shaders through it fine.

## Multi-slot serving benchmarks (6-agent fleet configs)
- **Always run `llama-server --list-devices` and pass `-dev <exact name>`**: Vulkan0 is often the CPU's iGPU (e.g. Raphael on a 7800X3D) — a bench without an explicit device silently runs on the APU and reports garbage numbers.
- **KV budget before promising Q8 KV**: total_tokens × kv_bytes_per_token + weights must fit VRAM. Overshooting KV on RDNA4 doesn't OOM cleanly — it crashes the driver with `vk::Queue::submit: ErrorDeviceLost` and may need a GPU reset/reboot. Halve with `-ctk q4_0 -ctv q4_0` and label it a different config.
- **Harness rules that saved hours**: check server liveness (`p.poll()`) before every batch and mark the config FATAL instead of firing requests at a dead server; cap socket timeouts ~300s (a dead-socket read at 1200s turns one crash into a multi-hour hang); size long-context prompts by calibrating with the server's `/tokenize` endpoint — word-count estimates overshoot ~4× for token-heavy filler and every request 400s.
- Use **`llama-bench`** (ships with the build) for pp/tg preliminaries — hand-parsed `/completion` timings keys differ across versions and waste cycles.
- AMD VRAM sampling for peak-VRAM metrics: `/sys/class/drm/card*/device/mem_info_vram_used` (the `/device/` segment is required; the glob without it silently records 0).
- Non-llama.cpp servers (e.g. Strata) may expose only `/v1/chat/completions` and `/v1/messages` — probe `/health` and one chat call before assuming `/v1/completions` exists; benchmark through chat completions with `usage.completion_tokens`.

## CUDA builds on the same boxes
When a box has both AMD (Vulkan) and NVIDIA cards: `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=<sm> -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc` (nvcc often isn't on PATH). CUDA 12.x rejects gcc≥15 at compiler-Id time — pin `-DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14` (and C/CXX compilers) when the distro default is newer. Verify which backend a running server uses by mapping libs in `/proc/<pid>/maps` (libcuda vs hsa/rocblas) — beats guessing from process names.

## GPU visibility gate
`llama-server --list-devices` printing only "Available devices:" (empty) = no `/dev/dri/renderD12*` access (render group missing or session predates group add — see hermes-host-migration reboot rule). Don't debug the build; check `getent group render` + `id` first.

## Serving notes
- Vision: `-m <model>.gguf --mmproj <mmproj-f16.gguf> -ngl 99 -c 8192 -fa on`. PITFALL: the `--mmap` flag does NOT exist in older tags (b6887 dies with `error: invalid argument: --mmap`, which the bench harness reports as a bogus 'load timeout'); mmap is the default there — omit the flag entirely. Newer master builds do accept `--mmap`. OpenAI-compatible `/v1/chat/completions` accepts `image_url` data-URI content parts.
- 8 GB VRAM fits Qwen2.5-VL-3B/7B and Qwen3-VL-4B Q4 + f16 mmproj; run one server at a time for fair benches.

## Wiring into Hermes as the agent's own eyes (verified end-to-end)
1. systemd user unit (`hanni-vision.service`) running llama-server with `--mmproj --alias <name>` on a fixed port (8277), linger keeps it up.
2. `hermes config set auxiliary.vision.base_url http://127.0.0.1:<port>/v1` + `auxiliary.vision.model <alias>` + `auxiliary.vision.timeout 120` + **`auxiliary.vision.api_key local`** — PITFALL: without api_key the aux client build fails and vision silently falls back to the MAIN model endpoint (error: "this server was started without the vision encoder"). llama-server ignores the key value.
3. No gateway restart needed for the config (read per call); the unit + config take effect immediately.

## Serving as Hermes' vision backend (gives a text-only main model eyes)
1. Permanent server as a systemd USER unit (`~/.config/systemd/user/hanni-vision.service`): `llama-server -m <vl>.gguf --mmproj <mmproj-f16.gguf> --host 127.0.0.1 --port 8277 -ngl 99 -c 8192 -fa on --alias <name>`, `Restart=on-failure`, `WantedBy=default.target`; `systemctl --user enable --now hanni-vision`.
2. Point Hermes at it: `hermes config set auxiliary.vision.base_url http://127.0.0.1:8277/v1`, `.model <alias>`, `.timeout 120`. When `base_url` is set Hermes ignores provider and calls the endpoint directly (OpenAI-compatible `/v1/chat/completions` with `image_url` data-URI parts); configuring any explicit auxiliary.vision backend also forces the text-description path even for vision-capable main models.
3. PITFALL: the gateway caches vision routing at startup — `vision_analyze` keeps hitting the OLD endpoint after the config change. The restart must come from the user (`hermes gateway restart`); never restart the gateway you are running inside.
4. Verify end-to-end with a real `vision_analyze` call, not just `/health`.

## Acuity-probe harness pitfalls (false MISSes)
- Probe `max_tokens` ~300 truncates dense transcriptions mid-answer and the missing tokens look like vision failures — use ~1200 for transcription probes and check `usage.completion_tokens` before believing a miss.
- Normalize BOTH sides before substring checks (Unicode ellipsis vs `...`, whitespace collapse): the model re-renders glyphs differently than the source image contains them.
- A 'load timeout' in a bench harness is often an invalid-argument death at startup — read the server log first, don't tune timeouts.
