"""Nonce-checked stop/readback for this verifier's recorded owned GPU PIDs only."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    session, output = args.session.resolve(), args.output.resolve()
    protected = (ROOT/'data/v41-verification').resolve()
    assert session.is_relative_to(protected) and output.is_relative_to(protected) and not output.exists()
    ownership = json.loads((session/'ownership.json').read_text())
    registry = ComputeRegistry(ROOT/'data')
    transport = InferenceTransport(registry)
    rows = []
    try:
        for key, record in ownership.items():
            worker = registry.worker(key)
            node = registry.node(worker['node_id'])
            assert key in {'athena-p40', 'athena-p6000'} and record['node']['id'] == node['id']
            assert type(record['pid']) is int and record['pid'] > 1 and re.fullmatch('[0-9a-f]{32}', record['nonce'])
            program = """import json,os,pathlib,signal,time
p=PARAMETERS
file=pathlib.Path('/proc/'+str(p['pid'])+'/environ')
if not file.exists(): print(json.dumps({'owned_process_exists':False,'stop_requested':False}))
else:
 env=file.read_bytes().split(b'\\0')
 if ('HANNI_COMPUTE_OWNER='+p['nonce']).encode() not in env: print(json.dumps({'ownership_matches':False,'stop_requested':False}))
 else:
  os.kill(p['pid'],signal.SIGTERM)
  deadline=time.monotonic()+3
  while file.exists() and time.monotonic()<deadline: time.sleep(.1)
  print(json.dumps({'ownership_matches':True,'stop_requested':True,'owned_process_exists':file.exists()}))
""".replace('PARAMETERS', repr({'pid': record['pid'], 'nonce': record['nonce']}))
            row = {'worker_id': key, 'owned_pid': record['pid'], 'closed_verified': False}
            try:
                address = transport._address(node)
                response = subprocess.run(transport._ssh(node, address)+['python3 -'], input=program.encode(),
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if response.returncode: row.update(state='unknown', error_class='AuthorizedSSHCommandFailed')
                else:
                    receipt = json.loads(response.stdout)
                    row.update(receipt=receipt, closed_verified=receipt.get('owned_process_exists') is False,
                               state='closed' if receipt.get('owned_process_exists') is False else 'unknown')
            except Exception as error: row.update(state='unknown', error_class=type(error).__name__)
            rows.append(row)
    finally:
        transport.close(); registry.close()
    report = {'owned_only': True, 'no_unrelated_process_targeted': True, 'workers': rows,
        'scope': 'A failed authenticated stop is unknown, never a successful cleanup. Private ownership receipts are retained for reconciliation.'}
    output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
