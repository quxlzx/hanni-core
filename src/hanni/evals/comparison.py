"""Compare completed tool-eval reports only when their test protocol matches."""
from __future__ import annotations

import json
from pathlib import Path

COMPARABLE_KEYS = ('corpus_sha256', 'routed_menus_sha256', 'prompt_sha256',
                   'evaluator_sha256', 'owner_timezone', 'max_tool_rounds', 'total_scenarios',
                   'context_length', 'max_tokens', 'max_tool_calls_per_case',
                   'tool_temperature', 'final_temperature', 'top_p')


def compare_reports(first: dict, second: dict) -> dict:
    if first.get('status') != 'completed' or second.get('status') != 'completed':
        raise ValueError('Both reports must be completed live-model evaluations.')
    count = first.get('total_scenarios')
    if not isinstance(count, int) or count <= 0 or second.get('total_scenarios') != count:
        raise ValueError('Reports must have the same positive scenario count.')
    first_ids = [row.get('id') for row in first.get('results', ())]
    second_ids = [row.get('id') for row in second.get('results', ())]
    if len(first_ids) != count or len(second_ids) != count or len(set(first_ids)) != count or first_ids != second_ids:
        raise ValueError('Reports must contain the same unique scenario results in order.')
    missing = [key for key in COMPARABLE_KEYS if first.get(key) is None or second.get(key) is None]
    if missing:
        raise ValueError('Reports lack comparison metadata: ' + ', '.join(missing))
    different = [key for key in COMPARABLE_KEYS if first[key] != second[key]]
    if different:
        raise ValueError('Reports used different test protocols: ' + ', '.join(different))
    warnings = []
    if first.get('quantization') != second.get('quantization'):
        warnings.append('Quantization differs; compare quality and latency with caution.')
    warnings.append('Physical hardware and VRAM usage are not verified; confirm the same machine manually.')
    return {'first':first, 'second':second, 'warnings':warnings}


def render_comparison(comparison: dict) -> str:
    first, second = comparison['first'], comparison['second']
    one, two = first['summary'], second['summary']
    label = lambda report: Path(report.get('model_file') or report.get('model_id') or 'model').stem
    rows = [f"HANNI LLM Tool Eval comparison ({first['total_scenarios']} cases)",
            f"Corpus SHA-256: {first['corpus_sha256']}",
            f"{'Metric':30} {label(first):>17} {label(second):>17}", '-' * 66]
    def metric(name, a, b, suffix=''):
        def fmt(value):
            return 'n/a' if value is None else f'{value:.2f}{suffix}'
        rows.append(f'{name:30} {fmt(a):>17} {fmt(b):>17}')
    for title, key in (('Task success','task_success_rate'), ('Tool selection','tool_selection_accuracy'),
                       ('Arguments','argument_accuracy'), ('Reasoning','reasoning_accuracy'),
                       ('Hallucinated tools','hallucination_rate'), ('Unsupported claims','unsupported_claim_rate')):
        metric(title, one.get(key), two.get(key), '%')
    for family in sorted(set(one.get('families', {})) | set(two.get('families', {}))):
        metric(family, one.get('families', {}).get(family, {}).get('task_success_rate'),
               two.get('families', {}).get(family, {}).get('task_success_rate'), '%')
    for title, key in (('Average tool calls','average_tool_calls'),
                       ('Average latency (ms)','average_latency_ms'),
                       ('Measured tokens/sec','measured_completion_tokens_per_second')):
        metric(title, one.get(key), two.get(key))
    metric('VRAM usage (MB)', first.get('vram_usage_mb'), second.get('vram_usage_mb'))
    rows.extend('Note: ' + warning for warning in comparison['warnings'])
    return '\n'.join(rows)


def run_cli(args) -> int:
    try:
        first = json.loads(Path(args.first).read_text(encoding='utf-8'))
        second = json.loads(Path(args.second).read_text(encoding='utf-8'))
        print(render_comparison(compare_reports(first, second)))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Cannot compare LLM reports: {exc}')
        return 2
