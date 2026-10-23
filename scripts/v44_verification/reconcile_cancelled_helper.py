"""Close receipt-matching transient SSH CLI leftovers of an already stopped helper."""
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
    args = parser.parse_args()
    session = args.session.resolve()
    assert session.is_relative_to((ROOT / 'data/v44-verification').resolve())
    ready = json.loads((session / 'ready.json').read_text(encoding='utf8'))
    owner = json.loads((session / 'ownership.json').read_text(encoding='utf8'))
    assert ready['session_nonce'] == owner['session_nonce'] and not owner['inference_owned']
    assert not psutil.pid_exists(ready['helper_pid'])
    receipts = json.loads((session / 'pre-cancellation-children.json').read_text(encoding='utf8'))
    closed_cli = []
    for row in receipts:
        try:
            process = psutil.Process(row['pid'])
        except psutil.NoSuchProcess:
            continue
        assert process.create_time() == row['create_time']
        command = process.cmdline()
        assert process.name().lower() in {'ssh.exe', 'tailscale.exe'}
        assert hashlib.sha256(json.dumps(command).encode()).hexdigest() == row['command_sha256']
        assert process.name().lower() == 'ssh.exe' or 'ssh' in command
        process.terminate()
        process.wait(10)
        closed_cli.append(row['pid'])
    external = psutil.Process(owner['inference_pid'])
    parent = psutil.Process(owner['external_parent_pid'])
    assert external.create_time() == owner['inference_create_time']
    assert parent.create_time() == owner['external_parent_create_time']
    assert hashlib.sha256(json.dumps(external.cmdline()).encode()).hexdigest() == owner['command_sha256']
    with socket.socket() as sock:
        sock.settimeout(1)
        connection_result = sock.connect_ex(('127.0.0.1', urlsplit(ready['url']).port))
    listeners = [c.pid for c in psutil.net_connections(kind='tcp')
                 if c.status == psutil.CONN_LISTEN and c.laddr.port == urlsplit(ready['url']).port]
    closed_port = connection_result != 0 and not listeners
    assert closed_port
    closed = {'closed_at': time.time(), 'owned_helper_closed': True, 'owned_http_server_closed': True,
              'owned_process_closed': True, 'external_original_preserved': True, 'closed_verified': True,
              'transient_cli_closed_pids': closed_cli, 'remaining_transient_children': [],
              'connection_result': connection_result, 'remaining_http_listeners': listeners,
              'campaign_cancelled': True, 'graceful_campaign_cancellation': False,
              'scope': 'Exact receipt-owned validation helper and its exact SSH CLI process leftovers only; original external model and HANNI launcher untouched.'}
    (session / 'closed.json').write_text(json.dumps(closed, indent=2), encoding='utf8')
    final = session / 'final-results.json'
    result = json.loads(final.read_text(encoding='utf8'))
    result.update(complete=False, status='cancelled', finished_at=time.time(),
        cancellation={'reason': 'Original refresh integration expired local health during failed-remote checks; no original final retries.',
                      'owned_helper_terminated': True, 'remaining_arms': 16-len(result['results']), 'remaining_status': 'NOT TESTED'})
    final.write_text(json.dumps(result, indent=2, default=str), encoding='utf8')
    print(json.dumps({'closed_verified': True, 'external_original_preserved': True,
                      'retained_arms': len(result['results']), 'transient_cli_closed': len(closed_cli)}), flush=True)


if __name__ == '__main__':
    main()
