"""Only service/device boundaries are replaced; stores and dispatch stay real."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import threading


class ModelService:
    def __init__(self):
        self.requests = []
        self.content = 'Goal: review the report. Constraints: no sending. Completed: inspected source [1]. Blockers: none. Next steps: review.'
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = False
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def send(self, data):
                wire = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(wire)))
                self.end_headers()
                self.wfile.write(wire)
            def do_GET(self):
                if self.path == '/v1/models':
                    self.send({'data': [{'id': 'fixture', 'context_length': 65536}]})
                elif self.path == '/props':
                    self.send({'model_path': 'fixture.gguf', 'build_info': 'offline-fixture',
                               'default_generation_settings': {'n_ctx': 65536},
                               'chat_template_caps': {'supports_reasoning_effort': True}})
                elif self.path in {'/health', '/v1/health'}:
                    self.send({'status': 'ok'})
                else:
                    self.send_error(404)
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append(data)
                owner.entered.set()
                if owner.block and not owner.release.wait(10):
                    self.send_error(503)
                    return
                content = owner.content
                if data.get('response_format'):
                    content = json.dumps({'route': 'chat', 'message': 'OFFLINE_HARNESS_OK', 'capability_hints': []})
                if data.get('stream'):
                    wire = ('data: ' + json.dumps({'choices': [{'delta': {'content': content}, 'finish_reason': 'stop'}]}) + '\n\n' +
                            'data: ' + json.dumps({'choices': [], 'usage': {'prompt_tokens': 40, 'completion_tokens': 12}}) + '\n\ndata: [DONE]\n\n').encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Content-Length', str(len(wire)))
                    self.end_headers()
                    self.wfile.write(wire)
                    return
                self.send({'choices': [{'message': {'role': 'assistant', 'content': content},
                    'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 40, 'completion_tokens': 12}})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
        self.thread.start()

    @property
    def endpoint(self):
        return f'http://127.0.0.1:{self.server.server_port}/v1'

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class CalendarService:
    """A synthetic Google HTTP transport, including acknowledged writes/readback."""
    def __init__(self):
        self.events = {}
        self.requests = []
        self.error = None

    def __call__(self, account, path, params, body=None, *, method='GET'):
        method = 'POST' if body is not None and method == 'GET' else method
        self.requests.append((method, path, deepcopy(params), deepcopy(body)))
        if self.error:
            raise self.error
        if path.endswith('/events'):
            if method == 'POST':
                event_id = f'fixture-event-{len(self.events) + 1}'
                result = {'id': event_id, **body, 'htmlLink': 'https://calendar.fixture.invalid/' + event_id}
                self.events[event_id] = deepcopy(result)
                return result
            return {'items': list(deepcopy(self.events).values())}
        event_id = path.rsplit('/', 1)[-1]
        if event_id in self.events:
            if method == 'PATCH':
                self.events[event_id].update(deepcopy(body))
            return deepcopy(self.events[event_id])
        if path.endswith('/calendarList'):
            return {'items': [{'id': 'primary', 'summary': 'Fixture calendar'}]}
        return {'items': []}


class ManualTicks:
    """Explicit clock ticks for an actual background monitor, without sleeps."""
    def __init__(self):
        self.queue = queue.Queue()
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.condition = threading.Condition()
        self.waits = 0
    def wait(self, timeout=None):
        with self.condition:
            self.waits += 1
            self.ready.set()
            self.condition.notify_all()
        return self.queue.get(timeout=10)
    def set(self):
        self.stopped.set()
        self.queue.put(True)
    def is_set(self):
        return self.stopped.is_set()
    def step(self):
        self.queue.put(False)
    def step_and_wait(self):
        assert self.ready.wait(5)
        with self.condition:
            target = self.waits + 1
            self.step()
            assert self.condition.wait_for(lambda: self.waits >= target, timeout=5), 'Monitor failed to return to its wait boundary.'
