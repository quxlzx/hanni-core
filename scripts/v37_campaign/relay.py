"""Bounded secure inference forward; never starts or stops a remote model."""
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
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    state = args.state.resolve()
    if not state.is_relative_to((ROOT / 'data').resolve()):
        raise SystemExit('Use a protected local campaign deployment.')
    registry = ComputeRegistry(state)
    transport = InferenceTransport(registry)
    output = state.parent / 'relay.json'
    try:
        worker = registry.worker(args.worker)
        health = transport.health(worker)
        if health['status'] != 'healthy':
            raise RuntimeError(health['error'])
        record = {'worker_id': args.worker, 'local_url': transport.endpoint(worker), 'health': health,
                  'owned_remote_server': False}
        output.write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(json.dumps(record), flush=True)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline and not (state.parent / 'relay-stop').exists():
            time.sleep(1)
    finally:
        transport.close()
        registry.close()


if __name__ == '__main__':
    main()
