"""Original components with explicit controlled dependency seams.

No owner deployment, credentials, sockets, SSH processes, or service lifecycle
are used. Credential-shaped values are generated in memory and never emitted.
"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from hanni.compute.registry import ComputeRegistry
from hanni.compute.transport import InferenceTransport
GIB = 1024 ** 3
GPU = 'GPU-12345678-1234-1234-1234-123456789abc'

def deployment(root):
    directory = Path(root) / 'compute'
    directory.mkdir(parents=True, exist_ok=True)
    raw = {'version': 1, 'enabled': True, 'nodes': [{'id': 'owned-fixture', 'name': 'Controlled fixture', 'emoji': '', 'lan_ip': '' + '.'.join(('10', '42', '0', '5')) + '', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '19')) + '', 'username': 'fixture'}], 'workers': [{'worker_id': 'c6-worker', 'node_id': 'owned-fixture', 'model_id': 'c6-synthetic-model', 'enabled': True, 'remote_port': 16101, 'context_configured': 8192, 'allowed_categories': ['synthetic'], 'concurrency': 1, 'startup': {'gpu_device': GPU}}], 'policy': {}}
    path = directory / 'deployment.json'
    path.write_text(json.dumps(raw), encoding='utf8', newline='\n')
    registry = ComputeRegistry(root)
    return (path, raw, registry, InferenceTransport(registry))

def replace_config(path, raw, registry):
    path.write_text(json.dumps(raw), encoding='utf8', newline='\n')
    registry.reload()

def sample():
    return {'os': 'Linux', 'cpu': 'Controlled CPU', 'logical_cpu_count': 8, 'ram_total_bytes': 16 * GIB, 'ram_available_bytes': 8 * GIB, 'gpus': [{'id': GPU, 'name': 'Controlled GPU', 'vram_total_bytes': 12 * GIB, 'vram_free_bytes': 6 * GIB, 'utilization_percent': 25}], 'storage_free_bytes': 32 * GIB, 'python_version': '3.12.0'}

def mock_resources(monkeypatch, transport, frames):
    calls = []
    iterator = iter(deepcopy(frames))
    monkeypatch.setattr(transport, '_address', lambda node: node['lan_ip'])
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kw: ['fixture-ssh', address])

    def run(command, **kwargs):
        calls.append({'address': command[1], 'operation': command[-1]})
        return SimpleNamespace(returncode=0, stdout=json.dumps(next(iterator)).encode())
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', run)
    return calls

class ControlledSocket:
    """A socket dependency object; never opens a real socket."""
    port = 16191

    def __init__(self, *args, **kwargs):
        self.bound = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def bind(self, value):
        self.bound = value

    def getsockname(self):
        return ('127.0.0.1', self.port)

    def close(self):
        pass

class ControlledProcess:
    """No OS PID or process is created; cleanup is a recorded leaf request."""

    def __init__(self, command):
        self.command = command
        self.stopped = False

    def poll(self):
        return 0 if self.stopped else None

def mock_tunnels(monkeypatch, transport):
    created, cleaned = ([], [])
    monkeypatch.setattr(transport, '_address', lambda node: node['lan_ip'])
    monkeypatch.setattr(transport, '_ssh', lambda node, address, **kw: ['fixture-ssh', node['username'], address, kw.get('forward')])
    monkeypatch.setattr('hanni.compute.transport.socket.socket', ControlledSocket)
    monkeypatch.setattr('hanni.compute.transport.socket.create_connection', lambda *args, **kwargs: ControlledSocket())

    def create(command, **kwargs):
        process = ControlledProcess(command)
        created.append(process)
        return process

    def stop(process):
        process.stopped = True
        cleaned.append(process)
    monkeypatch.setattr('hanni.compute.transport.subprocess.Popen', create)
    monkeypatch.setattr('hanni.dashboard.cluster._stop_process', stop)
    return (created, cleaned)
