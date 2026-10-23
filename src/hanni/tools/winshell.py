"""Shared, non-elevated Windows shell helper for registered capability handlers.

Capability handlers must never build shell strings from unvalidated model text.
Every caller in this package passes a fixed command template and supplies
arguments through :func:`quote`, which produces a PowerShell single-quoted
literal. This keeps the deterministic risk boundary in
``hanni.tools.powershell`` the only place where free-form owner commands run.
"""

from __future__ import annotations

import json
import base64
import os
import subprocess
from typing import Any


class WindowsOnlyError(OSError):
    """Raised when a Windows-only capability is invoked on another platform."""


def is_windows() -> bool:
    return os.name == "nt"


def require_windows(capability: str) -> None:
    if not is_windows():
        raise WindowsOnlyError(f"{capability} is available only on Windows in V1")


def quote(value: object) -> str:
    """Return a PowerShell single-quoted literal for an argument value."""
    if "\x00" in str(value):
        raise ValueError("PowerShell arguments cannot contain NUL")
    # PowerShell recognizes typographic quote characters as delimiters too.
    # Encode such data instead of allowing it into the parser's quote syntax.
    if any(char in str(value) for char in "‘’‚‛"):
        encoded = base64.b64encode(str(value).encode("utf-8")).decode("ascii")
        return "([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "')))"
    return "'" + str(value).replace("'", "''") + "'"


def run_powershell(command: str, *, timeout: int = 20, capability: str = "windows capability") -> str:
    """Run a fixed non-elevated PowerShell template and return stdout."""
    require_windows(capability)
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); " + command],
        capture_output=True,
        text=True,
        timeout=max(1, min(int(timeout), 120)),
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        detail = " ".join((proc.stderr or "").split())[:300]
        raise RuntimeError(f"{capability} failed (exit {proc.returncode}){': ' + detail if detail else ''}")
    return proc.stdout


def run_powershell_json(command: str, *, timeout: int = 20, capability: str = "windows capability") -> Any:
    """Run a template that ends in ConvertTo-Json and decode the result."""
    text = run_powershell(command, timeout=timeout, capability=capability).strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{capability} returned unparsable output") from exc


def as_rows(payload: Any) -> list[dict[str, Any]]:
    """Normalise ConvertTo-Json output, which collapses single rows to an object."""
    if payload is None:
        return []
    if isinstance(payload, dict):
        return [payload]
    return [row for row in payload if isinstance(row, dict)]
