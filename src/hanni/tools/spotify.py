"""Spotify capabilities driven entirely from the local desktop client.

V1 keeps H.A.N.N.I. local-first, so nothing here calls the Spotify Web API or
any other cloud service (D-0009, CLAUDE.md). What is playing is read from the
running client's own window title, transport control uses the standard Windows
media keys, and library navigation uses the locally registered ``spotify:`` URI
handler. Per-application volume uses the optional ``pycaw`` package when it is
installed and degrades honestly when it is not.
"""

from __future__ import annotations

import re
import time
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.media import (VK_MEDIA_NEXT, VK_MEDIA_PLAY_PAUSE, VK_MEDIA_PREV, press_key)
from hanni.tools.winshell import is_windows, quote, require_windows, run_powershell

_IDLE_TITLES = {"spotify", "spotify premium", "spotify free", "advertisement"}
_URI_RE = re.compile(r"^spotify:(track|album|playlist|artist|show|episode|user|search):[A-Za-z0-9%:._\- ]{1,180}$")
_SAFE_QUERY = re.compile(r"^[A-Za-z0-9 '&,.!?()\-_/]{1,120}$")


def _client_processes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "create_time"]):
        if str(proc.info.get("name", "")).casefold() == "spotify.exe":
            rows.append({"pid": proc.info["pid"], "started": float(proc.info.get("create_time") or 0)})
    return rows


def _client_window() -> dict[str, Any] | None:
    """Find the Spotify client's own visible window by resolving each window's PID."""
    if not is_windows():
        return None
    import ctypes
    from ctypes import wintypes

    pids = {row["pid"] for row in _client_processes()}
    if not pids:
        return None
    user32 = ctypes.windll.user32
    found: dict[str, Any] | None = None
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, lparam):
        nonlocal found
        if found is not None or not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) not in pids:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title:
            found = {"hwnd": int(hwnd), "title": title, "pid": int(pid.value)}
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found


def _read_now_playing() -> dict[str, Any]:
    window = _client_window()
    running = bool(_client_processes())
    if not running:
        return {"running": False, "playing": False, "title": "", "artist": "", "track": "", "window_title": ""}
    title = str(window.get("title", "")).strip() if window else ""
    normalized = title.casefold()
    if not title or normalized in _IDLE_TITLES:
        return {"running": True, "playing": False, "title": title, "artist": "", "track": "", "window_title": title}
    artist, _, track = title.partition(" - ")
    return {"running": True, "playing": True, "title": title,
            "artist": artist.strip() if track else "", "track": (track or title).strip(),
            "window_title": title, "advertisement": normalized == "advertisement"}


def _status(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    state = _read_now_playing()
    if not state["running"]:
        message = "Spotify is not running on this machine."
    elif not state["playing"]:
        message = "Spotify is open but nothing is playing right now."
    elif state["artist"]:
        message = f"Spotify is playing {state['track']} by {state['artist']}."
    else:
        message = f"Spotify is playing {state['track']}."
    state["source"] = "local Spotify client window title"
    state["playback_verified"] = False
    message = f"Spotify window reports: {state['title'] or 'no track title available'}." if state["running"] else message
    return ToolResult("spotify.status", True, message, state)


def _launch(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    require_windows("spotify.launch")
    if _client_processes():
        return ToolResult("spotify.launch", True, "Spotify is already running.", {"started": False, "running": True})
    run_powershell("Start-Process -FilePath 'spotify:'", timeout=30, capability="spotify.launch")
    for _ in range(20):
        time.sleep(0.5)
        if _client_processes():
            return ToolResult("spotify.launch", True, "Started the Spotify desktop client.",
                              {"started": True, "running": True})
    return ToolResult("spotify.launch", False, "Asked Windows to start Spotify but no client process appeared.",
                      {"started": False, "running": False})


def _ensure_running(capability: str) -> None:
    if not _client_processes():
        raise RuntimeError(f"{capability} needs the Spotify desktop client to be running; open it first")


def _transport(name: str, code: int, verb: str):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        _ensure_running(name)
        before = _read_now_playing()
        window = _client_window()
        for _ in range(10):
            if window is not None:
                break
            time.sleep(0.5)
            window = _client_window()
        if window is None:
            raise RuntimeError("Spotify has no visible window to receive this playback request")
        require_windows(name)
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        send = user32.SendMessageTimeoutW
        send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                         wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        send.restype = wintypes.LPARAM
        result = ctypes.c_size_t()
        command = {VK_MEDIA_NEXT: 11, VK_MEDIA_PREV: 12, VK_MEDIA_PLAY_PAUSE: 14}[code]
        if not send(int(window['hwnd']), 0x0319, int(window['hwnd']), command << 16, 2, 1000, ctypes.byref(result)):
            raise RuntimeError("Spotify did not accept the playback message")
        after = before
        for _ in range(6):
            time.sleep(0.5)
            after = _read_now_playing()
            if after["title"] != before["title"] or after["playing"] != before["playing"]:
                break
        return ToolResult(name, True,
                          "Sent Spotify playback request. Window reports: " + (f"{after['track']}" + (f" by {after['artist']}" if after["artist"] else "")
                                              if after["playing"] else "nothing playing."),
                          {"before": before["title"], "now_playing": after["title"],
                           "playing": after["playing"], "changed": before["title"] != after["title"]})
    return handler


def _open_uri(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    uri = str(args.get("uri", "")).strip()
    if not _URI_RE.match(uri):
        raise ValueError("uri must be a spotify: URI such as spotify:track:<id> or spotify:playlist:<id>")
    require_windows("spotify.open_uri")
    run_powershell(f"Start-Process -FilePath {quote(uri)}", timeout=30, capability="spotify.open_uri")
    time.sleep(1.0)
    return ToolResult("spotify.open_uri", True, f"Handed {uri} to the local Spotify client.",
                      {"uri": uri, "now_playing": _read_now_playing()["title"]})


def _search(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = " ".join(str(args.get("query", "")).split())
    if not _SAFE_QUERY.match(query):
        raise ValueError("query must be 1-120 plain characters (letters, digits, spaces, simple punctuation)")
    require_windows("spotify.search")
    from urllib.parse import quote as uri_quote
    uri = "spotify:search:" + uri_quote(query, safe="")
    run_powershell(f"Start-Process -FilePath {quote(uri)}", timeout=30, capability="spotify.search")
    return ToolResult("spotify.search", True,
                      f"Opened Spotify search for '{query}'. Playback still needs an explicit play action.",
                      {"query": query, "uri": uri, "played": False})


def _app_volume(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    require_windows("spotify.volume")
    percent = args.get("percent")
    try:  # pragma: no cover - depends on optional Windows audio stack
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        from ctypes import cast, POINTER

        for session in AudioUtilities.GetAllSessions():
            if session.Process and session.Process.name().casefold() == "spotify.exe":
                volume = cast(session._ctl.QueryInterface(ISimpleAudioVolume), POINTER(ISimpleAudioVolume))
                current = round(volume.GetMasterVolume() * 100)
                if percent is None:
                    return ToolResult("spotify.volume", True, f"Spotify's own volume is {current}%.",
                                      {"percent": current, "changed": False, "precise": True})
                level = int(percent)
                if not 0 <= level <= 100:
                    raise ValueError("percent must be between 0 and 100")
                volume.SetMasterVolume(level / 100, None)
                applied = round(volume.GetMasterVolume() * 100)
                verified = applied == level
                message = (f"Spotify volume is now {applied}% (was {current}%)." if verified
                           else f"Requested Spotify volume {level}%, but readback is {applied}%.")
                return ToolResult("spotify.volume", verified, message,
                                  {"percent": applied, "requested_percent": level,
                                   "previous_percent": current, "changed": applied != current,
                                   "precise": True, "verified": verified})
        return ToolResult("spotify.volume", False, "Spotify has no active audio session right now.",
                          {"percent": -1, "changed": False, "precise": True})
    except ImportError:
        return ToolResult("spotify.volume", False,
                          "Per-application volume needs the optional pycaw package; use audio.set_volume for the whole system.",
                          {"percent": -1, "changed": False, "precise": False})


def _focus(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    _ensure_running("spotify.focus")
    window = _client_window()
    if window is None:
        return ToolResult("spotify.focus", False, "Spotify is running but has no visible window to focus.",
                          {"focused": False})
    require_windows("spotify.focus")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    hwnd = int(window["hwnd"])
    user32.ShowWindow(hwnd, 9)
    accepted = bool(user32.SetForegroundWindow(hwnd))
    focused = int(user32.GetForegroundWindow() or 0) == hwnd
    return ToolResult("spotify.focus", focused,
                      f"Spotify is in the foreground ({window.get('title', '')})." if focused
                      else "Windows did not bring Spotify to the foreground.",
                      {"focused": focused, "title": window.get("title", ""),
                       "request_accepted": accepted, "verified": focused})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("spotify.status", "Read what the local Spotify client is playing right now, from its own window title.",
                       0, 0, {}, {"running": "boolean", "playing": "boolean", "track": "string", "artist": "string"}, _status,
                       side_effect="read",
                       tags=("spotify", "music", "playing", "song", "track", "artist", "now"),
                       aliases=("what song is this", "what is playing", "whats playing on spotify", "current song")),
        ToolDefinition("spotify.launch", "Open the Spotify desktop client if it is not already running.",
                       1, 1, {}, {"started": "boolean", "running": "boolean"}, _launch,
                       timeout_seconds=45, side_effect="external_action",
                       tags=("spotify", "open", "launch", "start", "music", "app"),
                       aliases=("open spotify", "start spotify")),
        ToolDefinition("spotify.play_pause", "Toggle Spotify playback once: playing becomes paused and paused becomes playing. Read spotify.status first when the current state is unknown; this does not select a song.",
                       1, 1, {}, {"playing": "boolean", "now_playing": "string"},
                       _transport("spotify.play_pause", VK_MEDIA_PLAY_PAUSE, "Toggled Spotify playback"),
                       timeout_seconds=30, side_effect="external_action",
                       tags=("spotify", "play", "pause", "resume", "music", "song"),
                       aliases=("pause spotify", "play my music", "resume the song")),
        ToolDefinition("spotify.next", "Skip to the next Spotify track and report what started.",
                       1, 1, {}, {"now_playing": "string", "changed": "boolean"},
                       _transport("spotify.next", VK_MEDIA_NEXT, "Skipped to the next track"),
                       timeout_seconds=30, side_effect="external_action",
                       tags=("spotify", "next", "skip", "song", "track", "music"),
                       aliases=("skip this song", "next song on spotify")),
        ToolDefinition("spotify.previous", "Go back to the previous Spotify track and report what started.",
                       1, 1, {}, {"now_playing": "string", "changed": "boolean"},
                       _transport("spotify.previous", VK_MEDIA_PREV, "Went back a track"),
                       timeout_seconds=30, side_effect="external_action",
                       tags=("spotify", "previous", "back", "song", "track", "replay", "music"),
                       aliases=("go back a song", "previous song")),
        ToolDefinition("spotify.search", "Open a Spotify search for a plain-text query in the desktop client. Does not start playback by itself.",
                       1, 1, {"query": str}, {"query": "string", "uri": "string", "played": "boolean"}, _search,
                       timeout_seconds=45, side_effect="external_action",
                       tags=("spotify", "search", "find", "music", "song", "album", "artist", "playlist"),
                       aliases=("look up on spotify", "find that song", "search spotify for")),
        ToolDefinition("spotify.open_uri", "Open an exact spotify: URI (track, album, playlist, artist, show, episode) in the local client.",
                       1, 1, {"uri": str}, {"uri": "string", "now_playing": "string"}, _open_uri,
                       timeout_seconds=45, side_effect="external_action",
                       tags=("spotify", "playlist", "album", "uri", "link", "open", "music"),
                       aliases=("play this playlist", "open this spotify link")),
        ToolDefinition("spotify.volume", "Read or set Spotify's own application volume, separate from system volume.",
                       2, 2, {"percent": int}, {"percent": "integer", "changed": "boolean"}, _app_volume,
                       timeout_seconds=40, side_effect="external_action",
                       tags=("spotify", "volume", "louder", "quieter", "music", "audio"),
                       aliases=("turn the music down", "spotify too loud")),
        ToolDefinition("spotify.focus", "Bring the Spotify window to the foreground.",
                       1, 1, {}, {"focused": "boolean", "title": "string"}, _focus,
                       side_effect="external_action",
                       tags=("spotify", "focus", "window", "show", "switch"),
                       aliases=("show me spotify", "switch to spotify")),
    )
