"""Assemble chat SSE deltas without executing incomplete tool proposals."""
from __future__ import annotations

from copy import deepcopy
import json


def read_chat_stream(response, on_delta):
    message = {'role': 'assistant', 'content': ''}
    calls = {}
    finish, usage, timings = None, {}, {}
    seen, done, size = False, False, 0

    def consume(payload):
        nonlocal finish, usage, timings, seen, done
        if payload.strip() == '[DONE]':
            done = True
            return
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError('Model stream payload must be an object.')
        if data.get('error'):
            raise RuntimeError('The model server reported an error while streaming.')
        if isinstance(data.get('usage'), dict):
            usage = data['usage']
        if isinstance(data.get('timings'), dict):
            timings = data['timings']
        changed = False
        choices = data.get('choices')
        choices = [] if choices is None else choices
        if not isinstance(choices, list):
            raise ValueError('Model stream choices must be an array.')
        for choice in choices:
            if not isinstance(choice, dict):
                raise ValueError('Model stream choice must be an object.')
            if choice.get('index', 0) != 0:
                continue
            seen = True
            delta = choice.get('delta') or {}
            if not isinstance(delta, dict):
                raise ValueError('Model stream delta must be an object.')
            for key in ('content', 'reasoning_content', 'reasoning'):
                if isinstance(delta.get(key), str):
                    message[key] = message.get(key, '') + delta[key]
                    changed = True
            for part in delta.get('tool_calls') or []:
                if not isinstance(part, dict):
                    raise ValueError('Streamed tool call must be an object.')
                index = part.get('index', 0)
                if type(index) is not int or not 0 <= index < 32:
                    raise ValueError('Streamed tool call exceeds the action budget.')
                call = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                if part.get('id'):
                    call['id'] = part['id']
                function = part.get('function') or {}
                if not isinstance(function, dict):
                    raise ValueError('Streamed tool function must be an object.')
                for key in ('name', 'arguments'):
                    if isinstance(function.get(key), str):
                        call['function'][key] += function[key]
                changed = True
            if calls:
                message['tool_calls'] = [calls[index] for index in sorted(calls)]
            if choice.get('finish_reason') is not None:
                finish = choice['finish_reason']
        if changed:
            on_delta(deepcopy(message))

    event = []
    for line in response.iter_lines():
        size += len(line)
        if size > 2_000_000:
            raise ValueError('Model stream exceeds the response limit.')
        if not line:
            if event:
                consume('\n'.join(event)); event = []
                if done:
                    break
        elif line.startswith('data:'):
            event.append(line[5:].lstrip())
    if event and not done:
        consume('\n'.join(event))
    if not seen or (not done and finish is None):
        raise RuntimeError('The model stream ended before a complete response was returned.')
    return {'message': message, 'finish': finish, 'usage': usage, 'timings': timings}
