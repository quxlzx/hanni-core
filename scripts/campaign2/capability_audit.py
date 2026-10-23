"""Exhaustive receipts, retaining original handlers and dynamically checking coverage."""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.core.identity import Actor
from hanni.core.shutdown import StopSource
from hanni.mcp.host import McpHost
from hanni.reliability.execution import close_service
from hanni.tools.base import ToolRequest, ToolPermissionError, ToolValidationError
from hanni.tools.registry import build_default_registry
from scripts.campaign2.fixtures import RootFixtures
from scripts.campaign2.inventory import capture, digest
DIMENSIONS = ('valid_arguments', 'invalid_arguments', 'missing_parameter', 'permission_enforcement', 'dependency_unavailable', 'output_contract', 'natural_language_selection', 'end_to_end')
PLATFORM_MODULES = {f'hanni.tools.{name}' for name in ('system', 'windows', 'apps', 'media', 'spotify', 'net', 'power', 'security', 'devices', 'uiextra', 'envtools')}

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, default=str) + '\n', encoding='utf8')

def assertion(check, passed, observed=None, expected=None):
    return {'check': check, 'passed': bool(passed), 'observed': observed, 'expected': expected}

def outcome(status, mode, receipt, checks=(), reason=None):
    row = {'status': status, 'mode': mode, 'assertions': list(checks), 'receipt': receipt, 'receipt_sha256': digest(receipt)}
    if reason:
        row['reason'] = reason
    return row

@contextmanager
def handler_entries(definition):
    code = getattr(definition.handler, '__code__', None)
    entries = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            entries.append(frame.f_code.co_name)
    sys.setprofile(profile)
    try:
        yield entries
    finally:
        sys.setprofile(previous)

def invoke(registry, definition, arguments, **options):
    with handler_entries(definition) as entries:
        try:
            result = registry.execute(ToolRequest(definition.name, arguments, confirmed=True, source='campaign2-isolated-audit', **options))
            receipt = {'result': result.to_dict()}
        except Exception as exc:
            result = None
            receipt = {'error': {'type': type(exc).__name__, 'message': str(exc)}}
    receipt.update(original_handler_entered=bool(entries), handler_entry_count=len(entries), handler_identity_retained=registry.get(definition.name).handler is definition.handler, effective_input=arguments)
    return (result, receipt)

def output_errors(definition, result):
    if result is None:
        return ['No successful result to validate']
    errors = []
    if result.name != definition.name:
        errors.append('Result name does not match capability')
    if type(result.ok) is not bool or not isinstance(result.message, str):
        errors.append('Invalid ToolResult envelope')
    if not isinstance(result.data, dict):
        errors.append('Result data is not an object')
    if not result.ok:
        envelope = result.to_dict()
        if not isinstance(envelope.get('error'), dict) or not envelope['error'].get('code'):
            errors.append('Failure envelope lacks error code')
    types = {'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'object': dict, 'array': (list, tuple), 'null': type(None)}
    for key, label in definition.output_schema.items():
        optional = label.startswith('optional ')
        label = label.removeprefix('optional ')
        if key not in result.data:
            if result.ok and (not optional):
                errors.append('Missing declared output ' + key)
            continue
        value = result.data[key]
        alternatives = label.split('|')
        valid = False
        for kind in alternatives:
            if kind in types:
                if isinstance(value, types[kind]) and (not (isinstance(value, bool) and kind in {'integer', 'number'})):
                    valid = True
            elif value == kind:
                valid = True
        if not valid:
            errors.append(f'{key}: expected {label}, observed {type(value).__name__}')
    return errors

def audit_case(name, tmp, inventory_row):
    cfg = load_config(ROOT / 'config', data_dir=tmp / 'state', env={})
    registry = build_default_registry(cfg)
    definition = registry.get(name)
    if definition.handler.__module__ in PLATFORM_MODULES:
        from scripts.campaign2.platform_cases import case
        spec = case(definition, tmp)
    else:
        fixtures = RootFixtures(tmp, registry)
        spec = fixtures.case(definition)
    dimensions = {}
    try:
        if spec is None:
            return {**inventory_row, 'dimensions': {dimension: outcome('blocked', 'unimplemented_case', {}, reason='No safe implementation case was authored for discovered capability.') for dimension in DIMENSIONS}}
        mode = {'LIVE': 'live_read', 'MOCK': 'original_mock_dependency', 'ISOLATED': 'isolated_original'}.get(spec.mode, spec.mode)
        args = deepcopy(spec.args)
        checked = definition.validate_arguments(args)
        permissions = []
        for actor in ('everyone_else', 'campaign2_unknown_actor'):
            _, receipt = invoke(registry, definition, checked, actor_profile=actor)
            passed = receipt.get('error', {}).get('type') in {'ToolPermissionError', 'ConfirmationRequired'} and (not receipt['original_handler_entered'])
            permissions.append(assertion('actor denied before original handler', passed, receipt, actor))
        _, stale = invoke(registry, definition, checked, expected_definition_hash='0' * 64)
        permissions.append(assertion('stale definition denied before handler', stale.get('error', {}).get('type') == 'ToolPermissionError' and (not stale['original_handler_entered']), stale))
        registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('campaign2'))
        _, stopped = invoke(registry, definition, checked)
        registry.context.emergency_stop.clear(Actor.local('campaign2'))
        permissions.append(assertion('emergency stop denies original handler', stopped.get('error', {}).get('type') == 'EmergencyStopActive' and (not stopped['original_handler_entered']), stopped))
        if definition.risk_level >= 3 or definition.permission_level > cfg.permissions.profiles['owner'].max_auto_approve_level:
            with handler_entries(definition) as entries:
                try:
                    registry.execute(ToolRequest(name, checked, source='campaign2-unconfirmed'))
                except ToolPermissionError as exc:
                    error = type(exc).__name__
                else:
                    error = None
            permissions.append(assertion('unconfirmed high-impact action denied', error == 'ConfirmationRequired' and (not entries), error))
        dimensions['permission_enforcement'] = outcome('pass' if all((a['passed'] for a in permissions)) else 'fail', 'original_gate', {'checks': permissions}, permissions)
        invalid = []
        malformed = [{'__unknown_campaign2_parameter': True}]
        for key, rule in definition.argument_schema().get('properties', {}).items():
            types = rule.get('type', 'string')
            types = types if isinstance(types, list) else [types]
            bad = [] if 'array' not in types else {} if 'object' not in types else 'wrong-type'
            malformed.append({**checked, key: bad})
        for invalid_args in malformed:
            _, receipt = invoke(registry, definition, invalid_args)
            invalid.append(assertion('invalid arguments rejected before handler', receipt.get('error', {}).get('type') == 'ToolValidationError' and (not receipt['original_handler_entered']), receipt))
        dimensions['invalid_arguments'] = outcome('pass' if all((a['passed'] for a in invalid)) else 'fail', 'original_gate', {'checks': invalid}, invalid)
        required = definition.argument_schema().get('required', [])
        important = ('expression', 'value', 'text', 'id', 'name', 'pid', 'path', 'source', 'archive', 'left', 'root', 'duration', 'message', 'title', 'summary', 'when', 'since', 'command', 'options')
        key = next(iter(required), None) or next((k for k in important if k in checked), None)
        if name == 'file.search':
            key = 'query'
        missing = deepcopy(checked)
        if key:
            missing.pop(key, None)
        with spec.deps(missing):
            if key:
                missing.pop(key, None)
            _, receipt = invoke(registry, definition, missing)
        schema_requires = key in required
        rejected = 'error' in receipt or not receipt.get('result', {}).get('ok', False)
        gate_error = receipt.get('error', {}).get('type')
        observed_implementation = receipt['original_handler_entered'] and receipt['handler_identity_retained']
        passed = rejected and gate_error == 'ToolValidationError' if schema_requires else observed_implementation
        missing_checks = [assertion('required omission rejected or optional behavior documented', passed, {'omitted': key, 'schema_required': schema_requires, 'behavior': receipt}, 'rejection' if schema_requires else 'observed optional/default or semantic requirement')]
        dimensions['missing_parameter'] = outcome('pass' if passed else 'fail', mode, receipt, missing_checks)
        with spec.deps(args):
            if definition.handler.__module__ in PLATFORM_MODULES:
                from scripts.campaign2.platform_cases import prompt
                valid_query = prompt(name, args)
            else:
                valid_query = spec.query
            result, receipt = invoke(registry, definition, args)
            errors = output_errors(definition, result)
            try:
                readback = spec.verify(result, args) if result is not None else ['Original handler failed']
            except Exception as exc:
                readback = ['Readback fixture error: ' + type(exc).__name__ + ': ' + str(exc)]
            receipt['readback_errors'] = readback
            if definition.handler.__module__ not in PLATFORM_MODULES:
                receipt['dependency_ledger'] = deepcopy(fixtures.ledger)
                receipt['readback_assertions'] = deepcopy(fixtures.observations)
            else:
                receipt['dependency_ledger'] = deepcopy(getattr(spec.state, 'calls', []))
                receipt['readback_assertions'] = deepcopy(getattr(spec, 'observations', []))
        checks = [assertion('original registered handler entered', receipt['original_handler_entered'], receipt['handler_entry_count'], 1), assertion('original handler identity retained', receipt['handler_identity_retained'], receipt['handler_identity_retained'], True), assertion('valid arguments produce successful original result', result is not None and result.ok, receipt.get('result', receipt.get('error')))]
        dimensions['valid_arguments'] = outcome('pass' if all((a['passed'] for a in checks)) else 'fail', mode, receipt, checks)
        checks = [assertion('actual output matches declared successful contract', result is not None and result.ok and (not errors), errors, [])]
        dimensions['output_contract'] = outcome('pass' if checks[0]['passed'] else 'fail', mode, receipt, checks)
        if readback == ['NO_INDEPENDENT_READBACK']:
            dimensions['end_to_end'] = outcome('blocked', mode, receipt, reason='Only output contract observed; independent readback not authored.')
        else:
            checks = [assertion('independent implementation readback matches', not readback, readback, [])]
            dimensions['end_to_end'] = outcome('pass' if not readback else 'fail', mode, receipt, checks)
        if getattr(spec, 'dependency', 'external dependency') == 'none':
            dimensions['dependency_unavailable'] = outcome('not_applicable', 'pure_in_process', {}, reason='No optional external dependency in this capability implementation.')
        else:
            unavailable_args = deepcopy(checked)
            try:
                with spec.deps(unavailable_args, unavailable=True):
                    unavailable_result, receipt = invoke(registry, definition, unavailable_args)
                    unavailable_errors = spec.verify(unavailable_result, unavailable_args) if unavailable_result is not None and definition.handler.__module__ in PLATFORM_MODULES else None
                    receipt['unavailable_readback_errors'] = unavailable_errors
                absence = unavailable_result is None or not unavailable_result.ok or (name in {'file.stat', 'file.locate', 'google.accounts'} and (not unavailable_result.data.get('exists', True) or not unavailable_result.data.get('matches', [1]) or (not unavailable_result.data.get('accounts', [1]))))
                if unavailable_errors is not None:
                    absence = not unavailable_errors
                entered = receipt['original_handler_entered'] and receipt['handler_identity_retained']
                checks = [assertion('original implementation handles absent dependency', entered, receipt['original_handler_entered'], True), assertion('unavailable dependency yields explicit failure or honest absence', absence, receipt)]
                dimensions['dependency_unavailable'] = outcome('pass' if all((check['passed'] for check in checks)) else 'fail', 'original_mock_dependency', receipt, checks)
            except Exception as exc:
                dimensions['dependency_unavailable'] = outcome('blocked', 'harness_error', {'error': str(exc)}, reason='Dependency fixture itself failed before original implementation could be tested.')
        host = McpHost(registry, read_only=cfg.hanni.mcp.read_only, max_tools=cfg.hanni.mcp.max_tools_per_turn, allowed_actions=cfg.hanni.mcp.allowed_actions)
        decision = host.route(valid_query)
        selected = [t.capability_id for t in decision.tools]
        from scripts.v36_engineering.scenarios import REQUESTS
        aliases = [{'google_calendar.agenda', 'google.calendar.events'}, {'google_calendar.list', 'google.calendar.list_calendars'}, {'google_calendar.next', 'google.calendar.next'}, {'google_calendar.create', 'google.calendar.create'}, {'email.search', 'gmail.search', 'google.gmail.search'}, {'email.read', 'gmail.read', 'google.gmail.read'}, {'google.drive.list', 'google.drive.recent'}]
        equivalents = next((group for group in aliases if name in group), {name})
        eligible = host._allowed(definition)
        passed = bool(equivalents.intersection(selected)) if eligible else not equivalents.intersection(selected)
        receipt = {'query': valid_query, 'selected_menu': selected, 'route_status': decision.status, 'host_eligible': eligible, 'accepted_equivalents': sorted(equivalents), 'menu': [{'id': tool.capability_id, 'wire_name': tool.wire_name, 'fixed_arguments': dict(tool.fixed_arguments)} for tool in decision.tools], 'scope': 'Actual original natural-language retrieval and host-policy test, not model inference.'}
        checks = [assertion('natural-language menu includes equivalent eligible tool or excludes denied tool', passed, selected, sorted(equivalents))]
        dimensions['natural_language_selection'] = outcome('pass' if passed else 'fail', 'retrieval_only', receipt, checks)
        return {**inventory_row, 'query': valid_query, 'valid_input': deepcopy(args), 'dimensions': dimensions}
    finally:
        close_service(tmp / 'state')

def run(output, only=None):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hanni-campaign2-inventory-') as folder:
        cfg = load_config(ROOT / 'config', data_dir=Path(folder), env={})
        registry = build_default_registry(cfg)
        try:
            inventory = capture(registry, cfg)
        finally:
            close_service(Path(folder))
    save(output / 'INVENTORY.json', inventory)
    selected = [r for r in inventory['builtins'] if not only or r['id'] in only]
    rows = []
    for item in selected:
        print('Audit ' + item['id'], flush=True)
        with tempfile.TemporaryDirectory(prefix='hanni-campaign2-case-') as folder:
            try:
                row = audit_case(item['id'], Path(folder), item)
            except Exception as exc:
                row = {**item, 'dimensions': {dim: outcome('blocked', 'harness_error', {'error': {'type': type(exc).__name__, 'message': str(exc)}}, reason='Case setup or harness error.') for dim in DIMENSIONS}}
        save(output / 'receipts' / f"{item['id']}.json", row)
        rows.append(row)
    for tool in inventory['owner_enabled_mcp_tools']:
        name = tool['internal_id']
        if only and name not in only:
            continue
        row = {'id': name, 'definition_hash': tool.get('definition_hash'), 'handler_module': 'hanni.mcp.adapter', 'handler_sha256': hashlib.sha256((ROOT / 'src/hanni/mcp/adapter.py').read_bytes()).hexdigest(), 'source': 'owner_enabled_external_mcp', 'persisted_metadata': tool, 'dimensions': {dim: outcome('blocked', 'persisted_discovery_only', {}, reason='Persisted enabled tool has not been connected or executed by this audit; no live success assumed.') for dim in DIMENSIONS}}
        save(output / 'receipts' / f'{name}.json', row)
        rows.append(row)
    ids = {r['id'] for r in inventory['builtins']} | {t['internal_id'] for t in inventory['owner_enabled_mcp_tools']}
    counts = {dim: dict(Counter((r['dimensions'][dim]['status'] for r in rows))) for dim in DIMENSIONS}
    result = {'baseline': inventory['baseline'], 'inventory_sha256': inventory['inventory_sha256'], 'inventory_count': len(ids), 'tested_count': len(rows), 'discovered_count': len(ids), 'discovered_ids': sorted(ids), 'inventory_coverage_complete': {r['id'] for r in rows} == ids, 'owner_enabled_mcp_tool_count': inventory['owner_enabled_mcp_tool_count'], 'dimension_counts': counts, 'capabilities': rows}
    save(output / 'SCORECARD.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'capabilities'}), flush=True)
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/campaign2')
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    run(args.output, args.only)
