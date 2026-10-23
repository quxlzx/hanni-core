"""Capture existing routing development benchmarks without executing tools.

Historical LLM holdouts and new Campaign 1 holdout files are never opened here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from hanni.evals.fixtures import fixture_timezone
from hanni.evals.routing import build_default_host, load_cases, run_benchmark
from hanni.evals.routing_multiturn import evaluate as evaluate_dialogues
CORPORA = ('cases.jsonl', 'multiturn_v1.jsonl', 'language_generalization_v2.jsonl', 'language_generalization_v3.jsonl', 'language_generalization_v4.jsonl', 'language_generalization_v4b.jsonl', 'false_positive_v4.jsonl', 'voice_routing_v1.jsonl', 'academic_calendar.jsonl', 'phrase_probe_v2.jsonl')

def run(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for name in CORPORA:
        path = root / 'evals' / 'routing' / name
        host = build_default_host(config_dir=root / 'config', data_dir=output / 'isolated-state', timezone_name=fixture_timezone(path))
        if name == 'multiturn_v1.jsonl':
            dialogues = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
            result = evaluate_dialogues(host, dialogues)
            destination = output / (path.stem + '.json')
            destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            summaries.append({'corpus': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'cases': result['dialogues'], 'turns': result['turns'], 'passes': sum((item['passed'] for item in result['results'])), 'pass_rate': result['dialogue_success_percent'], 'turn_pass_rate': result['turn_success_percent'], 'report': destination.name})
            continue
        report = run_benchmark(host, load_cases(path))
        destination = output / (path.stem + '.json')
        destination.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        summaries.append({'corpus': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'cases': report.total, 'passes': sum((item.passed for item in report.results)), 'pass_rate': report.pass_rate, 'average_score': report.average_score, 'report': destination.name})
    (output / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n', encoding='utf-8')
    return summaries

def compare(baseline: Path, current: Path):
    """Keep improvements from masking individual formerly passing failures."""
    regressions, improvements, summaries = ([], [], [])
    for name in CORPORA:
        report = Path(name).stem + '.json'
        old = json.loads((baseline / report).read_text(encoding='utf-8'))
        new = json.loads((current / report).read_text(encoding='utf-8'))
        previous = {row['id']: row for row in old['results']}
        assert set(previous) == {row['id'] for row in new['results']}
        corpus_regressions, corpus_improvements = ([], [])
        for row in new['results']:
            before = previous[row['id']]
            receipt = {'corpus': report, 'id': row['id'], 'query': row.get('query'), 'selected_before': before.get('selected'), 'selected_after': row.get('selected'), 'reasons': row.get('reasons'), 'turns': row.get('turns')}
            if before['passed'] and (not row['passed']):
                corpus_regressions.append(receipt)
            elif not before['passed'] and row['passed']:
                corpus_improvements.append(receipt)
        regressions.extend(corpus_regressions)
        improvements.extend(corpus_improvements)
        summaries.append({'corpus': report, 'regressions': len(corpus_regressions), 'improvements': len(corpus_improvements)})
    result = {'corpora': summaries, 'regressions': regressions, 'improvements': improvements, 'regression_count': len(regressions), 'improvement_count': len(improvements)}
    (current / 'comparison-vs-baseline.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--compare-only', action='store_true')
    args = parser.parse_args()
    if not args.compare_only:
        print(json.dumps(run(args.root.resolve(), args.output.resolve()), sort_keys=True))
    if args.baseline:
        result = compare(args.baseline.resolve(), args.output.resolve())
        print(json.dumps({k: v for k, v in result.items() if k not in {'regressions', 'improvements'}}, sort_keys=True))
