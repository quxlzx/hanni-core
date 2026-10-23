"""Disposable loopback protocol fixtures; never actual model/GPU evidence."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time

class Activity:

    def __init__(self):
        self.lock = threading.RLock()
        self.active = 0
        self.maximum = 0
        self.entries = []

    def enter(self, worker, label):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.entries.append({'worker_id': worker, 'label': label, 'at': time.monotonic()})

    def exit(self):
        with self.lock:
            self.active -= 1

@contextmanager
def endpoint(config, activity, *, workflow=False):
    state = {'id': config['id'], 'model': 'controlled-' + config['id'], 'behavior': config.get('response_behavior', 'complete'), 'calls': [], 'health': [], 'entered': threading.Event(), 'gate': None, 'gated_labels': None, 'closed': False, 'disconnections': 0, 'config': config}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_):
            pass

        def send(self, value, status=200, raw=None):
            body = json.dumps(value, allow_nan=False).encode() if raw is None else raw
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return body

        def do_GET(self):
            state['health'].append(self.path)
            if self.path == '/health':
                self.send({'status': 'ok'})
                return
            if self.path == '/v1/models':
                self.send({'data': [{'id': config.get('health_model', state['model'])}]})
                return
            if self.path == '/props':
                self.send({'default_generation_settings': {'n_ctx': config.get('context_reported', 32768)}, 'build_info': 'controlled-loopback-fixture'})
                return
            self.send({'error': 'Unsupported fixture health operation.'}, 404)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            payload = json.loads(raw)
            message = payload.get('messages', [{}])[-1].get('content', '')
            label = message.split('\n', 1)[0].removeprefix('label=') if message.startswith('label=') else 'main'
            record = {'path': self.path, 'label': label, 'request_body': raw.decode(), 'request_sha256': hashlib.sha256(raw).hexdigest(), 'entered_at': time.monotonic()}
            state['calls'].append(record)
            activity.enter(config['id'], label)
            state['entered'].set()
            try:
                gate = state['gate']
                labels = state['gated_labels']
                if gate is not None and (labels is None or label in labels):
                    gate.wait(5)
                behavior = state['behavior']
                if behavior == 'disconnect':
                    state['disconnections'] += 1
                    self.close_connection = True
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    self.connection.close()
                    return
                if behavior == 'http500':
                    record['response_raw'] = self.send({'error': 'Controlled provider failure.'}, 500).decode()
                    return
                if behavior == 'malformed':
                    record['response_raw'] = self.send(None, raw=b'controlled malformed JSON').decode()
                    return
                if behavior == 'array':
                    record['response_raw'] = self.send([]).decode()
                    return
                if behavior.startswith('context_'):
                    content = json.dumps({'marker': 'wrong' if behavior == 'context_wrong' else 'fixture'})
                    tokens = 500 if behavior == 'context_underfilled' else 1000
                    result = {'model': state['model'], 'usage': {'input_tokens': tokens}, 'content': [{'type': 'text', 'text': content}], 'stop_reason': 'max_tokens' if behavior == 'context_truncated' else 'end_turn'}
                else:
                    if workflow:
                        report = {'observations': [{'operation': 'percentage', 'sources': [{'step_id': 'read', 'path': '/data/text', 'json_path': '/passed'}, {'step_id': 'read', 'path': '/data/text', 'json_path': '/total'}], 'value': 41 if behavior == 'wrong_value' else '40' if behavior == 'string_value' else 40}]}
                        if behavior == 'wrong_source':
                            report['observations'][0]['sources'][0]['step_id'] = 'unavailable_source'
                        if behavior == 'invalid_report':
                            report = {'unsupported': True}
                        content = json.dumps(report)
                    else:
                        content = json.dumps({'delivered': label})
                    result = {'model': 'wrong-model' if behavior == 'wrong_model' else state['model'], 'choices': [{'message': {'content': content}, 'finish_reason': 'length' if behavior == 'truncated' else 'stop'}], 'usage': {'prompt_tokens': 30, 'completion_tokens': 10, 'total_tokens': 40}}
                record['response_raw'] = self.send(result).decode()
            finally:
                record['finished_at'] = time.monotonic()
                activity.exit()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    state['url'] = 'http://127.0.0.1:' + str(server.server_port)
    try:
        yield state
    finally:
        if state['gate'] is not None:
            state['gate'].set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        state['closed'] = True
