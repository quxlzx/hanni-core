"""One fresh complex goal through the actual original local planner and API.

No supplied plan or replaced model response. Approve only this campaign's reads
and managed report writes. Preserve unsupported/invalid plans as real failures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from desktop.main import request_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--identity', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('Keep raw model and workflow evidence in private data.')
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / 'synthetic-benchmark.json'
    fixture.write_text('{"passed":9,"total":10}', encoding='utf8')
    goal = (f'Read the synthetic benchmark JSON at {fixture}. Use available verified models '
            'for three independent analyses of the pass percentage. Compare the results and '
            'write a factual report in the managed workflow artifact directory. Cite the source, '
            'verify the calculation, and preserve the input file. Do not run code or use external services.')
    record = {'goal': goal, 'goal_sha256': hashlib.sha256(goal.encode()).hexdigest(),
              'planner_fixture': False, 'events': [], 'verified_completion': False}
    identity = json.loads(args.identity.read_text(encoding='utf8'))
    origin = identity['origin']
    token = request_json(origin, '/api/chat')['token']
    artifacts = Path(identity['data_dir']) / 'workflows/artifacts'

    def mutate(op, data):
        return request_json(origin, '/api/workflows', token=token, timeout=15,
            body={'id': str(uuid.uuid4()), 'operation': op, 'data': data})

    def safe(detail):
        for step in detail.get('steps', []):
            kind, cap, arguments = step.get('kind'), step.get('capability_id'), step.get('arguments') or {}
            if kind == 'analysis':
                continue
            path = arguments.get('path')
            if not isinstance(path, str):
                return False
            resolved = Path(path).resolve()
            if cap in {'file.read', 'file.stat', 'file.head', 'file.tail'} and resolved == fixture:
                continue
            if kind == 'artifact' and cap == 'file.write' and resolved.is_relative_to(artifacts.resolve()):
                continue
            return False
        return bool(detail.get('steps'))

    began = time.monotonic()
    try:
        reply = mutate('goal.submit', {'goal': goal, 'mode': 'assisted'})
        key = record['workflow_id'] = reply['workflow_id']
        record['events'].append({'operation': 'goal.submit', 'response': reply})
        revision = None
        while time.monotonic() - began < 240:
            detail = request_json(origin, f'/api/workflows/{key}', token=token)['workflow']
            if detail['revision'] != revision:
                record['events'].append({'detail': detail})
                revision = detail['revision']
            state = detail['status']
            if state in {'completed', 'partially_completed', 'blocked', 'cancelled', 'failed', 'paused'}:
                record.update(final_status=state, final_detail=detail,
                    verified_completion=state == 'completed' and detail.get('verification_status') == 'verified')
                break
            if state == 'awaiting_plan_approval':
                if not safe(detail):
                    mutate('cancel', {'workflow_id': key, 'expected_revision': revision})
                    record.update(final_status='BLOCKED_UNSAFE_PROPOSAL', final_detail=detail)
                    break
                mutate('approve_plan', {'workflow_id': key, 'expected_revision': revision, 'plan_hash': detail['plan_hash']})
            elif state == 'ready':
                mutate('start', {'workflow_id': key, 'expected_revision': revision, 'plan_hash': detail['plan_hash']})
            elif state == 'awaiting_step_approval':
                approval = next(a for a in detail['approvals'] if a['state'] == 'pending' and a.get('kind') == 'step')
                data = {k: approval[k] for k in ('step_id', 'approval_id', 'plan_hash', 'argument_hash', 'definition_hash')}
                mutate('approve_step', dict(data, workflow_id=key, expected_revision=revision))
            time.sleep(.1)
        else:
            mutate('cancel', {'workflow_id': key, 'expected_revision': revision})
            record.update(final_status='FAIL_TIMEOUT', final_detail=detail)
    except Exception as exc:
        record.update(final_status='FAIL', error={'class': type(exc).__name__, 'message': str(exc)})
    finally:
        record['elapsed_seconds'] = time.monotonic() - began
        (output / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf8')
        print(json.dumps({k: record[k] for k in ('final_status', 'verified_completion', 'elapsed_seconds')}))


if __name__ == '__main__':
    main()
