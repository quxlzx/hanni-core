"""JSONL audit trail for tool execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from hanni.logs.redaction import redact_value


class ToolAuditLog:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / "logs" / "tool_audit.jsonl"

    def write(self, definition, request, arguments: Mapping[str, Any], *, result=None, error: Exception | None = None, duration_ms: float | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": definition.name,
            "permission_level": definition.permission_level,
            "risk_level": definition.risk_level,
            "actor_profile": request.actor_profile,
            "source": request.source,
            "confirmed": request.confirmed,
            "arguments": _audit_arguments(definition.name, arguments),
            "ok": bool(result.ok) if result is not None else False,
            "message": ("[EXTERNAL MCP RESULT]" if definition.name.startswith('mcp.') else
                        "[PRIVATE GOOGLE RESULT]" if definition.name.startswith(('email.', 'gmail.', 'google.', 'google_calendar.'))
                        else "[PRIVATE TOOL RESULT]" if definition.name.startswith('note.') or definition.name in {'powershell.run', 'notify.toast'}
                        else redact_value(result.message)) if result is not None else None,
            "duration_ms": result.duration_ms if result is not None else duration_ms,
            "error": ('[EXTERNAL MCP ERROR]' if definition.name.startswith('mcp.') else
                      '[PRIVATE TOOL ERROR]' if definition.name.startswith('note.') or definition.name in {'powershell.run', 'notify.toast'}
                      else redact_value(str(error))) if error is not None else None,
        }
        if request.correlation_id is not None:
            record['correlation_id'] = request.correlation_id
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(redact_value(record), ensure_ascii=False) + "\n")

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows: list[dict[str, Any]] = []
        for line in lines[-max(1, limit):]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows


def _audit_arguments(tool_name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if tool_name == 'notify.toast':
        return {key: '[PRIVATE NOTIFICATION]' for key in arguments}
    if tool_name.startswith('reminder.'):
        return {key: '[PRIVATE REMINDER]' for key in arguments}
    safe = dict(arguments)
    if tool_name.startswith('mcp.'):
        return {key: '[EXTERNAL MCP ARGUMENT]' for key in safe}
    if tool_name.startswith(('workspace.', 'memory.desktop_', 'learning.desktop_')):
        # Desktop records can contain personal task titles, notes and memories.
        # Preserve the fixed operation name without copying record bodies to logs.
        return {key: '[PRIVATE WORKSPACE DATA]' for key in safe}
    if tool_name.startswith(("gmail.", "email.", "google_calendar.", "google.")):
        return {key: value if key in {"account", "days", "limit"} else "[PRIVATE QUERY]"
                for key, value in safe.items()}
    if tool_name.startswith("todo."):
        return {key: value if key in {"id", "status", "days", "limit"} else "[PRIVATE TASK]"
                for key, value in safe.items()}
    if tool_name.startswith('note.'):
        return redact_value({key: value if key in {'date', 'limit'} else '[PRIVATE NOTE DATA]'
                             for key, value in safe.items()})
    if tool_name == 'powershell.run' and 'command' in safe:
        safe['command'] = f"[COMMAND:{len(str(safe['command']))} chars]"
    # Do not turn the audit trail into a copy of files the owner asked H.A.N.N.I.
    # to write. Paths and metadata remain useful for traceability.
    if tool_name in {"file.write", "clipboard.write"} and "text" in safe:
        safe["text"] = f"[CONTENT:{len(str(safe['text']))} chars]"
    return redact_value(safe)
