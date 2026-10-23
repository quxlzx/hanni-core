"""Observe an owned runtime after stop; never stop an arbitrary PID/listener."""
import argparse
import json
from pathlib import Path
import socket
import time

import psutil

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output-name', default='cleanup-reconciled.json')
    args = parser.parse_args()
    session = args.session.resolve()
    assert session.is_relative_to((ROOT / 'data/v42-verification').resolve())
    owner = json.loads((session / 'ownership.json').read_text(encoding='utf8'))
    pid = owner['owned_pid']
    assert type(pid) is int and pid > 0 and (session / 'stop').is_file()
    output = session / args.output_name
    assert output.resolve().parent == session and output.suffix == '.json'
    assert not output.exists()
    absent = not psutil.pid_exists(pid)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(2)
        result = probe.connect_ex(('127.0.0.1', 8080))
    # A timeout is unknown. Only explicit platform connection refusal proves
    # the original loopback endpoint is no longer accepting requests.
    refused = result in (10061, 111)
    try:
        listeners = [entry.pid for entry in psutil.net_connections(kind='tcp')
                     if entry.status == psutil.CONN_LISTEN and entry.laddr.port == 8080
                     and entry.laddr.ip in ('127.0.0.1', '0.0.0.0', '::', '::1')]
    except (psutil.AccessDenied, OSError):
        listeners = None
    report = {
        'observed_at': time.time(),
        'owned_pid': pid,
        'owned_pid_absent': absent,
        'original_loopback_connection_result': result,
        'original_loopback_connection_refused': refused,
        'original_loopback_listener_pids': listeners,
        'helper_closed_receipt_present': (session / 'closed.json').is_file(),
        'closed_verified': absent and (refused or listeners == []),
        'scope': 'Independent reconciliation after original ModelManager.close. No PID or external listener was killed.',
        'receipt_failure': 'Already-running helper used an earlier cleanup reporter that dereferenced an entry cleared by manager.close; helper exited 1 after the owned server stopped. The script is fixed for future runs.',
    }
    output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report))
    assert report['closed_verified'], 'Cleanup remains unknown; preserve the receipt and report the actual state.'


if __name__ == '__main__':
    main()
