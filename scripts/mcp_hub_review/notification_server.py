"""Verification-only actual SDK stdio tool-list notification server.

Only synthetic echo data and test-owned control/ledger files are used. Changing
the control JSON revision changes the original definition and sends a genuine
SDK notification; no private HANNI callback is invoked by this fixture.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.stdio import stdio_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    session = None
    notified = 0

    def revision():
        try:
            return int(json.loads(args.control.read_text(encoding='utf-8')).get('revision', 0))
        except (OSError, ValueError, TypeError):
            return 0

    def record(event, **data):
        with args.ledger.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'event':event, **data})+'\n')

    async def listed(context, params):
        nonlocal session
        session = context.session
        current = revision()
        record('list', revision=current)
        tool = types.Tool(name='mock.echo', description=f'Echo a synthetic message. Definition revision {current}.',
            inputSchema={'type':'object','properties':{'message':{'type':'string'}},
                         'required':['message'],'additionalProperties':False},
            outputSchema={'type':'object','properties':{'message':{'type':'string'}},'required':['message']})
        return types.ListToolsResult(tools=[tool])

    async def called(context, params):
        record('call', name=params.name)
        payload = {'message':(params.arguments or {}).get('message', '')}
        return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(payload))],
                                    structuredContent=payload)

    async def notify():
        nonlocal notified
        while True:
            await asyncio.sleep(.05)
            current = revision()
            if session is not None and current>notified:
                notified = current
                try:
                    await session.send_tool_list_changed()
                    record('notification', revision=current)
                except Exception as error:
                    record('notification-error', error_type=type(error).__name__)

    server = Server('Independent SDK notifications fixture', version='1.0',
                    on_list_tools=listed, on_call_tool=called)

    async def run():
        async with stdio_server() as streams:
            notifier = asyncio.create_task(notify())
            try:
                await server.run(*streams, server.create_initialization_options(
                    notification_options=NotificationOptions(tools_changed=True)))
            finally:
                notifier.cancel()
                await asyncio.gather(notifier, return_exceptions=True)
    asyncio.run(run())


if __name__=='__main__':
    main()
