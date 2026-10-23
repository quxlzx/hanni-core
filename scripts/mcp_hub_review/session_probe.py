"""Verification-only deterministic model probe of HANNI's original MCP session.

The external server, manager, registry, retrieval and execution must be real.
Only model choice/text is deterministic. This is not local-model inference proof.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from hanni.core.orchestrator import TextSession
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.models.client import ModelToolCall, ModelTurn


@dataclass
class ProbeClient:
    """Select a test-specified identity only if original retrieval offered it."""

    wire_name: str
    arguments: dict[str, Any]
    menus: list[list[dict[str, Any]]] = field(default_factory=list)
    messages: list[list[dict[str, Any]]] = field(default_factory=list)

    def complete_with_tools(self, messages, *, tools, **kwargs):
        self.menus.append(json.loads(json.dumps(tools)))
        self.messages.append(json.loads(json.dumps(messages)))
        if len(self.menus) == 1:
            offered = {item['function']['name'] for item in tools}
            if self.wire_name not in offered:
                raise AssertionError(f'Original session did not offer imported identity {self.wire_name}')
            return ModelTurn('', (ModelToolCall('independent-mcp-probe-1',
                                               self.wire_name, self.arguments),))
        results = [item['content'] for item in messages if item.get('role') == 'tool']
        if not results:
            raise AssertionError('Original session provided no actual tool result to the model')
        return ModelTurn('Verification result: ' + results[-1])

    def chat(self, messages, **kwargs):
        raise AssertionError('Probe unexpectedly bypassed the original tool-calling session')

    def stream_chat(self, messages, **kwargs):
        raise AssertionError('Probe unexpectedly fell back without an imported tool menu')
        yield ''


def run_session_probe(registry, query: str, capability_id: str,
                      arguments: dict[str, Any], *, read_only=True):
    """Run the original model-facing retrieval and bounded session/tool loop.

    Caller separately checks the actual mock-server ledger and original audit.
    No host.call, registry.execute, tool schema or permission method is patched.
    """
    host = McpHost(registry, read_only=read_only, max_tools=8)
    decision = host.route(query)
    matches = [tool for tool in decision.tools if tool.capability_id == capability_id]
    if len(matches) != 1:
        raise AssertionError(f'Original routing did not retrieve imported capability {capability_id}')
    client = ProbeClient(matches[0].wire_name, dict(arguments))
    session = McpToolSession(TextSession(client), client, host)
    answer = ''.join(session.stream_response(query))
    return {'answer': answer, 'selected': [tool.capability_id for tool in decision.tools],
            'menus': client.menus, 'messages': client.messages,
            'disclosure': 'Deterministic model selection only; original host/session/registry execution. Caller must verify real MCP server and audit evidence.'}
