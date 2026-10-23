"""Preserve original dependencies before any scheduling campaign repair."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile
REPO = Path(__file__).resolve().parents[2]

def archive(output):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(REPO / 'data/campaign6-scheduling'):
        raise ValueError('Choose a fresh campaign-owned archive directory.')
    output.mkdir(parents=True)
    paths = [*(REPO / 'src').rglob('*.py'), *(REPO / 'scripts/campaign4_boundaries').glob('*.py'), *(REPO / 'tests').rglob('*.py')]
    manifest = {}
    with zipfile.ZipFile(output / 'source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(paths):
            key = path.relative_to(REPO).as_posix()
            raw = path.read_bytes()
            manifest[key] = hashlib.sha256(raw).hexdigest()
            bundle.writestr(key, raw)
            destination = output / 'extracted' / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8', newline='\n')
    result = {'files': len(manifest), 'source_zip_sha256': hashlib.sha256((output / 'source.zip').read_bytes()).hexdigest(), 'manifest_sha256': hashlib.sha256((output / 'manifest.json').read_bytes()).hexdigest(), 'scope': 'All production Python and reused controlled workflow/test dependencies; no owner data/configuration.'}
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(archive(parser.parse_args().output), indent=2))
