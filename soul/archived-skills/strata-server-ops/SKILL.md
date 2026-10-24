---
name: strata-server-ops
description: Use when benchmarking or tuning the Wonyoung Strata server.
version: 1.0.0
license: MIT
author: HANNI
metadata:
  hermes:
    tags: [strata, gpu, benchmark, inference, amd]
    related_skills: [k2-horizon-gpu-bench, fastmcp-local-apps]
---

# Strata server ops (Wonyoung = HANNI's brain)

## When to Use
Any benchmark, speed comparison, config/tuning-table change, restart, or outage diagnosis of the Strata inference server on wonyoung — including when that server is the one answering you.

## What this is
The Strata engine on wonyoung (LAN <lan-ip> since the 2026-10-18 board swap — old .177 is dead; Tailscale <tailnet-ip> unchanged) serves HANNI's own model on :8080 with **one slot** — every benchmark request competes with your own inference, and every restart is self-surgery. Announce downtime before restarting. Hardware as of 2026-10-18: R9700 + Ryzen 9 3900X (temp body) + T-Force 512GB root (cloned; KIOXIA fallback drive still installed). Baseline after full upgrade: prefill 218.6, decode 82.6, wall 3.0s (bench.py). Prefill tracks PCIe gen exactly (Gen3→Gen4 doubled it).

## Key facts
- Config: `~/Strata/strata-iq3_s.json` (wonyoung); engine `~/Strata/engine/strata`; log `~/Strata/strata-iq3_s.log`; model ~78GB IQ3_S in `~/Strata-data/` (spills to system RAM; expert cache auto-fills VRAM minus `--vram-reserve-mib`).
- Supervised by systemd user unit `strata-iq3s.service` (Restart=always). Restart ONLY via: `export XDG_RUNTIME_DIR=/run/user/1000; systemctl --user restart strata-iq3s`. Never pkill the engine, never write self-resurrection scripts — the unit guarantees the comeback.
- After any restart port 8080 refuses connections for ~4-5 min while the working set loads. Poll `curl http://<tailnet-ip>:8080/health` until `"ok"`. Hermes provider retries exhaust inside that window, so failed turns mid-reload are expected — warn the user first.
- API key: `HERMES_CUSTOM_OPENAI_COMPATIBLE_CUSTOM_OPENAI_API_KEY` in `~/.hanni/.env`. `/v1/chat/completions` responses carry a `timings` object: `prompt_per_second`, `predicted_per_second`, `draft_n`/`draft_n_accepted` — use those, not wall time, for speed claims.
- Thinking is governed server-side by `reasoning_budget_tokens` in the config (per-request override with the same key in the body). The `enable_thinking` request flag is decorative on this build — the model emits a short think block either way, so thinking costs on trivial prompts are ~0; measure think length via `reasoning_content` before claiming a thinking tax.

## Benchmark procedure
1. Run `scripts/bench.py` (5 sequential runs, ~535-token prompt, 150 max tokens, 8s cooldowns, temp 0). It prints per-run prefill/decode tok/s + draft acceptance and an aggregate.
2. Compare only quiet batches: your own conversation turns queue on the same slot and inflate wall time (and skew decode). If wall times jump to tens of seconds, the batch is contaminated — re-run or note it, never mix contaminated and clean numbers in one table.
3. Prefill and decode both warm up within a batch (climb run 1→5) and across restarts; compare like-for-like warmup positions, and batch order matters when A/B-ing configs.
4. To bench small GGUF models on OTHER fleet hosts (llama.cpp CPU-only, thin-client ISA pitfalls, measured speed reference points): see `references/llama-cpp-small-model-deployment.md`.

## hipBLASLt tuning tables (prefill GEMM)
- `env.STRATA_HIPBLASLT_TUNING` points at a table in `~/Strata/tools/hip/`. The runtime guard requires an EXACT hipBLASLt version match: check the log line `hipBLASLt version mismatch: file=X runtime=Y` to learn the runtime version (was 100200 on ROCm 7.10-alpha).
- A table whose version matches is used even if its arch label differs (gfx1100-100200 table runs fine on gfx1201 and is worth ~+25% prefill). A REJECTED table is worse than no table: it forces the slow hipBLASEx fallback path.
- After any change, verify by log line: `tuning enabled` = accepted, `version mismatch ... using hipBLASEx` = rejected → revert.
- To get a native table for a new GPU+ROCm combo (VERIFIED workflow): `cmake --build build-hip --target tune_hipblaslt`; extract unique shapes from the current working table into JSON objects `{"dtype":"bf16","N":n,"K":k,"ldy":l}` (the table rows are `dtype N K ldy T solution_id`); run via `systemd-run --user --unit=strata-tune --collect --property=WorkingDirectory=/home/user/Strata --setenv=LD_LIBRARY_PATH=<devel lib>:<gfx120X lib> .../build-hip/tune_hipblaslt --shapes-file <abs> --tuning-out tools/hip/gfx1201-custom-100200.txt` (systemd-run does NOT inherit cwd — absolute paths or WorkingDirectory property required). Takes ~60s, safe to run live alongside the server. Result accepted as `tuning enabled (30 rows, gfx1201, version 100200)`.
- PITFALL: a correct native table gave NO measurable prefill gain over the gfx1100 table — prefill is dominated by expert-cache warmth (PCIe streaming), not GEMM kernel choice. Prefill comparisons are only valid at equal cache warmth; a fresh restart's first batches plateau ~105-125 while a 20-min-warm server hits 147. Don't A/B tables across restarts without warming first.
- `setup.sh`/`update.sh` REWRITE `strata-iq3_s.json` (lib_dirs, env) — after running either, re-verify the env tuning var and lib_dirs survived.

## SSH-to-wonyoung pitfalls (cost real time)
- `pkill -f PAT` / `pgrep -f PAT` inside a remote command self-match the remote shell's own cmdline (the pattern string is in it) — kill your ssh session (exit 255) or inflate counts. Use the bracket trick: `pkill -f '[s]erve/server.py'`.
- Quote the remote command in single quotes; for anything with Python string literals use `ssh host 'python3 - <<PY ... PY'` heredoc. Nested double quotes through ssh+eval mangle silently.
- `sudo -A` needs `SUDO_ASKPASS=<helper>` (NOT `SSH_ASKPASS`); wonyoung sudoers also allows NOPASSWD `docker start|stop|restart hanni-strata-iq3s` — but that container is stale, the real server is the systemd unit.
- After a host REBUILD, the Tailscale IP may be intercepted by Tailscale SSH demanding a browser check (`login.tailscale.com/a/...`, ssh hangs) — don't debug keys; fall back to the LAN IP.
- A motherboard swap changes the MAC → new DHCP lease → the LAN IP moves (wonyoung .177→.187, yunjin .176→.177). On `No route to host` for a known host, try hostname@ adjacent addresses in the usual range, then update the fleet MCP HOSTS map and memory with the new IP.

## Not-yet-tried levers (flag, don't fire blind)
- HUGE PAGES: DONE 2026-10-17, VERIFIED WIN. `vm.nr_hugepages=23983` (46.8GiB) reserved while the server is STOPPED (fragmentation blocks it while running); persisted in `/etc/sysctl.d/99-strata-hugepages.conf`. Log confirmation: `expert arena: ... hugetlb 2 MB pages` (the `MAP_HUGETLB unavailable` line means it silently fell back). Effect: decode 50→71 tok/s avg (+40%, no cold-start dip); prefill unchanged (~106). The `WARNING: expert arena needs 46.84 GiB but 26.78 GiB available` at load is benign when swap stays idle — verify `swapon --show` after boot.
- PITFALL: `systemd-run --user ... bash -xe <<HEREDOC` does NOT forward stdin to the unit — the script runs empty and exits 0 looking successful. Always write the script to a file first, then systemd-run the file.
- sudo on wonyoung works via `SUDO_ASKPASS=/home/user/.local/bin/hanni-askpass sudo -A` (helper scp'd there; must be set in the REMOTE shell, local export doesn't cross ssh).
- SPEC DEPTH: A/B'd 2026-10-17 on the R9700. `--spec 4` decode 71.2 avg (accept ~78%), `--spec 5` **78.8** (accept ~67%, WINNER, locked in), `--spec 6` 76.6 then 71.0 (loses — rejected-tail cost). Each measured batch climbs run1→run4-5 (~65→80) even when warm; compare batch averages, never single runs. `--spec-min-p 0.5` untouched.
