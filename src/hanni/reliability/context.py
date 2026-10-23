"""Metadata-only request scopes; no prompt, model arguments or authority."""
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

_request = ContextVar('hanni_reliability_request', default=None)
_source = ContextVar('hanni_reliability_source', default='local')
_task = ContextVar('hanni_reliability_task', default=None)
_step = ContextVar('hanni_reliability_step', default=None)
_checking = ContextVar('hanni_reliability_checking', default=False)
_attempt = ContextVar('hanni_reliability_attempt', default=None)

@contextmanager
def attempt_scope(group, number):
    """Random retry identity and ordinal; no arguments or authority."""
    token = _attempt.set((group, number))
    try:
        yield
    finally:
        _attempt.reset(token)

def current_request_id():
    return _request.get()

def current_correlation_id():
    task = _task.get()
    return task.record['request_id'] if task else current_request_id()

def safe_source(source):
    for known in ('voice', 'chat', 'browser', 'terminal', 'dashboard', 'mcp', 'tool', 'test', 'local'):
        if isinstance(source, str) and (source == known or source.startswith(known + '.')):
            return known
    return 'local'

@contextmanager
def request_scope(request_id, source='local'):
    identifier = str(UUID(str(request_id)))
    token = _request.set(identifier)
    source_token = _source.set(safe_source(source))
    try:
        yield identifier
    finally:
        _source.reset(source_token)
        _request.reset(token)
