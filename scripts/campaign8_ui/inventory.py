"""Publish dynamic original route/control templates and authority dependencies."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import subprocess
REPO = Path(__file__).resolve().parents[2]

def inventory():
    result = subprocess.run(['node', str(Path(__file__).with_name('inventory.cjs'))], cwd=REPO, text=True, capture_output=True, timeout=30, check=True)
    value = json.loads(result.stdout)
    server = REPO / 'src/hanni/dashboard/server.py'
    tree = ast.parse(server.read_text(encoding='utf8'))
    private = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any((isinstance(t, ast.Name) and t.id == 'private_routes' for t in node.targets)):
            private.update(ast.literal_eval(node.value))
    value['authority'] = {'private_exact_get_routes': sorted(private), 'private_get_prefixes': ['/api/workflows/', '/api/memory/', '/api/model-lab/'], 'post': 'Original Host/Origin/Sec-Fetch-Site/session token + route-specific schema, permission, confirmation and shutdown gates.', 'get_side_effects': {'/api/calendar': 'Reads account metadata; explicit refresh=1 may perform authorized provider read and cache write.', '/api/notifications': 'Ingests generated notifications in the original local store.', '/api/cluster': 'Starts original cluster/power monitor threads.', '/api/compute': 'Starts original compute monitor; refresh=1 requests health refresh.', '/api/model-lab': 'Starts original routing monitor; refresh=1 requests health refresh.', '/api/memory/*': 'Original memory/project stores may initialize in the configured data directory.'}, 'sensitive_controls': ['Node power', 'SSH terminal', 'Inference/model start or stop', 'Microphone and speech control', 'Audio/GPU route configuration', 'External MCP connection/tool execution', 'Calendar provider refresh', 'Clipboard export', 'Global shortcut registration', 'Owner shutdown'], 'owner_mode': 'No writes or personal-store projections; actual campaign native sessions use disposable original backend.'}
    for module in value['modules']:
        for control in module['controls']:
            direct = [api for api in module['api_dependencies'] if api['component'] == control['component']]
            control['source_api_candidates'] = direct or module['api_dependencies']
            control['authority'] = {'status': 'UNVERIFIED_SOURCE_CANDIDATES', 'writes': 'Original write/request POST calls require same-origin session token plus route-specific original gates.', 'local': 'Local state/dialog/filter/navigation handlers confer no backend execution authority.', 'native': 'Owned Mini/OS bridge controls require verified process/window identity; physical/global behavior not proved by CDP.', 'evidence_required': 'Native action or documented dependency block; source candidates alone never grant PASS.'}
    paths = [server, *(REPO / 'frontend/src').glob('*')]
    value['source_hashes'] = {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()}
    value['counts'] = {'declared_routes': len(value['routes']), 'static_interactive_slots': sum((len(m['controls']) for m in value['modules'])), 'native_observed_controls': None, 'native_passes': None}
    return value

def publish(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Do not overwrite an earlier inventory checkpoint.')
    output.mkdir(parents=True)
    value = inventory()
    (output / 'inventory.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')
    return value
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = publish(args.output)
    print(json.dumps(value['counts']))
