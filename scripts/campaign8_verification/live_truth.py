"""Bounded read-only owner identity projection; no inference, refresh or store view."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from desktop.main import request_json

def main():
    import argparse
    import psutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.out.resolve()
    if not out.is_relative_to(root / 'data/campaign8-verifier') or out.exists():
        raise ValueError('Use a fresh verifier-owned evidence directory')
    out.mkdir(parents=True)
    results = {'timestamp': datetime.now(timezone.utc).isoformat(), 'evidence_class': 'LIVE_READ_ONLY', 'scope': 'Five original loopback GETs; whitelisted metadata only; no owner store view, refresh, POST, generation or capture', 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'observations': {}, 'errors': [], 'actual_generation_calls': 0, 'owner_mutations': 0}
    before = {}
    for pid in (38832, 46084):
        try:
            p = psutil.Process(pid)
            before[str(pid)] = {'create_time': p.create_time(), 'parent': p.ppid(), 'command_sha256': hashlib.sha256(json.dumps(p.cmdline(), ensure_ascii=False).encode()).hexdigest()}
        except psutil.Error as e:
            before[str(pid)] = {'error_type': type(e).__name__}
    operations = [('http://127.0.0.1:8080', '/health'), ('http://127.0.0.1:8080', '/props'), ('http://127.0.0.1:8080', '/v1/models'), ('http://127.0.0.1:8765', '/api/state'), ('http://127.0.0.1:8765', '/api/workspace')]
    for url, path in operations:
        try:
            value = request_json(url, path, timeout=3)
            if path == '/health':
                summary = {'status': value.get('status')}
            elif path == '/props':
                settings = value.get('default_generation_settings', {})
                summary = {'model_alias': value.get('model_alias'), 'model_file': Path(value.get('model_path', '')).name, 'total_slots': value.get('total_slots'), 'modalities': value.get('modalities'), 'context': settings.get('n_ctx'), 'context_evidence': 'declared_metadata_only'}
            elif path == '/v1/models':
                summary = {'ids': [m.get('id') for m in value.get('data', [])], 'reported_context': [m.get('meta', {}).get('n_ctx') for m in value.get('data', [])]}
            elif path == '/api/state':
                summary = {'sampled_at': value.get('sampled_at'), 'model_status': value.get('model_status'), 'error_present': bool(value.get('error')), 'model': value.get('model'), 'resources': value.get('resources'), 'safe_mode': value.get('safe_mode')}
            else:
                summary = {'version': value.get('version'), 'transport': value.get('transport'), 'screens': value.get('screens'), 'features': value.get('features')}
            results['observations'][path] = summary
        except Exception as e:
            results['errors'].append({'path': path, 'error_type': type(e).__name__})
    after = {}
    for pid in (38832, 46084):
        try:
            p = psutil.Process(pid)
            after[str(pid)] = {'create_time': p.create_time(), 'parent': p.ppid(), 'command_sha256': hashlib.sha256(json.dumps(p.cmdline(), ensure_ascii=False).encode()).hexdigest()}
        except psutil.Error as e:
            after[str(pid)] = {'error_type': type(e).__name__}
    results['process_identity_before'] = before
    results['process_identity_after'] = after
    results['process_identity_unchanged'] = before == after
    memory = psutil.virtual_memory()
    results['actual_ram'] = {'available_bytes': memory.available, 'used_percent': memory.percent}
    path = out / 'RESULTS.json'
    path.write_text(json.dumps(results, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'path': path.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'observed_paths': list(results['observations']), 'errors': results['errors'], 'identities_unchanged': results['process_identity_unchanged']}))
if __name__ == '__main__':
    main()
