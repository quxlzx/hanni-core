"""Real disposable processes prove cleanup; no host service is invoked."""
import json
from pathlib import Path
import subprocess
import sys

import psutil
import pytest

from hanni.native.code_execution import run_code


def test_script_completion_reaps_owned_descendants_and_preserves_unrelated_process(tmp_path):
    sibling = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid_file = tmp_path / 'owned-child.json'
    code = ("import json,subprocess,sys\n"
            "from pathlib import Path\n"
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
            f"Path({str(pid_file)!r}).write_text(json.dumps(child.pid))\nprint('parent done')\n")
    child = None
    try:
        receipt = run_code(code, runtime=None, call_id='owned-tree', workspace=tmp_path, cancelled=lambda: False)
        child = psutil.Process(json.loads(pid_file.read_text())) if psutil.pid_exists(json.loads(pid_file.read_text())) else None
        if child is not None:
            _, alive = psutil.wait_procs([child], timeout=2)
            assert not alive, 'A completed script left its owned child running.'
        assert receipt['ok'] and 'parent done' in receipt['data']['stdout']
        assert sibling.poll() is None
    finally:
        if child is not None and child.is_running():
            child.kill()
            child.wait(timeout=5)
        sibling.kill()
        sibling.wait(timeout=5)
