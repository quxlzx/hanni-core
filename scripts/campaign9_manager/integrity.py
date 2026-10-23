"""Freeze C9 public executables and check protected evidence without owner DBs."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
import zipfile
from .preflight import ROOT, digest, runtime
PRODUCTION_CHANGES = frozenset({'src/hanni/tools/base.py', 'src/hanni/tools/session.py', 'src/hanni/mcp/host.py', 'src/hanni/mcp/manager.py', 'src/hanni/memory/session.py', 'src/hanni/models/client.py', 'src/hanni/dashboard/server.py', 'src/hanni/logs/redaction.py', 'src/hanni/logs/formatter.py', 'src/hanni/tools/audit.py', 'src/hanni/dashboard/gateway.py'})

def write(path, value):
    if path.exists():
        raise RuntimeError('Preserve existing receipt: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def identity(value):
    return (value['ports'], [(row['pid'], row['created'], row['parent'], row['command_sha256']) for row in value['processes']])

def baseline_check(out):
    baseline = json.loads((ROOT / 'data/campaign9-manager/PREFLIGHT.json').read_text(encoding='utf-8'))
    changed = [name for name, expected in baseline['source_manifest'].items() if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
    unexpected = [name for name in changed if name not in PRODUCTION_CHANGES]
    protected_changed = [name for name, expected in baseline['protected'].items() if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
    artifact = baseline['native_artifact']
    observed_runtime = runtime()
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'baseline_source_files': len(baseline['source_manifest']), 'changed_baseline_sources': changed, 'unexpected_changed_baseline_sources': unexpected, 'protected_files_compared': len(baseline['protected']), 'changed_protected_files': protected_changed, 'native_artifact_unchanged': digest(ROOT / artifact['path']) == artifact['sha256'], 'owner_process_identities_unchanged': identity(observed_runtime) == identity(baseline['runtime']), 'runtime': observed_runtime, 'owner_database_byte_comparison': 'NOT_MEASURED; no owner database read or mount', 'private_holdout_inputs_or_answers_read': False}
    write(out, receipt)
    print(json.dumps({key: receipt[key] for key in ('changed_baseline_sources', 'unexpected_changed_baseline_sources', 'protected_files_compared', 'changed_protected_files', 'native_artifact_unchanged', 'owner_process_identities_unchanged')}))
    if unexpected or protected_changed or (not receipt['native_artifact_unchanged']) or (not receipt['owner_process_identities_unchanged']):
        raise RuntimeError('Integrity mismatch; retain the receipt and do not advance final.')

def sources():
    files = set()
    for directory in ('src', 'frontend/src', 'frontend/public', 'frontend/tests', 'desktop', 'config', 'tests', 'scripts', 'evals'):
        files.update((path for path in (ROOT / directory).rglob('*') if path.is_file() and (not any((part in {'__pycache__', 'node_modules', '.pytest_cache'} for part in path.parts))) and (path.suffix not in {'.pyc', '.log'})))
    files.update((path for path in (ROOT / 'frontend').glob('*') if path.is_file()))
    for name in ('.gitattributes', '.gitignore', 'pyproject.toml', 'START_HANNI.cmd', 'START_HANNI_OS.cmd', 'dist/HANNI OS/HANNI OS.exe', 'docs/campaign9/REQUEST.md', 'docs/campaign9/PROTOCOL.md', 'docs/campaign9/FINAL_SEAL.json', 'docs/campaign9/FINAL_ADAPTER.md', 'docs/campaign9/TOOLS_REVIEW.md', 'docs/campaign9/TOOLS_EVIDENCE.json', 'docs/campaign9/RESILIENCE_REVIEW.md', 'docs/campaign9/RESILIENCE_EVIDENCE.json', 'docs/campaign9/LIVE_REVIEW.md', 'docs/campaign9/INDEPENDENT_REVIEW.md', 'docs/campaign9/INDEPENDENT_CLOSEOUT.json', 'docs/campaign9/FINAL_STATUS.json'):
        path = ROOT / name
        if path.is_file():
            files.add(path)
    closeout = ROOT / 'docs/campaign9/INDEPENDENT_CLOSEOUT.json'
    if closeout.is_file():
        for row in json.loads(closeout.read_text(encoding='utf-8'))['receipts']:
            path = (ROOT / row['path']).resolve()
            if not path.is_relative_to(ROOT / 'data/campaign9-verifier') or path.is_relative_to(ROOT / 'data/campaign9-verifier/holdout') or path.name != 'RESULTS.json':
                raise ValueError('Only explicitly public closed development receipts may be added.')
            if digest(path) != row['sha256']:
                raise RuntimeError('Independent development receipt hash changed.')
            files.add(path)
    for directory in ('data/campaign9-tools', 'data/campaign9-resilience', 'data/campaign9-manager/development'):
        files.update((path for path in (ROOT / directory).rglob('*') if path.is_file() and '__pycache__' not in path.parts and (path.suffix not in {'.pyc', '.log'})))
    return sorted(files)

def dependencies():
    rows = {}
    for name in ('mcp', 'httpx2', 'httpcore2', 'anyio', 'pydantic', 'pydantic_core', 'jsonschema'):
        distribution = importlib.metadata.distribution(name)
        files = [distribution.locate_file(path) for path in distribution.files or () if not str(path).endswith('.pyc') and '__pycache__' not in Path(path).parts]
        rows[name] = {'version': distribution.version, 'installed_file_hashes': {str(path): digest(path) for path in files if path.is_file()}}
    rows['python'] = {'version': sys.version, 'executable': str(Path(sys.executable).resolve()), 'sha256': digest(Path(sys.executable)), 'base_executable': str(Path(sys._base_executable).resolve()), 'base_executable_sha256': digest(Path(sys._base_executable))}
    rows['stdlib_drivers'] = {name: {'path': str(Path(module.__file__).resolve()), 'sha256': digest(Path(module.__file__))} for name in ('urllib.request', 'urllib.error', 'http.client', 'ssl', '_ssl', '_socket', '_sqlite3') for module in [importlib.import_module(name)]}
    return rows

def seal(out):
    if out.exists() or not out.resolve().is_relative_to(ROOT / 'data/campaign9-manager'):
        raise ValueError('Fresh owned C9 manager directory required.')
    files = sources()
    manifest = {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
    driver_identity = dependencies()
    before = runtime()
    if before['native_clients']:
        raise RuntimeError('Unexpected native client; do not proceed.')
    out.mkdir(parents=True)
    write(out / 'MANIFEST.json', manifest)
    write(out / 'DEPENDENCIES.json', driver_identity)
    archive = out / 'SOURCE.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(ROOT).as_posix())
    changed = [name for name, expected in manifest.items() if digest(ROOT / name) != expected]
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'source_member_count': len(manifest), 'manifest_sha256': digest(out / 'MANIFEST.json'), 'archive_sha256': digest(archive), 'dependency_receipt_sha256': digest(out / 'DEPENDENCIES.json'), 'runtime': before, 'sources_unchanged_after_archive': not changed, 'changed_during_archive': changed, 'private_inputs_or_answers_read': False, 'mutable_final_reports_excluded': True}
    write(out / 'RECEIPT.json', receipt)
    print(json.dumps({key: value for key, value in receipt.items() if key != 'runtime'}))
    if changed:
        raise RuntimeError('Archive mismatch; no final GO.')

def verify(freeze, out):
    manifest = json.loads((freeze / 'MANIFEST.json').read_text(encoding='utf-8'))
    changed = [name for name, expected in manifest.items() if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
    dependencies_unchanged = dependencies() == json.loads((freeze / 'DEPENDENCIES.json').read_text(encoding='utf-8'))
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'files_compared': len(manifest), 'changed_frozen_files': changed, 'dependencies_unchanged': dependencies_unchanged, 'private_inputs_or_answers_read': False}
    write(out, receipt)
    print(json.dumps(receipt))
    if changed or not dependencies_unchanged:
        raise RuntimeError('Final freeze mismatch; do not erase or re-run final.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('baseline', 'seal', 'verify'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--freeze', type=Path)
    args = parser.parse_args()
    if args.action == 'baseline':
        baseline_check(args.out)
    elif args.action == 'seal':
        seal(args.out)
    else:
        verify(args.freeze, args.out)
if __name__ == '__main__':
    main()
