"""Independent original security readers over explicitly typed controlled data."""
from __future__ import annotations
import argparse
import importlib
import json
from pathlib import Path
from unittest.mock import patch
from hanni.config.loader import load_config
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolRequest
from hanni.tools.registry import build_default_registry
from scripts.campaign2.platform_cases import case
VALUES = (False, True, 0, 1, None, 'false', 'true', [], {}, 0.0, 1.0, 2, -1)

def run(root, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reg = build_default_registry(load_config(root / 'config', data_dir=output / 'state', env={}))
    rows = []
    try:
        for name in ('security.defender', 'security.firewall', 'security.pending_reboot'):
            definition = reg.get(name)
            module = importlib.import_module(definition.handler.__module__)
            scenario = case(definition, output / 'fixtures' / name)
            for value in VALUES:
                known = type(value) is bool or (type(value) is int and value in (0, 1))
                expected = bool(value) if known else None
                payload = {'RealTimeProtectionEnabled': value, 'AMServiceEnabled': value} if name == 'security.defender' else [{'Name': 'Public', 'Enabled': value}] if name == 'security.firewall' else {'cbs': value, 'wu': value, 'rename': value}
                with scenario.deps(scenario.args, controlled=True), patch.object(module, 'run_powershell_json', return_value=payload):
                    result = reg.execute(ToolRequest(name, dict(scenario.args), confirmed=True, source='campaign2-independent-provider-types'))
                field = {'security.defender': 'realtime_protection', 'security.firewall': 'all_enabled', 'security.pending_reboot': 'pending'}[name]
                passed = result.data.get('available') is known and result.ok is known and (result.data.get(field) is expected)
                if name == 'security.defender':
                    passed = passed and result.data.get('service_enabled') is expected
                if name == 'security.firewall':
                    passed = passed and result.data['profiles'][0]['enabled'] is expected
                rows.append({'id': name, 'provider_value': value, 'provider_type': type(value).__name__, 'expected': expected, 'available_expected': known, 'result': result.to_dict(), 'passed': passed, 'original_handler_identity_retained': reg.get(name).handler is definition.handler})
    finally:
        close_service(output / 'state')
    report = {'scope': 'Original registered security handlers, controlled PowerShell JSON leaf, no real firewall/Defender/registry action.', 'cases': len(rows), 'passed': sum((row['passed'] for row in rows)), 'failed': sum((not row['passed'] for row in rows)), 'rows': rows}
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
