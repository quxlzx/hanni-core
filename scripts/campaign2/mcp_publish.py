"""Publish compact derived MCP evidence, preserving raw receipts privately."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def passed(row):
    return row['phases'].get('call') == 'passed' and 'failed' not in row['phases'].values()
DIMENSIONS = {'valid_arguments': 'test_valid_original_registry_call_and_structured_output', 'invalid_arguments': 'test_invalid_arguments_never_reach_sdk', 'missing_arguments': 'test_required_arguments_never_reach_sdk', 'permission_denial': 'test_original_permission_profile_and_confirmation', 'dependency_absent': 'test_missing_connection_withdraws_live_and_cached_execution', 'output_contract': 'test_invalid_advertised_output_never_reports_success', 'nl_retrieval_policy': 'test_natural_language_original_menu_preserves_policy', 'original_host_e2e_policy': 'test_original_host_end_to_end_allowed_reads_and_denied_mutations'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--cleanup', type=Path, required=True)
    parser.add_argument('--owner-inventory', type=Path, required=True)
    parser.add_argument('--demo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    results = read(args.run / 'results.json')
    inventory = read(args.run / 'inventory.json')
    cleanup = read(args.cleanup)
    owner = read(args.owner_inventory)
    demo = read(args.demo)
    transcripts = []
    definition_hashes = {}
    for path in sorted((args.run / 'transport_receipts').glob('*.json')):
        receipt = read(path)
        transcripts.append({'name': path.name, 'sha256': digest(path), 'label': receipt['label'], 'transport': receipt['transport'], 'initialization': receipt['initialization'], 'observed_registry_base_count': receipt['base_count'], 'actual_sdk_calls': sum((event['event'] == 'call' for event in receipt['events']))})
        for server in receipt['snapshot']['servers']:
            for tool in server['tools']:
                definition_hashes.setdefault(tool['original_name'], set()).add(tool['definition_hash'])
    by_id = {row['nodeid']: row for row in results['tests']}
    per_tool = []
    for item in inventory['tools']:
        name = item['definition']['name']
        dimensions = {}
        for dimension, test in DIMENSIONS.items():
            checks = []
            for transport in ('stdio', 'streamable_http'):
                identity = f'tests/integration/test_campaign2_mcp_matrix.py::{test}[{transport}-{name}]'
                row = by_id[identity]
                checks.append({'transport': transport, 'nodeid': identity, 'status': 'pass' if passed(row) else 'fail'})
            dimensions[dimension] = {'checks': checks, 'status': 'pass' if all((row['status'] == 'pass' for row in checks)) else 'fail'}
        model = {'status': 'not_tested', 'reason': 'The transport audit performs no resident-model inference.'}
        if name == demo['original_name']:
            model = {'status': demo['status'], 'actual_model_http_requests': demo['actual_model_http_requests'], 'reason': demo.get('reason'), 'error': demo.get('error'), 'scope': 'Original guarded model-selection attempt; separate registry call is not model selection.'}
        per_tool.append({'original_name': name, 'owner_classification': item['owner_classification'], 'source_contract': item['definition'], 'actual_discovered_definition_hashes': sorted(definition_hashes.get(name, set())), 'dimensions': dimensions, 'actual_model_selection': model})
    public = {'schema_version': 1, 'campaign': 2, 'generated_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Actual isolated local SDK stdio/Streamable HTTP with controlled data; external-provider and model proof kept separate', 'sdk_version': results['sdk_version'], 'observed_original_registry_counts': inventory['observed_builtin_counts'], 'imported_fixture_tool_count': len(per_tool), 'tests': {'total': len(results['tests']), 'passed': sum((passed(row) for row in results['tests'])), 'failed': sum(('failed' in row['phases'].values() for row in results['tests'])), 'duration_seconds': results['duration_seconds'], 'matrix_cases': sum(('test_campaign2_mcp_matrix.py::' in row['nodeid'] for row in results['tests'])), 'lifecycle_cases': sum(('test_campaign2_mcp_lifecycle.py::' in row['nodeid'] for row in results['tests']))}, 'owner_mcp_inventory': {'server_count': len(owner['owner_mcp_servers']), 'enabled_tool_count': len(owner['owner_enabled_mcp_tools']), 'scope': owner['owner_mcp_scope'], 'source_sha256': digest(args.owner_inventory)}, 'per_tool': per_tool, 'source_unchanged': results['source_unchanged'], 'model_result_caution': 'Metadata retrieval passes are not model reasoning. Guarded unknown-tool model selection was blocked; no model-selection pass is inferred.', 'live_external_provider_result': 'not_tested'}
    trace = {'schema_version': 1, 'campaign': 2, 'run': 'verified-03', 'raw_results_sha256': digest(args.run / 'results.json'), 'raw_inventory_sha256': digest(args.run / 'inventory.json'), 'junit_sha256': digest(args.run / 'tests.xml'), 'source_hashes_before': results['source_hashes_before'], 'source_hashes_after': results['source_hashes_after'], 'test_receipts': [{'nodeid': row['nodeid'], 'phases': row['phases'], 'duration_seconds': row['duration_seconds']} for row in results['tests']], 'transport_receipts': transcripts, 'cleanup': {'source_sha256': digest(args.cleanup), 'scope': cleanup['scope'], 'all_cleanup_checks_passed': cleanup['all_cleanup_checks_passed'], 'rows': cleanup['rows']}, 'unknown_tool_demo': {'source_sha256': digest(args.demo), 'query': demo['query'], 'original_name': demo['original_name'], 'discovered_by_actual_sdk': demo['discovered_by_actual_sdk'], 'model_retraining_performed': demo['model_retraining_performed'], 'model_selection_status': demo['status'], 'actual_model_http_requests': demo['actual_model_http_requests'], 'resource_before': demo['resource_before'], 'separate_declared_argument_call': demo['separate_original_registry_call']}, 'boundaries': {'physical_external_provider': 'not_tested', 'model_selection': 'blocked', 'tool_response_independent_environment_verification': False, 'owner_services_mutated': 'not attempted; only proven test-owned process handles are controlled'}}
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in [('MCP_SCORECARD.json', public), ('MCP_EVIDENCE.json', trace)]:
        (args.out / name).write_text(json.dumps(value, indent=2), encoding='utf8')
    print(json.dumps({'tools': len(per_tool), 'tests': public['tests'], 'transport_receipts': len(transcripts), 'actual_model_selection': demo['status']}))
if __name__ == '__main__':
    main()
