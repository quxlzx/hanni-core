"""Disposable original desktop backend; unsafe dependencies remain unavailable.

This is CONTROLLED evidence. Original production services own all responses and
SQLite mutations. No synthetic HTTP projections or live-model answers exist.
"""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
import hashlib
import http.client
import json
from pathlib import Path
import socket
import subprocess
import threading
import time
from unittest.mock import patch
import psutil
REPO = Path(__file__).resolve().parents[2]

class EmptyGoogleVault:
    """Explicit dependency; never construct/read Windows Credential Manager."""

    def get(self, account):
        return None

    def labels(self):
        return ('personal', 'school')

    def preferences(self):
        return {}

def fixture_config(root):
    from hanni.config.loader import load_config
    config = load_config(REPO / 'config', data_dir=root, env={})
    models = tuple((replace(m, endpoint='http://127.0.0.1:1', model_file=str(root / 'unavailable-fixture-model.gguf'), health_timeout_seconds=1, request_timeout_seconds=2) for m in config.models.models))
    return replace(config, models=replace(config.models, models=models))

def source_hashes():
    paths = ['src/hanni/dashboard/server.py', 'src/hanni/dashboard/chat.py', 'src/hanni/dashboard/features.py', 'src/hanni/dashboard/productivity.py', 'src/hanni/dashboard/memory.py', 'src/hanni/dashboard/workflows.py', 'src/hanni/dashboard/static/app.js', 'src/hanni/dashboard/static/style.css']
    return {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in paths}

class OriginalBackend:

    def __init__(self, root, *, stack, port=0):
        if type(port) is not int or (port != 0 and (not 1024 <= port <= 65535)):
            raise ValueError('Use zero or a bounded owned loopback port.')
        if port in {8765, 8080}:
            raise ValueError('The existing owner dashboard/model ports are excluded.')
        self.root = Path(root).resolve()
        if self.root.exists():
            raise ValueError('A fresh disposable backend directory is required.')
        self.root.mkdir(parents=True)
        self.fixture_stack = stack
        self.config = fixture_config(self.root)
        self.calls = []
        self.stop = threading.Event()
        self.server = None
        self.thread = None
        self.closed = False
        self.before = source_hashes()
        from hanni.tools.google_access import GoogleAccess
        original_init = GoogleAccess.__init__

        def isolated_init(access, vault=None, transport=None, timezone_name=None):
            original_init(access, EmptyGoogleVault(), transport, timezone_name)
        stack.enter_context(patch.object(GoogleAccess, '__init__', isolated_init))
        original_connect = socket.socket.connect

        def owned_connect(sock, address):
            if self.server is not None and isinstance(address, tuple) and (address[0] in {'127.0.0.1', 'localhost', '::1'}) and (address[1] == self.server.server_port):
                return original_connect(sock, address)
            self.calls.append({'dependency': 'network', 'outcome': 'CONTROLLED_UNAVAILABLE'})
            raise OSError('Campaign fixture has no external or model network authority.')
        stack.enter_context(patch.object(socket.socket, 'connect', owned_connect))

        def unavailable_run(command, *args, **kwargs):
            self.calls.append({'dependency': 'subprocess.run', 'outcome': 'CONTROLLED_UNAVAILABLE'})
            output = '' if kwargs.get('text') or kwargs.get('encoding') else b''
            result = subprocess.CompletedProcess(command, 127, stdout=output, stderr=output)
            if kwargs.get('check'):
                raise subprocess.CalledProcessError(127, command, output=output, stderr=output)
            return result

        def unavailable_popen(*args, **kwargs):
            self.calls.append({'dependency': 'subprocess.Popen', 'outcome': 'CONTROLLED_UNAVAILABLE'})
            raise OSError('Campaign fixture forbids external processes and model startup.')
        stack.enter_context(patch.object(subprocess, 'run', unavailable_run))
        stack.enter_context(patch.object(subprocess, 'Popen', unavailable_popen))
        import os
        if hasattr(os, 'startfile'):
            stack.enter_context(patch.object(os, 'startfile', unavailable_popen))
        import sounddevice
        stack.enter_context(patch.object(sounddevice, 'InputStream', unavailable_popen))
        stack.enter_context(patch.object(sounddevice, 'OutputStream', unavailable_popen))
        from hanni.dashboard.cluster import NODES
        compute_root = self.root / 'compute'
        compute_root.mkdir()
        (compute_root / 'deployment.json').write_text(json.dumps({'version': 1, 'enabled': False, 'nodes': [asdict(n) for n in NODES], 'workers': []}), encoding='utf8', newline='\n')
        from hanni.tools.registry import build_default_registry
        from hanni.dashboard.features import DesktopFeatures
        from hanni.dashboard.chat import ChatHub
        from hanni.dashboard.server import DashboardServer, Telemetry
        self.registry = build_default_registry(self.config, data_dir=self.root)
        self.registry.google_access._vault = EmptyGoogleVault()
        self.features = DesktopFeatures(self.config, registry=self.registry)
        self.chat = ChatHub(self.root / 'campaign-chat.sqlite3')
        self.telemetry = Telemetry(self.config)
        self.server = DashboardServer(port, self.telemetry, self.chat, shutdown_event=self.stop, features=self.features)
        self.thread = threading.Thread(target=self.server.serve_forever, name='campaign8-owned-http', daemon=True)
        self.thread.start()
        self.telemetry.start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}'

    def ready(self):
        process = psutil.Process()
        return {'url': self.url, 'pid': process.pid, 'create_time': process.create_time(), 'root': self.root.as_posix(), 'evidence_class': 'CONTROLLED', 'scope': 'Original DashboardServer/Features/ChatHub/Telemetry with disposable stores; empty Google vault; unsafe network/process/audio dependencies unavailable; no inference controller attached.', 'source_before': self.before, 'native_launched': False, 'chat_controller_attached': False, 'model_generation': False}

    def request(self, path, *, method='GET', body=None, authorized=True, origin=None):
        headers = {'Origin': origin or self.url}
        if authorized:
            headers['X-Hanni-Token'] = self.chat.token
        wire = None
        if body is not None:
            wire = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        try:
            connection.request(method, path, body=wire, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            return (response.status, json.loads(payload) if payload else None)
        finally:
            connection.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        self.telemetry.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(15)
        self.chat.close()
        self.chat.db.close()

@contextmanager
def original_backend(root, *, port=0):
    with ExitStack() as stack:
        backend = OriginalBackend(root, stack=stack, port=port)
        try:
            yield backend
        finally:
            backend.close()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--seed', choices=['original-populated', 'original-populated-dense', 'original-task-fidelity', 'original-safe-gaps', 'original-lab-controls', 'original-mcp-tool-controls'])
    parser.add_argument('--port', type=int, default=0, help='Owned isolated loopback port; default auto. Existing owner ports excluded.')
    args = parser.parse_args()
    if not 1 <= args.timeout <= 1800:
        raise ValueError('Use a bounded timeout of at most 1800 seconds.')
    with original_backend(args.root, port=args.port) as backend:
        if args.seed:
            from .seed import populate, populate_dense, populate_task_fidelity, populate_safe_gaps
            seeders = {'original-populated': populate, 'original-populated-dense': populate_dense, 'original-task-fidelity': populate_task_fidelity, 'original-safe-gaps': populate_safe_gaps, 'original-lab-controls': populate, 'original-mcp-tool-controls': populate}
            seeded = seeders[args.seed](backend)
            if args.seed == 'original-lab-controls':
                from .lab_controls import install_delay
                seeded['lab_controls'] = install_delay(backend, backend.fixture_stack)
            if args.seed == 'original-mcp-tool-controls':
                from .inert_mcp import configure
                seeded['mcp_tool_controls'] = configure(backend, tool_metadata=True)
            (backend.root / 'SEEDED.json').write_text(json.dumps(seeded, indent=2) + '\n', encoding='utf8', newline='\n')
        ready = backend.ready()
        path = backend.root / 'READY.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(ready, indent=2) + '\n', encoding='utf8', newline='\n')
        temporary.replace(path)
        print(json.dumps(ready), flush=True)
        backend.stop.wait(args.timeout)
        backend.close()
        result = {'source_before': backend.before, 'source_after': source_hashes(), 'http_closed': not backend.thread.is_alive(), 'chat_closed': backend.chat.closed, 'dependency_calls': backend.calls, 'lab_control_calls': getattr(backend, 'lab_control_calls', []), 'owner_runtime_modified': False}
        (backend.root / 'CLOSED.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
if __name__ == '__main__':
    main()
