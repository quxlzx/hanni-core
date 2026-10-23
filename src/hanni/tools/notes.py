"""Owner-explicit quick notes, kept as plain daily Markdown files.

This is deliberately *not* durable memory. M9.0 memory is a structured SQLite
record with source and confidence, written only on an explicit remember command
(D-0021). Notes are the other thing owners ask for - "jot this down" - and they
land in readable, greppable files under the data directory that the owner can
edit or delete without H.A.N.N.I.'s help.

Note text passes the same privacy validator durable memory uses, so passwords,
2FA codes, API keys, and card numbers are refused rather than written to disk.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from hanni.memory.privacy import SensitiveMemoryError, validate_memory_text
from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

_MAX_CHARS = 2_000
_MAX_FILES = 400


def _notes_dir(root: Path) -> Path:
    path = Path(root) / "notes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _today_file(root: Path) -> Path:
    return _notes_dir(root) / f"{datetime.now().astimezone():%Y-%m-%d}.md"


def _append_handler(root: Path):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        raw = str(args.get("text", ""))
        tag = str(args.get("tag", "") or "").strip()
        if tag and not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", tag):
            raise ValueError("tag must be 1-24 letters, digits, hyphen or underscore")
        try:
            text = validate_memory_text(raw, max_chars=_MAX_CHARS)
        except SensitiveMemoryError as exc:
            raise ValueError(f"refused: {exc}") from exc
        stamp = datetime.now().astimezone()
        line = f"- {stamp:%H:%M} {('#' + tag + ' ') if tag else ''}{text}\n"
        target = _today_file(root)
        new_file = not target.exists()
        with target.open("a", encoding="utf-8") as handle:
            if new_file:
                handle.write(f"# Notes for {stamp:%A, %d %B %Y}\n\n")
            handle.write(line)
        total = sum(1 for entry in target.read_text(encoding="utf-8").splitlines()
                    if entry.startswith("- "))
        return ToolResult("note.append", True,
                          f"Noted in {target.name}: {text[:120]}",
                          {"path": str(target), "text": text, "tag": tag,
                           "notes_today": total, "created_file": new_file})
    return handler


def _list_handler(root: Path):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        day = str(args.get("date", "") or "").strip()
        limit = max(1, min(int(args.get("limit", 25)), 200))
        if day and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("date must be YYYY-MM-DD")
        target = _notes_dir(root) / f"{day}.md" if day else _today_file(root)
        if not target.exists():
            return ToolResult("note.list", True, f"No notes recorded for {target.stem}.",
                              {"date": target.stem, "notes": [], "total": 0})
        entries = [line[2:].strip() for line in target.read_text(encoding="utf-8").splitlines()
                   if line.startswith("- ")]
        return ToolResult("note.list", True,
                          f"{len(entries)} note(s) for {target.stem}."
                          + (f" Latest: {entries[-1][:120]}" if entries else ""),
                          {"date": target.stem, "path": str(target),
                           "notes": entries[-limit:], "total": len(entries)})
    return handler


def _search_handler(root: Path):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        query = " ".join(str(args.get("query", "")).split())
        limit = max(1, min(int(args.get("limit", 25)), 200))
        if not query:
            raise ValueError("query is required")
        needle = query.casefold()
        hits: list[dict[str, Any]] = []
        files = sorted(_notes_dir(root).glob("*.md"), reverse=True)[:_MAX_FILES]
        for path in files:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                if line.startswith("- ") and needle in line.casefold():
                    hits.append({"date": path.stem, "text": line[2:].strip()})
                    if len(hits) >= limit:
                        break
            if len(hits) >= limit:
                break
        return ToolResult("note.search", True,
                          f"{len(hits)} note(s) mention '{query}' across {len(files)} day file(s)."
                          + (f" Most recent: {hits[0]['text'][:120]}" if hits else ""),
                          {"query": query, "matches": hits, "match_count": len(hits),
                           "days_searched": len(files)})
    return handler


def _days_handler(root: Path):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        limit = max(1, min(int(args.get("limit", 30)), 400))
        rows = []
        for path in sorted(_notes_dir(root).glob("*.md"), reverse=True)[:limit]:
            try:
                count = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                            if line.startswith("- "))
            except OSError:
                continue
            rows.append({"date": path.stem, "notes": count,
                         "modified_utc": datetime.fromtimestamp(path.stat().st_mtime,
                                                                tz=timezone.utc).isoformat()})
        return ToolResult("note.days", True,
                          f"Notes exist for {len(rows)} day(s)."
                          + (f" Most recent: {rows[0]['date']} with {rows[0]['notes']} note(s)." if rows else ""),
                          {"days": rows, "total": len(rows), "directory": str(_notes_dir(root))})
    return handler


def definitions(data_dir: Path) -> tuple[ToolDefinition, ...]:
    root = Path(data_dir)
    return (
        ToolDefinition("note.append", "Append an owner-dictated note to today's plain Markdown note file. Refuses credential-shaped text.",
                       2, 2, {"text": str, "tag": str},
                       {"path": "string", "notes_today": "integer"}, _append_handler(root),
                       side_effect="reversible_write",
                       tags=("note", "jot", "write", "down", "capture", "record", "remember", "todo"),
                       aliases=("jot this down", "make a note", "write that down", "note to self")),
        ToolDefinition("note.list", "List the notes recorded on a given day (today by default).",
                       0, 0, {"date": str, "limit": int}, {"notes": "array", "total": "integer"},
                       _list_handler(root), side_effect="read",
                       tags=("note", "notes", "today", "list", "recorded", "captured"),
                       aliases=("what did i note today", "read my notes", "my notes")),
        ToolDefinition("note.search", "Search every note file for a phrase, newest day first.",
                       0, 0, {"query": str, "limit": int},
                       {"matches": "array", "match_count": "integer"}, _search_handler(root),
                       timeout_seconds=60, side_effect="read",
                       tags=("note", "notes", "search", "find", "mention", "did i note"),
                       aliases=("did i note anything about", "search my notes", "find that note")),
        ToolDefinition("note.days", "List which days have notes and how many, to orient a search.",
                       0, 0, {"limit": int}, {"days": "array", "total": "integer"}, _days_handler(root),
                       side_effect="read",
                       tags=("note", "notes", "days", "history", "when", "calendar"),
                       aliases=("which days did i take notes", "note history")),
    )
