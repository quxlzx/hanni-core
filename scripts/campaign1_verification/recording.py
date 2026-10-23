"""Transparent original-client telemetry hooks; raw evidence stays private.

Hooks observe every original local client, including the adaptive engine's
bounded callbacks. Inputs, original parsing, admission and retry behavior remain
unchanged. The only added stream option requests supported usage telemetry.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json
import time
import urllib.request
from hanni.models import client as module
ACTIVE = ContextVar('campaign1_recording', default=None)

class Recording:

    def __init__(self, sink):
        self.sink = sink
        self.calls = []
        self.current = None

    def emit(self, kind, **fields):
        self.sink({'kind': kind, 'timestamp': time.time(), 'monotonic': time.perf_counter(), **fields})

    @contextmanager
    def call(self, kind, messages, options):
        previous = self.current
        row = {'call_index': len(self.calls), 'kind': kind, 'started': time.perf_counter(), 'messages': deepcopy(messages), 'options': deepcopy(options), 'http_attempts': [], 'raw_responses': [], 'chunks': []}
        self.calls.append(row)
        self.current = row
        self.emit('model_call_started', call_index=row['call_index'], call_kind=kind, messages=messages, options=options)
        try:
            yield row
        except BaseException as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
            raise
        finally:
            row['duration_ms'] = (time.perf_counter() - row['started']) * 1000
            self.emit('model_call_finished', record=row)
            self.current = previous

@contextmanager
def hooks():
    from hanni.mcp import session as session_module
    from hanni.mcp.completion import CompletionLedger
    original_debug = session_module._debug_event
    original_observe = CompletionLedger.observe
    original_parse = module._parse_tool_turn
    original_sse = module._iter_sse_content
    original_complete = module.LlamaCppClient.complete_with_tools
    original_stream = module.LlamaCppClient.stream_chat
    original_open = urllib.request.urlopen

    def debug(kind, **fields):
        recorder = ACTIVE.get()
        if recorder is not None:
            recorder.emit('original_controller_trace', event=kind, fields=deepcopy(fields))
        return original_debug(kind, **fields)

    def observe(self, capability, result):
        answer = original_observe(self, capability, result)
        recorder = ACTIVE.get()
        if recorder is not None:
            recorder.emit('original_completion_ledger', capability=capability, ledger=self.to_dict())
        return answer

    def parse(raw):
        recorder = ACTIVE.get()
        if recorder is not None and recorder.current is not None:
            recorder.current['raw_responses'].append(raw)
            recorder.emit('raw_before_tool_parser', call_index=recorder.current['call_index'], raw=raw)
            try:
                payload = json.loads(raw)
                from hanni.models.performance import server_rates
                recorder.current.setdefault('raw_response_telemetry', []).append({'usage': deepcopy(payload.get('usage')), 'performance': server_rates(payload)})
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
        return original_parse(raw)

    def sse(response, **options):
        recorder = ACTIVE.get()

        def observed():
            for raw in response:
                if recorder is not None and recorder.current is not None:
                    recorder.emit('raw_before_sse_parser', call_index=recorder.current['call_index'], raw=raw.decode('utf8', errors='replace'))
                yield raw
        yield from original_sse(observed(), **options)

    def complete(self, messages, *, tools, **options):
        recorder = ACTIVE.get()
        if recorder is None:
            return original_complete(self, messages, tools=tools, **options)
        with recorder.call('tool_selection', messages, {'tools': tools, **options}) as row:
            row['transport_max_attempts'] = self.max_attempts
            answer = original_complete(self, messages, tools=tools, **options)
            row['parsed'] = {'content': answer.content, 'tool_calls': [{'id': c.id, 'name': c.name, 'arguments': dict(c.arguments)} for c in answer.tool_calls], 'usage': dict(answer.usage)}
            return answer

    def stream(self, messages, **options):
        recorder = ACTIVE.get()
        if recorder is None:
            yield from original_stream(self, messages, **options)
            return
        usage = options.get('usage')
        if usage is None:
            usage = {}
            options['usage'] = usage
        performance = options.get('performance')
        if performance is None:
            performance = {}
            options['performance'] = performance
        with recorder.call('text_generation', messages, {k: v for k, v in options.items() if k not in {'usage', 'performance'}}) as row:
            row['transport_max_attempts'] = self.max_attempts
            try:
                for chunk in original_stream(self, messages, **options):
                    row['chunks'].append(chunk)
                    recorder.emit('model_text_chunk', call_index=row['call_index'], text=chunk)
                    yield chunk
            finally:
                row.update(usage=dict(usage), performance=dict(performance))

    def urlopen(request, *args, **kwargs):
        recorder = ACTIVE.get()
        url = getattr(request, 'full_url', str(request))
        if recorder is not None and recorder.current is not None and url.endswith('/chat/completions'):
            payload = json.loads(request.data.decode('utf8'))
            attempt = {'url': url, 'payload': payload, 'started': time.perf_counter()}
            recorder.current['http_attempts'].append(attempt)
            recorder.emit('model_http_attempt', call_index=recorder.current['call_index'], attempt=attempt)
            try:
                return original_open(request, *args, **kwargs)
            except BaseException as exc:
                attempt['error'] = {'type': type(exc).__name__, 'message': str(exc)}
                recorder.emit('model_http_error', call_index=recorder.current['call_index'], attempt=attempt)
                raise
        return original_open(request, *args, **kwargs)
    module._parse_tool_turn = parse
    module._iter_sse_content = sse
    module.LlamaCppClient.complete_with_tools = complete
    module.LlamaCppClient.stream_chat = stream
    urllib.request.urlopen = urlopen
    session_module._debug_event = debug
    CompletionLedger.observe = observe
    try:
        yield
    finally:
        module._parse_tool_turn = original_parse
        module._iter_sse_content = original_sse
        module.LlamaCppClient.complete_with_tools = original_complete
        module.LlamaCppClient.stream_chat = original_stream
        urllib.request.urlopen = original_open
        session_module._debug_event = original_debug
        CompletionLedger.observe = original_observe

@contextmanager
def record_into(recorder):
    token = ACTIVE.set(recorder)
    try:
        yield recorder
    finally:
        ACTIVE.reset(token)
