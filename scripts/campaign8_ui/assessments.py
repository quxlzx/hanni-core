"""Map independently observed DEVELOPMENT actions to exact source declarations.

Matching is conservative: ambiguous names/unknown selectors remain unmatched.
One declaration's tested fixture branch never proves all repeated data values.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import re
from html import unescape
from .scorecard import routes_for

def literal(value):
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None
SELECTOR_SLOTS = {'.task-title': ('productivity.tsx', 307), '.project-list button': ('productivity.tsx', 598), '.project-note summary': ('productivity.tsx', 686), '.project-note button': ('productivity.tsx', 693), '.memory-tabs button': ('memory.tsx', 345), '.memory-tabs [role="tab"]': ('memory.tsx', 345), '.memory-tabs [role="tab"][tabindex="0"]': ('memory.tsx', 345), '.memory-search input': ('memory.tsx', 403), '.workflow-row': ('workflows.tsx', 290), '.workflow-history summary': ('workflows.tsx', 933), '.lab-tabs button': ('model_lab.tsx', 445), '.lab-row-link': ('model_lab.tsx', 521), '.lab-inventory thead th:first-child button': ('model_lab.tsx', 494), '.mcp-server-row': ('mcp_hub.tsx', 534), '.mcp-connection-details summary': ('mcp_hub.tsx', 702), '.mcp-import-json': ('mcp_hub.tsx', 1155), '.notification-preferences summary': ('awareness.tsx', 516), '.notification-preferences input': ('awareness.tsx', 524), '.memory-mode-details summary': ('memory.tsx', 326), '.routing-endpoint summary': ('model_routing.tsx', 415), '#motion': ('screens.tsx', 760), '#workspace-search': ('workspace.tsx', 1363), '.inspector button[aria-label="Hide inspector"]': ('workspace.tsx', 1171), '.area-button': ('workspace.tsx', 934), '.connection': ('workspace.tsx', 1062), '.memory-project-list button': ('memory.tsx', 885), '.memory-history details summary': ('memory.tsx', 627), 'section[aria-label="Pending memory suggestions"] .memory-index-row': ('memory.tsx', 706), 'dialog .mcp-import-candidate input[type="checkbox"]': ('mcp_hub.tsx', 1180), 'dialog input[type="file"]': ('mcp_hub.tsx', 1137), '.lab-case-list button': ('model_lab.tsx', 1150), '.memory-project-index button': ('memory.tsx', 885), '.mcp-checkbox input': ('mcp_hub.tsx', 1065), '.mini-capabilities button': ('mini.tsx', 359), '.lab-run-protocol summary': ('model_lab.tsx', 1269), '.execution-record > summary': ('activity.tsx', 286), '.execution-record details summary': ('activity.tsx', 338), '.cluster-node': ('cluster.tsx', 769), '.cluster-connection summary': ('cluster.tsx', 299), '.allowed-actions summary': ('screens.tsx', 723), '.awareness-diagnostic summary': ('awareness.tsx', 73), '.command-results button': ('workspace.tsx', 1372), '.notification-group-item:has-text("Controlled QA record available") button:has-text("Inspect event")': ('awareness.tsx', 435), '.mcp-tool-row button': ('mcp_hub.tsx', 835), '.calendar-deadlines button.text-link': ('productivity.tsx', 555), '.project-link button.text-link': ('productivity.tsx', 738), '.memory-project-section details summary': ('memory.tsx', 1338), '.memory-context-source summary': ('memory.tsx', 1375), '.workflow-control-reasons summary': ('workflows.tsx', 668), '.workflow-step > summary': ('workflows.tsx', 797), '.workflow-artifacts details summary': ('workflows.tsx', 904), '.settings-section .facts button:not([id])': ('screens.tsx', 754), '.lab-history tbody .lab-row-link': ('model_lab.tsx', 1029), '.lab-history tbody tr button:has-text("Inspect")': ('model_lab.tsx', 1054), '.command-results button:has-text("file.stat")': ('workspace.tsx', 1396)}

def source_line(row):
    return row.get('_mapping_anchor_line', row['line'])

def candidates(controls, step, route, routes, preceding=(), observed=None):
    available = [row for row in controls if route in routes_for(row, routes)]
    selector = step.get('selector', '')
    if selector in SELECTOR_SLOTS:
        file, line = SELECTOR_SLOTS[selector]
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == file]
    if selector == 'dialog' and step.get('action') == 'press' and (step.get('key') == 'Escape'):
        if any((s.get('name') == 'View output' for s in preceding)) and route == 'workflows':
            return [row for row in available if row['component'] == 'FeatureDialog' and row['tag'] == 'dialog']
        if any((s.get('name') == 'Search workspace' for s in preceding)):
            return [row for row in available if row['component'] == 'Modal' and row['tag'] == 'dialog']
        if route == 'models' and any((s.get('name') == 'View JSON' for s in preceding)):
            return [row for row in available if row['component'] == 'FeatureDialog' and row['tag'] == 'dialog']
    if route == 'models' and (step.get('name') == 'View JSON' or selector == '.lab-actions button:has-text("View JSON ")'):
        target = 'viewRunJson(r)' if selector else 'viewRunJson(detail.run)'
        return [row for row in available if row['component'] == 'ModelLabPage' and row['tag'] == 'button' and (target in str(row['attributes'].get('onClick', '')))]
    if selector.startswith('#'):
        return [row for row in available if literal(row['attributes'].get('id')) == selector[1:]]
    match = re.fullmatch('(\\w+)\\[aria-label="([^"]+)"\\]', selector)
    if match:
        return [row for row in available if row['tag'] == match[1] and literal(row['attributes'].get('aria-label')) == match[2]]
    match = re.fullmatch('(\\w+)\\[placeholder="([^"]+)"\\]', selector)
    if match:
        return [row for row in available if row['tag'] == match[1] and literal(row['attributes'].get('placeholder')) == match[2]]
    if route == 'memory' and selector == 'dialog textarea':
        triggers = {'Correct memory': 1015, 'Suggest from a statement': 961, 'Edit & approve': 1081}
        chosen = [line for name, line in triggers.items() if any((s.get('name') == name for s in preceding))]
        if len(chosen) == 1:
            return [row for row in available if source_line(row) == chosen[0] and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if route == 'memory' and selector == 'dialog input' and any((s.get('name') in {'Add alias', 'Link workflow'} for s in preceding)):
        return [row for row in available if source_line(row) == 1103 and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if route == 'memory' and selector == 'dialog select' and any((s.get('name') in {'Find related records', 'Suggest from a statement'} for s in preceding)):
        return [row for row in available if source_line(row) == 972 and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if route == 'memory' and selector == 'dialog select' and any((s.get('name') == 'Correct memory' for s in preceding)):
        line = {0: 1025, 1: 1039}.get(step.get('index', 0))
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if route == 'mcp' and selector == '.mcp-tool-inspector details summary':
        line = {0: 1408, 1: 1413, 2: 1419, 3: 1430}.get(step.get('index', 0))
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'mcp_hub.tsx']
    if route == 'workflows' and selector == '.workflow-step details summary':
        line = {0: 876, 1: 881}.get(step.get('index', 0))
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'workflows.tsx']
    if route == 'models' and selector == '.lab-case-detail details summary':
        line = {0: 1243, 1: 1253}.get(step.get('index', 0))
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'model_lab.tsx']
    if route == 'memory' and selector == '.memory-search select':
        line = {0: 413, 1: 431, 2: 456}.get(step.get('index', 0))
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if route == 'memory' and selector == '.memory-index-row':
        tab_steps = [s.get('name') for s in preceding if s.get('role') == 'tab']
        if not tab_steps:
            tab_steps = [r.get('name') for r in (observed or {}).get('controls', ()) if r.get('role') == 'tab' and str(r.get('ariaSelected')).lower() == 'true']
        if tab_steps:
            line = 706 if re.fullmatch('Review queue\\s*\\d*', tab_steps[-1] or '') else 490 if tab_steps[-1] == 'Stored memories' else None
            return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if selector:
        match = re.fullmatch('\\.([\\w-]+)(?:\\s+(input|select|textarea|button))?(?:\\[title="([^"]+)"\\])?', selector)
        if match:
            class_name, child, title = match.groups()
            direct = [row for row in available if class_name in str(literal(row['attributes'].get('className')) or '').split() and (not child) and (not title or literal(row['attributes'].get('title')) == title)]
            if direct:
                return direct
        match = re.fullmatch('\\.(\\w[\\w-]*) (button|input|select|textarea)\\[([^=\\]]+)="([^"]+)"\\]', selector)
        if match:
            _, tag, attribute, value = match.groups()
            matches = [row for row in available if row['tag'] == tag and literal(row['attributes'].get(attribute)) == value]
            if len(matches) == 1:
                return matches
    name = step.get('name')
    role = step.get('role')
    if not name:
        return []
    if name == 'Cancel' and route in {'tasks', 'projects', 'memory', 'mcp'}:
        if route in {'tasks', 'projects'}:
            confirmation = any((s.get('name', '').startswith(('Delete ', 'Remove ')) for s in preceding))
            file, line = ('productivity.tsx', 1048 if confirmation else 1021)
        elif route == 'memory':
            file, line = ('memory.tsx', 1123)
        else:
            confirmation = any((s.get('name') == 'Remove server' for s in preceding))
            importing = any((s.get('name') == 'Import config' for s in preceding))
            file, line = ('mcp_hub.tsx', 1298 if confirmation else 1206 if importing else 1111)
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == file]
    if route == 'notifications' and name == 'Cancel' and any((s.get('name') == 'Clear all' for s in preceding)):
        return [row for row in available if source_line(row) == 559 and Path(row['id'].split(':')[0]).name == 'awareness.tsx']
    if route == 'memory' and name in {'Next', 'Previous'}:
        selected = [r.get('name') for r in (observed or {}).get('controls', ()) if r.get('role') == 'tab' and str(r.get('ariaSelected')).lower() == 'true']
        if len(selected) == 1:
            selected = ['Review queue' if re.fullmatch('Review queue\\s*\\d*', selected[0] or '') else selected[0]]
            line = {'Stored memories': {'Next': 528, 'Previous': 522}, 'Review queue': {'Next': 734, 'Previous': 726}}.get(selected[0], {}).get(name)
            return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == 'memory.tsx']
    if route == 'memory' and role == 'tab':
        return [row for row in available if row['tag'] == 'button' and literal(row['attributes'].get('role')) == 'tab']
    if route == 'models' and role == 'button' and (name in {'Overview', 'Benchmark runner', 'Results', 'Compare', 'Routing insights'}):
        return [row for row in available if row['component'] == 'ModelLabPage' and row['attributes'].get('onClick') == '{() => setTab(t)}']
    if route == 'workflows' and name == 'Back to workflows':
        return [row for row in available if source_line(row) == 587 and Path(row['id'].split(':')[0]).name == 'workflows.tsx']
    aliases = {}
    if route in {'tasks', 'projects'}:
        aliases = {'Save': ('productivity.tsx', 1028), 'Confirm deletion': ('productivity.tsx', 1055)}
        if name.startswith(('Complete ', 'Reopen ')):
            aliases[name] = ('productivity.tsx', 287)
        elif name.startswith('Delete '):
            if route == 'tasks':
                aliases[name] = ('productivity.tsx', 333)
        elif name.startswith('Remove ') and 'link' in name:
            aliases[name] = ('productivity.tsx', 762)
    elif route == 'memory':
        aliases = {n: ('memory.tsx', 1126) for n in ('Save change', 'Reject suggestion', 'Approve suggestion', 'Approve memory', 'Dismiss suggestion', 'Create suggestion', 'Find suggestions', 'Save alias', 'Confirm deletion')}
        aliases['Statement type'] = ('memory.tsx', 1039)
        aliases['Remove'] = ('memory.tsx', 1290)
    elif route == 'mcp':
        aliases = {'Save server': ('mcp_hub.tsx', 1118), 'Remove integration': ('mcp_hub.tsx', 1305), 'Confirm change': ('mcp_hub.tsx', 1305), 'Approve tools': ('mcp_hub.tsx', 1305), 'Enable server': ('mcp_hub.tsx', 653), 'Disable server': ('mcp_hub.tsx', 653), 'Close dialog': ('feature_ui.tsx', 29)}
        aliases.update({'‹ All servers': ('mcp_hub.tsx', 596), 'Permission classification': ('mcp_hub.tsx', 1458), 'Approve & enable': ('mcp_hub.tsx', 1471), 'Review approval': ('mcp_hub.tsx', 1471)})
        if name == 'Select controlled_metadata_read':
            aliases[name] = ('mcp_hub.tsx', 818)
    elif route == 'settings':
        aliases['MCP Hub'] = ('screens.tsx', 639)
    elif route == 'models' and name == 'Resume checkpoint':
        changes = [s.get('name') for s in preceding if s.get('name') in {'Benchmark runner', 'Inspect results', 'Results'}]
        if changes:
            aliases[name] = ('model_lab.tsx', 909 if changes[-1] == 'Benchmark runner' else 1101)
    elif route == 'workflows' and name == 'Refresh workflow':
        if any((s.get('selector') == '.workflow-row' for s in preceding)):
            aliases[name] = ('workflows.tsx', 590)
    elif route == 'model-routing':
        aliases = {'Selection policy': ('model_routing.tsx', 295), 'Preferred endpoint': ('model_routing.tsx', 313), 'Refresh endpoints': ('model_routing.tsx', 244)}
    elif route == 'mini':
        aliases = {'Global shortcut': ('mini.tsx', 277)}
    if name in {'Show inspector', 'Hide inspector'}:
        aliases[name] = ('workspace.tsx', 1070)
    if role == 'button' and name == 'Workflows':
        aliases[name] = ('workspace.tsx', 959)
    if name in {'Show voice details', 'Hide voice details'}:
        aliases[name] = ('workspace.tsx', 1265)
    if name in {'Pause voice visual', 'Resume voice visual'}:
        aliases[name] = ('workspace.tsx', 1317)
    if name in aliases:
        file, line = aliases[name]
        return [row for row in available if source_line(row) == line and Path(row['id'].split(':')[0]).name == file]
    tag = {'button': 'button', 'link': 'a', 'combobox': 'select', 'textbox': 'input'}.get(role)
    matches = []
    for row in available:
        if tag and row['tag'] != tag:
            continue
        labels = [literal(row['attributes'].get(k)) for k in ('aria-label', 'title')]
        labels.append(unescape(re.sub('\\s+', ' ', row.get('static_child_text', '')).strip()))
        if name in labels:
            matches.append(row)
    return matches

def build(source, groups, *, controls_override=None):
    controls = controls_override if controls_override is not None else [row for module in source['modules'] for row in module['controls']]
    routes = [r['route'] for r in source['routes']]
    assessments, unmatched = ({}, [])
    for receipt_path, review_path, review_rows in groups:
        raw = json.loads(Path(receipt_path).read_text(encoding='utf8'))
        reviewed = {row['id']: row for row in review_rows}
        for case in raw.get('development_cases', []):
            identifier = case['input']['id']
            review = reviewed.get(identifier)
            if not review or review.get('status') != 'PASS' or case.get('executed') is not True:
                continue
            for index, step in enumerate(case['input'].get('steps', [])):
                if identifier == 'local-final-memory-correction-fields-cancel' and step.get('name') == 'Project':
                    unmatched.append({'case': identifier, 'step': index, 'input': step, 'reason': 'Independent native review explicitly found background filter selected; modal Project change was not measured.', 'candidate_ids': []})
                    continue
                route = 'mini' if case['input'].get('surface') == 'mini' else case['input']['route']
                native_steps = case.get('step_receipts', [])
                if index and route != 'mini' and (index <= len(native_steps)):
                    previous = native_steps[index - 1].get('result') or {}
                    actual_route = previous.get('url', '').partition('#')[2]
                    if actual_route in routes:
                        route = actual_route
                observed = native_steps[index].get('result') if index < len(native_steps) else None
                matches = candidates(controls, step, route, routes, case['input']['steps'][:index], observed)
                if len(matches) != 1:
                    unmatched.append({'case': identifier, 'step': index, 'input': step, 'reason': 'No unique reviewed original source declaration', 'candidate_ids': [r['id'] for r in matches]})
                    continue
                row = matches[0]
                reference = {'file': receipt_path, 'case_id': identifier, 'step': index, 'input': step, 'scope': review.get('observed_scope', ''), 'observed_pre_action_route': route, 'structural_anchor_id': row.get('_mapping_anchor_id'), 'structural_anchor_scope': 'Historical action/asset identity retained; exact declaration correspondence is not a new current-code execution.', 'actual_assets': raw.get('assets'), 'evidence_class': review.get('evidence_class', raw.get('evidence_class'))}
                if row['id'] not in assessments:
                    assessments[row['id']] = {'source_slot_ids': [row['id']], 'outcome': 'PASS', 'reason': 'Actual native original control action and independently reviewed result in the exact listed synthetic fixture branch. Other repeated values, hidden states and operation variants remain unproven.', 'evidence_references': [], 'action_evidence': [], 'readback_evidence': [], 'semantic_readback': [], 'coverage_scope': 'Listed controlled native fixture cases only; not all data-bound repetitions or whole-product acceptance.'}
                item = assessments[row['id']]
                item['action_evidence'].append(reference)
                item['readback_evidence'].append({'file': review_path, 'case_id': identifier, 'observed_scope': review.get('observed_scope', ''), 'original_readbacks': review.get('original_readbacks', review.get('source_API_evidence', review.get('readback_statuses')))})
                item['evidence_references'].extend([reference, {'file': review_path, 'case_id': identifier}])
                item['semantic_readback'].append(review.get('observed_scope', ''))
    return (list(assessments.values()), unmatched)

def reviewed_groups(paths):
    """Use public post-run reviews only; verify their referenced raw receipts."""
    groups = []
    for path in paths:
        review = json.loads(Path(path).read_text(encoding='utf8'))
        blocks = [review]
        if isinstance(review.get('corrected_exposed_v3'), dict):
            blocks.append(review['corrected_exposed_v3'])
        for block in blocks:
            raw = block.get('raw', block.get('raw_receipt'))
            if not raw:
                raise ValueError('Review must identify its original raw receipt.')
            raw_path = raw.get('path') if isinstance(raw, dict) else raw
            expected = raw.get('sha256') if isinstance(raw, dict) else block.get('sha256')
            if expected and hashlib.sha256(Path(raw_path).read_bytes()).hexdigest() != expected:
                raise ValueError('Raw receipt changed after independent review.')
            rows = block.get('case_grades', block.get('cases', []))
            groups.append((raw_path, str(path), rows))
    return groups

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--review', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve prior mapping checkpoints.')
    source = json.loads(args.inventory.read_text(encoding='utf8'))
    groups = reviewed_groups(args.review)
    values, unmatched = build(source, groups)
    args.output.mkdir(parents=True)
    for name, obj in [('assessments.json', values), ('unmatched.json', unmatched)]:
        (args.output / name).write_text(json.dumps(obj, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'scoped_source_slots': len(values), 'unmatched_reviewed_steps': len(unmatched)}))
if __name__ == '__main__':
    main()
