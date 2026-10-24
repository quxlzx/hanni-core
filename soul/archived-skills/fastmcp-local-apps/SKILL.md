---
name: fastmcp-local-apps
description: "Use when building a local tracker app that is also an MCP."
version: 1.0.0
license: MIT
author: Hermes Agent
metadata:
  hermes:
    tags: [mcp, fastmcp, webui, sqlite, tools]
    related_skills: [hermes-agent, hermes-fleet-deployment]
---

# FastMCP local apps (one port: MCP tools + REST + browser UI)

## When to Use
User asks for a personal tracker/app (homework, habits, inventory) they can view in a browser AND that the agent can read/write via MCP. One process, one port, one SQLite file.

## Pattern (verified end-to-end)
1. Single `server.py`: `FastMCP("<name>")`, SQLite next to the script, tools as `@mcp.tool(name="<domain>_<verb>")` returning JSON strings; browser side via `@mcp.custom_route("/api/...", methods=[...])` async handlers + a `HTMLResponse` single-page UI at `/` that fetches the same REST routes. Run: `mcp.run(transport="streamable-http", host="0.0.0.0", port=<P>, path="/mcp")`.
2. venv beside it: `python3 -m venv .venv && .venv/bin/pip install "fastmcp>=2"` (some Ubuntu images need `apt install python3-venv` first).
3. systemd USER unit (`Restart=on-failure`, `WantedBy=default.target`), `systemctl --user enable --now` — survives reboots with linger.
4. Register with Hermes: `hermes config set mcp_servers.<name>.url http://127.0.0.1:<P>/mcp` (+ `.timeout`). Takes effect in NEW sessions, not the current one — say so.
5. Give the user the LAN and Tailscale URLs for `/` (the UI).

## Verification order (do all three)
1. REST: `curl /api/<resource>` GET + POST one seeded row.
2. MCP over raw JSON-RPC: initialize (capture `Mcp-Session-Id` header) → `notifications/initialized` → `tools/list` → one `tools/call`. Subsequent calls MUST carry the session header.
3. Report both surfaces working with evidence, and seed one example row so the UI is visibly alive.
   Raw-JSON-RPC test client must tolerate an EMPTY 202 body for `notifications/initialized` (json.loads("") crashes) and check `"\ndata: "` before `body.startswith("data: ")` for SSE frames.

## Pitfalls
- Tool names need a domain prefix (`homework_add`, not `add`) — the agent's tool list is shared across servers.
- Keep the UI zero-build (one HTML string, vanilla JS, auto-refresh ~15s) — no node/npm, nothing to rot.
- SQLite `datetime('now','localtime')` default for created; compute overdue in the API layer (compare to local today), not via SQL string compares.
- templates/homework-app.py is the proven starting point — copy and rename the domain.
