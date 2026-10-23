"""Strict, bounded workflow data. Model data never supplies execution authority."""
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from hanni.logs.redaction import redact_value


class WorkflowError(ValueError):
    """A safe, user-facing workflow admission or persistence failure."""


class StaleWorkflow(WorkflowError):
    pass


class LeaseLost(WorkflowError):
    pass


MODES = frozenset({'assisted', 'supervised', 'background'})
STATUSES = frozenset({
    'submitted', 'planning', 'awaiting_plan_approval', 'ready', 'running',
    'awaiting_step_approval', 'verifying', 'retrying', 'recovering', 'paused',
    'blocked', 'completed', 'partially_completed', 'failed', 'cancelled',
})
TERMINAL = frozenset({'completed', 'partially_completed', 'failed', 'cancelled'})
TRANSITIONS = {
    'submitted': {'planning', 'awaiting_plan_approval', 'paused', 'blocked', 'cancelled'},
    'planning': {'awaiting_plan_approval', 'blocked', 'failed', 'paused', 'cancelled'},
    'awaiting_plan_approval': {'ready', 'planning', 'blocked', 'paused', 'cancelled'},
    'ready': {'running', 'awaiting_step_approval', 'paused', 'blocked', 'cancelled'},
    'running': {'verifying', 'retrying', 'recovering', 'awaiting_step_approval',
                'paused', 'blocked', 'completed', 'partially_completed', 'failed', 'cancelled'},
    'awaiting_step_approval': {'ready', 'running', 'blocked', 'paused', 'failed', 'cancelled'},
    'verifying': {'running', 'retrying', 'completed', 'partially_completed', 'blocked', 'failed', 'paused', 'cancelled'},
    'retrying': {'running', 'blocked', 'failed', 'paused', 'cancelled'},
    'recovering': {'paused', 'blocked', 'failed', 'cancelled'},
    'paused': {'ready', 'running', 'planning', 'awaiting_plan_approval', 'blocked', 'cancelled'},
    'blocked': {'ready', 'planning', 'awaiting_plan_approval', 'paused', 'failed', 'cancelled'},
}
STEP_STATUSES = frozenset({
    'pending', 'ready', 'awaiting_approval', 'running', 'verified', 'unverified',
    'failed', 'blocked', 'cancelled',
})
OPERATIONS = frozenset({
    'goal.submit', 'start', 'pause', 'resume', 'cancel', 'approve_plan',
    'approve_step', 'reject', 'revoke', 'retry_safe',
})


@dataclass(frozen=True)
class WorkflowLimits:
    max_steps: int = 16
    max_parallel_reads: int = 2
    max_active_workflows: int = 2
    max_retries: int = 1
    step_timeout_seconds: int = 30
    max_duration_seconds: int = 600
    planning_timeout_seconds: int = 120
    max_plan_attempts: int = 2
    approval_ttl_seconds: int = 300
    max_goal_chars: int = 4000
    max_payload_bytes: int = 65536
    max_result_bytes: int = 65536
    max_artifact_bytes: int = 5242880
    max_invocations: int = 32
    max_workflows: int = 500
    retention_days: int = 30
    lease_seconds: int = 10

    def __post_init__(self):
        caps = {
            'max_steps': 64, 'max_parallel_reads': 4, 'max_active_workflows': 4,
            'max_retries': 1, 'step_timeout_seconds': 300,
            'max_duration_seconds': 3600, 'planning_timeout_seconds': 300,
            'max_plan_attempts': 2, 'approval_ttl_seconds': 3600,
            'max_goal_chars': 16000, 'max_payload_bytes': 262144,
            'max_result_bytes': 262144, 'max_artifact_bytes': 20971520,
            'max_invocations': 128, 'max_workflows': 2000,
            'retention_days': 365, 'lease_seconds': 60,
        }
        for field in fields(self):
            value = getattr(self, field.name)
            minimum = 0 if field.name == 'max_retries' else 1
            if type(value) is not int or not minimum <= value <= caps[field.name]:
                raise WorkflowError(f'Invalid workflow limit: {field.name}.')

    @classmethod
    def from_config(cls, config):
        if config is None:
            return cls()
        if isinstance(config, cls):
            return config
        return cls(**{field.name: getattr(config, field.name) for field in fields(cls)})

    def to_dict(self):
        return asdict(self)


def canonical_json(value: Any, *, maximum=65536, private=True) -> str:
    """Reject secrets rather than persisting a silently altered resumption payload."""
    validate_json_bounds(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False,
                             sort_keys=True, separators=(',', ':'))
    except (TypeError, ValueError, RecursionError) as exc:
        raise WorkflowError('Workflow data must be finite JSON.') from exc
    try:
        length = len(encoded.encode('utf-8'))
    except UnicodeEncodeError as exc:
        raise WorkflowError('Workflow data must contain valid Unicode.') from exc
    if length > maximum:
        raise WorkflowError('Workflow data exceeds its size limit.')
    if private and (credential_fields(value) or redact_value(value) != value):
        raise WorkflowError('Credential-bearing data cannot be retained by workflows.')
    return encoded


def validate_json_bounds(value, *, max_depth=32, max_nodes=10000):
    """Iterative admission runs before the recursive JSON/privacy libraries."""
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > max_depth or count > max_nodes:
            raise WorkflowError('Workflow JSON exceeds its depth or element limit.')
        if isinstance(item, dict):
            if len(item) > max_nodes - count:
                raise WorkflowError('Workflow JSON exceeds its element limit.')
            if any(not isinstance(key, str) for key in item):
                raise WorkflowError('Workflow JSON object keys must be strings.')
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, (list, tuple)):
            if len(item) > max_nodes - count:
                raise WorkflowError('Workflow JSON exceeds its element limit.')
            pending.extend((child, depth + 1) for child in item)
        elif not isinstance(item, (str, int, float, bool, type(None))):
            raise WorkflowError('Workflow data must be finite JSON.')


_CREDENTIAL_KEY = re.compile(
    r'password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|'
    r'authorization|client[_-]?secret|private[_-]?key|credential|bearer|^secret$|^token$', re.I)


def credential_fields(value) -> bool:
    """Key-based rejection covers opaque and short credentials as well as patterns."""
    if isinstance(value, dict):
        return any((_CREDENTIAL_KEY.search(str(key)) and item not in (None, '', {}, []))
                   or credential_fields(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(credential_fields(item) for item in value)
    return False


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value, maximum=1048576, private=False).encode()).hexdigest()


def request_uuid(value) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise WorkflowError('A workflow operation requires a UUID request ID.') from exc


def identifier(value, *, workflow=False) -> str:
    pattern = r'wf_[0-9a-f]{32}' if workflow else r'[A-Za-z0-9_-]{1,64}'
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise WorkflowError('Invalid workflow identifier.')
    return value


def wall_time(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise WorkflowError('Workflow clock is unavailable.')
    value = float(value)
    if not math.isfinite(value) or not 0 < value < 253402300800:
        raise WorkflowError('Workflow clock is unavailable.')
    return value


def iso_time(value) -> str:
    return datetime.fromtimestamp(wall_time(value), timezone.utc).isoformat().replace('+00:00', 'Z')


def resource_identity(path) -> str:
    """Resolve junctions/symlinks and Windows case aliases before admission."""
    try:
        return os.path.normcase(str(Path(path).expanduser().resolve()))
    except (TypeError, ValueError, OSError, RuntimeError) as exc:
        raise WorkflowError('Workflow resource path cannot be safely resolved.') from exc


def within_root(path, root) -> bool:
    target, parent = resource_identity(path), resource_identity(root)
    try:
        return os.path.commonpath([target, parent]) == parent
    except ValueError:
        return False
