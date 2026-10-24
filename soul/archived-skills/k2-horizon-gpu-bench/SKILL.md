---
name: k2-horizon-gpu-bench
description: "Use when benching GPUs on Athena (P6000 vs RX 9060 XT)."
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [benchmark, llama.cpp, vllm, rocm, cuda, athena]
    related: [hermes-fleet-deployment]
---

# K2 Horizon GPU bench on Athena (P6000 CUDA vs RX 9060 XT ROCm)

## Harness (already on Athena)
- `~/k2-bench/bench_k2.py <gguf> <cuda|vulkan|hip> <ctx_per_req> [slots] --cache q8_0|q4_0` — one server per config, 3 batches × (typical ~350-tok-out, long ~80%-of-ctx prompt), reports TTFT / gen t/s per req / agg t/s.
- llama.cpp builds: `~/HANNI_BENCH_LINUX/llama.cpp/build-{cuda,vulkan,hip}`. HIP build: `cmake -B build-hip -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1200 -DCMAKE_PREFIX_PATH=/usr` against Ubuntu rocm-dev 7.1 (installs to /usr, not /opt/rocm). RX 9060 XT reports as **gfx1200**.
- Run long benches with `systemd-run --user --collect --unit=NAME bash -c '...'` — Ubuntu kills nohup'd processes on ssh disconnect (KillUserProcesses).
- Port 8310 = bench, 8320 = vllm, **8120 = fleet endpoint** (4B Vulkan `-dev Vulkan1` → runs on the **P6000**, NOT the 9060 XT; Vulkan1 = NVIDIA ICD there). Kill/restore it around P6000 benches or the bench OOMs on the leftover ~18GB.

## VRAM math first (K2-Horizon-7B: 36 layers, 8 KV heads, head_dim 128)
KV = 2×36×8×128 = 73,728 B/token q8_0 (144KB f16, 36KB q4_0). 64k slot q8_0 = 4.72GB.
- 3×64k q8_0 + Q4 weights ≈ 20GB → fits P6000 24GB, **does NOT fit 9060 XT 16GB** (llama.cpp dies: `cudaMalloc failed: out of memory` on the 14.7GB KV buffer). Fallbacks: 64k×2 q8_0, 32k×3 q8_0, or 64k×3 q4_0 (q4_0 long-phase gen collapses to ~0.5 t/s — eviction thrash, not usable).

## vLLM verdicts (Oct 2026, both FAILED on this box — don't re-litigate without new drivers)
- **P6000 (sm_61)**: current vLLM/torch CUDA wheels have no sm_61 kernels → `CUDA error: no kernel image is available` on the first `torch.zeros`. Last Pascal-era vLLM (0.6.x V0) needs py≤3.12 + community wheels. Dead end.
- **9060 XT (gfx1200)**: AMD RDNA wheels exist (`rocm.frameworks.amd.com/whl-multi-arch/vllm-rdna/`, cp314) but their torch+rocm7.14 userspace needs the **7.14 amdgpu-dkms kernel driver**; Ubuntu 26.04 ships 7.1.9 → `kpack_load_code_object failed` / `hipErrorInvalidImage`. Would need an AMD-repo DKMS swap on a production box — ask first.
- Wheel-fetch gotchas: AMD wheel CDN 403s pip — download with curl using a cookie from the listing page + browser UA + referer, then `pip install <local.whl>`. Rename to the real wheel filename (pip rejects arbitrary names). flash-attn dep: install the `py3-none-any` shim wheel from the same index first; `amd-quark>=0.8.99` dep unsatisfiable on py3.14 → use `--no-deps` (deps already satisfied by a prior `pip install vllm`).
- vLLM cannot run GGUF — needed the HF bf16 repo (17GB, `IFM/K2-Horizon-7B`); the local dir must include `configuration_k2_horizon.py` + `modeling_k2_horizon.py` or vLLM errors "does not appear to have a file named configuration_k2_horizon.py" even though K2HorizonForCausalLM is natively registered.

## Strata server bench (any host, no harness)
- Strata/llama.cpp `/v1/chat/completions` returns a `timings` object beside `usage`: `prompt_per_second` (prefill), `predicted_per_second` (decode), `draft_n`/`draft_n_accepted` (spec-decode acceptance). One curl gives full prefill/decode numbers — no bench harness needed for quick before/after comparisons (e.g. GPU swaps).
- Benching the server that SERVES you: it is your only slot — run sequentially, ~500-tok prompts, capped generation, ~8s sleep between runs; concurrent or long runs queue you out of your own inference mid-turn.
- Warmup dominates: prefill and decode climb across runs (a cold first probe can read 3× slow). Compare steady-state tails, not batch averages, and never A/B two configs in fixed order — the second batch inherits the warm engine and wins for free; alternate batch order or compare last-N runs.
- `enable_thinking` is decorative on Strata builds (the chat template emits reasoning either way); the real governor is the server config's `reasoning_budget_tokens` (0 = unlimited), overridable per-request in the request body.

## Results snapshot (Q4_K_M, -fa on, q8_0 KV, 3 concurrent)
- 32k×3 head-to-head: 9060XT HIP wins — TTFT ~1.9s vs ~2.9s, long-prefill TTFT 37-76s vs 76-177s, gen 33-36 vs 24-38 t/s.
- 64k: P6000 3×64k TTFT 237-466s gen 6.2; 9060XT 2×64k TTFT 115-128s gen 8.8.
- Client note: bench_k2 run_one socket timeout 300s = per-recv; >300s silent prefills show as 'timed out' failures, not server faults.
