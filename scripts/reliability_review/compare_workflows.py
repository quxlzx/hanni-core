"""Compare controlled workflow evidence, never a final holdout or live model.

The runner and development fixtures are shared across both source revisions.
Outcome counts, Wilson intervals and paired latency summaries remain descriptive;
scripted model choices are not measurements of configured-model intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).with_name('run_workflows.py')
FIXTURES = ROOT / 'tests/fixtures/reliability_workflows.py'
SDK_FIXTURE = ROOT / 'tests/fixtures/mcp_hub_mock.py'
STAGES = ('intent', 'retrieval', 'selection', 'arguments', 'authorization',
          'execution', 'outcome', 'final_answer')
KINDS = ('positive', 'safe_refusal', 'expected_failure', 'unverified_receipt')


def wilson(successes: int, total: int) -> dict:
    if not 0 <= successes <= total:
        raise ValueError('Invalid metric counts')
    if not total:
        return {'passed': 0, 'total': 0, 'rate': None, 'ci95': None}
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return {'passed': successes, 'total': total, 'rate': proportion,
            'ci95': {'lower': max(0, center - half), 'upper': min(1, center + half)}}


def percentiles(values: list[float]) -> dict:
    if not values:
        return {'samples': 0, 'p50_ms': None, 'p95_ms': None}
    ordered = sorted(values)
    rank = 0.95 * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    p95 = ordered[low] + (ordered[high] - ordered[low]) * (rank - low)
    return {'samples': len(values), 'p50_ms': statistics.median(values), 'p95_ms': p95}


def read_report(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Workflow report must be an object: {path}')
    return value


def run(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(RUNNER), '--source-root', str(source.resolve()),
         '--output', str(destination.resolve())],
        cwd=ROOT, check=True,
    )
    # Stable runner artifact name is agreed with the execution worker.
    return destination / 'workflows.json'


def fixture_hash() -> str:
    return hashlib.sha256(FIXTURES.read_bytes()).hexdigest()


def source_hash(source: Path) -> str:
    """Fingerprint runtime packages only; never enumerate/read evaluation sets."""
    digest = hashlib.sha256()
    package = source.resolve() / 'src/hanni'
    folders = ('tools', 'mcp', 'reliability', 'dashboard', 'core', 'memory', 'config', 'models', 'logs')
    for folder in folders:
        path = package / folder
        if path.exists():
            for module in sorted(path.rglob('*.py')):
                digest.update(str(module.relative_to(package)).encode())
                digest.update(module.read_bytes())
    return digest.hexdigest()


def checked_rows(report: dict) -> dict[str, dict]:
    rows = report.get('results')
    if not isinstance(rows, list):
        raise ValueError('Workflow report requires results[]')
    indexed = {}
    for row in rows:
        identifier = row.get('id')
        if not isinstance(identifier, str) or identifier in indexed:
            raise ValueError('Workflow case IDs must be unique strings')
        if row.get('expected_outcome_kind') not in KINDS:
            raise ValueError(f'{identifier}: missing explicit expected_outcome_kind')
        if type(row.get('passed')) is not bool:
            raise ValueError(f'{identifier}: passed must be an observed boolean')
        stages = row.get('stages')
        if not isinstance(stages, dict):
            raise ValueError(f'{identifier}: stages must be an object')
        if row.get('harness_error') is None and set(stages) != set(STAGES):
            raise ValueError(f'{identifier}: all eight stages must be explicit (true/false/null)')
        if any(value is not None and type(value) is not bool for value in stages.values()):
            raise ValueError(f'{identifier}: stage evidence must be boolean or not applicable')
        latency = row.get('latency_ms')
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
            raise ValueError(f'{identifier}: invalid latency')
        indexed[identifier] = row
    if report.get('count') != len(indexed):
        raise ValueError('Workflow report count differs from unique case count')
    return indexed


def rate(rows, predicate) -> dict:
    return wilson(sum(bool(predicate(row)) for row in rows), len(rows))


def summary(indexed: dict[str, dict]) -> dict:
    rows = list(indexed.values())
    positives = [row for row in rows if row['expected_outcome_kind'] == 'positive']
    result = {
        'pipeline_expectations': rate(rows, lambda row: row['passed']),
        'groups': {
            kind: rate([row for row in rows if row['expected_outcome_kind'] == kind],
                       lambda row: row['passed']) for kind in KINDS
        },
        # Fixture outcome assertions are distinct from execution tracing. An
        # absent old trace is unknown, not proof that the old outcome failed.
        'positive_fixture_outcomes': rate(positives, lambda row: row['stages'].get('outcome') is True),
        'positive_recorded_verified_scopes': rate(
            positives, lambda row: row.get('observed_verification') == 'VERIFIED'),
        'positive_recorded_partial_scopes': rate(
            positives, lambda row: row.get('observed_verification') == 'PARTIALLY_VERIFIED'),
        'positive_verification_not_recorded': sum(
            row.get('observed_verification') is None for row in positives),
        'stage_success': {
            stage: rate([row for row in rows if row['stages'].get(stage) is not None],
                        lambda row: row['stages'][stage]) for stage in STAGES
        },
        'harness_errors': sum(bool(row.get('harness_error')) for row in rows),
        'latency': percentiles([row['latency_ms'] for row in rows]),
    }
    for field in ('duplicate_side_effects', 'unauthorized_sensitive_executions'):
        values = [row.get(field) for row in rows]
        valid = all(type(value) is int and value >= 0 for value in values)
        result[field] = {'observed_count': sum(values) if valid else None,
                         'measured_cases': sum(type(value) is int and value >= 0 for value in values),
                         'total_cases': len(rows)}
    recovery = [row for row in rows if row.get('recovery_required') is True]
    result['recovery_success'] = rate(recovery, lambda row: row.get('recovery_success') is True)
    independent = [row for row in positives if row.get('independent_outcome_check') is not None]
    result['positive_independent_fixture_checks'] = rate(
        independent, lambda row: row.get('independent_outcome_check') is True)
    result['positive_independent_check_not_measured'] = len(positives) - len(independent)
    return result


def compare(before: dict, after: dict) -> dict:
    if not before.get('case_sha256') or before['case_sha256'] != after.get('case_sha256'):
        raise ValueError('Before/after fixtures differ; comparison refused')
    old, new = checked_rows(before), checked_rows(after)
    if old.keys() != new.keys():
        raise ValueError('Before/after case sets differ; comparison refused')
    paired = []
    failures = []
    for identifier in old:
        prior, current = old[identifier], new[identifier]
        if (prior['fixture'] != current['fixture'] or
                prior['expected_outcome_kind'] != current['expected_outcome_kind']):
            raise ValueError(f'{identifier}: expected fixture or outcome kind differs')
        pair = {'id': identifier, 'kind': current['expected_outcome_kind'],
                'before_passed': prior['passed'], 'after_passed': current['passed'],
                'before_ms': prior['latency_ms'], 'after_ms': current['latency_ms'],
                'delta_ms': current['latency_ms'] - prior['latency_ms']}
        paired.append(pair)
        if not prior['passed'] or not current['passed']:
            failures.append({
                'id': identifier, 'kind': pair['kind'],
                'before_failed_stages': [key for key in STAGES if prior['stages'].get(key) is False],
                'after_failed_stages': [key for key in STAGES if current['stages'].get(key) is False],
                'before_harness_error': prior.get('harness_error'),
                'after_harness_error': current.get('harness_error'),
                'before_errors': prior.get('errors', []), 'after_errors': current.get('errors', []),
                'before_verification': prior.get('observed_verification'),
                'after_verification': current.get('observed_verification'),
            })
    return {
        'scope': 'CONTROLLED DEVELOPMENT; deterministic model clients, not live-model intelligence',
        'fixture_sha256': before['case_sha256'],
        'conditions': {'before': before.get('conditions'), 'after': after.get('conditions')},
        'latency_percentile_method': 'Linear interpolation over sorted per-case measured latencies',
        'sources': {'before': before.get('source_root'), 'after': after.get('source_root')},
        'before': summary(old), 'after': summary(new),
        'paired': {
            'both_passed': sum(row['before_passed'] and row['after_passed'] for row in paired),
            'improved': sum(not row['before_passed'] and row['after_passed'] for row in paired),
            'regressed': sum(row['before_passed'] and not row['after_passed'] for row in paired),
            'both_failed': sum(not row['before_passed'] and not row['after_passed'] for row in paired),
            'latency_delta': percentiles([row['delta_ms'] for row in paired]),
        },
        'paired_cases': paired, 'failure_analysis': failures,
        'limitations': [
            'Intent and tool choice use scripted fixtures; no configured-model understanding is measured.',
            'Pipeline PASS includes expected refusal/failure/receipt handling; it is not positive task completion.',
            'VERIFIED refers to the recorded evidence scope; independent checks are reported separately.',
            'Null stage metrics are not applicable; absent evidence is not counted as successful measurement.',
            'Wilson intervals describe these exposed fixtures, not representative real-world performance.',
            'Latency includes fixture setup and execution; it excludes live model inference and voice capture.',
        ],
    }


def display_rate(value: dict) -> str:
    if value['rate'] is None:
        return 'Not measured (0 cases)'
    interval = value['ci95']
    return (f"{value['passed']}/{value['total']} ({value['rate']:.1%}; "
            f"95% Wilson {interval['lower']:.1%}–{interval['upper']:.1%})")


def render(report: dict) -> str:
    before, after = report['before'], report['after']
    lines = ['# Controlled development workflow comparison', '', report['scope'], '',
             'The same exposed fixtures run through each original source pipeline. OS/model/provider '
             'boundaries use controlled seams; no real-model intelligence score is implied.', '',
             '| Measure | Original | Current |', '|---|---|---|']
    metrics = [('Pipeline expectations (all kinds)', 'pipeline_expectations'),
               ('Positive fixture outcomes', 'positive_fixture_outcomes'),
               ('Recorded verified positive scopes', 'positive_recorded_verified_scopes'),
               ('Recorded partially verified positive scopes', 'positive_recorded_partial_scopes'),
               ('Positive independent fixture checks', 'positive_independent_fixture_checks'),
               ('Recovery success', 'recovery_success')]
    for title, key in metrics:
        lines.append(f'| {title} | {display_rate(before[key])} | {display_rate(after[key])} |')
    for kind in KINDS:
        lines.append(f"| {kind} expectation handling | {display_rate(before['groups'][kind])} | {display_rate(after['groups'][kind])} |")
    lines.extend(['', 'All eight stages (scripted-client intent is not measured; null stages are not applicable):', '',
                  '| Stage | Original | Current |', '|---|---|---|'])
    for stage in STAGES:
        lines.append(f"| {stage} | {display_rate(before['stage_success'][stage])} | {display_rate(after['stage_success'][stage])} |")
    lines.extend(['', 'Latency includes setup and controlled execution, not model inference.', '',
                  '| Paired latency | Original | Current |', '|---|---|---|'])
    for key in ('p50_ms', 'p95_ms'):
        lines.append(f"| {key} | {before['latency'][key]:.3f} ms | {after['latency'][key]:.3f} ms |")
    lines.extend(['', f"Paired outcomes: {json.dumps(report['paired'])}", '',
                  'Side effects and permission failures:', '',
                  f"- Original duplicates: {json.dumps(before['duplicate_side_effects'])}",
                  f"- Current duplicates: {json.dumps(after['duplicate_side_effects'])}",
                  f"- Original unauthorized sensitive executions: {json.dumps(before['unauthorized_sensitive_executions'])}",
                  f"- Current unauthorized sensitive executions: {json.dumps(after['unauthorized_sensitive_executions'])}",
                  '', 'Failures are retained without excluding difficult cases:', ''])
    for failure in report['failure_analysis']:
        lines.append(f"- {failure['id']} ({failure['kind']}): before {failure['before_failed_stages']} "
                     f"{failure['before_harness_error'] or ''}; after {failure['after_failed_stages']} "
                     f"{failure['after_harness_error'] or ''}.")
    lines.extend(['', 'Limits:', ''] + [f'- {text}' for text in report['limitations']])
    return '\n'.join(lines) + '\n'


def self_test() -> None:
    """Comparator unit checks only; these are never workflow benchmark cases."""
    from copy import deepcopy
    zero, complete = wilson(0, 10), wilson(10, 10)
    assert abs(zero['ci95']['upper'] - 0.2775327998628892) < 1e-12
    assert abs(complete['ci95']['lower'] - 0.7224672001371107) < 1e-12
    assert wilson(0, 0)['rate'] is None
    assert percentiles([1, 2, 3, 4])['p50_ms'] == 2.5
    fixture = {'id': 'COMPARATOR-UNIT-ONLY', 'fixture': 'synthetic-comparator-check',
               'expected_outcome_kind': 'positive', 'passed': True,
               'stages': dict.fromkeys(STAGES, True), 'latency_ms': 1.0,
               'duplicate_side_effects': 0, 'unauthorized_sensitive_executions': 0}
    before = {'case_sha256': 'unit-only', 'count': 1, 'results': [fixture]}
    after = deepcopy(before)
    after['results'][0]['passed'] = False
    after['results'][0]['stages']['outcome'] = False
    after['results'][0]['duplicate_side_effects'] = 1
    result = compare(before, after)
    assert result['paired']['regressed'] == 1
    assert result['before']['positive_verification_not_recorded'] == 1
    assert result['before']['positive_recorded_verified_scopes']['passed'] == 0
    assert result['after']['duplicate_side_effects']['observed_count'] == 1
    assert result['after']['recovery_success']['rate'] is None
    for mutation in ('hash', 'kind', 'stage'):
        invalid = deepcopy(after)
        if mutation == 'hash':
            invalid['case_sha256'] = 'changed'
        elif mutation == 'kind':
            invalid['results'][0]['expected_outcome_kind'] = 'safe_refusal'
        else:
            invalid['results'][0]['stages'].pop('authorization')
        try:
            compare(before, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Comparator accepted mismatched {mutation}')
    print('Comparator-only statistics, evidence separation and mismatch checks PASS')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-root', type=Path,
                        default=ROOT / 'data/hanni-reliability-v2-review/original-source')
    parser.add_argument('--current-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'data/hanni-reliability-v2-review/workflow-comparison')
    parser.add_argument('--before-report', type=Path)
    parser.add_argument('--after-report', type=Path)
    parser.add_argument('--self-test', action='store_true', help='Comparator unit checks; no workflow execution')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if bool(args.before_report) != bool(args.after_report):
        parser.error('--before-report and --after-report must be supplied together')
    inputs = {'fixture': fixture_hash(), 'runner': hashlib.sha256(RUNNER.read_bytes()).hexdigest(),
              'sdk_fixture': hashlib.sha256(SDK_FIXTURE.read_bytes()).hexdigest()}
    revisions = {'before': source_hash(args.original_root), 'after': source_hash(args.current_root)}
    before_path = args.before_report or run(args.original_root, args.output / 'before')
    after_path = args.after_report or run(args.current_root, args.output / 'after')
    before, after = read_report(before_path), read_report(after_path)
    if not args.before_report:
        if (inputs['fixture'] != fixture_hash()
                or inputs['runner'] != hashlib.sha256(RUNNER.read_bytes()).hexdigest()
                or inputs['sdk_fixture'] != hashlib.sha256(SDK_FIXTURE.read_bytes()).hexdigest()
                or revisions['before'] != source_hash(args.original_root)
                or revisions['after'] != source_hash(args.current_root)):
            raise RuntimeError('Runner, fixture or source changed during execution; comparison refused')
    result = compare(before, after)
    result['input_hashes'] = inputs if not args.before_report else {
        'fixture': before['case_sha256'], 'runner': None,
        'scope': 'Provided artifacts; original runner bytes were not captured by this invocation',
    }
    result['runtime_source_hashes'] = revisions if not args.before_report else {
        'before': before.get('runtime_source_sha256'),
        'after': after.get('runtime_source_sha256'),
        'scope': 'Only hashes present in the supplied artifacts; current files are not presumed tested',
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (args.output / 'comparison.md').write_text(render(result), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in {'paired_cases', 'failure_analysis'}}, indent=2))


if __name__ == '__main__':
    main()
