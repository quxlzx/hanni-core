"""Read-only local system/process/GPU tools."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import time
from typing import Any, Mapping

import psutil

from hanni.models.resource_manager import snapshot_resources
from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult


def _system_stats(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    snap = snapshot_resources(cpu_interval=0.15)
    data = snap.to_dict()
    message = f"CPU is at {snap.cpu_percent:.0f} percent and memory is at {snap.ram_percent:.0f} percent."
    if snap.gpus:
        gpu = snap.gpus[0]
        if gpu.utilization_percent is not None:
            message += f" GPU usage is about {gpu.utilization_percent:.0f} percent."
    return ToolResult("system.stats", True, message, data)


def _battery_status(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    battery = psutil.sensors_battery()
    if battery is None:
        return ToolResult("system.battery", False, "Windows isn't reporting battery measurements for this computer.",
                          {"available": False, "percent": None, "power_plugged": None, "seconds_left": None})
    percent = max(0.0, min(100.0, float(battery.percent)))
    plugged = bool(battery.power_plugged)
    if plugged:
        message = f"Your battery is at {percent:.0f} percent and the laptop is plugged in."
    else:
        message = f"Your battery is at {percent:.0f} percent and the laptop is running on battery."
    return ToolResult(
        "system.battery",
        True,
        message,
        {"available": True, "percent": round(percent, 1), "power_plugged": plugged, "seconds_left": battery.secsleft},
    )


def _process_list(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    limit = max(1, min(int(args.get("limit", 20)), 100))
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            info = proc.info
            rows.append({"pid": info["pid"], "name": info.get("name") or "unknown", "memory_percent": round(float(info.get("memory_percent") or 0.0), 2)})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda row: row["memory_percent"], reverse=True)
    rows = rows[:limit]
    preview = ", ".join(row["name"] for row in rows[:6])
    message = f"The top processes by memory are {preview}." if preview else "I couldn't read any running processes right now."
    return ToolResult("process.list", True, message, {"processes": rows})


def _top_memory(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    """Return real resident-memory usage aggregated by executable name."""
    limit = max(1, min(int(args.get("limit", 5)), 20))
    total_ram = max(1, int(psutil.virtual_memory().total))
    grouped: dict[str, dict[str, Any]] = {}
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = str(proc.info.get("name") or proc.name() or "unknown")
            rss = int(proc.info["memory_info"].rss if proc.info.get("memory_info") else proc.memory_info().rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        key = name.casefold()
        row = grouped.setdefault(key, {"name": name, "rss_bytes": 0, "pids": []})
        row["rss_bytes"] += max(0, rss)
        row["pids"].append(proc.pid)

    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        rss_bytes = int(row["rss_bytes"])
        if rss_bytes <= 0:
            continue
        rows.append({
            "name": row["name"],
            "rss_mb": round(rss_bytes / (1024**2), 1),
            "rss_gb": round(rss_bytes / (1024**3), 2),
            "memory_percent": round(rss_bytes * 100.0 / total_ram, 1),
            "instances": len(row["pids"]),
            "pids": tuple(row["pids"]),
        })
    rows.sort(key=lambda row: row["rss_mb"], reverse=True)
    rows = rows[:limit]
    if rows:
        parts = []
        for row in rows[:3]:
            amount = f"{row['rss_gb']:.1f} GB" if row["rss_mb"] >= 1024 else f"{row['rss_mb']:.0f} MB"
            parts.append(f"{row['name']} at about {amount}")
        message = "The biggest RAM users right now are " + ", followed by ".join(parts) + "."
    else:
        message = "I couldn't read meaningful per-process memory usage right now."
    return ToolResult("process.top_memory", True, message, {"processes": rows})


def _top_cpu(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    """Sample real process CPU and aggregate it by executable name.

    psutil allows per-process values above 100% on multi-core machines. User-facing
    values are normalized by logical CPU count to a Task-Manager-like 0-100 scale.
    """
    limit = max(1, min(int(args.get("limit", 5)), 20))
    procs: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or proc.name() or "").casefold()
            if proc.pid == 0 or name in {"system idle process", "idle"}:
                continue
            proc.cpu_percent(None)
            procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.25)
    logical_cpus = max(1, int(psutil.cpu_count(logical=True) or 1))
    grouped: dict[str, dict[str, Any]] = {}
    for proc in procs:
        try:
            raw = max(0.0, float(proc.cpu_percent(None)))
            normalized = raw / logical_cpus
            if normalized <= 0.0:
                continue
            name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        key = name.casefold()
        row = grouped.setdefault(key, {"name": name, "cpu_percent": 0.0, "raw_cpu_percent": 0.0, "pids": []})
        row["cpu_percent"] += normalized
        row["raw_cpu_percent"] += raw
        row["pids"].append(proc.pid)

    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        rows.append({
            "name": row["name"],
            "cpu_percent": round(min(100.0, row["cpu_percent"]), 1),
            "raw_cpu_percent": round(row["raw_cpu_percent"], 1),
            "instances": len(row["pids"]),
            "pids": tuple(row["pids"]),
        })
    rows.sort(key=lambda row: row["cpu_percent"], reverse=True)
    rows = rows[:limit]
    if rows:
        parts = [f"{row['name']} at about {row['cpu_percent']:.0f} percent" for row in rows[:3]]
        message = "The biggest CPU users in this sample are " + ", followed by ".join(parts) + "."
    else:
        message = "No non-idle process showed meaningful CPU use during the sample."
    return ToolResult("process.top_cpu", True, message, {"processes": rows})


def _run_command(command: list[str], *, timeout: float = 8.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


def _top_disk_io(args, context, request):
    """Rank deltas of accessible process read/write counters, never lifetime totals."""
    samples, skipped = [], 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            samples.append((proc, proc.create_time(), proc.io_counters(), time.monotonic()))
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, NotImplementedError):
            skipped += 1
    time.sleep(.25)
    rows = []
    for proc, identity, before, sampled_at in samples:
        try:
            if proc.create_time() != identity: continue
            after = proc.io_counters()
            elapsed = max(.001, time.monotonic() - sampled_at)
            read = max(0, after.read_bytes - before.read_bytes) / elapsed
            write = max(0, after.write_bytes - before.write_bytes) / elapsed
            rows.append({'pid': proc.pid, 'name': proc.name(), 'read_bytes_per_second': round(read, 1),
                         'write_bytes_per_second': round(write, 1), 'total_bytes_per_second': round(read + write, 1),
                         'sample_seconds': round(elapsed, 3)})
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, NotImplementedError):
            skipped += 1
    rows.sort(key=lambda row: (-row['total_bytes_per_second'], row['pid']))
    rows = rows[:args.get('limit', 5)]
    active = [r for r in rows if r['total_bytes_per_second'] > 0]
    message = ('The busiest process I/O in this sample: ' + ', '.join(
        f"{r['name']} (PID {r['pid']}) at {r['total_bytes_per_second']/1024:.1f} KiB/s" for r in active[:3]) + '.'
        if active else 'No activity was measured in the accessible process I/O counters during this sample.'
        if rows else 'Process I/O counters are unavailable.')
    if skipped: message += f' {skipped} process samples could not be read.'
    return ToolResult('process.top_disk_io', bool(rows), message,
                      {'processes': rows, 'skipped': skipped, 'partial': skipped > 0,
                       'source': 'process I/O counter deltas',
                       'scope': 'Current sample only; not historical physical-disk attribution.'})


def _nvidia_process_memory() -> dict[int, dict[str, Any]]:
    """Best-effort per-process dedicated VRAM from nvidia-smi compute contexts."""
    result = _run_command([
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_gpu_memory",
        "--format=csv,noheader,nounits",
    ])
    if result is None or result.returncode != 0:
        return {}
    rows: dict[int, dict[str, Any]] = {}
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 3:
            continue
        try:
            pid = int(row[0].strip())
        except ValueError:
            continue
        memory_text = row[2].strip().lower()
        try:
            memory_mb = float(memory_text) if memory_text not in {"n/a", "na", "[not supported]", "not supported"} else None
        except ValueError:
            memory_mb = None
        rows[pid] = {"pid": pid, "name": row[1].strip() or _process_name(pid), "vram_mb": memory_mb}
    return rows


def _process_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return f"PID {pid}"


def _windows_gpu_utilization() -> dict[int, float]:
    """Read Windows GPU-engine counters, returning max active engine per PID.

    Take two short samples because a single instantaneous performance-counter
    read frequently reports 0% for every process even while the GPU is active.
    Task Manager's process GPU percentage is closest to the busiest engine, so
    use max() rather than summing 3D/copy/video engines.
    """
    if os.name != "nt":
        return {}
    script = r"""
$ErrorActionPreference='SilentlyContinue'
$s=(Get-Counter '\GPU Engine(*)\Utilization Percentage' -SampleInterval 0.25 -MaxSamples 2 -ErrorAction SilentlyContinue).CounterSamples
$rows=@{}
foreach($c in $s){
  if($c.Path -match 'pid_(\d+)_'){
    $pidnum=[int]$matches[1]
    $v=[double]$c.CookedValue
    if($v -gt 0.05){
      if((-not $rows.ContainsKey($pidnum)) -or $v -gt $rows[$pidnum]){$rows[$pidnum]=$v}
    }
  }
}
$out=@()
foreach($k in $rows.Keys){$out += [pscustomobject]@{pid=[int]$k;usage=[math]::Round([double]$rows[$k],1)}}
$out | ConvertTo-Json -Compress
""".strip()
    executable = "powershell.exe" if os.name == "nt" else "powershell"
    result = _run_command([executable, "-NoProfile", "-NonInteractive", "-Command", script], timeout=10.0)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        payload = [payload]
    rows: dict[int, float] = {}
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                pid = int(item.get("pid"))
                usage = max(0.0, min(100.0, float(item.get("usage") or 0.0)))
            except (TypeError, ValueError):
                continue
            if usage > 0.05:
                rows[pid] = usage
    return rows


def _windows_gpu_dedicated_memory() -> dict[int, float]:
    """Best-effort dedicated GPU memory per PID from Windows performance counters."""
    if os.name != "nt":
        return {}
    script = r"""
$ErrorActionPreference='SilentlyContinue'
$s=(Get-Counter '\GPU Process Memory(*)\Dedicated Usage' -ErrorAction SilentlyContinue).CounterSamples
$rows=@{}
foreach($c in $s){
  if($c.Path -match 'pid_(\d+)_'){
    $pidnum=[int]$matches[1]
    $v=[double]$c.CookedValue
    if($v -gt 0){
      if(-not $rows.ContainsKey($pidnum)){$rows[$pidnum]=0.0}
      $rows[$pidnum]+=$v
    }
  }
}
$out=@()
foreach($k in $rows.Keys){$out += [pscustomobject]@{pid=[int]$k;bytes=[math]::Round([double]$rows[$k],0)}}
$out | ConvertTo-Json -Compress
""".strip()
    executable = "powershell.exe" if os.name == "nt" else "powershell"
    result = _run_command([executable, "-NoProfile", "-NonInteractive", "-Command", script], timeout=8.0)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        payload = [payload]
    rows: dict[int, float] = {}
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                pid = int(item.get("pid"))
                byte_count = max(0.0, float(item.get("bytes") or 0.0))
            except (TypeError, ValueError):
                continue
            if byte_count > 0:
                rows[pid] = byte_count / (1024 * 1024)
    return rows


def _usable_process_name(name: str) -> bool:
    clean = name.strip()
    if not clean:
        return False
    lowered = clean.casefold()
    if lowered.startswith("[") and lowered.endswith("]"):
        return False
    return lowered not in {"unknown", "n/a", "na", "insufficient permissions", "[insufficient permissions]"}


def _top_gpu(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    limit = max(1, min(int(args.get("limit", 5)), 20))
    usage = _windows_gpu_utilization()
    nvidia_memory = _nvidia_process_memory()
    windows_memory = _windows_gpu_dedicated_memory()
    pids = set(usage) | set(nvidia_memory) | set(windows_memory)

    grouped: dict[str, dict[str, Any]] = {}
    for pid in pids:
        nvidia_row = nvidia_memory.get(pid, {})
        name = str(nvidia_row.get("name") or _process_name(pid))
        if not _usable_process_name(name):
            continue
        gpu_percent = float(usage[pid]) if pid in usage and usage[pid] > 0.05 else None
        vram_candidates = [value for value in (nvidia_row.get("vram_mb"), windows_memory.get(pid)) if isinstance(value, (int, float)) and float(value) > 0]
        vram_mb = max(float(value) for value in vram_candidates) if vram_candidates else None
        if gpu_percent is None and vram_mb is None:
            continue
        key = name.casefold()
        row = grouped.setdefault(key, {"name": name, "gpu_percent": 0.0, "vram_mb": 0.0, "has_gpu_percent": False, "has_vram": False, "pids": []})
        if gpu_percent is not None:
            row["gpu_percent"] = max(float(row["gpu_percent"]), gpu_percent)
            row["has_gpu_percent"] = True
        if vram_mb is not None:
            row["vram_mb"] += vram_mb
            row["has_vram"] = True
        row["pids"].append(pid)

    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        rows.append({
            "name": row["name"],
            "gpu_percent": round(float(row["gpu_percent"]), 1) if row["has_gpu_percent"] else None,
            "vram_mb": round(float(row["vram_mb"]), 1) if row["has_vram"] else None,
            "instances": len(row["pids"]),
            "pids": tuple(row["pids"]),
        })
    rows.sort(key=lambda row: (row["gpu_percent"] or 0.0, row["vram_mb"] or 0.0), reverse=True)
    rows = rows[:limit]

    parts: list[str] = []
    for row in rows[:3]:
        if row["gpu_percent"] is not None and row["gpu_percent"] > 0.05:
            if row["vram_mb"] is not None and row["vram_mb"] >= 128:
                parts.append(f"{row['name']} at about {row['gpu_percent']:.0f} percent GPU and {row['vram_mb']:.0f} MB VRAM")
            else:
                parts.append(f"{row['name']} at about {row['gpu_percent']:.0f} percent GPU")
        elif row["vram_mb"] is not None:
            parts.append(f"{row['name']} using about {row['vram_mb']:.0f} MB of dedicated GPU memory")

    if parts:
        message = "The biggest GPU users I can measure right now are " + ", followed by ".join(parts) + "."
    else:
        snap = snapshot_resources(cpu_interval=0.05)
        overall = snap.gpus[0].utilization_percent if snap.gpus and snap.gpus[0].utilization_percent is not None else None
        if overall is not None:
            message = f"Overall GPU usage is about {overall:.0f} percent, but Windows isn't exposing a reliable per-process GPU breakdown right now."
        else:
            message = "Windows isn't exposing a reliable per-process GPU or VRAM breakdown right now."
    return ToolResult(
        "gpu.top_processes",
        True,
        message,
        {"processes": rows, "source": "windows_gpu_engine+windows_gpu_memory+nvidia_smi"},
    )


def _stop_process(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    pid = int(args.get("pid", 0))
    if pid <= 0 or pid == os.getpid():
        raise ValueError("a valid non-H.A.N.N.I. pid is required")
    proc = psutil.Process(pid)
    protected = {"system", "registry", "wininit.exe", "csrss.exe", "lsass.exe", "services.exe", "smss.exe"}
    name = proc.name().lower()
    if name in protected:
        raise PermissionError(f"refusing to stop protected Windows process {name}")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        proc.kill()
    return ToolResult("process.stop", True, f"Stopped {name}.", {"pid": pid, "name": name})


def _inspect_process(args, context, request):
    pid = int(args.get("pid", 0))
    if pid <= 0:
        raise ValueError("positive pid is required")
    exists = psutil.pid_exists(pid)
    return ToolResult("process.inspect", True, "Inspected process existence.", {"pid": pid, "exists": exists})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("process.inspect", "Check whether an exact PID still exists.", 0, 0, {"pid": int}, {"pid": "integer", "exists": "boolean"}, _inspect_process),
        ToolDefinition("system.stats", "Read local CPU, RAM and GPU usage/temperature for available adapters. Backend-dependent GPU readings may be unavailable; this is not per-process memory.", 0, 0, {}, {"cpu_percent": "number", "ram_percent": "number", "ram_used_gb": "number", "ram_total_gb": "number", "gpus": "array"}, _system_stats, retry_safe=True),
        ToolDefinition("system.battery", "Read the laptop battery percentage and charging state.", 0, 0, {}, {"available": "boolean", "percent": "number|null"}, _battery_status),
        ToolDefinition("process.list", "List local processes sorted by memory usage.", 0, 0, {"limit": int}, {"processes": "array"}, _process_list),
        ToolDefinition("process.top_memory", "Show the applications using the most RAM right now.", 0, 0, {"limit": int}, {"processes": "array"}, _top_memory, retry_safe=True),
        ToolDefinition("process.top_cpu", "Show the applications using the most CPU right now.", 0, 0, {"limit": int}, {"processes": "array"}, _top_cpu,
                       display_name='Top CPU Processes', aliases=('top cpu', 'cpu hog', 'high cpu'),
                       tags=('process', 'cpu', 'usage'), categories=('system', 'process', 'monitoring'),
                       argument_constraints={'limit': {'default': 5, 'minimum': 1, 'maximum': 20, 'nullable': False,
                                                       'description': 'Maximum applications to return.'}}),
        ToolDefinition('process.top_disk_io', 'Rank current process read/write I/O rates. Useful when files or apps load slowly, or disk activity seems high; this does not measure disk health or free space.',
                       0, 0, {'limit': int}, {'processes': 'array', 'skipped': 'integer', 'partial': 'boolean'}, _top_disk_io,
                       display_name='Top Process I/O', tags=('process', 'disk', 'io', 'read', 'write', 'usage'),
                       aliases=('disk io', 'hammering my disk', 'busiest disk process'),
                       categories=('system', 'process', 'monitoring'), timeout_seconds=5,
                       argument_constraints={'limit': {'default': 5, 'minimum': 1, 'maximum': 50, 'nullable': False}}),
        ToolDefinition("gpu.top_processes", "Show the processes using the most GPU/VRAM right now.", 0, 0, {"limit": int}, {"processes": "array"}, _top_gpu),
        ToolDefinition("process.stop", "Stop a local non-protected process by PID.", 2, 2, {"pid": int}, {"pid": "integer", "name": "string"}, _stop_process),
    )
