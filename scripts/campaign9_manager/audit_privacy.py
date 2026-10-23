"""Original audit sink readback with disposable notes and an inert shell leaf."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts.campaign8_ui.backend import original_backend
PRIVATE_TEXT = 'C9 synthetic private discussion about project prism release priorities'
CANARY = 'C9_SYNTHETIC_AUDIT_METADATA_327491'

def probe(backend):
    from hanni.tools.base import ToolRequest
    rows = []
    for name, arguments in [('note.append', {'text': PRIVATE_TEXT}), ('note.list', {}), ('note.search', {'query': 'project prism'})]:
        result = backend.registry.execute(ToolRequest(name, arguments))
        row = backend.registry.context.audit.tail(1)[0]
        raw = json.dumps(row, ensure_ascii=False)
        rows.append({'id': name, 'original_result_ok': result.ok is True, 'private_body_in_arguments_or_message': PRIVATE_TEXT in raw or 'project prism' in json.dumps(row['arguments']), 'audit_row_sha256': hashlib.sha256(raw.encode()).hexdigest()})
    command = "Write-Output '" + PRIVATE_TEXT + "'"
    with patch('hanni.tools.powershell.subprocess.run', return_value=subprocess.CompletedProcess(['owned-inert-fixture'], 0, stdout=PRIVATE_TEXT, stderr='')) as leaf:
        result = backend.registry.execute(ToolRequest('powershell.run', {'command': command}, confirmed=True))
    row = backend.registry.context.audit.tail(1)[0]
    raw = json.dumps(row, ensure_ascii=False)
    rows.append({'id': 'powershell.run', 'original_result_ok': result.ok is True, 'private_body_in_arguments_or_message': PRIVATE_TEXT in raw, 'mocked_leaf_entries': leaf.call_count, 'real_shell_processes': 0, 'audit_row_sha256': hashlib.sha256(raw.encode()).hexdigest()})
    from hanni.logs.redaction import register_secret, clear_registry
    register_secret('C9_SYNTHETIC_AUDIT_ONLY', CANARY)
    try:
        target = backend.root / 'synthetic-metadata.txt'
        target.write_text('Disposable ordinary metadata fixture.', encoding='utf-8')
        backend.registry.execute(ToolRequest('file.stat', {'path': str(target)}, correlation_id=CANARY))
        raw = backend.registry.context.audit.path.read_text(encoding='utf-8')
        rows.append({'id': 'audit_correlation_metadata', 'registered_canary_in_audit': CANARY in raw})
    finally:
        clear_registry()
    return rows

def historical_projection(backend):
    from hanni.dashboard.gateway import activity_snapshot
    path = backend.registry.context.audit.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'tool': 'note.search', 'arguments': {'query': PRIVATE_TEXT}, 'message': PRIVATE_TEXT, 'error': PRIVATE_TEXT, 'ok': False, 'duration_ms': 1, 'source': 'controlled-owned'}) + '\n', encoding='utf-8')
    wire = json.dumps(activity_snapshot(backend.root), ensure_ascii=False)
    return {'id': 'historical_activity_projection', 'private_body_in_arguments_or_message': PRIVATE_TEXT in wire, 'projection_sha256': hashlib.sha256(wire.encode()).hexdigest()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError('Preserve original observations; refusing overwrite.')
    with TemporaryDirectory(prefix='hanni-c9-audit-') as temp:
        with original_backend(Path(temp) / 'runtime') as backend:
            try:
                before = hashlib.sha256(Path('src/hanni/tools/audit.py').read_bytes()).hexdigest()
                rows = probe(backend)
                rows.append(historical_projection(backend))
                after = hashlib.sha256(Path('src/hanni/tools/audit.py').read_bytes()).hexdigest()
                assert before == after
            finally:
                from hanni.reliability.execution import close_service
                close_service(backend.root)
        result = {'evidence_class': 'CONTROLLED original audit and disposable original notes; shell leaf explicitly mocked', 'cases': rows, 'audit_source_sha256': before, 'source_unchanged': True, 'owned_backend_closed': backend.closed and (not backend.thread.is_alive()), 'real_credentials': False, 'owner_stores_mounted': False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(rows), 'privacy_reflections': sum((x.get('private_body_in_arguments_or_message', x.get('registered_canary_in_audit', False)) for x in rows)), 'owned_backend_closed': result['owned_backend_closed']}))
if __name__ == '__main__':
    main()
