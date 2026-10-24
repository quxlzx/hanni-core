"""Export complete Python source without runtime data, credentials or model weights."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import tomllib
import zipfile

ROOT_FILES = {'.env.example', '.gitignore', '.dockerignore', '.gitattributes', 'pyproject.toml', 'README.md', 'OVERNIGHT_HANDOFF.md',
              'CLAUDE.md', 'AGENTS.md', 'SETUP_HANNI.cmd', 'START_HANNI.cmd', 'START_HANNI_OS.cmd', 'MANIFEST.in',
              'EXPORT_HANNI_SOURCE.cmd', 'SETUP_HANNI_VOICE.cmd', 'LICENSE', 'CONTRIBUTING.md', 'SECURITY.md',
              'PUBLIC_READINESS.md','PUBLIC_READINESS.json','PUBLIC_RELEASE_REVIEW.json','.PUBLIC_RELEASE_OWNER',
              'START_BRAIN.cmd', 'start_brain.sh'}
SOURCE_DIRS = {'src', 'tests', 'scripts', 'config', 'docs', 'evals', '.github', 'frontend', 'desktop', 'deployment', 'soul'}
BLOCKED = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.pytest-work',
           '.pytest-overnight', 'data', 'node_modules', 'build', 'dist'}
EXTENSIONS = {'.py', '.ps1', '.cmd', '.sh', '.md', '.txt', '.yaml', '.yml', '.toml', '.json', '.jsonl', '.html', '.css', '.js', '.cjs', '.mjs', '.ts', '.tsx'}


def source_files(root):
    paths=[]
    for folder, directories, files in os.walk(root,followlinks=False):
        directories[:]=sorted(name for name in directories if name not in BLOCKED and not name.endswith('.egg-info') and not (Path(folder)/name).is_symlink())
        paths.extend(Path(folder)/name for name in files)
    for path in sorted(paths):
        rel = path.relative_to(root)
        if any(p in BLOCKED or p.endswith('.egg-info') for p in rel.parts): continue
        if any(p.is_symlink() for p in (path, *path.parents)): continue
        if not path.is_file(): continue
        if len(rel.parts) == 1:
            if path.name in ROOT_FILES: yield path
            continue
        if rel.parts[0] not in SOURCE_DIRS: continue
        if rel.parts[0] == 'config' and path.suffix.lower() != '.yaml': continue
        if rel.parts[0] == 'evals' and any(part in {'results', 'checkpoints', 'inbox'} for part in rel.parts[1:-1]):
            continue
        # The curated owner-failure corpus is versionable locally but must not
        # become part of an exported source archive, even after it has entries.
        if rel.parts[:2] == ('evals', 'real_world') and (
                'inbox' in rel.parts or path.suffix.lower() == '.jsonl'):
            continue
        name = path.name.lower()
        if name.endswith('.local.yaml'): continue  # local overrides never ship
        if (name.startswith('.env') or name in {'credentials.json', 'google-oauth-client.json'}
                or name.startswith('client_secret') or 'token' in name and path.suffix == '.json'):
            continue
        if 'models' in rel.parts and rel.parts[:3] != ('src', 'hanni', 'models'): continue
        if path.suffix.lower() in EXTENSIONS or path.name in {'Dockerfile','.dockerignore'} or rel.as_posix() == 'frontend/src/fonts/GeistSans-Variable.woff2' or (rel.parts[0] == 'desktop' and path.suffix.lower() in {'.spec', '.manifest', '.ico'}): yield path


def export(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError('Choose an output outside the repository')
    files = list(source_files(root))
    try:
        from audit_public_release import findings
    except ModuleNotFoundError:
        from scripts.audit_public_release import findings
    def inspect(path):
        data=path.read_bytes();observed=findings(data,path.relative_to(root).as_posix())
        if (path.suffix=='.ico' and data.startswith(b'\x00\x00\x01\x00')) or (path.suffix=='.woff2' and data.startswith(b'wOF2')):
            # Compressed pixels/glyphs can coincidentally resemble an IP. Keep
            # credential/path findings; network strings apply to textual source.
            observed=[f for f in observed if f['category'] not in {'network_address','nonpublic_endpoint'}]
        if path.relative_to(root).as_posix().startswith('tests/'):
            # Safety tests deliberately embed fake private/loopback endpoints
            # (SSRF guards, port guards). They are fixtures, not infrastructure.
            observed=[f for f in observed if f['category'] not in {'network_address','nonpublic_endpoint'}]
        return observed
    exposures = [(p.relative_to(root).as_posix(), inspect(p)) for p in files]
    blocked = [(name,issues) for name,issues in exposures if issues]
    if blocked:
        raise ValueError('Public-source export blocked by privacy audit; review '+str(len(blocked))+' files. Run scripts/audit_public_release.py; matched values are not printed.')
    names = {p.relative_to(root).as_posix() for p in files}
    metadata = tomllib.loads((root/'pyproject.toml').read_text())
    for package in metadata['tool']['setuptools']['packages']:
        required = 'src/' + package.replace('.', '/') + '/__init__.py'
        if required not in names:
            raise ValueError('Export missing declared package: ' + package)
    for path in (root/'src/hanni').rglob('*.py'):
        if '__pycache__' not in path.parts and path.relative_to(root).as_posix() not in names:
            raise ValueError('Export would omit Python source: ' + str(path))
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open('xb') as stream:
            created = True
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
                for path in files: z.write(path, 'hanni/' + path.relative_to(root).as_posix())
    except BaseException:
        if created: output.unlink(missing_ok=True)
        raise
    return len(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'Exported {export(Path(__file__).resolve().parents[1], args.output)} files to {args.output}')
