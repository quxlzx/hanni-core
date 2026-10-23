# HANNI Assistant Reset — Checkpoint

Date: 2026-09-22

## Purpose of this checkpoint

This checkpoint completes the architectural cutover far enough that future work can proceed from a coherent base. HANNI is now centered on one lightweight resident assistant model plus bounded natural-language MCP-style tools. It is no longer centered on autonomous planning, worker delegation, or multiple resident LLM roles.

## Completed

### 1. Single-model runtime

- `config/models.yaml` contains exactly one model with role `supervisor`.
- Default: `Qwen3.5-4B-Q4_K_M.gguf` via llama.cpp.
- 16K context, one parallel slot, quantized KV configuration, and a conservative VRAM budget are configured for background use.
- Configuration parsing rejects multiple model roles.
- Model management is single-model-first and does not silently fall back to retired router/planner profiles.

### 2. GPU routing foundation

- AUTO routing targets the smallest qualifying discrete 8 GB-class GPU.
- Driver-reported capacities slightly below 8192 MiB are accepted as 8 GB-class.
- Selection can step up to a larger GPU when the configured VRAM budget cannot fit safely.
- A persisted dashboard override can pin HANNI to a detected GPU.
- Routing persistence uses stable adapter identity information rather than trusting device indices alone.

### 3. MCP/tool-call foundation

- `hanni.mcp.host.McpHost` retrieves a bounded set of relevant capabilities instead of exposing the entire tool registry.
- Natural-language routing resolves high-confidence time, Calendar, and local-computer intents before model tool selection.
- Relative Calendar dates are converted from the Windows local clock to exact dates before tool execution.
- Google Calendar is the sole active calendar provider; the legacy local `.ics` calendar capability family has been removed.
- The MCP surface remains observe-first; `google_calendar.create` is the first and currently only explicitly allowlisted model-facing write action.
- Other write/action-style user requests are not silently converted into nearby read actions.
- Calls still execute through the existing `ToolRegistry`, keeping validation, permissions, safety checks, and audit behavior below the MCP boundary.
- `McpToolSession` implements a bounded model -> tool -> model loop and falls back to ordinary conversation if the local model/server cannot perform compatible tool calls.
- `hanni.mcp.server` provides an MCP v2 server facade over the same bounded capability layer for future external MCP clients/transports.

### 4. Live assistant path

- CLI text chat uses the same resident model/MCP path.
- The live voice path wraps the same model-facing MCP session rather than maintaining a separate planner/worker path.
- Dashboard conversation attaches to the same session path.
- System prompting explicitly defines HANNI as an observer/assistant, not an autonomous worker.

### 5. Legacy architecture removed from the active package

Removed from the active Python package in this checkpoint:

- autonomous `hanni.agent` planner/loop/delegation implementation
- old routing/evaluation package and fixed router benchmark assets
- screen-vision package and vision-model launch behavior
- tests whose sole purpose was validating those retired systems

The current package no longer declares those modules in `pyproject.toml`.

## Intentionally retained

- voice/STT/TTS/barge-in/relevance behavior
- memory subsystem
- validated local capability implementations
- permissions/privacy/audit foundations
- dashboard and telemetry
- GPU selection and model lifecycle
- Google/local integrations already implemented under the capability layer

Most mutation tools remain manual-only. Google Calendar creation is the sole current model-facing exception, admitted only from clear natural-language creation/scheduling requests and still executed through the normal permission/audit boundary.

## Known limitations / next work

1. **Windows/live hardware validation is still required.** This development checkpoint was assembled in a Linux build environment, so actual RX 6600 XT llama.cpp placement and Windows telemetry should be verified on the target PC.
2. **External MCP transport has not been end-to-end exercised here.** The code targets the MCP Python SDK v2 `MCPServer` API, while the in-process MCP host/session is the currently exercised HANNI path.
3. **Capability retrieval needs HANNI-specific evaluation.** The current bounded search/router should later be measured on a dedicated computer-awareness/tool-selection dataset.
4. **Dashboard still contains visual/CSS remnants from earlier benchmark-era UI.** These are harmless and can be cleaned during the later dashboard redesign rather than mixing UI work into this architecture checkpoint.
5. **No new convenience/startup scripts were added**, per the current project constraint.
6. Remote observers (LocalForge, Kubernetes, other PCs/servers) are not added yet. They should be separate MCP servers or capability providers in a later phase.
7. Additional write/action MCP tools must be added individually to the explicit action allowlist; never enable the whole mutation catalog by flipping `read_only` off.

## Recommended next phase

Build **local computer awareness** on top of this foundation:

1. inventory and normalize read-only system/GPU/process/storage/network/service/model capabilities;
2. add state/history storage that does not require LLM activity;
3. expose the most useful state in the dashboard;
4. build a HANNI-specific MCP/tool-use evaluation suite;
5. only after local awareness is reliable, add LocalForge and remote-server MCP observers.

Do not reintroduce router/planner/delegation models unless a measured requirement justifies them.

## Checkpoint validation

At packaging time in the development environment:

- shipped YAML configuration loaded successfully;
- Python sources compiled/imported through the test suite;
- retained automated suite: **344 passed, 2 skipped, 17 subtests passed**;
- the two skips were environment/optional-dependency checks (installed console entry point and optional Google auth package), not core assistant failures;
- no live Windows GPU/model process was launched in this Linux build environment.

The main existing setup/start scripts were also updated to stop referencing retired vision, benchmark, multi-model, or agent components. No new convenience/runtime scripts were added.

### Natural-language routing checkpoint (2026-09-22)

- `what's on my calendar tmr?` and `what do I have tomorrow?` resolve tomorrow from the machine-local date before Google Calendar is queried.
- Calendar follow-ups can inherit recent Calendar context, while unrelated phrases do not.
- `schedule/add/create` Calendar requests use the deterministic date/time parser and lock the resolved start/end before execution.
- Explicit non-Calendar mutations such as `kill the process using the most CPU` are blocked before they can collapse into a nearby read route.
- Google Calendar creation uses the event-write OAuth scope; previously connected read-only credentials must be reconnected. Gmail remains read-only.
- No new PowerShell/CMD convenience scripts were added for this change.

### Negative routing + model-final tool selection (2026-09-22)

- Added negative routing signals for common lexical traps: RAM vs VRAM, incidental “right now” vs clock intent, and Windows OS performance vs UI-window intent.
- Negative signals only alter retrieval eligibility/ranking; they do not diagnose or execute anything.
- The deterministic layer may resolve fixed context such as exact relative dates, but `McpToolSession` no longer auto-executes allowlisted actions.
- Qwen now makes the final tool-call decision for every model-facing MCP turn, including Google Calendar creation. Registry safety/permission/audit enforcement remains below that boundary.
- No new capabilities or scripts were added in this checkpoint.
