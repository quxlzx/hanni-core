"""Pin Campaign 6 source/public inputs; never inspect private final scenarios."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import zipfile
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.campaign5_manager import freeze as checker
HOLDOUT_SEAL = {'cases': 22, 'sealed_at': '2026-10-10T10:33:52.226124+00:00', 'inputs_sha256': '77672a471be52e1dadc7e4d8593856f569dd9cc594c6921bf24ed7d9e73dd18e', 'oracles_sha256': 'bfb1f432a4833b9d3a27508e2a5aa812c39d4d021fc18f50d1fce94900ad4fc2', 'protocol_sha256': '96e71356ac1c48ba6acf6c62df50148f2e425fe8349d4bee7abb46582412f23c', 'source': 'Independent verifier announcement; no private input or oracle opened by manager.'}

def paths():
    selected = {*ROOT.joinpath('src/hanni').rglob('*.py'), *ROOT.joinpath('config').rglob('*.yaml'), *ROOT.joinpath('tests').rglob('*.py'), ROOT / '.gitattributes', ROOT / 'pyproject.toml', ROOT / 'docs/campaign6/PROTOCOL.md'}
    for pattern in ('campaign4*', 'campaign5*', 'campaign6*'):
        for folder in ROOT.joinpath('scripts').glob(pattern):
            if folder.is_dir():
                selected.update(folder.rglob('*.py'))
    selected.add(ROOT / 'scripts/campaign3_manager/model_probe.py')
    for directory, pattern in (('evals/workflows', 'campaign4*.json'), ('evals/models', 'campaign5*.json'), ('evals/compute', 'campaign6*.json')):
        selected.update(ROOT.joinpath(directory).glob(pattern))
    return sorted((p for p in selected if p.is_file()))
checker.paths = paths

def guarded(output):
    output = output.resolve()
    if not output.is_relative_to((ROOT / 'data/campaign6-manager').resolve()):
        raise ValueError('Use a Campaign 6 owned freeze directory')
    return output

def run(output):
    output = guarded(output)
    if output.exists():
        raise ValueError('Never overwrite a freeze checkpoint')
    output.mkdir(parents=True)
    manifest = {}
    with zipfile.ZipFile(output / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in paths():
            if path.is_symlink():
                raise ValueError('Source freeze refuses symbolic links')
            blob = path.read_bytes()
            relative = path.relative_to(ROOT).as_posix()
            manifest[relative] = checker.digest(blob)
            archive.writestr(relative, blob)
    checker.save(output / 'MANIFEST.json', manifest)
    owner = {}
    for name in ('deployment.json', 'context-measurements.json'):
        path = ROOT / 'data/compute' / name
        if path.is_file():
            owner[path.relative_to(ROOT).as_posix()] = checker.digest(path.read_bytes())
    checker.save(output / 'SUMMARY.json', {'created_at': datetime.now(timezone.utc).isoformat(), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'python': sys.version, 'files': len(manifest), 'manifest_sha256': checker.digest((output / 'MANIFEST.json').read_bytes()), 'archive_sha256': checker.digest((output / 'source.zip').read_bytes()), 'owner_configuration_sha256': owner, 'private_holdout_seal': HOLDOUT_SEAL, 'scope': 'All production/configuration/tests, C4-C6 public helpers and inputs; derived reports excluded.'})
    checker.check(output)
    print((output / 'SUMMARY.json').read_text(), flush=True)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        print(json.dumps(checker.check(guarded(args.output))))
    else:
        run(args.output)
