"""Bounded manager-owned GPU session; inference evidence is collected separately.

Uses only protected existing paths. Stop via its local stop file; a fifteen-minute
deadline independently prevents unattended owned inference from persisting.
"""
import json
import argparse
import shutil
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute.registry import ComputeRegistry
from hanni.compute.transport import InferenceTransport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--context', type=int, choices=(8192, 16384, 32768, 65536, 131072), default=8192)
    parser.add_argument('--output', type=Path, help='New protected campaign directory; existing evidence is preserved.')
    args = parser.parse_args()
    output = (args.output or ROOT / ('data/v37-manager/gpu-session' if args.context == 8192 else f'data/v37-manager/gpu-session-{args.context}')).resolve()
    if not output.is_relative_to((ROOT / 'data/v37-manager').resolve()) or output.exists():
        raise SystemExit('Choose a new protected --output directory under data/v37-manager; prior evidence is preserved.')
    output.mkdir(parents=True, exist_ok=False)
    state = output / 'state'
    protected = state / 'compute'
    protected.mkdir(parents=True, exist_ok=True)
    deployment = json.loads((ROOT / 'data/compute/deployment.json').read_text(encoding='utf-8'))
    for worker in deployment['workers']:
        if worker['worker_id'].startswith('athena-'):
            worker['context_configured'] = args.context
            worker['startup']['context'] = args.context
    (protected / 'deployment.json').write_text(json.dumps(deployment), encoding='utf-8')
    shutil.copyfile(ROOT / 'data/compute/context-measurements.json', protected / 'context-measurements.json')
    registry = ComputeRegistry(state)
    transport = InferenceTransport(registry)
    deadline = time.monotonic() + 900
    workers = [worker for worker in registry.workers() if worker['worker_id'].startswith('athena-')]
    evidence = {'model_quantization': 'Q4_K_S', 'requested_IQ3_S': 'NOT_FOUND', 'workers': []}
    try:
        for worker in workers:
            record = {'worker_id': worker['worker_id']}
            try:
                record['startup'] = transport.start(worker)
                began = time.monotonic()
                while time.monotonic()-began < 120:
                    health = transport.health(worker)
                    if health['status'] == 'healthy':
                        record.update(health=health, local_url=transport.endpoint(worker))
                        break
                    time.sleep(2)
                else:
                    record.update(status='BLOCKED', reason='Existing backend did not become ready within the bounded load budget.')
            except Exception as exc:
                record.update(status='BLOCKED', reason=str(exc))
            evidence['workers'].append(record)
            (output / 'endpoints.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            (output / 'ownership.json').write_text(json.dumps(transport.owned, indent=2), encoding='utf-8')
            print(json.dumps(record), flush=True)
            if record.get('status') == 'BLOCKED':
                break
        while time.monotonic() < deadline and not (output / 'stop').exists() and any(row.get('health') for row in evidence['workers']):
            time.sleep(1)
    finally:
        transport.close()
        registry.close()
        (output / 'closed.json').write_text(json.dumps({'owned_shutdown_requested': True, 'time': time.time()}), encoding='utf-8')
        print('Owned GPU session closed.', flush=True)


if __name__ == '__main__':
    main()
