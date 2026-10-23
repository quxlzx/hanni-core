"""Battery detail, power plans, and sleep/idle behaviour.

Read paths use ``psutil`` and CIM queries; the two capabilities that change how
the machine behaves (active power plan, idle timeouts) are Level 2 and go
through fixed ``powercfg`` templates with validated arguments.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import quote, require_windows, run_powershell

_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


def _battery_detail(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    battery = psutil.sensors_battery()
    if battery is None:
        return ToolResult("power.battery_detail", False, "Battery measurements are unavailable on this machine.",
                          {"present": False, "percent": None, "plugged_in": None,
                           "minutes_remaining": None, "state": "unknown"})
    minutes = (int(battery.secsleft // 60)
               if battery.secsleft not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN)
               else -1)
    state = "charging" if battery.power_plugged else "on battery"
    estimate = f", about {minutes // 60}h {minutes % 60}m remaining" if minutes > 0 else ""
    return ToolResult("power.battery_detail", True,
                      f"Battery is at {round(battery.percent)}% and {state}{estimate}.",
                      {"present": True, "percent": round(battery.percent, 1),
                       "plugged_in": bool(battery.power_plugged), "minutes_remaining": minutes,
                       "state": state, "low": battery.percent < 20 and not battery.power_plugged})


def _plans(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    text = run_powershell("powercfg /list", timeout=25, capability="power.plans")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = re.search(r"([0-9a-fA-F-]{36})\s*\(([^)]*)\)(\s*\*)?", line)
        if match:
            rows.append({"guid": match.group(1), "name": match.group(2).strip(),
                         "active": bool(match.group(3))})
    active_row = next((row for row in rows if row["active"]), None)
    active = active_row["name"] if active_row else ""
    # Windows' built-in Power saver GUID has a stable meaning across localized
    # display names. Custom plans remain unknown rather than being diagnosed.
    power_saver = bool(active_row and active_row["guid"].casefold() ==
                       "a1841308-3541-4fab-bc81-f71556f20b4a")
    intent = "energy_saving" if power_saver else "unknown"
    return ToolResult("power.plans", True,
                      f"{len(rows)} power plan(s); active plan is {active or 'unknown'}."
                      + (" Power saver can limit performance, but this does not prove it caused the slowdown."
                         if power_saver else ""),
                      {"plans": rows, "active": active, "active_plan_intent": intent,
                       "performance_limit_possible": power_saver,
                       "causal_status": "possible_not_verified" if power_saver else "unknown"})


def _set_plan(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    guid = str(args.get("guid", "")).strip()
    name = str(args.get("name", "") or "").strip()
    if not guid and not name:
        raise ValueError("provide the plan guid, or its name as shown by power.plans")
    if guid and not _GUID_RE.match(guid):
        raise ValueError("guid must be a plan GUID as reported by power.plans")
    require_windows("power.set_plan")
    if not guid:
        listing = _plans({}, context, request)
        match = next((row for row in listing.data["plans"]
                      if row["name"].casefold() == name.casefold()), None)
        if match is None:
            raise ValueError(f"no power plan named {name!r}; run power.plans to see the options")
        guid = match["guid"]
    run_powershell(f"powercfg /setactive {quote(guid)}", timeout=25, capability="power.set_plan")
    listing = _plans({}, context, request)
    active_row = next((row for row in listing.data["plans"] if row["active"]), None)
    active_guid = active_row["guid"] if active_row else None
    verified = bool(active_guid and active_guid.casefold() == guid.casefold())
    return ToolResult("power.set_plan", verified,
                      f"Active power plan is now {listing.data['active']}." if verified
                      else "The requested power plan was not observed as active after the change.",
                      {"guid": guid, "active": listing.data["active"],
                       "active_guid": active_guid, "verified": verified})


def _idle_settings(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    text = run_powershell("powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE; "
                          "powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE",
                          timeout=30, capability="power.idle_settings")
    values = [int(match, 16) for match in re.findall(r"Current AC Power Setting Index:\s*0x([0-9a-fA-F]+)", text)]
    screen = values[0] // 60 if len(values) > 0 else -1
    sleep = values[1] // 60 if len(values) > 1 else -1
    describe = lambda minutes: "never" if minutes == 0 else (f"{minutes} minute(s)" if minutes > 0 else "unknown")
    return ToolResult("power.idle_settings", True,
                      f"On AC power the screen turns off after {describe(screen)} and the machine sleeps after {describe(sleep)}.",
                      {"screen_off_minutes": screen, "sleep_minutes": sleep})


def _set_idle(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    target = str(args.get("target", "")).casefold()
    minutes = int(args.get("minutes", -1))
    if target not in {"screen", "sleep"}:
        raise ValueError("target must be screen or sleep")
    if not 0 <= minutes <= 600:
        raise ValueError("minutes must be between 0 (never) and 600")
    require_windows("power.set_idle")
    command = "monitor-timeout-ac" if target == "screen" else "standby-timeout-ac"
    run_powershell(f"powercfg /change {command} {minutes}", timeout=25, capability="power.set_idle")
    settings = _idle_settings({}, context, request)
    applied = settings.data["screen_off_minutes" if target == "screen" else "sleep_minutes"]
    verified = applied == minutes
    return ToolResult("power.set_idle", verified,
                      (f"{'Screen off' if target == 'screen' else 'Sleep'} on AC power is now "
                       + ("never." if applied == 0 else f"{applied} minute(s).")) if verified
                      else "The requested AC idle timeout could not be verified after the change.",
                      {"target": target, "minutes": applied, "requested_minutes": minutes,
                       "verified": verified})


def _battery_report(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    destination = str(args.get("destination", "")).strip()
    path = Path(destination).expanduser() if destination else None
    if path is None or not path.is_absolute() or path.suffix.casefold() != ".html":
        raise ValueError("destination must be an absolute .html path for the generated report")
    require_windows("power.battery_report")
    path.parent.mkdir(parents=True, exist_ok=True)
    run_powershell(f"powercfg /batteryreport /output {quote(str(path))}",
                   timeout=60, capability="power.battery_report")
    exists = path.is_file()
    return ToolResult("power.battery_report", exists,
                      f"Battery health report written to {path}." if exists
                      else "Windows did not produce a battery report on this machine.",
                      {"destination": str(path), "written": exists,
                       "size_kb": round(path.stat().st_size / 1024, 1) if exists else 0.0})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("power.battery_detail", "Read battery percentage, charging state, and estimated time remaining.",
                       0, 0, {}, {"present": "boolean", "percent": "number|null", "plugged_in": "boolean|null", "minutes_remaining": "integer|null"},
                       _battery_detail, side_effect="read",
                       tags=("battery", "charge", "charging", "remaining", "power", "unplugged"),
                       aliases=("how long will my battery last", "am i charging", "battery time left")),
        ToolDefinition("power.plans", "Read active Windows power plan. Built-in Power saver may limit performance; a plan alone does not prove the cause of slowness.",
                       0, 0, {}, {"plans": "array", "active": "string", "active_plan_intent": "string",
                                  "performance_limit_possible": "boolean"}, _plans,
                       timeout_seconds=40, side_effect="read",
                       tags=("power", "plan", "balanced", "performance", "saver", "profile"),
                       aliases=("what power plan am i on", "power mode")),
        ToolDefinition("power.set_plan", "Switch the active Windows power plan by GUID or name.",
                       2, 2, {"guid": str, "name": str}, {"guid": "string", "active": "string"}, _set_plan,
                       timeout_seconds=60, side_effect="external_action",
                       tags=("power", "plan", "performance", "saver", "switch", "battery", "mode"),
                       aliases=("switch to high performance", "change power plan", "battery saver mode")),
        ToolDefinition("power.idle_settings", "Read how long before the screen turns off and the machine sleeps on AC power.",
                       0, 0, {}, {"screen_off_minutes": "integer", "sleep_minutes": "integer"}, _idle_settings,
                       timeout_seconds=45, side_effect="read",
                       tags=("sleep", "screen", "timeout", "idle", "power", "off", "lock"),
                       aliases=("when does my screen turn off", "sleep timeout")),
        ToolDefinition("power.set_idle", "Set the AC-power screen-off or sleep timeout in minutes (0 means never).",
                       2, 2, {"target": str, "minutes": int}, {"target": "string", "minutes": "integer"}, _set_idle,
                       timeout_seconds=45, side_effect="external_action",
                       tags=("sleep", "screen", "timeout", "idle", "stop", "keep", "awake", "power"),
                       aliases=("stop my screen turning off", "keep my pc awake", "change sleep timeout")),
        ToolDefinition("power.battery_report", "Generate the Windows battery health report to a chosen .html file.",
                       2, 2, {"destination": str}, {"destination": "string", "written": "boolean"},
                       _battery_report, timeout_seconds=90, side_effect="reversible_write",
                       tags=("battery", "health", "report", "wear", "capacity", "degraded"),
                       aliases=("is my battery healthy", "battery health report")),
    )
