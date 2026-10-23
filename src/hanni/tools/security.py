"""Read-only Windows security and update posture.

Everything here observes. H.A.N.N.I. does not disable Defender, alter firewall
rules, manage BitLocker keys, or install updates in V1 - those are exactly the
Level 3 security changes the Master Spec calls dangerous, and they stay outside
the registry until an owner-approved decision adds them (D-0027).
"""

from __future__ import annotations

from typing import Any, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import as_rows, run_powershell_json


def _provider_bool(value: Any) -> bool | None:
    """CIM/PowerShell boolean and 0/1 enum values; other types are unknown."""
    if isinstance(value, bool):
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    return None


def _defender(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "Get-MpComputerStatus | Select-Object AMServiceEnabled, RealTimeProtectionEnabled, "
        "AntivirusSignatureLastUpdated, QuickScanEndTime, AntivirusSignatureVersion "
        "| ConvertTo-Json -Compress", timeout=45, capability="security.defender")
    rows = as_rows(payload)
    row = rows[0] if rows else {}
    realtime = _provider_bool(row.get("RealTimeProtectionEnabled"))
    available = realtime is not None
    return ToolResult("security.defender", available,
                      (f"Microsoft Defender real-time protection is {'on' if realtime else 'OFF'}; "
                       f"signature version {row.get('AntivirusSignatureVersion') or 'unknown'}.") if available
                      else "Microsoft Defender protection measurements are unavailable; protection state is unknown.",
                      {"service_enabled": _provider_bool(row.get("AMServiceEnabled")),
                       "realtime_protection": realtime,
                       "available": available,
                       "signature_version": str(row.get("AntivirusSignatureVersion") or ""),
                       "signatures_updated": str(row.get("AntivirusSignatureLastUpdated") or ""),
                       "last_quick_scan": str(row.get("QuickScanEndTime") or "")})


def _firewall(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction | ConvertTo-Json -Compress",
        timeout=45, capability="security.firewall")
    rows = [{"profile": str(row.get("Name") or ""), "enabled": _provider_bool(row.get("Enabled")),
             "default_inbound": str(row.get("DefaultInboundAction") or "")} for row in as_rows(payload)]
    disabled = [row["profile"] for row in rows if row["enabled"] is False]
    available = bool(rows) and all(row["enabled"] is not None for row in rows)
    return ToolResult("security.firewall", available,
                      f"{len(rows)} firewall profile(s); "
                      + ("profile protection measurements are unavailable or incomplete." if not available
                         else f"disabled on: {', '.join(disabled)}." if disabled else "all profiles enabled."),
                      {"profiles": rows, "all_enabled": not disabled if available else None,
                       "disabled_profiles": disabled, "available": available})


def _bitlocker(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "Get-BitLockerVolume -ErrorAction SilentlyContinue "
        "| Select-Object MountPoint, VolumeStatus, ProtectionStatus, EncryptionPercentage "
        "| ConvertTo-Json -Compress", timeout=45, capability="security.bitlocker")
    rows = [{"mount_point": str(row.get("MountPoint") or ""),
             "status": str(row.get("VolumeStatus") or ""),
             "protected": str(row.get("ProtectionStatus") or "") in {"1", "On"},
             "encryption_percent": int(row.get("EncryptionPercentage") or 0)} for row in as_rows(payload)]
    protected = [row["mount_point"] for row in rows if row["protected"]]
    return ToolResult("security.bitlocker", True,
                      f"{len(rows)} volume(s) reported; encryption protection on: "
                      + (", ".join(protected) if protected else "none")
                      + ". Recovery keys are never read or stored by H.A.N.N.I.",
                      {"volumes": rows, "protected_volumes": protected})


def _updates(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    limit = max(1, min(int(args.get("limit", 15)), 100))
    payload = run_powershell_json(
        "Get-HotFix | Sort-Object InstalledOn -Descending "
        "| Select-Object -First 50 HotFixID, Description, InstalledOn | ConvertTo-Json -Compress",
        timeout=60, capability="security.updates")
    rows = [{"id": str(row.get("HotFixID") or ""), "description": str(row.get("Description") or ""),
             "installed_on": str(row.get("InstalledOn") or "")} for row in as_rows(payload)]
    return ToolResult("security.updates", True,
                      f"{len(rows)} installed update(s) recorded."
                      + (f" Most recent: {rows[0]['id']} on {rows[0]['installed_on'][:10]}." if rows else ""),
                      {"updates": rows[:limit], "total": len(rows),
                       "note": "installed history only; H.A.N.N.I. does not install updates in V1"})


def _pending_reboot(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "@{ cbs = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending'); "
        "wu = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'); "
        "rename = ((Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager' "
        "-Name PendingFileRenameOperations -ErrorAction SilentlyContinue) -ne $null) } | ConvertTo-Json -Compress",
        timeout=45, capability="security.pending_reboot")
    rows = as_rows(payload)
    row = rows[0] if rows else {}
    states = {key: _provider_bool(row.get(key)) for key in ("cbs", "wu", "rename")}
    reasons = [name for name, key in (("servicing", "cbs"), ("windows update", "wu"),
                                      ("pending file rename", "rename")) if states[key] is True]
    available = bool(reasons) or all(value is not None for value in states.values())
    pending = bool(reasons) if available else None
    return ToolResult("security.pending_reboot", available,
                      f"A restart is pending ({', '.join(reasons)})." if pending
                      else "No restart is pending." if available
                      else "Restart-pending measurements are unavailable; restart state is unknown.",
                      {"pending": pending, "reasons": reasons, "available": available})


def _event_errors(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    hours = max(1, min(int(args.get("hours", 24)), 24 * 14))
    limit = max(1, min(int(args.get("limit", 15)), 100))
    log = str(args.get("log", "System")).strip()
    if log not in {"System", "Application"}:
        raise ValueError("log must be System or Application")
    payload = run_powershell_json(
        "try { $hanniEvents = @("
        f"Get-WinEvent -FilterHashtable @{{ LogName='{log}'; Level=1,2; "
        f"StartTime=(Get-Date).AddHours(-{hours}) }} -MaxEvents 100 -ErrorAction Stop"
        ") } catch { "
        "if ($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*') { throw }; "
        "$hanniEvents = @() }; "
        "ConvertTo-Json -InputObject @($hanniEvents | "
        "Select-Object TimeCreated, Id, ProviderName, LevelDisplayName, Message) -Compress",
        timeout=90, capability="system.event_errors")
    rows = []
    for row in as_rows(payload):
        message = " ".join(str(row.get("Message") or "").split())[:300]
        rows.append({"time": str(row.get("TimeCreated") or ""), "id": row.get("Id"),
                     "provider": str(row.get("ProviderName") or ""),
                     "level": str(row.get("LevelDisplayName") or ""), "message": message})
    providers = sorted({row["provider"] for row in rows})
    return ToolResult("system.event_errors", True,
                      f"{len(rows)} error/critical entry/entries in the {log} log over the last {hours} hour(s)"
                      + (f"; sources include {', '.join(providers[:4])}." if providers else "."),
                      {"log": log, "hours": hours, "events": rows[:limit], "total": len(rows),
                       "providers": providers})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("security.defender", "Read Microsoft Defender real-time protection state and signature freshness.",
                       0, 0, {}, {"realtime_protection": "boolean|null", "signature_version": "string"}, _defender,
                       timeout_seconds=60, side_effect="read",
                       tags=("defender", "antivirus", "virus", "protection", "security", "scan", "safe"),
                       aliases=("is my antivirus on", "am i protected", "defender status")),
        ToolDefinition("security.firewall", "Read whether each Windows Firewall profile is enabled and its default inbound action.",
                       0, 0, {}, {"profiles": "array", "all_enabled": "boolean|null"}, _firewall,
                       timeout_seconds=60, side_effect="read",
                       tags=("firewall", "security", "inbound", "blocked", "network", "profile"),
                       aliases=("is my firewall on", "firewall status")),
        ToolDefinition("security.bitlocker", "Read BitLocker volume encryption status. Recovery keys are never read.",
                       0, 0, {}, {"volumes": "array", "protected_volumes": "array"}, _bitlocker,
                       timeout_seconds=60, side_effect="read",
                       tags=("bitlocker", "encryption", "encrypted", "drive", "security", "protection"),
                       aliases=("is my drive encrypted", "bitlocker status")),
        ToolDefinition("security.updates", "List recently installed Windows updates and hotfixes.",
                       0, 0, {"limit": int}, {"updates": "array", "total": "integer"}, _updates,
                       timeout_seconds=90, side_effect="read",
                       tags=("update", "updates", "hotfix", "patch", "windows", "installed", "recent"),
                       aliases=("when did windows last update", "recent updates")),
        ToolDefinition("security.pending_reboot", "Report whether Windows is waiting on a restart to finish servicing or updates.",
                       0, 0, {}, {"pending": "boolean|null", "reasons": "array"}, _pending_reboot,
                       timeout_seconds=60, side_effect="read",
                       tags=("reboot", "restart", "pending", "update", "required", "waiting"),
                       aliases=("do i need to restart", "is a reboot pending")),
        ToolDefinition("system.event_errors", "Read recent error and critical entries from the Windows System or Application event log.",
                       0, 0, {"hours": int, "limit": int, "log": str},
                       {"events": "array", "total": "integer"}, _event_errors,
                       timeout_seconds=120, side_effect="read",
                       tags=("error", "errors", "crash", "event", "log", "problem", "wrong", "bluescreen", "why"),
                       aliases=("what went wrong", "why did my pc crash", "any errors recently")),
    )
