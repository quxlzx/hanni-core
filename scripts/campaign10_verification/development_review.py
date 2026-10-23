"""Independent reproductions using only public Campaign 10 development inputs."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import traceback
from .integrity import digest, snapshot_source
from .contracts import opaque_observation
ROOT = Path(__file__).resolve().parents[2]

def interface_reproductions(output):
    import importlib.util
    import sys
    from scripts.campaign10_core import harness
    source = ROOT / 'data/campaign10-core/interface-before-01/INPUTS.json'
    cases = json.loads(source.read_text(encoding='utf-8'))
    baseline = ROOT / 'data/campaign10-verifier-public/development-memory-before/harness-snapshot.py'
    recorded = json.loads((baseline.parent / 'RECEIPT.json').read_text(encoding='utf-8'))
    assert digest(baseline) == recorded['helper_sha256']
    spec = importlib.util.spec_from_file_location('scripts.campaign10_core.independent_baseline', baseline)
    old = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = old
    spec.loader.exec_module(old)
    old.REPO = ROOT
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in cases:
        if case['id'] == 'interface-memory':
            continue
        observations = {}
        for phase, module in [('before', old), ('after', harness)]:
            receipt = module.run_case(case, output / (case['id'] + '-' + phase))
            path = output / (case['id'] + '-' + phase + '.json')
            path.write_text(json.dumps(receipt, indent=2, default=opaque_observation) + '\n', encoding='utf-8')
            action = receipt['actions']['call' if case['id'] == 'interface-inert-mcp' else 'create']
            observations[phase] = {'receipt_sha256': digest(path), 'error': action['error'], 'handler_entries': action['handler_entries'], 'result': action['result']}
        rows.append({'id': case['id'], 'observations': observations})
    result = {'state': 'INDEPENDENT_INTERFACE_BEFORE_AFTER_REPRODUCED', 'baseline_helper_sha256': digest(baseline), 'current_helper_sha256': digest(ROOT / 'scripts/campaign10_core/harness.py'), 'inputs_sha256': digest(source), 'rows': rows, 'actual_model_posts': 0, 'provider_scope': 'Inert leaf through original MCP adapter; no external provider requests.'}
    (output / 'SUMMARY.json').write_text(json.dumps(result, indent=2, default=opaque_observation) + '\n', encoding='utf-8')
    return {'state': result['state'], 'tasks': len(rows), 'actual_model_posts': 0}

def workflow_reproductions(output, selected=None):
    from scripts.campaign10_systems.runner import run_case
    source = ROOT / 'data/campaign10-systems/prospective-cycle1/inputs.jsonl'
    cases = {row['id']: row for row in map(json.loads, source.read_text(encoding='utf-8').splitlines())}
    selected = selected or ['C10-SYS-020', 'C10-SYS-021', 'C10-SYS-027', 'C10-SYS-035']
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = snapshot_source(ROOT)
    summaries = []
    for ident in selected:
        case = cases[ident]
        receipt = run_case(case, output / (ident + '-before'))
        (output / (ident + '-before.json')).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        summary = {'id': ident, 'before_status': receipt.get('status'), 'before_harness_error': receipt['harness_error']}
        if case['fixtures']['adapter'] == 'workflow':
            corrected = deepcopy(case)
            changes = []

            def repair(value, path=''):
                if isinstance(value, dict):
                    if value.get('operator') in {'present', 'nonempty', 'json_valid', 'evidence_report'} and 'expected' not in value:
                        value['expected'] = None
                        changes.append(path)
                    for key, item in value.items():
                        repair(item, path + '/' + key)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        repair(item, path + '/' + str(index))
            repair(corrected['fixtures'], '/fixtures')
            after = run_case(corrected, output / (ident + '-schema-only-after'))
            (output / (ident + '-schema-only-after.json')).write_text(json.dumps(after, indent=2) + '\n', encoding='utf-8')
            summary.update(schema_only_changes=changes, after_status=after.get('status'), after_verified_steps=after.get('verified_steps'), after_restarts=after.get('restart_count'), after_unauthorized_effects=after.get('unauthorized_effects'), after_duplicate_effects=after.get('duplicate_effects'), after_rejected_controls=after.get('rejected_controls'))
        else:
            summary.update(alias_removal=receipt['observations'][1]['data'], ordinary_name_match=receipt['observations'][2]['data'])
        summaries.append(summary)
    result = {'state': 'INDEPENDENT_PUBLIC_DEVELOPMENT_REPRODUCTIONS', 'input_sha256': digest(source), 'source_before': before['source_sha256'], 'source_after': snapshot_source(ROOT)['source_sha256'], 'rows': summaries, 'actual_model_posts': 0, 'physical_or_provider_operations': 0, 'scope': 'Original isolated services; controlled outline/binding only; no final holdout access.'}
    (output / 'SUMMARY.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result

def memory_seed_reproduction(output):
    from scripts.campaign10_core.harness import run_case
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    case = {'id': 'PUBLIC-INDEPENDENT-MEMORY-SEED', 'category': 'public_memory_contract', 'query': 'Inspect my stored formatting preference.', 'setup': {'memories': [{'content': 'I prefer compact status summaries.'}]}, 'actions': []}
    source = ROOT / 'scripts/campaign10_core/harness.py'
    (output / 'harness-snapshot.py').write_bytes(source.read_bytes())
    try:
        receipt = run_case(case, output / 'fresh-state')
        row = {'completed': True, 'receipt': receipt}
    except Exception as exc:
        row = {'completed': False, 'error': {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}}
    row.update(input_only_case=case, helper_sha256=digest(source), actual_model_posts=0)
    (output / 'RECEIPT.json').write_text(json.dumps(row, indent=2) + '\n', encoding='utf-8')
    return {key: row[key] for key in ('completed', 'helper_sha256', 'actual_model_posts')}
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['workflows', 'memory_seed', 'interfaces'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ids', nargs='+')
    args = parser.parse_args()
    result = workflow_reproductions(args.output, args.ids) if args.kind == 'workflows' else interface_reproductions(args.output) if args.kind == 'interfaces' else memory_seed_reproduction(args.output)
    print(json.dumps(result, indent=2))
