"""Archive campaign implementation and public inputs without opening holdout data."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
import zipfile
ROOT = Path(__file__).resolve().parents[2]
HOLDOUT_SEAL = {'cases': 100, 'sealed_at': '2026-10-10T09:49:15.610481+00:00', 'inputs_sha256': '5ee4b787856e27a1031a8cdd3e5f753e525579413d1cf25ae65ca6e7b6fb6b34', 'oracles_sha256': '0cfc00fbf6d1c3eba979ebbd2aae443d617b216ffcd34bd394720d5534a521cc', 'protocol_sha256': 'd8dbe6a9a4eeba8e61c7416126f3548c17eaecec9a99191398cf18844ff3325b', 'source': 'Independent verifier announcement; manager never opens private corpus.'}

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def paths():
    selected = {*ROOT.joinpath('src/hanni').rglob('*.py'), *ROOT.joinpath('config').rglob('*.yaml'), *ROOT.joinpath('tests').rglob('*.py'), ROOT / '.gitattributes', ROOT / 'pyproject.toml', ROOT / 'docs/campaign5/PROTOCOL.md', ROOT / 'scripts/campaign3_manager/model_probe.py'}
    for folder in ROOT.joinpath('scripts').glob('campaign5*'):
        if folder.is_dir():
            selected.update(folder.rglob('*.py'))
    selected.update(ROOT.joinpath('evals/models').glob('campaign5*.json'))
    return sorted((p for p in selected if p.is_file()))

def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')

def run(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign5-manager').resolve()):
        raise ValueError('Choose a fresh campaign-owned freeze directory.')
    output.mkdir(parents=True)
    selected = paths()
    manifest = {}
    with zipfile.ZipFile(output / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            if path.is_symlink():
                raise ValueError('Source freeze does not follow symbolic links.')
            relative = path.relative_to(ROOT).as_posix()
            blob = path.read_bytes()
            manifest[relative] = digest(blob)
            archive.writestr(relative, blob)
    save(output / 'MANIFEST.json', manifest)
    owner_configuration = {}
    for name in ('deployment.json', 'context-measurements.json'):
        path = ROOT / 'data/compute' / name
        if path.is_file():
            owner_configuration[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
    save(output / 'SUMMARY.json', {'created_at': datetime.now(timezone.utc).isoformat(), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'python': sys.version, 'files': len(manifest), 'manifest_sha256': digest((output / 'MANIFEST.json').read_bytes()), 'archive_sha256': digest((output / 'source.zip').read_bytes()), 'owner_configuration_sha256': owner_configuration, 'private_holdout_seal': HOLDOUT_SEAL, 'scope': 'Production, configuration, tests, campaign helpers and public inputs; reports excluded.'})
    check(output)
    print((output / 'SUMMARY.json').read_text(encoding='utf8'), flush=True)

def check(output):
    manifest = json.loads((output / 'MANIFEST.json').read_text(encoding='utf8'))
    current_names = {path.relative_to(ROOT).as_posix() for path in paths()}
    membership_changes = sorted(current_names.symmetric_difference(manifest))
    mismatches = [relative for relative, expected in manifest.items() if not (ROOT / relative).is_file() or digest((ROOT / relative).read_bytes()) != expected]
    summary = json.loads((output / 'SUMMARY.json').read_text(encoding='utf8'))
    archive_mismatches = []
    with zipfile.ZipFile(output / 'source.zip') as archive:
        if set(archive.namelist()) != set(manifest):
            archive_mismatches.append('archive membership')
        archive_mismatches.extend((name for name in archive.namelist() if digest(archive.read(name)) != manifest.get(name)))
    owner_mismatches = [name for name, expected in summary['owner_configuration_sha256'].items() if digest((ROOT / name).read_bytes()) != expected]
    result = {'source_mismatches': mismatches, 'source_membership_changes': membership_changes, 'archive_mismatches': archive_mismatches, 'owner_configuration_mismatches': owner_mismatches, 'manifest_matches': digest((output / 'MANIFEST.json').read_bytes()) == summary['manifest_sha256'], 'archive_matches': digest((output / 'source.zip').read_bytes()) == summary['archive_sha256']}
    save(output / 'CHECK.json', result)
    if mismatches or membership_changes or archive_mismatches or owner_mismatches or (not result['manifest_matches']) or (not result['archive_matches']):
        raise RuntimeError('Campaign implementation/input freeze no longer matches.')
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.output.resolve())))
    else:
        run(args.output)
