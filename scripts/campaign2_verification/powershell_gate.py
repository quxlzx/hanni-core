"""Original shell authorization with a throwing guard; never execute shell code."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from hanni.config.loader import load_config
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolRequest
from hanni.tools.registry import build_default_registry
COMMANDS = (('literal_restart', 'Restart-Computer'), ('computed_restart', "& ('Restart'+'-Computer')"), ('computed_stop', "& ('Stop'+'-Computer')"), ('ordinary_arbitrary_code', "Write-Output 'owned gate-only observation'"))

class GuardReached(RuntimeError):
    pass

def run(root, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reg = build_default_registry(load_config(root / 'config', data_dir=output / 'state', env={}))
    definition = reg.get('powershell.run')
    rows = []
    try:
        for label, command in COMMANDS:
            for confirmed in (False, True):
                entered = []
                guard = []
                prior = sys.getprofile()

                def profile(frame, event, arg):
                    if event == 'call' and frame.f_code is definition.handler.__code__:
                        entered.append(True)

                def prevent_execution():
                    guard.append(True)
                    raise GuardReached('Independent pre-handler marker; shell handler cannot execute.')
                sys.setprofile(profile)
                try:
                    try:
                        reg.execute(ToolRequest('powershell.run', {'command': command}, confirmed=confirmed, source='campaign2-independent-gate-only', execution_guard=prevent_execution))
                    except Exception as exc:
                        error = type(exc).__name__
                    else:
                        error = None
                finally:
                    sys.setprofile(prior)
                passed = not entered and (confirmed and error == 'GuardReached' and guard or (not confirmed and error == 'ConfirmationRequired' and (not guard)))
                rows.append({'label': label, 'command': command, 'confirmed': confirmed, 'error': error, 'prehandler_guard_reached': bool(guard), 'original_handler_entered': bool(entered), 'passed': bool(passed)})
    finally:
        close_service(output / 'state')
    report = {'scope': 'Original registry schema/actor/confirmation checks, with mandatory throwing execution_guard before shell handler; no shell process or physical effect.', 'source_sha256': hashlib.sha256((root / 'src/hanni/tools/powershell.py').read_bytes()).hexdigest(), 'permission_level': definition.permission_level, 'risk_level': definition.risk_level, 'cases': len(rows), 'passed': sum((row['passed'] for row in rows)), 'rows': rows}
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path.cwd())
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    r = run(args.root.resolve(), args.output)
    print(json.dumps({k: v for k, v in r.items() if k != 'rows'}))
    raise SystemExit(0 if r['passed'] == r['cases'] else 1)
if __name__ == '__main__':
    main()
