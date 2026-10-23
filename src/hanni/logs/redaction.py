"""Secret redaction for log output and reports.

Two layers:

1. A process-wide registry of loaded secret values (populated by
   :func:`hanni.config.secrets.load_secrets`). Any occurrence of a registered
   value is replaced with ``[REDACTED:<NAME>]``.
2. Pattern-based scrubbing for token-shaped strings that were never registered:
   three-segment platform tokens, ``Bearer`` credentials, and ``key=value``
   pairs whose key looks like a secret.

The registry is intentionally in-memory only.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

MIN_REGISTERED_LENGTH = 6  # shorter values would shred ordinary text

_lock = threading.Lock()
_registry: dict[str, str] = {}  # name -> value
_registry_revision = 0

_THREE_SEGMENT_TOKEN = re.compile(r"[\w-]{24,}\.[\w-]{6}\.[\w-]{27,}")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*")
_KEY_VALUE = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key|private[_-]?key|authorization)\b"
    r"(\s*[:=]\s*)(['\"]?)([^\s'\",;]+)"
)


def register_secret(name: str, value: str | None) -> None:
    """Register a secret value so it is scrubbed from every rendered log record."""
    if not value or len(value) < MIN_REGISTERED_LENGTH:
        return
    global _registry_revision
    with _lock:
        if _registry.get(name) != value:
            _registry[name] = value
            _registry_revision += 1


def clear_registry() -> None:
    """Forget all registered values (tests only)."""
    global _registry_revision
    with _lock:
        _registry.clear()
        _registry_revision += 1


def secret_registry_revision() -> int:
    """Return a monotonic privacy-policy epoch without exposing secret values."""
    with _lock:
        return _registry_revision


def registered_names() -> tuple[str, ...]:
    with _lock:
        return tuple(sorted(_registry))


def redact_text(text: str) -> str:
    """Scrub registered secret values and token-shaped strings from ``text``."""
    if not text:
        return text
    with _lock:
        items = sorted(_registry.items(), key=lambda kv: len(kv[1]), reverse=True)
    for name, value in items:
        if value in text:
            text = text.replace(value, f"[REDACTED:{name}]")
    text = _THREE_SEGMENT_TOKEN.sub("[REDACTED:token]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _KEY_VALUE.sub(lambda m: m.group(0) if m.group(4).lower() == "bearer" else f"{m.group(1)}{m.group(2)}{m.group(3)}[REDACTED]", text)
    return text


def redact_value(value: Any) -> Any:
    """Redact string values and mapping keys before serialization."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {redact_text(k) if isinstance(k, str) else k: redact_value(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact_value(v) for v in value)
    return value


class RedactionFilter(logging.Filter):
    """Scrub message, args, and ``extra`` attributes before a handler formats them."""

    _STANDARD_ATTRS = frozenset(
        {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
            "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
            "relativeCreated", "thread", "threadName", "processName", "process", "message",
            "asctime", "taskName", "correlation_id", "node_id",
        }
    )

    def filter(self, record: logging.LogRecord) -> bool:
        # Render the message first: scrubbing a %-format string before formatting could
        # eat a placeholder (e.g. "token=%s") and make logging drop the whole record.
        try:
            rendered = record.getMessage()
        except Exception:  # noqa: BLE001 - let logging's own error handler report a bad format call
            return True
        record.msg = redact_text(rendered)
        record.args = ()
        for key, value in list(record.__dict__.items()):
            if key not in self._STANDARD_ATTRS and isinstance(value, (str, dict, list, tuple)):
                record.__dict__[key] = redact_value(value)
        if record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True
