"""Disposable native router fixture. All model and hardware observations are synthetic.

No owner configuration, process, model, SSH service, or external provider is used.
Capability proofs are deliberately labelled controlled, never live certification.
"""
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
from hanni.config import load_config
from hanni.compute import ComputeRegistry, ComputeScheduler, ComputeError
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
from tests.helpers import write_config_dir

class ControlledTransport:

    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.outputs = ['controlled source value'] * 20
        self.before_return = None
        self.failure = None

    def health(self, worker):
        return {'status': 'healthy', 'model_id': worker['model_id'], 'context_reported': 8192, 'last_heartbeat': self.clock(), 'runtime_identity': 'controlled-runtime-remote'}

    def resources(self, worker):
        return {'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 1024 ** 3, 'queue_depth': 0, 'resource_sampled_at': self.clock()}

    def request(self, worker, method, path, **kwargs):
        self.calls.append({'worker_id': worker['worker_id'], 'method': method, 'path': path, 'payload': kwargs.get('payload')})
        if self.failure:
            raise ComputeError('Controlled transport failure.')
        value = self.outputs.pop(0)
        if self.before_return:
            self.before_return()
        return {'model': worker['model_id'], 'choices': [{'message': {'content': value}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 20, 'completion_tokens': 4, 'total_tokens': 24}}

    def close(self):
        pass

@contextmanager
def controlled_engine(root, *, prove=True, clock=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = load_config(write_config_dir(root / 'config'), data_dir=root, env={})
    spec = replace(config.models.supervisor, context_length=8192, max_tokens=64)
    config = replace(config, models=replace(config.models, models=(spec,)))
    directory = root / 'compute'
    directory.mkdir(exist_ok=True)
    worker = {'worker_id': 'controlled', 'node_id': 'fixture_node', 'remote_port': 18080, 'model_id': 'controlled.gguf', 'enabled': True, 'capabilities': ['analysis', 'structured_json'], 'allowed_categories': ['synthetic'], 'context_configured': 8192, 'concurrency': 1}
    (directory / 'deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [{'id': 'fixture_node', 'tailscale_ip': '' + '.'.join(('100', '64', '0', '18')) + '', 'username': 'fixture'}], 'workers': [worker], 'policy': {}}), encoding='utf8')
    clock = clock or (lambda: 1000)
    registry = ComputeRegistry(root, clock=clock)
    transport = ControlledTransport(clock)
    scheduler = ComputeScheduler(registry, transport=transport)

    def local_probe(row):
        return {'status': 'healthy', 'model_id': spec.api_model, 'context_reported': 8192, 'last_heartbeat': clock(), 'runtime_identity': 'controlled-runtime-local', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 1024 ** 3, 'queue_depth': 0}
    engine = AdaptiveModelEngine(config, compute_scheduler=scheduler, clock=clock, local_probe=local_probe)
    engine.refresh()
    if prove:
        for key in ('local:supervisor', 'worker:controlled'):
            engine.record_capability_evidence(key, identity=engine.endpoint_identity(key), capabilities=['text', 'structured_json', 'tool_calling'], context_tokens=8192, observed_prompt_tokens=7600, retrieval_passed=True, evidence_sha256='c' * 64, environment='controlled implementation fixture; not real model evidence', metadata={'structured_output_formats': ['json_object', 'json_schema'], 'tool_calling_formats': ['openai_function']})
    try:
        yield engine
    finally:
        engine.close()
        scheduler.close()

def request(**changes):
    return ModelRequest(privacy_categories=frozenset({'synthetic'}), output_tokens=64, **changes)
MESSAGES = [{'role': 'user', 'content': 'Use the controlled source value.'}]
