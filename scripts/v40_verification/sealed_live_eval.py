"""Prospective synthetic holdout. Oracle sealed before model calls; no production code."""
import argparse
from fractions import Fraction
import hashlib
import itertools
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

SYSTEM = 'Solve the supplied synthetic task. Return only the requested JSON. Do not execute tools or change state.'
SETTINGS = {'stream': False, 'temperature': 0, 'max_tokens': 384,
            'chat_template_kwargs': {'enable_thinking': False}}


def dataset():
    probability = Fraction(7, 100) * Fraction(82, 100)
    probability /= probability + Fraction(93, 100) * Fraction(9, 100)
    cases = [
        {'id': 'development-arithmetic', 'split': 'development', 'category': 'analysis',
         'prompt': 'A synthetic batch has 17 successful tasks out of 40. What exact percentage succeeded? Return {"percent":NUMBER}.',
         'expected': {'percent': 42.5}},
        {'id': 'development-structured', 'split': 'development', 'category': 'structured_output',
         'prompt': 'From this synthetic list select items with pending=true, sort their IDs ascending, and return {"ids":[...]}. Items: [{"id":9,"pending":true},{"id":3,"pending":false},{"id":5,"pending":true}].',
         'expected': {'ids': [5, 9]}},
        {'id': 'holdout-posterior', 'split': 'holdout', 'category': 'analysis',
         'prompt': 'Exactly 7% of synthetic packets are defective. A test is positive for 82% of defective packets and 9% of nondefective packets. Given a positive test, calculate the exact reduced probability of a defective packet. Return {"numerator":INTEGER,"denominator":INTEGER}.',
         'expected': {'numerator': probability.numerator, 'denominator': probability.denominator}},
        {'id': 'holdout-queue-order', 'split': 'holdout', 'category': 'structured_output',
         'prompt': 'Synthetic jobs are ordered by priority descending, then submitted ascending, then id ascending. Exclude cancelled jobs. Jobs: [{"id":"m","priority":2,"submitted":4,"cancelled":false},{"id":"a","priority":3,"submitted":7,"cancelled":false},{"id":"f","priority":3,"submitted":7,"cancelled":false},{"id":"b","priority":3,"submitted":1,"cancelled":true},{"id":"z","priority":3,"submitted":2,"cancelled":false}]. Return {"ids":[...]}.',
         'expected': {'ids': ['z', 'a', 'f', 'm']}},
        {'id': 'holdout-graph', 'split': 'holdout', 'category': 'planning',
         'prompt': 'A synthetic directed graph has edges A->B cost8, A->C cost3, C->B cost2, B->D cost4, C->D cost9, D->E cost1, B->E cost8. Find the minimum cost path from A to E. Return {"path":[NODE_STRINGS],"cost":INTEGER}.',
         'expected': {'path': ['A', 'C', 'B', 'D', 'E'], 'cost': 10}},
        {'id': 'holdout-code', 'split': 'holdout', 'category': 'coding',
         'prompt': 'Determine the printed list from this Python code without executing tools: xs=[4,1,4,2,1,3]; seen=set(); ys=[]\nfor x in reversed(xs):\n if x not in seen:\n  seen.add(x); ys.append(x)\nprint(list(reversed(ys)))\nReturn {"output":[INTEGER_VALUES]}.',
         'expected': {'output': [4, 2, 1, 3]}},
        {'id': 'holdout-synthetic-memory', 'split': 'holdout', 'category': 'memory',
         'prompt': 'The following records are synthetic test data. May2: deployment target=blue, active. May3: correction supersedes May2, target=green, active. May4: hypothetical proposal target=red, not a confirmed preference. What is the latest confirmed target? Return {"target":STRING,"source":STRING} using the date as source.',
         'expected': {'target': 'green', 'source': 'May3'}},
        {'id': 'holdout-grounded-conversation', 'split': 'holdout', 'category': 'conversation',
         'prompt': 'This synthetic conversation provides no name for the fictional owner. Asked "what is the owner\'s name?", avoid inventing a name. Return {"answer":"unknown"} if no name is supplied.',
         'expected': {'answer': 'unknown'}},
    ]
    # Independently recompute the algorithm/graph oracles rather than accepting answers from any model.
    xs = [4, 1, 4, 2, 1, 3]
    assert [x for i, x in enumerate(xs) if x not in xs[i+1:]] == cases[5]['expected']['output']
    edges = {'A': [('B', 8), ('C', 3)], 'C': [('B', 2), ('D', 9)],
             'B': [('D', 4), ('E', 8)], 'D': [('E', 1)], 'E': []}
    def paths(node, path, cost):
        if node == 'E':
            yield cost, path
        for dest, weight in edges[node]:
            yield from paths(dest, path + [dest], cost + weight)
    best = min(paths('A', ['A'], 0))
    assert best == (10, ['A', 'C', 'B', 'D', 'E'])
    return {'version': 1, 'cases': cases, 'system': SYSTEM, 'settings': SETTINGS,
            'grading': 'Exact bounded JSON equality to sealed deterministic oracle; no prose credit.',
            'scope': 'Synthetic response tasks, six fresh holdouts per model; not a general model-quality certification.'}


def grade(response, case):
    try:
        choice = response['choices'][0]
        assert choice['finish_reason'] in {'stop', 'eos'}
        value = parse_evidence_json(choice['message']['content'])
        passed = value == case['expected']
        return {'passed': passed, 'value': value}
    except Exception as error:
        return {'passed': False, 'error_class': type(error).__name__}


def local_request(spec, payload):
    req = urllib.request.Request(spec.endpoint.rstrip('/') + '/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def run(args):
    directory = args.output.resolve()
    if not directory.is_relative_to((ROOT / 'data/v40-verification').resolve()):
        raise SystemExit('Protected verifier output required.')
    if args.mode == 'seal':
        directory.mkdir(parents=True, exist_ok=False)
        data = json.dumps(dataset(), indent=2, sort_keys=True).encode()
        (directory / 'protocol.json').write_bytes(data)
        (directory / 'protocol.sha256').write_text(hashlib.sha256(data).hexdigest(), encoding='ascii')
        print(json.dumps({'sealed': True, 'cases': len(dataset()['cases'])}))
        return
    encoded = (directory / 'protocol.json').read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    assert digest == (directory / 'protocol.sha256').read_text().strip()
    protocol = json.loads(encoded)
    output = directory / (args.mode + '-results.jsonl')
    if output.exists():
        raise SystemExit('Preserve evaluated results; choose a new campaign.')
    config = load_config(ROOT / 'config', env={})
    registry = ComputeRegistry(ROOT / 'data')
    transport = InferenceTransport(registry)
    endpoints = ['local:supervisor', 'worker:athena-p40', 'worker:athena-p6000', 'worker:wonyoung-strata']
    try:
        for endpoint in endpoints:
            for case in protocol['cases']:
                messages = [{'role': 'system', 'content': protocol['system']}, {'role': 'user', 'content': case['prompt']}]
                row = {'endpoint_id': endpoint, 'case_id': case['id'], 'split': case['split'],
                       'category': case['category'], 'protocol_sha256': digest,
                       'messages_sha256': hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()}
                try:
                    if endpoint.startswith('worker:'):
                        worker = registry.worker(endpoint.split(':', 1)[1])
                        health = transport.health(worker)
                        registry.observe(worker['worker_id'], **health)
                        snapshot = next(w for w in registry.snapshot()['workers'] if w['worker_id'] == worker['worker_id'])
                        resources = transport.resources(worker)
                        assert registry.enabled and worker['enabled'] and 'synthetic' in worker['allowed_categories']
                        assert health['status'] == 'healthy' and health['model_id'] == worker['model_id']
                        assert snapshot['max_context_verified'] >= len(json.dumps(messages).encode()) + protocol['settings']['max_tokens']
                        assert resources.get('ram_available_bytes', 2 * 1024**3) >= 2 * 1024**3
                        row.update(health=health, resources=resources, max_context_verified=snapshot['max_context_verified'])
                        payload = {'model': worker['model_id'], 'messages': messages, **protocol['settings']}
                        began = time.perf_counter()
                        response = transport.request(worker, 'POST', '/v1/chat/completions', payload=payload, timeout=120)
                        assert response.get('model') == worker['model_id']
                    else:
                        spec = config.models.supervisor
                        payload = {'model': spec.api_model, 'messages': messages, **protocol['settings']}
                        began = time.perf_counter()
                        response = local_request(spec, payload)
                        assert response.get('model') == spec.api_model
                    row.update(response=response, latency_ms=(time.perf_counter() - began) * 1000,
                               grading=grade(response, case), real_inference=True)
                except Exception as error:
                    row.update(error_class=type(error).__name__, grading={'passed': False}, real_inference=False)
                with output.open('a', encoding='utf8') as f:
                    f.write(json.dumps(row) + '\n')
                print(json.dumps({'endpoint': endpoint, 'case': case['id'], 'passed': row['grading']['passed'],
                                  'milliseconds': round(row.get('latency_ms', 0), 1), 'error': row.get('error_class')}), flush=True)
    finally:
        transport.close()
        registry.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['seal', 'baseline'], required=True)
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args())
