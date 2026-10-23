"""Prospectively sealed bounded reference/schema probes over original functions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from hanni.workflows.references import resolve
from hanni.workflows.transport_schema import generation_schema
from hanni.workflows.types import WorkflowError

def probes():
    return [{'id': 'integer-large', 'type': 'integer', 'value': 10 ** 400, 'expected': 'exact_value'}, {'id': 'number-large', 'type': 'number', 'value': 10 ** 400, 'expected': 'WorkflowError'}, {'id': 'integer-bool', 'type': 'integer', 'value': True, 'expected': 'WorkflowError'}, {'id': 'string-integer-large', 'type': 'string', 'value': 10 ** 400, 'expected': 'WorkflowError'}, {'id': 'number-finite', 'type': 'number', 'value': 12.5, 'expected': 'exact_value'}, {'id': 'escaped-key', 'type': 'string', 'value': {'a/b': {'~k': 'quoted evidence'}}, 'path': '/data/value/a~1b/~0k', 'expected_value': 'quoted evidence', 'expected': 'exact_value'}, {'id': 'noncanonical-index', 'type': 'string', 'value': ['first', 'second'], 'path': '/data/value/01', 'expected': 'WorkflowError'}, {'id': 'unverified-source', 'type': 'string', 'value': 'available', 'source_status': 'unverified', 'expected': 'WorkflowError'}, {'id': 'outside-dependency', 'type': 'string', 'value': 'available', 'dependencies': [], 'expected': 'WorkflowError'}, {'id': 'literal-schema', 'kind': 'schema', 'expected': 'schema_literal_preserved'}]

def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    from scripts.campaign4.run_cohort import production_manifest
    source_before = production_manifest()
    (output / 'source-before.json').write_text(json.dumps(source_before, indent=2), encoding='utf-8')
    cases = probes()
    raw = json.dumps(cases, sort_keys=True, indent=2).encode() + b'\n'
    (output / 'sealed-probes.json').write_bytes(raw)
    receipts = []
    for case in cases:
        if case.get('kind') == 'schema':
            schema = {'type': 'object', 'properties': {'value': {'type': 'string', 'minLength': 2}}, 'const': {'pattern': 'literal payload', 'minItems': 7}}
            before = deepcopy(schema)
            value = generation_schema(schema)
            receipt = {'id': case['id'], 'classification': 'schema_literal_preserved', 'passed': schema == before and value['const'] == before['const'] and ('minLength' not in value['properties']['value'])}
        else:
            source = {'status': case.get('source_status', 'verified'), 'verification': {'status': 'VERIFIED'}, 'result': {'ok': True, 'data': {'value': case['value']}}}
            try:
                value = resolve({'$ref': {'step_id': 'source', 'path': case.get('path', '/data/value'), 'type': case['type']}}, case.get('dependencies', ['source']), {'source': source})
                receipt = {'id': case['id'], 'classification': 'exact_value', 'observed': value, 'passed': case['expected'] == 'exact_value' and value == case.get('expected_value', case['value'])}
            except Exception as exc:
                receipt = {'id': case['id'], 'classification': type(exc).__name__, 'error': str(exc), 'passed': type(exc).__name__ == case['expected']}
        receipts.append(receipt)
    summary = {'sealed_sha256': hashlib.sha256(raw).hexdigest(), 'cases': len(cases), 'passed': sum((row['passed'] for row in receipts)), 'receipts': receipts, 'scope': 'direct_original_reference_and_transport_schema; no scheduler/model claim'}
    source_after = production_manifest()
    summary['source_uniform'] = source_before == source_after
    (output / 'source-after.json').write_text(json.dumps(source_after, indent=2), encoding='utf-8')
    (output / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    print(json.dumps(run(parser.parse_args().output), indent=2))
