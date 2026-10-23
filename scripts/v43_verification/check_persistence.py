"""Reopen genuine completed campaign state through a new original HTTP server.

No inference, model startup, benchmark dispatch, synthetic scores or cleanup of
external processes occurs. This proves private persisted results survive owner
shutdown and are readable/exportable from a distinct current-source service.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.config.loader import load_config
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.server import DashboardServer
from hanni.evals.model_lab import digest
from hanni.reliability.execution import close_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--native', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    session, output = args.session.resolve(), args.output.resolve()
    private = (ROOT / 'data/v43-verification').resolve()
    assert session.is_relative_to(private) and output.is_relative_to(private) and not output.exists()
    closed = json.loads((session / 'closed.json').read_text(encoding='utf8'))
    assert closed['closed_verified'] and closed['external_original_preserved']
    campaign = json.loads((args.campaign / 'results.json').read_text(encoding='utf8'))
    run_ids = [r['id'] for r in campaign['runs']]
    for folder in args.native:
        reviewed = json.loads((folder / 'results.json').read_text(encoding='utf8'))
        assert reviewed['passed'] and reviewed['native_app_reviewed']
        run_ids.append(reviewed['native_ui_run_id'])
    assert len(set(run_ids)) == 7
    output.mkdir(parents=True)
    config = load_config(ROOT / 'config', data_dir=session / 'state', env={})
    hub = ChatHub()
    stop = threading.Event()
    cluster = SimpleNamespace(start=lambda: None, close=lambda: None,
                              snapshot=lambda: {'nodes': [], 'available': False, 'sampled_at': None})
    server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {'safe_mode': False}), hub,
                             shutdown_event=stop, cluster=cluster,
                             cluster_power=SimpleNamespace(start=lambda: None, close=lambda: None, project=lambda v: v),
                             cluster_terminal=SimpleNamespace(project=lambda v: v))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path, token=None):
        headers = {'X-Hanni-Token': token} if token else {}
        with opener.open(urllib.request.Request(url + path, headers=headers), timeout=10) as response:
            assert response.status == 200
            return json.load(response)
    report = {'genuine_persisted_state': True, 'real_model_dispatches': 0, 'runs': [], 'passed': False}
    try:
        token = get('/api/chat?before=1')['token']
        snapshot = get('/api/model-lab', token)
        assert snapshot['total_runs'] == 7 and snapshot['active_run_id'] is None
        for run_id in run_ids:
            evidence = get('/api/model-lab/export/' + run_id, token)
            run, cases = evidence['run'], evidence['results']
            assert run['status'] == 'completed' and len(cases) == run['completed'] == run['total']
            assert [c['ordinal'] for c in cases] == list(range(len(cases)))
            for case in cases:
                unhashed = deepcopy(case)
                checksum = unhashed.pop('evidence_sha256')
                assert digest(unhashed) == checksum
            report['runs'].append({'id': run_id, 'completed': len(cases), 'status': run['status']})
        assert sum(r['completed'] for r in report['runs']) == 33
        report.update(passed=True, reopened_total_cases=33, checked_at=time.time())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        close_service(config.paths.data_dir)
        hub.close()
        hub.db.close()
        report['owned_reopened_http_closed'] = server.socket.fileno() == -1
        (output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
