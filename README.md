# H.A.N.N.I.

**Experimental alpha.** Use the current [publication checklist](docs/PUBLIC_RELEASE_PREPARATION.md) and `PUBLIC_READINESS.json` in the prepared release copy. Automated software checks do not certify live voice latency, model planning quality, or external integrations. Historical evaluation reports retain their original scope and failures.

H.A.N.N.I. (Highly Adaptive Neural Network Intelligence) is a **local Windows 11 assistant** with bounded, permission-aware workflows for persistent goals.

## Quick start on Windows

1. Install **Python 3.12**. The setup command can install llama.cpp with WinGet when available.
2. Download or clone this repository, open its folder, and run `SETUP_HANNI.cmd`. It creates `.venv` and installs the normal app, speech, and Google dependencies. The first setup needs internet access; model weights are not included in GitHub.
3. Run `START_HANNI.cmd` to open HANNI. The first model start may need to download the configured Qwen3.5-4B GGUF.

## Portable native brain (any machine, no install ritual)

The native agent stack — agent loop, durable memory, skills, local + web tools, approval receipts — also runs standalone on **Linux or Windows** with just Python 3.10+:

```
git clone <this repo> && cd HANNI
python scripts/get_models.py            # tier models + llama.cpp binaries
./start_brain.sh                        # Linux   (Windows: START_BRAIN.cmd)
```

First boot **benchmarks every tier on the actual hardware** (7B → 3.7B → 2B) and picks the fastest one the machine can host — no guessing from spec sheets. When ready, your browser opens the **full Hanni OS dashboard** at `http://127.0.0.1:8313/` (Mission → Tasks is the live agent console: approvals, submissions, receipts). The raw model chat is at `:8311`, the agent API at `:8312`. Everything (memories, skills, tool receipts) lives in the repo folder. The same layout fits on a USB stick: copy the repo, plug into any machine, run the launcher.


To connect Google Calendar, obtain a Google OAuth **Desktop app** client in Google Cloud, then run this from the repository folder in PowerShell:

```powershell
.\.venv\Scripts\hanni.exe google login
```

HANNI finds a downloaded client JSON in Downloads or asks for its path, opens browser sign-in, and saves the authorization locally. Check or remove the connection with `.\.venv\Scripts\hanni.exe google status` and `.\.venv\Scripts\hanni.exe google logout`. Google login is optional for non-Google features. See [Google setup](docs/GOOGLE.md) for the one-time Google Cloud steps.

Optional **Laya memory intelligence** is now bundled as an opt-in, read-only shadow observer. The normal `START_HANNI.cmd` launch can also start or connect to Laya automatically, including over SSH to a private GPU machine. Laya does not influence memory writes, replies or permissions. It is **off by default** and training weights/private datasets are not shipped. See [Laya shadow setup](docs/LAYA_SHADOW.md).

**V3.5 personal memory** adds a Memory Explorer with source/history inspection, owner-reviewed corrections and suggestions, bounded contextual retrieval, and explicit links to existing projects and verified workflow receipts. New contextual integration and LAYA advisory/reranking remain disabled by default. A working installed LAYA model has not been independently verified, so its production quality gate remains closed. See [V3.5 configuration](docs/HANNI_V3_5_SETUP.md), [verified results and limitations](docs/HANNI_V3_5_REPORT.md), and [milestone checkpoints](docs/HANNI_V3_5_CHECKPOINTS.md).

This repository does **not** include model weights, Google credentials, account tokens, logs, chat history, or local evaluation transcripts. Keep those files local; see [security and sharing](SECURITY.md).

Models now opens the integrated four-model inference control center, with lifecycle controls, streaming chats, comparison, saved histories and live metrics. The same controls appear in HANNI and Wonyoung cluster details. See [control-center integration and deployment](docs/CONTROL_CENTER_INTEGRATION.md).

## Current architecture

This checkpoint intentionally has one resident language model and one model-facing capability path:

```text
Owner (text / voice / dashboard)
            |
            v
family / sub-intent retrieval + resolved local dates
            |
            v
1-8 relevant MCP schemas -> Qwen3.5-4B chooses tool calls
            |
            v
validated HANNI capability registry
            |
            v
live local computer state / approved MCP servers
```

The model is conversational and interpretive. It is not the source of truth for live machine state. CPU, RAM, GPU, process, storage, network, application, and service information must come from validated local tools.

**Settings → Integrations → MCP Hub** adds owner-configured stdio and Streamable HTTP servers to this same execution path. Connect approval, hash-bound tool approval and execution confirmation remain separate; imported tools start disabled. See [MCP Hub setup and policy](docs/MCP_HUB.md) for safe connection settings, import/export, persistence and the observe-first model limits. [Implementation checkpoints](docs/MCP_HUB_CHECKPOINTS.md) record actual verification progress.

## Deliberate constraints at this checkpoint

[Reliability & Intelligence V2](docs/RELIABILITY_V2.md) documents metadata-based retrieval, conservative action verification, bounded recovery and execution inspection in Activity. [Milestone checkpoints](docs/RELIABILITY_V2_CHECKPOINTS.md) distinguish measured baseline, development checks and independent final acceptance.

The [final independent comparison](docs/RELIABILITY_V2_REPORT.md) is **PARTIAL**: controlled reliability and Activity checks pass, while untouched language retrieval remains below target. It includes measured counts, confidence intervals, failure analysis and reproducible evaluation inputs.

Persistent local goals now use the original controller through **Workflows**: bounded dependency plans, exact approvals, durable invocation checkpoints, conservative crash recovery and required outcome criteria. [Workflow setup and architecture](docs/WORKFLOWS_V3.md) explains modes, limits, private retention and the independent backend/window lifecycle. [V3 checkpoints](docs/WORKFLOWS_V3_CHECKPOINTS.md) preserve completed checks and failed evaluation cycles.

[V4 adaptive routing](docs/HANNI_V4_ADAPTIVE_MODELS.md) uses measured endpoint capabilities and existing sharing permissions. [V4.1 collaboration](docs/HANNI_V4_1_COLLABORATION.md) adds selective independent analysis and review to the same Workflows interface; the original controller still verifies outcomes and controls tools.

[V4.2 performance optimization](docs/HANNI_V4_2_PERFORMANCE.md) adds bounded recent placement, compatible-worker queue ordering, invalidated profile/memory caches, and endpoint telemetry in Model routing. The [independent comparison](docs/HANNI_V4_2_BENCHMARK_COMPARISON.md) records measured application gains, unchanged model settings, verified 8K/16K context, and the limits of current remote hardware access.

[V4.3 Model Intelligence Lab](docs/HANNI_V4_3_MODEL_LAB.md) brings registered model inventory, benchmark controls, per-case evidence, historical runs, export, comparison and routing insights into the existing desktop. Implemented development suites retain explicit evaluation scopes and original scoring/admission; [checkpoints](docs/HANNI_V4_3_CHECKPOINTS.md) and the [independent review](docs/v43-reviews/INDEPENDENT_REVIEW.md) record actual execution and visual evidence.

[V4.4 full-system validation](docs/HANNI_V4_4_FINAL_VALIDATION.md) evaluates routing, collaboration, distributed inference, workflows, memory, MCP and the native desktop. [Durable checkpoints](docs/HANNI_V4_4_CHECKPOINTS.md) distinguish controlled regression coverage from actual model results and unavailable deployment evidence.

The [V3 implementation and independent assessment](docs/WORKFLOWS_V3_REPORT.md) is **PARTIAL**. Execution, recovery, security and the native interface pass their documented engineering checks. Natural-language goal planning remains experimental: the current configured planning path completed **0/15 fresh supported multi-step goals**. The requested 95% autonomous completion target is not met; scripted execution tests do not measure model planning quality.

To run that backend without voice capture or interactive input:

```powershell
.\.venv\Scripts\python.exe -m hanni.dashboard.launcher --workflow-only --no-browser
```

Keep that backend terminal open. Submit `/goal <objective>` from the existing keyboard session. The primary interface now contains Assistant, Mission and Hermes; the former Workspace navigation is removed. Workflow execution still obeys original permissions and Stop; an uncertain write never becomes an automatic retry. Unattended intent execution remains disabled until its task-family acceptance gate passes.

- Exactly **one configured LLM** (`supervisor`).
- The default model is `Qwen3.5-4B-Q4_K_M.gguf` through llama.cpp.
- The resident model is intended to stay loaded with a modest 16K context.
- GPU AUTO routing prefers the **smallest discrete 8 GB-class GPU** that can safely fit the model; dashboard override remains available.
- The model is exposed to at most a small relevant set of tools per turn.
- The MCP layer is **observe-first**: read tools and explicitly allowlisted owner actions are exposed. The allowlist includes Calendar creation, existing application launch and media/Spotify controls.
- Existing validation, permission, safety, and audit checks remain below MCP.
- Voice, memory, telemetry, and the dashboard remain part of the foundation.
- Legacy autonomous agent/planner/delegation and screen-vision runtime were removed from the active package. The current routing and mocked-tool evaluations are maintained separately under `src/hanni/evals/`.

## Important files

- `config/models.yaml` — the single resident model and GPU/runtime budget.
- `config/hanni.yaml` — MCP, voice, memory, logging, and recovery configuration.
- `src/hanni/mcp/host.py` — natural-language routing, bounded capability discovery, exact argument locking, and action allowlisting.
- `src/hanni/mcp/session.py` — model -> tool -> model loop.
- `src/hanni/mcp/server.py` — MCP v2 server facade for the same validated local capabilities.
- `src/hanni/tools/` — existing local computer capability implementations.
- `src/hanni/models/runtime.py` — llama.cpp launch and GPU routing.
- `src/hanni/dashboard/` — local dashboard and GPU selection UI.
- `docs/ASSISTANT_RESET_CHECKPOINT.md` — exact state of this handoff and next steps.

## Natural-language routing

The routing-hardening milestone covers all **150 registered capabilities** with
**1,087 cases**, including blocked actions. Qwen remains the final tool selector.
See [architecture and benchmark commands](docs/ROUTING_HARDENING.md),
[before/after scores](evals/routing/BASELINE.md), and
[capability coverage](evals/routing/capability-coverage.json).
The [150-case LLM Tool Eval](docs/LLM_TOOL_EVAL.md) is separate from routing scores.
The current Qwen3.5-4B live development run passed **139/150 (92.67%)** of
tasks with the configured Personality V2 prompt. Diagnostics passed **37/45
(82.22%)**; tuned Language V3 routing passed **150/150** on its development
phrases. The once-run locked Holdout V2 passed **45/72 (62.50%)**, with 24
routing failures, so Tool Intelligence V1 is **not frozen**. See the
[freeze blockers](docs/TOOL_INTELLIGENCE_V1_BLOCKERS.md) and
[final handoff](FINAL_GENERALIZATION_HANDOFF.md).

Language Generalization V2 adds a separate 200-case owner-style development
corpus and a 50-dialogue follow-up corpus. These are inspectable development
tests, not blind evidence. Run `hanni eval routing-language-v2` and
`hanni eval routing-multiturn-v1`; results and freeze status are in
[the V2 report](docs/LANGUAGE_GENERALIZATION_V2_REPORT.md). HANNI's
warm/casual style is configured under `personality` in `config/hanni.yaml`;
[Personality V2](docs/PERSONALITY_V2.md) documents its grounding and the
50-pair synthetic A/B evaluation. Run `hanni eval llm-coverage --strict` to
audit two mocked schema/menu probes for each model-facing capability.

HANNI uses Google Calendar as its only calendar provider and accepts ordinary owner language rather than tool/API syntax. High-confidence time and Calendar intents are resolved deterministically before the 4B model sees a tool. For example, `what do I have tomorrow?` resolves tomorrow in `config/hanni.yaml`'s `user.timezone` and exposes exactly that Google Calendar window; `schedule dinner Friday at 8pm for 2 hours` resolves an exact start/end in the same IANA timezone and routes to the single allowlisted `google_calendar.create` action. The resolved arguments are locked server-side so the model cannot silently change the date. Set `user.timezone` to your local IANA timezone if you move. Generic computer/file/process questions continue through the bounded capability retriever.

Google login defaults to Calendar read-only access. Add Calendar writes with `hanni google login --replace --scopes calendar.write`. Gmail, Drive, Docs and Google Tasks have separate opt-in grants. See [Google capabilities and setup](docs/GOOGLE.md) for scopes, named accounts, follow-ups and write gates.

## Development setup

The native **HANNI OS** workspace includes Assistant, Workspace and Mission
Control, with sixteen screens and the globally accessible HANNI Mini. It reuses
the existing local controller, chat inbox, permissions and voice loop. Launch
`START_HANNI_OS.cmd` for the desktop or `START_HANNI.cmd` for the assistant session.
See [desktop setup](docs/HANNI_DESKTOP.md),
[workspace integration](docs/HANNI_WORKSPACE_INTEGRATION.md), and
[Phase 1 + Phase 2 verification](docs/HANNI_PHASE12_FINAL_VERIFICATION.md)
for measured results, actual screenshots and remaining limitations.

Python 3.12+ is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Google support is included in a normal HANNI install. With the virtual environment activated, use:

```powershell
hanni google login
hanni google status
hanni google logout
```

If this HANNI installation has no Google OAuth Desktop client yet, `login` looks
for one in Downloads. If none is found, it opens Google Cloud and asks for the
downloaded client JSON path. It imports the file
into the ignored `config/google-oauth-client.json` path, then continues directly
to browser sign-in. A client created for HANNI must exist before Google can
authorize Gmail and Calendar; the user does not need to copy files manually.

Named accounts such as `personal`, `school` and `work` use `--account`. HANNI stores
authorization in Windows Credential Manager. Enable other read services with
`hanni google login --replace --scopes calendar.read gmail.read drive.read docs.read tasks.read`.
Use `hanni google use school --service calendar` to choose a service default;
unqualified requests search one account. `google status --verify` checks authorized APIs.

To benchmark the configured resident model against synthetic MCP results:

```powershell
hanni eval llm-tools
hanni eval llm-tools --audit
hanni eval compare data\qwen-4b-tool-eval-final.json data\k2-tool-eval.json
```

See [LLM Tool Eval V1](docs/LLM_TOOL_EVAL.md) for filters, scoring, and safety guarantees.

For local speech dependencies:

```powershell
python -m pip install -e ".[dev,speech]"
```

The project depends on the stable MCP Python SDK v2 line.

## Validate this checkpoint

```powershell
python -m pytest
hanni health
hanni model-info
```

A live-model test additionally requires a current llama.cpp build and the configured Qwen GGUF (or Hugging Face loading through llama.cpp).

## Not implemented yet

Do not treat this checkpoint as the final HANNI architecture. The next phase should expand **computer awareness and MCP coverage**, then improve dashboard/state presentation and only later add remote-server observers such as LocalForge/Kubernetes. Additional write/action tools should remain separately and explicitly allowlisted; do not expose the full mutation catalog to the resident model.

## Natural-language routing evaluation

HANNI includes a 1,087-case routing benchmark that does **not** execute real capabilities.
It checks whether normal owner language retrieves the right bounded MCP tool set, resolves
calendar dates/times correctly, and blocks unsupported write actions.

```powershell
python -m hanni.evals.routing
```

See `evals/routing/README.md` for the corpus, scoring, and untuned baseline.

The [Routing Generalization V4 handoff](ROUTING_GENERALIZATION_V4_HANDOFF.md)
records the 300-case development run, the untouched V4B first-run gate, and
the current non-freeze decision. Inspect a request's deterministic menu and
prototype scores with:

```powershell
hanni eval routing-debug "Friday agenda, remaining disk space"
```

## Native brain (no Hermes required)

HANNI can now run its own resident agent loop instead of delegating to an
installed Hermes. The native loop (`src/hanni/native/`) speaks the
OpenAI-compatible `/chat/completions` protocol directly to the resident model
endpoint from `config/models.yaml` (Strata, llama-server, or any compatible
server), while keeping the existing security architecture identical: bounded
tool menus, JSON-Schema validation, durable action requests, and
receipt-producing execution authority (`hanni.hermes.state`).

Select the engine when starting the bridge service:

```sh
# Linux
./run_hanni_native.sh
```

```bat
:: Windows
START_HANNI_NATIVE.cmd
```

or directly:

```
python -m hanni.hermes.service --root <root> --hermes-config config/hanni.yaml \
    --token-file <token> --brain native
```

Environment:

- `HANNI_MODEL_CONFIG` — path to `models.yaml` (defaults to `config/models.yaml`)
- `HANNI_MODEL_ID` — pick a model entry by id (defaults to the `supervisor` role)
- `HANNI_MODEL_API_KEY` — bearer token for the endpoint (default `local`)

Native-loop options can be set per model entry in `models.yaml`:
`native_max_tokens`, `native_temperature`, `native_reasoning_budget`
(the last maps to llama-server's `--reasoning-budget`, which keeps small
models from ruminating without converging).

## Cross-platform support

The repository targets both Windows and Linux:

- process supervision in `hanni.hermes.service` uses process groups on both
  platforms (`CREATE_NEW_PROCESS_GROUP`/`taskkill` on Windows,
  `start_new_session`/`killpg` on POSIX)
- all path handling is `pathlib`-based
- Linux quick start:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
sudo apt install libportaudio2   # audio stack (speech features; tests that
                                 # boot the full UI backend need it too)
./run_hanni_native.sh
```

- Windows quick start: `SETUP_HANNI.cmd` then `START_HANNI_NATIVE.cmd`
- run the test suite on either platform with `.venv/bin/python -m pytest tests/`
  (`tests/test_native_loop.py` covers the native loop with a scripted model
  client and needs no network, model, or audio device)
