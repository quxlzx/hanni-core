"""Independent bounded read-only confirmation using original strict SSH code.

Only sanitized classifications and hashes are retained. Authentication URLs,
credentials, and raw provider stderr never enter the evidence files.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from hanni.dashboard.cluster import load_nodes, tailscale_snapshot, _ssh_prefix, _run, _tailscale_executable

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def failure_evidence(stderr):
    folded = stderr.casefold()
    flags = {'explicit_fresh_check': any((term in folded for term in ('additional check', 'reauth', 'check period'))), 'host_key_failure': any((term in folded for term in ('host key verification failed', 'host identification has changed'))), 'authentication_denied': 'permission denied' in folded, 'connection_timeout': any((term in folded for term in ('timed out', 'timeout')))}
    reason = next((key for key, present in flags.items() if present), 'unclassified_ssh_failure')
    return {'reason': reason, 'flags': flags, 'stderr_sha256': hashlib.sha256(stderr.encode('utf-8')).hexdigest(), 'raw_stderr_retained': False}

def probe(node, tail):
    row = {'node_id': node.id, 'captured_at': time.time(), 'attempts': [], 'ssh_authenticated': False, 'hardware_measured': False, 'inference_requests': 0}
    peer = tail['peers'].get(node.tailscale_ip, {})
    row['tailscale_projection'] = {key: peer.get(key) for key in ('online', 'ssh_enabled')}
    for kind, address in (('lan', node.lan_ip), ('tailscale', node.tailscale_ip)):
        attempt = {'connection': kind, 'tcp_reachable': False, 'ssh_authenticated': False, 'host_verification': 'NOT_COMPLETED'}
        began = time.monotonic()
        try:
            with socket.create_connection((address, 22), timeout=0.6):
                attempt['tcp_reachable'] = True
        except OSError as exc:
            attempt.update(reason='tcp_unreachable', exception_type=type(exc).__name__, elapsed_ms=(time.monotonic() - began) * 1000)
            row['attempts'].append(attempt)
            continue
        native = _tailscale_executable() if kind == 'tailscale' and peer.get('ssh_enabled') else None
        command = _ssh_prefix(node, address, tailscale=native)
        attempt['strict_host_key_option'] = 'StrictHostKeyChecking=yes' in command
        attempt['batch_mode_option'] = 'BatchMode=yes' in command
        attempt['transport'] = 'original_tailscale_ssh' if native else 'original_openssh'
        try:
            result = _run(command + ['true'], timeout=12)
            attempt['exit_code'] = result.returncode
            if result.returncode == 0:
                attempt.update(reason='original_strict_ssh_succeeded', ssh_authenticated=True, host_verification='ORIGINAL_STRICT_CONNECTION_SUCCEEDED')
                row['ssh_authenticated'] = True
            else:
                attempt.update(failure_evidence(result.stderr))
        except subprocess.TimeoutExpired as exc:
            value = exc.stderr or b''
            if isinstance(value, bytes):
                value = value.decode('utf-8', 'replace')
            attempt.update(failure_evidence(value), deadline_expired=True)
        except OSError as exc:
            attempt.update(reason='original_transport_unavailable', exception_type=type(exc).__name__)
        attempt['elapsed_ms'] = (time.monotonic() - began) * 1000
        row['attempts'].append(attempt)
        if row['ssh_authenticated']:
            break
    return row

def run(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign6-verifier').resolve()):
        raise ValueError('Use a new private Campaign 6 evidence directory')
    output.mkdir(parents=True)
    owned_state = output / 'state/compute'
    owned_state.mkdir(parents=True)
    hashes = {}
    for name in ('deployment.json', 'context-measurements.json'):
        owner = ROOT / 'data/compute' / name
        if owner.exists():
            if owner.is_symlink() or owner.stat().st_size > 1048576:
                raise ValueError('Unsafe protected configuration')
            hashes[name] = sha(owner)
            (owned_state / name).write_bytes(owner.read_bytes())
    source_paths = [ROOT / 'src/hanni/dashboard/cluster.py', Path(__file__)]
    sources_before = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths}
    nodes = load_nodes(output / 'state')
    tail = tailscale_snapshot(nodes)
    save(output / 'ROSTER.json', [asdict(node) for node in nodes])
    save(output / 'TAILSCALE.json', tail)
    selected = [node for node in nodes if node.id in {'hanni', 'wonyoung'}]
    if len(selected) != 2:
        raise ValueError('Expected protected Hanni and Wonyoung registrations')
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda node: probe(node, tail), selected))
    sources_after = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths}
    owner_unchanged = all((sha(ROOT / 'data/compute' / name) == value for name, value in hashes.items()))
    save(output / 'RESULTS.json', {'receipts': receipts, 'sources_before': sources_before, 'sources_after': sources_after, 'protected_hashes': hashes, 'owner_configuration_unchanged': owner_unchanged, 'scope': 'Two independent strict original SSH true commands; no hardware, inference, authentication interaction or services.'})
    if sources_after != sources_before or not owner_unchanged:
        raise RuntimeError('Independent confirmation changed its protected source/config boundary')
    print(json.dumps({'output': str(output), 'nodes': [{'node_id': row['node_id'], 'ssh_authenticated': row['ssh_authenticated'], 'reasons': [a['reason'] for a in row['attempts']]} for row in receipts], 'configuration_unchanged': owner_unchanged}))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
