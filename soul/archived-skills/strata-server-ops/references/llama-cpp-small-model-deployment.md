# Deploying/benchmarking small llama.cpp models on fleet hosts

Use when running or benching a GGUF model on a fleet box (thin clients, laptops, non-GPU hosts).

## Procedure
1. Download the GGUF on Yunjin (fast link), rsync to target — verify with `md5sum` on both sides after transfer.
2. Check the llama.cpp version supports the model architecture: a checkout older than the model's release fails with the bare `failed to load model` and no detail. `git clone --depth 1 https://github.com/ggml-org/llama.cpp` + build on Yunjin, confirm the model loads there BEFORE shipping to the target.
3. CPU-only bench: `llama-bench --model X.gguf -ngl 0 -t <cores> -p 512 -n 128`. Run long jobs via `systemd-run --user --unit=NAME --collect script.sh` (write the script to a file first — systemd-run does not forward heredoc stdin; ssh timeouts kill foreground benches).
4. Expect 10-30 min builds on thin-client CPUs; poll `systemctl --user is-active <unit>` + the log file, not the ssh session.

## CPU-ISA pitfalls (illegal instruction crashes)
- Probe the target first: `grep -m1 flags /proc/cpuinfo`. Old thin clients (Pentium Silver J5005 / Gemini Lake: SSE4.2 only, no AVX/FMA/F16C/BMI) reject binaries built `-march=native` on modern CPUs AND current llama.cpp `GGML_NATIVE=OFF` baseline builds — llama.cpp's x86-64 floor has risen past these chips.
- For no-AVX2 hosts, build natively on the target (needs `cmake` — install via `SUDO_ASKPASS=<helper> sudo -A apt-get install -y cmake`).
- llama.cpp ships its own `.so`s: rsync the whole `bin/` (or `build/bin/`) dir and set `LD_LIBRARY_PATH` to it.

## Measured reference points (MiniCPM5-2B Q4_K_M, 2.52B)
- Pentium Silver J5005 (Wyse 5070 thin client, CPU-only): pp512 2.7 tok/s, tg128 2.0 tok/s — chat-slideshow speed, not an agent.
- Ryzen 7 5700G CPU-only, 4 threads: tg ~42 tok/s — modern laptop-class CPUs are ~20x thin clients.
- Rule for tier selection: micro-benchmark the host (30s llama-bench) rather than inferring from RAM/GPU specs; sub-3-tok/s decode = chat-only mode regardless of model tier.
