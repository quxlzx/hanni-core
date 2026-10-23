"""Additional window-management capabilities built on the Win32 window list.

Closing a window is a polite WM_CLOSE, never a process kill, so the application
still gets to prompt about unsaved work; it is Level 2 and confirmation-gated
because it can interrupt the owner's work.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import is_windows, require_windows

_SW_MINIMIZE = 6
_SW_RESTORE = 9
_SW_MAXIMIZE = 3
_WM_CLOSE = 0x0010
_PROTECTED_TITLES = ("task manager", "windows security")


def _windows_with_processes() -> list[dict[str, Any]]:
    if not is_windows():
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    rows: list[dict[str, Any]] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = ""
        try:
            name = psutil.Process(int(pid.value)).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            name = ""
        rows.append({"hwnd": int(hwnd), "title": title, "pid": int(pid.value), "process": name,
                     "minimized": bool(user32.IsIconic(hwnd))})
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return rows


def _detailed_windows(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = str(args.get("query", "") or "").casefold().strip()
    rows = _windows_with_processes()
    if query:
        rows = [row for row in rows
                if query in row["title"].casefold() or query in row["process"].casefold()]
    processes = sorted({row["process"] for row in rows if row["process"]})
    return ToolResult("ui.windows_detailed", True,
                      f"{len(rows)} visible window(s) across {len(processes)} application(s).",
                      {"windows": rows[:60], "total": len(rows), "processes": processes})


def _minimize_all(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    require_windows("ui.minimize_all")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    minimized = 0
    attempted = 0
    for row in _windows_with_processes():
        if row["minimized"]:
            continue
        attempted += 1
        user32.ShowWindow(row["hwnd"], _SW_MINIMIZE)
        if user32.IsIconic(row["hwnd"]):
            minimized += 1
    verified = minimized == attempted
    return ToolResult("ui.minimize_all", verified,
                      f"Observed {minimized} of {attempted} requested window(s) minimized.",
                      {"minimized": minimized, "attempted": attempted, "verified": verified})


def _window_state(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    title = str(args.get("title", "")).strip()
    state = str(args.get("state", "")).casefold()
    if not title:
        raise ValueError("title substring is required")
    if state not in {"minimize", "restore", "maximize"}:
        raise ValueError("state must be minimize, restore, or maximize")
    require_windows("ui.window_state")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    for function in (user32.IsIconic, user32.IsZoomed):
        function.argtypes = [wintypes.HWND]
        function.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    matches = [row for row in _windows_with_processes() if title.casefold() in row["title"].casefold()]
    if not matches:
        return ToolResult("ui.window_state", False, f"No visible window title contains {title!r}.",
                          {"matched": 0, "title": title, "state": state, "verified": False})
    flag = {"minimize": _SW_MINIMIZE, "restore": _SW_RESTORE, "maximize": _SW_MAXIMIZE}[state]
    for row in matches:
        user32.ShowWindow(row["hwnd"], flag)
    def observed(row):
        minimized = bool(user32.IsIconic(row["hwnd"]))
        maximized = bool(user32.IsZoomed(row["hwnd"]))
        return minimized if state == "minimize" else maximized if state == "maximize" else not minimized and not maximized
    verified_count = sum(observed(row) for row in matches)
    verified = verified_count == len(matches)
    return ToolResult("ui.window_state", verified,
                      f"Observed {verified_count} of {len(matches)} window(s) matching {title!r} in the requested {state} state.",
                      {"matched": len(matches), "state": state,
                       "titles": [row["title"] for row in matches[:10]],
                       "verified_count": verified_count, "verified": verified})


def _close_window(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    title = str(args.get("title", "")).strip()
    if len(title) < 3:
        raise ValueError("title substring must be at least 3 characters, to avoid closing the wrong window")
    if any(marker in title.casefold() for marker in _PROTECTED_TITLES):
        raise ValueError(f"{title!r} names a protected system window and will not be closed")
    require_windows("ui.close_window")
    import ctypes

    user32 = ctypes.windll.user32
    matches = [row for row in _windows_with_processes() if title.casefold() in row["title"].casefold()]
    if not matches:
        return ToolResult("ui.close_window", False, f"No visible window title contains {title!r}.",
                          {"closed": 0, "title": title})
    if len(matches) > 1 and not bool(args.get("all_matches", False)):
        return ToolResult("ui.close_window", False,
                          f"{len(matches)} windows match {title!r}; be more specific or pass all_matches=true.",
                          {"closed": 0, "candidates": [row["title"] for row in matches[:10]]})
    closed = []
    for row in matches:
        user32.PostMessageW(row["hwnd"], _WM_CLOSE, 0, 0)
        closed.append(row["title"])
    time.sleep(0.6)
    remaining = {row["hwnd"] for row in _windows_with_processes()}
    still_open = [row["title"] for row in matches if row["hwnd"] in remaining]
    return ToolResult("ui.close_window", True,
                      f"Asked {len(closed)} window(s) to close"
                      + (f"; {len(still_open)} still open (the app may be prompting to save)." if still_open
                         else "; all closed."),
                      {"closed": closed, "still_open": still_open})


def _close_reason(args: Mapping[str, Any]) -> str | None:
    return f"closing windows matching {args.get('title')!r} can interrupt unsaved work"


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("ui.windows_detailed", "List visible windows with their owning process, PID, and minimized state.",
                       0, 0, {"query": str}, {"windows": "array", "total": "integer"}, _detailed_windows,
                       side_effect="read",
                       tags=("window", "windows", "open", "apps", "visible", "which", "running"),
                       aliases=("what do i have open", "list my windows", "what apps are open")),
        ToolDefinition("ui.minimize_all", "Minimize every visible window to show the desktop.",
                       1, 1, {}, {"minimized": "integer"}, _minimize_all,
                       side_effect="external_action",
                       tags=("minimize", "desktop", "hide", "clear", "windows", "show"),
                       aliases=("show my desktop", "minimize everything", "clear my screen")),
        ToolDefinition("ui.window_state", "Minimize, restore, or maximize windows whose title contains a substring.",
                       1, 1, {"title": str, "state": str},
                       {"matched": "integer", "state": "string"}, _window_state,
                       side_effect="external_action",
                       tags=("minimize", "maximize", "restore", "window", "resize", "full", "screen"),
                       aliases=("maximize that window", "minimize this", "bring it back")),
        ToolDefinition("ui.close_window", "Politely close windows matching a title substring with WM_CLOSE, never a forced process kill.",
                       2, 2, {"title": str, "all_matches": bool},
                       {"closed": "array", "still_open": "array"}, _close_window,
                       side_effect="external_action", requires_confirmation_if=_close_reason,
                       tags=("close", "window", "quit", "exit", "shut", "dismiss"),
                       aliases=("close that window", "close those tabs", "quit that app")),
    )
