"""Independent sealed synthetic retrieval against an actual owned loopback worker.

Run only after the manager assigns the endpoint and exclusive inference slot.
Configured capacity is never promoted without actual near-limit inference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute.registry import loopback_url


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def messages(case, count):
    rng = random.Random(370071 + case['target_context_tokens'])
    lines = [f'archive record {i:06d} reference {rng.getrandbits(72):018x} disposition recorded.'
             for i in range(count)]
    for position, needle in zip(case['needle_positions'], case['needles']):
        lines.insert(round(position * count), f'Special ledger entry {needle["key"]} = {needle["value"]}.')
    return [{'role': 'system', 'content': 'Retrieve exact synthetic ledger values. Return only the requested JSON object.'},
            {'role': 'user', 'content': 'Return ledger_0, ledger_1, and ledger_2 with their exact values from this document. '
             'Archive references are unrelated filler.\nBEGIN DOCUMENT\n' + '\n'.join(lines) + '\nEND DOCUMENT'}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--worker-id', required=True)
    parser.add_argument('--stage', type=int, choices=[8192, 16384, 32768, 65536, 131072], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--timeout', type=int, default=150)
    parser.add_argument('--max-repetitions', type=int, choices=[1,2], default=2,
                        help='Limit authorized requests; one passing trial never verifies the sealed two-trial stage.')
    args = parser.parse_args()
    url = loopback_url(args.url)
    output = args.output.resolve()
    if ROOT / 'data' not in output.parents or output.exists():
        raise SystemExit('Choose a new private evidence artifact in repository data.')
    sealed = ROOT / 'data/v37-verification/sealed/protocol.json'
    raw = sealed.read_bytes()
    protocol_sha = hashlib.sha256(raw).hexdigest()
    if (sealed.with_suffix('.sha256')).read_text().strip() != protocol_sha:
        raise SystemExit('The sealed expectations changed.')
    protocol = json.loads(raw)
    case = next(row for row in protocol['context_cases'] if row['target_context_tokens'] == args.stage)
    if args.stage > 8192:
        if args.previous is None:
            raise SystemExit('A passing previous-stage artifact is required before increasing context.')
        previous = json.loads(args.previous.read_text())
        if (previous.get('worker_id') != args.worker_id or previous.get('stage') != args.stage // 2
                or previous.get('status') != 'LIVE_PASS'):
            raise SystemExit('The same worker must have passed the preceding context stage.')
    expected = {needle['key']: needle['value'] for needle in case['needles']}
    record = {'worker_id': args.worker_id, 'stage': args.stage, 'protocol_sha256': protocol_sha,
        'status': 'BLOCKED', 'max_context_verified': None, 'attempts': [], 'tokenizer_probes': 0,
        'prompt_saved': False, 'source': 'actual owned loopback HTTP worker; synthetic sealed ledger only'}
    output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        output.write_text(json.dumps(record, indent=2), encoding='utf8')
    save()
    try:
        with httpx.Client(timeout=args.timeout, trust_env=False, follow_redirects=False) as client:
            def request(path, payload=None):
                response = client.get(url + path) if payload is None else client.post(url + path, json=payload)
                if response.is_redirect:
                    raise RuntimeError('Trust-boundary redirect refused.')
                response.raise_for_status()
                return response.json()
            health = request('/health')
            record['health'] = health
            if health.get('status') not in {'ok', 'ready', 'healthy'}:
                raise RuntimeError('Worker is not ready.')
            models = request('/v1/models')
            record['model_identity'] = models
            model_id = models['data'][0]['id']
            props = request('/props')
            record['properties'] = props
            configured = props.get('default_generation_settings', {}).get('n_ctx')
            if type(configured) is int and configured < args.stage:
                raise RuntimeError('Actual runtime configured context is below requested stage.')
            def count_tokens(count):
                prompt_messages = messages(case, count)
                templated = request('/apply-template', {'messages': prompt_messages,
                    'add_generation_prompt': True, 'chat_template_kwargs': {'enable_thinking': False}})
                prompt = templated.get('prompt')
                if not isinstance(prompt, str):
                    raise RuntimeError('Actual chat template could not be applied.')
                tokenized = request('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})
                record['tokenizer_probes'] += 1
                tokens = tokenized.get('tokens')
                if not isinstance(tokens, list):
                    raise RuntimeError('Actual server tokenizer count is unavailable.')
                return len(tokens), prompt_messages
            lower, upper = 1, args.stage
            target = round(args.stage * .94)
            selected = None
            for _ in range(19):
                candidate = (lower + upper) // 2
                actual_count, prompt_messages = count_tokens(candidate)
                if actual_count <= target:
                    selected = (actual_count, prompt_messages)
                    lower = candidate + 1
                else:
                    upper = candidate - 1
                if lower > upper:
                    break
            if selected is None or selected[0] < case['minimum_actual_prompt_fraction'] * args.stage:
                raise RuntimeError('Could not build an actual near-limit prompt without overflow.')
            tokenizer_count, prompt_messages = selected
            record['actual_tokenizer_count'] = tokenizer_count
            record['prompt_sha256'] = digest(prompt_messages)
            record['generation_budget'] = 128
            record['authorized_repetitions'] = args.max_repetitions
            for repetition in range(min(case['repetitions'],args.max_repetitions)):
                started = time.monotonic()
                attempt = {'repetition': repetition + 1, 'passed': False, 'started_monotonic': started}
                record['attempts'].append(attempt)
                save()
                try:
                    response = request('/v1/chat/completions', {'model': model_id, 'messages': prompt_messages,
                        'max_tokens': 128, 'temperature': 0, 'stream': False,
                        'chat_template_kwargs': {'enable_thinking': False},
                        'response_format': {'type': 'json_object'}, 'cache_prompt': False})
                    attempt['latency_ms'] = (time.monotonic() - started) * 1000
                    attempt['usage'] = response.get('usage')
                    attempt['timings'] = response.get('timings')
                    attempt['finish_reason'] = response['choices'][0]['finish_reason']
                    content = response['choices'][0]['message']['content']
                    attempt['answer_sha256'] = hashlib.sha256(content.encode()).hexdigest()
                    attempt['answer'] = json.loads(content)
                    runtime_count = (response.get('usage') or {}).get('prompt_tokens')
                    attempt['runtime_prompt_tokens'] = runtime_count
                    attempt['passed'] = (attempt['answer'] == expected and attempt['finish_reason'] == 'stop'
                        and type(runtime_count) is int and args.stage * .9 <= runtime_count <= args.stage - 128)
                    if not attempt['passed']:
                        record['status'] = 'FAIL'
                        save()
                        break
                except Exception as exc:
                    attempt['latency_ms'] = (time.monotonic() - started) * 1000
                    attempt['error'] = type(exc).__name__ + ': ' + str(exc)[:500]
                    record['status'] = 'FAIL'
                    save()
                    break
                save()
            if len(record['attempts']) == case['repetitions'] and all(row['passed'] for row in record['attempts']):
                record.update(status='LIVE_PASS', max_context_verified=args.stage)
            elif record['status'] != 'FAIL' and any(row['passed'] for row in record['attempts']):
                record['blocker'] = 'Only one stage trial was authorized; sealed two-trial verification is incomplete.'
    except Exception as exc:
        record['blocker'] = type(exc).__name__ + ': ' + str(exc)[:500]
    finally:
        save()
    print(json.dumps({'worker_id': args.worker_id, 'stage': args.stage, 'status': record['status'],
                      'max_context_verified': record['max_context_verified'], 'requests': len(record['attempts'])}))

if __name__ == '__main__':
    main()
