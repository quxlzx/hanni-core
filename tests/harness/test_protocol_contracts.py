"""A malformed provider batch must never crash or partially execute effects."""
from copy import deepcopy
import json

import httpx
import pytest

from hanni.native.loop import run_loop
from hanni.native.runtime import ToolRuntime
from hanni.native.streaming import read_chat_stream


def capability(name='inspect'):
    return {'name': name, 'target': 'local', 'hash': 'fixture', 'remote': {}, 'schema': {
        'type': 'function', 'function': {'name': name, 'parameters': {'type': 'object',
            'properties': {'value': {'type': 'integer'}}, 'additionalProperties': False}}}}


def tool(call_id='one', name='inspect', arguments='{}'):
    return {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': arguments}}


class ScriptedModel:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def chat(self, messages, tools):
        self.requests.append(deepcopy(messages))
        value = next(self.responses)
        if isinstance(value, BaseException):
            raise value
        return value


def run(model, execute, **kwargs):
    return run_loop(model, system_prompt='Use receipts, not claims.', user_message='Inspect and verify the value.',
                    tool_specs=[capability()], execute=execute, **kwargs)


@pytest.mark.parametrize('content', [42, True, ['unsupported content'], {'text': 'unsupported'}])
def test_invalid_assistant_content_returns_provider_failure_without_escaping(content):
    model = ScriptedModel({'message': {'content': content}})
    effects = []
    result = run(model, lambda *args: effects.append(args) or {'ok': True})
    assert result['stop_reason'] == 'provider_failure'
    assert result['interrupted'] and not effects
    assert result['failure']['effects'] == 'none'


@pytest.mark.parametrize('invalid', [
    tool(name=[]), tool(name={'bad': 'name'}), tool(call_id=[]), tool(call_id=123),
    tool(arguments={'value': 1}), tool(arguments=True),
])
def test_invalid_call_envelope_blocks_the_entire_batch_before_effects(invalid):
    model = ScriptedModel({'message': {'tool_calls': [tool('valid'), invalid]}})
    effects = []
    result = run(model, lambda *args: effects.append(args) or {'ok': True})
    assert result['stop_reason'] == 'provider_failure'
    assert not effects


def test_duplicate_call_ids_are_rejected_before_any_dispatch():
    model = ScriptedModel({'message': {'tool_calls': [tool('same'), tool('same', arguments='{"value":2}')]}})
    effects = []
    result = run(model, lambda *args: effects.append(args) or {'ok': True})
    assert result['stop_reason'] == 'provider_failure' and not effects


def test_length_truncated_tool_turn_is_not_an_execution_authorization():
    model = ScriptedModel({'finish': 'length', 'message': {'content': '', 'tool_calls': [tool()]}})
    effects = []
    result = run(model, lambda *args: effects.append(args) or {'ok': True})
    assert result['stop_reason'] == 'provider_failure' and not effects


@pytest.mark.parametrize('status', [408, 429, 500, 502, 503, 504, 529])
def test_transient_failures_have_a_fixed_retry_budget(monkeypatch, status):
    now = [0.0]
    monkeypatch.setattr('hanni.native.loop.time.monotonic', lambda: now[0])
    monkeypatch.setattr('hanni.native.loop.time.sleep', lambda delay: now.__setitem__(0, now[0] + delay))
    response = httpx.Response(status, request=httpx.Request('POST', 'http://fixture.invalid'))
    failure = httpx.HTTPStatusError('synthetic provider failure', request=response.request, response=response)
    model = ScriptedModel(failure, failure, failure)
    result = run(model, lambda *_: pytest.fail('Provider failures cannot invoke tools.'))
    assert len(model.requests) == 3
    assert result['stop_reason'] == 'provider_failure'
    assert result['stats']['provider_failures'] == 3


def test_multiple_rounds_and_multi_call_turn_keep_ids_results_and_order():
    model = ScriptedModel({'message': {'tool_calls': [tool('a', arguments='{"value":1}'), tool('b', arguments='{"value":2}')]}},
                          {'message': {'tool_calls': [tool('c', arguments='{"value":3}')]}}, {'message': {'content': 'Sum is 6'}})
    dispatched = []
    runtime = ToolRuntime([capability()], lambda name, args, key: dispatched.append(key) or {'ok': True, 'data': args['value']})
    result = run(model, runtime.call)
    assert dispatched == ['a', 'b', 'c'] and result['claims'] == 'Sum is 6'
    messages = model.requests[-1]
    for index, message in enumerate(messages):
        if message.get('tool_calls'):
            calls = message['tool_calls']
            receipts = messages[index + 1:index + 1 + len(calls)]
            assert [m['tool_call_id'] for m in receipts] == [c['id'] for c in calls]
            assert all(m['role'] == 'tool' for m in receipts)


def test_tool_failure_can_be_corrected_without_inventing_success():
    model = ScriptedModel({'message': {'tool_calls': [tool('bad', arguments='{"value":"wrong"}')]}},
                          {'message': {'tool_calls': [tool('fixed', arguments='{"value":7}')]}}, {'message': {'content': 'Readback: 7'}})
    effects = []
    runtime = ToolRuntime([capability()], lambda name, args, key: effects.append(args) or {'ok': True, 'data': args['value']})
    result = run(model, runtime.call)
    first = json.loads(model.requests[1][-1]['content'])['untrusted_observation']
    assert not first['ok'] and first['effects'] == 'none'
    assert effects == [{'value': 7}] and result['claims'] == 'Readback: 7'


@pytest.mark.parametrize('events', [
    ['data: []', ''], ['data: null', ''], ['data: {"choices":[null]}', ''],
    ['data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":[]}]}}]}', ''],
])
def test_malformed_streams_fail_as_protocol_errors(events):
    class Response:
        def iter_lines(self):
            return iter(events)
    with pytest.raises((ValueError, RuntimeError), match='stream|Stream|response|Response|payload|Payload|delta|Delta|tool|Tool'):
        read_chat_stream(Response(), lambda _: None)


def test_time_budget_does_not_request_an_extra_final_generation(monkeypatch):
    now = [0.0]
    monkeypatch.setattr('hanni.native.loop.time.monotonic', lambda: now[0])
    class Model:
        requests = 0
        def chat(self, *_):
            self.requests += 1
            now[0] = 2
            return {'message': {'tool_calls': [tool()]}}
    model = Model()
    result = run(model, lambda *_: pytest.fail('Expired proposal must not execute.'), budget_seconds=1)
    assert result['stop_reason'] == 'time_budget' and model.requests == 1
