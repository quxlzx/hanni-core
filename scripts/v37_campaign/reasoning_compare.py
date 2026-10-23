"""A sealed, fixed synthetic reasoning comparison on registered real workers.

This is a user-authorized controlled benchmark using HANNI's transport, not a
claim that the local planner completed an autonomous WorkflowService goal.
Private deployment/authentication never appears in the saved public report.
"""
import hashlib
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport

WORKERS = ('athena-p40', 'athena-p6000', 'wonyoung-strata')
TASKS = {
    'A': {'executor': 'GPU', 'duration': 4, 'dependencies': []},
    'B': {'executor': 'CPU', 'duration': 3, 'dependencies': []},
    'C': {'executor': 'GPU', 'duration': 5, 'dependencies': ['A']},
    'D': {'executor': 'GPU', 'duration': 7, 'dependencies': ['A']},
    'E': {'executor': 'CPU', 'duration': 4, 'dependencies': ['B', 'C']},
    'F': {'executor': 'CPU', 'duration': 2, 'dependencies': ['D', 'E']},
}


def oracle():
    """Exhaustive serial schedule generation over all valid topological orders."""
    candidates = []
    for order in itertools.permutations(TASKS):
        ends, starts, available = {}, {}, {'CPU': 0, 'GPU': 0}
        for key in order:
            task = TASKS[key]
            if any(dep not in ends for dep in task['dependencies']):
                break
            starts[key] = max([available[task['executor']]] + [ends[d] for d in task['dependencies']])
            ends[key] = starts[key] + task['duration']
            available[task['executor']] = ends[key]
        else:
            candidates.append((max(ends.values()), starts))
    best = min(candidates, key=lambda candidate: candidate[0])
    bayes = Fraction(3, 100) * Fraction(90, 100)
    posterior = bayes / (bayes + Fraction(97, 100) * Fraction(4, 100))
    return {'optimal_makespan_minutes': best[0], 'valid_witness': best[1],
            'probability_numerator': posterior.numerator, 'probability_denominator': posterior.denominator,
            'logic_answer': 'not_entailed', 'oracle_method': 'Exhaustive precedence/resource scheduling; exact rational Bayes; direct finite-world predicate evaluation.'}


def protocol():
    user = (
        'Solve all three independent synthetic reasoning problems. Explain each briefly (at most 45 words each). '
        'Return only one JSON object, no markdown. Use exactly the structure given below.\n'
        '1. Scheduling: one GPU executor and one CPU executor, each can run at most one task at a time. '
        'Tasks are non-preemptive, cannot move between executors, start times are nonnegative whole minutes. '
        'Dependencies must finish before a task starts. All tasks must finish. Minimize the finishing time of the last task. '
        'Give the minimum makespan and a valid start time for every task. '
        'Tasks: ' + json.dumps(TASKS, sort_keys=True) + '\n'
        '2. Probability: exactly 3% of jobs are faulty. A detector returns positive for 90% of faulty jobs '
        'and 4% of nonfaulty jobs. A randomly selected job tests positive. What is the conditional probability '
        'that it is faulty? Give the exact reduced fraction.\n'
        '3. Logic: every archived run is checksum-verified; some checksum-verified runs are benchmark runs; '
        'no benchmark run is interactive; at least one archived run exists. Does it logically follow that '
        'some archived run is noninteractive? Answer entailed or not_entailed. If not entailed, give a '
        'counterexample world of two to four runs satisfying every premise and falsifying the conclusion. '
        'Give all four boolean properties for every run. If entailed, give an empty counterexample.\n'
        'Required output structure (N and D stand for integer answers, sA through sF for integer start times): '
        '{"schedule":{"makespan_minutes":N,"starts":{"A":sA,"B":sB,"C":sC,"D":sD,"E":sE,"F":sF},"reason":"brief"},'
        '"probability":{"numerator":N,"denominator":D,"reason":"brief"},'
        '"logic":{"answer":"entailed or not_entailed","counterexample":[{"archived":true,"verified":true,"benchmark":false,"interactive":true}],"reason":"brief"}}. '
        'The example booleans illustrate the format only; determine a complete valid world yourself.'
    )
    messages = [{'role': 'system', 'content': 'Solve the supplied reasoning problems carefully. Return only the requested JSON. Do not run tools or change state.'},
                {'role': 'user', 'content': user}]
    return {'version': 1, 'workers': list(WORKERS), 'repetitions': 2, 'messages': messages,
            'settings': {'temperature': 0, 'max_tokens': 1024, 'stream': False,
                         'chat_template_kwargs': {'enable_thinking': False}},
            'oracle': oracle(), 'grading': 'Three tasks, exact deterministic independent scoring; no changes after output.',
            'timing': 'Client wall time starts immediately before inference POST, after health/model/resource checks. Native reported prefill/generation timings remain separate. Repeated-prompt cache usage is disclosed.'}


def grade(response, expected):
    checks, failures = {}, []
    try:
        choice = response['choices'][0]
        content = choice['message']['content']
        if choice['finish_reason'] != 'stop':
            raise ValueError('Output did not finish normally.')
        from hanni.workflows.verification import parse_evidence_json
        answer = parse_evidence_json(content)
        if not isinstance(answer, dict) or set(answer) != {'schedule', 'probability', 'logic'}:
            raise ValueError('Required complete JSON object is absent.')
    except Exception as error:
        return {'score': 0, 'maximum': 3, 'checks': {}, 'error': type(error).__name__ + ': ' + str(error), 'answer': None}
    try:
        schedule = answer['schedule']
        starts = schedule['starts']
        assert set(starts) == set(TASKS)
        assert all(type(s) is int and s >= 0 for s in starts.values())
        ends = {k: starts[k] + t['duration'] for k, t in TASKS.items()}
        assert all(starts[k] >= ends[d] for k, t in TASKS.items() for d in t['dependencies'])
        for a, b in itertools.combinations(TASKS, 2):
            if TASKS[a]['executor'] == TASKS[b]['executor']:
                assert ends[a] <= starts[b] or ends[b] <= starts[a]
        assert type(schedule['makespan_minutes']) is int
        assert schedule['makespan_minutes'] == max(ends.values()) == expected['optimal_makespan_minutes']
        checks['schedule'] = True
    except Exception:
        checks['schedule'] = False
    try:
        p = answer['probability']
        assert type(p['numerator']) is int and type(p['denominator']) is int and p['denominator'] > 0
        assert math.gcd(p['numerator'], p['denominator']) == 1
        assert p['numerator'] == expected['probability_numerator'] and p['denominator'] == expected['probability_denominator']
        checks['probability'] = True
    except Exception:
        checks['probability'] = False
    try:
        logic = answer['logic']
        world = logic['counterexample']
        assert logic['answer'] == expected['logic_answer']
        assert isinstance(world, list) and 2 <= len(world) <= 4
        assert all(set(run) == {'archived', 'verified', 'benchmark', 'interactive'}
                   and all(type(v) is bool for v in run.values()) for run in world)
        assert all(not run['archived'] or run['verified'] for run in world)
        assert any(run['verified'] and run['benchmark'] for run in world)
        assert all(not run['benchmark'] or not run['interactive'] for run in world)
        assert any(run['archived'] for run in world)
        assert not any(run['archived'] and not run['interactive'] for run in world)
        checks['logic'] = True
    except Exception:
        checks['logic'] = False
    for key, passed in checks.items():
        if not passed:
            failures.append(key)
    return {'score': sum(checks.values()), 'maximum': 3, 'checks': checks, 'failed_tasks': failures, 'answer': answer,
            'scope': 'Fixed synthetic scheduling, exact probability and finite-world entailment; prose quality not certified.'}


def main():
    output = ROOT / 'data/v37-manager/reasoning-comparison-20261009'
    output.mkdir(parents=True, exist_ok=True)
    seal = output / 'protocol.json'
    encoded = json.dumps(protocol(), sort_keys=True, indent=2).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    if seal.exists():
        raise SystemExit('Preserve the evaluated protocol; use a new campaign directory for another evaluation.')
    seal.write_bytes(encoded)
    seal.with_suffix('.sha256').write_text(digest + '\n', encoding='ascii')
    plan = json.loads(encoded)
    prompt_sha = hashlib.sha256(json.dumps(plan['messages'], sort_keys=True).encode()).hexdigest()
    registry = ComputeRegistry(ROOT / 'data')
    transport = InferenceTransport(registry)
    records = []
    try:
        for repetition in range(1, 3):
            for key in WORKERS:
                worker = registry.worker(key)
                record = {'worker_id': key, 'repetition': repetition, 'prompt_sha256': prompt_sha,
                          'protocol_sha256': digest, 'status': 'BLOCKED'}
                try:
                    health = transport.health(worker)
                    registry.observe(key, **health)
                    snapshot = next(w for w in registry.snapshot()['workers'] if w['worker_id'] == key)
                    resources = transport.resources(worker)
                    required = len(json.dumps(plan['messages']).encode()) + plan['settings']['max_tokens']
                    if not registry.enabled or not worker['enabled'] or 'synthetic' not in worker['allowed_categories']:
                        raise RuntimeError('Synthetic benchmark authorization is absent.')
                    if health['status'] != 'healthy' or health['model_id'] != worker['model_id']:
                        raise RuntimeError('The exact registered model is unavailable.')
                    if snapshot['max_context_verified'] is None or snapshot['max_context_verified'] < required:
                        raise RuntimeError('Measured context does not cover the conservative request budget.')
                    if resources.get('ram_available_bytes') is not None and resources['ram_available_bytes'] < 2 * 1024**3:
                        raise RuntimeError('Observed RAM reserve is insufficient.')
                    if resources.get('vram_free_bytes') is not None and resources['vram_free_bytes'] < 256 * 1024**2:
                        raise RuntimeError('Observed VRAM reserve is insufficient.')
                    record.update(health=health, resources=resources, max_context_verified=snapshot['max_context_verified'])
                    payload = {'model': worker['model_id'], 'messages': plan['messages'], **plan['settings']}
                    began = time.perf_counter()
                    response = transport.request(worker, 'POST', '/v1/chat/completions', payload=payload,
                                                 timeout=registry.deployment['policy'].get('timeout_seconds', 120))
                    record.update(response_seconds=time.perf_counter() - began, response=response,
                                  grading=grade(response, plan['oracle']))
                    record['status'] = 'PASS' if record['grading']['score'] == 3 else 'FAIL'
                except Exception as error:
                    record['error'] = type(error).__name__ + ': ' + str(error)
                records.append(record)
                (output / 'results.json').write_text(json.dumps(records, indent=2), encoding='utf8')
                print(json.dumps({'worker_id': key, 'repetition': repetition, 'status': record['status'],
                    'score': record.get('grading', {}).get('score'),
                    'response_seconds': round(record.get('response_seconds', 0), 3)}), flush=True)
    finally:
        transport.close()
        registry.close()


if __name__ == '__main__':
    main()
