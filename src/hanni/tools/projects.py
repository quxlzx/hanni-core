"""Bounded Python project tests with a real process exit status, without a shell."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hanni.tools.base import ToolDefinition, ToolResult


def _test(args, context, request):
    root = Path(str(args.get('root', ''))).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('project.test root must be an absolute existing project directory')
    target = str(args.get('target', 'tests'))
    resolved = (root / target).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
        raise ValueError('test target must exist inside root')
    timeout = max(1, min(int(args.get('timeout', 120)), 300))
    runner = args.get('runner', 'pytest')
    if runner not in {'pytest', 'script'}:
        raise ValueError('runner must be pytest or script')
    expected = args.get('expected_stdout')
    if runner == 'script' and (resolved.suffix.casefold() != '.py' or not isinstance(expected, str) or not expected.strip()):
        raise ValueError('script verification requires a .py target and nonempty expected_stdout')
    command = ([sys.executable, '-m', 'pytest', '-q', str(resolved)] if runner == 'pytest'
               else [sys.executable, str(resolved)])
    result = subprocess.run(command,
                            cwd=root, capture_output=True, text=True, timeout=timeout,
                            encoding='utf-8', errors='replace')
    passed = result.returncode == 0 and (runner != 'script' or result.stdout.strip() == expected.strip())
    return ToolResult('project.test', passed, f'Project verification {runner}: exit {result.returncode}, passed={passed}.',
                      {'root': str(root.resolve()), 'target': str(resolved), 'runner': runner, 'exit_code': result.returncode,
                       'stdout': result.stdout[-20000:], 'stderr': result.stderr[-5000:]})


def definitions():
    return (ToolDefinition('project.test', 'Verify a Python project using pytest (runner=pytest) or run a .py program and compare exact expected_stdout (runner=script). Executes project code and returns real exit status.',
                           2, 2, {'root': str, 'target': str, 'timeout': int, 'runner': str, 'expected_stdout': str},
                           {'root': 'string', 'exit_code': 'integer', 'stdout': 'string', 'stderr': 'string'},
                           _test, timeout_seconds=300, side_effect='external_action',
                           tags=('python', 'tests', 'pytest', 'verify', 'code', 'fix')) ,)
