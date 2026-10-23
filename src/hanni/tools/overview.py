"""Composite machine snapshot and process lookup.

``system.performance`` answers "how is my PC doing" in one measured call so the
Supervisor does not have to chain four telemetry capabilities and stitch the
result together. Every number comes from a deterministic local reading.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult


def _gb(value: float) -> float:
    return round(value / 1024 ** 3, 2)


def _performance(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    try:
        battery = psutil.sensors_battery()
    except (OSError, NotImplementedError):
        # Some desktops/VMs and minimal Linux test environments expose no
        # power-supply backend at all. Absence of a battery is not a telemetry
        # failure; report the rest of the snapshot normally.
        battery = None
    uptime_seconds = int(time.time() - psutil.boot_time())

    drives = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        drives.append({"drive": part.mountpoint, "percent_used": round(usage.percent, 1),
                       "free_gb": _gb(usage.free)})

    top = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        info = proc.info
        rss = getattr(info.get("memory_info"), "rss", 0) or 0
        top.append({"pid": info["pid"], "name": info.get("name", ""), "memory_gb": _gb(rss)})
    top.sort(key=lambda row: -row["memory_gb"])

    pressure = []
    if cpu >= 85:
        pressure.append("CPU is saturated")
    if memory.percent >= 85:
        pressure.append("RAM is nearly full")
    for drive in drives:
        if drive["percent_used"] >= 90:
            pressure.append(f"{drive['drive']} is {drive['percent_used']}% full")
    if battery is not None and not battery.power_plugged and battery.percent < 20:
        pressure.append(f"battery is low at {round(battery.percent)}%")

    healthy = not pressure
    summary = (f"CPU {round(cpu)}%, RAM {round(memory.percent)}% "
               f"({_gb(memory.used)} of {_gb(memory.total)} GB), up {uptime_seconds // 3600}h. ")
    summary += ("No measured CPU, RAM, storage-capacity, or low-battery pressure. "
                "Disk I/O, GPU load, and power plan are not checked here." if healthy
                else "Pressure: " + "; ".join(pressure) + ".")
    return ToolResult("system.performance", True, summary,
                      {"cpu_percent": round(cpu, 1), "ram_percent": round(memory.percent, 1),
                       "ram_used_gb": _gb(memory.used), "ram_total_gb": _gb(memory.total),
                       "uptime_seconds": uptime_seconds, "drives": drives,
                       "battery_percent": round(battery.percent, 1) if battery else -1,
                       "plugged_in": bool(battery.power_plugged) if battery else True,
                       "top_memory": top[:5], "healthy": healthy, "pressure": pressure,
                       "cpu_pressure": "saturated" if cpu >= 85 else "elevated" if cpu >= 70 else "normal",
                       "memory_pressure": "critical" if memory.percent >= 90 else "high" if memory.percent >= 85 else "normal",
                       "snapshot_scope": "CPU, RAM, storage capacity, low battery; excludes disk I/O, GPU load, and power plan"})


def _find_process(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    name = str(args.get("name", "")).strip().casefold()
    limit = max(1, min(int(args.get("limit", 20)), 100))
    if len(name) < 2:
        raise ValueError("name must be at least 2 characters")
    rows = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "create_time"]):
        info = proc.info
        process_name = str(info.get("name") or "")
        if name not in process_name.casefold():
            continue
        rss = getattr(info.get("memory_info"), "rss", 0) or 0
        rows.append({"pid": info["pid"], "name": process_name, "memory_gb": _gb(rss),
                     "running_minutes": int((time.time() - float(info.get("create_time") or time.time())) // 60)})
    rows.sort(key=lambda row: -row["memory_gb"])
    running = bool(rows)
    return ToolResult("process.find", running,
                      f"{len(rows)} process(es) match '{name}'."
                      + (f" Largest is pid {rows[0]['pid']} using {rows[0]['memory_gb']} GB." if running
                         else " It does not appear to be running."),
                      {"query": name, "processes": rows[:limit], "running": running, "count": len(rows)})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("system.performance", "Current CPU/RAM, storage capacity, battery and top-memory snapshot. Healthy here does not rule out disk I/O, GPU load, or a power-plan limit.",
                       0, 0, {}, {"cpu_percent": "number", "ram_percent": "number", "healthy": "boolean",
                                  "pressure": "array", "cpu_pressure": "string", "memory_pressure": "string",
                                  "snapshot_scope": "string"}, _performance,
                       timeout_seconds=30, side_effect="read",
                       tags=("performance", "slow", "health", "snapshot", "overall", "doing", "lag",
                             "struggling", "system", "check"),
                       aliases=("how is my pc doing", "why is my computer slow", "is everything ok",
                                "check my system", "how is my machine")),
        ToolDefinition("process.find", "Find running processes by name and report PID, memory, and how long each has run.",
                       0, 0, {"name": str, "limit": int},
                       {"processes": "array", "running": "boolean", "count": "integer"}, _find_process,
                       side_effect="read",
                       tags=("process", "running", "open", "find", "is", "pid", "app"),
                       aliases=("is chrome running", "is that app open", "find that process")),
    )
