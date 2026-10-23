"""Repeat original workflow regressions without opening owner workflow state."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]

def sources():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT / 'src/hanni').rglob('*.py'))}

def run(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted({*(ROOT / 'tests/unit').glob('test_workflow*.py'), *(ROOT / 'tests/integration').glob('test_workflow*.py'), ROOT / 'tests/unit/test_dashboard_workflows.py', ROOT / 'tests/unit/test_email_workflow_reliability.py'})
    command = [sys.executable, '-X', 'utf8', '-m', 'pytest', *[str(path.relative_to(ROOT)) for path in paths], '-q', f"--junitxml={output / 'results.xml'}"]
    before = sources()
    started = time.perf_counter()
    with (output / 'output.log').open('w', encoding='utf8') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    suites = ET.parse(output / 'results.xml').getroot().findall('testsuite')
    counts = {field: sum((int(suite.attrib.get(field, 0)) for suite in suites)) for field in ('tests', 'failures', 'errors', 'skipped')}
    receipt = {'command': command, 'test_files': len(paths), 'exit_code': result.returncode, 'duration_seconds': time.perf_counter() - started, 'counts': counts, 'source_before': before, 'source_after': sources()}
    receipt['source_unchanged'] = receipt['source_before'] == receipt['source_after']
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: receipt[key] for key in ('exit_code', 'test_files', 'counts', 'duration_seconds', 'source_unchanged')}))
    return result.returncode
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
