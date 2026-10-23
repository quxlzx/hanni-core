"""PowerShell execution with mandatory confirmation for arbitrary code."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

_DANGEROUS_PATTERNS = (
    r"\bformat-volume\b",
    r"\bdiskpart\b",
    r"\bclear-disk\b",
    r"\bremove-partition\b",
    r"\bremove-item\b",
    r"\bdel(?:ete)?\b[^\r\n]*/s",
    r"\brd\b[^\r\n]*/s",
    r"\bshutdown\b",
    r"\brestart-computer\b",
    r"\bstop-computer\b",
    r"\bset-executionpolicy\b",
    r"\bdisable-windowsoptionalfeature\b",
    r"\bset-mppreference\b",
    r"\bnet\s+user\b",
    r"\bset-localuser\b",
    r"\bbcdedit\b",
    r"\breg\s+delete\b",
    r"\bstart-process\b[^\r\n]*-verb\s+runas\b",
    r"\brunas(?:\.exe)?\b",
    r"(?:^|\s)-(?:encodedcommand|enc)\b",
)
_DANGEROUS_RE = re.compile("|".join(f"(?:{p})" for p in _DANGEROUS_PATTERNS), re.IGNORECASE)


def dangerous_reason(args: Mapping[str, Any]) -> str | None:
    command = str(args.get("command", ""))
    if _DANGEROUS_RE.search(command):
        return "the PowerShell command matches a destructive/high-impact pattern"
    return None


def _run(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    command = str(args.get("command", "")).strip()
    timeout = max(1, min(int(args.get("timeout", 30)), 300))
    if not command:
        raise ValueError("command is required")
    if os.name != "nt":
        raise OSError("PowerShell execution is available only on Windows in V1")
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    stdout = proc.stdout[-30_000:]
    stderr = proc.stderr[-30_000:]
    ok = proc.returncode == 0
    if ok:
        preview = " ".join(stdout.strip().split())
        if preview:
            if len(preview) > 800:
                preview = preview[:797] + "..."
            summary = preview
        else:
            summary = "PowerShell command completed successfully."
    else:
        detail = " ".join(stderr.strip().split())
        if len(detail) > 500:
            detail = detail[:497] + "..."
        summary = f"PowerShell command failed with exit code {proc.returncode}." + (f" {detail}" if detail else "")
    return ToolResult("powershell.run", ok, summary, {"exit_code": proc.returncode, "stdout": stdout, "stderr": stderr})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition(
            "powershell.run",
            "Run a local non-elevated PowerShell command after explicit confirmation and capture stdout/stderr.",
            # PowerShell can construct command names, invoke scripts and access
            # arbitrary APIs. Pattern matching supplies an explanation, never
            # authorization to execute code without owner confirmation.
            3,
            3,
            {"command": str, "timeout": int},
            {"exit_code": "integer", "stdout": "string", "stderr": "string"},
            _run,
            timeout_seconds=300,
            requires_confirmation_if=dangerous_reason,
        ),
    )
