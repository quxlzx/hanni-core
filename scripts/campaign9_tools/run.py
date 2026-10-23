"""Preserves raw isolated original-security receipts, then grades offline."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from scripts.campaign9_tools.harness import run_case, environment, inventory, invoke, valid_shape

def grade(receipt, oracle):
    response = receipt['response']
    errors = []
    dispatches = sum((e.get('dispatched') is True for e in receipt['leaf_effects']))
    if 'dispatches' in oracle and dispatches != oracle['dispatches']:
        errors.append(f"dispatch count {dispatches}, expected {oracle['dispatches']}")
    for key, path, invert in [('victim_exists', 'victim.txt', False), ('alias_absent', 'ordinary.txt', True), ('archive_absent', 'ordinary.zip', True)]:
        if key in oracle:
            value = path in receipt['files_after']
            value = not value if invert else value
            if value is not oracle[key]:
                errors.append(f'{key}={value}')
    if 'ok' in oracle:
        returned = response.get('returned', response) if isinstance(response, dict) else {}
        value = bool(returned and returned.get('ok'))
        if value is not oracle['ok']:
            errors.append(f"result ok={value}, expected {oracle['ok']}")
    return {'passed': not errors, 'errors': errors, 'dispatches': dispatches}

def run_matrix(out):
    from hanni.tools.base import ToolRequest
    from hanni.core.shutdown import Actor, StopSource
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix='hanni-c9-registry-') as temporary:
        with environment(Path(temporary)) as state:
            manifest = inventory(state)
            (out / 'INVENTORY.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
            definitions = state.registry.definitions()
            for kind in ['denied_profile', 'emergency_stop', 'model_confirmed_argument']:
                if kind == 'emergency_stop':
                    state.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('C9'), reason='Synthetic matrix stop')
                for definition in definitions:
                    args = valid_shape(definition)
                    if kind == 'model_confirmed_argument':
                        args['confirmed'] = True
                    state.entries = []
                    state.leaf_calls = []
                    result = invoke(state.registry, ToolRequest(definition.name, args, actor_profile='denied' if kind == 'denied_profile' else 'owner', source='campaign9.matrix'), state)
                    expected = {'denied_profile': 'ToolPermissionError', 'emergency_stop': 'EmergencyStopActive', 'model_confirmed_argument': 'ToolValidationError'}[kind]
                    actual = (result.get('exception') or {}).get('type')
                    rows.append({'tool': definition.name, 'boundary': kind, 'response': result, 'handler_entries': state.entries, 'leaf_effects': state.leaf_calls, 'passed': actual == expected and (not state.entries) and (not state.leaf_calls)})
                if kind == 'emergency_stop':
                    state.registry.context.emergency_stop.clear(Actor.local('C9'))
    (out / 'RESULTS.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8', newline='\n')
    summary = {'registered': len(manifest), 'cases': len(rows), 'passed': sum((r['passed'] for r in rows)), 'failed': sum((not r['passed'] for r in rows)), 'evidence_class': 'CONTROLLED_ORIGINAL_DENIAL', 'original_handler_entries': sum((len(r['handler_entries']) for r in rows)), 'attempted_unsafe_leaves': sum((len(r['leaf_effects']) for r in rows))}
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
    return summary

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path)
    p.add_argument('--oracles', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--matrix', action='store_true')
    a = p.parse_args()
    if a.matrix:
        print(json.dumps(run_matrix(a.out)))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    cases = json.loads(a.inputs.read_text(encoding='utf-8'))
    oracles = {r['id']: r for r in json.loads(a.oracles.read_text(encoding='utf-8'))}
    results = []
    started = datetime.now(timezone.utc).isoformat()
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='hanni-c9-case-') as temporary:
            receipt = run_case(case, Path(temporary))
        target = a.out / (case['id'] + '.json')
        target.write_text(json.dumps(receipt, indent=2, default=str) + '\n', encoding='utf-8', newline='\n')
        results.append({'id': case['id'], 'raw_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), **grade(receipt, oracles[case['id']])})
    summary = {'cases': len(results), 'passed': sum((r['passed'] for r in results)), 'failed': sum((not r['passed'] for r in results)), 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(), 'results': results, 'helper_sha256': {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in ['harness.py', 'run.py']}, 'input_sha256': hashlib.sha256(a.inputs.read_bytes()).hexdigest(), 'oracle_sha256': hashlib.sha256(a.oracles.read_bytes()).hexdigest()}
    (a.out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'results'}))
if __name__ == '__main__':
    main()
