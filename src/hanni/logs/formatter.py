"""JSON-lines and text formatters. Both redact their final output."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from hanni.logs.redaction import RedactionFilter, redact_text, redact_value


class JsonFormatter(logging.Formatter):
    """One JSON object per line with stable field names."""

    def __init__(self, *, node_id: str) -> None:
        super().__init__()
        self.node_id = node_id

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "node": getattr(record, "node_id", self.node_id),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in RedactionFilter._STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info
        # Object representations become strings only during JSON encoding. Scrub
        # that conversion too, before quoting/escaping can conceal a known value.
        return json.dumps(redact_value(payload), ensure_ascii=False,
                          default=lambda value: redact_text(str(value)))


class TextFormatter(logging.Formatter):
    """Human-readable console format."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-8s %(name)s [%(correlation_id)s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return redact_text(super().format(record))
