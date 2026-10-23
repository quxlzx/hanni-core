"""Actual MCP SDK fixture with owned stdio/loopback HTTP and controlled facts."""
from __future__ import annotations
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from mcp import types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp_contracts import definitions

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--transport', choices=('stdio', 'http'), default='stdio')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    args.ledger.with_suffix('.pid').write_text(str(os.getpid()), encoding='utf8')
    records = {}

    def control():
        return json.loads(args.control.read_text(encoding='utf8'))

    def record(event, **fields):
        with args.ledger.open('a', encoding='utf8') as handle:
            handle.write(json.dumps({'event': event, **fields}) + '\n')
    record('process_started', pid=os.getpid(), transport=args.transport)
    watched = set()

    async def watch(session):
        revision = control().get('revision', 0)
        while True:
            await asyncio.sleep(0.05)
            fresh = control().get('revision', 0)
            if fresh != revision:
                revision = fresh
                await session.send_tool_list_changed()
                record('notification', revision=revision)

    async def listed(context, params):
        identity = id(context.session._connection)
        if identity not in watched:
            watched.add(identity)
            asyncio.create_task(watch(context.session))
        current = control()
        if current.get('list_delay'):
            await asyncio.sleep(current['list_delay'])
        offset = int(params.cursor) if params and params.cursor else 0
        tools = current.get('tools', definitions())
        record('list', cursor=offset)
        page = tools[offset:offset + 3]
        return types.ListToolsResult(tools=[types.Tool.model_validate(item) for item in page], nextCursor=str(offset + 3) if offset + 3 < len(tools) else None)

    async def called(context, params):
        current = control()
        value = params.arguments or {}
        name = params.name
        record('call', name=name, arguments=value)
        if current.get('delay'):
            await asyncio.sleep(current['delay'])
        if current.get('tool_error'):
            return types.CallToolResult(content=[types.TextContent(type='text', text='Controlled tool failure.')], isError=True)
        if name == 'prism.read_alignment':
            data = {'axis': value['axis'], 'alignment': {'x': 0.25, 'y': -0.5}[value['axis']]}
        elif name == 'prism.echo_label':
            data = {'label': value['label']}
        elif name == 'prism.sum_samples':
            data = {'total': sum(value['samples']), 'count': len(value['samples'])}
        elif name == 'prism.decode_profile':
            data = {'profile': value['profile']}
        elif name == 'prism.create_record':
            records[value['record_id']] = value['title']
            data = {'record_id': value['record_id'], 'created': True}
        elif name == 'prism.erase_record':
            data = {'record_id': value['record_id'], 'deleted': records.pop(value['record_id'], None) is not None}
        elif name == 'prism.defer_read':
            data = {'channel': value['channel'], 'complete': True}
        elif name == 'quartz.inspect_flux_band':
            band, intensity = {'AX-17': ('narrow', 0.42), 'BQ-04': ('broad', 0.18)}[value['calibration']]
            data = {'calibration': value['calibration'], 'band': band, 'intensity': intensity}
        else:
            return types.CallToolResult(content=[types.TextContent(type='text', text='Unknown local fixture capability.')], isError=True)
        if current.get('invalid_output'):
            data = {'unadvertised': True}
        record('result', name=name, data=data)
        return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(data))], structuredContent=data)

    class FixtureServer(Server):

        def create_initialization_options(self, notification_options=None, **kwargs):
            return super().create_initialization_options(notification_options or NotificationOptions(tools_changed=True), **kwargs)
    server = FixtureServer('Campaign 2 owned SDK fixture', version='2.0', on_list_tools=listed, on_call_tool=called)

    async def stdio():
        async with stdio_server() as streams:
            await server.run(*streams, server.create_initialization_options(notification_options=NotificationOptions(tools_changed=True)))
    if args.transport == 'stdio':
        asyncio.run(stdio())
        return
    session_manager = StreamableHTTPSessionManager(server, json_response=True)

    @asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    async def mcp_app(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    import uvicorn
    app = Starlette(routes=[Route('/health', lambda request: JSONResponse({'owned_fixture': True})), Mount('/mcp', app=mcp_app)], lifespan=lifespan)
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='critical', access_log=False)
if __name__ == '__main__':
    main()
