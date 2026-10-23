"""Official MCP v2 server facade for HANNI's validated local capability layer.

This module intentionally exposes only read-only capability calls. It is not
started automatically yet; the in-process HANNI host uses the same contracts.
Future LocalForge/server integrations can connect through standard MCP transports.
"""
from __future__ import annotations

from typing import Any

from hanni.mcp.host import McpHost


def create_local_mcp_server(registry):
    # Imported lazily so repository analysis/tests can run before optional/runtime
    # dependencies are installed. pyproject installs MCP v2 for real deployments.
    from mcp.server import MCPServer

    host = McpHost(registry, read_only=True, max_tools=8,
                   allowed_actions=("google_calendar.create",))
    server = MCPServer("HANNI Local Computer")

    @server.tool(name="capability_search", description="Find read-only HANNI computer capabilities relevant to a request.")
    def capability_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
        tools = host.select_tools(query)[: max(1, min(limit, 5))]
        return [
            {"id": t.capability_id, "description": t.description, "input_schema": dict(t.input_schema), "risk": t.risk}
            for t in tools
        ]

    @server.tool(name="capability_get", description="Get the schema for one read-only HANNI capability.")
    def capability_get(capability_id: str) -> dict[str, Any]:
        definition = registry.get(capability_id)
        if not host._allowed(definition):
            return {"ok": False, "error": "Capability is not exposed by the read-only HANNI MCP server."}
        schema = registry.capabilities.get(capability_id)
        return {"ok": True, "capability": schema}

    @server.tool(name="capability_call", description="Call one validated read-only HANNI computer capability.")
    def capability_call(capability_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        candidates = {t.capability_id: t for t in host.select_tools(capability_id)}
        tool = candidates.get(capability_id)
        if tool is None:
            definition = registry.get(capability_id)
            if not host._allowed(definition):
                return {"ok": False, "error": "Capability is not exposed by the read-only HANNI MCP server."}
            from hanni.tools.capabilities import describe
            cap = describe(definition)
            from hanni.tools.capability_api import risk_of
            from hanni.mcp.host import McpTool
            tool = McpTool("local-computer", cap.name, host._wire_name(cap.name), cap.description,
                           cap.argument_schema, risk_of(cap))
        return host.call(tool, arguments)

    return server
