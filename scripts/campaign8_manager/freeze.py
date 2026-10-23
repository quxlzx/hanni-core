"""Seal reviewable source bytes before the independent once-only native final."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile
from .preflight import ROOT, digest, runtime

def sources(extra=()):
    files = set()
    for name in ('src', 'frontend/src', 'frontend/public', 'desktop', 'config', 'evals', 'tests', 'scripts'):
        for path in (ROOT / name).rglob('*'):
            if path.is_file() and (not any((part in {'__pycache__', 'node_modules', '.pytest_cache'} for part in path.parts))):
                if path.suffix not in {'.pyc', '.log'}:
                    files.add(path)
    files.update((path for path in (ROOT / 'frontend').glob('*') if path.is_file()))
    for name in ('.gitattributes', 'pyproject.toml', 'START_HANNI.cmd', 'START_HANNI_OS.cmd', 'dist/HANNI OS/HANNI OS.exe', 'docs/campaign8/REQUEST.md', 'docs/campaign8/PROTOCOL.md', 'docs/campaign8/VISUAL_RUBRIC.md', 'docs/campaign8/FINAL_ADAPTER.md', 'docs/campaign8/FINAL_SEAL.json'):
        path = ROOT / name
        if path.is_file():
            files.add(path)
    for name in extra:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or path.is_relative_to(ROOT / 'data/campaign8-verifier'):
            raise ValueError('Only explicit public development inputs outside verifier-private data may be added')
        if not path.is_file():
            raise ValueError('Extra immutable source must name a file')
        files.add(path)
    return sorted(files)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--extra', action='append', default=[])
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'data/campaign8-manager') or out.exists():
        raise ValueError('A fresh campaign-manager directory is required')
    files = sources(args.extra)
    manifest = {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
    before = runtime()
    if before['native_clients']:
        raise RuntimeError('Close the owned native executor before sealing source')
    out.mkdir(parents=True)
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8', newline='\n')
    archive = out / 'SOURCE.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(ROOT).as_posix())
    changed = [name for name, expected in manifest.items() if digest(ROOT / name) != expected]
    if changed:
        raise RuntimeError('Sources changed while sealing; retain failed archive: ' + ', '.join(changed[:5]))
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'source_member_count': len(manifest), 'manifest_sha256': digest(out / 'MANIFEST.json'), 'archive_sha256': digest(archive), 'runtime': before, 'private_inputs_or_answers_read': False, 'mutable_reports_excluded': True, 'sources_unchanged_after_archive': True}
    (out / 'RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: value for key, value in receipt.items() if key != 'runtime'}))
if __name__ == '__main__':
    main()
