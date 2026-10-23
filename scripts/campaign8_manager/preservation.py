"""Compare original source, protected evidence and owner process identities."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from .preflight import ROOT, digest, runtime

def main():
    initial = json.loads((ROOT / 'data/campaign8-manager/PREFLIGHT.json').read_text(encoding='utf8'))
    current = runtime()
    changed, missing = ([], [])
    for name, original in initial['source_manifest'].items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif digest(path) != original:
            changed.append(name)
    allowed = lambda name: name == 'src/hanni/dashboard/server.py' or name.startswith(('frontend/src/', 'src/hanni/dashboard/static/', 'scripts/campaign8_', 'tests/integration/test_campaign8'))
    protected = {name: 'UNCHANGED' if (ROOT / name).is_file() and digest(ROOT / name) == old else 'CHANGED_OR_MISSING' for name, old in initial['protected'].items()}
    native = ROOT / initial['native_artifact']['path']
    result = {'at': datetime.now(timezone.utc).isoformat(), 'original_source_count': len(initial['source_manifest']), 'approved_frontend_or_qa_changes': [name for name in changed if allowed(name)], 'unrelated_changed_originals': [name for name in changed if not allowed(name)], 'missing_originals': missing, 'protected_file_count': len(protected), 'protected_files': protected, 'native_executable_unchanged': digest(native) == initial['native_artifact']['sha256'], 'owner_ports_unchanged': initial['runtime']['ports'] == current['ports'], 'owner_process_identities_unchanged': initial['runtime']['processes'] == current['processes'], 'runtime_after': current, 'owner_memory_database_byte_comparison': 'NOT_MEASURED: no initial database byte hash was collected; disposable fixtures did not mount owner stores'}
    result['pass'] = all((not result['unrelated_changed_originals'], not missing, all((value == 'UNCHANGED' for value in protected.values())), result['native_executable_unchanged'], result['owner_ports_unchanged'], result['owner_process_identities_unchanged'], not current['native_clients']))
    out = ROOT / 'docs/campaign8/PRESERVATION.json'
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key not in {'protected_files', 'runtime_after'}}))
if __name__ == '__main__':
    main()
