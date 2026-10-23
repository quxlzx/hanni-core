"""Windows application launching and lightweight UI-control primitives."""

from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

APP_ALIASES = {
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "opera": "opera.exe",
    "spotify": "spotify.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
}


def _normalize_app_name(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"\.(?:exe|lnk)$", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _shortcut_roots() -> tuple[Path, ...]:
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("PROGRAMDATA")
    userprofile = os.environ.get("USERPROFILE")
    onedrive = os.environ.get("OneDrive")
    if appdata:
        candidates.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        candidates.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if userprofile:
        candidates.append(Path(userprofile) / "Desktop")
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop")
    # Preserve order while removing duplicate resolved-ish paths.
    seen: set[str] = set()
    roots: list[Path] = []
    for path in candidates:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            roots.append(path)
    return tuple(roots)


def _shortcut_score(query: str, candidate: str) -> int:
    q = _normalize_app_name(query)
    c = _normalize_app_name(candidate)
    if not q or not c:
        return -1
    if any(bad in c for bad in ("uninstall", "readme", "manual", "website")):
        return -1
    if c == q:
        return 100
    if c.startswith(q + " ") or q.startswith(c + " "):
        return 90
    if q in c:
        return 80
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    if q_tokens and q_tokens.issubset(c_tokens):
        return 70
    return -1


def _find_start_menu_shortcut(app: str) -> Path | None:
    best: tuple[int, Path] | None = None
    for root in _shortcut_roots():
        if not root.exists():
            continue
        try:
            for shortcut in root.rglob("*.lnk"):
                score = _shortcut_score(app, shortcut.stem)
                if score >= 0 and (best is None or score > best[0]):
                    best = (score, shortcut)
        except OSError:
            continue
    return best[1] if best else None


def _known_launch_command(app: str) -> list[str] | None:
    """Return safe argv for common apps that often are not on PATH.

    Start-menu shortcut discovery is preferred. These are fallbacks for common
    per-user/game launchers whose executables Windows ``start`` often cannot
    resolve by friendly name.
    """
    name = _normalize_app_name(app)
    local = Path(os.environ.get("LOCALAPPDATA", "")) if os.environ.get("LOCALAPPDATA") else None
    roaming = Path(os.environ.get("APPDATA", "")) if os.environ.get("APPDATA") else None
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    pfx86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))

    if name in {"discord", "discord app"} and local:
        updater = local / "Discord" / "Update.exe"
        if updater.exists():
            return [str(updater), "--processStart", "Discord.exe"]
        discord_root = local / "Discord"
        try:
            versions = sorted(discord_root.glob("app-*/Discord.exe"), reverse=True)
        except OSError:
            versions = []
        if versions:
            return [str(versions[0])]

    if name in {"steam", "steam client"}:
        for exe in (pfx86 / "Steam" / "steam.exe", pf / "Steam" / "steam.exe"):
            if exe.exists():
                return [str(exe)]


    if name in {"spotify", "spotify music"}:
        candidates = []
        if roaming:
            candidates.append(roaming / "Spotify" / "Spotify.exe")
        if local:
            candidates.extend((
                local / "Microsoft" / "WindowsApps" / "Spotify.exe",
                local / "Spotify" / "Spotify.exe",
            ))
        for exe in candidates:
            if exe.exists():
                return [str(exe)]

    if name in {"riot", "riot client", "riot games", "riot games client"}:
        # Riot commonly installs outside Program Files at C:\Riot Games.
        for exe in (
            Path(r"C:\Riot Games\Riot Client\RiotClientServices.exe"),
            pf / "Riot Vanguard" / "RiotClientServices.exe",
        ):
            if exe.exists():
                return [str(exe)]

    return None


def _start_file(path: Path) -> None:
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise OSError("Windows shell launching is unavailable")
    startfile(str(path))


def _open_folder(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    """A remembered project can only hand off a verified directory to Explorer."""
    raw = str(args.get("path", "")).strip()
    if not raw or any(char in raw for char in ('\r', '\n', '\x00')):
        raise ValueError("a valid absolute folder path is required")
    supplied = Path(raw).expanduser()
    if not supplied.is_absolute():
        raise ValueError("folder path must be absolute")
    folder = supplied.resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("folder.open only accepts existing directories, never scripts or executables")
    if os.name != "nt":
        raise RuntimeError("folder.open requires Windows File Explorer")
    # Fixed executable and separate argument: remembered text is never shell code.
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    subprocess.Popen([str(windows_dir / "explorer.exe"), str(folder)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ToolResult("folder.open", True, "Started File Explorer for the verified folder.",
                      {"path": str(folder), "directory_verified": True, "launch_requested": True,
                       "window_verified": False})


def _open_app(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    app = str(args.get("app", "")).strip()
    if not app:
        raise ValueError("app is required")
    if any(ch in app for ch in ("&", "|", "<", ">", "^", "%", "!", "\r", "\n")):
        raise ValueError("app name/path contains shell metacharacters that are not allowed")
    if os.name != "nt":
        # Cross-platform test/development fallback. Production V1 targets
        # Windows, but keeping this path lets the tool layer be unit-tested in
        # non-Windows CI without pretending Start Menu discovery exists there.
        command = APP_ALIASES.get(app.lower(), app)
        process = subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        friendly = app if app.lower() not in {"code"} else "VS Code"
        return ToolResult("app.open", True, f"Started {friendly}.",
                          {"app": app, "method": "direct", "command": command,
                           "outcome": "process_started", "process_id": process.pid, "verified": False})

    # Explicit existing path wins.
    supplied = Path(app).expanduser()
    if supplied.exists():
        _start_file(supplied)
        return ToolResult("app.open", True, f"Sent Windows a request to open {supplied.stem}.",
                          {"app": app, "method": "path", "target": str(supplied),
                           "outcome": "accepted", "verified": False})

    # Friendly-name launching should use Windows' own Start Menu shortcuts first.
    # This covers Discord, Steam, Riot Client, launchers, and user-installed apps
    # that are not placed on PATH.
    # Prefer known executable locations for common launchers/apps. This avoids
    # stale or cloud-synced Desktop shortcuts (for example a OneDrive Spotify
    # shortcut) taking precedence over a working local installation.
    known = _known_launch_command(app)
    if known is not None:
        process = subprocess.Popen(known, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ToolResult("app.open", True, f"Started {app}.",
                          {"app": app, "method": "known_path", "command": known,
                           "outcome": "process_started", "process_id": process.pid, "verified": False})

    shortcut_error: OSError | None = None
    shortcut = _find_start_menu_shortcut(app)
    if shortcut is not None:
        try:
            _start_file(shortcut)
            return ToolResult("app.open", True, f"Sent Windows a request to open {app}.",
                              {"app": app, "method": "shortcut", "target": str(shortcut),
                               "outcome": "accepted", "verified": False})
        except OSError as exc:
            # A shortcut can be stale, blocked, or point at a removed package.
            # Fall through to Windows' normal app-resolution path instead of
            # failing the whole request.
            shortcut_error = exc

    command = APP_ALIASES.get(app.lower(), app)
    friendly = app if app.lower() not in {"code"} else "VS Code"
    if app.lower() in APP_ALIASES:
        try:
            process = subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass  # Windows shell resolution may still find an App Execution Alias.
        else:
            return ToolResult("app.open", True, f"Started {friendly}.",
                              {"app": app, "method": "direct", "command": command,
                               "outcome": "process_started", "process_id": process.pid, "verified": False})
    # `start` remains a useful last fallback for App Execution Aliases / PATH.
    subprocess.Popen(["cmd.exe", "/d", "/c", "start", "", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data = {"app": app, "method": "shell", "command": command,
            "outcome": "accepted", "verified": False}
    if shortcut_error is not None:
        data["shortcut_fallback"] = str(shortcut_error)
    return ToolResult("app.open", True, f"Sent Windows a request to open {friendly}.", data)


def _open_url(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("url is required")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    ok = webbrowser.open(url, new=2)
    return ToolResult("browser.open_url", bool(ok), f"Opened {url}." if ok else f"Asked Windows to open {url}.", {"url": url})


def _active_window(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    if os.name != "nt":
        raise OSError("ui.active_window is available only on Windows")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise OSError("Windows did not report a foreground window")
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    title = buffer.value.strip() or "Untitled window"
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_name = "unknown"
    if pid.value:
        try:
            process_name = psutil.Process(pid.value).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    message = f"Your active window is {title}."
    if process_name != "unknown":
        message += f" It's running in {process_name}."
    return ToolResult(
        "ui.active_window",
        True,
        message,
        {"hwnd": int(hwnd), "title": title, "pid": int(pid.value), "process": process_name},
    )


def _list_windows(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    rows = _enumerate_windows()
    return ToolResult("ui.list_windows", True, f"I found {len(rows)} visible windows.", {"windows": rows})


def _focus_window(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = str(args.get("title", "")).strip().lower()
    if not query:
        raise ValueError("title is required")
    if os.name != "nt":
        raise OSError("ui.focus_window is available only on Windows")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    target = None
    for row in _enumerate_windows():
        if query in row["title"].lower():
            target = row
            break
    if target is None:
        raise LookupError(f"no visible window title contains {query!r}")
    hwnd = wintypes.HWND(int(target["hwnd"]))
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    if not user32.SetForegroundWindow(hwnd):
        raise OSError("Windows refused to focus the requested window")
    return ToolResult("ui.focus_window", True, f"Focused {target['title']}.", target)


def _enumerate_windows() -> list[dict[str, Any]]:
    if os.name != "nt":
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
        if title:
            rows.append({"hwnd": int(hwnd), "title": title})
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return rows


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("folder.open", "Open an existing project directory in Windows File Explorer; never execute a file.",
                       1, 1, {"path": str}, {"path": "string", "directory_verified": "boolean", "launch_requested": "boolean", "window_verified": "boolean"},
                       _open_folder, side_effect="external_action", tags=("project", "folder", "explorer")),
        ToolDefinition("app.open", "Request Windows to open a local application by name, shortcut, executable, or path; launch acceptance does not verify that it is running.", 1, 1, {"app": str}, {"app": "string", "outcome": "accepted", "verified": "boolean"}, _open_app),
        ToolDefinition("browser.open_url", "Open an HTTP/HTTPS URL in the default browser.", 1, 1, {"url": str}, {"url": "string"}, _open_url),
        ToolDefinition("ui.active_window", "Read the current foreground Windows window title and process.", 0, 0, {}, {"title": "string", "process": "string"}, _active_window),
        ToolDefinition("ui.list_windows", "List visible top-level Windows windows.", 0, 0, {}, {"windows": "array"}, _list_windows),
        ToolDefinition("ui.focus_window", "Focus a visible window by title substring.", 1, 1, {"title": str}, {"title": "string"}, _focus_window),
    )
