"""Detected execution-host facts, independent of model hosting or chat history."""
from __future__ import annotations

import json
import platform


def host_facts(*, workspace=None, terminal_cwd=None):
    system = platform.system()
    facts = {'operating_system': system, 'os_release': platform.release(),
             'architecture': platform.machine(), 'local_terminal_shell': 'none (direct executable; shell=False)',
             'user_command_syntax': 'PowerShell' if system == 'Windows' else 'POSIX shell' if system in {'Linux', 'Darwin'} else 'check the host'}
    if workspace is not None: facts['file_workspace'] = str(workspace)
    if terminal_cwd is not None: facts['terminal_working_directory'] = str(terminal_cwd)
    return facts


def host_environment_prompt(*, workspace=None, terminal_cwd=None):
    facts = host_facts(workspace=workspace, terminal_cwd=terminal_cwd)
    windows = facts['operating_system'] == 'Windows'
    guidance = (
        'This execution host runs Windows. Use Windows paths and PowerShell syntax when giving the owner commands to run. '
        'Do not assume Bash, Linux utilities, /bin, /home, /mnt, apt, sudo, or WSL are available. '
        if windows else
        'Use commands and paths appropriate to the detected execution host. '
    )
    return ('## Detected execution environment (trusted runtime facts)\n' + json.dumps(facts, ensure_ascii=False) + '\n'
            + guidance
            + 'local_terminal starts one allowlisted executable directly; it is not a PowerShell, cmd.exe, or Bash session. '
              'Shell aliases, built-ins, cmdlets, pipes, redirection, glob expansion, and shell composition are unavailable there. '
              'Prefer local_list_dir to list folders, local_read_file/local_read_document to read files, '
              'local_search_files to search text, and local_python with pathlib for portable filesystem work. '
              'For Python in local_terminal use python -c with a double-quoted code argument; single quotes do not group Windows arguments. '
              'These local facts remain authoritative after context compression and override stale environment assumptions in history or skills. '
              'The inference server may run on a different machine; its OS does not change where local tools execute. '
              'Use another OS syntax only for an explicitly selected remote tool whose target OS is known. '
              'Use only the capabilities supplied in the current tool menu; this environment description grants no extra tool access.')
