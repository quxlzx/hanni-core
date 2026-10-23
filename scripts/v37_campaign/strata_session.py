"""Bounded owned session for the existing protected Strata deployment.

Starts no inference, retains the original installation, and closes only its
own nonce-identified server. The remote RAM/deadline guardian remains active
even if this manager exits unexpectedly. Evidence stays under protected data.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, default=ROOT / 'data')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = (ROOT / 'data').resolve()
    state, output = args.state.resolve(), args.output.resolve()
    if not state.is_relative_to(data) or not output.is_relative_to(data):
        raise SystemExit('Use protected data paths for the campaign deployment and evidence.')
    output.mkdir(parents=True, exist_ok=False)
    registry = ComputeRegistry(state)
    transport = InferenceTransport(registry)
    evidence = {'purpose': 'Original workflow three-worker cohort; no context re-verification.',
                'workers': [], 'started_at': time.time()}
    try:
        if not registry.enabled:
            raise RuntimeError('The protected compute deployment is not enabled.')
        worker = registry.worker('wonyoung-strata')
        if worker.get('startup', {}).get('kind') != 'strata':
            raise RuntimeError('The existing protected Strata startup definition is required.')
        # A bounded diagnostic session cannot silently lengthen deployment life.
        worker['startup']['max_runtime_seconds'] = min(worker['startup'].get('max_runtime_seconds', 900), 900)
        record = {'worker_id': worker['worker_id'], 'startup': transport.start(worker)}
        (output / 'ownership.json').write_text(json.dumps(transport.owned, indent=2), encoding='utf8')
        deadline = time.monotonic() + worker['startup']['max_runtime_seconds']
        load_deadline = min(deadline, time.monotonic() + 180)
        while time.monotonic() < load_deadline and not (output / 'stop').exists():
            health = transport.health(worker)
            if health['status'] == 'healthy':
                registry.observe(worker['worker_id'], **health)
                record.update(health=health, local_url=transport.endpoint(worker),
                              max_context_verified=next(row['max_context_verified'] for row in registry.snapshot()['workers']
                                  if row['worker_id'] == worker['worker_id']))
                break
            time.sleep(2)
        else:
            record.update(status='BLOCKED', reason='Existing Strata did not become ready within its bounded load budget.')
        evidence['workers'].append(record)
        (output / 'endpoints.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        print(json.dumps({'worker_id': worker['worker_id'], 'status': record.get('status', 'healthy'),
                          'owned': record['startup']['owned']}), flush=True)
        while (time.monotonic() < deadline and not (output / 'stop').exists()
               and record.get('health', {}).get('status') == 'healthy'):
            time.sleep(1)
    except Exception as exc:
        evidence.update(status='BLOCKED', reason=str(exc))
        (output / 'endpoints.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        raise
    finally:
        transport.close()
        registry.close()
        (output / 'closed.json').write_text(json.dumps({'owned_shutdown_requested': True,
            'closed_at': time.time()}), encoding='utf8')


if __name__ == '__main__':
    main()
