"""Reconcile source slots with native observations without visibility-as-PASS."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
OUTCOMES = frozenset({'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN', 'NOT_IMPLEMENTED', 'UNSUPPORTED'})

def _name(control):
    attributes = control['attributes']
    for field in ['aria-label', 'title']:
        value = attributes.get(field, '')
        if value.startswith('"') and value.endswith('"'):
            return json.loads(value)
    return control['static_child_text']

def reconcile(source, native, *, evidence_file, assessments=()):
    slots = [{**control, 'native_candidates': [], 'outcome': 'NOT_RUN', 'reason': 'Source slot has not received a verified native action/readback. Conditional/data-dependent instances may be absent in this fixture.'} for module in source['modules'] for control in module['controls']]
    instances = []
    for action in native.get('actions', []):
        dom = action.get('result')
        if action.get('input', {}).get('action') != 'inventory' or not isinstance(dom, dict):
            continue
        route = dom.get('url', '').split('#')[-1] if '#' in dom.get('url', '') else 'mini'
        if action.get('input', {}).get('view') == 'mini':
            route = 'mini'
        for control in dom.get('controls', []):
            identifier = action['id'] + ':' + str(control['index'])
            candidates = [s['id'] for s in slots if _name(s) and re.sub('\\s+', ' ', _name(s)).strip() == re.sub('\\s+', ' ', control.get('name', '')).strip()]
            state = 'NOT_RUN' if control.get('visible') and control.get('enabled') else 'BLOCKED'
            row = {'id': identifier, 'route': route, 'capture_action': action['id'], 'native_window': action.get('after'), 'viewport': dom.get('viewport'), 'control': control, 'source_candidates': candidates, 'source_mapping_status': 'NAME_CANDIDATES_ONLY', 'outcome': state, 'reason': 'Visible enabled control observed; actual action and semantic/readback check still required.' if state == 'NOT_RUN' else 'Original UI currently hides or disables this instance. Exact dependency/state must be reviewed before claiming functional coverage.', 'evidence_file': evidence_file, 'evidence_class': action.get('evidence_class', native.get('evidence_class')), 'api_authority': 'Not inferred from a DOM label. Source candidates and original route permission gates require action/readback correlation.'}
            instances.append(row)
            for slot in slots:
                if slot['id'] in candidates:
                    slot['native_candidates'].append(identifier)
    for assessment in assessments:
        state = assessment.get('outcome')
        if state not in OUTCOMES or not assessment.get('reason') or (not assessment.get('evidence_file')):
            raise ValueError('Each assessment needs a supported outcome, reason and evidence file.')
        if state == 'PASS' and (not (assessment.get('action_evidence') and assessment.get('readback_evidence'))):
            raise ValueError('PASS requires actual action and semantic/readback evidence, not visibility.')
        keys = set(assessment.get('source_slot_ids', ())) | set(assessment.get('dynamic_instance_ids', ()))
        targets = [row for row in slots + instances if row['id'] in keys]
        if len(targets) != len(keys):
            raise ValueError('Assessment contains unknown or duplicate target identifiers.')
        for row in targets:
            row.update({k: v for k, v in assessment.items() if k not in {'source_slot_ids', 'dynamic_instance_ids'}})
    return {'scope': 'Static JSX slots and concrete native instances are separate denominators; no visibility-based functional passes.', 'static_slots': slots, 'native_instances': instances, 'counts': {'source': dict(Counter((r['outcome'] for r in slots))), 'native': dict(Counter((r['outcome'] for r in instances)))}, 'native_complete': native.get('complete'), 'native_owned_cleanup': native.get('owned_native_cleanup'), 'native_evidence_file': evidence_file}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--assessments', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve coverage checkpoints; choose a fresh output path.')
    data = reconcile(json.loads(args.inventory.read_text(encoding='utf8')), json.loads(args.native.read_text(encoding='utf8')), evidence_file=args.native.as_posix(), assessments=json.loads(args.assessments.read_text(encoding='utf8')) if args.assessments else ())
    data['input_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.inventory, args.native] + ([args.assessments] if args.assessments else [])}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(data['counts']))
if __name__ == '__main__':
    main()
