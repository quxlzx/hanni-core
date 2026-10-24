---
name: official-mcp-sdk-2-server
description: Use when building MCP servers on the official mcp SDK 2.x.
tags: [mcp, sdk, stdio, testing]
related_skills: [mcp-server-selftest, fastmcp-local-apps]
---

# Official MCP Python SDK 2.x (mcp package, not fastmcp)

## When to Use
Building an MCP server that must use the official `mcp` PyPI package (2.x), or testing one with a real client.

## API facts (verified on mcp 2.3.0)
- `from mcp.server.mcpserver import MCPServer` — FastMCP was RENAMED in 2.x; `mcp.server.fastmcp` raises a ModuleNotFoundError with a migration hint. Pin `mcp>=2,<3`.
- `@server.tool()` decorator and `run(transport="stdio")` work like FastMCP; streamable-http takes `run(transport="streamable-http", host=..., port=...)`.
- Client results use SNAKE_CASE: `result.is_error`, `result.structured_content` (often None for dict returns — parse JSON from `result.content[0].text` instead).
- Raise `mcp.server.mcpserver.exceptions.ToolError` for anticipated failures: client gets `is_error=True` WITH your message. A plain ValueError becomes UnexpectedToolError and the client only sees "Error executing tool <name>" — the message is lost.

## Client-test pitfalls (pytest-asyncio + anyio)
- Do NOT put `stdio_client`/`ClientSession` in an async-generator fixture: teardown raises "Attempted to exit cancel scope in a different task". Open the full client lifecycle INSIDE each test via an `@contextlib.asynccontextmanager` helper.
- Launch the server child with `StdioServerParameters(command=sys.executable, args=["-m","pkg.cli"])` and pass config through `env=`.

## Packaging
- hatchling refuses to build when README.md referenced in pyproject is missing — write docs before first `pip install -e .`.
