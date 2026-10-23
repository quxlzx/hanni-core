"""Enumerate original routing contracts without tool or provider execution.

The persisted MCP inspection uses SQLite read-only mode and deliberately excludes
server configuration, credentials, connection approvals and audit arguments.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from hanni.config import load_config
from hanni.mcp.host import McpHost, classification, family_of
from hanni.tools.registry import build_default_registry

def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')

def inventory(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    config = load_config(root / 'config', data_dir=output / 'isolated-state', env={})
    registry = build_default_registry(config, data_dir=output / 'isolated-state')
    contracts = sorted((registry.capabilities.get(item.name) for item in registry.definitions()), key=lambda item: item['id'])
    payload = encode(contracts)
    (output / 'capabilities.json').write_bytes(payload)
    host = McpHost(registry, read_only=config.hanni.mcp.read_only, max_tools=config.hanni.mcp.max_tools_per_turn, allowed_actions=config.hanni.mcp.allowed_actions)
    routing = [{'id': item.name, 'wire_name': host._wire_name(item.name), 'routing_family': family_of(item.name), 'classification': classification(item), 'risk_level': item.risk_level, 'permission_level': item.permission_level, 'side_effect': item.side_effect, 'conditionally_confirmed': item.requires_confirmation_if is not None, 'eligible_by_host_policy': host._allowed(item), 'model_schema_without_request_specific_fixed_arguments': host._as_tool(item).openai_schema()} for item in sorted(registry.definitions(), key=lambda item: item.name)]
    (output / 'routing-catalog.json').write_bytes(encode(routing))
    store = root / 'data' / 'mcp' / 'hub.sqlite3'
    persisted = []
    if store.is_file():
        with sqlite3.connect(store.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            for row in connection.execute('SELECT payload FROM servers ORDER BY id'):
                server = json.loads(row[0])
                persisted.append({'server_id': server.get('id'), 'enabled': server.get('enabled'), 'persisted_state': server.get('state'), 'tools': [{key: tool.get(key) for key in ('internal_id', 'original_name', 'description', 'input_schema', 'classification', 'enabled', 'valid', 'available', 'definition_hash')} for tool in server.get('tools', [])]})
    summary = {'baseline': '227a628', 'enumerated_at_utc': datetime.now(timezone.utc).isoformat(), 'registered_count': len(contracts), 'host_policy_eligible_count': sum((item['eligible_by_host_policy'] for item in routing)), 'routing_family_counts': dict(sorted(Counter((item['routing_family'] for item in routing)).items())), 'families': dict(sorted(Counter((item['family'] for item in contracts)).items())), 'contract_sha256': hashlib.sha256(payload).hexdigest(), 'core_scope': 'Current-source default registry; isolated stores; no handlers invoked', 'persisted_mcp_store_present': store.is_file(), 'persisted_mcp_server_count': len(persisted), 'persisted_mcp_tool_count': sum((len(server['tools']) for server in persisted)), 'runtime_scope': 'Persisted discovery only; no connections or runtime services started. Persisted availability is not proof of current process registration.', 'read_only': config.hanni.mcp.read_only, 'allowed_actions': list(config.hanni.mcp.allowed_actions), 'menu_k': config.hanni.mcp.max_tools_per_turn, 'max_rounds': config.hanni.mcp.max_tool_rounds}
    (output / 'persisted-mcp-metadata.json').write_bytes(encode(persisted))
    (output / 'summary.json').write_bytes(encode(summary))
    return summary
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inventory(args.root.resolve(), args.output.resolve()), sort_keys=True))
