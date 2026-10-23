"""Basic local resource monitoring used by Milestone 1.

CPU/RAM come from psutil. NVIDIA telemetry is queried through nvidia-smi.
On AMD/Vulkan systems, H.A.N.N.I. falls back to llama.cpp --list-devices so it
can still identify multiple GPUs and report approximate device-memory usage
without adding a vendor-specific Python dependency.
"""

from __future__ import annotations

import csv
import io
import json
import re
import subprocess
from dataclasses import asdict, dataclass

import psutil


@dataclass(frozen=True, slots=True)
class GpuSnapshot:
    name: str
    memory_total_mb: int
    memory_used_mb: int
    utilization_percent: float | None
    temperature_c: float | None


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    cpu_percent: float
    ram_total_gb: float
    ram_used_gb: float
    ram_percent: float
    gpus: tuple[GpuSnapshot, ...]
    gpu_note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "cpu_percent": self.cpu_percent,
            "ram_total_gb": self.ram_total_gb,
            "ram_used_gb": self.ram_used_gb,
            "ram_percent": self.ram_percent,
            "gpus": [asdict(gpu) for gpu in self.gpus],
            "gpu_note": self.gpu_note,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def render_text(self) -> str:
        lines = [
            f"CPU: {self.cpu_percent:.1f}%",
            f"RAM: {self.ram_used_gb:.1f}/{self.ram_total_gb:.1f} GiB ({self.ram_percent:.1f}%)",
        ]
        if self.gpus:
            for index, gpu in enumerate(self.gpus):
                util = "?" if gpu.utilization_percent is None else f"{gpu.utilization_percent:.0f}%"
                temp = "?" if gpu.temperature_c is None else f"{gpu.temperature_c:.0f}C"
                lines.append(
                    f"GPU {index}: {gpu.name} - VRAM {gpu.memory_used_mb}/{gpu.memory_total_mb} MiB, util {util}, temp {temp}"
                )
        else:
            lines.append(f"GPU: unavailable ({self.gpu_note or 'no NVIDIA telemetry'})")
        return "\n".join(lines)


def snapshot_resources(*, cpu_interval: float = 0.05) -> ResourceSnapshot:
    memory = psutil.virtual_memory()
    gpus, nvidia_note = _nvidia_gpus()
    note = nvidia_note
    if not gpus:
        gpus, llama_note = _llama_cpp_gpus()
        if gpus:
            note = "GPU memory from llama.cpp device listing; utilization/temperature unavailable"
        else:
            details = [part for part in (nvidia_note, llama_note) if part]
            note = "; ".join(details) if details else "no GPU telemetry available"
    return ResourceSnapshot(
        cpu_percent=float(psutil.cpu_percent(interval=cpu_interval)),
        ram_total_gb=memory.total / (1024**3),
        ram_used_gb=memory.used / (1024**3),
        ram_percent=float(memory.percent),
        gpus=gpus,
        gpu_note=note,
    )


def _nvidia_gpus() -> tuple[tuple[GpuSnapshot, ...], str | None]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return (), str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        return (), detail[:300]

    gpus: list[GpuSnapshot] = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 5:
            continue
        try:
            gpus.append(
                GpuSnapshot(
                    name=row[0].strip(),
                    memory_total_mb=int(float(row[1].strip())),
                    memory_used_mb=int(float(row[2].strip())),
                    utilization_percent=_optional_float(row[3]),
                    temperature_c=_optional_float(row[4]),
                )
            )
        except ValueError:
            continue
    return tuple(gpus), None if gpus else "nvidia-smi returned no parseable GPU rows"



def _llama_cpp_gpus() -> tuple[tuple[GpuSnapshot, ...], str | None]:
    """Best-effort GPU inventory for Vulkan/ROCm/other llama.cpp backends.

    llama.cpp prints device memory as ``DEVICE: name (TOTAL MiB, FREE MiB free)``.
    This is intentionally a fallback after nvidia-smi so NVIDIA users retain
    utilization and temperature telemetry. On AMD it gives H.A.N.N.I. reliable
    VRAM totals without relying on Win32_VideoController.AdapterRAM, which can
    truncate values above 4 GiB.
    """
    command = ["llama-server", "--list-devices"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return (), f"llama.cpp device query unavailable: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        return (), f"llama.cpp device query failed: {detail[:300]}"

    # Backends may write discovery logs to stderr and the final list to stdout.
    text = "\n".join(part for part in (result.stdout, result.stderr) if part)
    pattern = re.compile(
        r"^\s*[A-Za-z][A-Za-z0-9_-]*\d+:\s*(?P<name>.+?)\s+"
        r"\((?P<total>\d+)\s+MiB,\s*(?P<free>\d+)\s+MiB\s+free\)\s*$",
        re.MULTILINE,
    )
    gpus: list[GpuSnapshot] = []
    seen: set[tuple[str, int]] = set()
    for match in pattern.finditer(text):
        name = match.group("name").strip()
        total = int(match.group("total"))
        free = min(total, max(0, int(match.group("free"))))
        key = (name, total)
        if key in seen:
            continue
        seen.add(key)
        gpus.append(
            GpuSnapshot(
                name=name,
                memory_total_mb=total,
                memory_used_mb=max(0, total - free),
                utilization_percent=None,
                temperature_c=None,
            )
        )
    return tuple(gpus), None if gpus else "llama.cpp returned no parseable GPU devices"

def _optional_float(value: str) -> float | None:
    text = value.strip().lower()
    if not text or text in {"n/a", "na", "[not supported]"}:
        return None
    return float(text)
