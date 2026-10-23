"""File-inventory insight: recency, duplicates, composition, and opening files.

These answer the questions that come before an organise or cleanup task -
what did I touch recently, what is duplicated, what is actually in this folder -
so a plan can be grounded in real observations rather than assumptions.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import is_windows

_MAX_ENTRIES = 100_000
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "$RECYCLE.BIN",
              "System Volume Information", ".mypy_cache"}


def _resolve_dir(raw: object, label: str = "root") -> Path:
    path = Path(str(raw or "")).expanduser()
    if not str(raw or "").strip():
        raise ValueError(f"{label} is required")
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    if not path.is_dir():
        raise ValueError(f"{label} must be an existing folder: {path}")
    return path


def _walk(root: Path) -> Iterator[Path]:
    seen = 0
    for current, dirnames, filenames in os.walk(root, onerror=lambda _: None):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("$")]
        for name in filenames:
            seen += 1
            if seen > _MAX_ENTRIES:
                return
            yield Path(current) / name


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _recent(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve_dir(args.get("root"))
    hours = max(1, min(int(args.get("hours", 24)), 24 * 90))
    limit = max(1, min(int(args.get("limit", 25)), 200))
    pattern = str(args.get("extension", "") or "").casefold().lstrip(".")
    cutoff = time.time() - hours * 3600
    rows: list[dict[str, Any]] = []
    for item in _walk(root):
        try:
            stat = item.stat()
        except OSError:
            continue
        if stat.st_mtime < cutoff:
            continue
        if pattern and item.suffix.casefold().lstrip(".") != pattern:
            continue
        rows.append({"path": str(item), "name": item.name, "modified_utc": _iso(stat.st_mtime),
                     "size_kb": round(stat.st_size / 1024, 1), "extension": item.suffix.casefold()})
    rows.sort(key=lambda row: row["modified_utc"], reverse=True)
    return ToolResult("file.recent", True,
                      f"{len(rows)} file(s) under {root} changed in the last {hours} hour(s)."
                      + (f" Most recent: {rows[0]['name']}." if rows else ""),
                      {"root": str(root), "hours": hours, "files": rows[:limit], "total": len(rows)})


def _duplicates(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve_dir(args.get("root"))
    min_kb = max(1, min(int(args.get("min_kb", 64)), 10 ** 7))
    limit = max(1, min(int(args.get("limit", 25)), 200))
    by_size: dict[int, list[Path]] = defaultdict(list)
    for item in _walk(root):
        try:
            size = item.stat().st_size
        except OSError:
            continue
        if size >= min_kb * 1024:
            by_size[size].append(item)

    groups: list[dict[str, Any]] = []
    reclaimable = 0
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        by_digest: dict[str, list[Path]] = defaultdict(list)
        for candidate in candidates:
            try:
                digest = hashlib.sha256()
                with candidate.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError:
                continue
            by_digest[digest.hexdigest()].append(candidate)
        for digest, matches in by_digest.items():
            if len(matches) < 2:
                continue
            reclaimable += size * (len(matches) - 1)
            groups.append({"sha256": digest, "size_kb": round(size / 1024, 1),
                           "copies": len(matches), "paths": [str(p) for p in matches[:10]]})
    groups.sort(key=lambda group: -(group["size_kb"] * (group["copies"] - 1)))
    return ToolResult("file.duplicates", True,
                      f"{len(groups)} duplicate group(s) under {root}; about "
                      f"{round(reclaimable / 1024 ** 3, 2)} GB is redundant. Nothing was deleted.",
                      {"root": str(root), "groups": groups[:limit], "group_count": len(groups),
                       "reclaimable_gb": round(reclaimable / 1024 ** 3, 2),
                       "note": "report only; deletion remains a separate confirmed action"})


def _composition(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve_dir(args.get("root"))
    limit = max(1, min(int(args.get("limit", 15)), 100))
    counts: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "bytes": 0})
    total_files = 0
    for item in _walk(root):
        try:
            size = item.stat().st_size
        except OSError:
            continue
        key = item.suffix.casefold() or "(no extension)"
        counts[key]["count"] += 1
        counts[key]["bytes"] += size
        total_files += 1
    rows = [{"extension": key, "count": int(value["count"]),
             "size_mb": round(value["bytes"] / 1024 ** 2, 1)} for key, value in counts.items()]
    rows.sort(key=lambda row: -row["count"])
    top = ", ".join(f"{row['count']} {row['extension']}" for row in rows[:5])
    return ToolResult("file.composition", True,
                      f"{total_files} file(s) under {root} across {len(rows)} extension(s)."
                      + (f" Most common: {top}." if rows else ""),
                      {"root": str(root), "types": rows[:limit], "total_files": total_files,
                       "distinct_extensions": len(rows)})


def _empty_folders(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve_dir(args.get("root"))
    limit = max(1, min(int(args.get("limit", 50)), 500))
    empties: list[str] = []
    for current, dirnames, filenames in os.walk(root, topdown=False, onerror=lambda _: None):
        if current == str(root):
            continue
        path = Path(current)
        if path.name in _SKIP_DIRS:
            continue
        try:
            if not any(path.iterdir()):
                empties.append(str(path))
        except OSError:
            continue
    return ToolResult("file.empty_folders", True,
                      f"{len(empties)} empty folder(s) under {root}. Nothing was removed.",
                      {"root": str(root), "folders": empties[:limit], "total": len(empties)})


def _open_with_default(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    raw = str(args.get("path", "")).strip()
    path = Path(raw).expanduser()
    if not raw or not path.is_absolute():
        raise ValueError("path must be an absolute path")
    if not path.exists():
        raise ValueError(f"path does not exist: {path}")
    if not is_windows():
        raise OSError("file.open is available only on Windows in V1")
    os.startfile(str(path))  # noqa: S606 - Windows shell open of an existing owner path
    return ToolResult("file.open", True,
                      f"Submitted an open request for {path.name}; application visibility has not been verified.",
                      {"path": str(path), "kind": "folder" if path.is_dir() else "file",
                       "request_submitted": True, "display_verified": False})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("file.recent", "List files changed recently under a folder, newest first.",
                       0, 0, {"root": str, "hours": int, "limit": int, "extension": str},
                       {"files": "array", "total": "integer"}, _recent,
                       timeout_seconds=180, side_effect="read",
                       tags=("recent", "changed", "modified", "today", "yesterday", "latest", "files", "worked"),
                       aliases=("what did i work on", "what changed recently", "recent files")),
        ToolDefinition("file.duplicates", "Find byte-identical duplicate files under a folder by hash, and report how much space they waste. Reports only.",
                       0, 0, {"root": str, "min_kb": int, "limit": int},
                       {"groups": "array", "reclaimable_gb": "number"}, _duplicates,
                       timeout_seconds=300, side_effect="read",
                       tags=("duplicate", "duplicates", "copies", "same", "identical", "wasted", "space", "files"),
                       aliases=("do i have duplicates", "find duplicate files", "same file twice")),
        ToolDefinition("file.composition", "Break a folder down by file extension: how many of each type and how much space they take.",
                       0, 0, {"root": str, "limit": int},
                       {"types": "array", "total_files": "integer"}, _composition,
                       timeout_seconds=180, side_effect="read",
                       tags=("types", "extension", "breakdown", "composition", "what kind", "files", "inventory"),
                       aliases=("what is in this folder", "how many pdfs", "what types of files")),
        ToolDefinition("file.empty_folders", "List empty folders under a root. Reports only; removes nothing.",
                       0, 0, {"root": str, "limit": int}, {"folders": "array", "total": "integer"}, _empty_folders,
                       timeout_seconds=180, side_effect="read",
                       tags=("empty", "folders", "cleanup", "leftover", "tidy"),
                       aliases=("any empty folders", "leftover folders")),
        ToolDefinition("file.open", "Open an existing file or folder with its default Windows application.",
                       1, 1, {"path": str}, {"path": "string", "kind": "string"}, _open_with_default,
                       side_effect="external_action",
                       tags=("open", "launch", "show", "view", "file", "folder", "explorer"),
                       aliases=("open that file", "show me that folder", "open it")),
    )
