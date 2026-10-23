"""Archive actual source and shipped UI before screen/indicator repairs."""
from pathlib import Path
import hashlib
import json
import zipfile
REPO = Path(__file__).resolve().parents[2]

def archive(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Never overwrite an earlier source checkpoint.')
    output.mkdir(parents=True)
    members = set((REPO / 'src').rglob('*.py'))
    members.update((p for p in (REPO / 'src/hanni/dashboard/static').glob('*') if p.is_file()))
    members.update((p for p in (REPO / 'frontend/src').rglob('*') if p.is_file()))
    members.update((p for p in (REPO / 'frontend/tests').rglob('*') if p.is_file()))
    members.update((REPO / p for p in ('frontend/package.json', 'frontend/package-lock.json', 'frontend/tsconfig.json', 'frontend/vite.config.ts', 'tests/helpers.py', 'tests/unit/test_desktop_features.py', 'tests/unit/test_desktop_voice.py', 'tests/unit/test_adaptive_model_routing.py')))
    members = sorted((p for p in members if p.is_file()))
    manifest = {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
    with zipfile.ZipFile(output / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in members:
            bundle.write(path, path.relative_to(REPO).as_posix())
    with zipfile.ZipFile(output / 'source.zip') as bundle:
        bundle.extractall(output / 'extracted')
    value = {'scope': 'Source, frontend, shipped static UI and applicable existing tests; no owner config/data.', 'files': manifest, 'zip_sha256': hashlib.sha256((output / 'source.zip').read_bytes()).hexdigest()}
    (output / 'manifest.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')
    return value
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = archive(args.output)
    print(json.dumps({'files': len(value['files']), 'zip_sha256': value['zip_sha256']}))
