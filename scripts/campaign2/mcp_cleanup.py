"""Supplemental live provenance/readback for only test-owned SDK child cleanup."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import psutil
from scripts.campaign2.mcp_harness import FIXTURE, OwnedHub, eventually

def matches(proof):
    try:
        process = psutil.Process(proof['pid'])
        return process.create_time() == proof['create_time'] and str(FIXTURE) in process.cmdline()
    except psutil.NoSuchProcess:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for transport in ('stdio', 'streamable_http'):
        with OwnedHub(args.out / transport, transport, approved=False) as hub:
            hub.connect()
            pid = int(hub.ledger_path.with_suffix('.pid').read_text(encoding='utf8'))
            process = psutil.Process(pid)
            proof = {'pid': pid, 'create_time': process.create_time(), 'parent_pids': [parent.pid for parent in process.parents()], 'command': process.cmdline(), 'launching_audit_pid': os.getpid()}
            assert os.getpid() in proof['parent_pids']
            assert str(FIXTURE) in proof['command']
            if hub.http_process is not None:
                proof['launcher_pid'] = hub.http_process.pid
                assert pid == hub.http_process.pid or hub.http_process.pid in proof['parent_pids']
            assert not hub.calls()
            discovered = len(hub.snapshot()['tools'])
            hub.manager.remove(hub.server_id)
            if transport == 'stdio':
                eventually(lambda: not matches(proof))
                assert not matches(proof)
                after_manager = False
            else:
                after_manager = matches(proof)
                assert after_manager and hub.http_process.poll() is None
            assert not hub.manager.connections and (not hub.manager.adapters)
            row = {'transport': transport, 'proof_before_removal': proof, 'actual_initialization': hub.initialization, 'discovered_tools': discovered, 'registry_base_count': hub.base_count, 'sdk_tool_calls': len(hub.calls()), 'alive_after_manager_removal': after_manager, 'ownership_rule': 'SDK-owned stdio; harness-owned external HTTP process', 'manager_remaining_connections': len(hub.manager.connections), 'manager_remaining_adapters': len(hub.manager.adapters)}
        eventually(lambda: not matches(proof))
        row['alive_after_harness_cleanup'] = matches(proof)
        rows.append(row)
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Actual owned SDK process provenance; owner services/configuration not accessed or mutated', 'rows': rows, 'all_cleanup_checks_passed': all((not row['alive_after_harness_cleanup'] for row in rows))}
    (args.out / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({'transports_checked': len(rows), 'all_cleanup_checks_passed': report['all_cleanup_checks_passed']}))
if __name__ == '__main__':
    main()
