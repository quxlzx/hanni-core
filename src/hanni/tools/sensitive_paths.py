"""Conservative filename guard for content sent to a resident model.

This is a content-exposure boundary, not an authorization decision for local
manual file operations. Resolve links so an innocently named symlink cannot
point at a known credential file.
"""
from __future__ import annotations

from pathlib import Path


_NAMES = frozenset({
    "credentials.json", "google-oauth-client.json", "id_rsa", "id_ed25519",
    "id_ecdsa", "id_dsa", "authorized_user.json",
})
_PRIVATE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".kdbx"})
_PRIVATE_DIRS = frozenset({".ssh", ".aws", ".azure", "gcloud"})


def is_sensitive_path(value: object) -> bool:
    """Identify well-known local credential paths without reading their data."""
    if not isinstance(value, (str, Path)) or not str(value).strip():
        return False
    try:
        path = Path(value).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return True  # Fail closed when a path cannot be safely classified.
    name = path.name.casefold()
    parts = {part.casefold() for part in path.parts[:-1]}
    return (
        name in _NAMES
        or (name.startswith(".env") and name != ".env.example")
        or (name.startswith("client_secret") and name.endswith(".json"))
        or ("token" in name and name.endswith(".json"))
        or any(marker in name for marker in ("credential", "secret", "password", "private_key", "oauth"))
        or path.suffix.casefold() in _PRIVATE_SUFFIXES
        or name in _PRIVATE_DIRS
        or bool(parts & _PRIVATE_DIRS)
    )
