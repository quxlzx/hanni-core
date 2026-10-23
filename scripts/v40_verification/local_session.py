"""Bounded verifier-owned session for installed configured default weights only."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.config.loader import load_config
from hanni.models.manager import ModelManager


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--weights', type=Path, required=True)
    args = p.parse_args()
    output, weights = args.output.resolve(), args.weights.resolve()
    if not output.is_relative_to((ROOT / 'data/v40-verification').resolve()) or output.exists():
        raise SystemExit('New protected verifier output required.')
    config = load_config(ROOT / 'config', data_dir=output / 'state', env={})
    if not weights.is_file() or weights.name != config.models.supervisor.model_file:
        raise SystemExit('Existing exact configured default weights required; no downloads.')
    output.mkdir(parents=True)
    digest = hashlib.sha256()
    with weights.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    manager = ModelManager(config, model_files={config.models.supervisor.id: str(weights)}, startup_timeout=180)
    process = None
    evidence = {'weights_sha256': digest.hexdigest(), 'weight_bytes': weights.stat().st_size,
                'configured_model': config.models.supervisor.model_file,
                'no_download': True, 'started_at': time.time()}
    try:
        entry = manager.ensure_loaded(config.models.supervisor.id)
        process = entry.process
        if process is None:
            raise RuntimeError('Session requires an owned process; existing external process is preserved.')
        evidence.update(owned_pid=process.pid, runtime_command=entry.command, state='ready')
        (output / 'ownership.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        print(json.dumps({'state': 'ready', 'owned_pid': process.pid}), flush=True)
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline and not (output / 'stop').exists() and process.poll() is None:
            time.sleep(1)
    finally:
        manager.close()
        evidence.update(closed_at=time.time(), owned_process_closed=process is None or process.poll() is not None)
        (output / 'closed.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        print(json.dumps({'state': 'closed', 'owned_process_closed': evidence['owned_process_closed']}), flush=True)


if __name__ == '__main__':
    main()
