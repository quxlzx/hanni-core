"""Fixed synthetic discovery metadata through original MCP approval controls."""
import hashlib
import json
from pathlib import Path
from .inert_mcp import TOOL, TOOL_NAME
from .plan import validate_input
from .supplement import button, select

def cases():
    inputs, oracles = ([], [])
    reset = [{'action': 'click', 'selector': '.mcp-server-row', 'index': 0}, {'action': 'click', 'selector': '.mcp-tool-row button', 'index': 0}]
    specs = [('inspect-schemas', reset + [{'action': 'click', 'selector': '.mcp-tool-inspector details summary', 'index': i} for i in range(4)] + [select('Permission classification', 'read_only'), button('Approve & enable'), button('Cancel')], {'fixed_original_schema_metadata_identity_visible': True, 'draft_classification': 'read_only', 'approval_cancelled': True, 'tool_enabled': False, 'tool_approval': None}), ('approve-disable', reset + [select('Permission classification', 'read_only'), button('Approve & enable'), button('Approve tools', settle_ms=800), button('Disable tool', settle_ms=800)], {'original_matching_definition_hash_approval': True, 'approved_classification': 'read_only', 'actual_enabled_then_disabled': True, 'final_tool_enabled': False}), ('bulk-approval-disable', reset + [{'action': 'click', 'role': 'checkbox', 'name': 'Select ' + TOOL_NAME}, select('Tool permission classification', 'read_only'), button('Approve selected'), button('Approve tools', settle_ms=800), {'action': 'click', 'role': 'checkbox', 'name': 'Select ' + TOOL_NAME}, button('Disable selected', settle_ms=800)], {'actual_bulk_matching_hash_approval_then_disable': True, 'final_tool_enabled': False, 'original_registration_removed': True}), ('close-inspector', reset + [button('Close tool inspector')], {'actual_inspector_closed': True, 'persisted_tool_unchanged': True})]
    for key, steps, checks in specs:
        identifier = 'mcp-tool-controls-' + key
        row = {'id': identifier, 'route': 'mcp', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-mcp-tool-controls', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': ['/api/mcp']}
        validate_input(row)
        inputs.append(row)
        oracles.append({'id': identifier, 'check': checks, 'scope': 'CONTROLLED_MOCK discovery metadata only; original manager/config hash/definition approval/registry synchronization and native UI. Every invocation refused; no external/provider/tool execution.'})
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Keep all prospective versions and original results.')
    output.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'fixed_synthetic_metadata': TOOL, 'execution_attempted': False, 'generation_authorized': False, 'tool_invocation_authorized': False, 'process_network_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
