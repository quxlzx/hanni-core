"""Publish source provenance and XML assertions, never private task material."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ('baseline-regressions', 'controlled-before', 'controlled-before-v2', 'collaboration-before', 'bootstrap-before', 'bootstrap-before-expanded', 'fallback-before', 'http-identity-before', 'identity-profile-before', 'cycle1-focused', 'cycle1-focused-b', 'http-identity-repair', 'cycle2-relevant', 'cycle2-relevant-b', 'cycle2-focused', 'cycle2-final-focused')
PRODUCTION = ('src/hanni/models/adaptive.py', 'src/hanni/models/collaboration.py', 'src/hanni/models/client.py', 'src/hanni/compute/scheduler.py')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    receipts = []
    for name in ARTIFACTS:
        path = ROOT / 'data/campaign5-intelligence' / (name + '.xml')
        if not path.exists():
            continue
        suite = ET.parse(path).getroot().find('testsuite')
        cases = suite.findall('testcase')
        rows = []
        for case in cases:
            outcome = 'error' if case.find('error') is not None else 'failed' if case.find('failure') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
            rows.append({'node': case.get('classname') + '::' + case.get('name'), 'outcome': outcome, 'seconds': float(case.get('time', 0))})
        receipts.append({'id': name, 'scope': 'original_logic_controlled_dependencies', 'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path), 'declared_tests': int(suite.get('tests')), 'seconds': float(suite.get('time')), 'counts': {key: sum((row['outcome'] == key for row in rows)) for key in ('passed', 'failed', 'error', 'skipped')}, 'assertions': rows})
    source_paths = list(PRODUCTION) + ['tests/unit/test_compute_registry.py']
    source_paths += [p.relative_to(ROOT).as_posix() for p in (ROOT / 'scripts/campaign5_intelligence').glob('*.py')]
    source_paths += [p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests/integration').glob('test_campaign5_intelligence*.py')]
    payload = {'schema_version': 1, 'scope': 'Campaign 5 native implementation controls; not model-quality scores', 'actual_model_responses_in_this_audit': 0, 'transport_note': 'Owned loopback HTTP/SSE is real protocol transport with controlled provider bytes; other dependencies are controlled adapters.', 'original_archive': {'path': 'data/campaign5-intelligence/original-source/source.zip', 'sha256': digest(ROOT / 'data/campaign5-intelligence/original-source/source.zip'), 'manifest_sha256': digest(ROOT / 'data/campaign5-intelligence/original-source/manifest.json')}, 'sources': {name: digest(ROOT / name) for name in sorted(source_paths)}, 'receipts': receipts, 'errata': [{'receipt': 'controlled-before', 'scope': 'prospective implementation controls only', 'reason': 'Two initial result assertions wrongly demanded rejection for an old heartbeat and newly saturated queue. A genuine expired-health probe may renew the lease; new-dispatch queue/load cannot invalidate an already returned result. Original v1 bytes and failures are preserved under prospective-v1.'}, {'receipt': 'cycle2-relevant', 'scope': 'collection failure, zero tests', 'reason': 'Command included nonexistent test_compute_integration.py. The subsequent explicit cycle2-relevant-b is the actual 356-test run.'}, {'receipt': 'cycle1-focused-b', 'scope': 'three still-original client identity failures', 'reason': 'Client was loaded before its authorized repair; later separate and integrated suites verify the repaired path.'}], 'owner_state': 'No owner configuration/database/default-model/process changes; intentional Campaign4 changes preserved.', 'live_comparisons': 'Parent-owned discovery/development/final reporting; none claimed from these controls.'}
    dest = ROOT / 'docs/campaign5/INTELLIGENCE_EVIDENCE.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'path': dest.relative_to(ROOT).as_posix(), 'sha256': digest(dest), 'receipts': len(receipts)}))
if __name__ == '__main__':
    main()
