# HANNI V3.7 deployment

## Existing infrastructure

Use the original HANNI launcher and local model manager. Distributed inference is
an optional analysis dispatch extension to the original WorkflowService. Planning,
tool calls, permission checks, reviewed scopes, completion verification and durable
workflow history stay on the HANNI controller. Remote model responses cannot run
shell commands or obtain tool authority.

The owner-specific roster and worker definitions live under the configured data
directory at `compute/deployment.json`. That ignored file contains private network
addresses. Keep its directory owner-only (Windows ACL or mode 0700) and its file
owner-only (Windows ACL or mode 0600). Do not copy it into source control or public
reports. Missing or invalid configuration disables distributed inference and leaves
named cluster placeholders without targets. Existing sudo credentials remain in
Windows Credential Manager, scoped to the data directory and exact node identity.

## Secure connections

Discovery attempts authenticated LAN SSH first, with strict host-key checking,
short timeouts and bounded attempts. Failed LAN trust/authentication falls back to
the existing Tailscale SSH policy and coordination-verified host keys when available.
An SSH port or an online Tailscale peer alone is insufficient to supply resource
measurements. An optional existing SSH identity can be referenced through
`HANNI_CLUSTER_SSH_IDENTITY`; no private key is stored in deployment JSON.

Inference HTTP travels through a controller-owned SSH forward bound to
`127.0.0.1`, targeting the worker's `127.0.0.1`. HTTP redirects and environment proxy
settings are refused. Servers started by HANNI also bind loopback. No public
inference listener, Docker/Kubernetes installation or system service is required.

## Worker configuration

Deployment schema version 1 contains `enabled`, `nodes`, `workers` and `policy`.
Each node has its fixed `id`, display `name`/`emoji`, private `lan_ip` and
`tailscale_ip`, SSH `username`, and optional boolean `maintenance` flag. Worker
records reference a roster `node_id` or use `local` with a literal loopback
`local_url`.

A worker has a stable `worker_id`, `label`, observed device label `gpu`, expected
`model_id`, supported `protocol` (`llama_cpp`, `openai` or `strata_openai`), private
`remote_port`, boolean `enabled`, `concurrency` (1–4), `interactive_reserve`,
`capabilities`, and `allowed_categories`. Context fields `context_configured` and
`model_context_limit` describe configuration and metadata; neither proves runtime
capacity. The registry separately reports empirically verified context, loaded
model identity, health, reservations, latency and throughput.

Start with concurrency 1. The categories `project`, `conversation`, `memory`,
`screen` and `sensitive` are separate approvals. All are denied by default;
`synthetic` alone permits engineering probes. Source categories are derived from
trusted capability provenance and followed through analysis dependencies. Model
labels cannot lower their sensitivity. Connectivity never grants data-sharing
approval. Authentication references an existing protected remote config through
`auth_config_file`, or an environment variable named `HANNI_COMPUTE_*` through
`api_key_env`. Secret values are excluded from public configuration and UI.

Policy limits include `max_queue` (1–128), `timeout_seconds` (1–300), `max_retries`
(0–1), `fallback_local`, and controller-classified `workflow_categories`.

## Separate Athena GPU servers

GPU startup uses an explicitly authorized `startup` object with `kind: llama_cpp`,
absolute existing `executable` and `model_file`, the discovered `gpu_device` UUID,
and initial `context: 8192`. KV caches default to `f16`; flash attention is disabled
until compatibility is established. The two GPU processes use separate ports and
separate GPU UUID assignments. An existing or uncertain listener prevents duplicate
startup. Only a process whose PID and environment match HANNI's generated ownership
nonce can be stopped by its lifecycle cleanup.

On this deployment, discovery verified a P6000 and a P40 with 24 GiB each,
compute capability 6.1, and an existing CUDA backend containing sm_61 kernels.
The existing 27B file is **Qwen3.8-27B-Q4_K_S.gguf**. Requested 27B IQ3_S weights
were not found. Testing the installed Q4_K_S file does not validate IQ3_S. No model
download, replacement or requantization was performed.

Context growth follows 8K → 16K → 32K → 64K → 128K. Require a passing near-limit
retrieval test from the same worker at the preceding stage before increasing
allocation. Stop after instability or OOM. Metadata declaring 262,144 tokens is not
runtime verification. The independently sealed benchmark uses actual server
tokenization, actual inference usage and two exact retrieval trials per stage.

## Existing Wonyoung Strata

Use the original Strata installation, interpreter, model shards and engine.
The optional authorized `startup.kind: strata` references the existing
`installation_dir`, `config_file` and `python_executable`. HANNI creates an
owner-only temporary configuration in `.hanni-managed/<nonce>` without changing
the original launcher or model files. It applies an 8K initial context, loopback
binding, bounded runtime and a RAM reserve. The owned wrapper disables external
hooks and browser opening for the engineering server.

The first wrapper attempt incorrectly resolved the virtual environment interpreter
symlink and selected the base interpreter. That startup defect was fixed while
preserving the existing virtual environment; no package installation was attempted.
The corrected bounded startup passed actual load, health, model identity, two
small inference requests and two sealed near-8K retrieval requests. Cache accounting
is explicit: fresh input plus reused input constitutes the full tested prompt.
The two existing IQ3_S shards total approximately 77.88 GiB; mmap and expert-cache
support must be inspected rather than assuming the entire file is resident.
Strata's measured limit is 8,192 tokens; its original larger configuration remains
untested. Its existing environment and model files are preserved.

Context evidence is durable at `compute/context-measurements.json`, bound to model,
backend, device and allocation identity. Configured limits alone do not enable
context-based dispatch. Changed allocations retain only the preceding-stage proof
needed for controlled growth, until new actual retrieval evidence is reviewed.
Worker health is rechecked separately; a saved capacity receipt is not an online
heartbeat. The current protected deployment enables the three measured workers
for synthetic data only. Forwarding owner conversations or project data still
requires explicit per-worker category configuration.

## Reproducible validation

Run the read-only eight-node census with:

```powershell
.\.venv\Scripts\python.exe scripts/v37_campaign/discover.py
```

Raw private results remain under `data/v37-manager/discovery`. Independent hardware
and model inspection scripts are under `scripts/v37_verification`. The prospective
protocol is sealed before output scoring; expected retrieval answers are not tuned.
The bounded `gpu_session.py` runner starts only the authorized existing Athena
workers and cleans up its own processes. Its loopback endpoint and ownership
receipts remain private. A local `data/v37-manager/gpu-session/stop` file requests
cleanup; the session also has a fifteen-minute deadline.

For a higher stage, use the following only after both same-worker 16K receipts
pass:

```powershell
.\.venv\Scripts\python.exe scripts/v37_campaign/gpu_session.py --context 32768 --output data/v37-manager/reproduce-32k-new
```

Its stop file and evidence are under
the chosen output directory. The runner refuses existing directories and always
clones deployment into isolated state, including at 8K. Independent
`benchmark_context.py` requires
the assigned loopback URL, worker ID, new output artifact and passing preceding
artifact. The manager imports reviewed sealed GPU evidence with
`import_context_evidence.py`; no frontend or model operation can manufacture
verification receipts. Files are protected deployment inputs, rather than source.

The existing Strata can be started for a bounded controlled campaign with
`strata_session.py --output data/v37-manager/strata-new-cohort`. Its output must be
new; its stop file is `<output>/stop`. The original server is untouched. To reproduce
the reviewed three-analysis comparison after all actual workers are ready, use:

```powershell
.\.venv\Scripts\python.exe scripts/v37_campaign/workflow_benchmark.py --cycle cycle4 --analyses 3 --output data/v37-manager/workflow-three-new
```

Choose a new output name for every evaluated campaign; the runner refuses to
overwrite prior responses or results. The comparison uses a
disclosed synthetic planner fixture and the original WorkflowService for execution
and verification. `primary_planner.py` separately tests a fresh complex goal with
the unchanged actual 4B planner and no supplied plan.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_compute_v37_verifier.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Controlled HTTP regression results prove integration boundaries, cancellation,
recovery and original completion semantics. GPU/model performance claims require
separate actual backend evidence. Every unavailable or untested value is reported
as unknown or blocked. Native UI scores require independent visible screenshot
review at large, small and compact sizes.
