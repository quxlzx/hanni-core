"""Account for every source declaration, separately from observed DOM instances.

This is a coverage ledger, not a visual grader. Source data never establishes a
functional PASS. Assessments require original native action and result evidence.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from .coverage import OUTCOMES
ROUTES = {'ActivityPage': ['agents', 'activity'], 'ScreenAwarenessPage': ['screen'], 'VoicePage': ['voice'], 'NotificationsPage': ['notifications'], 'NodeDetail': ['cluster'], 'NodePower': ['cluster'], 'ClusterPage': ['cluster'], 'ComputeWorkers': ['cluster'], 'ComputeJobs': ['workflows'], 'ExecutionTracePanel': ['activity'], 'FeatureDialog': ['tasks', 'planner', 'calendar', 'projects', 'memory', 'workflows', 'mcp', 'cluster', 'models'], 'MCPHubPage': ['mcp'], 'ToolInspector': ['mcp'], 'MemoryPage': ['memory'], 'ProjectView': ['memory'], 'Mini': ['mini'], 'Fields': ['models'], 'ModelLabPage': ['models'], 'Outcome': ['models'], 'ModelRoutingPage': ['model-routing', 'models'], 'WorkspacePage': ['planner', 'tasks', 'calendar', 'projects'], 'HomeScreen': ['home'], 'ConversationScreen': ['chat'], 'MissionScreen': ['mission'], 'SettingsScreen': ['settings'], 'ModelRow': ['mission'], 'AudioSettings': ['settings', 'voice'], 'GpuSettings': ['settings'], 'WorkflowsPage': ['workflows'], 'WorkflowDetailView': ['workflows'], 'WorkflowPolicy': ['workflows'], 'WorkflowCollaborationView': ['workflows']}

def label(control):
    for name in ['aria-label', 'title', 'placeholder']:
        value = control['attributes'].get(name)
        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
            return json.loads(value)
    return control.get('static_child_text') or control['attributes'].get('id') or '<data-bound/unnamed declaration>'

def routes_for(control, all_routes):
    candidates = set(control.get('route_predicate_candidates', all_routes + ['mini']))
    if control['component'] == 'App' or control['component'] == 'Modal':
        return [route for route in all_routes if route in candidates]
    if control['component'] == 'ToolActivity':
        return ['home', 'chat', 'mission']
    return [route for route in ROUTES.get(control['component'], []) if route in candidates]

def pending_outcome(control, routes):
    attrs = control['attributes']
    description = ' '.join((str(attrs.get(key, '')) for key in ['aria-label', 'className', 'onClick', 'onChange'])) + ' ' + control.get('static_child_text', '')
    disabled = str(attrs.get('disabled', ''))
    if control['component'] == 'ScreenAwarenessPage' and 'prepare(' in description:
        return ('NOT_IMPLEMENTED', 'Original /api/awareness reports no capture/context pipeline; no physical acquisition, image analysis, expiry, or sensitive-frame enforcement can be exercised. Disabled-state pixels are a separate truth check.')
    if control['component'] in {'NodePower', 'ComputeWorkers'} and re.search('confirm|reboot|sleep|terminal|control\\(|start|stop', description, re.I):
        return ('BLOCKED', 'Original isolated deployment has no authenticated/configured node workers. Node power, SSH terminal and model process start/stop are excluded from this safe native fixture.')
    if re.search('clipboard|copyExport|copy.*JSON', description, re.I):
        return ('BLOCKED', 'Clipboard write requires a controlled clipboard leaf; owner clipboard may not be overwritten. A selected-text fallback or scoped dependency test is not a physical clipboard pass.')
    if control['component'] in {'VoicePage', 'Mini'} and re.search('act\\(|controlVoice\\(', description):
        return ('BLOCKED', 'Original fixture has no active voice controller; physical microphone/speaker unavailable. No voice activation or acoustic output is permitted.')
    if control['component'] in {'WorkflowsPage', 'WorkflowDetailView'} and re.search('control\\(|approve|reject|revoke|confirmReview|submit', description, re.I):
        return ('BLOCKED', 'Original fixture workflow runner/controller is unattached. Manually seeded history proves original persistence/projection only; it does not authorize actual planning, execution or approval consumption.')
    if control['component'] in {'ModelLabPage', 'Fields'} and control['tag'] == 'button' and re.search('control\\(|Start benchmark', description):
        return ('NOT_RUN', 'Model-required suites are ineligible on the unavailable controlled endpoint. The original routing-development suite is model-free and may enable Start/Pause/Cancel/Resume; absence of a matching native receipt is a coverage gap, not a blanket model dependency block.')
    if control['component'] == 'MCPHubPage' and re.search('askServer\\("(?:test_discover|reconnect|disconnect)|\\"refresh\\"', description):
        return ('BLOCKED', 'No connected external MCP provider is present. Discovery/reconnect may launch an executable or contact a provider; unsafe process/network leaves remain unavailable.')
    if disabled == '{true}' or attrs.get('disabled') is True:
        return ('BLOCKED', 'This declaration is explicitly disabled in original source; native disabled-state truth can be checked, but no supported activation exists in the present state.')
    boundary = '; '.join((f"{item['kind']}: {item['expression']}" for item in control.get('render_boundaries', ())))
    if not routes:
        return ('NOT_RUN', 'Source declaration has no resolved original route ownership; no native action/readback may be attributed until its importing/rendering component is reviewed.')
    reason = f"No verified original native action/result receipt yet for this {control['tag']} declaration on {', '.join(routes)}."
    if boundary:
        reason += ' Required render/data state: ' + boundary[:1400] + '.'
    if disabled:
        reason += ' Original disabled predicate: ' + disabled[:500] + '.'
    return ('NOT_RUN', reason)

def build(source, *, source_file, native_observations=None, assessments=()):
    routes = [row['route'] for row in source['routes']]
    rows = []
    for module in source['modules']:
        for control in module['controls']:
            routed = routes_for(control, routes)
            outcome, reason = pending_outcome(control, routed)
            row = {**control, 'declaration': {'component': control['component'], 'tag': control['tag'], 'label': label(control)}, 'source_locator': {'file': module['file'], 'line': control['line'], 'column': control['column']}, 'routed_screens': routed, 'route_status': 'RESOLVED' if routed else 'UNRESOLVED_SOURCE_DECLARATION', 'outcome': outcome, 'reason': reason, 'evidence_references': [{'file': module['file'], 'line': control['line'], 'scope': 'Source declaration and original render/disabled predicates only'}, {'file': source_file, 'path': control['id'], 'scope': 'Dynamic original source inventory'}], 'authority_status': 'SOURCE_CANDIDATES_ONLY; original HTTP/OS gates still required', 'keyboard': {'declared_handlers': {key: value for key, value in control['attributes'].items() if key in {'onKeyDown', 'onKeyUp', 'onCancel', 'tabIndex', 'role'}}, 'native_focus_verified': False}, 'semantic_readback': None, 'coverage_scope': 'One static JSX declaration, potentially many conditional/data-bound native instances.'}
            rows.append(row)
    by_id = {row['id']: row for row in rows}
    for assessment in assessments:
        if assessment.get('outcome') not in OUTCOMES or not assessment.get('reason') or (not assessment.get('evidence_references')):
            raise ValueError('Assessments require outcome, concrete reason, and evidence references.')
        if assessment['outcome'] == 'PASS' and (not (assessment.get('action_evidence') and assessment.get('readback_evidence'))):
            raise ValueError('A source-slot PASS requires actual action and semantic readback.')
        for key in assessment.get('source_slot_ids', ()):
            if key not in by_id:
                raise ValueError('Unknown source locator; do not infer a source match.')
            by_id[key].update({k: v for k, v in assessment.items() if k != 'source_slot_ids'})
            if assessment['outcome'] == 'PASS':
                by_id[key]['scope'] = 'Observed only in the exact independently reviewed native fixture branch; source origin and unobserved repeated variants remain separate.'
    if len(rows) != sum((len(module['controls']) for module in source['modules'])) or len(by_id) != len(rows):
        raise ValueError('Source declarations must each have exactly one unique scorecard row.')
    return {'scope': 'Complete dynamic source-slot accounting. Observed DOM instances, native actions, and dependency contracts remain separate denominators.', 'source_inventory': source_file, 'source_identity': source['source_hashes'], 'static_slot_count': len(rows), 'outcome_counts': dict(Counter((row['outcome'] for row in rows))), 'route_declaration_candidates': {route: dict(Counter((row['outcome'] for row in rows if route in row['routed_screens']))) for route in routes + ['mini']}, 'route_count_scope': 'Source-render candidates after provable route predicate narrowing; shared/editor declarations can remain possible on several screens. These are not observed native control counts or per-route execution passes.', 'rows': rows, 'native_observation_counts': native_observations, 'source_slots_are_not_concrete_control_count': True, 'eligible_functional_fraction': None, 'fraction_reason': 'Eligibility/action/readback review is incomplete; NOT_RUN is not a pass or excluded denominator.'}

def markdown(scorecard):
    lines = ['# Static control scorecard', '', 'Each row is one original JSX declaration. Repeated values and physical DOM instances are separate observations. Source-only evidence never produces PASS.', '', f"Dynamic declarations: {scorecard['static_slot_count']}. Outcomes: {json.dumps(scorecard['outcome_counts'], sort_keys=True)}.", '', '| Source declaration | Component/control | Routed screen | Outcome | Concrete reason |', '| --- | --- | --- | --- | --- |']
    for row in scorecard['rows']:
        locator = row['source_locator']
        control = f"{row['component']}: {row['declaration']['label']} ({row['tag']})"
        values = [f"[{row['id']}](../../../{locator['file']}#L{locator['line']})", control, ', '.join(row['routed_screens']) or 'UNRESOLVED', row['outcome'], row['reason']]
        lines.append('| ' + ' | '.join((re.sub('\\s+', ' ', value).replace('|', '\\|') for value in values)) + ' |')
    lines.extend(['', 'The JSON companion retains all attributes, render boundaries, source API candidates, evidence scopes and keyboard predicates. No visibility-based functional acceptance is inferred.', ''])
    return '\n'.join(lines)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--assessments', type=Path)
    parser.add_argument('--native-coverage', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Choose a fresh scorecard checkpoint; preserve prior outcomes.')
    source = json.loads(args.inventory.read_text(encoding='utf8'))
    native = json.loads(args.native_coverage.read_text(encoding='utf8')) if args.native_coverage else None
    value = build(source, source_file=args.inventory.as_posix(), native_observations=native['counts']['native'] if native else None, assessments=json.loads(args.assessments.read_text(encoding='utf8')) if args.assessments else ())
    value['inventory_sha256'] = hashlib.sha256(args.inventory.read_bytes()).hexdigest()
    args.output.mkdir(parents=True)
    (args.output / 'STATIC_SCORECARD.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')
    (args.output / 'STATIC_SCORECARD.md').write_text(markdown(value), encoding='utf8', newline='\n')
    print(json.dumps({'source_slots': value['static_slot_count'], 'outcomes': value['outcome_counts']}))
if __name__ == '__main__':
    main()
