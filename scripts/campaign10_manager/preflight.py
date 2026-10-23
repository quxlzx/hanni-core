"""Archive source and public prior evidence without inspecting private holdouts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile
from scripts.campaign8_manager.preflight import digest, runtime
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign10-manager'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'original-source.zip'
    if archive.exists():
        raise FileExistsError('Preserve the original C10 baseline.')
    files = set()
    for directory in ('src', 'frontend/src', 'frontend/public', 'frontend/tests', 'desktop', 'config', 'tests', 'scripts', 'evals'):
        files.update((p for p in (ROOT / directory).rglob('*') if p.is_file() and (not any((x in {'__pycache__', 'node_modules', '.pytest_cache'} for x in p.parts))) and (p.suffix not in {'.pyc', '.log'}) and ('campaign10' not in p.relative_to(ROOT).as_posix())))
    files.update((p for p in (ROOT / 'frontend').glob('*') if p.is_file()))
    for name in ('.gitattributes', '.gitignore', 'pyproject.toml', 'START_HANNI.cmd', 'START_HANNI_OS.cmd'):
        if (ROOT / name).is_file():
            files.add(ROOT / name)
    manifest = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(files)}
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for p in sorted(files):
            bundle.write(p, p.relative_to(ROOT))
    protected = {}
    for n in range(1, 10):
        for p in (ROOT / f'docs/campaign{n}').rglob('*'):
            if p.is_file():
                protected[p.relative_to(ROOT).as_posix()] = digest(p)
    for directory in (ROOT / 'data').glob('campaign*'):
        if directory.is_dir() and 'verifier' not in directory.name and (not directory.name.startswith('campaign10')):
            for p in directory.rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:
                    protected[p.relative_to(ROOT).as_posix()] = digest(p)
    for name in ('data/compute/deployment.json', 'data/compute/context-measurements.json', 'CALENDAR_FUTURE_DATE_ROOT_CAUSE.md', 'HANNI_LAYA_SHADOW_PATCH_20261009.zip', 'MODEL_BAKEOFF_FINAL.json', 'MODEL_BAKEOFF_FINAL.md', 'MODEL_PERSONALITY_BLIND.md'):
        if (ROOT / name).is_file():
            protected[name] = digest(ROOT / name)
    native = ROOT / 'dist/HANNI OS/HANNI OS.exe'
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'source_manifest': manifest, 'archive_sha256': digest(archive), 'protected': protected, 'runtime': runtime(), 'native_artifact': {'path': native.relative_to(ROOT).as_posix(), 'sha256': digest(native)}, 'owner_databases_mounted': False, 'private_holdout_inspected': False}
    (OUT / 'PREFLIGHT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'source_files': len(manifest), 'protected_files': len(protected), 'archive_sha256': receipt['archive_sha256'], 'runtime': receipt['runtime']}))
if __name__ == '__main__':
    main()
