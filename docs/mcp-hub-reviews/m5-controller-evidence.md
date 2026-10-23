# Independent inspection of configured-model controller evidence

**PASS for the observed read-only imported-tool scenario.** The coordinator executed this test; the verifier independently read its harness, result, original controller log, original execution audit and actual SDK fixture ledger. It is genuine configured-model inference, distinct from the deterministic model used for native fixture interactions.

Evidence directory: `data/hanni-mcp-hub-review/live-controller-cycle-1/`.

The harness `scripts/check_hanni_mcp_controller.py` starts the original `hanni.dashboard.launcher --text --no-browser` with an isolated data directory and ephemeral loopback port. It does not replace the model client, router, controller, registry or private Hub API. The original log identifies configured `Qwen3.5-4B-Q4_K_M.gguf`, llama.cpp device Vulkan1 and verified 33/33 GPU layers. Keyboard mode explicitly starts no microphone, VAD or STT.

Observed corroborating records:

| Evidence | Observation |
|---|---|
| results.json | Six coordinator assertions pass: readiness/binding, paginated discovery without calls, hot registration, actual inference/execution, hot withdrawal and clean original shutdown. |
| fixture-ledger.jsonl | Actual SDK events are tools/list cursor 0, tools/list cursor 2, then exactly one tools/call with original external name `mock.echo`. |
| controller-audit.jsonl | The imported capability `mcp.6b14d5b25853437ba92e74b821de088f.29b7953076d3d810` executes successfully with source `mcp.model`, permission/risk 0, `confirmed:false`, redacted arguments/result and a nonempty correlation ID. Management uses the original confirmed owner gate. |
| controller.log | The actual model reply is `The returned message is: "HANNI MCP verification".`; the original model manager reports its owned supervisor stopped and memory released. |

The harness checks that the live workspace contract gains the approved capability, loses it after disable, and has no configured server after removal, all without restarting the controller. Shutdown returns exit code zero. These checks and matching ledger/audit records substantiate the result beyond direct SDK connectivity.

This proof uses the actual local configured model and an official SDK stdio server with synthetic harmless echo data. It does not prove a live external provider, HTTP-model inference scenario, voice input, write confirmation UX or native rendering. The separate independent tests cover actual Streamable HTTP execution and original write permission separation. Default observe-first sessions expose approved read-only tools; a trusted confirmed ToolRequest on the attached original registry is required for tested writes. No generic frontend tools/call endpoint or nonexistent CLI write workflow is claimed.
