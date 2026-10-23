"""Publish compact manager evidence; raw messages and private oracles stay private."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def reference(path):
    return {'path': str(path.resolve().relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def publish(model, tokens, regressions, proof, output):
    rows = [read(path) for path in sorted(model.glob('*/*/receipt.json'))]
    timings = [row['native_memory_request_ms'] for row in rows]
    identity = read(model / 'RUNTIME_IDENTITY.json')
    before = read(ROOT / 'data/campaign3-manager/baseline-model/RUNTIME_IDENTITY.json')
    metadata = read(model / 'RUN_METADATA.json')
    suites = ET.parse(regressions).getroot()
    test_suites = list(suites.iter('testsuite'))
    evidence = {'captured_at': datetime.now(timezone.utc).isoformat(), 'model': read(model / 'SUMMARY.json'), 'model_status_counts': dict(Counter((row['status'] for row in rows))), 'error_type_counts': dict(Counter((row.get('error', {}).get('type') for row in rows if row.get('error')))), 'separate_post_refusal_inspection_reasons': dict(Counter((reason for row in rows for endpoint in row.get('separate_original_admission_inspection', {}).get('excluded', []) for reason in endpoint.get('reasons', [])))), 'available_ram_at_attempt_bytes': {'minimum': min((row['resource_before']['available_ram_bytes'] for row in rows)) if rows else None, 'maximum': max((row['resource_before']['available_ram_bytes'] for row in rows)) if rows else None}, 'model_categories': sorted({row.get('category') for row in rows if row.get('category')}), 'model_source_unchanged': metadata['source_unchanged'], 'model_file': identity.get('model_process', {}).get('model_file'), 'model_sha256': identity.get('model_process', {}).get('model_sha256'), 'model_identity_unchanged': before.get('model_process') == identity.get('model_process'), 'launcher_identity_unchanged': before.get('parent_process') == identity.get('parent_process'), 'observed_laya_config': identity['laya_config'], 'observed_memory_config': identity['memory_config'], 'observed_laya_environment': identity.get('parent_laya_flags'), 'original_model_health': identity['original_client_health'], 'admission_attempt_latency_ms': {'samples': len(timings), 'p50': statistics.median(timings) if timings else None, 'p95': statistics.quantiles(timings, n=100, method='inclusive')[94] if len(timings) > 1 else None, 'scope': 'Native request time, including blocked attempts; separate admission inspection excluded. Not generated-answer latency.'}, 'exact_retrieval_tokens': {'baseline': read(ROOT / 'data/campaign3-manager/baseline-tokens/SUMMARY.json'), 'final': read(tokens / 'SUMMARY.json')}, 'regressions': {key: sum((int(suite.get(key, '0')) for suite in test_suites)) for key in ('tests', 'failures', 'errors', 'skipped')}, 'regression_duration_seconds': sum((float(suite.get('time', '0')) for suite in test_suites)), 'references': {name: reference(path) for name, path in {'model_summary': model / 'SUMMARY.json', 'model_source': model / 'RUN_METADATA.json', 'model_selection': model / 'SELECTED_DEVELOPMENT.json', 'token_summary': tokens / 'SUMMARY.json', 'regressions': regressions, 'source_freeze': proof}.items()}, 'source_freeze_file_count': len(read(proof)['files']), 'scope': 'No owner memory database was opened. Actual model responses require generation HTTP evidence. Controlled fixtures and tokenizer calls are separate.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'output': str(output), 'model_attempts': len(rows), 'actual_generation_http_requests': evidence['model']['actual_model_http_requests'], 'regressions': evidence['regressions']}))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('model', 'tokens', 'regressions', 'proof', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    publish(args.model, args.tokens, args.regressions, args.proof, args.output)
