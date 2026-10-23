"""Environment and shell-context capabilities: variables, PATH, known folders.

Environment values can hold secrets, so ``env.get`` and ``env.list`` pass every
value through the same redactor the audit log uses and never return the raw
contents of a variable whose name looks credential-shaped.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from hanni.logs.redaction import redact_value
from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

_SECRET_NAME = ("key", "token", "secret", "password", "passwd", "credential", "auth", "session")
_REDACTED = "[REDACTED]"


def _is_secret_name(name: str) -> bool:
    lowered = name.casefold()
    return any(marker in lowered for marker in _SECRET_NAME)


def _safe_value(name: str, value: str) -> str:
    if _is_secret_name(name):
        return _REDACTED
    return str(redact_value(value))


def _list_env(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    query = str(args.get("query", "") or "").strip().casefold()
    limit = max(1, min(int(args.get("limit", 40)), 300))
    rows = []
    for name, value in sorted(os.environ.items()):
        if query and query not in name.casefold():
            continue
        rows.append({"name": name, "value": _safe_value(name, value),
                     "redacted": _is_secret_name(name), "length": len(value)})
    redacted = sum(1 for row in rows if row["redacted"])
    return ToolResult("env.list", True,
                      f"{len(rows)} environment variable(s) match"
                      + (f"; {redacted} redacted as credential-shaped." if redacted else "."),
                      {"variables": rows[:limit], "total": len(rows), "redacted_count": redacted})


def _get_env(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    name = str(args.get("name", "")).strip()
    if not name:
        raise ValueError("name is required")
    raw = os.environ.get(name)
    if raw is None:
        return ToolResult("env.get", False, f"{name} is not set in this environment.",
                          {"name": name, "set": False, "value": ""})
    return ToolResult("env.get", True,
                      f"{name} = {_safe_value(name, raw)}",
                      {"name": name, "set": True, "value": _safe_value(name, raw),
                       "redacted": _is_secret_name(name)})


def _which(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    command = str(args.get("command", "")).strip()
    if not command or any(ch in command for ch in "\\/|&;<>`\"' \t"):
        raise ValueError("command must be a bare executable name such as git or python")
    found = shutil.which(command)
    return ToolResult("env.which", bool(found),
                      f"{command} resolves to {found}." if found
                      else f"{command} is not on PATH for this process.",
                      {"command": command, "found": bool(found), "path": found or ""})


def _path_entries(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    raw = os.environ.get("PATH", "")
    entries = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for part in raw.split(os.pathsep):
        cleaned = part.strip().strip('"')
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            duplicates.append(cleaned)
            continue
        seen.add(key)
        entries.append({"path": cleaned, "exists": Path(cleaned).is_dir()})
    missing = [row["path"] for row in entries if not row["exists"]]
    return ToolResult("env.path", True,
                      f"PATH has {len(entries)} unique entry/entries; {len(missing)} do not exist"
                      + (f" and {len(duplicates)} duplicate(s) are present." if duplicates else "."),
                      {"entries": entries, "missing": missing, "duplicates": duplicates,
                       "entry_count": len(entries)})


def _user_folders(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    home = Path.home()
    candidates = {"home": home, "desktop": home / "Desktop", "documents": home / "Documents",
                  "downloads": home / "Downloads", "pictures": home / "Pictures",
                  "videos": home / "Videos", "music": home / "Music"}
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates["onedrive"] = Path(onedrive)
        for label in ("Desktop", "Documents", "Pictures"):
            candidates[f"onedrive_{label.casefold()}"] = Path(onedrive) / label
    rows = {name: {"path": str(path), "exists": path.is_dir()} for name, path in candidates.items()}
    present = [name for name, row in rows.items() if row["exists"]]
    return ToolResult("env.user_folders", True,
                      f"Resolved {len(present)} of {len(rows)} standard user folder(s) for this account.",
                      {"folders": rows, "present": present, "home": str(home)})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("env.list", "List environment variables, with credential-shaped values redacted.",
                       0, 0, {"query": str, "limit": int},
                       {"variables": "array", "total": "integer"}, _list_env,
                       side_effect="read",
                       tags=("environment", "variable", "env", "config", "setting", "path"),
                       aliases=("my environment variables", "is that variable set")),
        ToolDefinition("env.get", "Read one environment variable, redacted when its name looks credential-shaped.",
                       0, 0, {"name": str}, {"name": "string", "set": "boolean", "value": "string"}, _get_env,
                       side_effect="read",
                       tags=("environment", "variable", "env", "value", "set", "config"),
                       aliases=("what is that env var", "is it set")),
        ToolDefinition("env.which", "Resolve where an executable on PATH actually lives.",
                       0, 0, {"command": str}, {"command": "string", "found": "boolean", "path": "string"}, _which,
                       side_effect="read",
                       tags=("which", "where", "executable", "path", "installed", "command", "resolve"),
                       aliases=("is git on my path", "where is python", "do i have that command")),
        ToolDefinition("env.path", "Inspect PATH entries, flagging directories that do not exist and duplicates.",
                       0, 0, {}, {"entries": "array", "missing": "array"}, _path_entries,
                       side_effect="read",
                       tags=("path", "environment", "broken", "duplicate", "entries", "command"),
                       aliases=("what is on my path", "is my path broken")),
        ToolDefinition("env.user_folders", "Resolve this account's standard folders (Desktop, Documents, Downloads, OneDrive) to real paths.",
                       0, 0, {}, {"folders": "object", "home": "string"}, _user_folders,
                       side_effect="read",
                       tags=("folder", "downloads", "desktop", "documents", "onedrive", "home", "where", "path"),
                       aliases=("where is my downloads folder", "my documents path", "where do my files live")),
    )
