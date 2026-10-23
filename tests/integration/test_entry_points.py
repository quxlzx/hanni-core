"""The installed entry point works as a subprocess (the console script requires `pip install -e .`)."""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from tests.helpers import REPO_ROOT, TempDirTestCase

class EntryPointTests(TempDirTestCase):

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith('HANNI_')}
        env['HANNI_CONFIG_DIR'] = str(self.config_dir())
        env['HANNI_DATA_DIR'] = str(self.data_dir)
        env['PYTHONPATH'] = str(REPO_ROOT / 'src') + os.pathsep + env.get('PYTHONPATH', '')
        return env

    def test_python_module_entry_point(self) -> None:
        result = subprocess.run([sys.executable, '-m', 'hanni.cli', 'health', '--no-file-log', '--env-file', str(self.tmp / 'none.env')], env=self._env(), capture_output=True, text=True, timeout=60, cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Overall: HEALTHY', result.stdout)

    def test_console_script_if_installed(self) -> None:
        exe = shutil.which('hanni')
        if exe is None:
            self.skipTest('hanni not on PATH (run `pip install -e .`)')
        result = subprocess.run([exe, 'version'], env=self._env(), capture_output=True, text=True, timeout=60, cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('hanni '))
