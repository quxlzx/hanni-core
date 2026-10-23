"""Bounded read-only cluster discovery through existing strict connection code."""
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
import zipfile
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.dashboard.cluster import load_nodes, tailscale_snapshot, _run, _ssh_prefix, _tailscale_executable
from hanni.compute.transport import RESOURCE_SAMPLE

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf-8')

def classify(stderr):
    value = stderr.casefold()
    if 'additional check' in value or 'reauth' in value or 'check period' in value:
        return 'TAILSCALE_FRESH_AUTH_REQUIRED'
    if 'host key verification' in value or 'host identification has changed' in value:
        return 'HOST_VERIFICATION_FAILED'
    if 'permission denied' in value or 'authentication' in value:
        return 'AUTHENTICATION_FAILED'
    if 'timed out' in value or 'timeout' in value:
        return 'CONNECTION_TIMEOUT'
    if 'refused' in value:
        return 'CONNECTION_REFUSED'
    return 'SSH_OPERATION_FAILED'

def node_probe(node, tail, timeout):
    row = {'node_id': node.id, 'maintenance': node.maintenance, 'captured_at': time.time(), 'attempts': [], 'hardware': None, 'authenticated_ssh': False, 'host_verification': 'NOT_COMPLETED'}
    peer = tail['peers'].get(node.tailscale_ip, {})
    row['tailscale_peer'] = peer
    if node.maintenance:
        return {**row, 'status': 'MAINTENANCE_SKIPPED'}
    if not node.username:
        return {**row, 'status': 'ACCOUNT_NOT_CONFIGURED'}
    for connection, address in [('lan', node.lan_ip), ('tailscale', node.tailscale_ip)]:
        if not address:
            continue
        attempt = {'connection': connection, 'tcp_connected': False, 'authenticated_ssh': False, 'host_verification': 'NOT_COMPLETED'}
        began = time.monotonic()
        try:
            with socket.create_connection((address, 22), timeout=0.6):
                attempt['tcp_connected'] = True
        except OSError as exc:
            attempt.update(status='TCP_UNREACHABLE', exception_type=type(exc).__name__)
            attempt['elapsed_ms'] = (time.monotonic() - began) * 1000
            row['attempts'].append(attempt)
            continue
        wrapper = _tailscale_executable() if connection == 'tailscale' and peer.get('ssh_enabled') else None
        prefix = _ssh_prefix(node, address, tailscale=wrapper)
        attempt['trust_path'] = 'TAILSCALE_COORDINATOR_AND_STRICT_SSH' if wrapper else 'EXISTING_OPENSSH_STRICT_HOST_KEYS'
        try:
            result = _run(prefix + ['true'], timeout=timeout)
            attempt['exit_code'] = result.returncode
            if result.returncode:
                attempt.update(status=classify(result.stderr), stderr_sha256=hashlib.sha256(result.stderr.encode()).hexdigest())
            else:
                attempt.update(status='AUTHENTICATED_HOST_VERIFIED', authenticated_ssh=True, host_verification='ORIGINAL_STRICT_CONNECTION_SUCCEEDED')
                row.update(authenticated_ssh=True, host_verification=attempt['host_verification'], connection=connection)
                hardware = _run(prefix + ['python3 -'], input=RESOURCE_SAMPLE, timeout=timeout)
                if hardware.returncode == 0 and len(hardware.stdout.encode()) <= 65536:
                    data = json.loads(hardware.stdout)
                    if not isinstance(data, dict):
                        raise ValueError('Invalid bounded hardware output')
                    row['hardware'] = data
                    row['hardware_sampled_at'] = time.time()
                    row['status'] = 'HARDWARE_MEASURED'
                else:
                    row['status'] = 'AUTHENTICATED_HARDWARE_UNAVAILABLE'
                    attempt['hardware_error'] = classify(hardware.stderr)
                attempt['elapsed_ms'] = (time.monotonic() - began) * 1000
                row['attempts'].append(attempt)
                return row
        except subprocess.TimeoutExpired as exc:
            stderr = exc.stderr or b''
            if isinstance(stderr, bytes):
                stderr = stderr.decode('utf-8', 'replace')
            attempt.update(status=classify(stderr) if stderr else 'OWNED_SSH_TIMEOUT', stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest())
        except (OSError, ValueError) as exc:
            attempt.update(status='PROBE_ERROR', exception_type=type(exc).__name__)
        attempt['elapsed_ms'] = (time.monotonic() - began) * 1000
        row['attempts'].append(attempt)
    row['status'] = 'SSH_UNAVAILABLE'
    return row

def run(output, *, workers=2, timeout=12, endpoints=True):
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign6-manager').resolve()):
        raise ValueError('Choose a fresh Campaign 6 discovery directory')
    if type(workers) is not int or not 1 <= workers <= 2 or (not 1 <= timeout <= 12):
        raise ValueError('Read-only probe budget exceeded')
    output.mkdir(parents=True)
    paths = sorted([*(ROOT / 'src/hanni').rglob('*.py'), *(ROOT / 'config').rglob('*.yaml')])
    before = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    save(output / 'SOURCE_BEFORE.json', before)
    with zipfile.ZipFile(output / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for p in paths:
            content = p.read_bytes()
            if hashlib.sha256(content).hexdigest() != before[p.relative_to(ROOT).as_posix()]:
                raise RuntimeError('Source changed during archive')
            archive.writestr(p.relative_to(ROOT).as_posix(), content)
    config_hashes = {}
    state = output / 'state'
    for name in ['deployment.json', 'context-measurements.json']:
        original = ROOT / 'data/compute' / name
        if original.exists():
            if original.is_symlink() or original.stat().st_size > 1048576:
                raise ValueError('Unsafe protected configuration copy')
            target = state / 'compute' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
            config_hashes[name] = digest(original)
    nodes = load_nodes(state)
    tail = tailscale_snapshot(nodes)
    save(output / 'TAILSCALE.json', tail)
    save(output / 'ROSTER.json', [asdict(n) for n in nodes])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(lambda n: node_probe(n, tail, timeout), nodes))
    save(output / 'NODE_PROBES.json', records)
    for record in records:
        print(json.dumps({'node_id': record['node_id'], 'status': record['status'], 'authenticated_ssh': record['authenticated_ssh'], 'attempts': [a['status'] for a in record['attempts']]}), flush=True)
    registry = ComputeRegistry(state)
    compute = ComputeScheduler(registry)
    try:
        registered = [{k: w.get(k) for k in ['worker_id', 'node_id', 'label', 'gpu', 'model_id', 'protocol', 'enabled', 'context_configured', 'model_context_limit', 'concurrency', 'interactive_reserve', 'remote_port', 'capabilities', 'allowed_categories']} for w in registry.workers()]
        save(output / 'REGISTERED_WORKERS.json', registered)
        if endpoints:
            snapshot = compute.refresh()
            save(output / 'NATIVE_SNAPSHOT.json', snapshot)
            save(output / 'NATIVE_OBSERVATIONS.json', registry.observations)
        else:
            snapshot = registry.snapshot()
        summary = {'node_count': len(nodes), 'worker_count': len(registered), 'tailscale_state': tail['state'], 'authenticated_nodes': sum((r['authenticated_ssh'] for r in records)), 'hardware_measured_nodes': sum((r['hardware'] is not None for r in records)), 'healthy_workers': sum((w['status'] == 'healthy' for w in snapshot['workers'])), 'generation_http_requests': 0, 'owner_services_started_or_stopped': 0, 'configured_owner_sha256': config_hashes, 'scope': 'Live bounded read-only TCP/strict SSH/hardware/original endpoint discovery. No model inference.'}
        save(output / 'SUMMARY.json', summary)
        print(json.dumps(summary), flush=True)
    finally:
        compute.close()
        registry.close()
        save(output / 'SOURCE_AFTER.json', {p.relative_to(ROOT).as_posix(): digest(p) for p in paths})
        if json.loads((output / 'SOURCE_AFTER.json').read_text()) != before:
            raise RuntimeError('Source changed during live discovery')
        if any((digest(ROOT / 'data/compute' / name) != value for name, value in config_hashes.items())):
            raise RuntimeError('Protected owner configuration changed')
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--ssh-timeout', type=float, default=12)
    parser.add_argument('--no-endpoints', action='store_true')
    args = parser.parse_args()
    run(args.output, workers=args.workers, timeout=args.ssh_timeout, endpoints=not args.no_endpoints)
