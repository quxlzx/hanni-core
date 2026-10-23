"""Source freeze and preservation checks; never reads private holdout material."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile
import psutil
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from scripts.campaign7_manager.preflight import sources
BASE = ROOT / 'data/campaign7-manager/preflight'
FINAL = ROOT / 'data/campaign7-manager/final-freeze'
ALLOWED = {'src/hanni/speech/microphone.py', 'src/hanni/speech/stt.py', 'src/hanni/speech/pipeline.py', 'src/hanni/speech/live.py', 'src/hanni/dashboard/voice.py', 'frontend/src/awareness.tsx', 'frontend/src/mini.tsx', 'frontend/src/workspace.tsx', 'src/hanni/dashboard/static/app.js', '.gitattributes'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def current_sources():
    chosen = set(sources())
    for folder in ROOT.joinpath('scripts').glob('campaign[4567]*'):
        chosen.update((p for p in folder.rglob('*') if p.is_file() and p.suffix in {'.py', '.js', '.cjs', '.ps1', '.sh', '.json', '.jsonl', '.yaml', '.toml'}))
    chosen.update((p for p in ROOT.joinpath('frontend').glob('*') if p.is_file()))
    chosen.update((p for p in ROOT.joinpath('frontend/public').rglob('*') if p.is_file()))
    chosen.update((p for p in ROOT.joinpath('frontend/tests').rglob('*') if p.is_file()))
    for path in ROOT.joinpath('evals').rglob('*'):
        if path.is_file() and path.suffix in {'.json', '.jsonl'} and ('campaign' in path.as_posix()):
            chosen.add(path)
    chosen.update((ROOT.joinpath('docs/campaign7', name) for name in ('PROTOCOL.md', 'FINAL_SEAL.json', 'FINAL_ADAPTER.md')))
    return sorted((p for p in chosen if p.is_file()))

def preservation():
    original = read(BASE / 'SOURCE_BEFORE.json')
    changed = [name for name, before in original.items() if not (ROOT / name).is_file() or sha(ROOT / name) != before]
    unexpected = [name for name in changed if name not in ALLOWED]
    prior = read(BASE / 'PRIOR_CAMPAIGN_AND_OWNER_FILES.json')
    prior_bad = [name for name, before in prior.items() if not (ROOT / name).is_file() or sha(ROOT / name) != before]
    owner = read(BASE / 'OWNER_FILE_IDENTITIES.json')
    owner_now = {}
    for name in owner:
        path = ROOT / 'data' / name
        owner_now[name] = {'exists': path.is_file()}
        if path.is_file():
            owner_now[name]['sha256'] = sha(path)
    before_attrs = zipfile.ZipFile(BASE / 'source.zip').read('.gitattributes')
    after_attrs = (ROOT / '.gitattributes').read_bytes()
    result = {'changed_original_files': changed, 'unexpected_source_changes': unexpected, 'prior_files_checked': len(prior), 'prior_file_mismatches': prior_bad, 'owner_file_identities_preserved': owner == owner_now, 'gitattributes_original_prefix_preserved': after_attrs.startswith(before_attrs), 'configuration_files_unchanged': not any((x.startswith('config/') for x in changed))}
    result['passed'] = not unexpected and (not prior_bad) and (owner == owner_now) and after_attrs.startswith(before_attrs)
    return result

def budget():
    from hanni.config.loader import load_config
    output = ROOT / 'data/campaign7-manager/RESOURCE_RECHECK.json'
    if output.exists():
        raise RuntimeError('The single bounded resource recheck has already been recorded')
    config = load_config(ROOT / 'config', data_dir=ROOT / 'data/campaign7-manager/isolated-recheck', env={})
    memory = psutil.virtual_memory()
    result = {'observed_at': time.time(), 'available_ram_bytes': memory.available, 'total_ram_bytes': memory.total, 'used_percent': memory.percent, 'reserve_mb': config.models.ram_reserve_mb, 'critical_percent': config.models.critical_ram_percent, 'additional_model_budget_bytes': 1024 ** 3}
    result['additional_model_load_allowed'] = memory.available >= config.models.ram_reserve_mb * 1024 ** 2 + 1024 ** 3 and memory.percent < config.models.critical_ram_percent
    save(output, result)
    print(json.dumps(result))

def freeze():
    protected = preservation()
    if not protected['passed']:
        raise RuntimeError(json.dumps(protected))
    FINAL.mkdir(parents=True, exist_ok=False)
    manifest = {}
    with zipfile.ZipFile(FINAL / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in current_sources():
            if path.is_symlink():
                raise RuntimeError('Refuse symlinked executable evidence')
            name = path.relative_to(ROOT).as_posix()
            blob = path.read_bytes()
            manifest[name] = hashlib.sha256(blob).hexdigest()
            archive.writestr(name, blob)
    save(FINAL / 'MANIFEST.json', manifest)
    result = {'frozen_at': time.time(), 'source_files': len(manifest), 'manifest_sha256': sha(FINAL / 'MANIFEST.json'), 'archive_sha256': sha(FINAL / 'source.zip'), 'private_holdout_material_read': False, 'preservation': protected}
    save(FINAL / 'RECEIPT.json', result)
    save(ROOT / 'docs/campaign7/FINAL_FREEZE.json', result)
    print(json.dumps(result))

def check():
    manifest = read(FINAL / 'MANIFEST.json')
    actual = {p.relative_to(ROOT).as_posix(): sha(p) for p in current_sources()}
    mismatches = sorted((name for name in set(manifest) | set(actual) if manifest.get(name) != actual.get(name)))
    runtime = []
    for connection in psutil.net_connections('tcp'):
        if connection.status == psutil.CONN_LISTEN and connection.laddr.port in (8080, 8765) and connection.pid:
            process = psutil.Process(connection.pid)
            runtime.append({'port': connection.laddr.port, 'pid': process.pid, 'created': process.create_time(), 'parent_pid': process.ppid(), 'command_sha256': hashlib.sha256(json.dumps(process.cmdline()).encode()).hexdigest()})
    before = read(BASE / 'LOCAL_RUNTIME.json')
    order = lambda rows: sorted(rows, key=lambda r: (r['port'], r['pid']))
    result = {'checked_at': time.time(), 'frozen_source_mismatches': mismatches, 'preservation': preservation(), 'runtime_identities_unchanged': order(before) == order(runtime), 'runtime_after': runtime, 'manifest_sha256': sha(FINAL / 'MANIFEST.json'), 'archive_sha256': sha(FINAL / 'source.zip')}
    result['passed'] = not mismatches and result['preservation']['passed'] and result['runtime_identities_unchanged']
    save(FINAL / 'CLOSE_CHECK.json', result)
    print(json.dumps(result))
    if not result['passed']:
        raise RuntimeError('Final evidence preservation check failed')
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('budget', 'freeze', 'check'))
    args = parser.parse_args()
    {'budget': budget, 'freeze': freeze, 'check': check}[args.action]()
