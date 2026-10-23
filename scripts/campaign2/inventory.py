"""Dynamic, non-executing registry inventory and read-only owner MCP inspection."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost, classification
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

def capture(registry, config):
    host = McpHost(registry, read_only=config.hanni.mcp.read_only, allowed_actions=config.hanni.mcp.allowed_actions, max_tools=config.hanni.mcp.max_tools_per_turn)
    tools = []
    for definition in sorted(registry.definitions(), key=lambda item: item.name):
        contract = registry.capabilities.get(definition.name)
        module = definition.handler.__module__
        module_file = ROOT / 'src' / Path(*module.split('.')).with_suffix('.py')
        tools.append({'id': definition.name, 'contract': contract, 'definition_hash': digest(contract), 'handler_module': module, 'handler_sha256': hashlib.sha256(module_file.read_bytes()).hexdigest() if module_file.is_file() else None, 'classification': classification(definition), 'host_eligible': host._allowed(definition)})
    store = ROOT / 'data/mcp/hub.sqlite3'
    servers = []
    if store.is_file():
        with sqlite3.connect(store.resolve().as_uri() + '?mode=ro', uri=True) as db:
            for payload, in db.execute('SELECT payload FROM servers ORDER BY id'):
                server = json.loads(payload)
                servers.append({'id': server['id'], 'enabled': server.get('enabled', False), 'state': server.get('state'), 'tools': [{key: tool.get(key) for key in ('internal_id', 'original_name', 'description', 'input_schema', 'output_schema', 'classification', 'enabled', 'valid', 'available', 'definition_hash')} for tool in server.get('tools', [])]})
    enabled = [tool for server in servers if server['enabled'] for tool in server['tools'] if tool['enabled']]
    try:
        revision = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=False)
        baseline = revision.stdout.strip() if revision.returncode == 0 else None
    except OSError:
        baseline = None
    return {'baseline': baseline, 'baseline_scope': 'git_revision' if baseline else 'source_archive; Git revision unavailable', 'captured_at': datetime.now(timezone.utc).isoformat(), 'builtins': tools, 'builtin_count': len(tools), 'inventory_sha256': digest(tools), 'owner_mcp_store_present': store.is_file(), 'owner_mcp_servers': servers, 'owner_enabled_mcp_tools': enabled, 'owner_enabled_mcp_tool_count': len(enabled), 'owner_mcp_scope': 'Read-only persisted discovery; availability is not proof of live registration.'}
