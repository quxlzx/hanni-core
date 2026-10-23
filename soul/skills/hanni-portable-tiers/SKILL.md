---
name: hanni-portable-tiers
description: "Use for the USB-portable HANNI tier design and benchmarks."
version: 1.0.0
license: MIT
author: HANNI
metadata:
  hermes:
    tags: [hanni-core, llama.cpp, benchmark, portable, models]
    related_skills: [strata-server-ops, local-llama-cpp-vulkan]
---

# HANNI portable USB tiers — measured design (Oct 2026)

## When to Use
Any work on the hanni-core USB-portable project: picking models for tiers, benchmarking candidate hosts, building/shipping llama.cpp binaries, or deciding what runs where.

## Goal
USB stick carries: 29MB soul (memories/skills/SOUL.md from ~/.hanni) + 3 models + llama.cpp binaries. Any host plugs in; a boot-time probe picks the tier. Brain server (Strata, 78GB IQ3_S) stays on Wonyoung-class hardware only.

## Measured MiniCPM5-2B Q4_K_M results (llama-bench -ngl 0 -t 4)
| Host | CPU | pp512 | tg128 | verdict |
|---|---|---|---|---|
| Wonyoung | R9700 (full me runs there) | 218 | 82 | full tier |
| Yunjin | Ryzen 7 5700G | — | 41.9 | 2B comfy, 8B fine |
| jeongyeon | i5-7500T (Kaby Lake, AVX2) | 70.6 | 17.9 | 2B = real agent |
| chaewon/haerin/minju | Pentium Silver J5005 (Wyse 5070) | 2.7 | 2.0 | chat-only slideshow |

Usable-agent floor: ~15 tok/s decode. Thin clients are 9x under it — remote brain over LAN beats local 2B there.

## Arc A380 Vulkan (yunjin, Oct 19)
- MiniCPM5-2B Q4_K_M on Arc A380 (Vulkan, -ngl 99): pp512 **437**, tg128 **25.8** (vs CPU 70.6/17.9).
- llama.cpp master Vulkan build dies on distro glslang: OCP-FP4 shaders need `GL_EXT_float_e2m1` (Ubuntu glslang 16.2 lacks it). Window: MiniCPM5 support starts **b9354**; OCP-FP4 shaders start **b9992** → build b9354 with `-DGGML_VULKAN=ON` + ~/bin/glslc shim, compiles clean.
- llama-bench device flag is `-d`/`--device "Vulkan0"`; llama-server only accepts `--device` (no `-d`). A380 = Vulkan0 on yunjin (6600 XT = Vulkan1, runs vision :8277).
- Standby brains live: yunjin `hanni-2b.service` :8300 (Arc), karina `llama-2b.service` :8300 (CPU, LD_LIBRARY_PATH via /usr/bin/env in ExecStart), jeongyeon `llama-2b.service` :8300 (CPU, `--reasoning-budget 300`).
- 2B reasoning loop fix (VERIFIED): MiniCPM5-2B without a budget ruminates forever (train catch-up problem: 1500 tokens of restating the setup, never solved). With llama-server `--reasoning-budget 300` it solved it correctly (13:30, 270 km) — small models need deadlines, not more smarts. Quirk: budget truncation leaks the think block into `content` and the model still victory-laps; give max_tokens ≥1500.

## Binary compatibility traps (all hit for real)
- llama.cpp built with defaults on a Zen3 host = `-march=native` → SIGILL on older x86-64 (GFNI/VAES). Never ship native builds cross-host.
- Current llama.cpp `GGML_NATIVE=OFF` baseline STILL SIGILLs on Gemini Lake (J5005) — SSE4.2-era CPUs are below its floor. Only a build compiled ON the machine runs there.
- Ship 3 binaries: x86-64-v3, x86-64-v2, plus build-on-first-use fallback (30 min on a J5005, 3 min on a Kaby Lake quad).
- Selector: try v3 → SIGILL? v2 → SIGILL? native build. Then 30s llama-bench micro-bench decides tier by REAL tok/s, not spec-guessing.
- rsync'd llama.cpp bins need LD_LIBRARY_PATH=<bin dir> (own .so files).
- Old llama.cpp checkouts silently fail new models: `failed to load model` with no arch detail = version too old, not corrupt file (verify with md5sum to be sure). MiniCPM5-2B needs llama.cpp ≥ Oct 2026.

## Model picks
- Floor: MiniCPM5-2B (openbmb/MiniCPM5-2B-GGUF Q4_K_M, 1.56GB) — beats Qwen3.5-4B on avg (53.9 vs 51.1); sub-2B models are useless for tool calling (MiniCPM5-1B: 6.3/100, rank 224/224).
- Mid: K2 Horizon 3.7B (fleet-proven).
- Top: Hermes 4 Horizon 8B (Nous agent-tuned).
- Context floors: 32K viable / 64K comfortable / 128K luxury. Tool schemas are the context tax: Hermes pays ~20K tokens of tool defs — HANNI-Core must use tiered toolsets (2B tier ≤4 tools ≈1.5K tokens).

## Standby-brain deployment checklist (repeat on any fleet host)
1. Build every target you will ship — `llama-bench` does NOT pull in `llama-server`; a unit pointing at a missing binary fails 203/EXEC or 127.
2. rsync the WHOLE `bin/` dir, never a single binary — llama-server links its own `.so`s (`libllama-server-impl.so` etc. appear only when that target is built), and a lone binary dies exit 127 with a confusing `env: No such file or directory`.
3. systemd user unit ExecStart must carry the lib path: `ExecStart=/usr/bin/env LD_LIBRARY_PATH=<bin dir> <bin dir>/llama-server -m <gguf> -c 8192 -t 4 -ngl 0 --host 0.0.0.0 --port 8300 --alias hanni-2b` (CPU) or `-ngl 99 --device Vulkan0` (GPU; llama-server has no `-d`).
4. Check `loginctl show-user <host>` on EVERY fleet host before enabling — linger is off on most (jeongyeon was), and without it the service dies at logout. Fix: `sudo loginctl enable-linger <user>` (needs the askpass helper scp'd to that host first).
5. Helper scripts in `~/bin` need `chmod +x` — a missing exec bit fails identically under sudo (os error 13); user-level systemd management needs NO sudo at all.
6. Probe with `max_tokens ≥ 200`: even the 2B tier emits a `reasoning_content` block (150 think-tokens for 12×12) — a 30-token probe returns empty `content` and looks like a broken server when it's just a starved budget.

## Files that make "me" portable (~29MB)
~/.hanni/{config.yaml,.env,state.db,memories/,skills/,cron/} — identical across tiers. SOUL.md ~820 tok, memory ~756 tok are the highest-value tokens in the system.

## HANNI-Core project home (standing decision)
Build on the user's existing repo `<owner>/HANNI` — NEVER scaffold a new agent repo. The React frontend and `src/hanni/` backend skeleton exist; the work is replacing the `src/hanni/hermes/` bridge with a native tool-calling loop pointed at the tier brain. Repo layout, seam audit steps, and the feature-flag migration plan: `references/hanni-core-repo-map.md`.

## Native brain status + bridge API contract (verified end-to-end)
- Branch `hanni-core-native` (pushed): `src/hanni/native/` (loop.py/provider.py/worker.py — drop-in replacement for `hanni.hermes.worker`, same CLI contract, security core reused), `probe.py` tier selector (`decide()` → full/large/small/pocket/none; static floors: full ≥64GB RAM+≥16GB VRAM, large ≥10GB VRAM or ≥16GB RAM, small ≥8GB RAM, pocket ≥5GB; a llama-bench decode measurement OVERRIDES spec-guessing: <8 tok/s none, <15 pocket, <40 small), `scripts/e2e_native_proof.py` (reusable proof harness), `config/models.fleet.yaml` (Wonyoung Strata profile; key via env `HANNI_MODEL_API_KEY`, config via `HANNI_MODEL_CONFIG`). Service flag: `--brain native|hermes`.
- Soul quartet wired into the native worker (verified live): `data/SOUL.md` persona (override via `HANNI_SOUL`) injected ABOVE the operating contract; `skills.py` loads markdown skills with frontmatter `name/description/triggers` from `HANNI_SKILLS_DIR` (copy the Hermes `skills/` dir onto the stick and point at it), keyword-matched under a 6K char budget; `compact.py` folds oldest middle turns into one model-written summary before EVERY model call when over `context_budget_tokens` (tool-call groups never split; extractive fallback if the summary call fails); `memory_inject.py` searches the durable `MemoryStore` at `<root>/memory.sqlite3` (sibling of tasks.sqlite3) with the task prompt and injects as untrusted data with a staleness warning. System prompt is built in worker.py via `build_system_prompt(SYSTEM_PROMPT, load_soul(), match_skills(load_skills(), msg))`.
- Bridge strict contracts (violations surface as bare 400 / ValueError / 409 — read `state.py` before hand-rolling a client): task payload keys EXACTLY `{prompt, windows_tools, origin, context}` with `origin=='hanni'` and `context` a dict; capability spec keys EXACTLY `{name, target, hash, schema, remote}` with target in {windows, karina}; owner approval is TWO-PHASE — `POST /actions/<id> {state:'dispatching'}` (claim) then `{state:'fulfilled', receipt}`; a direct pending→fulfilled is rejected by design (replay protection).
- Completion requires ≥1 fulfilled receipt: a tool-free chat task ends 'failed' by design ("no evidence = unverified proposal") — an E2E test must include a tool call whose action the harness fulfills in the approver role.
- PITFALL: re-typing a redacted/truncated env var name silently expands to empty and yields 401s from the model endpoint after minutes of debugging the wrong layer. Always reference the exact full name in `"${BRACES}"` and assert it is non-empty (`echo ${#VAR}`) before launching.
- PITFALL: to prove a test failure is pre-existing when your changes are already COMMITTED on a branch, `git checkout <base>` and re-run — `git stash` is a no-op post-commit and will deceptively re-test your own branch.
- Linux test env: integration tests that boot the full UI backend need `sudo apt install libportaudio2` (sounddevice). Known pre-existing failures on Linux `main`: two unit tests where the router returns `blocked` for calendar writes the tests expect to execute — that is router behavior to investigate, not an OS-path problem.
