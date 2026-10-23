# Campaign 2 MCP audit

The new MCP audit passes **157/157 checks** over actual installed MCP SDK 2.2.0 stdio and Streamable HTTP connections. The test run took 52.234 seconds. No production MCP code changed and no product defect was reproduced after correcting the test harness. This is evidence about real local protocol connections carrying controlled fixture data; it does not establish connectivity or factual quality for a physical instrument or an external provider.

Fresh machine-readable evidence is in `data/campaign2-mcp/verified-03/results.json`, `tests.xml`, `inventory.json`, and the 29 files under `transport_receipts/`. Each receipt records the negotiated initialization, discovered definitions, original registry imports and actual endpoint events. The inventory derives eight imported tools from the authored contracts and observes 172 original built-ins in the isolated registry. The built-in count is observed rather than hardcoded, and those built-ins remain the Manager's separate audit responsibility.

Reviewable public evidence is retained in `MCP_SCORECARD.json` and `MCP_EVIDENCE.json`. It derives every per-tool dimension from the actual pytest node IDs, retains production hashes and hashes of all 29 transport receipts, and links the private raw evidence by hash. The Manager's separate read-only persisted owner inventory observes zero configured MCP servers and zero enabled tools; these counts are derived from the inventory lists rather than hardcoded. They describe saved owner discovery, not a live external connection.

## Scope and isolation

Every MCP server, store, configuration copy and in-memory record in this audit belongs to the test. The owner's MCP database, credential vault, saved servers and running services were not used. A no-credential vault is attached only to the temporary registry. The tests retain the production `MCPManager`, `SDKConnection`, `ToolRegistry`, `McpHost`, JSON Schema validators, permission profiles, confirmation checks, background policy and emergency-stop behavior. No real model calls, node power actions, terminals, desktop operations or foreign account mutations run in this suite.

Stdio children are owned by the original SDK connection. HTTP fixtures are launched by the harness on explicitly approved literal loopback ports; the manager owns the connection, while the harness owns the server process. Windows virtual-environment launcher and interpreter PIDs are distinguished using parent provenance, creation time and the exact fixture command. Removal proves stdio cleanup and proves HTTP servers are not silently adopted or terminated by the manager; harness teardown stops its own HTTP process afterward.

Supplemental `cleanup-04/results.json` persists exact PID, creation-time, parent ancestry and fixture commands while both children are alive, then records the expected difference after manager removal and confirms both owned children are gone after harness cleanup. This performs discovery only and records no `tools/call`. The main run's separate readback checks 30 fixture PID files and observes zero remaining processes matching those exact owned fixture commands.

## New tool inventory

All tools are freshly authored for Campaign 2. Input and output schemas are preserved exactly through discovery, the registry and the model menu; the complete JSON definitions are in `scripts/campaign2/mcp_contracts.py` and the evidence inventory. All input objects reject additional properties and declare their required fields. Output schema validation applies to the SDK's `structuredContent` before HANNI wraps it as `ToolResult.data.structured_content`.

| Original SDK tool | Input contract | Structured output fields | Explicit owner classification | Default assistant menu |
|---|---|---|---|---|
| `prism.read_alignment` | required axis `x` or `y` | axis, alignment | read only | admitted |
| `prism.echo_label` | required label, 1–64 characters | label | read only | admitted |
| `prism.sum_samples` | required numeric array, 1–8 values | total, count | read only | admitted |
| `prism.decode_profile` | required nested enabled/channel profile, optional nullable label | profile | read only | admitted |
| `prism.create_record` | required nonempty record ID and title | record_id, created | write | denied by default session policy |
| `prism.erase_record` | required nonempty record ID | record_id, deleted | destructive | denied by default session policy |
| `prism.defer_read` | required channel `primary` | channel, complete | read only | admitted |
| `quartz.inspect_flux_band` | required calibration `AX-17` or `BQ-04` | calibration, band, intensity | read only | admitted |

Create and erase affect only the fixture's in-memory records. They are called through the original registry after explicit test-owner confirmation. The destructive tool deliberately advertises false read-only/non-destructive hints; these do not override the explicit owner classification. The remaining observations are controlled local facts or pure calculations/echoes, not readings from physical hardware.

## Assertions and results

The 130 matrix tests include eight dimensions for every tool on both transports, plus discovery/schema/classification checks for each transport:

- Valid original-registry calls produce typed structured results with original tool names and correlated definition/capability receipts.
- Invalid arguments and missing required arguments are rejected before any SDK call.
- Unknown actor profiles are rejected. Write and destructive operations require original confirmation; a model's text grants no permission.
- Disconnect withdraws every executable adapter and rejects both ordinary registry dispatch and previously cached handlers.
- Invalid advertised outputs never return success; the next valid call succeeds.
- Six read-only natural-language requests retrieve their required imported tool. The two mutation requests retain the original default session denial. These are metadata retrieval checks, not claims about resident-model selection.
- Original-host read calls traverse the SDK and validate the response contract. Original-host mutation calls return permission denial and do not reach the endpoint.

The remaining 27 lifecycle checks verify exact connection approval before launch, paginated discovery without tool execution, explicit enable/disable and inert persistence, changed-definition approval revocation, actual SDK `list_changed` notifications, tool removal from live/cache menus, duplicate-name failure within one server, separate identities for duplicate original names across servers, failed initialization and explicit recovery, timeouts, explicit tool errors, removal during an active RPC, unsupported remote schema references, original foreground/stop gates, and process cleanup/ownership.

Description and annotation changes require renewed exact approval. A malicious description instructing the assistant to erase records or claim success remains data: discovery performs no action, the destructive capability keeps its original risk/confirmation policy, and the tested read dispatch invokes only the requested original tool. This establishes host/registry authority containment; it is not a broad model prompt-injection quality result.

A delayed read times out within the original bound. Stdio recovers on the existing session in this run. Streamable HTTP cancellation ends its SDK session and safely withdraws adapters; an explicit approved reconnect restores availability. Neither path silently replays a timed-out call or returns a completed result from it. Active removal similarly rejects any late result.

## Preserved harness corrections

`baseline-01` is retained with 99 passes and 58 failures out of 157. The major cause was supplying an MCP approval digest where `ToolRequest.expected_definition_hash` requires the registry's original authorization fingerprint. Other failures were test assumptions about the stop method's keyword-only signature, per-request SDK session proxies, HTTP notification advertisement, Windows launcher versus actual interpreter PIDs, and waiting for an intermediate notification-refresh snapshot. The unsupported-reference test also initially omitted the object type required by the SDK, so the SDK rejected the whole discovery response before HANNI could classify the schema.

`baseline-02` is retained with 154 passes and three failures. Two stop tests reconstructed requests after definitions had already been withdrawn; the correct original failure is `UnknownToolError`, with cached handlers also denied. The remaining test incorrectly required a cancelled HTTP session to remain open; recovery now verifies safe withdrawal followed by explicit owner reconnect. These are documented harness corrections, not production repairs or weakened authority gates. The final corrected run is `verified-03`.

## Unknown capability and remaining boundary

`quartz.inspect_flux_band` did not exist in the initial router development. It is discovered dynamically, receives an owner-approved classification, enters the original menu through its metadata, and executes through both actual SDK transports without routing code changes or retraining. The independent request is:

> On Quartz Bench, inspect the flux band for calibration AX-17 and report the returned band and intensity.

The Manager's initial separate original guarded resident-model demonstration was **blocked**, with zero actual model HTTP requests. The recorded available RAM was 1,770,528,768 bytes; the original selector refused inference, and the Manager's admission inspection identified insufficient RAM reserve. A separate declared-argument original-registry SDK call succeeded and returned calibration `AX-17`, band `narrow`, intensity `0.42`. Its verification remains `UNVERIFIED` with scope `external_tool_response` and `independent: false`. This is a typed controlled server response, not independent instrument verification or a model-selected answer.

The final sweep after repository tests exited again blocked all 173 attempts
(every built-in plus the novel tool), with zero inference HTTP requests and
1.781–1.884 GiB available RAM. See [final model outcomes](MODEL_SELECTION.json)
and [the final unknown-tool receipt](UNKNOWN_TOOL.json). This later evidence
preserves the original reserve and does not overwrite the initial probe.

The public scorecard records actual unknown-tool model selection as blocked and the other fixture tools' actual model selection as not tested. This report does not count deterministic retrieval checks or original-host calls as a real model choosing a tool. No external MCP provider is authenticated or contacted by this suite.

## Checkpoint

The five production MCP files have identical before/after hashes in `verified-03/results.json`: `adapter.py`, `host.py`, `manager.py`, `security.py`, and `transport.py`. The new source is limited to `scripts/campaign2/mcp_*`, `tests/integration/test_campaign2_mcp_*` and this report. No staging or commit was performed. Independent verifier findings and the Manager's model demonstration remain separately owned evidence.
