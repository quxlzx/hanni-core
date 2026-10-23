"""Diagnostic session using protected preauthorized GPU definitions.

The local helper has a finite deadline. Remote expiry is best effort: original
startup and guardian installation use separate authenticated SSH requests. An
authentication loss between them can leave an owned server awaiting recorded
nonce-checked reconciliation; this helper does not guarantee remote cleanup.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=1800)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'data/v41-verification').resolve()) or output.exists() or not 60 <= args.seconds <= 1800:
        raise SystemExit('New protected evidence and bounded GPU session required.')
    output.mkdir(parents=True)
    registry = ComputeRegistry(ROOT/'data')
    transport = InferenceTransport(registry)
    evidence = {'workers': [], 'started_at': time.time(), 'local_deadline_seconds': args.seconds,
                'remote_expiry_guardian_atomic': False,
                'no_download': True, 'unrelated_servers_preserved': True}
    deadline = time.monotonic()+args.seconds
    try:
        for key in ['athena-p40', 'athena-p6000']:
            worker = registry.worker(key)
            record = {'worker_id': key, 'startup': transport.start(worker)}
            evidence['workers'].append(record)
            # Persist nonce ownership before the second authentication request.
            # If it fails, the exact cleanup target remains recoverable.
            (output/'ownership.json').write_text(json.dumps(transport.owned, indent=2), encoding='utf8')
            (output/'endpoints.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
            if record['startup']['owned']:
                owned = transport.owned[key]
                # A helper exit or later authentication loss must not leave an
                # unbounded owned server. Install this guardian while the same
                # authorized startup connection is still available.
                program = """import json,os,pathlib,signal,time
p=PARAMETERS
guardian=os.fork()
if guardian:
 print(json.dumps({'guardian_pid':guardian}),flush=True)
else:
 os.setsid()
 for fd in (0,1,2):
  try: os.close(fd)
  except OSError: pass
 time.sleep(p['seconds'])
 try:
  env=pathlib.Path('/proc/'+str(p['pid'])+'/environ').read_bytes().split(b'\\0')
  if ('HANNI_COMPUTE_OWNER='+p['nonce']).encode() in env: os.kill(p['pid'],signal.SIGTERM)
 except (OSError,ProcessLookupError): pass
 os._exit(0)
""".replace('PARAMETERS', repr({'pid': owned['pid'], 'nonce': owned['nonce'],
                              'seconds': max(1, int(deadline-time.monotonic()))}))
                response = subprocess.run(transport._ssh(owned['node'], transport._address(owned['node']))+['python3 -'],
                    input=program.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if response.returncode != 0:
                    raise RuntimeError('Owned GPU expiry guardian could not be installed.')
                record['expiry_guardian'] = json.loads(response.stdout)
            load_deadline = min(deadline, time.monotonic()+180)
            while time.monotonic() < load_deadline and not (output/'stop').exists():
                health = transport.health(worker)
                if health['status'] == 'healthy':
                    registry.observe(key, **health)
                    record.update(health=health, state='ready')
                    break
                time.sleep(2)
            else:
                record['state'] = 'blocked'
            (output/'ownership.json').write_text(json.dumps(transport.owned, indent=2), encoding='utf8')
            (output/'endpoints.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
            print(json.dumps({'worker_id': key, 'state': record['state'], 'owned': record['startup']['owned']}), flush=True)
            if record['state'] != 'ready':
                break
        while time.monotonic() < deadline and not (output/'stop').exists():
            time.sleep(1)
    finally:
        transport.close(); registry.close()
        evidence.update(closed_at=time.time(), owned_shutdown_requested=True)
        (output/'closed.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        print(json.dumps({'state': 'closed', 'owned_shutdown_requested': True}), flush=True)


if __name__ == '__main__':
    main()
