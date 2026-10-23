"""Local time, scheduled-task visibility, and desktop notifications.

Time comes from the operating system clock, never from the conversational
model. Notifications are best-effort local toasts and carry no authority.
"""

from __future__ import annotations

import re
import time
import threading
from hanni.logs import get_logger
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import as_rows, quote, run_powershell, run_powershell_json

_DURATION_RE = re.compile(r"^\s*(\d{1,4})\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\s*$",
                          re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
                 "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
                 "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}


def parse_duration(text: str) -> int:
    match = _DURATION_RE.match(text or "")
    if not match:
        raise ValueError("duration must look like '10 minutes', '30s', or '2 hours'")
    return int(match.group(1)) * _UNIT_SECONDS[match.group(2).casefold()]


def _zone(name: str):
    if name.casefold() in {"utc", "etc/utc", "gmt"}:
        return timezone.utc
    aliases = {'eastern': 'America/New_York', 'central': 'America/Chicago',
               'mountain': 'America/Denver', 'pacific': 'America/Los_Angeles'}
    return ZoneInfo(aliases.get(name.casefold().removesuffix(' time zone').removesuffix(' time'), name))


def _now(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    zone_name = str(args.get("timezone", "") or "").strip()
    local = datetime.now().astimezone()
    target = local
    if zone_name:
        try:
            target = datetime.now(tz=_zone(zone_name))
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone '{zone_name}'") from exc
    kind = args.get('kind', 'both')
    offset = args.get('day_offset', 0)
    if kind not in {'both', 'time', 'date'} or offset not in {-1, 0, 1}:
        raise ValueError('kind must be time, date or both; day_offset must be -1, 0 or 1')
    if offset and kind != 'date':
        raise ValueError('day_offset is only supported for date questions')
    day = target.date() + timedelta(days=offset)
    if kind == 'date':
        message = f"{ {-1:'Yesterday was', 0:'Today is', 1:'Tomorrow is'}[offset]} {day:%A, %B %d, %Y}.".replace(' 0', ' ')
    elif kind == 'time':
        message = target.strftime("It's %I:%M %p %Z.").replace(' 0', ' ')
    else:
        message = target.strftime("%A, %d %B %Y at %I:%M %p %Z").replace(' 0', ' ')
    return ToolResult("time.now", True, message,
                      {"iso": target.isoformat(), "utc_iso": target.astimezone(timezone.utc).isoformat(),
                       "date": target.strftime("%Y-%m-%d"), "time": target.strftime("%H:%M:%S"),
                       "weekday": target.strftime("%A"), "timezone": str(target.tzinfo),
                       "local_timezone": str(local.tzinfo), "epoch": int(time.time()),
                       "requested_date": day.isoformat(), "day_offset": offset})


def _convert(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    when = str(args.get("when", "")).strip()
    to_zone = str(args.get("to_timezone", "")).strip()
    from_zone = str(args.get("from_timezone", "") or "").strip()
    if not when or not to_zone:
        raise ValueError("when (ISO timestamp or HH:MM) and to_timezone are required")
    try:
        source_zone = _zone(from_zone) if from_zone else datetime.now().astimezone().tzinfo
        target_zone = _zone(to_zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone names must be IANA identifiers such as America/Chicago") from exc
    try:
        if re.fullmatch(r"\d{1,2}:\d{2}", when):
            today = datetime.now(tz=source_zone).date()
            hour, minute = (int(part) for part in when.split(":"))
            moment = datetime(today.year, today.month, today.day, hour, minute, tzinfo=source_zone)
        else:
            parsed = datetime.fromisoformat(when)
            moment = parsed if parsed.tzinfo else parsed.replace(tzinfo=source_zone)
    except ValueError as exc:
        raise ValueError("when must be an ISO timestamp or HH:MM") from exc
    converted = moment.astimezone(target_zone)
    return ToolResult("time.convert", True,
                      f"{moment.strftime('%Y-%m-%d %H:%M %Z')} is {converted.strftime('%Y-%m-%d %H:%M %Z')}.",
                      {"source_iso": moment.isoformat(), "converted_iso": converted.isoformat(),
                       "source_timezone": str(source_zone), "target_timezone": to_zone})


def _elapsed(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    since = str(args.get("since", "")).strip()
    if not since:
        raise ValueError("since must be an ISO timestamp")
    try:
        moment = datetime.fromisoformat(since)
    except ValueError as exc:
        raise ValueError("since must be an ISO timestamp") from exc
    if not moment.tzinfo:
        moment = moment.replace(tzinfo=datetime.now().astimezone().tzinfo)
    delta = datetime.now(tz=timezone.utc) - moment.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    future = seconds < 0
    seconds = abs(seconds)
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    pretty = " ".join(part for part in (f"{days}d" if days else "", f"{hours}h" if hours or days else "",
                                        f"{minutes}m") if part)
    return ToolResult("time.elapsed", True,
                      f"That is {pretty} {'from now' if future else 'ago'}.",
                      {"seconds": seconds, "pretty": pretty, "in_future": future,
                       "reference_iso": moment.isoformat()})


def _scheduled_tasks(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = str(args.get("query", "")).strip().casefold()
    limit = max(1, min(int(args.get("limit", 30)), 200))
    ready_only = bool(args.get("ready_only", True))
    payload = run_powershell_json(
        "Get-ScheduledTask | Select-Object TaskName, TaskPath, State | ConvertTo-Json -Compress",
        timeout=60, capability="schedule.list_tasks")
    rows: list[dict[str, Any]] = []
    for row in as_rows(payload):
        state = str(row.get("State", ""))
        state_text = {"1": "disabled", "3": "ready", "4": "running"}.get(state, state.casefold())
        rows.append({"name": str(row.get("TaskName") or ""), "path": str(row.get("TaskPath") or ""),
                     "state": state_text})
    if ready_only:
        rows = [row for row in rows if row["state"] in {"ready", "running"}]
    if query:
        rows = [row for row in rows if query in row["name"].casefold() or query in row["path"].casefold()]
    return ToolResult("schedule.list_tasks", True,
                      f"{len(rows)} scheduled task(s) match.",
                      {"tasks": rows[:limit], "total": len(rows)})


def _notify(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    title = " ".join(str(args.get("title", "H.A.N.N.I.")).split())[:60]
    message = " ".join(str(args.get("message", "")).split())[:200]
    if not message:
        raise ValueError("message is required")
    command = (
        "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
        "$icon = New-Object System.Windows.Forms.NotifyIcon; "
        "$icon.Icon = [System.Drawing.SystemIcons]::Information; $icon.Visible = $true; "
        f"$icon.ShowBalloonTip(8000, {quote(title)}, {quote(message)}, "
        "[System.Windows.Forms.ToolTipIcon]::Info); Start-Sleep -Seconds 8; $icon.Dispose()"
    )
    run_powershell(command, timeout=25, capability="notify.toast")
    return ToolResult("notify.toast", True,
                      f"Submitted a desktop notification: {title} - {message}. Visibility has not been verified.",
                      {"title": title, "message": message, "submitted": True, "shown": None})


def _timer_handler(registry):
    active: set[threading.Timer] = set()
    lock = threading.RLock()

    def cancel(change, record):
        if change == "tripped":
            with lock:
                for timer in active:
                    timer.cancel()
                active.clear()
    if registry is not None:
        registry.context.emergency_stop.add_listener(cancel)

    def handler(args, context, request):
        from hanni.tools.winshell import require_windows
        seconds = parse_duration(str(args.get("duration", "")))
        if not 5 <= seconds <= 4 * 3600:
            raise ValueError("timer duration must be between 5 seconds and 4 hours")
        require_windows("timer.set")
        if registry is None or request.source == "cli":
            raise ValueError("Timers need a running HANNI session; one-shot tool-run exits immediately")
        label = " ".join(str(args.get("label", "timer")).split())[:60] or "timer"
        def fire():
            try:
                # Never reuse a confirmation flag or bypass current permissions/stop.
                registry.execute(ToolRequest("notify.toast", {"title": "H.A.N.N.I. timer", "message": label},
                                             actor_profile=request.actor_profile, source="timer"))
            except Exception as exc:
                get_logger("tools.timer").warning("Timer notification blocked/failed: %s", type(exc).__name__)
            finally:
                with lock:
                    active.discard(timer)
        with lock:
            if len(active) >= 16:
                raise ValueError("maximum 16 active timers per runtime")
            timer = threading.Timer(seconds, fire)
            timer.daemon = True
            active.add(timer)
            timer.start()
        fires_at = datetime.now().astimezone() + timedelta(seconds=seconds)
        return ToolResult("timer.set", True, f"Timer scheduled for {seconds} seconds while this HANNI process stays running.",
                          {"label": label, "seconds": seconds, "fires_at_iso": fires_at.isoformat(),
                           "note": "ephemeral; cancelled on process exit or local emergency stop"})
    return handler


def definitions(registry=None) -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("time.now", "Read the OS clock. Omit timezone for local time; accepts IANA zones or Eastern/Central/Mountain/Pacific. kind=date with day_offset=1 resolves tomorrow, -1 yesterday.",
                       0, 0, {"timezone": str, "kind": str, "day_offset": int},
                       {"iso": "string", "date": "string", "time": "string", "weekday": "string"}, _now,
                       side_effect="read",
                       tags=("time", "date", "today", "now", "clock", "day", "timezone"),
                       aliases=("what time is it", "what is today's date", "what day is it")),
        ToolDefinition("time.convert", "Convert a time between IANA timezones.",
                       0, 0, {"when": str, "from_timezone": str, "to_timezone": str},
                       {"converted_iso": "string", "target_timezone": "string"}, _convert,
                       side_effect="read",
                       tags=("timezone", "convert", "time", "meeting", "utc", "difference"),
                       aliases=("what time is that in", "convert this time")),
        ToolDefinition("time.elapsed", "Report how long ago (or how far ahead) an ISO timestamp is.",
                       0, 0, {"since": str}, {"seconds": "integer", "pretty": "string", "in_future": "boolean"}, _elapsed,
                       side_effect="read", tags=("elapsed", "ago", "since", "duration", "how long", "time"),
                       aliases=("how long ago was that", "time since")),
        ToolDefinition("schedule.list_tasks", "List Windows Scheduled Tasks and their state.",
                       0, 0, {"query": str, "ready_only": bool, "limit": int},
                       {"tasks": "array", "total": "integer"}, _scheduled_tasks,
                       timeout_seconds=90, side_effect="read",
                       tags=("scheduled", "task", "cron", "automation", "runs", "schedule", "job"),
                       aliases=("what is scheduled", "scheduled tasks", "what runs automatically")),
        ToolDefinition("notify.toast", "Show a desktop notification on this machine.",
                       1, 1, {"title": str, "message": str}, {"shown": "boolean|null"}, _notify,
                       timeout_seconds=40, side_effect="external_action",
                       tags=("notify", "notification", "remind", "toast", "alert", "popup", "tell me"),
                       aliases=("pop up a reminder", "notify me")),
        ToolDefinition("timer.set", "Set a short ephemeral timer that raises a desktop notification when it fires.",
                       1, 1, {"duration": str, "label": str},
                       {"seconds": "integer", "fires_at_iso": "string"}, _timer_handler(registry),
                       timeout_seconds=40, side_effect="external_action",
                       tags=("timer", "remind", "reminder", "alarm", "minutes", "countdown", "later"),
                       aliases=("remind me in", "set a timer for", "wake me in")),
    )
