"""Read-only identity evidence for the existing externally owned model server."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import psutil
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.models.client import LlamaCppClient
from scripts.campaign1_verification.run import identity

def snapshot(output: Path):
    spec = load_config(ROOT / 'config', env={}).models.supervisor
    evidence = identity(spec)
    command = psutil.Process(evidence['pid']).cmdline()
    keys = [key for key in ('-m', '--model') if key in command]
    if keys:
        model = Path(command[command.index(keys[0]) + 1])
    else:
        mapped = {Path(item.path) for item in psutil.Process(evidence['pid']).memory_maps() if item.path.lower().endswith('.gguf')}
        assert len(mapped) == 1, 'Expected one mapped GGUF; no identity guess allowed.'
        model = mapped.pop()
    assert model.name == spec.model_file
    digest = hashlib.sha256()
    with model.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    health = LlamaCppClient(spec).health()
    evidence.update(model_file=model.name, model_bytes=model.stat().st_size, model_sha256=digest.hexdigest(), original_client_health_ok=health.ok, observed_utc=datetime.now(timezone.utc).isoformat(), scope='Read-only external identity; no model manager or launch', config_generation_defaults={'temperature': spec.temperature, 'top_p': spec.top_p, 'max_tokens': spec.max_tokens})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return evidence
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(snapshot(args.output)))
