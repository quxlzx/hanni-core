"""Disk-space capabilities: where the space went, and bounded cleanup.

Every measurement here is read-only. The one capability that removes bytes,
``disk.cleanup_temp``, is Level 3, always confirmation-gated, restricted to
known temporary directories, and reports a dry run unless ``apply`` is true.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

_MAX_SCAN_ENTRIES = 200_000


def _gb(value: float) -> float:
    return round(value / 1024 ** 3, 2)


def _resolve(raw: object, label: str) -> Path:
    path = Path(str(raw or "")).expanduser()
    if not str(raw or "").strip():
        raise ValueError(f"{label} is required")
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def _walk_files(root: Path) -> Iterator[Path]:
    seen = 0
    for current, dirnames, filenames in os.walk(root, onerror=lambda _: None):
        dirnames[:] = [d for d in dirnames if not d.startswith(("$", ".")) and not (Path(current) / d).is_symlink() and not (Path(current) / d).is_junction()]
        for name in filenames:
            seen += 1
            if seen > _MAX_SCAN_ENTRIES:
                return
            item = Path(current) / name
            if not item.is_symlink() and item.resolve().is_relative_to(root.resolve()):
                yield item


def _usage(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    rows: list[dict[str, Any]] = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        rows.append({"drive": part.mountpoint, "filesystem": part.fstype,
                     "total_gb": _gb(usage.total), "used_gb": _gb(usage.used),
                     "free_gb": _gb(usage.free), "percent_used": round(usage.percent, 1),
                     "low_space": usage.percent >= 90})
    rows.sort(key=lambda row: -row["percent_used"])
    tight = [row["drive"] for row in rows if row["low_space"]]
    requested = str(args.get('drive') or '').strip().upper().rstrip(':\\/')
    if requested and (len(requested) != 1 or not requested.isalpha()):
        raise ValueError('drive must be a single letter')
    present = any(row['drive'].upper().startswith(requested + ':') for row in rows) if requested else None
    if requested and not present:
        message = f"{requested}: is not among the mounted fixed drives."
    else:
        reported = [row for row in rows if row['drive'].upper().startswith(requested + ':')] if requested else rows
        message = '; '.join(f"{r['drive']} {r['free_gb']} GB free of {r['total_gb']} GB ({r['percent_used']}% used)"
                            for r in reported) or 'No fixed drives reported.'
    return ToolResult("disk.usage", True,
                      message, {"drives": rows, "low_space_drives": tight,
                                "requested_drive": requested or None, "present": present})


def _folder_size(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve(args.get("path"), "path")
    if not root.is_dir():
        raise ValueError("path must be a folder")
    total = 0
    files = 0
    for item in _walk_files(root):
        try:
            total += item.stat().st_size
            files += 1
        except OSError:
            continue
    return ToolResult("disk.folder_size", True,
                      f"{root} holds {_gb(total)} GB across {files} file(s).",
                      {"path": str(root), "size_gb": _gb(total), "size_bytes": total, "file_count": files,
                       "truncated": files >= _MAX_SCAN_ENTRIES})


def _largest_files(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve(args.get("root"), "root")
    if not root.is_dir():
        raise ValueError("root must be a folder")
    limit = max(1, min(int(args.get("limit", 15)), 100))
    min_mb = max(0, min(int(args.get("min_mb", 50)), 100_000))
    found: list[tuple[int, Path]] = []
    for item in _walk_files(root):
        try:
            size = item.stat().st_size
        except OSError:
            continue
        if size >= min_mb * 1024 * 1024:
            found.append((size, item))
    found.sort(key=lambda pair: -pair[0])
    rows = [{"path": str(path), "size_gb": _gb(size), "size_mb": round(size / 1024 ** 2, 1)}
            for size, path in found[:limit]]
    return ToolResult("disk.largest_files", True,
                      f"{len(found)} file(s) at or above {min_mb} MB under {root}; largest listed first.",
                      {"root": str(root), "files": rows, "matches": len(found)})


def _largest_folders(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _resolve(args.get("root"), "root")
    if not root.is_dir():
        raise ValueError("root must be a folder")
    limit = max(1, min(int(args.get("limit", 10)), 50))
    rows: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        total = 0
        for item in _walk_files(child):
            try:
                total += item.stat().st_size
            except OSError:
                continue
        rows.append({"path": str(child), "name": child.name, "size_gb": _gb(total), "size_bytes": total})
    rows.sort(key=lambda row: -row["size_bytes"])
    return ToolResult("disk.largest_folders", True,
                      f"Immediate subfolders of {root} ranked by size; largest is "
                      + (f"{rows[0]['name']} at {rows[0]['size_gb']} GB." if rows else "none."),
                      {"root": str(root), "folders": rows[:limit]})


def _temp_roots() -> list[Path]:
    candidates = [Path(tempfile.gettempdir())]
    local = os.environ.get("LOCALAPPDATA")
    windir = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if local:
        candidates.append(Path(local) / "Temp")
    if windir:
        candidates.append(Path(windir) / "Temp")
    unique: list[Path] = []
    for path in candidates:
        resolved = path.expanduser()
        if resolved.is_dir() and resolved not in unique:
            unique.append(resolved)
    return unique


def _cleanup_temp(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    apply_changes = bool(args.get("apply", False))
    older_than_days = max(1, min(int(args.get("older_than_days", 7)), 365))
    cutoff = time.time() - older_than_days * 86_400
    reclaimed = 0
    removed = 0
    skipped = 0
    samples: list[str] = []
    for root in _temp_roots():
        for item in _walk_files(root):
            try:
                stat = item.stat()
            except OSError:
                skipped += 1
                continue
            if stat.st_mtime > cutoff:
                continue
            reclaimed += stat.st_size
            if len(samples) < 20:
                samples.append(str(item))
            if apply_changes:
                try:
                    context.emergency_stop.guard("temporary file deletion")
                    if not item.resolve().is_relative_to(root.resolve()):
                        raise ValueError("temporary path escaped its root")
                    item.unlink()
                    removed += 1
                except OSError:
                    skipped += 1
    verb = "Removed" if apply_changes else "Would remove"
    return ToolResult("disk.cleanup_temp", True,
                      f"{verb} temporary files older than {older_than_days} days: about {_gb(reclaimed)} GB"
                      + (f" ({removed} file(s) deleted, {skipped} skipped)." if apply_changes else " (dry run; set apply=true to delete)."),
                      {"applied": apply_changes, "older_than_days": older_than_days,
                       "reclaimable_gb": _gb(reclaimed), "removed_files": removed,
                       "skipped": skipped, "roots": [str(r) for r in _temp_roots()], "sample": samples})


def _recycle_bin(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    total = 0
    count = 0
    for part in psutil.disk_partitions(all=False):
        candidate = Path(part.mountpoint) / "$Recycle.Bin"
        if not candidate.is_dir():
            continue
        for item in _walk_files(candidate):
            try:
                total += item.stat().st_size
                count += 1
            except OSError:
                continue
    return ToolResult("disk.recycle_bin_size", True,
                      f"Recycle Bin holds about {_gb(total)} GB across {count} readable item(s).",
                      {"size_gb": _gb(total), "item_count": count,
                       "note": "emptying the Recycle Bin is a Level 3 owner action and is not performed here"})


def _free_space_check(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    drive = str(args.get("drive", "")).strip() or (os.environ.get("SystemDrive", "/") + os.sep if os.name == "nt" else "/")
    if os.name == 'nt' and len(drive) == 1 and drive.isalpha():
        drive += ':\\'
    needed_gb = max(0.0, float(args.get("needed_gb", 0)))
    if os.name == 'nt' and len(drive.rstrip('\\/')) == 2 and drive[1] == ':':
        mounted = {part.mountpoint[:2].casefold() for part in psutil.disk_partitions(all=False)
                   if part.fstype and 'cdrom' not in part.opts.casefold()}
        if drive[:2].casefold() not in mounted:
            return ToolResult('disk.free_space', True, f'{drive[:2].upper()} is not among the mounted fixed drives.',
                              {'drive': drive[:2].upper(), 'present': False, 'free_gb': None,
                               'total_gb': None, 'needed_gb': needed_gb, 'sufficient': False})
    usage = shutil.disk_usage(drive)
    free = _gb(usage.free)
    ok = free >= needed_gb
    return ToolResult("disk.free_space", ok,
                      f"{drive} has {free} GB free"
                      + (f"; {needed_gb} GB requested, {'enough' if ok else 'not enough'} room." if needed_gb else "."),
                      {"drive": drive, "present": True, "free_gb": free, "total_gb": _gb(usage.total),
                       "needed_gb": needed_gb, "sufficient": ok})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("disk.usage", "Enumerate mounted fixed drives, their free and used space, and check if a requested drive exists.",
                       0, 0, {'drive': str}, {"drives": "array", "low_space_drives": "array", "present": "boolean|null"}, _usage,
                       side_effect="read", tags=("disk", "drive", "space", "storage", "full", "capacity", "gb"),
                       aliases=("how much space do i have", "is my drive full", "c drive space")),
        ToolDefinition("disk.free_space", "Check free space on one drive, optionally against a required amount before a large write.",
                       0, 0, {"drive": str, "needed_gb": (int, float)},
                       {"drive": "string", "free_gb": "number", "sufficient": "boolean"}, _free_space_check,
                       side_effect="read", tags=("disk", "space", "free", "room", "storage", "verify"),
                       aliases=("enough room", "do i have space")),
        ToolDefinition("disk.folder_size", "Measure the total size and file count of one folder tree.",
                       0, 0, {"path": str}, {"path": "string", "size_gb": "number", "file_count": "integer"}, _folder_size,
                       timeout_seconds=120, side_effect="read",
                       tags=("folder", "size", "disk", "storage", "measure", "how big"),
                       aliases=("how big is this folder", "size of directory")),
        ToolDefinition("disk.largest_files", "Find the biggest files under a folder so space can be reclaimed deliberately.",
                       0, 0, {"root": str, "limit": int, "min_mb": int},
                       {"root": "string", "files": "array", "matches": "integer"}, _largest_files,
                       timeout_seconds=180, side_effect="read",
                       tags=("disk", "space", "large", "biggest", "files", "cleanup", "hogging", "storage"),
                       aliases=("what is taking up space", "biggest files", "space hogs")),
        ToolDefinition("disk.largest_folders", "Rank the immediate subfolders of a folder by total size.",
                       0, 0, {"root": str, "limit": int}, {"root": "string", "folders": "array"}, _largest_folders,
                       timeout_seconds=180, side_effect="read",
                       tags=("disk", "space", "folder", "biggest", "storage", "breakdown"),
                       aliases=("which folder is biggest", "where did my space go")),
        ToolDefinition("disk.recycle_bin_size", "Measure how much space the Recycle Bin is holding.",
                       0, 0, {}, {"size_gb": "number", "item_count": "integer"}, _recycle_bin,
                       timeout_seconds=120, side_effect="read",
                       tags=("recycle", "bin", "trash", "deleted", "disk", "space"),
                       aliases=("recycle bin", "trash size")),
        ToolDefinition("disk.cleanup_temp", "Report, and with apply=true delete, temporary files older than a chosen age in known temp folders only. Always requires explicit confirmation.",
                       3, 3, {"apply": bool, "older_than_days": int},
                       {"applied": "boolean", "reclaimable_gb": "number", "removed_files": "integer"}, _cleanup_temp,
                       timeout_seconds=300, side_effect="destructive",
                       tags=("cleanup", "temp", "temporary", "free", "space", "disk", "clean"),
                       aliases=("clean up my temp files", "free up space")),
    )
