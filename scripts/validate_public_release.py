"""Validate a prepared public copy without models, accounts or remote services.

Run from any directory with --candidate and a private --reports directory.
The report distinguishes controlled software checks from live acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from export_source import source_files


def source_digest(root):
    digest = hashlib.sha256()
    for path in source_files(root):
        if path.name in {'PUBLIC_READINESS.md','PUBLIC_READINESS.json','PUBLIC_RELEASE_REVIEW.json'}:
            continue  # Release verdict metadata is written after validation.
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def validate(candidate, reports, *, skip_install=False):
    candidate, reports = Path(candidate).resolve(), Path(reports).resolve()
    if candidate == reports or reports.is_relative_to(candidate):
        raise ValueError('Keep full logs outside the public candidate.')
    if (candidate/'.PUBLIC_RELEASE_OWNER').read_text() != 'hanni-public-candidate-v1':
        raise ValueError('Validate a prepared, independently reviewed public copy.')
    reports.mkdir(parents=True, exist_ok=True)
    python = candidate/('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
    gates = []

    def run(name, command):
        began = time.monotonic()
        with (reports/(name+'.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=candidate, stdout=log, stderr=subprocess.STDOUT)
        gates.append({'gate':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-began,3)})
        print(f'{name}: {"PASS" if result.returncode == 0 else "FAIL"}', flush=True)
        return result.returncode == 0

    if not python.exists():
        if not run('create-venv', [sys.executable,'-m','venv',str(candidate/'.venv')]):
            raise RuntimeError('Could not create isolated environment.')
    if not skip_install:
        if not run('python-install',[str(python),'-m','pip','install','-e','.[dev,ui-test]','build']):
            raise RuntimeError('Clean dependency installation failed; see private logs.')
        if not run('frontend-install',['npm.cmd' if os.name == 'nt' else 'npm','ci','--prefix','frontend']):
            raise RuntimeError('Clean frontend installation failed; see private logs.')
    # Build before freezing: tests must inspect exactly the shipped assets.
    run('frontend-build',['npm.cmd' if os.name == 'nt' else 'npm','run','build','--prefix','frontend'])
    before = source_digest(candidate)
    run('frontend-tests',['node','--test',*[str(p.relative_to(candidate)) for p in sorted((candidate/'frontend/tests').glob('*.test.ts'))]])
    run('python-tests',[str(python),'-m','pytest','-q','--tb=short','--junitxml='+str(reports/'pytest.xml')])
    run('health',[str(python),'-m','hanni.cli','health','--no-file-log'])
    run('package-build',[str(python),'-m','build'])
    run('distribution-privacy',[str(python),'scripts/check_distribution.py'])
    run('source-privacy',[str(python),'scripts/audit_public_release.py','--report',str(reports/'privacy.json')])
    after = source_digest(candidate)
    gates.append({'gate':'unchanged-source-during-validation','exit_code':0 if before == after else 1})
    counts = {}
    if (reports/'pytest.xml').exists():
        suites=ET.parse(reports/'pytest.xml').getroot()
        counts={key:sum(int(s.attrib.get(key,0)) for s in suites.findall('testsuite'))
                for key in ('tests','failures','errors','skipped')}
    report={'status':'SOFTWARE_GATES_PASSED_ALPHA_ONLY' if all(g['exit_code']==0 for g in gates) else 'NOT_PUBLIC_READY',
            'scope':'Clean software regression and packaging; not live model or speech acceptance.',
            'python':platform.python_version(),'platform':platform.system(),'gates':gates,
            'tests':counts,'source_sha256_before':before,'source_sha256_after':after,
            'not_tested':['Physical microphone/TTS responsiveness','Live model held-out task quality',
                          'External provider accounts','Private remote deployment','Separate Control Center deployment']}
    (reports/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--reports',type=Path,required=True)
    parser.add_argument('--skip-install',action='store_true',help='Recheck an already installed copy; not a fresh-install measurement.')
    args=parser.parse_args()
    report=validate(args.candidate,args.reports,skip_install=args.skip_install)
    print(report['status'])
    raise SystemExit(0 if report['status']=='SOFTWARE_GATES_PASSED_ALPHA_ONLY' else 1)
