# Hermes connection and automatic SSH forwards

## Approved direct MCP startup connections (2026-10-13)

The owner subsequently authorized direct HANNI MCP connections while retaining existing tool approvals. The private `data/mcp/auto-connect.json` pins three existing, already approved configurations by server ID and configuration hash: core on 8090, speech on 8091 and browser on 8931. Private `data/hermes/config.json` has `direct_mcp: true`; `connection_only: true` still prevents catalog imports or overwrites. The existing controller can attach approved external adapters. Hermes delegation remains explicit-only.

Dashboard startup starts one background reconnect worker through the original MCP manager. It performs initialization and tool discovery only, with at most eight consecutive attempts per pinned configuration and exponential backoff capped at 60 seconds. It reuses saved exact connection approval; it never grants new connection or tool approval. Disabled, removed, changed and revoked configurations remain blocked. Authenticated owner disconnect/disable/removal removes the startup pin. Shutdown stops the worker and closes owned MCP connections through the existing manager. Connection status appears in Hermes Overview.

Live validation used the actual SSH forwards and production MCP manager: core, speech and browser remained connected after discovery with respectively 6, 2 and 25 tools, all disabled. The probe closed its own SSH and MCP resources; reopening HANNI is needed to activate the new background startup path. An initial probe without active forwards failed; that failure was retained, and successful discovery was not substituted for tool execution. No MCP tool was invoked, no approval was broadened, and no remote service was restarted.

Reproduce connection lifecycle tests with:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_mcp_autoconnect.py tests/unit/test_mcp_hub.py tests/unit/test_hermes_bridge.py tests/unit/test_dashboard.py -q
```

Rollback this preference by setting the private startup policy's `servers` to an empty list and `direct_mcp: false`, then reopening HANNI. Retain saved tool definitions, approvals and unrelated MCP registrations. Private deployment policies and credentials are not committed.

## Assistant-only interface and explicit delegation (2026-10-13)

Primary navigation now contains Assistant, Mission and Hermes. Workspace pages (Planner, Workflows, Tasks, Calendar, Projects and Memory) and Screen Awareness are removed from navigation, search and rendering. Old links to those screens resolve to Home. Existing saved data and HANNI's local task capabilities remain intact.

Ordinary requests and follow-ups stay in HANNI. The resident semantic delegation classifier has been removed. Only direct owner instructions naming Hermes (for example `Give this to Hermes: research local speech recognition` or `Ask Hermes to inspect this file`) enter the existing scoped bridge. `Give it to Hermes` can use the preceding owner request for up to two minutes; missing or stale context asks which task to delegate. A disabled/unavailable bridge never silently executes that explicitly delegated request locally. Cancellation and original task authority, confirmation, audit and uncertain-write boundaries are preserved.

The private policy is recorded as `delegation_policy: explicit`; the Hermes toggle now permits or disables explicitly requested delegation. It cannot re-enable automatic routing. Reopen HANNI's backend to load the new session behavior.

Validation for this change: 75 targeted backend tests passed, including direct delegation, ordinary tasks staying local, negation, quoted examples, missing/stale context, explicit follow-ups, and unavailable/disabled Hermes. Frontend typecheck and production build passed. Live voice delegation after reopening the desktop was NOT TESTED.

## Hermes inspector tab (2026-10-13)

The Hermes page now has Overview, Capabilities, Commands, Skills and Current tasks sections. Search installed native toolsets, tool descriptions and arguments, slash commands/aliases, and skill metadata. Overview displays read-only service status, configured model/backend resources, platform toolsets, HANNI-approved Windows scope and current delegated commands. MCP connections show configured filters and timestamps of previously observed schema lists. Current tasks retains exact-action approval, cancellation, arguments, progress and receipts.

The live read-only inspection found 103 slash commands, 59 toolsets, 60 skills, four configured MCP connections (including GitHub), and 41 native tools with statically inspectable registrations. Source-generated registrations, plugins, live provider availability and commands in other Hermes sessions are not fully exposed by this bridge; these limitations are displayed. Installed and configured entries are not automatically labelled executable or healthy.

Inventory inspection runs over the existing authorized Karina SSH reference, in one background worker with an 18-second timeout and a one-minute cache. It parses installed source without importing tool handlers or invoking native slash commands. Failed reads retain previous inventory marked stale. Configuration projections omit credentials, environment values, HTTP headers, stdio arguments and URL authentication/query strings. This inspection does not attach MCP tools to HANNI's registry, change tool permission, run inference, or restart services. Inventory closes with the dashboard.

Validation: 58 targeted backend tests passed, including five new inventory tests for source parsing without execution, secret filtering, bounded background refresh, stale results, and revoked node access. The TypeScript check and production frontend build passed. Real Karina inventory was inspected successfully; physical desktop/voice and runtime availability of every native tool were NOT TESTED. Reopen the HANNI backend to load the new inspector. Reproduce the new tests with:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_hermes_inventory.py tests/unit/test_hermes_bridge.py tests/unit/test_dashboard.py -q
```

Open HANNI normally with `START_HANNI.cmd` or `START_HANNI_OS.cmd`, then select **Hermes**. The page shows authenticated bridge health, SSH status, task delegation, and exact action approvals. Ordinary conversation and voice remain in HANNI. Existing execution permissions and emergency stop still apply.

The private `data/hermes/config.json` now has `connection_only: true`. HANNI does not import Hermes MCP servers into its live registry, automatically reconcile the shared catalog, or accept shared-catalog management operations in this mode. Existing MCP configuration is retained. Hermes still uses its registered tools and their approval requirements. The existing delegation-enabled preference is preserved.

When the dashboard backend starts, `HermesControl` starts the owned `ManagedTunnel`; both normal launchers and desktop backend auto-start use this path. It forwards only loopback listeners:

| Windows endpoint | Karina destination |
| --- | --- |
| http://127.0.0.1:8090 | 127.0.0.1:8090 |
| http://127.0.0.1:8091 | 127.0.0.1:8091 |
| http://127.0.0.1:8931 | 127.0.0.1:8931 |
| http://127.0.0.1:18092 | Authenticated Hermes bridge, 127.0.0.1:8092 |

SSH destination: `karina@192.0.2.26`. Keepalives run every 30 seconds. Existing authorized keys and verified host keys are required; there are no password prompts or new public listeners. The forwarded MCP services must already be running on Karina. Forwarding does not start Docker services.

Backend exit stops only its owned SSH process. Closing to tray keeps the backend and tunnel running. An already running backend needs a normal exit and reopen to load these changes; attaching another window does not create another tunnel. Reconnection has bounded retries. An occupied port blocks the tunnel rather than adopting or terminating an unrelated listener. During validation an existing manual `ssh.exe` held ports 8090, 8091 and 8931: close that SSH session before reopening HANNI.

For standalone use while HANNI is closed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_mcp_tunnels.ps1
```

Keep the script running; Ctrl+C closes its own tunnel. This script uses the same Python tunnel implementation as automatic backend startup. Do not run both owners concurrently.

Validation:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_hermes_bridge.py tests/unit/test_mcp_hub.py tests/unit/test_dashboard.py tests/unit/test_mcp_session.py tests/unit/test_assistant_lifecycle.py -q
cd frontend
npm run check
npm run build
```

All 112 targeted backend tests passed. The frontend typecheck/build and PowerShell parser passed. A live authenticated `/health` probe over a temporary, unoccupied SSH forward returned protocol 1 and ready=true; the probe's owned SSH process stopped on cleanup. It did not run a model or restart a remote service. Exact requested-port startup remains blocked by the existing manual SSH listener until that session closes. Physical voice and a full reopened desktop/model task were NOT TESTED in this change.

Rollback: restore previous private forwards (18090→8090, 18091→8091, 8931→8931, 18092→8092), set `connection_only: false`, and reopen the backend to restore the prior catalog/controller integration. Restoring the old MCP Hub navigation requires reverting only this change's frontend import/render/label edits and rebuilding. Retain private credentials and task receipts; do not restore other unrelated workspace changes.
