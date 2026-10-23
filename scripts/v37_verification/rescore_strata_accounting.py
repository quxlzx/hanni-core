"""Preserve the original campaign and correct evidenced Anthropic cache accounting.

No inference is performed and the prospective sealed retrieval oracle is unchanged.
The unchanged server's usage counts split uncached input from reused KV input.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute.registry import ComputeRegistry

def main():
    original_path = ROOT / 'data/v37-verification/context/strata-8k-cycle1.json'
    source_path = ROOT / 'data/v37-verification/hardware/strata-cache-accounting-source.json'
    output = original_path.with_name('strata-8k-accounting-erratum.json')
    if output.exists():
        raise SystemExit('Preserve existing erratum; choose a new campaign for new evidence.')
    original_bytes = original_path.read_bytes()
    original = json.loads(original_bytes)
    source = json.loads(source_path.read_text())
    seal = ROOT / 'data/v37-verification/sealed/protocol.json'
    encoded = seal.read_bytes()
    seal_hash = hashlib.sha256(encoded).hexdigest()
    assert seal_hash == original['protocol_sha256'] == seal.with_suffix('.sha256').read_text().strip()
    case = json.loads(encoded)['context_cases'][0]
    expected = {needle['key']:needle['value'] for needle in case['needles']}
    assert source['server_sha256'] == 'cfed32b2be52ffde372aebb8a4ab889234a9f4fb3aa4ad17dfdb6f54b833773b'
    assert any('len(ids) - reused' in item['text'] and 'cache_read_input_tokens' in item['text']
               for item in source['excerpt'])
    attempts = []
    for item in original['attempts']:
        response = item['response']
        usage = response['usage']
        fresh, cached = usage['input_tokens'], usage.get('cache_read_input_tokens', 0)
        assert type(fresh) is int and type(cached) is int and fresh >= 0 and cached >= 0
        full = fresh + cached
        text = ''.join(part['text'] for part in response['content'] if part.get('type') == 'text')
        answer = json.loads(text)
        passed = (answer == expected and response['stop_reason'] == 'end_turn'
                  and full == original['actual_tokenizer_count']
                  and 8192 * case['minimum_actual_prompt_fraction'] <= full <= 8192 - original['generation_budget'])
        attempts.append({'repetition':item['repetition'],'passed':passed,
            'uncached_input_tokens':fresh,'cached_input_tokens':cached,'runtime_prompt_tokens':full,
            'output_tokens':usage['output_tokens'],'answer':answer,'latency_ms':item['latency_ms'],
            'response_sha256':hashlib.sha256(json.dumps(response,sort_keys=True,ensure_ascii=False).encode()).hexdigest()})
    passed = len(attempts) == case['repetitions'] and all(item['passed'] for item in attempts)
    record = {'worker_id':original['worker_id'],'stage':8192,'status':'LIVE_PASS' if passed else 'FAIL',
        'max_context_verified':8192 if passed else None,'protocol_sha256':seal_hash,
        'original_artifact_sha256':hashlib.sha256(original_bytes).hexdigest(),
        'source_server_sha256':source['server_sha256'],'attempts':attempts,
        'actual_tokenizer_count':original['actual_tokenizer_count'],'prompt_sha256':original['prompt_sha256'],
        'erratum':'Original verifier omitted cache_read_input_tokens from full context; original failure preserved. Unchanged original server and tokenizer confirm uncached plus cached equals full KV context.',
        'inference_repeated':False,'oracle_changed':False,'timing_disclosure':'Second repetition reuses KV; it is not an uncached prefill throughput sample.'}
    if passed:
        registry = ComputeRegistry(ROOT / 'data/v37-engineering/strata-context-cycle3')
        try:
            registry.observe(original['worker_id'], **original['health'])
            registry.record_context_verified(original['worker_id'],target_tokens=8192,
                prompt_tokens=attempts[-1]['runtime_prompt_tokens'],model_id=original['health']['model_id'],
                prompt_sha256=original['prompt_sha256'],response_sha256=attempts[-1]['response_sha256'])
            record['persisted_proof'] = registry.observations[original['worker_id']]['context_verification']
        finally:
            registry.close()
    output.write_text(json.dumps(record,indent=2),encoding='utf8')
    assert original_path.read_bytes() == original_bytes
    print(json.dumps({'status':record['status'],'verified_context':record['max_context_verified'],
                      'full_prompt_tokens':[a['runtime_prompt_tokens'] for a in attempts]}))

if __name__ == '__main__':
    main()
