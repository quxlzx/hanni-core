"""Use devices the serving backend can actually open, with CPU/RAM fallback."""
from __future__ import annotations

from pathlib import Path
import re

from hanni.models.runtime import list_devices, supported_options


def executable(bin_dir: Path, name: str) -> Path:
    path = bin_dir / name
    return path if path.is_file() else bin_dir / (name + '.exe')


def devices(bin_dir: Path) -> list[tuple[str, str]]:
    # Windows AdapterRAM truncates capacities and says nothing about whether the
    # installed llama.cpp backend can use an adapter. Ask that backend instead.
    found = list_devices([str(executable(bin_dir, 'llama-server'))])
    return [(key, name) for key, name in found if not re.search(
        r'llvmpipe|lavapipe|software|Microsoft Basic|\bCPU\b|\bRPC\b', key + ' ' + name, re.I)]


def preferred_device(found: list[tuple[str, str]]) -> tuple[str, str] | None:
    def rank(item):
        key, name = item
        integrated = bool(re.search(r'\bintegrated\b|\bAPU\b|Radeon\s*(?:\(TM\)\s*)?Graphics\b|'
                                    r'Radeon\s+\d{3,4}M\b|Intel.*(?:\bUHD\b|\bHD\b|\bIris\b)|'
                                    r'Intel\s*(?:\(R\)\s*)?Graphics\b', name, re.I))
        memory = re.search(r'\((\d+) MiB, (\d+) MiB free\)', name)
        free = int(memory[2]) if memory else 0
        total = int(memory[1]) if memory else 0
        return (not integrated, free, total, key)
    return max(found, key=rank) if found else None


def flags(bin_dir: Path, *, context: int | None = None, benchmark: bool = False) -> list[str]:
    prefix = [str(executable(bin_dir, 'llama-bench' if benchmark else 'llama-server'))]
    help_text = supported_options(prefix)
    if not all(option in help_text for option in ('--cache-type-k', '--cache-type-v', '--flash-attn')):
        raise RuntimeError('The installed llama.cpp build cannot enforce Q8 K/V cache. Update the model binaries.')
    selected = preferred_device(devices(bin_dir))
    args = ['-fa', 'on', '-ctk', 'q8_0', '-ctv', 'q8_0']
    if selected:
        # Leave layers adjustable so --fit can move excess weights to system RAM.
        # An explicitly fixed layer count disables that adjustment in new builds.
        auto_layers = not benchmark and bool(re.search(r'--(?:n-)?gpu-layers[^\n]*\n?[^\n]*\bauto\b', help_text))
        args += ['--device', selected[0], '--split-mode', 'none', '-ngl', 'auto' if auto_layers else '99']
        if not benchmark and '--fit ' in help_text:
            args += ['--fit', 'on']
            if context is not None and '--fit-ctx' in help_text:
                args += ['--fit-ctx', str(context)]
    else:
        args += ['-ngl', '0', '--device', 'none']
        if not benchmark and '--no-op-offload' in help_text:
            args += ['--no-op-offload']
    if not benchmark and '--log-verbosity' in help_text:
        # Allocation evidence, without prompt/response logging.
        args += ['--log-verbosity', '4']
    return args
