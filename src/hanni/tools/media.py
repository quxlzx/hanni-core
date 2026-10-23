"""Audio, transport-key, and display capabilities.

Volume and playback use the standard Windows virtual media keys, which are the
same events a keyboard sends. Exact volume control uses ``pycaw`` when it is
installed and otherwise falls back to deterministic 2%-per-step key presses
from a known floor, so the reported value stays honest either way.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import as_rows, require_windows, run_powershell_json

VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
_KEYEVENTF_KEYUP = 0x0002
_STEP_PERCENT = 2


def press_key(code: int, *, repeat: int = 1, capability: str = "media key") -> int:
    """Send a virtual key press/release pair; returns how many times it fired."""
    require_windows(capability)
    import ctypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    count = max(1, min(int(repeat), 100))
    for _ in range(count):
        user32.keybd_event(code, 0, 0, 0)
        user32.keybd_event(code, 0, _KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
    return count


def _endpoint_volume():
    """Return a pycaw endpoint volume interface, or None when unavailable."""
    try:  # pragma: no cover - depends on optional Windows audio stack
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return None


def _volume_status(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    require_windows("audio.status")
    volume = _endpoint_volume()
    if volume is not None:  # pragma: no cover - hardware dependent
        percent = round(volume.GetMasterVolumeLevelScalar() * 100)
        muted = bool(volume.GetMute())
        return ToolResult("audio.status", True,
                          f"System volume is {percent}%{' and muted' if muted else ''}.",
                          {"percent": percent, "muted": muted, "precise": True})
    payload = run_powershell_json(
        "Get-CimInstance -ClassName Win32_SoundDevice | Select-Object Name, Status | ConvertTo-Json -Compress",
        timeout=30, capability="audio.status")
    devices = [{"name": str(row.get("Name") or ""), "status": str(row.get("Status") or "")} for row in as_rows(payload)]
    return ToolResult("audio.status", True,
                      "Volume and mute state are unknown without exact readback; reporting audio devices instead.",
                      {"percent": -1, "muted": None, "precise": False, "devices": devices})


def _set_volume(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    if "percent" in args and args.get("percent") is not None:
        percent = int(args["percent"])
        if not 0 <= percent <= 100:
            raise ValueError("percent must be between 0 and 100")
    else:
        percent = -1
    delta = int(args.get("delta", 0) or 0)
    if percent < 0 and delta == 0:
        raise ValueError("provide percent (absolute) or delta (relative change)")
    if not -100 <= delta <= 100:
        raise ValueError("delta must be between -100 and 100")
    require_windows("audio.set_volume")

    volume = _endpoint_volume()
    if volume is not None:  # pragma: no cover - hardware dependent
        current = round(volume.GetMasterVolumeLevelScalar() * 100)
        target = percent if percent >= 0 else max(0, min(100, current + delta))
        volume.SetMasterVolumeLevelScalar(target / 100, None)
        applied = round(volume.GetMasterVolumeLevelScalar() * 100)
        verified = applied == target
        return ToolResult("audio.set_volume", verified,
                          f"Volume is now {applied}% (was {current}%)." if verified
                          else f"Requested volume {target}%, but readback is {applied}%.",
                          {"percent": applied, "previous_percent": current,
                           "requested_percent": target, "precise": True, "verified": verified})
    if percent < 0 and delta:
        steps = max(1, abs(delta) // _STEP_PERCENT)
        press_key(VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN, repeat=steps, capability="audio.set_volume")
        return ToolResult("audio.set_volume", True,
                          f"Nudged volume {'up' if delta > 0 else 'down'} by about {steps * _STEP_PERCENT}%.",
                          {"percent": -1, "steps": steps, "precise": False})
    press_key(VK_VOLUME_DOWN, repeat=60, capability="audio.set_volume")
    steps = percent // _STEP_PERCENT
    if steps:
        press_key(VK_VOLUME_UP, repeat=steps, capability="audio.set_volume")
    return ToolResult("audio.set_volume", True,
                      f"Volume driven to about {steps * _STEP_PERCENT}% using media keys (install pycaw for exact control).",
                      {"percent": steps * _STEP_PERCENT, "steps": steps, "precise": False})


def _mute(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    require_windows("audio.mute")
    desired = args.get("muted")
    volume = _endpoint_volume()
    if volume is not None:  # pragma: no cover - hardware dependent
        target = (not bool(volume.GetMute())) if desired is None else bool(desired)
        volume.SetMute(1 if target else 0, None)
        applied = bool(volume.GetMute())
        verified = applied == target
        return ToolResult("audio.mute", verified,
                          f"Audio is now {'muted' if applied else 'unmuted'}." if verified
                          else f"Requested {'mute' if target else 'unmute'}, but audio remains {'muted' if applied else 'unmuted'}.",
                          {"muted": applied, "requested_muted": target, "precise": True, "verified": verified})
    if desired is not None:
        return ToolResult("audio.mute", False, "Exact mute/unmute requires pycaw; I did not toggle an unknown state.",
                          {"muted": None, "precise": False})
    press_key(VK_VOLUME_MUTE, capability="audio.mute")
    return ToolResult("audio.mute", True, "Sent the mute toggle key; exact mute state needs the optional pycaw package.",
                      {"muted": None, "precise": False})


def _transport(name: str, code: int, description: str):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        press_key(code, capability=name)
        return ToolResult(name, True, description, {"key": name, "sent": True})
    return handler


def _display_info(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    payload = run_powershell_json(
        "Get-CimInstance -ClassName Win32_VideoController "
        "| Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate, AdapterRAM "
        "| ConvertTo-Json -Compress", timeout=40, capability="display.info")
    rows = []
    for row in as_rows(payload):
        width = int(row.get("CurrentHorizontalResolution") or 0)
        height = int(row.get("CurrentVerticalResolution") or 0)
        rows.append({"adapter": str(row.get("Name") or ""), "width": width, "height": height,
                     "resolution": f"{width}x{height}" if width and height else "",
                     "refresh_hz": int(row.get("CurrentRefreshRate") or 0),
                     "adapter_ram_gb": round(int(row.get("AdapterRAM") or 0) / 1024 ** 3, 2)})
    active = [row for row in rows if row["width"]]
    return ToolResult("display.info", True,
                      "; ".join(f"{r['adapter']} at {r['resolution']} @ {r['refresh_hz']}Hz" for r in active)
                      or "No active display adapter reported.",
                      {"displays": rows, "active_count": len(active)})


def _brightness(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    percent = args.get("percent")
    if percent is not None and not 0 <= int(percent) <= 100:
        raise ValueError("percent must be between 0 and 100")
    if percent is None:
        payload = run_powershell_json(
            "Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness "
            "| Select-Object CurrentBrightness | ConvertTo-Json -Compress",
            timeout=30, capability="display.brightness")
        rows = as_rows(payload)
        level = int(rows[0].get("CurrentBrightness") or 0) if rows else -1
        return ToolResult("display.brightness", True,
                          f"Panel brightness is {level}%." if level >= 0 else "Brightness reporting is unavailable on this panel.",
                          {"percent": level, "changed": False})
    level = int(percent)
    if not 0 <= level <= 100:
        raise ValueError("percent must be between 0 and 100")
    previous = _brightness({}, context, request).data["percent"]
    run_powershell_json(
        "(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods)"
        f".WmiSetBrightness(1, {level}); @{{ ok = $true }} | ConvertTo-Json -Compress",
        timeout=30, capability="display.brightness")
    applied = _brightness({}, context, request).data["percent"]
    verified = applied == level
    message = (f"Panel brightness is now {applied}%." if verified
               else "Brightness change could not be verified on this panel." if applied < 0
               else f"Requested brightness {level}%, but the panel reports {applied}%.")
    return ToolResult("display.brightness", verified, message,
                      {"percent": applied, "requested_percent": level,
                       "changed": applied >= 0 and previous >= 0 and applied != previous,
                       "verified": verified})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("audio.status", "Read the current system volume and mute state.",
                       0, 0, {}, {"percent": "integer", "muted": "boolean|null", "precise": "boolean"}, _volume_status,
                       timeout_seconds=40, side_effect="read",
                       tags=("volume", "audio", "sound", "loud", "mute", "level"),
                       aliases=("how loud is it", "what is my volume", "sound level")),
        ToolDefinition("audio.set_volume", "Set the system volume to an absolute percent, or nudge it up/down with delta.",
                       2, 2, {"percent": int, "delta": int},
                       {"percent": "integer", "precise": "boolean"}, _set_volume,
                       argument_constraints={'percent': {'minimum': 0, 'maximum': 100, 'description': 'Absolute system volume percentage.'},
                                             'delta': {'minimum': -100, 'maximum': 100, 'description': 'Relative percentage change.'}},
                       timeout_seconds=40, side_effect="external_action",
                       tags=("volume", "louder", "quieter", "turn", "down", "up", "audio", "sound"),
                       aliases=("turn it down", "turn it up", "set volume to")),
        ToolDefinition("audio.mute", "Mute or unmute system audio; with no argument, toggles.",
                       2, 2, {"muted": bool}, {"muted": "boolean|null"}, _mute,
                       timeout_seconds=40, side_effect="external_action",
                       tags=("mute", "silence", "quiet", "unmute", "audio", "sound"),
                       aliases=("mute it", "silence the audio", "unmute")),
        ToolDefinition("media.play_pause", "Send the play/pause media key to whatever is playing.",
                       1, 1, {}, {"key": "string", "sent": "boolean"},
                       _transport("media.play_pause", VK_MEDIA_PLAY_PAUSE, "Sent the play/pause media key."),
                       side_effect="external_action",
                       tags=("play", "pause", "music", "media", "resume", "stop", "song", "video"),
                       aliases=("pause the music", "play it", "resume playback")),
        ToolDefinition("media.next_track", "Skip to the next track.",
                       1, 1, {}, {"key": "string", "sent": "boolean"},
                       _transport("media.next_track", VK_MEDIA_NEXT, "Sent the next-track media key."),
                       side_effect="external_action",
                       tags=("next", "skip", "track", "song", "media", "forward"),
                       aliases=("skip this song", "next track")),
        ToolDefinition("media.previous_track", "Go back to the previous track.",
                       1, 1, {}, {"key": "string", "sent": "boolean"},
                       _transport("media.previous_track", VK_MEDIA_PREV, "Sent the previous-track media key."),
                       side_effect="external_action",
                       tags=("previous", "back", "track", "song", "media", "replay"),
                       aliases=("go back a song", "previous track")),
        ToolDefinition("media.stop", "Send the stop media key.",
                       1, 1, {}, {"key": "string", "sent": "boolean"},
                       _transport("media.stop", VK_MEDIA_STOP, "Sent the stop media key."),
                       side_effect="external_action", tags=("stop", "media", "playback", "halt"),
                       aliases=("stop the music",)),
        ToolDefinition("display.info", "Read connected display adapters, resolution, and refresh rate.",
                       0, 0, {}, {"displays": "array", "active_count": "integer"}, _display_info,
                       timeout_seconds=60, side_effect="read",
                       tags=("display", "monitor", "screen", "resolution", "refresh", "hz", "gpu"),
                       aliases=("what resolution am i running", "my monitors", "refresh rate")),
        ToolDefinition("display.brightness", "Read panel brightness, or set it when percent is supplied.",
                       2, 2, {"percent": int}, {"percent": "integer", "changed": "boolean"}, _brightness,
                       timeout_seconds=40, side_effect="external_action",
                       tags=("brightness", "dim", "bright", "screen", "display", "backlight"),
                       aliases=("dim my screen", "brighten the display", "screen too dark")),
    )
