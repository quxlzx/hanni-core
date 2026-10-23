"""Bounded original-service development run; no actual inference or owner reads."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import time
import zipfile
from .harness import REPO, run_case, digest
from .grading import score

def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8', newline='\n')

def source_manifest():
    paths = sorted((REPO / 'src/hanni').rglob('*.py'))
    paths += sorted((REPO / 'scripts/campaign10_core').glob('*.py'))
    paths += sorted((REPO / 'scripts/campaign2').glob('platform_*.py'))
    return {p.relative_to(REPO).as_posix(): digest(p) for p in paths}

def archive(out, manifest):
    with zipfile.ZipFile(out / 'original-source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for relative in manifest:
            output.write(REPO / relative, relative)

def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * percent)]

def execute(inputs, oracles, output, *, limit=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads(Path(inputs).read_text(encoding='utf-8'))
    expectations = json.loads(Path(oracles).read_text(encoding='utf-8'))
    if limit is not None:
        cases = cases[:limit]
    before = source_manifest()
    write(output / 'SOURCE_BEFORE.json', before)
    archive(output, before)
    write(output / 'INPUT_BINDING.json', {'inputs_sha256': digest(inputs), 'oracles_sha256': digest(oracles), 'source_zip_sha256': digest(output / 'original-source.zip'), 'cases': len(cases), 'scope': 'Prescribed original contracts; no model, owner data or live providers'})
    rows, declared, entered, category_counts = ([], {}, Counter(), defaultdict(Counter))
    began = time.perf_counter()
    for index, case in enumerate(cases, 1):
        root = output / f'case-{index:03d}'
        root.mkdir()
        try:
            raw = run_case(case, root)
        except Exception as exc:
            raw = {'id': case['id'], 'category': case['category'], 'mode': 'HARNESS_ERROR', 'error': {'type': type(exc).__name__, 'message': str(exc)}, 'actions': {}, 'actual_generated': False, 'model_call_count': 0}
        raw_path = output / f'receipt-{index:03d}.json'
        write(raw_path, raw)
        try:
            graded = score(case, expectations[case['id']], raw)
        except Exception as exc:
            graded = {'id': case['id'], 'passed': False, 'grade_error': {'type': type(exc).__name__, 'message': str(exc)}, 'checks': []}
        write(output / f'grade-{index:03d}.json', graded)
        for definition in raw.get('inventory_after', []):
            declared[definition['id']] = definition
        for action in raw.get('actions', {}).values():
            for entry in action.get('handler_entries', []):
                if isinstance(entry.get('tool'), str):
                    entered[entry['tool']] += 1
        row = {'id': case['id'], 'category': case['category'], 'passed': graded['passed'], 'raw_sha256': digest(raw_path), 'elapsed_ms': raw.get('elapsed_ms'), 'harness_error': raw.get('error'), 'checks': len(graded['checks']), 'failed_checks': sum((not c['passed'] for c in graded['checks']))}
        rows.append(row)
        category_counts[case['category']]['cases'] += 1
        category_counts[case['category']]['passed'] += int(graded['passed'])
        write(output / 'CHECKPOINT.json', {'closed_cases': index, 'total': len(cases), 'rows': rows, 'model_call_count': 0, 'preserved_failures': True})
        print(json.dumps(row), flush=True)
    after = source_manifest()
    write(output / 'SOURCE_AFTER.json', after)
    coverage = [{'definition': declared[name], 'original_handler_entries': entered[name], 'outcome': 'ORIGINAL_ENTRY_OBSERVED' if entered[name] else 'NOT_TESTED_IN_CORE_TASKS', 'scope': 'Actual prescribed contract entry count; does not assert all capability dimensions'} for name in sorted(declared)]
    write(output / 'CAPABILITY_COVERAGE.json', coverage)
    times = [r['elapsed_ms'] for r in rows if r['elapsed_ms'] is not None]
    summary = {'tasks': len(rows), 'passed': sum((r['passed'] for r in rows)), 'failed': sum((not r['passed'] for r in rows)), 'rows': rows, 'categories': {key: dict(value) for key, value in category_counts.items()}, 'actual_model_calls': 0, 'semantic_model_accuracy': None, 'whole_case_latency_ms': {'p50': statistics.median(times) if times else None, 'p95': percentile(times, 0.95), 'denominator': len(times), 'scope': 'Setup, original dispatch, readback and snapshots; excludes service cleanup'}, 'batch_ms': (time.perf_counter() - began) * 1000, 'source_unchanged': before == after, 'registered_inventory': len(declared), 'distinct_original_handler_entries': len(entered), 'all_failures_preserved': True, 'oracles_unchanged': True, 'scope': 'Controlled original implementation contracts, never natural-language E2E success'}
    write(output / 'SUMMARY.json', summary)
    return summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--oracles', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    summary = execute(args.inputs, args.oracles, args.output, limit=args.limit)
    print(json.dumps({key: summary[key] for key in ('tasks', 'passed', 'failed', 'source_unchanged')}))
if __name__ == '__main__':
    main()
