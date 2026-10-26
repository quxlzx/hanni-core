"""Shared validation and error receipts for every native execution path."""
from __future__ import annotations

from jsonschema import Draft202012Validator, ValidationError
from contextvars import ContextVar
from contextlib import contextmanager

_cancel_scope = ContextVar('native_execution_cancelled', default=lambda: False)


def scope_cancelled():
    return _cancel_scope.get()()


@contextmanager
def cancellation_scope(check):
    token = _cancel_scope.set(check)
    try:
        yield
    finally:
        _cancel_scope.reset(token)


def error_receipt(exc: Exception, *, dispatched=False) -> dict:
    from hanni.logs.redaction import redact_text
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    code = ('authentication_expired' if status in (401, 403) else
            'invalid_arguments' if isinstance(exc, (ValidationError, ValueError, TypeError)) else
            'timeout' if isinstance(exc, TimeoutError) or 'timeout' in type(exc).__name__.lower() else
            'connection_failed' if isinstance(exc, ConnectionError) else 'tool_failed')
    return {'ok': False, 'error': redact_text(str(exc))[:500] or type(exc).__name__,
            'error_code': code, 'retryable': not dispatched and code in {'timeout', 'connection_failed'},
            'effects': 'unknown' if dispatched else 'none', 'exception_type': type(exc).__name__}


class ToolRuntime:
    """Model calls and scripts share schemas and the durable dispatch boundary."""
    def __init__(self, specs, dispatch, *, cancelled=lambda: False):
        self.specs = {spec['name']: spec for spec in specs}
        if len(self.specs) != len(specs):
            raise ValueError('Duplicate capability names.')
        self.dispatch = dispatch
        self.cancelled = cancelled

    def call(self, name, arguments, call_id):
        if self.cancelled() or scope_cancelled():
            raise InterruptedError('Task cancelled.')
        spec = self.specs.get(name)
        if spec is None:
            return {'ok': False, 'error': 'Capability outside task scope.',
                    'error_code': 'unavailable', 'retryable': False, 'effects': 'none'}
        try:
            Draft202012Validator(spec['schema']['function']['parameters']).validate(arguments)
        except (ValidationError, ValueError, TypeError) as exc:
            return error_receipt(exc)
        try:
            result = self.dispatch(name, arguments, call_id)
            if not isinstance(result, dict):
                raise TypeError('Tool handler did not return an object receipt.')
            if result.get('ok') is False:
                result = dict(result)
                detail = result.get('error')
                detail = detail if isinstance(detail, dict) else {}
                result.setdefault('error_code', str(detail.get('code') or 'tool_failed').lower())
                data = result.get('data')
                data = data if isinstance(data, dict) else {}
                read_only = (spec.get('remote') or {}).get('classification') == 'read_only' or name in {
                    'skill_read', 'skill_search', 'memory_search', 'history_search', 'session_search', 'skill_propose', 'local_read_file',
                    'local_list_dir', 'local_search_files', 'web_fetch', 'web_search', 'system_info'}
                result.setdefault('effects', 'none' if read_only or data.get('created') is False else 'unknown')
                result.setdefault('retryable', bool(detail.get('retryable')) and result['effects'] == 'none')
            return result
        except InterruptedError:
            raise
        except Exception as exc:
            return error_receipt(exc, dispatched=True)
