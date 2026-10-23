"""Archive the exact implementation used for Campaign 4 verification."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[2]

def manifest():
    paths = set((ROOT / 'src/hanni').rglob('*.py'))
    paths.update((ROOT / 'config').rglob('*.yaml'))
    paths.add(ROOT / 'docs/campaign4/PROTOCOL.md')
    paths.update({ROOT / '.gitattributes', ROOT / 'pyproject.toml', ROOT / 'tests/helpers.py', ROOT / 'tests/unit/test_dashboard_workflows.py', ROOT / 'tests/unit/test_email_workflow_reliability.py', ROOT / 'tests/unit/test_workflow_model_context.py', ROOT / 'scripts/campaign1_verification/recording.py', ROOT / 'scripts/campaign3_manager/model_probe.py'})
    paths.update((ROOT / 'tests').rglob('conftest.py'))
    paths.update((ROOT / 'scripts/v3_review').glob('*.py'))
    for directory in (ROOT / 'scripts').glob('campaign4*'):
        paths.update(directory.rglob('*.py'))
    for directory in ('tests/unit', 'tests/integration'):
        paths.update((ROOT / directory).glob('test_campaign4*.py'))
        paths.update((ROOT / directory).glob('test_workflow*.py'))
    paths.update((path for path in (ROOT / 'evals/workflows').glob('campaign4*.json') if not path.name.endswith(('_results.json', '_coverage.json'))))
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths) if path.is_file()}

def freeze(output):
    output.mkdir(parents=True, exist_ok=True)
    original = manifest()
    with zipfile.ZipFile(output / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, expected in original.items():
            content = (ROOT / name).read_bytes()
            if hashlib.sha256(content).hexdigest() != expected:
                raise RuntimeError(f'Source changed during archive: {name}')
            archive.writestr(name, content)
    if manifest() != original:
        raise RuntimeError('Source changed during freeze')
    receipt = {'manifest': original, 'manifest_sha256': hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest(), 'source_zip_sha256': hashlib.sha256((output / 'source.zip').read_bytes()).hexdigest(), 'scope': 'All HANNI Python source, configuration YAML, Campaign4 code/corpus, workflow regressions and protocol.'}
    (output / 'FREEZE.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: value for key, value in receipt.items() if key != 'manifest'}))
    return receipt
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    freeze(parser.parse_args().output)
