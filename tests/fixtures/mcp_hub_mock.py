"""Real SDK MCP fixture. Only loopback/stdio; test-owned files and no external services."""
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
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route
TOOLS = [{'name': 'mock.get_status', 'description': 'Get the integration fixture current status.', 'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'status': {'type': 'string'}}, 'required': ['status']}, 'annotations': {'readOnlyHint': True}}, {'name': 'mock.echo', 'description': 'Echo a supplied fixture message without changes.', 'inputSchema': {'type': 'object', 'properties': {'message': {'type': 'string', 'maxLength': 500}}, 'required': ['message'], 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'message': {'type': 'string'}}, 'required': ['message']}, '_meta': {'fixture': 'echo-v1'}}, {'name': 'mock.create_record', 'description': 'Create a test record in the fixture ledger.', 'inputSchema': {'type': 'object', 'properties': {'title': {'type': 'string', 'minLength': 1}}, 'required': ['title'], 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'created': {'type': 'boolean'}, 'title': {'type': 'string'}}, 'required': ['created', 'title']}, 'annotations': {'readOnlyHint': False, 'destructiveHint': False}}]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--transport', choices=['stdio', 'http'], default='stdio')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    args.ledger.with_suffix('.pid').write_text(str(os.getpid()), encoding='utf-8')

    def control():
        try:
            return json.loads(args.control.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def record(event, **fields):
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        with args.ledger.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'event': event, **fields}) + '\n')
    watching = set()

    async def watch(session):
        revision = control().get('notify_revision', 0)
        while True:
            await asyncio.sleep(0.1)
            current = control().get('notify_revision', 0)
            if current != revision:
                revision = current
                try:
                    await session.send_tool_list_changed()
                    record('notification', revision=revision)
                except Exception:
                    return

    async def listed(context, params):
        if id(context.session) not in watching:
            watching.add(id(context.session))
            asyncio.create_task(watch(context.session))
        current = control()
        definitions = current.get('tools', TOOLS)
        offset = int(params.cursor) if params and params.cursor else 0
        record('list', cursor=offset)
        if current.get('list_delay'):
            await asyncio.sleep(current['list_delay'])
        page = definitions[offset:offset + 2]
        return types.ListToolsResult(tools=[types.Tool.model_validate(raw) for raw in page], nextCursor=str(offset + 2) if offset + 2 < len(definitions) else None)

    async def called(context, params):
        current = control()
        record('call', name=params.name)
        if current.get('delay'):
            await asyncio.sleep(current['delay'])
        if current.get('error'):
            return types.CallToolResult(content=[types.TextContent(type='text', text='Fixture execution failed.')], isError=True)
        arguments = params.arguments or {}
        if params.name == 'mock.get_status':
            data = {'status': 'ok'}
        elif params.name == 'mock.echo':
            data = {'message': arguments.get('message', '')}
        elif params.name == 'mock.create_record':
            data = {'created': True, 'title': arguments.get('title', '')}
        else:
            data = {'original_name': params.name, 'arguments': arguments}
        if current.get('invalid_output'):
            data = {'unexpected': True}
        if current.get('large_output'):
            data = {'message': 'x' * current['large_output']}
        return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(data))], structuredContent=data)
    server = Server('HANNI MCP integration fixture', version='1.0', on_list_tools=listed, on_call_tool=called)

    async def run_stdio():
        async with stdio_server() as streams:
            await server.run(*streams, server.create_initialization_options(notification_options=NotificationOptions(tools_changed=True)))
    if args.transport == 'stdio':
        asyncio.run(run_stdio())
        return
    manager = StreamableHTTPSessionManager(server, json_response=True)

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    async def health(request):
        return JSONResponse({'fixture': True})

    async def redirect(request):
        return RedirectResponse(control().get('redirect', '/health'), status_code=307)

    async def mcp_route(scope, receive, send):
        required = control().get('require_bearer')
        headers = dict(scope.get('headers', []))
        if required and headers.get(b'authorization') != ('Bearer ' + required).encode():
            await JSONResponse({'error': 'Authentication required'}, status_code=401)(scope, receive, send)
            return
        await manager.handle_request(scope, receive, send)
    from starlette.routing import Mount
    app = Starlette(routes=[Route('/health', health), Route('/redirect', redirect, methods=['GET', 'POST', 'DELETE']), Mount('/mcp', app=mcp_route)], lifespan=lifespan)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='critical', access_log=False)
if __name__ == '__main__':
    main()
