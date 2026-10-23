"""Receipt-verified cancellation of an owned V4.4 helper only.

This explicit force path is used only for a helper lacking a running campaign
cancellation boundary. External model/launcher identities are independently
checked and preserved; no arbitrary descendants or foreign services are stopped.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit

import psutil

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    session = args.session.resolve()
    assert session.is_relative_to((ROOT / 'data/v44-verification').resolve())
    ready = json.loads((session / 'ready.json').read_text(encoding='utf8'))
    owner = json.loads((session / 'ownership.json').read_text(encoding='utf8'))
    assert ready['session_nonce'] == owner['session_nonce']
    assert not owner['inference_owned']
    helper = psutil.Process(ready['helper_pid'])
    assert helper.create_time() == ready['helper_create_time'] == owner['helper_create_time']
    command = helper.cmdline()
    assert any(Path(part).name == 'lab_session.py' for part in command)
    assert command.count('--output') == 1
    configured_output = Path(command[command.index('--output')+1])
    if not configured_output.is_absolute():
        configured_output = Path(helper.cwd()) / configured_output
    assert configured_output.resolve() == session
    external = psutil.Process(owner['inference_pid'])
    parent = psutil.Process(owner['external_parent_pid'])
    assert external.create_time() == owner['inference_create_time']
    assert parent.create_time() == owner['external_parent_create_time']
    assert hashlib.sha256(json.dumps(external.cmdline()).encode()).hexdigest() == owner['command_sha256']
    final = session / 'final-results.json'
    snapshot = json.loads(final.read_text(encoding='utf8')) if final.exists() else None
    assert snapshot is None or all(row['response'] is None and not row['telemetry'] for row in snapshot['results'])
    transient = [{'pid': p.pid, 'create_time': p.create_time(), 'name': p.name(),
                  'command_sha256': hashlib.sha256(json.dumps(p.cmdline()).encode()).hexdigest()}
                 for p in helper.children(recursive=False)]
    (session / 'pre-cancellation-children.json').write_text(json.dumps(transient, indent=2), encoding='utf8')
    helper.terminate()
    helper.wait(15)
    port = urlsplit(ready['url']).port
    with socket.socket() as sock:
        sock.settimeout(1)
        closed_port = sock.connect_ex(('127.0.0.1', port)) in (10061, 111)
    external_preserved = external.is_running() and external.create_time() == owner['inference_create_time']
    parent_preserved = parent.is_running() and parent.create_time() == owner['external_parent_create_time']
    deadline = time.monotonic() + 20
    pending = []
    while time.monotonic() < deadline:
        pending = []
        for row in transient:
            try:
                child = psutil.Process(row['pid'])
                if child.is_running() and child.create_time() == row['create_time']:
                    pending.append(row)
            except psutil.NoSuchProcess:
                pass
        if not pending:
            break
        time.sleep(.2)
    closed = {'closed_at': time.time(), 'owned_helper_closed': not psutil.pid_exists(helper.pid),
        'owned_http_server_closed': closed_port, 'owned_process_closed': True,
        'external_original_preserved': external_preserved and parent_preserved,
        'closed_verified': closed_port and external_preserved and parent_preserved and not pending,
        'transient_child_receipts': transient, 'remaining_transient_children': pending,
        'campaign_cancelled': True, 'graceful_campaign_cancellation': False,
        'scope': 'Only exact PID/create-time/nonce receipt validation helper terminated; original external model and original HANNI launcher preserved.',
        'reason': args.reason}
    assert closed['closed_verified']
    (session / 'closed.json').write_text(json.dumps(closed, indent=2), encoding='utf8')
    if snapshot is not None:
        snapshot.update(complete=False, status='cancelled', finished_at=time.time(),
            cancellation={'reason': args.reason, 'owned_helper_terminated': True,
                          'remaining_arms': 16-len(snapshot['results']), 'remaining_status': 'NOT TESTED'})
        final.write_text(json.dumps(snapshot, indent=2, default=str), encoding='utf8')
    print(json.dumps({'closed_verified': True, 'external_original_preserved': True,
                      'retained_arms': len(snapshot['results']) if snapshot else 0}), flush=True)


if __name__ == '__main__':
    main()
