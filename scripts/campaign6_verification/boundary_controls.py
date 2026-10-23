"""Independent exposed-development fixtures retaining original implementations."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.compute.transport import InferenceTransport
GIB = 1024 ** 3
DEVICE = 'GPU-abcdef12-3456-7890-abcd-0123456789ab'

@contextmanager
def environment(root, clock=lambda: 7000.0):
    path = Path(root) / 'compute/deployment.json'
    path.parent.mkdir(parents=True)
    data = {'version': 1, 'enabled': True, 'nodes': [{'id': 'probe-node', 'lan_ip': '' + '.'.join(('10', '42', '0', '7')) + '', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '23')) + '', 'username': 'observer'}], 'workers': [{'worker_id': 'probe-worker', 'node_id': 'probe-node', 'enabled': True, 'model_id': 'controlled-protocol-model', 'remote_port': 17131, 'allowed_categories': ['synthetic'], 'capabilities': ['analysis'], 'context_configured': 8192, 'startup': {'gpu_device': DEVICE}}], 'policy': {}}
    path.write_text(json.dumps(data), encoding='utf-8')
    registry = ComputeRegistry(root, clock=clock)
    transport = InferenceTransport(registry)
    try:
        yield SimpleNamespace(path=path, data=data, registry=registry, transport=transport, worker=lambda: registry.worker('probe-worker'))
    finally:
        transport.close()
        registry.close()

def replace(env):
    env.path.write_text(json.dumps(env.data), encoding='utf-8')
    env.registry.reload()

def bind_controlled_proof(env):
    """Controlled original proof writer, not an observed model/context claim."""
    env.registry.record_context_verified('probe-worker', target_tokens=8192, prompt_tokens=8000, model_id='controlled-protocol-model', prompt_sha256='a' * 64, response_sha256='b' * 64)

def resource_frame():
    return {'os': 'Linux', 'cpu': 'Owned synthetic CPU', 'logical_cpu_count': 6, 'ram_total_bytes': 12 * GIB, 'ram_available_bytes': 5 * GIB, 'storage_free_bytes': 20 * GIB, 'python_version': '3.12.0', 'gpus': [{'id': DEVICE, 'name': 'Owned synthetic GPU', 'vram_total_bytes': 10 * GIB, 'vram_free_bytes': 4 * GIB, 'utilization_percent': 37}]}

@contextmanager
def resource_leaves(env, frames):
    iterator = iter(deepcopy(frames))
    calls = []

    def execute(command, **kwargs):
        calls.append(command[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(next(iterator)).encode())
    with patch.object(env.transport, '_address', lambda node: node['lan_ip']), patch.object(env.transport, '_ssh', lambda node, address, **kw: ['owned-leaf', address]), patch('hanni.compute.transport.subprocess.run', execute):
        yield calls

class LeafSocket:
    """No actual connection, file descriptor, or process is created."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def bind(self, value):
        pass

    def getsockname(self):
        return ('127.0.0.1', 17381)

    def close(self):
        pass

def cluster_frame(at):
    return {'status': 'online', 'checked_at': at, 'sampled_at': at, 'metrics': {'cpu_percent': 31.0, 'ram_percent': 62.0, 'ram_used_bytes': 6 * GIB, 'ram_total_bytes': 10 * GIB}, 'uptime_seconds': 97.0, 'processes': [{'name': 'owned', 'cpu_percent': 14.0, 'ram_percent': 9.0}], 'availability_source': 'telemetry', 'address': '' + '.'.join(('10', '42', '0', '7')) + '', 'connection': 'lan', 'tailscale_online': None, 'os': 'linux', 'message': None}
