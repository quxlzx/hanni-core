"""Sealed near8K retrieval via original Strata's authenticated Anthropic API.

Token counts come from Strata's existing count endpoint and actual inference
usage. The original model, launch script, configuration and tokenizer are reused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
from hanni.compute.registry import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from scripts.v37_verification.benchmark_context import messages, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base, output = args.data_dir.resolve(), args.output.resolve()
    if ROOT / 'data' not in base.parents or ROOT / 'data' not in output.parents or output.exists():
        raise SystemExit('Use assigned private registered deployment and a new evidence artifact.')
    sealed = ROOT / 'data/v37-verification/sealed/protocol.json'
    encoded = sealed.read_bytes()
    protocol_sha = hashlib.sha256(encoded).hexdigest()
    if sealed.with_suffix('.sha256').read_text().strip() != protocol_sha:
        raise SystemExit('Sealed expectations changed.')
    case = json.loads(encoded)['context_cases'][0]
    expected = {item['key']: item['value'] for item in case['needles']}
    registry = ComputeRegistry(base)
    transport = InferenceTransport(registry)
    worker = registry.worker('wonyoung-strata')
    record = {'worker_id': worker['worker_id'], 'stage': 8192, 'protocol_sha256': protocol_sha,
              'status': 'BLOCKED', 'max_context_verified': None, 'tokenizer_probes': 0,
              'attempts': [], 'source': 'actual original Strata Anthropic API, strict SSH tunnel and existing authentication',
              'private_context_transmitted': False, 'credentials_logged': False, 'prompt_saved': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        output.write_text(json.dumps(record, indent=2), encoding='utf8')
    save()
    try:
        health = transport.health(worker)
        record['health'] = health
        registry.observe(worker['worker_id'], **health)
        if health['status'] != 'healthy' or health['model_id'] != worker['model_id']:
            raise RuntimeError('The assigned original Strata model is not healthy.')
        record['properties'] = transport.request(worker, 'GET', '/props', timeout=10)
        def payload(count):
            original = messages(case, count)
            return {'model': worker['model_id'], 'system': original[0]['content'],
                    'messages': [original[1]], 'max_tokens': 256, 'temperature': 0,
                    'stream': False, 'thinking': {'type': 'disabled'}}
        low, high, selected = 1, 8192, None
        for _ in range(17):
            count = (low + high) // 2
            request = payload(count)
            counted = transport.request(worker, 'POST', '/v1/messages/count_tokens', payload=request, timeout=15)
            record['tokenizer_probes'] += 1
            actual = counted.get('input_tokens')
            if type(actual) is not int:
                raise RuntimeError('Original Strata tokenizer returned no actual count.')
            if actual <= round(8192 * .94):
                selected = (actual, request)
                low = count + 1
            else:
                high = count - 1
            if low > high:
                break
        if selected is None or selected[0] < 8192 * .9:
            raise RuntimeError('A safe near8K actual tokenized prompt could not be prepared.')
        actual_count, request = selected
        record['actual_tokenizer_count'] = actual_count
        record['prompt_sha256'] = digest(request)
        record['generation_budget'] = 256
        save()
        for i in range(case['repetitions']):
            attempt = {'repetition': i + 1, 'passed': False}
            record['attempts'].append(attempt)
            save()
            started = time.monotonic()
            try:
                response = transport.request(worker, 'POST', '/v1/messages', payload=request, timeout=180)
                attempt['latency_ms'] = (time.monotonic() - started) * 1000
                attempt['response'] = response
                text = ''.join(part['text'] for part in response['content'] if part.get('type') == 'text')
                answer = json.loads(text)
                usage = response['usage']
                fresh = usage['input_tokens']
                cached = usage.get('cache_read_input_tokens', 0)
                if type(fresh) is not int or type(cached) is not int or fresh < 0 or cached < 0:
                    raise RuntimeError('Actual Anthropic cache accounting is unavailable.')
                count = fresh + cached
                attempt['uncached_input_tokens'] = fresh
                attempt['cached_input_tokens'] = cached
                attempt['answer'] = answer
                attempt['runtime_prompt_tokens'] = count
                attempt['passed'] = (answer == expected and response['stop_reason'] == 'end_turn'
                    and type(count) is int and 8192 * .9 <= count <= 8192 - 256)
                if not attempt['passed']:
                    record['status'] = 'FAIL'
                    break
            except Exception as error:
                attempt['error'] = type(error).__name__ + ': ' + str(error)[:500]
                attempt['latency_ms'] = (time.monotonic() - started) * 1000
                record['status'] = 'FAIL'
                break
            finally:
                save()
        if len(record['attempts']) == case['repetitions'] and all(item['passed'] for item in record['attempts']):
            record.update(status='LIVE_PASS', max_context_verified=8192)
            registry.record_context_verified(worker['worker_id'], target_tokens=8192,
                prompt_tokens=record['attempts'][-1]['runtime_prompt_tokens'], model_id=worker['model_id'],
                prompt_sha256=record['prompt_sha256'], response_sha256=digest(record['attempts'][-1]['response']))
            record['persisted_proof'] = registry.observations.get(worker['worker_id'], {}).get('context_verification')
    except Exception as error:
        record['blocker'] = type(error).__name__ + ': ' + str(error)[:500]
    finally:
        save()
        transport.close()
        registry.close()
    print(json.dumps({'status':record['status'], 'actual_tokenizer_count':record.get('actual_tokenizer_count'),
                     'attempts':len(record['attempts']), 'max_context_verified':record['max_context_verified']}))

if __name__ == '__main__':
    main()
