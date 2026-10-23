"""Structured logging with secret redaction and correlation IDs.

* JSON lines to ``<data_dir>/logs/hanni.jsonl`` (git-ignored), text or JSON on the console.
* Every rendered record passes through :mod:`hanni.logs.redaction`, so a loaded
  secret or a token-shaped string never reaches a sink.
* Later milestones must never log raw audio, transcript windows, or screen frames;
  logs are not allowed to recreate the two-minute ephemeral buffers.

This package depends on nothing else in ``hanni`` so it can be imported first.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from hanni.logs.context import ContextFilter, correlation, get_correlation_id, new_correlation_id
from hanni.logs.formatter import JsonFormatter, TextFormatter
from hanni.logs.redaction import RedactionFilter, redact_text, register_secret

__all__ = [
    "ContextFilter",
    "JsonFormatter",
    "RedactionFilter",
    "TextFormatter",
    "correlation",
    "get_correlation_id",
    "get_logger",
    "new_correlation_id",
    "redact_text",
    "register_secret",
    "setup_logging",
]

_HANNI_HANDLER_ATTR = "_hanni_managed"


def setup_logging(
    *,
    node_id: str,
    level: str = "INFO",
    console_format: str = "text",
    log_dir: Path | None = None,
    file_format: str = "json",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    stream=None,
) -> None:
    """Configure the root logger. Idempotent: previously installed H.A.N.N.I. handlers are replaced."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        if getattr(handler, _HANNI_HANDLER_ATTR, False):
            root.removeHandler(handler)
            handler.close()

    context_filter = ContextFilter(node_id=node_id)
    redaction_filter = RedactionFilter()

    console = logging.StreamHandler(stream or sys.stderr)
    console.setFormatter(_formatter(console_format, node_id))
    _install(root, console, context_filter, redaction_filter)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / f"hanni.{'jsonl' if file_format == 'json' else 'log'}",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(_formatter(file_format, node_id))
        _install(root, file_handler, context_filter, redaction_filter)

    logging.captureWarnings(True)


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``hanni`` namespace."""
    return logging.getLogger(name if name.startswith("hanni") else f"hanni.{name}")


def _formatter(fmt: str, node_id: str) -> logging.Formatter:
    return JsonFormatter(node_id=node_id) if fmt == "json" else TextFormatter()


def _install(root: logging.Logger, handler: logging.Handler, *filters: logging.Filter) -> None:
    for f in filters:
        handler.addFilter(f)
    setattr(handler, _HANNI_HANDLER_ATTR, True)
    root.addHandler(handler)
