"""Bounded verifier-owned default-model helper, never launches HANNI Core."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from hanni.config.loader import load_config
from hanni.models.manager import ModelManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=1800)
    args = parser.parse_args()
    output, weights = args.output.resolve(), args.weights.resolve()
    if not output.is_relative_to((ROOT/'data/v41-verification').resolve()) or output.exists():
        raise SystemExit('New protected verifier output required.')
    if not 60 <= args.seconds <= 3600:
        raise SystemExit('Bounded 60-3600 second session required.')
    config = load_config(ROOT/'config', data_dir=output/'state', env={})
    if not weights.is_file() or weights.name != config.models.supervisor.model_file:
        raise SystemExit('Exact existing configured primary weights required.')
    output.mkdir(parents=True)
    digest = hashlib.sha256()
    with weights.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    manager = ModelManager(config, model_files={config.models.supervisor.id: str(weights)}, startup_timeout=180)
    process = None
    evidence = {'weights_sha256': digest.hexdigest(), 'weight_bytes': weights.stat().st_size,
                'no_download': True, 'started_at': time.time(), 'maximum_runtime_seconds': args.seconds}
    try:
        entry = manager.ensure_loaded(config.models.supervisor.id)
        process = entry.process
        if process is None:
            raise RuntimeError('External process preserved; this helper requires owned runtime.')
        evidence.update(owned_pid=process.pid, state='ready')
        (output/'ownership.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        print(json.dumps({'state': 'ready', 'owned_pid': process.pid}), flush=True)
        deadline = time.monotonic()+args.seconds
        while time.monotonic() < deadline and not (output/'stop').exists() and process.poll() is None:
            time.sleep(1)
    finally:
        manager.close()
        evidence.update(closed_at=time.time(), owned_process_closed=process is None or process.poll() is not None)
        (output/'closed.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        print(json.dumps({'state': 'closed', 'owned_process_closed': evidence['owned_process_closed']}), flush=True)


if __name__ == '__main__':
    main()
