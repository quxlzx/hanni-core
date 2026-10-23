"""Reproducible development-only deterministic memory retrieval comparison.

This is not the independently sealed V3.5 validation/holdout benchmark and does
not measure generative factual accuracy or actual LAYA model quality. Both arms
share today's v3 authoritative store; A uses its legacy lexical retriever.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import tempfile
import time
from pathlib import Path

from hanni.memory.retrieval import ContextAwareRetriever, LocalMemoryRetriever
from hanni.memory.store import MemoryStore


def development_cases():
    cases = []
    for name, identifier in [('Atlas', 'atlas'), ('Birch', 'birch'), ('Cedar', 'cedar'), ('Dawn', 'dawn')]:
        memories = [{'id': 'result', 'content': f'The {name} benchmark scored 81 out of 100 cases'},
                    {'id': 'plan', 'content': f'I plan to repeat the {name} benchmark'},
                    {'id': 'other', 'content': 'The unrelated garden project grows tomatoes'}]
        for suffix, query, expected in [('exact', f'{name} benchmark', ['result', 'plan']),
                                        ('score', f'What did {name} score?', ['result', 'plan']),
                                        ('intent', f'{name} repeat benchmark', ['plan']),
                                        ('negative', 'Which telescope has a damaged lens?', [])]:
            cases.append({'id': f'dev-{identifier}-{suffix}', 'partition': 'development', 'query': query,
                          'memories': memories, 'expected_ids': expected})
    for key, memory, query in [('editor', 'My preferred code editor is Code', 'Which IDE do I prefer?'),
                                ('folder', 'My demo project folder is C:/synthetic/demo', 'Find demo directory'),
                                ('response', 'I prefer concise responses', 'Explain the compiler briefly'),
                                ('routine', 'When I publish a report, I always check the sources', 'report sources')]:
        cases.append({'id': f'dev-preference-{key}', 'partition': 'development', 'query': query,
                      'memories': [{'id': 'expected', 'content': memory}, {'id': 'other', 'content': 'My favorite drink is tea'}],
                      'expected_ids': ['expected']})
    return cases


def validate_cases(cases):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 1000:
        raise ValueError('Use 1..1000 development scenarios')
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'partition', 'query', 'memories', 'expected_ids'}:
            raise ValueError('Unknown development case fields')
        if case['partition'] != 'development':
            raise ValueError('This runner must not expose validation or holdout fixtures')
        if not isinstance(case['id'], str) or not case['id'] or case['id'] in seen:
            raise ValueError('Unique scenario IDs required')
        seen.add(case['id'])
        if not isinstance(case['query'], str) or not 1 <= len(case['query']) <= 1200:
            raise ValueError('Bounded query required')
        if not isinstance(case['memories'], list) or not 1 <= len(case['memories']) <= 100:
            raise ValueError('Use 1..100 synthetic source memories per scenario')
        ids = set()
        for memory in case['memories']:
            if not isinstance(memory, dict) or set(memory) != {'id', 'content'} or not isinstance(memory['id'], str) or not memory['id'] or memory['id'] in ids:
                raise ValueError('Stable unique source IDs required')
            from hanni.memory.privacy import validate_memory_text
            validate_memory_text(memory['content'], max_chars=1200)
            ids.add(memory['id'])
        if not isinstance(case['expected_ids'], list) or any(not isinstance(value, str) or value not in ids for value in case['expected_ids']) or len(set(case['expected_ids'])) != len(case['expected_ids']):
            raise ValueError('Expected source IDs must be unique and exist')
    return cases


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    floor = math.floor(index)
    return ordered[floor] + (ordered[min(floor + 1, len(ordered) - 1)] - ordered[floor]) * (index - floor)


def evaluate(cases, *, repeats=3):
    validate_cases(cases)
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError('Use 1..10 timed repetitions')
    arms = {key: [] for key in ('A', 'B')}
    timings = {key: [] for key in arms}
    corpus = json.dumps(cases, sort_keys=True, separators=(',', ':')).encode('utf-8')
    with tempfile.TemporaryDirectory(prefix='hanni-memory-development-') as temporary:
        for index, case in enumerate(cases):
            store = MemoryStore(Path(temporary) / f'case-{index}.db')
            expected_mapping = {}
            for memory in case['memories']:
                record, _ = store.remember(memory['content'], source='owner_explicit:synthetic-development',
                                           source_ref=case['id'] + ':' + memory['id'])
                expected_mapping[memory['id']] = record.id
            if len(set(expected_mapping.values())) != len(expected_mapping):
                raise ValueError('Fixture source memories deduplicate; give distinct statements')
            expected = {expected_mapping[value] for value in case['expected_ids']}
            original = store.fingerprint()
            retrievers = {'A': LocalMemoryRetriever(store, limit=5, max_chars=4000),
                          'B': ContextAwareRetriever(store, limit=5, max_chars=4000, max_tokens=4000)}
            # Alternate deterministic arm order by case to reduce one-sided
            # page-cache warming. Timings remain same-process development samples.
            order = ('A', 'B') if index % 2 == 0 else ('B', 'A')
            for key in order:
                result = None
                for _ in range(repeats):
                    started = time.perf_counter()
                    result = retrievers[key].retrieve(case['query'])
                    timings[key].append((time.perf_counter() - started) * 1000)
                returned = {match.record.id for match in result.matches}
                true = len(returned & expected)
                arms[key].append({'case_id': case['id'], 'expected_count': len(expected),
                                  'returned_count': len(returned), 'relevant_count': true,
                                  'recall_at_5': true / len(expected) if expected else None,
                                  'precision': true / len(returned) if returned else (1. if not expected else 0.),
                                  'negative_correct': not returned if not expected else None,
                                  'all_ids_grounded': all(store.get(memory_id) is not None for memory_id in returned),
                                  'injected_characters': len(result.text), 'utf8_token_upper_bound': len(result.text.encode('utf-8'))})
            if store.fingerprint() != original:
                raise RuntimeError('Retrieval mutated authoritative memory')
    summary = {}
    for key, rows in arms.items():
        positive = [row for row in rows if row['expected_count']]
        negative = [row for row in rows if not row['expected_count']]
        summary[key] = {'scenarios': len(rows), 'positive_scenarios': len(positive), 'negative_scenarios': len(negative),
                        'mean_recall_at_5': statistics.mean(row['recall_at_5'] for row in positive) if positive else None,
                        'mean_precision': statistics.mean(row['precision'] for row in rows),
                        'correct_negative_count': sum(row['negative_correct'] for row in negative),
                        'grounded_id_count': sum(row['all_ids_grounded'] for row in rows),
                        'p50_retrieval_ms': percentile(timings[key], .5), 'p95_retrieval_ms': percentile(timings[key], .95),
                        'timed_samples': len(timings[key]), 'mean_injected_characters': statistics.mean(row['injected_characters'] for row in rows),
                        'mean_utf8_token_upper_bound': statistics.mean(row['utf8_token_upper_bound'] for row in rows)}
    return {'version': 1, 'partition': 'development', 'corpus_sha256': hashlib.sha256(corpus).hexdigest(),
            'protocol': {'limit': 5, 'max_chars': 4000, 'B_max_tokens_conservative_bytes': 4000, 'repeats': repeats,
                         'timing': 'retrieval only, fixture creation excluded, alternate arm order, same process',
                         'A': 'current v3 store + original lexical retrieval, not frozen pre-V3.5 baseline',
                         'B': 'current v3 store + deterministic ContextAwareRetriever'},
            'summary': summary, 'cases': arms,
            'C_actual_laya_advisory': {'status': 'BLOCKED', 'reason': 'No independently verified installed LAYA model or gate supplied; no inference attempted'},
            'D_full_context': {'status': 'NOT_EVALUATED', 'reason': 'Project/workflow integration belongs to separate independent suite'},
            'unauthorized_memory_changes': 0,
            'limitations': ['Synthetic development cases are visible and may be used to tune rules.',
                            'No actual-model inference, generative factual accuracy, confidence calibration, real provider calls or holdout claims.',
                            'Precision describes expected source relevance, ID grounding checks identity only.',
                            'UTF-8 byte bounds are conservative budget measurements, not exact model token counts.',
                            'Same-process small-store timing is not production or independent end-to-end performance.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, help='Explicitly approved synthetic DEVELOPMENT JSONL; never private memory exports')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args(argv)
    cases = ([json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines() if line.strip()]
             if args.cases else development_cases())
    report = evaluate(cases, repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(report, target, indent=2)
        target.write('\n')
    print(json.dumps({'partition': 'development', 'scenarios': len(cases), 'summary': report['summary'], 'C': 'BLOCKED', 'D': 'NOT_EVALUATED'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
