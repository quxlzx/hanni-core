"""Four frozen M0 interface checks; no model, SSH, provider or power calls.

Model launch/health/resource and cluster probe/tailnet seams are injected into
the original classes. These are boundary checks, not model understanding,
authorization tests, live node measurements or verified user objectives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from hanni.config.loader import load_config
    from hanni.models.manager import ModelManager
    from hanni.models.client import ModelUnavailableError
    from hanni.dashboard.cluster import ClusterMonitor, NODES

    rows = []
    with tempfile.TemporaryDirectory(prefix='hanni-v3-m0-boundary-') as temporary:
        config = load_config(ROOT / 'config', data_dir=Path(temporary), env={})
        forbidden = []

        def no_launch(spec):
            forbidden.append('launch')
            raise AssertionError('Boundary review must never launch a model')

        def no_stop(process):
            forbidden.append('stop')
            raise AssertionError('No owned model process exists in this fixture')

        started = time.perf_counter()
        resource_calls = []

        def low_resources():
            resource_calls.append(True)
            return SimpleNamespace(ram_total_gb=1, ram_used_gb=1,
                                   ram_percent=100, gpus=[])

        manager = ModelManager(config, launch=no_launch, stop=no_stop,
                               health=lambda spec: False, resources=low_resources)
        denied = []
        for _ in range(2):
            try:
                manager.ensure_loaded(config.models.supervisor.id)
            except ModelUnavailableError:
                denied.append(True)
        snapshot = manager.snapshot()[config.models.supervisor.id]
        manager.close()
        rows.append({'id': 'model-resource-admission-and-cooldown',
                     'passed': len(denied) == 2 and len(resource_calls) == 1
                     and snapshot['state'] == 'UNHEALTHY' and not snapshot['owned']
                     and not snapshot['resident'] and not forbidden,
                     'evidence': {'denials': len(denied), 'resource_checks': len(resource_calls),
                                  'state': snapshot['state'], 'owned': snapshot['owned']},
                     'latency_ms': (time.perf_counter() - started) * 1000})

        started = time.perf_counter()
        manager = ModelManager(config, launch=no_launch, stop=no_stop,
                               health=lambda spec: True, resources=low_resources)
        with manager.lease(config.models.supervisor.id):
            busy = manager.snapshot()[config.models.supervisor.id]
        released = manager.snapshot()[config.models.supervisor.id]
        manager.close()
        rows.append({'id': 'model-external-endpoint-not-adopted-or-stopped',
                     'passed': busy['state'] == 'BUSY' and busy['active_inferences'] == 1
                     and not busy['owned'] and released['active_inferences'] == 0
                     and not forbidden,
                     'evidence': {'busy_state': busy['state'], 'active_inferences': busy['active_inferences'],
                                  'owned': busy['owned'], 'released_active': released['active_inferences']},
                     'latency_ms': (time.perf_counter() - started) * 1000})

        started = time.perf_counter()
        probes = []

        def healthy_probe(node, peer):
            probes.append(node.id)
            return {'status': 'online', 'checked_at': 123.0, 'sampled_at': 123.0,
                    'metrics': {'cpu_percent': 25.0, 'ram_percent': 50.0},
                    'address': node.tailscale_ip, 'connection': 'fixture',
                    'uptime_seconds': 600, 'processes': [], 'message': 'Injected sample'}

        monitor = ClusterMonitor(probe=healthy_probe,
                                 tailnet=lambda: {'state': 'fixture', 'peers': {}})
        monitor.sample_once()
        snapshot = monitor.snapshot()
        repair = [row for row in snapshot['nodes'] if row['maintenance']]
        active = [row for row in snapshot['nodes'] if not row['maintenance']]
        snapshot['nodes'][0]['history'].clear()
        copy_safe = bool(monitor.snapshot()['nodes'][0]['history'])
        monitor.close()
        rows.append({'id': 'cluster-maintenance-unprobed-and-snapshot-isolated',
                     'passed': len(probes) == 8 and len(set(probes)) == 8
                     and len(repair) == 1 and repair[0]['status'] == 'repair'
                     and repair[0]['metrics'] is None and repair[0]['id'] not in probes
                     and len(active) == 8 and all(row['status'] == 'online' for row in active)
                     and copy_safe,
                     'evidence': {'probed_count': len(probes), 'maintenance_count': len(repair),
                                  'maintenance_status': repair[0]['status'], 'snapshot_copy': copy_safe},
                     'latency_ms': (time.perf_counter() - started) * 1000})

        started = time.perf_counter()

        def failing_probe(node, peer):
            raise ValueError('Injected transport failure')

        monitor = ClusterMonitor(probe=failing_probe,
                                 tailnet=lambda: {'state': 'unavailable', 'peers': {}})
        monitor.sample_once()
        snapshot = monitor.snapshot()
        active = [row for row in snapshot['nodes'] if not row['maintenance']]
        monitor.close()
        rows.append({'id': 'cluster-probe-failure-has-no-fabricated-measurements',
                     'passed': len(active) == 8 and all(row['status'] == 'unreachable'
                         and row['metrics'] is None and row['sampled_at'] is None
                         and row['history'][-1]['cpu'] is None
                         and row['history'][-1]['ram'] is None for row in active),
                     'evidence': {'unavailable_nodes': len(active), 'fabricated_samples':
                                  sum(row['metrics'] is not None for row in active)},
                     'latency_ms': (time.perf_counter() - started) * 1000})

    report = {'passed': all(row['passed'] for row in rows), 'count': len(rows),
              'results': rows, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'disclosure': __doc__, 'stage_limits': {'intent': 'NOT MEASURED',
              'retrieval': 'NOT APPLICABLE', 'selection': 'NOT APPLICABLE',
              'arguments': 'Direct interface calls', 'authorization': 'NOT MEASURED',
              'execution': 'Original classes, injected transport/runtime boundaries',
              'verification': 'Independent fixture assertions', 'final_response': 'NOT MEASURED'}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'count': len(rows)}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
