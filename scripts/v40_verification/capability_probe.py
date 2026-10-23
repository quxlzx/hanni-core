"""Read-only actual format/context probes on exact registered inference identities."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from hanni.config.loader import load_config
from hanni.workflows.verification import parse_evidence_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--context', action='store_true')
    args = p.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'data/v40-verification').resolve()) or output.exists():
        raise SystemExit('New protected evidence output required.')
    output.mkdir(parents=True)
    config = load_config(ROOT / 'config', env={})
    registry = ComputeRegistry(ROOT / 'data')
    transport = InferenceTransport(registry)
    rows = []
    def local(method, path, payload=None):
        base = config.models.supervisor.endpoint.rstrip('/').removesuffix('/v1')
        req = urllib.request.Request(base + path, method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    try:
        for endpoint in ['local:supervisor', 'worker:athena-p40', 'worker:athena-p6000', 'worker:wonyoung-strata']:
            if endpoint.startswith('worker:'):
                worker = registry.worker(endpoint.split(':', 1)[1])
                health = transport.health(worker)
                assert registry.enabled and worker['enabled'] and 'synthetic' in worker['allowed_categories']
                assert health['status'] == 'healthy' and health['model_id'] == worker['model_id']
                model = worker['model_id']
                request = lambda method, path, payload=None: transport.request(worker, method, path, payload=payload, timeout=120)
            else:
                model = config.models.supervisor.api_model
                request = local
            base_payload = {'model': model, 'stream': False, 'temperature': 0, 'max_tokens': 192,
                            'chat_template_kwargs': {'enable_thinking': False}}
            probes = [
                ('structured_json', {'messages': [{'role': 'user', 'content': 'Return only {"serial":731,"ready":false}.'}],
                    'response_format': {'type': 'json_object'}}, {'serial': 731, 'ready': False}),
                ('tool_calling', {'messages': [{'role': 'user', 'content': 'For this synthetic test, call synthetic_sensor_read with sensor_id set to node_r47. Do not execute anything else.'}],
                    'tools': [{'type': 'function', 'function': {'name': 'synthetic_sensor_read',
                        'description': 'Read-only synthetic sensor data, no side effects.',
                        'parameters': {'type': 'object', 'properties': {'sensor_id': {'type': 'string'}},
                                       'required': ['sensor_id'], 'additionalProperties': False}}}],
                    'tool_choice': 'auto', 'parallel_tool_calls': False}, {'sensor_id': 'node_r47'}),
            ]
            for kind, payload, expected in probes:
                row = {'endpoint_id': endpoint, 'kind': kind, 'expected_model': model,
                       'payload_sha256': hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                       'synthetic_only': True, 'tool_executed': False}
                began = time.perf_counter()
                try:
                    result = request('POST', '/v1/chat/completions', {**base_payload, **payload})
                    assert result['model'] == model
                    choice = result['choices'][0]
                    if kind == 'structured_json':
                        assert choice['finish_reason'] in {'stop', 'eos'}
                        assert parse_evidence_json(choice['message']['content']) == expected
                    else:
                        calls = choice['message'].get('tool_calls', [])
                        assert len(calls) == 1 and calls[0]['function']['name'] == 'synthetic_sensor_read'
                        arguments = calls[0]['function']['arguments']
                        arguments = parse_evidence_json(arguments) if isinstance(arguments, str) else arguments
                        assert arguments == expected
                        assert choice['finish_reason'] in {'tool_calls', 'stop', 'eos'}
                    row.update(passed=True, response=result)
                except Exception as error:
                    row.update(passed=False, error_class=type(error).__name__)
                row['latency_ms'] = (time.perf_counter() - began) * 1000
                rows.append(row)
                (output / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
                print(json.dumps({k: row[k] for k in ('endpoint_id', 'kind', 'passed', 'latency_ms')}), flush=True)
        if args.context:
            target = config.models.supervisor.context_length
            row = {'endpoint_id': 'local:supervisor', 'kind': 'long_context', 'target_tokens': target,
                   'expected_model': config.models.supervisor.api_model, 'passed': False, 'synthetic_only': True}
            try:
                # Stable harmless filler and three sealed-position needles; tokenizer is real server API.
                expected = {'head': 'mica-4831', 'middle': 'tulip-9274', 'tail': 'orbit-1608'}
                count = 1000
                messages = None
                for _ in range(4):
                    lines = [f'Neutral synthetic filler entry {i:05d} carries marker none.' for i in range(count)]
                    lines.insert(0, 'HEAD_CODE=mica-4831')
                    lines.insert(len(lines)//2, 'MIDDLE_CODE=tulip-9274')
                    lines.append('TAIL_CODE=orbit-1608')
                    prompt = '\n'.join(lines) + '\nRetrieve the exact HEAD_CODE, MIDDLE_CODE, and TAIL_CODE values. Return only {"head":"value","middle":"value","tail":"value"}.'
                    messages = [{'role': 'user', 'content': prompt}]
                    formatted = local('POST', '/apply-template', {'messages': messages,
                        'chat_template_kwargs': {'enable_thinking': False}})
                    tokens = local('POST', '/tokenize', {'content': formatted['prompt'], 'add_special': False, 'parse_special': True})['tokens']
                    if .91 * target <= len(tokens) <= .98 * target:
                        break
                    count = max(1, int(count * .95 * target / len(tokens)))
                assert .90 * target <= len(tokens) < target - 128
                row.update(tokenizer_prompt_tokens=len(tokens), prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest())
                began = time.perf_counter()
                result = local('POST', '/v1/chat/completions', {'model': config.models.supervisor.api_model,
                    'messages': messages, 'max_tokens': 128, 'temperature': 0, 'stream': False,
                    'chat_template_kwargs': {'enable_thinking': False}})
                row['latency_ms'] = (time.perf_counter() - began) * 1000
                assert result['model'] == row['expected_model']
                assert result['usage']['prompt_tokens'] >= .90 * target
                assert result['usage']['prompt_tokens'] <= target - result['usage']['completion_tokens']
                assert result['choices'][0]['finish_reason'] == 'stop'
                assert parse_evidence_json(result['choices'][0]['message']['content']) == expected
                row.update(passed=True, retrieval_passed=True, observed_prompt_tokens=result['usage']['prompt_tokens'], response=result)
            except Exception as error:
                row.update(error_class=type(error).__name__)
            rows.append(row)
            (output / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
            print(json.dumps({k: row.get(k) for k in ('endpoint_id', 'kind', 'passed', 'observed_prompt_tokens', 'latency_ms')}), flush=True)
    finally:
        transport.close()
        registry.close()


if __name__ == '__main__':
    main()
