---
name: mcp-server-selftest
description: Build and test a local MCP stdio server without an LLM.
version: 1
author: hermes
license: MIT
metadata:
  hermes:
    tags: [mcp, stdio, testing, hanni]
    related_skills: [windows-ssh-remote-dev]
---

# Build and self-test a local stdio MCP server (no LLM)

## When to Use
Wrapping an existing tool/capability registry as an MCP stdio server, keeping the registry's own gates, and proving every tool works by driving the server as a client — no model in the loop. Also covers registering such a server for auto-start/auto-stop with a hub (HANNI MCP Hub pattern).

## Server construction
- Expose the whole registry as ONE stdio server rather than one process per tool; each `call_tool` handler must re-run the registry's real gates (arg validation, permission profile, confirmation, emergency stop, audit, post-exec verification) so the MCP path is not a bypass.
- Gated tools: accept an explicit `_confirm: true` argument mirroring the in-process confirmation gate.
- List all tools in a single page when count is under the hub cap — cursor pagination across SDK versions is a needless compatibility risk.
- MCP SDK model fields differ by version: read both `next_cursor`/`nextCursor`, `structured_content`/`structuredContent`, `is_error`/`isError` via getattr fallbacks.
- **Teardown hang pitfall:** if the server process spawns non-daemon helper threads (watchers, client pools), the interpreter never exits after stdin EOF, so the client's `stdio_client` teardown waits forever. End the server's `main()` with `sys.stdout.flush(); os._exit(0)` after `asyncio.run(...)`. Mirror this in the test client: write the report INSIDE the `async with` block, then `os._exit(0)` — never exit the context normally.

## Per-tool test harness
- Start the server exactly how production will start it (same command, cwd, env), `initialize`, `list_tools`, then call each tool with safe/self-reversing args.
- Alphabetical iteration breaks dependency chains (archive.list runs before archive.zip created the file). Keep a `DEFERRED` set of tools that must not run in the main loop, and a `CHAIN_AFTER` map: after tool X passes, call its dependents with args built from X's payload via a `_dig(payload, key)` helper that scans `data` and common list fields (`items`, `tasks`, `events`, `processes`, `windows`, `plans`, `todo`, `messages`) for the key. Extend `_dig`'s field list when a chain reports CHAIN_MISSING_ID.
- Gated tools: call once WITHOUT `_confirm` and require a refusal containing the confirmation error (status GATED_OK), then call again WITH it.
- Seed fixture files the chains need before the main loop (write via the server's own write tool with `_confirm` to also exercise it).
- Restore side effects via chains: mute→unmute, volume +1→-1, create→delete, open window→close window, find process→inspect→stop a sacrificial process the harness itself launched.
- Distinguish three failure classes in the report: harness arg bugs (fix the PLAN), launch-context artifacts (see windows-ssh-remote-dev skill), and legitimate tool findings (a linter tool returning "issues found" means the tool WORKS).
- Write a JSON report to disk + stream `PROGRESS <tool> <status>` lines with flush so a killed run is still diagnosable; verify the tool count in the report matches the registry count.

## Hub auto-start/auto-stop registration (HANNI MCP Hub pattern)
- Register through the manager's own API so config validation applies: `manager.add(config)` (transport stdio, command, args, cwd, `auto_connect: true`), then `manager.connect(id, approved=True, expected_config_hash=hash)` — this grants the connection consent that `reconnect_approved` later requires (`connection_approval_hash == config_hash`; startup reuses consent, never creates it).
- Pin `{'version':1,'servers':[{'id': <32hex>, 'config_hash': <64hex>}]}` in `<data_dir>/mcp/auto-connect.json` (merge, don't clobber) — the AutoConnections thread reconnects pinned servers on every boot; hub close terminates stdio children. Verify auto-stop by counting the child processes after close.
- Verify the boot path without booting the app: instantiate the manager + AutoConnections with a no-op guard, `tick()`, and assert the server shows `connected` with the expected tool count.
