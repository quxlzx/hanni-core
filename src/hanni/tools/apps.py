"""Installed software, Windows services, startup items, and OS identity."""

from __future__ import annotations

import platform
import time
from datetime import datetime, timezone
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import as_rows, quote, run_powershell_json

_UNINSTALL_KEYS = (
    "HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
    "HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
    "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
)
_PROTECTED_SERVICES = {
    "winlogon", "lsass", "rpcss", "dcomlaunch", "wininit", "csrss", "services",
    "windefend", "securityhealthservice", "wscsvc", "mpssvc", "eventlog",
    "bfe", "trustedinstaller", "cryptsvc", "dnscache", "nsi", "power", "plugplay",
}


def _installed(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = str(args.get("query", "")).strip().casefold()
    limit = max(1, min(int(args.get("limit", 40)), 200))
    keys = ",".join(quote(key) for key in _UNINSTALL_KEYS)
    payload = run_powershell_json(
        f"Get-ItemProperty -Path {keys} -ErrorAction SilentlyContinue "
        "| Where-Object { $_.DisplayName } "
        "| Select-Object -Property DisplayName, DisplayVersion, Publisher, InstallDate "
        "| Sort-Object DisplayName -Unique | ConvertTo-Json -Compress",
        timeout=60, capability="app.list_installed")
    rows = [{"name": str(row.get("DisplayName", "")), "version": str(row.get("DisplayVersion") or ""),
             "publisher": str(row.get("Publisher") or ""), "install_date": str(row.get("InstallDate") or "")}
            for row in as_rows(payload)]
    if query:
        rows = [row for row in rows if query in row["name"].casefold() or query in row["publisher"].casefold()]
    found = bool(rows)
    return ToolResult("app.list_installed", True,
                      (f"{len(rows)} installed program(s) match '{query}'." if query
                       else f"{len(rows)} installed program(s) found.")
                      + (f" First: {rows[0]['name']} {rows[0]['version']}." if found else ""),
                      {"programs": rows[:limit], "total": len(rows), "query": query, "found": found})


def _service_list(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = str(args.get("query", "")).strip().casefold()
    status = str(args.get("status", "")).strip().casefold()
    limit = max(1, min(int(args.get("limit", 40)), 200))
    if status and status not in {"running", "stopped"}:
        raise ValueError("status must be running or stopped")
    payload = run_powershell_json(
        "Get-Service | Select-Object -Property Name, DisplayName, Status, StartType | ConvertTo-Json -Compress",
        timeout=40, capability="service.list")
    rows: list[dict[str, Any]] = []
    for row in as_rows(payload):
        state = str(row.get("Status", ""))
        state_text = {"1": "stopped", "4": "running"}.get(state, state.casefold())
        start = str(row.get("StartType", ""))
        rows.append({"name": str(row.get("Name", "")), "display_name": str(row.get("DisplayName") or ""),
                     "status": state_text,
                     "start_type": {"2": "automatic", "3": "manual", "4": "disabled"}.get(start, start.casefold())})
    if query:
        rows = [row for row in rows if query in row["name"].casefold() or query in row["display_name"].casefold()]
    if status:
        rows = [row for row in rows if row["status"] == status]
    running = sum(1 for row in rows if row["status"] == "running")
    return ToolResult("service.list", True,
                      f"{len(rows)} matching service(s); {running} running.",
                      {"services": rows[:limit], "total": len(rows), "running": running})


def _service_control(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    name = str(args.get("name", "")).strip()
    action = str(args.get("action", "")).strip().casefold()
    if not name or len(name) > 80 or not all(ch.isalnum() or ch in "_-. " for ch in name):
        raise ValueError("service name must be a simple Windows service name")
    if action not in {"start", "stop", "restart"}:
        raise ValueError("action must be start, stop, or restart")
    if name.casefold() in _PROTECTED_SERVICES:
        raise ValueError(f"{name} is a protected Windows service and cannot be controlled by H.A.N.N.I.")
    verb = {"start": "Start-Service", "stop": "Stop-Service", "restart": "Restart-Service"}[action]
    run_powershell_json(f"{verb} -Name {quote(name)} -ErrorAction Stop; "
                        f"Get-Service -Name {quote(name)} | Select-Object Name, Status | ConvertTo-Json -Compress",
                        timeout=60, capability="service.control")
    payload = run_powershell_json(
        f"Get-Service -Name {quote(name)} | Select-Object Name, Status | ConvertTo-Json -Compress",
        timeout=30, capability="service.control")
    rows = as_rows(payload)
    state = str(rows[0].get("Status", "")) if rows else ""
    state_text = {"1": "stopped", "4": "running"}.get(state, state.casefold())
    expected = "stopped" if action == "stop" else "running"
    return ToolResult("service.control", state_text == expected, f"Service {name} after {action}: {state_text or 'unknown'}.",
                      {"name": name, "action": action, "status": state_text})


def _protected_service_reason(args: Mapping[str, Any]) -> str | None:
    return f"changing the state of Windows service {args.get('name')} affects system behaviour"


def _startup_list(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    limit = max(1, min(int(args.get("limit", 40)), 200))
    payload = run_powershell_json(
        "Get-CimInstance -ClassName Win32_StartupCommand "
        "| Select-Object -Property Name, Command, Location, User | ConvertTo-Json -Compress",
        timeout=40, capability="startup.list")
    rows = [{"name": str(row.get("Name") or ""), "command": str(row.get("Command") or ""),
             "location": str(row.get("Location") or ""), "user": str(row.get("User") or "")}
            for row in as_rows(payload)]
    return ToolResult("startup.list", True,
                      f"{len(rows)} program(s) are configured to start with Windows.",
                      {"items": rows[:limit], "total": len(rows)})


def _os_info(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    uptime_seconds = int(time.time() - psutil.boot_time())
    return ToolResult("system.os_info", True,
                      f"{platform.system()} {platform.release()} (build {platform.version()}) on "
                      f"{platform.machine()}, {psutil.cpu_count(logical=True)} logical CPUs, Python {platform.python_version()}.",
                      {"system": platform.system(), "release": platform.release(), "version": platform.version(),
                       "machine": platform.machine(), "hostname": platform.node(),
                       "logical_cpus": psutil.cpu_count(logical=True) or 0,
                       "physical_cpus": psutil.cpu_count(logical=False) or 0,
                       "python_version": platform.python_version(),
                       "boot_time_utc": boot.isoformat(), "uptime_seconds": uptime_seconds})


def _uptime(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    seconds = int(time.time() - psutil.boot_time())
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = [f"{days}d" if days else "", f"{hours}h" if hours or days else "", f"{minutes}m"]
    pretty = " ".join(p for p in parts if p)
    return ToolResult("system.uptime", True, f"This machine has been up for {pretty}.",
                      {"uptime_seconds": seconds, "pretty": pretty, "days": days, "hours": hours, "minutes": minutes,
                       "boot_time_utc": datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).isoformat()})


def _process_uptime(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    name = str(args.get("name", "")).strip().casefold()
    pid = int(args.get("pid", 0) or 0)
    if not name and pid <= 0:
        raise ValueError("name or a positive pid is required")
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "create_time"]):
        info = proc.info
        if pid and info["pid"] != pid:
            continue
        if name and name not in str(info.get("name", "")).casefold():
            continue
        started = float(info.get("create_time") or 0)
        rows.append({"pid": info["pid"], "name": info.get("name", ""),
                     "running_seconds": int(time.time() - started) if started else 0,
                     "started_utc": datetime.fromtimestamp(started, tz=timezone.utc).isoformat() if started else ""})
    rows.sort(key=lambda row: -row["running_seconds"])
    return ToolResult("process.uptime", bool(rows),
                      f"{len(rows)} matching process(es)."
                      + (f" {rows[0]['name']} (pid {rows[0]['pid']}) has run {rows[0]['running_seconds'] // 60} minute(s)." if rows else ""),
                      {"processes": rows[:20], "found": bool(rows)})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("app.list_installed", "List installed Windows programs, optionally filtered, to answer whether something is installed and at what version.",
                       0, 0, {"query": str, "limit": int}, {"programs": "array", "total": "integer", "found": "boolean"}, _installed,
                       timeout_seconds=90, side_effect="read",
                       tags=("installed", "programs", "software", "apps", "version", "uninstall", "have"),
                       aliases=("do i have installed", "what version is installed", "list my programs")),
        ToolDefinition("service.list", "List Windows services with running state and start type.",
                       0, 0, {"query": str, "status": str, "limit": int},
                       {"services": "array", "total": "integer", "running": "integer"}, _service_list,
                       timeout_seconds=60, side_effect="read",
                       tags=("service", "services", "windows", "background", "daemon", "running"),
                       aliases=("is the service running", "list services")),
        ToolDefinition("service.control", "Start, stop, or restart one non-protected Windows service. Always requires explicit confirmation.",
                       3, 3, {"name": str, "action": str}, {"name": "string", "status": "string"}, _service_control,
                       timeout_seconds=120, side_effect="external_action",
                       requires_confirmation_if=_protected_service_reason,
                       tags=("service", "restart", "start", "stop", "windows", "fix"),
                       aliases=("restart the service", "stop that service")),
        ToolDefinition("startup.list", "List the programs configured to launch when Windows starts.",
                       0, 0, {"limit": int}, {"items": "array", "total": "integer"}, _startup_list,
                       timeout_seconds=60, side_effect="read",
                       tags=("startup", "boot", "launch", "autostart", "slow", "login"),
                       aliases=("what starts with my pc", "startup programs", "why is boot slow")),
        ToolDefinition("system.os_info", "Read the Windows edition, build, CPU count, hostname, and Python version.",
                       0, 0, {}, {"system": "string", "release": "string", "hostname": "string"}, _os_info,
                       side_effect="read", tags=("os", "windows", "version", "build", "machine", "specs", "hostname"),
                       aliases=("what windows am i on", "my specs", "system info")),
        ToolDefinition("system.uptime", "Report how long this machine has been running since boot.",
                       0, 0, {}, {"uptime_seconds": "integer", "pretty": "string"}, _uptime,
                       side_effect="read", tags=("uptime", "boot", "restart", "how long", "running"),
                       aliases=("when did i last reboot", "how long has my pc been on")),
        ToolDefinition("process.uptime", "Report how long a named process or PID has been running.",
                       0, 0, {"name": str, "pid": int}, {"processes": "array", "found": "boolean"}, _process_uptime,
                       side_effect="read", tags=("process", "uptime", "running", "since", "started"),
                       aliases=("how long has it been open", "when did that start")),
    )
