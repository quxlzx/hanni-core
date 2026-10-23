"""Independently execute the owner oracle after a malicious harness edit."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest

def worker():
    path = Path(__file__).resolve().parents[2] / 'deployment/cluster-harnesses/worker.py'
    spec = importlib.util.spec_from_file_location('hanni_worker_checks', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_weakened_checker_cannot_manufacture_pass_for_wrong_program(tmp_path):
    checker = "from pathlib import Path\nassert Path('answer.txt').read_text() == '7'\n"
    (tmp_path / 'answer.txt').write_text('6')
    (tmp_path / 'verify.py').write_text('assert True\n')
    snapshot = {'check_files': ['verify.py'], 'files': {'verify.py': checker}}
    hashes = worker().restore_checks(snapshot, tmp_path)
    outcome = subprocess.run([sys.executable, 'verify.py'], cwd=tmp_path, capture_output=True)
    assert outcome.returncode != 0
    assert (tmp_path / 'verify.py').read_text() == checker and len(hashes['verify.py']) == 64
    (tmp_path / 'answer.txt').write_text('7')
    assert subprocess.run([sys.executable, 'verify.py'], cwd=tmp_path, capture_output=True).returncode == 0

def test_checker_symlink_cannot_modify_an_outside_file(tmp_path):
    outside = tmp_path / 'outside.py'
    outside.write_text('unchanged')
    project = tmp_path / 'project'
    project.mkdir()
    try:
        (project / 'verify.py').symlink_to(outside)
    except OSError:
        pytest.skip('Symlink creation unavailable')
    with pytest.raises(ValueError, match='symbolic link'):
        worker().restore_checks({'check_files': ['verify.py'], 'files': {'verify.py': 'assert True'}}, project)
    assert outside.read_text() == 'unchanged'
