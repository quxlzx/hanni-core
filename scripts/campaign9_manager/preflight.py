"""Archive current source and hash protected evidence without reading owner stores."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile
from scripts.campaign8_manager.preflight import digest, runtime
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign9-manager'

def eligible(path: Path) -> bool:
    name = path.relative_to(ROOT).as_posix()
    return path.is_file() and (not any((part in {'__pycache__', 'node_modules', '.pytest_cache'} for part in path.parts))) and (path.suffix not in {'.pyc', '.log'}) and ('campaign9' not in name)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'original-source.zip'
    if archive.exists():
        raise RuntimeError('Campaign 9 baseline already exists; refusing overwrite.')
    files = set()
    for directory in ('src', 'frontend/src', 'frontend/public', 'frontend/tests', 'desktop', 'config', 'tests', 'scripts', 'evals'):
        files.update((path for path in (ROOT / directory).rglob('*') if eligible(path)))
    for name in ('.gitattributes', '.gitignore', 'pyproject.toml', 'START_HANNI.cmd', 'START_HANNI_OS.cmd'):
        path = ROOT / name
        if path.is_file():
            files.add(path)
    files.update((path for path in (ROOT / 'frontend').glob('*') if path.is_file()))
    manifest = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(files)}
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(files):
            bundle.write(path, path.relative_to(ROOT))
    protected = {}
    for number in range(1, 9):
        for path in (ROOT / f'docs/campaign{number}').rglob('*'):
            if path.is_file():
                protected[path.relative_to(ROOT).as_posix()] = digest(path)
    for directory in (ROOT / 'data').glob('campaign*'):
        if directory.is_dir() and (not directory.name.startswith('campaign9')) and ('verifier' not in directory.name):
            for path in directory.rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    protected[path.relative_to(ROOT).as_posix()] = digest(path)
    for name in ('CALENDAR_FUTURE_DATE_ROOT_CAUSE.md', 'HANNI_LAYA_SHADOW_PATCH_20261009.zip', 'MODEL_BAKEOFF_FINAL.json', 'MODEL_BAKEOFF_FINAL.md', 'MODEL_PERSONALITY_BLIND.md', 'data/compute/deployment.json', 'data/compute/context-measurements.json'):
        path = ROOT / name
        if path.is_file():
            protected[name] = digest(path)
    artifact = ROOT / 'dist/HANNI OS/HANNI OS.exe'
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'source_manifest': manifest, 'archive_sha256': digest(archive), 'protected': protected, 'native_artifact': {'path': artifact.relative_to(ROOT).as_posix(), 'sha256': digest(artifact)}, 'runtime': runtime(), 'owner_databases_mounted': False, 'owner_database_byte_comparison': 'NOT_MEASURED; no owner database read or mount', 'private_holdout_inputs_or_answers_inspected': False}
    (OUT / 'PREFLIGHT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source_files': len(manifest), 'protected_files': len(protected), 'archive_sha256': receipt['archive_sha256'], 'runtime': receipt['runtime']}))
if __name__ == '__main__':
    main()
