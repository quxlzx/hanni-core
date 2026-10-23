"""Security-relevant source routes plus bounded read-only owner capability metadata."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
from scripts.campaign8_manager.preflight import runtime
from .api_security import private_routes
ROOT = Path(__file__).resolve().parents[2]

def main():
    out = ROOT / 'data/campaign9-manager/INVENTORY.json'
    if out.exists():
        raise RuntimeError('Preserve the original inventory; refusing overwrite.')
    baseline = json.loads((out.parent / 'PREFLIGHT.json').read_text(encoding='utf-8'))
    before = runtime()
    if before['ports'] != baseline['runtime']['ports'] or before['processes'] != baseline['runtime']['processes']:
        raise RuntimeError('Existing service identity changed; do not query a replacement.')
    path = ROOT / 'src/hanni/dashboard/server.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    post = next((node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'do_POST'))
    routes = set()
    for node in ast.walk(post):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith('/api/'):
            routes.add(node.value)
    connection = http.client.HTTPConnection('127.0.0.1', 8765, timeout=5)
    try:
        connection.request('GET', '/api/workspace')
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError('Authoritative owner capability metadata unavailable.')
        workspace = json.loads(response.read())
    finally:
        connection.close()
    capabilities = [{k: row.get(k) for k in ('name', 'permission_level', 'risk_level')} for row in workspace.get('capabilities', [])]
    after = runtime()
    assert before['ports'] == after['ports'] and before['processes'] == after['processes']
    result = {'at': datetime.now(timezone.utc).isoformat(), 'source_private_exact_GET_routes': list(private_routes()), 'source_private_GET_prefixes': ['/api/workflows/', '/api/memory/', '/api/model-lab/'], 'source_POST_routes': sorted(routes), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'live_read_only_owner_capabilities': capabilities, 'live_capability_count': len(capabilities), 'live_read_only_owner_capability_revision': workspace.get('capability_revision'), 'owner_interval_identities_unchanged': True, 'owner_mutations': 0, 'scope': 'Read-only runtime names/levels, not handler/provider success or all concrete runtime states', 'local_trust_limit': 'Loopback Host/Origin/fetch-site/token gates resist browser-origin misuse; public chat bootstraps token/history for same-origin UI. No separate OS-user/process sandbox or user login is implemented.'}
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'inventory': out.relative_to(ROOT).as_posix(), 'live_capabilities': len(capabilities), 'private_exact_GET': len(private_routes()), 'POST_routes': len(routes), 'owner_interval_identities_unchanged': True}))
if __name__ == '__main__':
    main()
