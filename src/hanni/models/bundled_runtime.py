"""Find app-local llama.cpp before developer installs or system PATH."""
from __future__ import annotations

import os
from pathlib import Path

ENVIRONMENT_KEY = 'HANNI_LLAMA_RUNTIME_DIR'


def runtime_roots(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    candidates = []
    explicit = os.environ.get(ENVIRONMENT_KEY)
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute(): raise RuntimeError('HANNI_LLAMA_RUNTIME_DIR must be an absolute directory.')
        candidates.append(path)
    candidates += [root / 'dist/HANNI OS/_internal/runtimes/llama.cpp',
                   root / 'build/llama-runtime', root / 'binaries']
    return list(dict.fromkeys(path.resolve() for path in candidates))


def runtime_directories(root=None):
    names = (('windows-cuda', 'windows-vulkan', 'windows-x86_64') if os.name == 'nt'
             else ('linux-cuda', 'linux-vulkan', 'linux-x86_64'))
    return [base / name for base in runtime_roots(root) for name in names]
