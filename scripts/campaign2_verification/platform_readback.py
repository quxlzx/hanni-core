"""Independent baseline/current original-handler replay over controlled OS leaves.

Baseline code comes from exact git bytes, never a hand-written simulated handler.
No-op setters must not be reported successful. Empty observations stay unknown.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from unittest.mock import patch
from hanni.config.loader import load_config
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolRegistry, ToolRequest
from hanni.tools.registry import build_default_registry
from scripts.campaign2.platform_cases import case
NOOPS = ('spotify.focus', 'spotify.volume', 'audio.mute', 'audio.set_volume', 'display.brightness', 'power.set_plan', 'power.set_idle', 'ui.window_state', 'ui.minimize_all')
EMPTY = ('security.defender', 'security.firewall', 'security.pending_reboot', 'device.disk_health')
BATTERY = ('system.battery', 'power.battery_detail')
MODULES = ('devices', 'media', 'power', 'security', 'spotify', 'system', 'uiextra')

def run(root, output, revision=None):
    root = root.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cfg = load_config(root / 'config', data_dir=output / 'state', env={})
    current = build_default_registry(cfg)
    rows = []
    sources = {}
    with ExitStack() as stack:
        if revision:
            modules = {}
            for short in MODULES:
                relative = f'src/hanni/tools/{short}.py'
                raw = subprocess.check_output(['git', 'show', revision + ':' + relative], cwd=root)
                saved = output / 'original-bytes' / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(raw)
                sources[relative] = hashlib.sha256(raw).hexdigest()
                name = 'hanni.tools.' + short
                module = ModuleType(name)
                module.__file__ = str(saved)
                module.__package__ = 'hanni.tools'
                exec(compile(raw, str(saved), 'exec'), module.__dict__)
                modules[name] = module
            stack.enter_context(patch.dict(sys.modules, modules))
            registry = ToolRegistry(current.context)
            for module in modules.values():
                for definition in module.definitions():
                    registry.register(definition)
        else:
            registry = current
            sources = {f'src/hanni/tools/{short}.py': hashlib.sha256((root / f'src/hanni/tools/{short}.py').read_bytes()).hexdigest() for short in MODULES}
        try:
            for name in (*NOOPS, *EMPTY, *BATTERY):
                definition = registry.get(name)
                original = definition.handler
                scenario = case(definition, output / 'fixtures' / name)
                with ExitStack() as dependencies:
                    dependencies.enter_context(scenario.deps(scenario.args, controlled=True, noop=name in NOOPS, unavailable=name in BATTERY))
                    if name in EMPTY:
                        module = importlib.import_module(definition.handler.__module__)
                        dependencies.enter_context(patch.object(module, 'run_powershell_json', return_value=[]))
                    result = registry.execute(ToolRequest(name, dict(scenario.args), confirmed=True, source='campaign2-independent-original-readback'))
                    leaf = {key: getattr(scenario.state, key) for key in ('calls', 'active_plan', 'screen_minutes', 'sleep_minutes', 'brightness', 'foreground')}
                    if name in NOOPS:
                        passed = result.ok is False
                        reason = 'Unchanged controlled OS/SDK state must not report successful application.'
                    elif name in EMPTY:
                        passed = result.ok is False and result.data.get('available') is False
                        reason = 'Empty controlled source must produce unavailable/unknown, not healthy or disabled certainty.'
                    else:
                        passed = result.ok is False and result.data.get('percent') is None
                        reason = 'Absent controlled battery must not fabricate a numeric reading.'
                    rows.append({'id': name, 'trigger': 'noop' if name in NOOPS else 'empty_provider' if name in EMPTY else 'absent_sensor', 'result': result.to_dict(), 'leaf_observation': leaf, 'original_handler_identity_retained': registry.get(name).handler is original, 'passed': passed, 'criterion': reason})
        finally:
            close_service(output / 'state')
    report = {'scope': 'Original version-specific handlers + original registry gates, controlled OS/SDK/provider leaves only; no real desktop/power/provider mutation.', 'source_revision': revision or 'current_worktree', 'source_hashes': sources, 'cases': len(rows), 'passed': sum((row['passed'] for row in rows)), 'failed': sum((not row['passed'] for row in rows)), 'rows': rows}
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path.cwd())
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--revision')
    args = p.parse_args()
    r = run(args.root, args.output, args.revision)
    print(json.dumps({k: v for k, v in r.items() if k != 'rows'}))
    raise SystemExit(0 if r['passed'] == r['cases'] else 1)
if __name__ == '__main__':
    main()
