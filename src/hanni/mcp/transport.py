"""Official SDK connections with bounded lifetime and DNS-pinned HTTP transport."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
from contextlib import AsyncExitStack
import os
import ssl
import threading

from hanni.mcp.security import (MCPAuthenticationRequired, MCPConfigurationError,
                                MAX_DISCOVERY, MAX_RESULT, MAX_TOOLS, endpoint, json_copy,
                                protect_sdk_diagnostics, resolve_credentials)


class AsyncRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name='HANNI-MCP', daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        self.loop.close()

    def submit(self, operation):
        return asyncio.run_coroutine_threadsafe(operation, self.loop)

    def close(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)


def guarded_http_transport(target):
    import httpcore2
    import httpx2
    from httpcore2._backends.anyio import AnyIOBackend

    class PinnedBackend(httpcore2.AsyncNetworkBackend):
        def __init__(self): self.delegate = AnyIOBackend()

        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            if host != target['host'] or port != target['port']:
                raise MCPConfigurationError('Connection origin changed.')
            last = None
            for address in target['addresses']:
                try:
                    return await self.delegate.connect_tcp(address, port, timeout, local_address, socket_options)
                except (OSError, httpcore2.ConnectError, httpcore2.ConnectTimeout) as exc: last = exc
            raise last or MCPConfigurationError('Endpoint has no approved addresses.')

        async def connect_unix_socket(self, *args, **kwargs):
            raise MCPConfigurationError('Unix socket transport is not permitted.')

        async def sleep(self, seconds): await self.delegate.sleep(seconds)

    class LimitedStream(httpx2.AsyncByteStream):
        def __init__(self, stream): self.stream, self.total = stream, 0
        async def __aiter__(self):
            async for chunk in self.stream:
                self.total += len(chunk)
                if self.total > MAX_DISCOVERY + MAX_RESULT:
                    raise MCPConfigurationError('MCP response exceeds the supported size.')
                yield chunk
        async def aclose(self): await self.stream.aclose()

    class GuardedTransport(httpx2.AsyncHTTPTransport):
        def __init__(self):
            super().__init__(trust_env=False)
            # The public HTTPX transport API accepts no network_backend; configure
            # its public httpcore pool with pinned addresses while retaining TLS SNI.
            self._pool = httpcore2.AsyncConnectionPool(
                ssl_context=ssl.create_default_context(), network_backend=PinnedBackend(),
                max_connections=4, max_keepalive_connections=2, retries=0)

        async def handle_async_request(self, request):
            parsed = request.url
            original = endpoint(target['url']) if parsed.scheme == 'https' else endpoint(target['url'], allow_local_http=True)
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            if (parsed.host != original['host'] or port != original['port']
                    or parsed.scheme != target['url'].split(':', 1)[0]):
                raise MCPConfigurationError('MCP request attempted an unapproved origin.')
            response = await super().handle_async_request(request)
            if 300 <= response.status_code < 400:
                await response.aclose()
                raise MCPConfigurationError('MCP endpoint redirects are not permitted.')
            if response.status_code in {401, 403}:
                await response.aclose()
                raise MCPAuthenticationRequired('MCP server requires valid authentication.')
            response.stream = LimitedStream(response.stream)
            return response

    return GuardedTransport()


class SDKConnection:
    """One task owns SDK contexts; operations are serialized and cancellable."""
    def __init__(self, runtime, config, *, changed=None, env=None, vault=None):
        self.runtime, self.config = runtime, config
        self.changed, self.env, self.vault = changed, env, vault
        self.ready = Future()
        self.queue = None
        self.closed = False
        self.protected_values = ()
        self.finished = threading.Event()
        self.worker = runtime.submit(self._serve())
        self.active_task, self.active_call = None, None

    def wait_ready(self):
        try: return self.ready.result(timeout=self.config['timeout_seconds'] + 3)
        except BaseException:
            self.close()
            raise

    async def _serve(self):
        from mcp import ClientSession, StdioServerParameters, types
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client
        protect_sdk_diagnostics()
        self.queue = asyncio.Queue(maxsize=64)
        try:
            child_env, headers = resolve_credentials(self.config, env=self.env, vault=self.vault)
            self.protected_values = tuple(child_env.values()) + tuple(
                value.removeprefix('Bearer ') for value in headers.values())
            async with AsyncExitStack() as stack:
                if self.config['transport'] == 'stdio':
                    stderr = stack.enter_context(open(os.devnull, 'w'))
                    streams = await stack.enter_async_context(stdio_client(StdioServerParameters(
                        command=self.config['command'], args=self.config['args'], cwd=self.config['cwd'],
                        env=child_env), errlog=stderr))
                else:
                    import httpx2
                    target = await asyncio.to_thread(endpoint, self.config['url'],
                        allow_local_http=self.config['allow_local_http'], resolve=True)
                    client = await stack.enter_async_context(httpx2.AsyncClient(
                        headers=headers, transport=guarded_http_transport(target), trust_env=False,
                        follow_redirects=False, timeout=self.config['timeout_seconds']))
                    streams = await stack.enter_async_context(streamable_http_client(self.config['url'], http_client=client))

                async def message(message):
                    if isinstance(message, types.ToolListChangedNotification) and self.changed:
                        self.changed()
                session = await stack.enter_async_context(ClientSession(
                    *streams, read_timeout_seconds=self.config['timeout_seconds'], message_handler=message))
                async with asyncio.timeout(self.config['timeout_seconds']):
                    initialized = await session.initialize()
                self.ready.set_result(initialized.model_dump(mode='json', by_alias=True, exclude_none=True))
                while True:
                    try:
                        method, arguments, future = await asyncio.wait_for(self.queue.get(), timeout=1)
                    except TimeoutError:
                        async with asyncio.timeout(min(3, self.config['timeout_seconds'])):
                            await session.send_ping()
                        continue
                    if method == 'close':
                        if not future.done(): future.set_result(None)
                        break
                    if future.cancelled(): continue
                    task = asyncio.create_task(self._dispatch(session, method, arguments))
                    self.active_task = task
                    self.active_call = arguments.get('name') if method == 'call' else None
                    future.add_done_callback(lambda completed, running=task: running.cancel() if completed.cancelled() else None)
                    try:
                        async with asyncio.timeout(self.config['timeout_seconds']): result = await task
                        if not future.done(): future.set_result(result)
                    except asyncio.CancelledError:
                        if not future.done(): future.cancel()
                        if self.closed: raise
                    except Exception as exc:
                        if not future.done(): future.set_exception(exc)
                    finally:
                        self.active_task, self.active_call = None, None
        except BaseException as exc:
            if not self.ready.done(): self.ready.set_exception(exc)
            raise
        finally:
            self.closed = True
            if self.queue:
                while not self.queue.empty():
                    _, _, future = self.queue.get_nowait()
                    if not future.done(): future.set_exception(ConnectionError('MCP connection is closed.'))
            self.finished.set()

    async def _dispatch(self, session, method, arguments):
        from mcp import types
        if method == 'list':
            tools, cursor, seen, size = [], None, set(), 0
            for _ in range(32):
                page = await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor) if cursor else None)
                for tool in page.tools:
                    raw = tool.model_dump(mode='json', by_alias=True, exclude_none=True)
                    raw = json_copy(raw)
                    import json
                    size += len(json.dumps(raw).encode('utf-8'))
                    if size > MAX_DISCOVERY or len(tools) >= MAX_TOOLS:
                        raise MCPConfigurationError('MCP discovery exceeds the supported tool limit.')
                    tools.append(raw)
                cursor = page.next_cursor
                if not cursor: return tools
                if cursor in seen: raise MCPConfigurationError('MCP discovery returned a repeated pagination cursor.')
                seen.add(cursor)
            raise MCPConfigurationError('MCP discovery exceeded the pagination limit.')
        if method == 'call':
            arguments['admit']()
            try:
                result = await session.call_tool(arguments['name'], arguments['arguments'],
                                                 read_timeout_seconds=self.config['timeout_seconds'])
            except RuntimeError as exc:
                text = str(exc)
                if text.startswith('Invalid structured content returned by tool ') or 'output schema but did not return' in text:
                    from hanni.tools.base import ToolError
                    raise ToolError('MCP structured result does not match the approved output schema.') from None
                raise
            return json_copy(result.model_dump(mode='json', by_alias=True, exclude_none=True), limit=MAX_RESULT)
        raise MCPConfigurationError('Unknown MCP transport operation.')

    async def _request(self, method, arguments):
        if self.closed or self.queue is None: raise ConnectionError('MCP connection is closed.')
        future = asyncio.get_running_loop().create_future()
        self.queue.put_nowait((method, arguments, future))
        return await future

    def request(self, method, arguments=None):
        pending = self.runtime.submit(self._request(method, arguments or {}))
        try: return pending.result(timeout=self.config['timeout_seconds'] + 3)
        except BaseException:
            pending.cancel()
            raise

    def cancel_tools(self, names):
        def cancel():
            if self.active_task and self.active_call in names:
                self.active_task.cancel()
        self.runtime.loop.call_soon_threadsafe(cancel)

    def signal_close(self):
        self.closed = True
        # Canceling the owner task enters SDK cancellation-shielded subprocess cleanup.
        self.worker.cancel()

    def close(self):
        if self.finished.is_set(): return
        self.signal_close()
        self.finished.wait(timeout=8)
