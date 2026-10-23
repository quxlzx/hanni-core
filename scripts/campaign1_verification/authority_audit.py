"""Independent exhaustive original-contract and authority audit without effects."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.tools.base import ToolRequest, ToolResult, ToolPermissionError, ToolValidationError
from hanni.core.shutdown import StopSource, EmergencyStopActive
from hanni.core.identity import Actor
from hanni.mcp.host import McpHost

def argument_example(schema):
    result = {}
    for key in schema.get('required', []):
        rule = schema['properties'][key]
        kind = rule.get('type', 'string')
        if isinstance(kind, list):
            kind = next((x for x in kind if x != 'null'), 'string')
        result[key] = rule.get('default', rule.get('enum', [None])[0] if rule.get('enum') else {'string': 'fixture', 'integer': int(rule.get('minimum', 1)), 'number': float(rule.get('minimum', 1)), 'boolean': False, 'array': [], 'object': {}, 'null': None}[kind])
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    assert out.is_relative_to((ROOT / 'data/campaign1-verifier').resolve()) and (not out.exists())
    out.mkdir(parents=True)
    cfg = load_config(ROOT / 'config', data_dir=out / 'state', env={})
    reg = build_default_registry(cfg, data_dir=out / 'state')
    originals = reg.definitions()
    called = []

    def controlled(args, context, request):
        called.append(request.name)
        return ToolResult(request.name, True, 'Controlled audit handler only; no physical action.', {})
    for d in originals:
        assert reg.unregister(d.name, expected=d)
        reg.register(replace(d, handler=controlled))
    host = McpHost(reg, read_only=cfg.hanni.mcp.read_only, allowed_actions=cfg.hanni.mcp.allowed_actions, max_tools=8)
    rows = []
    for d in reg.definitions():
        args = argument_example(d.argument_schema())
        d.validate_arguments(args)
        row = {'tool': d.name, 'input_schema': d.argument_schema(), 'output_schema': dict(d.output_schema), 'permission_level': d.permission_level, 'risk_level': d.risk_level, 'side_effect': d.side_effect, 'dynamic_confirmation_retained': d.requires_confirmation_if is not None, 'owner_menu_allowed': host._allowed(d)}
        try:
            d.validate_arguments({'__unknown_argument__': True})
        except ToolValidationError:
            row['unknown_arguments_rejected'] = True
        else:
            row['unknown_arguments_rejected'] = False
        for actor in ('everyone_else', 'nonexistent_profile'):
            count = len(called)
            try:
                reg.execute(ToolRequest(d.name, args, actor_profile=actor, confirmed=True, source='campaign1-authority-fixture'))
            except ToolPermissionError:
                row[actor + '_denied'] = len(called) == count
            else:
                row[actor + '_denied'] = False
        count = len(called)
        try:
            reg.execute(ToolRequest(d.name, args, expected_definition_hash='0' * 64, source='campaign1-authority-fixture'))
        except ToolPermissionError:
            row['stale_authority_denied'] = len(called) == count
        else:
            row['stale_authority_denied'] = False
        count = len(called)
        reg.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('campaign1-audit'))
        try:
            reg.execute(ToolRequest(d.name, args, confirmed=True, source='campaign1-authority-fixture'))
        except EmergencyStopActive:
            row['emergency_stop_denied'] = len(called) == count
        else:
            row['emergency_stop_denied'] = False
        finally:
            reg.context.emergency_stop.clear(Actor.local('campaign1-private-fixture'))
        if not host._allowed(d):
            count = len(called)
            try:
                host.prepare_call(host._as_tool(d), args)
            except ToolPermissionError:
                row['denied_host_preparation'] = len(called) == count
            else:
                row['denied_host_preparation'] = False
        if d.permission_level > cfg.permissions.profiles['owner'].max_auto_approve_level or d.risk_level >= 3:
            count = len(called)
            try:
                reg.execute(ToolRequest(d.name, args, source='campaign1-authority-fixture'))
            except ToolPermissionError:
                row['confirmation_required'] = len(called) == count
            else:
                row['confirmation_required'] = False
        flags = [v for k, v in row.items() if k.endswith(('_denied', '_rejected')) or k in {'denied_host_preparation', 'confirmation_required'}]
        row['passed'] = all(flags)
        rows.append(row)
    result = {'scope': 'all base contracts; original validators/registry authorization/stale-definition/stop/host preparation; controlled handlers only', 'contracts': len(rows), 'passed': sum((r['passed'] for r in rows)), 'handler_dispatch_count': len(called), 'original_foreign_handler_dispatches': 0, 'results': rows}
    (out / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    from hanni.reliability.execution import close_service
    close_service(out / 'state')
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}))
if __name__ == '__main__':
    main()
