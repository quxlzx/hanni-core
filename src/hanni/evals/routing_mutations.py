"""Development-only phrase and ASR-noise routing probes; no tool execution."""
from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import replace
from pathlib import Path

from hanni.evals.fixtures import fixture_timezone
from hanni.evals.routing import build_default_host, evaluate_case, load_cases
from hanni.evals.routing_multiturn import evaluate as evaluate_dialogues


def variants(query: str) -> tuple[tuple[str, str], ...]:
    """Reversible/light transcription variants that preserve the requested task."""
    short = query.replace(' and ', ' n ').replace('what is ', 'whats ').replace('please', 'pls')
    short = re.sub(r'\b(?:the|a|an)\s+', '', short, flags=re.I)
    if short == query:
        short = 'uh ' + query
    return (('casing', query.upper()),
            ('punctuation', query.rstrip('?.!') + '?'),
            ('filler', 'hey hanni, ' + query),
            ('asr_spacing_and_articles', short))


def run(host, cases, *, seed=17):
    shuffled = list(cases)
    random.Random(seed).shuffle(shuffled)
    clean, changed = [], []
    for case in shuffled:
        base = evaluate_case(host, case)
        clean.append(base)
        for label, query in variants(case.query):
            mutated = evaluate_case(host, replace(case, id=case.id + ':' + label, query=query))
            changed.append({'source_id': case.id, 'mutation': label, 'query': query,
                            'clean_passed': base.passed, 'passed': mutated.passed,
                            'selected': list(mutated.selected), 'reasons': list(mutated.reasons),
                            'status': mutated.metrics['status'],
                            'required_retrieval': mutated.metrics['required_retrieval'],
                            'irrelevant_exposure': mutated.metrics['irrelevant_exposure']})
    total = len(changed)
    safety = [row for row in changed if row['source_id'] in {case.id for case in cases if case.mode == 'blocked'}]
    by_mutation = {}
    for label in sorted({row['mutation'] for row in changed}):
        subset = [row for row in changed if row['mutation'] == label]
        by_mutation[label] = {'cases': len(subset),
                              'strict_percent': round(100 * sum(row['passed'] for row in subset) / len(subset), 2),
                              'clarifications': sum(row['status'] == 'clarification' for row in subset)}
    return {'seed': seed, 'source_cases': len(cases), 'mutated_cases': total,
            'clean_strict_percent': round(100 * sum(row.passed for row in clean) / len(clean), 2) if clean else 0,
            'mutated_strict_percent': round(100 * sum(row['passed'] for row in changed) / total, 2) if total else 0,
            'required_retrieval_percent': round(100 * sum(row['required_retrieval'] is True for row in changed
                                                          if row['required_retrieval'] is not None) /
                                                max(1, sum(row['required_retrieval'] is not None for row in changed)), 2),
            'irrelevant_exposures': sum(bool(row['irrelevant_exposure']) for row in changed),
            'clarifications': sum(row['status'] == 'clarification' for row in changed),
            'blocked_safety_regressions': sum(bool(row['selected']) for row in safety),
            'by_mutation': by_mutation,
            'results': changed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=Path('evals/routing/language_generalization_v3.jsonl'))
    parser.add_argument('--json', type=Path, default=Path('evals/routing/results/language_v3_mutations.json'))
    parser.add_argument('--seed', type=int, default=17)
    args = parser.parse_args(argv)
    cases = load_cases(args.cases)
    report = run(build_default_host(timezone_name=fixture_timezone(args.cases)), cases, seed=args.seed)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Routing mutations: {report['mutated_cases']} variants, seed {args.seed}; "
          f"clean {report['clean_strict_percent']:.2f}%, mutated {report['mutated_strict_percent']:.2f}%; "
          f"blocked safety regressions {report['blocked_safety_regressions']}.")
    return 0


def multiturn_main(argv=None):
    parser = argparse.ArgumentParser(description='Probe final-turn follow-ups with controlled mutations')
    parser.add_argument('--cases', type=Path, default=Path('evals/routing/multiturn_v1.jsonl'))
    parser.add_argument('--json', type=Path, default=Path('evals/routing/results/multiturn_mutations.json'))
    args = parser.parse_args(argv)
    dialogues = [json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines() if line.strip()]
    host = build_default_host(timezone_name=fixture_timezone(args.cases))
    clean = evaluate_dialogues(host, dialogues)
    mutations = []
    for dialogue in dialogues:
        for label, query in variants(dialogue['turns'][-1]['query']):
            changed = {**dialogue, 'id': dialogue['id'] + ':' + label,
                       'turns': [*dialogue['turns'][:-1], {**dialogue['turns'][-1], 'query': query}]}
            result = evaluate_dialogues(host, [changed])['results'][0]
            mutations.append({'id': changed['id'], 'query': query, 'passed': result['passed'],
                              'turns': result['turns']})
    report = {'dialogues': len(dialogues), 'mutations': len(mutations),
              'clean_dialogue_success_percent': clean['dialogue_success_percent'],
              'mutated_dialogue_success_percent': round(100 * sum(row['passed'] for row in mutations) /
                                                       len(mutations), 2) if mutations else 0,
              'results': mutations}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Multi-turn mutations: {len(mutations)} final-turn variants; "
          f"clean {report['clean_dialogue_success_percent']:.2f}%, "
          f"mutated {report['mutated_dialogue_success_percent']:.2f}%.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
