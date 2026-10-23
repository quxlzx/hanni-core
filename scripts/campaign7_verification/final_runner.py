"""Exclusive whole once-only final execution and separate after-run grading."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from scripts.campaign7_verification.executor import run_case
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'data/campaign7-verifier/holdout'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8', newline='\n')

def verify_seal():
    seal = json.loads((PRIVATE / 'SEAL.json').read_text(encoding='utf-8'))
    for filename, field in [('inputs.json', 'input_sha256'), ('oracles.json', 'oracle_sha256'), ('protocol.json', 'protocol_sha256')]:
        if sha(PRIVATE / filename) != seal[field]:
            raise ValueError('Private prospective seal changed')
    if sha(PRIVATE.parent / 'author_final.py') != seal['author_sha256']:
        raise ValueError('Private author bytes changed')
    return seal

def verify_source(freeze):
    manifest_path = Path(freeze) / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    changed = [name for name, expected in manifest.items() if sha(ROOT / name) != expected]
    if changed:
        raise ValueError('Frozen source changed: ' + ', '.join(changed))
    return {'files': len(manifest), 'manifest_sha256': sha(manifest_path)}

def execute(freeze, out):
    out = Path(out).resolve()
    if not out.is_relative_to((ROOT / 'data/campaign7-verifier').resolve()):
        raise ValueError('Use verifier-owned output')
    seal, proof = (verify_seal(), verify_source(freeze))
    claim_path = PRIVATE / 'CLAIM.json'
    descriptor = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump({'created_at': datetime.now(timezone.utc).isoformat(), 'output': str(out), 'seal': seal, 'source_proof': proof, 'policy': 'whole once only; no retries'}, handle, indent=2)
    out.mkdir(parents=True, exist_ok=False)
    inputs = json.loads((PRIVATE / 'inputs.json').read_text(encoding='utf-8'))
    if len(inputs) != seal['case_count'] or len({c['id'] for c in inputs}) != len(inputs):
        raise ValueError('Invalid sealed case coverage')
    receipts = []
    start = time.monotonic()
    for index, case in enumerate(inputs):
        verify_source(freeze)
        before = time.monotonic()
        error, observed = (None, None)
        try:
            observed = run_case(case, out / 'isolated' / case['id'])
        except Exception as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)}
        path = out / (case['id'] + '.json')
        save(path, {'id': case['id'], 'domain': case['domain'], 'category': case['category'], 'observed': observed, 'harness_error': error, 'controlled_elapsed_ms': (time.monotonic() - before) * 1000, 'scope': 'original implementation, controlled inputs/leaves; no physical capture or actual model'})
        receipts.append({'id': case['id'], 'path': path.name, 'sha256': sha(path)})
        save(out / 'PROGRESS.json', {'completed': len(receipts), 'planned': len(inputs), 'harness_errors': sum((json.loads((out / r['path']).read_text(encoding='utf8'))['harness_error'] is not None for r in receipts))})
        if (index + 1) % 10 == 0:
            print(json.dumps({'completed': index + 1, 'planned': len(inputs)}), flush=True)
    final_proof = verify_source(freeze)
    closed = {'created_at': datetime.now(timezone.utc).isoformat(), 'case_count': len(inputs), 'receipts': receipts, 'source_before': proof, 'source_after': final_proof, 'seal': seal, 'duration_seconds': time.monotonic() - start, 'actual_asr_calls': 0, 'physical_audio_capture_calls': 0, 'speaker_playbacks': 0, 'actual_vision_inference_calls': 0, 'physical_screen_capture_calls': 0, 'pycache_prefix': os.environ.get('PYTHONPYCACHEPREFIX'), 'scope': 'Independent controlled protocol/state holdout; not acoustic or vision quality'}
    save(out / 'CLOSED.json', closed)
    from scripts.campaign7_verification.scoring import score_run
    graded = score_run(out, PRIVATE / 'oracles.json')
    print(json.dumps(graded['aggregate']), flush=True)
    return closed
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    execute(args.freeze, args.out)
