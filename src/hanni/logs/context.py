"""Correlation IDs carried through async tasks and threads via contextvars."""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_correlation_id: ContextVar[str | None] = ContextVar("hanni_correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


def get_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def correlation(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation ID for the duration of the block (new one if not given)."""
    cid = correlation_id or new_correlation_id()
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)


class ContextFilter(logging.Filter):
    """Attach ``correlation_id`` and ``node_id`` to every record."""

    def __init__(self, node_id: str) -> None:
        super().__init__()
        self.node_id = node_id

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "correlation_id", None):
            record.correlation_id = get_correlation_id() or "-"
        record.node_id = self.node_id
        return True
