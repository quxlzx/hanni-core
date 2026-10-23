"""Fresh protected inventory through original transports; no start/stop or tunnels.

Unknown remote resources remain unknown. Public stdout contains only selected
non-secret metadata; private artifacts stay below ignored data/v43-verification.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from hanni.config.loader import load_config
from hanni.models.resource_manager import snapshot_resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/v43-verification').resolve())
    assert not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / 'config', data_dir=output.parent / 'inventory-state', env={})
    spec = config.models.supervisor
    registry = ComputeRegistry(ROOT / 'data')
    transport = InferenceTransport(registry)
    rows = []
    try:
        for worker in registry.workers():
            began = time.perf_counter()
            health = transport.health(worker)
            startup = worker.get('startup', {})
            row = {
                'endpoint_id': 'worker:' + worker['worker_id'],
                'configured_model': worker.get('model_id'),
                'actual_health_status': health.get('status'),
                'reported_model': health.get('model_id'),
                'reported_context': health.get('context_reported'),
                'configured_context': startup.get('context'),
                'configured_backend': startup.get('kind'),
                'configured_gpu': startup.get('gpu_device'),
                'configured_cache_k': startup.get('cache_type_k'),
                'configured_cache_v': startup.get('cache_type_v'),
                'configured_concurrency': worker.get('concurrency', 1),
                'current_verified_context': None,
                'resources': None,
                'check_duration_ms': (time.perf_counter() - began) * 1000,
            }
            if health.get('status') == 'healthy':
                sampled = transport.resources(worker)
                row['resources'] = {key: sampled.get(key) for key in (
                    'ram_total_bytes', 'ram_available_bytes', 'vram_total_bytes',
                    'vram_free_bytes', 'gpus', 'resource_sampled_at')}
            rows.append(row)
            print(json.dumps({key: row[key] for key in (
                'endpoint_id', 'actual_health_status', 'reported_model', 'check_duration_ms')}), flush=True)
        report = {
            'sampled_at': time.time(), 'local_host': asdict(snapshot_resources()),
            'local_configuration': {
                'model_id': spec.id, 'model_file': spec.model_file,
                'quantization': spec.quantization, 'context': spec.context_length,
                'parallel': spec.parallel, 'kv_key_type': spec.kv_key_type,
                'kv_value_type': spec.kv_value_type,
            },
            'workers': rows, 'remote_start_attempts': 0,
            'original_strata_not_stopped': True,
            'remote_cleanup': 'Unknown; no process was stopped by this inspection.',
            'scope': 'Original protected ComputeRegistry/InferenceTransport health paths; no raw endpoint bypass.',
        }
        output.write_text(json.dumps(report, indent=2), encoding='utf8')
    finally:
        transport.close()
        registry.close()


if __name__ == '__main__':
    main()
