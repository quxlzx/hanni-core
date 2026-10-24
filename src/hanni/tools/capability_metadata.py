"""Stable, advisory metadata for the registered capability inventory.

This layer describes existing tools. It does not rank them or grant authority;
ToolRegistry remains the sole validation and permission boundary.
"""
from __future__ import annotations

from hanni.tools.base import ToolDefinition


# Major domains are intentionally fewer than the existing namespace prefixes.
# A new prefix must be classified explicitly instead of silently becoming a
# forty-fourth top-level domain.
NAMESPACE_DOMAIN = {
    "app": "applications", "archive": "files", "audio": "media",
    "browser": "applications", "calc": "utilities", "clipboard": "desktop",
    "device": "computer", "disk": "computer", "display": "desktop",
    "env": "development", "file": "files", "folder": "files",
    "git": "development", "gmail": "communications", "email": "communications", "google": "productivity",
    "google_calendar": "productivity", "gpu": "computer", "hanni": "assistant",
    "id": "utilities", "media": "media", "model": "assistant",
    "net": "network", "note": "productivity", "notify": "desktop",
    "power": "computer", "powershell": "development", "process": "computer",
    "project": "development", "python": "development", "random": "utilities",
    "schedule": "productivity", "security": "security", "service": "computer",
    "spotify": "media", "startup": "computer", "system": "computer",
    "text": "utilities", "time": "productivity", "timer": "productivity",
    "todo": "productivity", "ui": "desktop", "unit": "utilities",
    "web": "research", "screen": "desktop", "reminder": "productivity",
}

STATES = frozenset({"production", "experimental", "proposed", "deprecated", "blocked"})
RISKS = frozenset({"read_only", "low_risk_write", "sensitive_write", "destructive", "credential_sensitive"})
READ_WRITE_CLASSES = frozenset({"read", "write", "destructive"})


def metadata_for(definition: ToolDefinition, side_effect: str) -> dict[str, object]:
    """Derive common metadata without changing routing or execution semantics."""
    namespace = definition.name.split(".", 1)[0]
    # Runtime extensions can register before their domain taxonomy is adopted.
    # Keep them visible under one extensions domain; tests and future plugins
    # must not be able to break discovery with an unknown namespace.
    family = NAMESPACE_DOMAIN.get(namespace, "extensions")
    if definition.risk_level >= 3 or side_effect == "destructive":
        risk, read_write_class = "destructive", "destructive"
    elif namespace in {"gmail", "email"} and side_effect == "read":
        risk, read_write_class = "credential_sensitive", "read"
    elif side_effect == "read" and definition.permission_level == 0:
        risk, read_write_class = "read_only", "read"
    elif definition.permission_level <= 1 and definition.risk_level <= 1:
        risk, read_write_class = "low_risk_write", "write"
    else:
        risk, read_write_class = "sensitive_write", "write"
    source = ('mcp' if namespace == 'mcp' else
              "google_oauth" if namespace in {"gmail", "email", "google", "google_calendar"} else "local")
    return {
        "family": family,
        "subfamily": namespace,
        "risk": risk,
        "state": "production",  # Active registration, not a claim of benchmark success.
        "source": source,
        "requires": definition.prerequisites,
        "permission": f"level_{definition.permission_level}",
        "read_write_class": read_write_class,
        "priority": 0,  # Reserved metadata; retrieval ranking is unchanged.
        "introduced_version": "legacy_untracked",
    }
