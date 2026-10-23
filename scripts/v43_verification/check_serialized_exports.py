"""Audit exact serialized transport of every existing genuine campaign run.

Only token-gated read-only original Lab API routes are called. No benchmark,
model dispatch or tool action is initiated.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.evals.model_lab import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    session, output = args.session.resolve(), args.output.resolve()
    private = (ROOT / 'data/v43-verification').resolve()
    assert session.is_relative_to(private) and output.is_relative_to(private) and not output.exists()
    output.mkdir(parents=True)
    ready = json.loads((session / 'ready.json').read_text(encoding='utf8'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token = None
    def get(path):
        headers = {'X-Hanni-Token': token} if token else {}
        with opener.open(urllib.request.Request(ready['url'] + path, headers=headers), timeout=10) as response:
            assert response.status == 200
            return json.load(response)
    token = get('/api/chat?before=1')['token']
    snapshot = get('/api/model-lab')
    assert snapshot['total_runs'] == 7 and snapshot['active_run_id'] is None
    report = {'read_only': True, 'model_dispatches': 0, 'runs': [], 'passed': False,
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [ROOT / 'src/hanni/evals/model_lab.py', ROOT / 'src/hanni/dashboard/server.py',
                              ROOT / 'src/hanni/dashboard/static/app.js', ROOT / 'src/hanni/dashboard/static/style.css']}}
    for run in snapshot['runs']:
        encoded = get('/api/model-lab/export/' + run['id'] + '?representation=serialized')
        assert encoded['export_complete'] and encoded['next_offset'] is None
        manifest = json.loads(encoded['run_json'])
        assert digest(manifest['configuration']) == manifest['configuration_sha256']
        assert digest(manifest['protocol']) == manifest['protocol_sha256']
        cases = [json.loads(raw) for raw in encoded['results_json']]
        assert len(cases) == manifest['completed'] == manifest['total']
        assert [case['ordinal'] for case in cases] == list(range(len(cases)))
        for case in cases:
            body = deepcopy(case)
            checksum = body.pop('evidence_sha256')
            assert digest(body) == checksum
        default = get('/api/model-lab/export/' + run['id'])
        assert default['run'] == manifest and default['results'] == cases
        (output / (run['id'] + '.json')).write_text(json.dumps(encoded, indent=2), encoding='utf8')
        report['runs'].append({'id': run['id'], 'cases': len(cases), 'configuration_hash_verified': True,
                               'protocol_hash_verified': True, 'all_case_hashes_verified': True})
    assert len(report['runs']) == 7 and sum(r['cases'] for r in report['runs']) == 33
    report.update(passed=True, cases=33)
    (output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({'passed': True, 'runs': 7, 'cases': 33, 'model_dispatches': 0}), flush=True)


if __name__ == '__main__':
    main()
