"""Local file tools with explicit permission levels."""

from __future__ import annotations

import shutil
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.sensitive_paths import is_sensitive_path

MAX_READ_CHARS = 200_000


def _path(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("path is required")
    return Path(text).expanduser().resolve()


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stat(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    path = _path(args.get("path"))
    # stat() errors other than absence must not masquerade as verified deletion.
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return ToolResult("file.stat", True, "Path does not exist.", {"path": str(path), "exists": False})
    is_folder = path.is_dir()
    data = {"path": str(path), "exists": True, "type": "folder" if is_folder else "file",
            "size_bytes": None if is_folder else metadata.st_size}
    if args.get("hash") and path.is_file():
        data["sha256"] = _sha256(path)
    return ToolResult("file.stat", True, "Inspected path metadata.", data)


def _read(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    path = _path(args.get("path"))
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    text = raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
    truncated = len(text) > MAX_READ_CHARS
    if truncated:
        text = text[:MAX_READ_CHARS]
    return ToolResult("file.read", True, f"Read {path.name}.", {"path": str(path), "text": text,
                      "truncated": truncated, "sha256": hashlib.sha256(raw).hexdigest()})


def _list_dir(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    path = _path(args.get("path"))
    limit = max(1, min(int(args.get("limit", 50)), 200))
    kind = str(args.get("kind", "all") or "all").strip().lower()
    if kind not in {"all", "file", "folder"}:
        raise ValueError("kind must be all, file, or folder")
    if not path.is_dir():
        raise NotADirectoryError(path)
    entries: list[dict[str, Any]] = []
    try:
        children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
    except OSError as exc:
        raise OSError(f"could not list {path}: {exc}") from exc
    for child in children:
        try:
            if is_sensitive_path(child):
                continue
            child_kind = "folder" if child.is_dir() else "file"
            if kind != "all" and child_kind != kind:
                continue
            entries.append({"name": child.name, "path": str(child), "type": child_kind})
            if len(entries) >= limit:
                break
        except OSError:
            continue
    if entries:
        names = ", ".join(row["name"] for row in entries[:10])
        suffix = "" if len(entries) <= 10 else f", and {len(entries) - 10} more"
        noun = "folders" if kind == "folder" else "files" if kind == "file" else "items"
        message = f"{path.name or path} {noun} include {names}{suffix}."
    else:
        noun = "folders" if kind == "folder" else "files" if kind == "file" else "items"
        message = f"{path.name or path} has no {noun}."
    return ToolResult("file.list_dir", True, message, {"path": str(path), "entries": entries})



def _mkdir(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    path = _path(args.get("path"))
    existed = path.exists()
    if existed and not path.is_dir():
        raise FileExistsError(f"a non-folder item already exists at {path}")
    path.mkdir(parents=True, exist_ok=True)
    message = f"Folder {path.name} already exists." if existed else f"Created folder {path.name}."
    return ToolResult("file.mkdir", True, message, {"path": str(path), "created": not existed})


def _locate(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    """Resolve an exact local basename without guessing a relative path."""
    name = str(args.get("name", "") or "").strip()
    kind = str(args.get("kind", "all") or "all").strip().lower()
    if not name or name in {".", ".."} or any(sep in name for sep in ("/", "\\")):
        raise ValueError("name must be one exact file or folder basename")
    if kind not in {"all", "file", "folder"}:
        raise ValueError("kind must be all, file, or folder")

    root_arg = str(args.get("root", "") or "").strip()
    if root_arg:
        roots = [_path(root_arg)]
        recursive = True
    else:
        home = Path.home()
        roots = [home / "Downloads", home / "Desktop", home / "Documents", Path.cwd()]
        recursive = False

    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        try:
            if not root.is_dir():
                continue
            candidates = root.rglob(name) if recursive else (root / name,)
            for candidate in candidates:
                try:
                    if (is_sensitive_path(candidate) or not candidate.exists()
                            or candidate.name.casefold() != name.casefold()):
                        continue
                    candidate_kind = "folder" if candidate.is_dir() else "file"
                    if kind != "all" and candidate_kind != kind:
                        continue
                    resolved = str(candidate.resolve())
                    if resolved.casefold() in seen:
                        continue
                    seen.add(resolved.casefold())
                    matches.append({"name": candidate.name, "path": resolved, "type": candidate_kind})
                    if len(matches) >= 20:
                        break
                except OSError:
                    continue
        except OSError:
            continue
        if len(matches) >= 20:
            break

    if not matches:
        message = f"I couldn't find {name} in the common local locations."
    elif len(matches) == 1:
        message = f"Found {name} at {matches[0]['path']}."
    else:
        message = f"Found {len(matches)} items named {name}; the location is ambiguous."
    return ToolResult("file.locate", True, message, {"name": name, "matches": matches})

def _search(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    supplied = str(args.get('root') or '').strip()
    roots = [_path(supplied)] if supplied else [Path.home() / name for name in ('Downloads', 'Documents', 'Desktop')]
    query = str(args.get("query", "")).strip().casefold()
    limit = max(1, min(int(args.get("limit", 50)), 200))
    if supplied and not roots[0].is_dir():
        raise NotADirectoryError(roots[0])
    excluded = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.mypy_cache',
                'site-packages', 'dist', 'build', '.next'}
    tokens = [word for word in query.split() if word]
    found = []
    scanned = 0
    deadline = time.monotonic() + 10
    truncated = False
    for root in roots:
        if not root.is_dir():
            continue
        for current, dirs, names in os.walk(root, onerror=lambda _: None):
            dirs[:] = [name for name in dirs if name.casefold() not in excluded
                       and not (Path(current) / name).is_symlink()
                       and not (Path(current) / name).is_junction()]
            for name in names:
                scanned += 1
                if scanned > 20000 or time.monotonic() >= deadline:
                    truncated = True
                    break
                path = Path(current) / name
                try:
                    if (path.is_symlink() or not path.resolve().is_relative_to(root.resolve())
                            or is_sensitive_path(path) or not path.is_file()):
                        continue
                    title = path.stem.casefold()
                    if tokens and not all(token in title or token in name.casefold() for token in tokens):
                        continue
                    score = (20 if title == query else 10 if query and query in title else 0)
                    score += sum(2 for token in tokens if token in title)
                    score += 3 if path.suffix.casefold() in {'.pdf', '.docx', '.xlsx', '.txt', '.md'} else 0
                    score -= len(path.relative_to(root).parts)
                    found.append((score, str(path)))
                except OSError:
                    continue
            if truncated:
                break
        if truncated:
            break
    found.sort(key=lambda item: (-item[0], item[1].casefold()))
    matches = [path for _, path in found[:limit]]
    return ToolResult('file.search', True, f'Found {len(matches)} matching files.' +
                      (' Search was limited.' if truncated else ''),
                      {'matches': matches, 'root': supplied or 'common user folders',
                       'roots': [str(root) for root in roots if root.is_dir()],
                       'truncated': truncated or len(found) > limit})


def _write(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    path = _path(args.get("path"))
    text = str(args.get("text", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return ToolResult("file.write", True, f"Created {path.name}." if not text else f"Wrote {path.name}.", {"path": str(path), "chars": len(text)})


def _copy(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    src = _path(args.get("source")); dst = _path(args.get("destination"))
    if not src.is_file():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    source_sha256 = _sha256(src)
    final = shutil.copy2(src, dst)
    return ToolResult("file.copy", True, f"Copied {src.name}.", {"source": str(src), "destination": str(final), "source_sha256": source_sha256})


def _move(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    src = _path(args.get("source")); dst = _path(args.get("destination"))
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    final = shutil.move(str(src), str(dst))
    return ToolResult("file.move", True, f"Moved {src.name}.", {"source": str(src), "destination": str(final)})


def _delete(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    path = _path(args.get("path"))
    recursive = bool(args.get("recursive", False))
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        if not recursive:
            raise PermissionError("directory deletion requires recursive=true and explicit confirmation")
        shutil.rmtree(path)
        return ToolResult("file.delete", True, f"Deleted folder {path.name}.", {"path": str(path), "recursive": True})
    path.unlink()
    return ToolResult("file.delete", True, f"Deleted {path.name}.", {"path": str(path), "recursive": False})


def _protected_path_reason(args: Mapping[str, Any]) -> str | None:
    candidates = [args.get("path"), args.get("destination")]
    protected = []
    import os
    for key in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(key)
        if value:
            try:
                protected.append(Path(value).resolve())
            except OSError:
                pass
    for candidate in candidates:
        if not candidate:
            continue
        try:
            resolved = Path(str(candidate)).expanduser().resolve()
        except OSError:
            continue
        for root in protected:
            try:
                resolved.relative_to(root)
                return f"writing/moving into protected system path {root} requires confirmation"
            except ValueError:
                continue
    return None


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("file.stat", "Check whether a path exists and its type. Existing regular files include measured size_bytes; folder size is unknown (null). Optionally return the full SHA-256 file hash.", 0, 0, {"path": str, "hash": bool}, {"path": "string", "exists": "boolean", "type": "optional file|folder", "size_bytes": "optional integer|null", "sha256": "optional string"}, _stat, retry_safe=True),
        ToolDefinition("file.read", "Read an ordinary local text file and return its observed byte hash.", 0, 0, {"path": str}, {"text": "string", "sha256": "string"}, _read),
        ToolDefinition("file.list_dir", "List files and folders directly inside a local folder.", 0, 0, {"path": str, "limit": int, "kind": str}, {"entries": "array"}, _list_dir),
        ToolDefinition("file.mkdir", "Create a local folder, including missing parent folders.", 2, 2, {"path": str}, {"path": "string"}, _mkdir, requires_confirmation_if=_protected_path_reason),
        ToolDefinition("file.locate", "Locate an exact file/folder basename. With no root, checks common user locations (Downloads, Desktop, Documents, current working directory) without guessing; with root, searches recursively under it.", 0, 0, {"name": str, "kind": str, "root": str}, {"matches": "array"}, _locate),
        ToolDefinition("file.search", "Search filenames in Downloads, Documents and Desktop by default, or recursively under an explicit folder. Excludes dependency and credential paths.", 0, 0, {"root": str, "query": str, "limit": int}, {"matches": "array"}, _search),
        ToolDefinition("file.write", "Create or replace a local text file.", 2, 2, {"path": str, "text": str}, {"path": "string"}, _write, requires_confirmation_if=_protected_path_reason),
        ToolDefinition("file.copy", "Copy a local file.", 2, 2, {"source": str, "destination": str}, {"destination": "string"}, _copy, requires_confirmation_if=_protected_path_reason),
        ToolDefinition("file.move", "Move or rename a local file or folder.", 2, 2, {"source": str, "destination": str}, {"destination": "string"}, _move, requires_confirmation_if=_protected_path_reason),
        ToolDefinition("file.delete", "Permanently delete one local file or, with recursive=true, a folder tree. Always requires explicit confirmation.", 3, 3, {"path": str, "recursive": bool}, {"path": "string"}, _delete),
    )
