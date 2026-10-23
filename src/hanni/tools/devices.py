"""Read-only hardware inventory: audio endpoints, Bluetooth, USB, printers, disks."""

from __future__ import annotations

from typing import Any, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import as_rows, run_powershell_json

_PNP_STATUS = {"OK": "working", "Error": "error", "Degraded": "degraded", "Unknown": "unknown"}


def _pnp_query(class_filter: str, capability: str) -> list[dict[str, Any]]:
    payload = run_powershell_json(
        f"Get-PnpDevice -Class {class_filter} -ErrorAction SilentlyContinue "
        "| Select-Object FriendlyName, Status, Present, InstanceId | ConvertTo-Json -Compress",
        timeout=60, capability=capability)
    rows = []
    for row in as_rows(payload):
        status = str(row.get("Status") or "")
        rows.append({"name": str(row.get("FriendlyName") or ""),
                     "status": _PNP_STATUS.get(status, status.casefold()),
                     "present": bool(row.get("Present")),
                     "connected": status == "OK"})
    rows.sort(key=lambda item: (not item["connected"], item["name"]))
    return rows


def _audio_devices(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    rows = _pnp_query("AudioEndpoint", "device.audio")
    working = [row["name"] for row in rows if row["connected"]]
    return ToolResult("device.audio", True,
                      f"{len(rows)} audio endpoint(s); {len(working)} working"
                      + (f", including {working[0]}." if working else "."),
                      {"devices": rows[:40], "working": working[:20], "total": len(rows),
                       "note": "changing the default output device is not a V1 capability"})


def _bluetooth(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    rows = _pnp_query("Bluetooth", "device.bluetooth")
    connected = [row["name"] for row in rows if row["connected"]]
    return ToolResult("device.bluetooth", True,
                      f"{len(rows)} Bluetooth device(s) known; {len(connected)} currently connected"
                      + (f": {', '.join(connected[:5])}." if connected else "."),
                      {"devices": rows[:40], "connected": connected, "total": len(rows)})


def _usb(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    rows = _pnp_query("USB", "device.usb")
    problems = [row["name"] for row in rows if row["present"] and not row["connected"]]
    return ToolResult("device.usb", True,
                      f"{len(rows)} USB device(s)."
                      + (f" Reporting a problem: {', '.join(problems[:4])}." if problems else ""),
                      {"devices": rows[:40], "problem_devices": problems, "total": len(rows)})


def _printers(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "Get-Printer -ErrorAction SilentlyContinue | Select-Object Name, PrinterStatus, Default, PortName "
        "| ConvertTo-Json -Compress", timeout=60, capability="device.printers")
    rows = [{"name": str(row.get("Name") or ""), "status": str(row.get("PrinterStatus") or ""),
             "default": bool(row.get("Default")), "port": str(row.get("PortName") or "")}
            for row in as_rows(payload)]
    default = next((row["name"] for row in rows if row["default"]), "")
    return ToolResult("device.printers", True,
                      f"{len(rows)} printer(s); default is {default or 'not set'}.",
                      {"printers": rows[:40], "default": default, "total": len(rows)})


def _disk_health(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "Get-PhysicalDisk -ErrorAction SilentlyContinue "
        "| Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus, Size "
        "| ConvertTo-Json -Compress", timeout=60, capability="device.disk_health")
    rows = []
    for row in as_rows(payload):
        rows.append({"name": str(row.get("FriendlyName") or ""),
                     "media_type": str(row.get("MediaType") or ""),
                     "health": str(row.get("HealthStatus") or ""),
                     "operational": str(row.get("OperationalStatus") or ""),
                     "size_gb": round(int(row.get("Size") or 0) / 1024 ** 3, 1)})
    unhealthy = [row["name"] for row in rows
                 if str(row["health"]).casefold() not in {"healthy", "0", "", "unknown"}]
    unknown = [row["name"] for row in rows if str(row["health"]).casefold() in {"", "unknown"}]
    available = bool(rows) and not unknown
    return ToolResult("device.disk_health", available and not unhealthy,
                      f"{len(rows)} physical disk(s); "
                      + (f"health warning on {', '.join(unhealthy)}." if unhealthy
                         else "health measurements are unavailable or incomplete." if not available
                         else "all report healthy."),
                      {"disks": rows, "unhealthy": unhealthy, "unknown": unknown, "available": available})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("device.audio", "List Windows audio endpoints and which are working.",
                       0, 0, {}, {"devices": "array", "working": "array"}, _audio_devices,
                       timeout_seconds=90, side_effect="read",
                       tags=("audio", "device", "speaker", "headphones", "microphone", "output", "endpoint"),
                       aliases=("what are my speakers", "audio devices", "is my headset connected")),
        ToolDefinition("device.bluetooth", "List known Bluetooth devices and which are currently connected.",
                       0, 0, {}, {"devices": "array", "connected": "array"}, _bluetooth,
                       timeout_seconds=90, side_effect="read",
                       tags=("bluetooth", "paired", "connected", "headphones", "device", "wireless"),
                       aliases=("are my headphones connected", "bluetooth devices")),
        ToolDefinition("device.usb", "List USB devices and flag any reporting a problem.",
                       0, 0, {}, {"devices": "array", "problem_devices": "array"}, _usb,
                       timeout_seconds=90, side_effect="read",
                       tags=("usb", "device", "plugged", "drive", "peripheral", "problem"),
                       aliases=("what is plugged in", "usb devices")),
        ToolDefinition("device.printers", "List installed printers and the default one.",
                       0, 0, {}, {"printers": "array", "default": "string"}, _printers,
                       timeout_seconds=90, side_effect="read",
                       tags=("printer", "print", "default", "device"),
                       aliases=("what printers do i have", "default printer")),
        ToolDefinition("device.disk_health", "Read physical disk media type and SMART health status.",
                       0, 0, {}, {"disks": "array", "unhealthy": "array"}, _disk_health,
                       timeout_seconds=90, side_effect="read",
                       tags=("disk", "ssd", "hdd", "health", "smart", "failing", "hardware", "drive"),
                       aliases=("is my ssd healthy", "disk health", "is my drive failing")),
    )
