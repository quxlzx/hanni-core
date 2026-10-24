"""Real SSE decoding, durable progress, and streamed tool execution boundaries."""
import json
from contextlib import closing
from unittest.mock import patch

import httpx
import pytest

from hanni.hermes.state import TaskStore
from hanni.native.loop import run_loop
from hanni.native.provider import NativeClient
from hanni.native.streaming import read_chat_stream
from tests.test_native_loop import spec


def sse(*events, done=True):
    text = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events)
    return text + ('data: [DONE]\n\n' if done else '')


def chunk(delta, finish=None):
    return {'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}


def test_separate_reasoning_is_delivered_before_the_final_answer():
    updates = []
    body = sse(chunk({'reasoning_content': 'Compare '}), chunk({'reasoning_content': 'the options.'}),
               chunk({'content': 'Answer'}, 'stop'), {'choices': [], 'usage': {'completion_tokens': 12},
                                                      'timings': {'predicted_ms': 100, 'predicted_n': 12}})
    with closing(httpx.Response(200, text=body)) as response:
        result = read_chat_stream(response, updates.append)
    assert updates[0]['reasoning_content'] == 'Compare '
    assert updates[0]['content'] == ''
    assert result['message']['reasoning_content'] == 'Compare the options.'
    assert result['message']['content'] == 'Answer'
    assert result['usage']['completion_tokens'] == 12
    assert result['timings']['predicted_n'] == 12


def test_fragmented_tool_arguments_are_not_executed_until_the_stream_finishes():
    calls, progress = [], []
    class Client:
        def chat_stream(self, messages, tools, *, on_delta):
            assert not calls
            body = sse(chunk({'reasoning_content': 'Use lookup.'}),
                chunk({'tool_calls': [{'index': 0, 'id': 'c1', 'function': {'name': 'look', 'arguments': '{'}}]}),
                chunk({'tool_calls': [{'index': 0, 'function': {'name': 'up', 'arguments': '}'}}]}, 'tool_calls'))
            def receive(message):
                assert not calls
                on_delta(message)
            with closing(httpx.Response(200, text=body)) as response:
                result = read_chat_stream(response, receive)
            return result
        def chat(self, messages, tools):
            raise AssertionError('Expected streaming')
    client = Client()
    count = 0
    original = client.chat_stream
    def stream(messages, tools, *, on_delta):
        nonlocal count
        count += 1
        if count == 1:
            return original(messages, tools, on_delta=on_delta)
        assert messages[-2]['reasoning_content'] == 'Use lookup.'
        on_delta({'content': 'Finished'})
        return {'message': {'content': 'Finished'}}
    client.chat_stream = stream
    result = run_loop(client, system_prompt='s', user_message='u', tool_specs=[spec('lookup')],
                      execute=lambda *args: calls.append(args) or {'ok': True},
                      context_budget_tokens=None, on_progress=progress.append)
    assert len(calls) == 1
    assert calls[0] == ('lookup', {}, 'c1')
    assert result['claims'] == 'Finished'
    assert any(item['reasoning'] and item['stats']['model_requests'] == 0 for item in progress)
    assert any(item['activity']['phase'] == 'tools' for item in progress)
    assert any(item['draft'] == 'Finished' for item in progress)


def test_truncated_stream_does_not_silently_succeed():
    with closing(httpx.Response(200, text=sse(chunk({'content': 'Partial'}), done=False))) as response:
        with pytest.raises(RuntimeError, match='before a complete'):
            read_chat_stream(response, lambda _: None)


def test_progress_keeps_events_and_cannot_overwrite_a_cancelled_task(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        task = store.submit('progress', {'prompt': 'u', 'windows_tools': [], 'origin': 'hanni', 'context': {}})
        store.event(task['id'], 'Skills applied: meeting-notes', state='running')
        for index in range(100):
            store.progress(task['id'], {'draft': str(index)})
        assert len(store.get(task['id'])['events']) == 1
        store.cancel(task['id'])
        store.progress(task['id'], {'draft': 'late'})
        assert store.get(task['id'])['result']['draft'] == '99'
        with pytest.raises(ValueError, match='exceeds limit'):
            store.progress(task['id'], {'draft': 'a' * 66000})
    finally:
        store.close()


def test_provider_falls_back_only_when_streaming_is_explicitly_unsupported():
    payloads = []
    original = httpx.Client
    def respond(request):
        payload = json.loads(request.content); payloads.append(payload)
        if payload.get('stream'):
            return httpx.Response(400, json={'error': {'param': 'stream_options', 'message': 'unsupported'}})
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Answer'}}]})
    updates = []
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        client = NativeClient({'id': 'test', 'endpoint': 'https://models.example/v1', 'source': 'api'})
        result = client.chat_stream([{'role': 'user', 'content': 'Hi'}], on_delta=updates.append)
    assert result['message']['content'] == 'Answer'
    assert len(payloads) == 2
    assert 'reasoning_budget_tokens' not in payloads[0]
    assert updates == [{'content': 'Answer'}]


def test_provider_streams_with_auth_and_preserves_usage():
    original = httpx.Client
    def respond(request):
        assert request.headers['authorization'] == 'Bearer fixture-stream-key'
        assert json.loads(request.content)['stream'] is True
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, text=sse(
            chunk({'content': 'Answer'}, 'stop'), {'choices': [], 'usage': {'completion_tokens': 4}}))
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        client = NativeClient({'id': 'test', 'endpoint': 'https://models.example/v1'}, api_key='fixture-stream-key')
        result = client.chat_stream([{'role': 'user', 'content': 'Hi'}], on_delta=lambda _: None)
    assert result['usage']['completion_tokens'] == 4
