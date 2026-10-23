"""Independent bounded typed-reference controls; no planner or model calls."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from hanni.workflows.references import resolve

def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_file = Path(__file__).parents[2] / 'src/hanni/workflows/references.py'
    before = hashlib.sha256(source_file.read_bytes()).hexdigest()
    controls = [('exact-bounded-integer', 'integer', 7 * 10 ** 380, 'value'), ('integer-as-string', 'string', 7 * 10 ** 380, 'WorkflowError'), ('integer-as-number', 'number', 7 * 10 ** 380, 'WorkflowError'), ('boolean-is-not-integer', 'integer', False, 'WorkflowError'), ('finite-number', 'number', -8.125, 'value'), ('integer-exact-small', 'integer', -27, 'value')]
    receipts = []
    for key, kind, value, expected in controls:
        row = {'id': key, 'type': kind, 'expected_class': expected}
        try:
            actual = resolve({'argument': {'$ref': {'step_id': 'source', 'path': '/data/reading', 'type': kind}}}, ['source'], {'source': {'status': 'verified', 'verification': {'status': 'VERIFIED'}, 'result': {'data': {'reading': value}}}})
            row.update(classification='value', actual=actual, passed=expected == 'value' and actual['argument'] == value)
        except Exception as exc:
            row.update(classification=type(exc).__name__, message=str(exc), passed=type(exc).__name__ == expected)
        receipts.append(row)
    result = {'scope': 'direct_original_reference_function_no_execution_or_model', 'count': len(receipts), 'passed': sum((x['passed'] for x in receipts)), 'source_before': before, 'source_after': hashlib.sha256(source_file.read_bytes()).hexdigest(), 'receipts': receipts}
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({key: result[key] for key in ('count', 'passed', 'source_before', 'source_after')}))
