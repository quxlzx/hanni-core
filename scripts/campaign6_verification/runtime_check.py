"""Read-only owner-process preservation receipt; no model inference/actions."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
import httpx
import psutil
ROOT = Path(__file__).resolve().parents[2]

def run(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign6-verifier').resolve()):
        raise ValueError('Use a fresh verifier evidence path')
    output.mkdir(parents=True)
    baseline_path = ROOT / 'data/campaign6-manager/baseline/LOCAL_RUNTIME.json'
    baseline = json.loads(baseline_path.read_text())
    rows = []
    for expected in baseline['process_identities']:
        try:
            process = psutil.Process(expected['pid'])
            row = {'pid': process.pid, 'create_time': process.create_time(), 'parent_pid': process.ppid(), 'command_sha256': hashlib.sha256(json.dumps(process.cmdline()).encode()).hexdigest()}
            row['identity_matches'] = all((row.get(name) == value for name, value in expected.items()))
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            row = {'pid': expected['pid'], 'identity_matches': False, 'error': type(exc).__name__}
        rows.append(row)
    listeners = sorted(([connection.laddr.port, connection.pid] for connection in psutil.net_connections('tcp') if connection.status == psutil.CONN_LISTEN and connection.laddr.port in {8080, 8765}))
    health, error = (False, None)
    try:
        with httpx.Client(timeout=2, trust_env=False, follow_redirects=False) as client:
            reply = client.get('http://127.0.0.1:8080/health')
            health = reply.status_code == 200 and reply.json().get('status') in {'ok', 'ready', 'healthy'}
    except (httpx.HTTPError, ValueError) as exc:
        error = type(exc).__name__
    current_yaml = hashlib.sha256((ROOT / 'config/models.yaml').read_bytes()).hexdigest()
    receipt = {'captured_at': time.time(), 'process_identities': rows, 'listener_identities': listeners, 'listeners_match': listeners == sorted(baseline['listener_identities']), 'owner_models_yaml_sha256': current_yaml, 'owner_models_yaml_matches': current_yaml == baseline['owner_models_yaml_sha256'], 'resident_health': health, 'health_error_type': error, 'available_ram_bytes': psutil.virtual_memory().available, 'baseline_sha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(), 'generation_requests': 0, 'services_started_stopped': 0, 'scope': 'Process/listener preservation and bounded health only; healthy endpoint is not inference eligibility/GPU/context proof.'}
    (output / 'RESULT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'identity_matches': all((row['identity_matches'] for row in rows)), 'listeners_match': receipt['listeners_match'], 'resident_health': health, 'config_matches': receipt['owner_models_yaml_matches'], 'generation_requests': 0}))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
