"""Independent public resumed probes; never reads or runs a final holdout."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from .adapter import run_input
from .contracts import receipt_observation
from .integrity import digest
ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'data/campaign10-verifier-public'

def reproduce_shared(cycle=1):
    from scripts.campaign10_systems.shared import execute_input
    source = ROOT / 'data/campaign10-systems/public-shared-smoke-prospective-cycle1'
    seal = json.loads((source / 'SEAL.json').read_text(encoding='utf8'))
    inputs = source / 'inputs.json'
    assert digest(inputs) == seal['input_sha256']
    cases = json.loads(inputs.read_text(encoding='utf8'))['cases']
    selected = {'PUBLIC-SYSTEMS-UNREVIEWED', 'PUBLIC-SYSTEMS-REVIEWED', 'PUBLIC-SYSTEMS-PREREQUISITE', 'PUBLIC-SYSTEMS-NONOWNER', 'PUBLIC-SYSTEMS-MISSINGPLAN'}
    cases = [case for case in cases if case['id'] in selected]
    assert len(cases) == 5
    destination = PUBLIC / f'resume-shared-independent-cycle{cycle}'
    destination.mkdir(parents=True, exist_ok=False)
    records = []
    for index, case in enumerate(cases, 1):
        row = run_input(case, destination / f'case-{index:03d}', execute_input)
        target = destination / f'receipt-{index:03d}.json'
        target.write_text(json.dumps(receipt_observation(row), indent=2, allow_nan=False) + '\n', encoding='utf8')
        records.append({'id': case['id'], 'receipt': target.name, 'sha256': digest(target), 'evidence_categories': row['evidence_categories'], 'request_path_original': row['request_path_original'], 'actual_model_calls': row['actual_model_calls'], 'harness_error': row.get('harness_error'), 'adapter_limitation': row.get('adapter_limitation')})
    summary = {'version': 1, 'scope': 'Independent public controlled original Systems bridge reproduction', 'input_sha256': seal['input_sha256'], 'task_count': 5, 'records': records, 'source_pins': {path: digest(ROOT / path) for path in ('scripts/campaign10_systems/shared.py', 'scripts/campaign10_systems/runner.py')}, 'private_final_executed': False, 'model_or_provider_requests': 0}
    target = destination / 'MANIFEST.json'
    target.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
    return {'public_probe_count': 5, 'manifest_sha256': digest(target), 'private_final_executed': False}

def reproduce_shared_path_controls():
    from scripts.campaign10_systems.shared import execute_input
    source = ROOT / 'data/campaign10-systems/public-shared-smoke-prospective-cycle1/inputs.json'
    cases = json.loads(source.read_text(encoding='utf8'))['cases']
    base = next((case for case in cases if case['id'] == 'PUBLIC-SYSTEMS-REVIEWED'))
    destination = PUBLIC / 'resume-shared-path-independent-cycle1'
    destination.mkdir(parents=True, exist_ok=False)
    marker = destination / 'sibling-marker.txt'
    marker.write_text('Public owned sibling marker.', encoding='utf8')
    before = digest(marker)
    negative = deepcopy(base)
    negative['id'] = 'PUBLIC-REFERENCE-OUTSIDE'
    negative['fixtures']['files']['a.txt'] = str(marker)
    negative['fixtures']['steps'][1]['arguments']['path'] = {'$ref': {'step_id': 'first', 'path': '/data/text', 'type': 'string'}}
    positive = deepcopy(base)
    positive['id'] = 'PUBLIC-REFERENCE-ARTIFACT'
    goal = 'Read {root}/a.txt, save that verified text as a report, then read the saved report.'
    positive['user_turns'][0]['prompt'] = positive['fixtures']['goal'] = goal
    positive['fixtures']['steps'] = [positive['fixtures']['steps'][0], {'step_id': 'save', 'description': 'Save the requested report to {artifact_root}/handoff.md', 'kind': 'artifact', 'capability_id': 'file.write', 'dependencies': ['first'], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/path', 'expected': None}], 'arguments': {'path': '{artifact_root}/handoff.md', 'text': {'$ref': {'step_id': 'first', 'path': '/data/text', 'type': 'string'}}}}, {'step_id': 'readback', 'description': 'Read the saved report file {artifact_root}/handoff.md', 'kind': 'tool', 'capability_id': 'file.read', 'dependencies': ['save'], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/text', 'expected': None}], 'arguments': {'path': {'$ref': {'step_id': 'save', 'path': '/data/path', 'type': 'string'}}}}]
    inputs = destination / 'inputs.json'
    inputs.write_text(json.dumps({'cases': [negative, positive]}, indent=2) + '\n', encoding='utf8')
    input_hash = digest(inputs)
    (destination / 'SEAL.json').write_text(json.dumps({'task_count': 2, 'input_sha256': input_hash, 'scope': 'New public independent path-boundary controls sealed before execution'}) + '\n', encoding='utf8')
    records = []
    for index, case in enumerate([negative, positive], 1):
        row = run_input(case, destination / f'case-{index:03d}', execute_input)
        target = destination / f'receipt-{index:03d}.json'
        target.write_text(json.dumps(receipt_observation(row), indent=2, allow_nan=False) + '\n', encoding='utf8')
        records.append({'id': case['id'], 'receipt': target.name, 'sha256': digest(target), 'adapter_limitation': row.get('adapter_limitation'), 'status': row.get('status'), 'verified_steps': row.get('verified_steps'), 'invocation_count': row.get('invocation_count'), 'write_effect_count': row.get('write_effect_count'), 'report_texts': row.get('report_texts'), 'unauthorized_effects': row.get('unauthorized_effects'), 'duplicate_effects': row.get('duplicate_effects'), 'request_path_original': row['request_path_original'], 'actual_model_calls': row['actual_model_calls']})
    assert digest(inputs) == input_hash and digest(marker) == before
    negative_raw = json.loads((destination / 'receipt-001.json').read_text(encoding='utf8'))
    assert negative_raw['original_adapter_invocations'] == 0 and (not (destination / 'case-001/services').exists())
    positive_raw = json.loads((destination / 'receipt-002.json').read_text(encoding='utf8'))
    assert positive_raw['status'] == 'completed' and positive_raw['verified_steps'] == 3
    assert positive_raw['write_effect_count'] == 1 and positive_raw['duplicate_effects'] == positive_raw['unauthorized_effects'] == 0
    assert positive_raw['raw_workflow']['workflow']['steps'][2]['result']['data']['text'] == base['fixtures']['files']['a.txt']
    summary = {'input_sha256': input_hash, 'records': records, 'sibling_marker_unchanged': True, 'source_sha256': digest(ROOT / 'scripts/campaign10_systems/shared.py'), 'new_model_or_provider_calls': 0, 'private_final_executed': False}
    target = destination / 'INDEPENDENT_REVIEW.json'
    target.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
    return {'public_path_controls': 2, 'review_sha256': digest(target), 'private_final_executed': False}

def replay_public_mcp_guard(stage):
    from hanni.mcp.session import McpToolSession
    from hanni.core.orchestrator import TextSession
    from scripts.campaign10_core.harness import NoInferenceClient
    live = ROOT / 'data/campaign10-manager/resumed-controller-smoke-cycle1/execution'
    receipt_path = live / 'receipt-004.json'
    wire_path = live / 'model/WIRE.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf8'))
    wires = json.loads(wire_path.read_text(encoding='utf8'))
    originals = [r for r in wires if r['task_id'] == 'SMOKE-INERT-MCP']
    responses = [json.loads(r['raw_response'])['choices'][0]['message'].get('content') for r in originals]
    answer = next((text for text in reversed(responses) if text))
    call = receipt['actual_registry_calls'][0]
    result = deepcopy(call['result'])
    assert result['verification']['status'] == 'UNVERIFIED'
    client = NoInferenceClient()
    controller = McpToolSession(TextSession(client), client, None)
    controller._turn_results = [(call['name'], deepcopy(call['arguments']), result, True)]
    guarded = controller._guard_answer(answer)
    source = ROOT / 'src/hanni/mcp/session.py'
    target = PUBLIC / f'mcp-guard-{stage}.json'
    row = {'scope': 'Replay of actual public captured model answer through current original final guard; no new inference', 'source_sha256': digest(source), 'live_receipt_source_sha256': receipt['source_pins']['src/hanni/mcp/session.py'], 'receipt_sha256': digest(receipt_path), 'wire_sha256': digest(wire_path), 'captured_model_answer': answer, 'original_tool_result': result, 'actual_guarded_answer': guarded, 'verification_status_after': result['verification']['status'], 'actual_generation_posts': 0, 'private_final_executed': False}
    with target.open('x', encoding='utf8') as stream:
        stream.write(json.dumps(row, indent=2) + '\n')
    if stage == 'before':
        with (PUBLIC / 'mcp-guard-before-source.py').open('x', encoding='utf8') as stream:
            stream.write(source.read_text(encoding='utf8'))
    return {'stage': stage, 'source_matches_live_receipt': row['source_sha256'] == row['live_receipt_source_sha256'], 'actual_guarded_answer': guarded, 'receipt_sha256': digest(target), 'new_generation_posts': 0}

def reproduce_message_bounds():
    """Load the public preserved before class, without changing original code."""
    import importlib.util
    from hanni.core.orchestrator import TextSession
    from hanni.mcp.session import McpToolSession
    from hanni.logs.redaction import register_secret
    from scripts.campaign10_core.harness import NoInferenceClient
    before_root = ROOT / 'data/campaign10-core/message-bound-before'
    before_source = before_root / 'session.py'
    before_seal = json.loads((before_root / 'SEAL.json').read_text(encoding='utf8'))
    assert digest(before_source) == before_seal['source_sha256']
    spec = importlib.util.spec_from_file_location('campaign10_public_before_message', before_source)
    before_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before_module)
    destination = PUBLIC / 'resume-message-bounds-independent-cycle1'
    destination.mkdir(parents=True, exist_ok=False)
    canary = 'public-independent-message-canary-538017'
    register_secret('public_independent_message', canary)
    message = canary + ' ' + '雪🧭\n"\\' * 6000
    inputs = {'message': message, 'limits': [1000, 12000], 'verification': {'status': 'UNVERIFIED', 'scope': 'external_tool_response', 'independent': False}}
    input_path = destination / 'inputs.json'
    input_path.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    input_hash = digest(input_path)
    (destination / 'SEAL.json').write_text(json.dumps({'input_sha256': input_hash, 'scope': 'Public independent UTF-8/escaping/redaction controls sealed before replay', 'before_source_sha256': digest(before_source), 'after_source_sha256': digest(ROOT / 'src/hanni/mcp/session.py')}) + '\n', encoding='utf8')
    rows = []
    for label, controller_class in [('before', before_module.McpToolSession), ('after', McpToolSession)]:
        for limit in inputs['limits']:
            client = NoInferenceClient()
            controller = controller_class(TextSession(client), client, None, tool_result_chars=limit)
            result = {'ok': True, 'message': message, 'data': {'structured_content': None}, 'verification': deepcopy(inputs['verification'])}
            snapshot = deepcopy(result)
            controller._turn_results = [('mcp.public_read', {}, result, True)]
            answer = controller._guard_answer('A synthetic unsupported verification claim.')
            quoted = answer.split(': ', 1)[1].split(' This is server-reported data;', 1)[0]
            decoded = json.loads(quoted)
            row = {'stage': label, 'limit': min(limit, 8192), 'quoted_utf8_bytes': len(quoted.encode('utf8')), 'within_budget': len(quoted.encode('utf8')) <= min(limit, 8192), 'valid_quoted_unicode': all((part in decoded for part in ('雪', '🧭', '\n"\\'))) and '�' not in decoded, 'canary_redacted': canary not in answer, 'verification_unchanged': result == snapshot, 'unverified_attribution': 'not independently verified' in answer, 'truncation_disclosed': 'truncated' in answer, 'actual_guarded_answer': answer}
            rows.append(row)
            if label == 'after':
                assert all((row[key] for key in ('within_budget', 'valid_quoted_unicode', 'canary_redacted', 'verification_unchanged', 'unverified_attribution', 'truncation_disclosed')))
            else:
                assert row['within_budget'] is False
    assert digest(input_path) == input_hash
    receipt = {'scope': 'Public original guard before/after replay; no model or tool dispatch', 'input_sha256': input_hash, 'rows': rows, 'actual_model_calls': 0, 'private_final_executed': False}
    target = destination / 'RECEIPT.json'
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return {'public_message_bound_controls': 4, 'before_budget_failures': 2, 'after_budget_passes': 2, 'receipt_sha256': digest(target), 'private_final_executed': False, 'new_generation_posts': 0}

def reproduce_facades():
    from scripts.campaign10_core.harness import environment, attach_dashboard_facades, original_session, NoInferenceClient
    from hanni.mcp.runtime import workflow_hub
    destination = PUBLIC / 'resume-original-facades-independent-cycle1'
    destination.mkdir(parents=True, exist_ok=False)
    with environment(destination / 'owned-state') as state:
        facade = attach_dashboard_facades(state)
        session = original_session(state, NoInferenceClient())
        row = {'scope': 'Original facade/controller attachment without command submission, sampling or inference', 'original_types': {'mcp': type(facade).__module__ + '.' + type(facade).__name__, 'workflow': type(state.workflow_facade).__module__ + '.' + type(state.workflow_facade).__name__, 'telemetry': type(state.controller_telemetry).__module__ + '.' + type(state.controller_telemetry).__name__}, 'session_metadata': deepcopy(state.session_metadata), 'workflow_items': state.workflow_facade.require().snapshot(), 'telemetry_started': state.controller_telemetry.worker is not None, 'denied_external_leaves': deepcopy(state.effects), 'model_calls': state.model_call_count, 'request_path_original': False, 'private_final_executed': False}
        assert state.workflow_facade.registry is state.registry and state.workflow_facade.runner_attached
        assert not row['workflow_items'] and (not row['telemetry_started']) and (not row['denied_external_leaves'])
        assert row['session_metadata']['workflow_resource_admission']['allowed'] is False
    row['cleanup'] = {'mcp_closed': facade.closed, 'workflow_closed': state.workflow_facade.closed, 'runtime_uninstalled': workflow_hub(state.config) is None, 'original_services_closed': state.cleanup['original_services_closed']}
    assert all(row['cleanup'].values())
    row['source_pins'] = {p: digest(ROOT / p) for p in ('scripts/campaign10_core/harness.py', 'src/hanni/dashboard/mcp_hub.py', 'src/hanni/dashboard/workflows.py', 'src/hanni/mcp/runtime.py', 'src/hanni/cli.py')}
    target = destination / 'RECEIPT.json'
    target.write_text(json.dumps(row, indent=2) + '\n', encoding='utf8')
    return {'public_original_facade_probe': True, 'receipt_sha256': digest(target), 'private_final_executed': False}
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shared', action='store_true')
    parser.add_argument('--shared-cycle', type=int, choices=[1, 2], default=1)
    parser.add_argument('--path-controls', action='store_true')
    parser.add_argument('--facades', action='store_true')
    parser.add_argument('--message-bounds', action='store_true')
    parser.add_argument('--mcp-stage', choices=['before', 'after', 'after-message'])
    args = parser.parse_args()
    if args.shared:
        print(json.dumps(reproduce_shared(args.shared_cycle)))
    if args.path_controls:
        print(json.dumps(reproduce_shared_path_controls()))
    if args.mcp_stage:
        print(json.dumps(replay_public_mcp_guard(args.mcp_stage)))
    if args.message_bounds:
        print(json.dumps(reproduce_message_bounds()))
    if args.facades:
        print(json.dumps(reproduce_facades()))
