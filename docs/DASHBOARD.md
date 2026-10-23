# Local dashboard and Phi-4

From the repository folder, run:

```powershell
.\START_HANNI.cmd
```

Requires Windows, Python 3.12+, and llama.cpp on PATH. If needed, install llama.cpp
with `winget install --id ggml.llamacpp --source winget`, then open a new terminal.
The launcher creates the virtual environment, installs Python/speech/vision dependencies,
opens http://127.0.0.1:8765, starts the configured Phi-4 server, waits for readiness,
and runs the existing `hanni attend` voice session. If the dashboard port is
occupied, it selects a free loopback port and prints/opens that URL instead.
First use downloads uncached
GGUF and Whisper weights; subsequent inference is local. No account is required.

Keep the terminal open: existing tool confirmations appear there. Say “Hanni” to
engage, “that's all” to disengage, or “Hanni, stop everything” to trip the existing
persisted emergency stop. **Stop HANNI** in the Safety State panel or Ctrl+C
stops the dashboard session and its owned model process after the current response
finishes. Closing the browser alone does not stop the assistant. A reused model
server remains running. Vision remains
on demand through the separate configured vision model; run
`.\scripts\start_vision.ps1` when visual understanding is needed.

```powershell
# Fast subsequent starts after dependencies are installed:
.\START_HANNI.cmd -SkipInstall
# Hardware dashboard only: no microphone or model process started:
.\START_HANNI.cmd -SkipInstall -DashboardOnly
# Existing keyboard session with dashboard and Phi-4:
.\START_HANNI.cmd -SkipInstall -Text
# Reuse a server you have verified serves Phi-4 on the configured endpoint:
.\START_HANNI.cmd -SkipInstall -ReuseModel
# Alternative port / microphone:
.\scripts\start_dashboard.ps1 -SkipInstall -Port 8766 -Device 1
# Reuse already downloaded weights without copying them into the repository:
.\START_HANNI.cmd -SkipInstall -ModelFile 'D:\models\phi-4-Q4_K_S.gguf'
```

The launcher refuses an occupied model port by default. `-ReuseModel` explicitly
opts into an existing server, checks its health, and leaves it running on exit;
health alone does not verify loaded weights. It never kills unrelated servers.
Model loading gets a 15-minute deadline. Inspect `data/dashboard-model.log` for
download/GPU failures. Python entry point `hanni-dashboard --startup-timeout 1800`
allows a longer first download. Use `--no-browser` for headless monitoring.
`--model-file` or the optional `HANNI_MODEL_FILE` environment variable selects
existing weights; the filename must match the configured model. Keep personal
paths in your local environment or git-ignored `.env`, not tracked YAML.
Run from the source checkout, or provide `--config-dir` and `--data-dir` to the
Python entry point. The wheel contains the web assets and benchmark, while the
source archive contains editable runtime configuration and Windows scripts.

## Why Phi-4

The supplied `benchmark_scores.csv` is preserved byte-for-byte at
`src/hanni/dashboard/benchmark_scores.csv`. Its text fields are data, not
instructions. No models were evaluated anew to produce these scores.

| Supplied Phi-4 14B Q4_K_S result | Value |
| --- | --- |
| Strict pass | 170/300 (56.7%) |
| Partial | 78/300 (26.0%) |
| Fail | 52/300 (17.3%) |
| Pass or partial | 82.7% |
| Effective correctness (pass + half partial credit) | 69.7% |
| Completed / timeouts | 300/300 / 0 |
| Median / p90 first token | 0.1239 s / 0.1922 s |
| Median total response | 3.6357 s |
| Estimated throughput | 40.87 tokens/s |

Phi-4 has the highest reported effective correctness, slightly above Qwen3 32B
(69.5%), with no timeouts. Qwen3 8B is faster, and other models have higher strict
pass rates. This is a tradeoff based on the supplied local evaluation, not a claim
of universal superiority. Mistral's correctness fields are blank: the UI keeps
them null, displays an em dash, and places missing scores last when sorting.
Benchmark timings are historical and are not displayed as live inference speed.

The Supervisor now selects `bartowski/phi-4-GGUF:Q4_K_S`; its registry ID and API
alias remain `supervisor`. The existing assistant launcher uses this default
instead of overriding it with Qwen3.8. Experimental models remain available.
The supervisor sets `jinja_enabled: false`, which both model launchers translate
to `--no-jinja`. On this installed llama.cpp build, Phi-4's Jinja path returned
Markdown-fenced decisions despite `response_format`; the built-in template
returned grammar-constrained JSON and passed the existing strict turn parser.
JSON parsing, schema validation and tool permission checks remain strict.
Other configured models retain their prior template behavior. See the
[llama.cpp server options](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
for the template switch.
The [quantization publisher's model card](https://huggingface.co/bartowski/phi-4-GGUF)
lists `phi-4-Q4_K_S.gguf` at approximately 8.44 GB before runtime/KV allocations.
The portable default keeps 8K context and 24 GPU layers for partial offload on
8 GB cards. On 16 GB GPUs, tune `gpu_layers` to 99 in `config/models.yaml` after
checking available memory. Hardware/offload differences affect the supplied speeds.

## Telemetry and voice

CPU/RAM, system-drive space, battery, uptime, and network byte rates come from
psutil. GPU readings reuse HANNI's existing nvidia-smi/llama.cpp probes. On AMD,
VRAM is a device-list estimate; utilization and temperature are unavailable and
shown as missing. The first network rate is missing until two samples exist.
Charts contain only observed samples. GPU/model queries run in a background
worker; slow probes may lengthen the nominal two-second sample interval. The UI
labels readings stale when probes fail or the connection is lost.

The orb is decorative geometry driven by the existing microphone's measured RMS
amplitude. “Listening” means microphone frames are arriving, not that a wake word
has been accepted. TTS uses actual local playback state; its visual pulse is not
an output audio waveform. The browser never opens a microphone, captures system
audio, transcribes speech, or synthesizes a replacement voice. Pause Motion and
the OS reduced-motion preference stop decorative motion while readings update.

Observers are disabled outside the dashboard launcher. Only the latest normalized
input level, capture time and playback state are retained in memory. Raw audio,
transcripts, screen contents, and prompt text are not stored or returned by the
dashboard. Existing wake/relevance, echo suppression, barge-in, local SAPI voice,
memory privacy, tool permission gates, and persisted Safe Mode are preserved.

## Local HTTP boundary

The server binds only to `127.0.0.1`. It serves a fixed asset allowlist and two
read-only endpoints: `/api/state` and `/api/benchmarks`. Host/Origin checks and
cross-site fetch rejection protect against browser rebinding and foreign pages.
No CORS, remote assets, file browsing, command endpoint, or browser confirmation
bypass is added. Local programs on the same PC can read aggregate telemetry.

## Review and packaging

```powershell
.\.venv\Scripts\python.exe -m pytest -ra
.\.venv\Scripts\python.exe -m build
# Optional browser regression check (installed Microsoft Edge):
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe scripts\check_dashboard_browser.py
.\scripts\export_source.ps1 -OutputPath ..\HANNI_PHI4_DASHBOARD_SOURCE.zip
```

The exporter refuses to overwrite an existing output and excludes secrets,
environments, runtime data, model weights and perception artifacts. It now includes
the dashboard assets, benchmark CSV, launcher, license, contributor/security docs,
and package manifest. Windows CI runs the tests and builds distributions. Add your
real GitHub repository URL to package metadata when you choose an owner/name.
No repository was published or pushed as part of this change.


## Three-model update

The current launcher also starts Qwen3 8B for admission, and the dashboard exposes
read-only background job history. The named GPU profile now uses RX 9060 XT for
Phi-4 (full offload) and RX 6600 XT for Qwen3 8B. Older partial-offload examples in
this document are historical. See [THREE_MODEL_ROUTING.md](THREE_MODEL_ROUTING.md)
for the current configuration, optional 32B server, queue controls and recovery.
