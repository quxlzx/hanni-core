"""Exercise every discovered dynamic confirmation callback with no handler entry.

Original validators, callback, profile and registered handler remain unchanged.
The dangerous inputs are only presented to the unconfirmed original gate.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from hanni.config.loader import load_config
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolRequest, ConfirmationRequired
from hanni.tools.registry import build_default_registry

def sample(rule):
    if 'default' in rule:
        return rule['default']
    if rule.get('enum'):
        return rule['enum'][0]
    kinds = rule.get('type', 'string')
    kind = next((v for v in kinds if v != 'null'), 'string') if isinstance(kinds, list) else kinds
    if kind == 'object':
        return {name: sample(rule['properties'][name]) for name in rule.get('required', [])}
    if kind == 'array':
        return [sample(rule.get('items', {})) for _ in range(rule.get('minItems', 0))]
    return {'string': 'independent-specimen', 'integer': max(1, int(rule.get('minimum', 1))), 'number': max(1.0, float(rule.get('minimum', 1))), 'boolean': False, 'null': None}[kind]

def audit(root, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    owned = output / 'owned'
    owned.mkdir(exist_ok=True)
    cfg = load_config(root / 'config', data_dir=output / 'state', env={})
    registry = build_default_registry(cfg)
    protected = str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'independent-campaign2-never-created.txt')
    rows = []
    try:
        for definition in registry.definitions():
            if definition.requires_confirmation_if is None:
                continue
            args = sample(definition.argument_schema())
            if definition.name.startswith('file.'):
                args.update(path=protected) if 'path' in definition.input_schema else args.update(source=str(owned / 'never-read.txt'), destination=protected)
            elif definition.name.startswith('archive.'):
                args.update(destination=str(owned))
            elif definition.name == 'project.format':
                args.update(root=str(owned), apply=True)
            elif definition.name == 'powershell.run':
                args.update(command='Restart-Computer')
            elif definition.name == 'service.control':
                args.update(name='IndependentCampaign2FixtureService', action='start')
            elif definition.name == 'ui.close_window':
                args.update(title='Independent never-opened fixture window')
            validated = definition.validate_arguments(args)
            reason = definition.requires_confirmation_if(validated)
            entered = []
            original = sys.getprofile()
            code = definition.handler.__code__

            def profile(frame, event, value):
                if event == 'call' and frame.f_code is code:
                    entered.append(True)
            sys.setprofile(profile)
            try:
                try:
                    registry.execute(ToolRequest(definition.name, args, confirmed=False, source='campaign2-independent-dynamic-denial'))
                except ConfirmationRequired as exc:
                    error = type(exc).__name__
                else:
                    error = None
            finally:
                sys.setprofile(original)
            rows.append({'id': definition.name, 'callback_triggered': bool(reason), 'error': error, 'original_handler_entered': bool(entered), 'original_handler_identity_retained': registry.get(definition.name).handler is definition.handler, 'passed': bool(reason) and error == 'ConfirmationRequired' and (not entered)})
    finally:
        close_service(output / 'state')
    result = {'scope': 'Fresh dynamically enumerated original confirmation callbacks; unconfirmed requests only, no handler replacement or physical/provider operation.', 'callback_count': len(rows), 'passed': sum((row['passed'] for row in rows)), 'original_handler_entries': sum((row['original_handler_entered'] for row in rows)), 'rows': rows}
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path.cwd())
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.root.resolve(), args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    raise SystemExit(0 if result['callback_count'] and result['passed'] == result['callback_count'] else 1)
if __name__ == '__main__':
    main()
