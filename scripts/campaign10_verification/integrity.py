"""Whole-source freeze and exclusive final claims, with no executable task content."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
SOURCE_ROOTS = ('src', 'frontend', 'desktop', 'scripts', 'tests', 'config', 'evals')
IGNORED_DIRS = frozenset({'node_modules', '.git', '__pycache__', '.pytest_cache', '.venv', 'build', 'dist', 'coverage', 'test-results', 'playwright-report'})
SUFFIXES = frozenset({'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.json', '.jsonl', '.yaml', '.yml', '.css', '.html', '.md', '.cmd', '.bat', '.ps1', '.toml', '.txt', '.lock', '.spec', '.svg', '.woff', '.woff2', '.ico', '.manifest', '.in'})

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def snapshot_source(repo):
    repo = Path(repo).resolve()
    rows = []
    for directory in SOURCE_ROOTS:
        root = repo / directory
        if not root.exists():
            continue
        for path in root.rglob('*'):
            rel = path.relative_to(repo)
            if path.is_file() and (not set(rel.parts).intersection(IGNORED_DIRS)) and (path.suffix.casefold() in SUFFIXES):
                if path.is_symlink() or not path.resolve().is_relative_to(repo):
                    raise ValueError('Source manifest does not follow links outside repository.')
                rows.append({'path': rel.as_posix(), 'sha256': digest(path), 'size': path.stat().st_size})
    for name in ('pyproject.toml', '.env.example', 'README.md', 'CLAUDE.md', 'SECURITY.md', 'MANIFEST.in', 'START_HANNI.cmd', 'START_HANNI_OS.cmd', 'SETUP_HANNI.cmd', 'EXPORT_HANNI_SOURCE.cmd'):
        path = repo / name
        if path.exists():
            rows.append({'path': name, 'sha256': digest(path), 'size': path.stat().st_size})
    rows.sort(key=lambda row: row['path'])
    return {'version': 1, 'files': rows, 'file_count': len(rows), 'source_sha256': canonical_digest(rows)}

def assert_freeze(repo, freeze):
    if not isinstance(freeze, dict) or not freeze.get('files'):
        raise ValueError('A whole-source manifest is required before final collection.')
    if canonical_digest(freeze['files']) != freeze.get('source_sha256'):
        raise ValueError('Source manifest hash is invalid.')
    actual = snapshot_source(repo)
    if actual['files'] != freeze['files']:
        raise RuntimeError('Frozen source/helper/assets/configuration changed; final is forbidden.')
    return actual['source_sha256']

def claim_once(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {'claimed_at': datetime.now(timezone.utc).isoformat(), **payload}
    with path.open('x', encoding='utf-8') as handle:
        json.dump(body, handle, indent=2)
        handle.write('\n')
    return body

def verify_go(go, freeze_sha256, input_sha256):
    if not isinstance(go, dict) or go.get('approved') is not True or go.get('authorized_by') != '/root':
        raise PermissionError('Explicit coordinator GO is required before private final collection.')
    if go.get('source_sha256') != freeze_sha256 or go.get('input_sha256') != input_sha256:
        raise PermissionError('Coordinator GO must bind the exact source freeze and untouched input seal.')
    if not isinstance(go.get('nonce'), str) or len(go['nonce']) < 16:
        raise PermissionError('Coordinator GO needs a unique nonce.')
