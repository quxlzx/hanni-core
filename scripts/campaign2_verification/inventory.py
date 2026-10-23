"""Fresh independent original-contract inventory without executing handlers."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sqlite3
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from scripts.campaign2_verification.scorecard import digest

def capture(root, state):
    config = load_config(root / 'config', data_dir=state, env={})
    registry = build_default_registry(config, data_dir=state)
    tools = []
    schema_problems = []
    from jsonschema.validators import validator_for
    for definition in registry.definitions():
        contract = registry.capabilities.get(definition.name)
        handler = definition.handler
        source = Path(inspect.getsourcefile(handler) or importlib.import_module(handler.__module__).__file__)
        schema = definition.argument_schema()
        try:
            validator_for(schema).check_schema(schema)
        except Exception as exc:
            schema_problems.append({'id': definition.name, 'type': type(exc).__name__})
        tools.append({'id': definition.name, 'contract': contract, 'definition_hash': digest(contract), 'handler_module': handler.__module__, 'handler_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'handler_qualname': handler.__qualname__, 'handler_source_path': str(source.resolve()), 'dynamic_confirmation': definition.requires_confirmation_if is not None})
    tools.sort(key=lambda item: item['id'])
    from hanni.mcp.host import McpHost, classification
    host = McpHost(registry, read_only=config.hanni.mcp.read_only, allowed_actions=config.hanni.mcp.allowed_actions, max_tools=config.hanni.mcp.max_tools_per_turn)
    manager_projection = []
    for tool in tools:
        definition = registry.get(tool['id'])
        manager_projection.append({key: tool[key] for key in ('id', 'contract', 'definition_hash', 'handler_module', 'handler_sha256')} | {'classification': classification(definition), 'host_eligible': host._allowed(definition)})
    enabled = []
    store = root / 'data/mcp/hub.sqlite3'
    server_count = 0
    if store.is_file():
        with sqlite3.connect(store.resolve().as_uri() + '?mode=ro', uri=True) as database:
            for payload, in database.execute('SELECT payload FROM servers ORDER BY id'):
                server = json.loads(payload)
                server_count += 1
                if server.get('enabled'):
                    for tool in server.get('tools', []):
                        if tool.get('enabled'):
                            enabled.append({key: tool.get(key) for key in ('internal_id', 'definition_hash', 'classification', 'enabled', 'valid', 'available')})
    return {'scope': 'Fresh original default registry, isolated state; no handler or owner MCP connection invoked.', 'builtins': tools, 'builtin_count': len(tools), 'inventory_sha256': digest(manager_projection), 'owner_mcp_servers_observed': server_count, 'owner_enabled_mcp_tools': enabled, 'schema_problems': schema_problems, 'handler_module_counts': dict(Counter((t['handler_module'] for t in tools)))}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = capture(args.root.resolve(), args.output.resolve() / 'isolated-state')
    (args.output / 'inventory.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: value for key, value in result.items() if key != 'builtins'}))
if __name__ == '__main__':
    main()
