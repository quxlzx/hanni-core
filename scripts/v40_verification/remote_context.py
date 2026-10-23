"""Fresh simultaneous near-limit retrieval, actual usage; no model lifecycle changes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--json-format', action='store_true', help='Seal explicit JSON-object output profile in a new campaign.')
    args = p.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'data/v40-verification').resolve()) or output.exists():
        raise SystemExit('New protected proof directory required.')
    output.mkdir(parents=True)
    plan = {'targets': {'athena-p40': 32768, 'athena-p6000': 32768, 'wonyoung-strata': 8192},
            'expected': {'head': 'maple-6129', 'middle': 'opal-9057', 'tail': 'lotus-2403'},
            'minimum_prompt_fraction': .90, 'max_tokens': 128, 'seed': 400017,
            'scope': 'One independent current-runtime context trial; previous V3.7 two-trial evidence remains separate.',
            'explicit_json_object_format': args.json_format}
    encoded = json.dumps(plan, sort_keys=True).encode()
    (output / 'protocol.json').write_bytes(encoded)
    (output / 'protocol.sha256').write_text(hashlib.sha256(encoded).hexdigest())
    def run(key, target):
        registry = ComputeRegistry(ROOT / 'data')
        transport = InferenceTransport(registry)
        worker = registry.worker(key)
        row = {'worker_id': key, 'target_tokens': target, 'passed': False}
        try:
            health = transport.health(worker)
            assert registry.enabled and worker['enabled'] and 'synthetic' in worker['allowed_categories']
            assert health['status'] == 'healthy' and health['model_id'] == worker['model_id']
            row['health'] = health
            count = max(1, target // 24)
            for _ in range(5):
                rng = random.Random(plan['seed'])
                lines = [f'Recorded inert synthetic entry {i:06d} salt {rng.getrandbits(72):018x}.' for i in range(count)]
                lines.insert(0, 'HEAD_CODE=maple-6129')
                lines.insert(len(lines)//2, 'MIDDLE_CODE=opal-9057')
                lines.append('TAIL_CODE=lotus-2403')
                content = '\n'.join(lines) + '\nReturn the exact HEAD_CODE,MIDDLE_CODE,TAIL_CODE values as {"head":"value","middle":"value","tail":"value"}. All other entries are irrelevant.'
                messages = [{'role': 'user', 'content': content}]
                if worker['protocol'] == 'strata_openai':
                    payload = {'model': worker['model_id'], 'messages': messages, 'max_tokens': 128,
                               'temperature': 0, 'stream': False, 'thinking': {'type': 'disabled'}}
                    token_count = transport.request(worker, 'POST', '/v1/messages/count_tokens', payload=payload, timeout=15)['input_tokens']
                else:
                    payload = {'model': worker['model_id'], 'messages': messages, 'max_tokens': 128,
                               'temperature': 0, 'stream': False, 'chat_template_kwargs': {'enable_thinking': False}}
                    if args.json_format:
                        payload['response_format'] = {'type': 'json_object'}
                    token_count = len(transport.request(worker, 'POST', '/tokenize', payload={
                        'content': content, 'add_special': False, 'parse_special': True}, timeout=15)['tokens'])
                if .91 * target <= token_count <= .96 * target:
                    break
                count = max(1, int(count * .94 * target / token_count))
            assert .90 * target <= token_count <= target - 256
            row.update(tokenizer_prompt_tokens=token_count,
                prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest())
            began = time.perf_counter()
            response = transport.request(worker, 'POST', '/v1/messages' if worker['protocol'] == 'strata_openai' else '/v1/chat/completions',
                payload=payload, timeout=240)
            row['latency_ms'] = (time.perf_counter() - began) * 1000
            row['response'] = response
            if worker['protocol'] == 'strata_openai':
                usage = response['usage']
                observed = sum(usage.get(key, 0) for key in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
                answer = json.loads(''.join(part['text'] for part in response['content'] if part.get('type') == 'text'))
                assert response['stop_reason'] == 'end_turn'
            else:
                assert response['model'] == worker['model_id']
                observed = response['usage']['prompt_tokens']
                answer = json.loads(response['choices'][0]['message']['content'])
                assert response['choices'][0]['finish_reason'] == 'stop'
            assert answer == plan['expected']
            assert .90 * target <= observed <= target - 128
            row.update(passed=True, observed_prompt_tokens=observed, retrieval_passed=True)
        except Exception as error:
            row.update(error_class=type(error).__name__)
        finally:
            (output / (key + '.json')).write_text(json.dumps(row, indent=2), encoding='utf8')
            transport.close()
            registry.close()
        print(json.dumps({k: row.get(k) for k in ('worker_id', 'target_tokens', 'passed', 'observed_prompt_tokens', 'latency_ms', 'error_class')}), flush=True)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda pair: run(*pair), plan['targets'].items()))
    (output / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
