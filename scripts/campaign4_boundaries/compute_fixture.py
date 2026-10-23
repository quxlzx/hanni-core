"""Owned loopback inference transport, controlled data; no real model/provider."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
from hanni.compute.registry import ComputeRegistry
from hanni.compute.scheduler import ComputeScheduler
from hanni.compute.transport import InferenceTransport
from scripts.campaign4_boundaries.harness import QueuedStructuredClient, criterion, step

def report(value=40):
    return {'observations': [{'operation': 'percentage', 'sources': [{'step_id': 'read', 'path': '/data/text', 'json_path': '/passed'}, {'step_id': 'read', 'path': '/data/text', 'json_path': '/total'}], 'value': value}]}

def analysis_client(source, *, local_fallback=False):
    read = step('read', source, criteria=[criterion('/data/text', operator='json_valid')])
    analysis = dict(step_id='analyze', kind='analysis', description='Calculate the cited pass percentage.', dependencies=['read'], required=True, criteria=[criterion('/data/report', operator='evidence_report')])
    save = dict(step_id='save', kind='artifact', description='Save the verified calculation as a private report.', dependencies=['analyze'], required=True, criteria=[criterion('/data/path')])

    def bind(messages, _):
        root = json.loads(messages[1]['content'])['artifact_root']
        return dict(unsupported_reason=None, steps=[read[1], dict(step_id='analyze', capability_id=None, arguments={'sources': ['read']}), dict(step_id='save', capability_id='file.write', arguments=dict(path=str(Path(root) / 'report.json'), text={'$ref': dict(step_id='analyze', path='/data/text', type='string')}))])
    rows = [dict(summary='Controlled cited analysis; no model quality claim.', unsupported_reason=None, steps=[read[0], analysis, save]), bind]
    if local_fallback:
        rows.append(report())
    return QueuedStructuredClient(*rows)

@contextmanager
def endpoint(model, *, behavior='complete', value=40, gate=None):
    state = {'model_id': model, 'behavior': behavior, 'calls': [], 'health_paths': [], 'entered': threading.Event(), 'disconnections': 0}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_):
            pass

        def respond(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            state['health_paths'].append(self.path)
            self.respond({'/health': {'status': 'ok'}, '/v1/models': {'data': [{'id': model}]}, '/props': {'default_generation_settings': {'n_ctx': 32768}}}[self.path])

        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            payload = json.loads(raw)
            state['calls'].append({'path': self.path, 'payload_sha256': hashlib.sha256(raw).hexdigest(), 'model': payload.get('model'), 'response_format_type': (payload.get('response_format') or {}).get('type')})
            state['entered'].set()
            if gate is not None and (not gate.wait(5)):
                return
            if behavior == 'disconnect':
                state['disconnections'] += 1
                self.close_connection = True
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
                return
            self.respond({'model': model, 'choices': [{'message': {'content': json.dumps(report(value))}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 60}})
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state['url'] = 'http://127.0.0.1:' + str(server.server_port)
    try:
        yield state
    finally:
        if gate is not None:
            gate.set()
        server.shutdown()
        server.server_close()
        thread.join(2)

@contextmanager
def scheduler(root, endpoints, *, fallback_local=False, retries=0, timeout=1):
    root = Path(root)
    (root / 'compute').mkdir(parents=True)
    workers = [dict(worker_id='controlled_worker_' + str(index), node_id='local', local_url=item['url'], model_id=item['model_id'], enabled=True, allowed_categories=['project', 'conversation'], capabilities=['analysis', 'structured_json'], concurrency=1) for index, item in enumerate(endpoints)]
    (root / 'compute' / 'deployment.json').write_text(json.dumps(dict(version=1, enabled=True, nodes=[], workers=workers, policy=dict(max_queue=2, timeout_seconds=timeout, max_retries=retries, fallback_local=fallback_local))), encoding='utf-8')
    registry = ComputeRegistry(root)
    transport = InferenceTransport(registry)
    transport.resources = lambda _worker: {'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': None, 'resource_sampled_at': registry.clock()}
    engine = ComputeScheduler(registry, transport=transport)
    try:
        engine.refresh()
        for index, worker in enumerate(workers):
            registry.record_context_verified(worker['worker_id'], target_tokens=32768, prompt_tokens=31000, model_id=worker['model_id'], prompt_sha256='a' * 64, response_sha256='b' * 64)
            registry.observe(worker['worker_id'], latency_ms=1 + index * 100)
        yield engine
    finally:
        engine.close()

def evidence(final, engine, endpoints):
    return dict(scope='native workflow + original compute registry/scheduler/HTTP transport; controlled loopback data', real_model=False, real_cluster=False, workflow_id=final['workflow_id'], status=final['status'], counts=final['counts'], steps=[{key: row.get(key) for key in ('step_id', 'kind', 'status', 'attempts', 'verification', 'resolved_arguments')} for row in final['steps']], invocations=final['invocations'], checkpoints=final['checkpoints'], jobs=engine.registry.jobs(final['workflow_id']), endpoints=[{key: row[key] for key in ('model_id', 'behavior', 'calls', 'health_paths', 'disconnections')} for row in endpoints], active_reservations=dict(engine.registry.active))
