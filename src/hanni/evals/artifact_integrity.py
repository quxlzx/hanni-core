"""Reject incomplete or internally inconsistent live LLM benchmark artifacts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_HASH_FIELDS = ('corpus_sha256', 'prompt_sha256', 'evaluator_sha256', 'routed_menus_sha256')
_IDENTITY_FIELDS = ('model_id', 'model_file', 'api_model', 'endpoint', 'quantization',
                    'config_profile', 'owner_timezone', 'production_timezone')


def validate_llm_artifact(report: dict) -> list[str]:
    errors = []
    for field in (*_HASH_FIELDS, *_IDENTITY_FIELDS, 'timestamp', 'total_scenarios',
                  'completed_scenarios', 'results', 'summary', 'status'):
        if field not in report or report[field] in (None, ''):
            errors.append(f'missing {field}')
    for field in _HASH_FIELDS:
        if field in report and not re.fullmatch(r'[0-9a-f]{64}', str(report[field])):
            errors.append(f'invalid {field}')
    rows = report.get('results', [])
    if not isinstance(rows, list):
        return errors + ['results is not a list']
    ids = [row.get('id') for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        errors.append('duplicate or missing result IDs')
    if report.get('completed_scenarios') != len(rows):
        errors.append('completed count does not match results')
    if report.get('status') == 'completed' and report.get('total_scenarios') != len(rows):
        errors.append('completed artifact has missing cases')
    summary = report.get('summary') or {}
    if isinstance(summary, dict) and rows and all(isinstance(row, dict) and 'passed' in row for row in rows):
        actual = round(100 * sum(bool(row['passed']) for row in rows) / len(rows), 2)
        if summary.get('task_success_rate') != actual:
            errors.append('task success rate disagrees with result rows')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding='utf-8'))
    errors = validate_llm_artifact(report)
    if errors:
        for error in errors:
            print('INVALID: ' + error)
        return 1
    print(f"Artifact valid: {len(report['results'])} {report['status']} cases; "
          f"model {report['model_id']}; corpus {report['corpus_sha256'][:12]}.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
