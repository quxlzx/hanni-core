"""Independent real Model Lab API campaign and exported evidence audit.

Only fixed implemented development suites execute. The fixture tool suite uses
actual original scoped file.read; LLM tool evaluations retain synthetic results.
The script rejects unknown ownership, never starts an arbitrary remote model,
and never substitutes fixture scores for real primary-model measurements.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.evals.model_lab import corpus, digest
from hanni.workflows.verification import parse_evidence_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    session, output = args.session.resolve(), args.output.resolve()
    private = (ROOT / 'data/v43-verification').resolve()
    assert session.is_relative_to(private) and output.is_relative_to(private) and not output.exists()
    owner = json.loads((session / 'ownership.json').read_text(encoding='utf8'))
    ready = json.loads((session / 'ready.json').read_text(encoding='utf8'))
    assert ready['session_nonce'] == owner['session_nonce']
    helper = psutil.Process(ready['helper_pid'])
    assert helper.create_time() == ready['helper_create_time']
    owned = psutil.Process(owner['inference_pid'])
    assert owned.create_time() == owner['inference_create_time']
    assert hashlib.sha256(json.dumps(owned.cmdline()).encode()).hexdigest() == owner['command_sha256']
    output.mkdir(parents=True)
    url = ready['url']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token = None
    report = {'real_model_campaign': True, 'started_at': time.time(), 'checks': [],
              'runs': [], 'progress': {}, 'weights_sha256': owner['weights_sha256'],
              'inference_owned': owner['inference_owned'],
              'performance_limitations': owner.get('performance_limitations'),
              'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in [ROOT / 'src/hanni/evals/model_lab.py', ROOT / 'src/hanni/dashboard/model_lab.py',
                               ROOT / 'src/hanni/dashboard/server.py', ROOT / 'src/hanni/dashboard/static/app.js',
                               ROOT / 'src/hanni/dashboard/static/style.css']},
              'disclosure': 'Genuine original local primary requests through Model Lab API. All datasets exposed development; no holdout tuning or adaptive proof publication.'}
    def request(path, payload=None, *, authorized=True):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Origin': url}
        if authorized and token:
            headers['X-Hanni-Token'] = token
        req = urllib.request.Request(url + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        try:
            with opener.open(req, timeout=10) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    def check(name, passed, **evidence):
        report['checks'].append({'name': name, 'passed': bool(passed), **evidence})
        print(json.dumps({'check': name, 'passed': bool(passed)}), flush=True)
        assert passed, name
    def action(name, data):
        status, body = request('/api/model-lab', {'id': str(uuid4()), 'action': name, 'data': data, 'confirmed': True})
        assert status == 200, (name, status, body)
        return body
    def detail(run_id):
        status, body = request('/api/model-lab/run/' + run_id + '?limit=500')
        assert status == 200, (status, body)
        return body
    def wait(run_id, desired=None, timeout=600):
        deadline = time.monotonic() + timeout
        observations = report['progress'].setdefault(run_id, [])
        while time.monotonic() < deadline:
            body = detail(run_id)
            run = body['run']
            observed = {key: run.get(key) for key in ('status', 'completed', 'total', 'current_case')}
            if not observations or observations[-1] != observed:
                assert not observations or observed['completed'] >= observations[-1]['completed']
                observations.append(observed)
            if desired == 'inflight' and run['current_case'] is not None:
                return body
            if desired is not None and run['status'] == desired:
                return body
            if desired is None and run['status'] not in {'running', 'pausing', 'cancelling'}:
                return body
            time.sleep(.05)
        raise RuntimeError('Live benchmark did not reach its documented boundary.')
    def settings(suite, cases, repetitions):
        return {'suite_id': suite, 'endpoint_id': None if suite == 'routing-development' else 'local:supervisor',
                'max_cases': cases, 'repetitions': repetitions, 'max_tokens': 192, 'max_rounds': 3}
    def export(run_id):
        status, body = request('/api/model-lab/export/' + run_id)
        assert status == 200
        (output / (run_id + '.json')).write_text(json.dumps(body, indent=2), encoding='utf8')
        run, rows = body['run'], body['results']
        check('Persisted exported case count agrees with progress ' + run_id[:8],
              len(rows) == run['completed'] and [r['ordinal'] for r in rows] == list(range(run['completed'])))
        for row in rows:
            public = deepcopy(row)
            checksum = public.pop('evidence_sha256')
            assert digest(public) == checksum, 'Public exported evidence digest mismatch.'
            if run['suite_id'] == 'structured-development':
                parsed = parse_evidence_json(row['final_answer'])
                expected = row['expected']
                correct = parsed == expected and all(type(parsed[key]) is type(value) for key, value in expected.items())
                assert row['passed'] == correct and row['score'] == (100 if correct else 0)
                assert row['real_inference'] is True and row['tool_execution'] is False
                assert row['verified_task_success'] is None
            elif run['suite_id'] == 'file-read-development':
                receipts = row.get('original_receipts', [])
                verified = any(r['capability_id'] == 'file.read' and r['result'].get('ok') is True
                               and r['result'].get('verification', {}).get('status') == 'VERIFIED' for r in receipts)
                correct = verified and 'coral-8427' in row.get('final_answer', '')
                assert row['passed'] == correct and row['verified_task_success'] == correct
                assert row['real_inference'] is True and row['tool_execution'] is True
            elif run['suite_id'] == 'llm-tools-development':
                weights = {'tool_selection': .20, 'argument_correctness': .15, 'tool_sequencing': .15,
                           'final_conclusion': .25, 'evidence_grounding': .10, 'no_hallucinated_tools': .05,
                           'no_unsupported_claims': .05, 'correct_stopping': .05}
                score = round(sum(row['component_scores'][key] * weight for key, weight in weights.items()), 2)
                assert score == row['score']
                assert row['tool_execution'] is False and row['verified_task_success'] is None
        if rows:
            rate = 100 * sum(row['passed'] is True for row in rows) / len(rows)
            assert abs(run['summary']['pass_rate_percent'] - rate) < 1e-9
        report['runs'].append({'id': run_id, 'suite_id': run['suite_id'], 'status': run['status'],
                               'completed': run['completed'], 'total': run['total'], 'summary': run['summary'],
                               'export': run_id + '.json'})
        return body
    try:
        token = request('/api/chat?before=1', authorized=False)[1]['token']
        check('All Model Lab reads remain token protected', request('/api/model-lab', authorized=False)[0] == 403)
        status, snapshot = request('/api/model-lab?refresh=1')
        assert status == 200
        (output / 'initial-inventory.json').write_text(json.dumps(snapshot, indent=2), encoding='utf8')
        primary = next(row for row in snapshot['models'] if row['endpoint_id'] == 'local:supervisor')
        check('Original primary is configured installed loaded and currently available',
              all(primary[key] is True for key in ('configured', 'installed', 'loaded', 'available')))
        check('Configured context is retained without invented context proof',
              primary['context_configured'] == 16384 and primary['max_context_verified'] is None)
        status, long_preflight = request('/api/model-lab/preflight?suite_id=structured-development&endpoint_id=local:supervisor&max_cases=2&max_tokens=192')
        (output / 'long-context-preflight.json').write_text(json.dumps(long_preflight, indent=2), encoding='utf8')
        check('Unchanged original long prompt fails admission before model scoring',
              status == 200 and long_preflight.get('eligible') is False
              and any(row['id'] == 'long' for row in long_preflight['unsupported_cases']))
        first = action('start', settings('structured-development', 1, 5))
        wait(first['id'], 'inflight')
        paused = action('pause', {'run_id': first['id']})
        check('Pause declares the in-flight case boundary', paused['status'] == 'pausing')
        checkpoint = wait(first['id'], 'paused')
        check('Real paused checkpoint retains completed cases', 0 < checkpoint['run']['completed'] < 5)
        action('resume', {'run_id': first['id']})
        wait(first['id'])
        first_export = export(first['id'])
        check('Real structured campaign completes', first_export['run']['status'] == 'completed')
        second = action('start', settings('structured-development', 1, 5))
        wait(second['id'], 'inflight')
        action('cancel', {'run_id': second['id']})
        cancelled = wait(second['id'], 'cancelled')
        check('Cancellation leaves original inference helper alive',
              psutil.Process(owner['inference_pid']).create_time() == owner['inference_create_time'])
        check('Cancelled checkpoint preserves a unique durable boundary', 0 < cancelled['run']['completed'] < 5)
        action('resume', {'run_id': second['id']})
        wait(second['id'])
        export(second['id'])
        files = action('start', settings('file-read-development', 1, 5))
        wait(files['id'])
        export(files['id'])
        llm = action('start', settings('llm-tools-development', 2, 1))
        wait(llm['id'])
        export(llm['id'])
        routing = action('start', settings('routing-development', 10, 1))
        wait(routing['id'])
        export(routing['id'])
        status, comparable = request('/api/model-lab/compare?ids=' + first['id'] + ',' + second['id'])
        check('Matching actual workloads compare without automatic ranking',
              status == 200 and comparable['comparable'] and comparable['automatic_ranking'] is False
              and comparable['scales']['pass_rate_percent'] == [0, 100])
        (output / 'comparable.json').write_text(json.dumps(comparable, indent=2), encoding='utf8')
        status, mixed = request('/api/model-lab/compare?ids=' + first['id'] + ',' + files['id'])
        check('Different actual suite conditions remain explicitly noncomparable', status == 200 and not mixed['comparable'])
        status, history = request('/api/model-lab?status=completed')
        check('Actual historical run filtering and persistence', status == 200 and history['history_count'] >= 4)
        check('Result paging remains bounded', request('/api/model-lab/run/' + first['id'] + '?limit=501')[0] == 400)
        report.update(completed_at=time.time(), passed=all(row['passed'] for row in report['checks']))
    except Exception as error:
        report.update(completed_at=time.time(), passed=False, blocker=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        (output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps({'passed': report.get('passed'), 'runs': len(report['runs']), 'blocker': report.get('blocker')}), flush=True)


if __name__ == '__main__':
    main()
