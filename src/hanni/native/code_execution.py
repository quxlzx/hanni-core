"""Bounded Python orchestration using authenticated calls to the scoped registry.

This is an owned subprocess, not an OS sandbox. Every tool RPC retains the
normal per-action authorization and durable receipt policy.
"""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time

CLIENT = '''import json, os, urllib.request
def call(name, arguments=None):
    data = json.dumps({"name": name, "arguments": arguments or {}}).encode()
    request = urllib.request.Request(os.environ["HANNI_TOOL_RPC"], data=data,
        headers={"Authorization": "Bearer " + os.environ["HANNI_TOOL_RPC_KEY"], "Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=300) as response:
        return json.load(response)
'''


def run_code(code, *, runtime, call_id, workspace, cancelled, timeout=60, max_calls=24):
    from ..logs.redaction import redact_text, register_secret
    token = secrets.token_urlsafe(32)
    register_secret('tool-rpc-' + call_id, token)
    gate = threading.Lock()
    counts = {'calls': 0}
    done = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != '/' or not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32768:
                    raise ValueError('RPC request exceeds limit.')
                request = json.loads(self.rfile.read(length))
                with gate:
                    if done.is_set() or cancelled() or counts['calls'] >= max_calls:
                        raise ValueError('Script stopped or tool-call budget exhausted.')
                    if set(request) != {'name', 'arguments'} or request['name'] in {'execute_code', 'delegate_task'}:
                        raise ValueError('Recursive orchestration is unavailable inside scripts.')
                    counts['calls'] += 1
                    from .runtime import cancellation_scope
                    with cancellation_scope(lambda: done.is_set() or cancelled()):
                        receipt = runtime.call(request['name'], request['arguments'], f'{call_id}:rpc:{counts["calls"]}')
                wire = json.dumps(receipt).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(wire)))
                self.end_headers()
                self.wfile.write(wire)
            except Exception as exc:
                wire = json.dumps({'ok': False, 'error': redact_text(str(exc))[:300]}).encode()
                self.send_response(400)
                self.send_header('Content-Length', str(len(wire)))
                self.end_headers()
                try:
                    self.wfile.write(wire)
                except OSError:
                    pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
    thread.start()
    process = None
    job = None
    captures = {'stdout': bytearray(), 'stderr': bytearray()}
    sizes = {'stdout': 0, 'stderr': 0}
    readers = []
    reason = None
    try:
        Path(workspace).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='hanni-code-') as folder:
            Path(folder, 'hanni_tools.py').write_text(CLIENT, encoding='utf-8')
            script = Path(folder, 'task.py')
            script.write_text(code, encoding='utf-8')
            env = {**os.environ, 'HANNI_TOOL_RPC': f'http://127.0.0.1:{server.server_port}/', 'HANNI_TOOL_RPC_KEY': token}
            if os.name == 'nt':
                from .lifecycle import WindowsJob
                job = WindowsJob()
                # Suspend until the kernel owns the tree, so a fast snippet
                # cannot spawn a child before assignment to the job.
                flags = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004}
            else:
                flags = {'start_new_session': True}
            process = subprocess.Popen([sys.executable, '-u', str(script)], cwd=workspace,
                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **flags)
            if job is not None:
                import ctypes
                from ctypes import wintypes
                job.assign(process)
                resume = ctypes.WinDLL('ntdll').NtResumeProcess
                resume.argtypes = [wintypes.HANDLE]
                resume.restype = ctypes.c_long
                if resume(int(process._handle)) != 0:
                    raise OSError('Could not resume the owned script process.')
            def drain(label, stream):
                while block := stream.read(4096):
                    sizes[label] += len(block)
                    captures[label].extend(block[:max(0, 8000 - len(captures[label]))])
                stream.close()
            for label in captures:
                reader = threading.Thread(target=drain, args=(label, getattr(process, label)), daemon=True)
                reader.start()
                readers.append(reader)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancelled() or time.monotonic() >= deadline:
                    reason = 'cancelled' if cancelled() else 'time_limit'
                    done.set()
                    if os.name == 'nt':
                        job.close()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                    break
                time.sleep(.05)
            # Normal script exit must also release owned background children.
            # Close before joining readers: a descendant may hold a pipe open.
            if job is not None:
                job.close()
            elif process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for reader in readers:
                reader.join(timeout=2)
        return {'ok': not reason and process.returncode == 0,
                'message': reason or f'Python exited {process.returncode}',
                'data': {**{key: redact_text(bytes(value).decode('utf-8', errors='replace')) for key, value in captures.items()},
                         'exit_code': process.returncode, 'tool_calls': counts['calls'],
                         'truncated': any(sizes[k] > 8000 for k in sizes), 'full_tool_receipts_saved': True}}
    finally:
        done.set()
        if job is not None:
            job.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        # Waiting-for-approval callbacks observe the scoped cancellation before
        # their task store is closed by the worker.
        with gate:
            pass
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
