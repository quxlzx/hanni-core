"""Read-only UI projections of the existing configuration and tool audit.

No execution, credentials, model loading, or independent permission decisions.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from hanni.logs.redaction import redact_value
from hanni.tools.audit import _audit_arguments


def workspace_contract(config):
    base = {
        'version': 1, 'transport': 'http-snapshots',
        'screens': ['home', 'chat', 'voice', 'planner', 'tasks', 'calendar',
                    'projects', 'memory', 'mission', 'models', 'agents', 'cluster',
                    'activity', 'screen', 'notifications', 'settings', 'mcp', 'workflows', 'model-routing'],
        'features': {
            'chat': True, 'history': True, 'telemetry': True,
            'audio_devices': config is not None, 'gpu_routing': config is not None,
            'tool_activity': config is not None,
            'execution_traces': config is not None,
            'mcp_hub': config is not None,
            'workflows': config is not None,
            'model_routing': config is not None,
            'attachments': False, 'agents': config is not None, 'cluster': True,
            'planner': config is not None, 'memory_browser': config is not None,
            'voice_controls': config is not None, 'notifications': config is not None,
            'agent_runtime': False, 'live_approval_queue': False, 'screen_awareness': False,
            'output_audio_levels': False, 'native_launcher': False,
            'inference_speed': False, 'benchmark_browser': False,
        },
        'models': [], 'capabilities': [], 'timezone': None, 'policies': None,
    }
    if config is None:
        return base
    from hanni.tools.registry import build_default_registry
    definitions = build_default_registry(config).definitions()
    model = config.models.supervisor
    base.update(
        timezone=config.hanni.user.timezone,
        models=[{'id': model.id, 'name': model.model_file, 'role': model.role,
                 'context': model.context_length, 'quantization': model.quantization}],
        capabilities=[{'name': item.name, 'permission_level': item.permission_level,
                       'risk_level': item.risk_level} for item in definitions],
        policies={
            'observe_first': config.hanni.mcp.read_only,
            'allowed_actions': list(config.hanni.mcp.allowed_actions),
            'memory_enabled': config.hanni.memory.enabled,
            'memory_retrieval': config.hanni.memory.retrieval_enabled,
            'memory_extraction': config.hanni.memory.extraction_enabled,
            'owner_auto_approve_level': config.permissions.profiles['owner'].max_auto_approve_level,
            'dangerous_actions_require_confirmation': True,
        },
    )
    return base


_SECRET_KEY = re.compile(r'password|passwd|secret|token|credential|authorization|api.?key|private.?key', re.I)
_TOKEN = re.compile(r'\b(?:sk-[\w-]{20,}|ghp_\w{20,}|github_pat_[\w_]{20,}|AIza[\w-]{30,}|AKIA[A-Z0-9]{16})\b')


def safe_value(value, depth=0):
    if depth > 6:
        return '[TRUNCATED]'
    if isinstance(value, dict):
        return {str(k)[:100]: '[REDACTED]' if _SECRET_KEY.search(str(k)) else safe_value(v, depth+1)
                for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [safe_value(v, depth+1) for v in value[:40]]
    if isinstance(value, str):
        return _TOKEN.sub('[REDACTED]', redact_value(value))[:2000]
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return '[UNSUPPORTED]'


def activity_snapshot(data_dir, limit=30):
    if data_dir is None:
        return {'available': False, 'events': [], 'reason': 'Tool audit is unavailable in this session.'}
    root = Path(data_dir).resolve()
    path = root / 'logs' / 'tool_audit.jsonl'
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        return {'available': False, 'events': [], 'reason': 'Tool audit path is unavailable.'}
    if not path.exists():
        return {'available': True, 'events': [], 'reason': 'No tool executions recorded yet.'}
    rows = []
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            offset = max(0, stream.tell() - 262144)
            stream.seek(offset)
            if offset:
                stream.readline()  # Discard an incomplete leading record.
            lines = stream.read(262144).decode('utf-8', errors='replace').splitlines()
        for line in lines:
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict) or not isinstance(raw.get('tool'), str):
                    continue
                arguments = raw.get('arguments', {})
                arguments = _audit_arguments(raw['tool'], arguments) if isinstance(arguments, dict) else {}
                private = raw['tool'].startswith(('google.', 'google_calendar.', 'email.', 'gmail.', 'todo.', 'workspace.', 'memory.desktop_', 'note.')) or raw['tool'] == 'powershell.run'
                row = {
                    'id': len(rows), 'timestamp': raw.get('timestamp'), 'tool': raw['tool'],
                    'status': 'completed' if raw.get('ok') is True else 'failed',
                    'confirmed': raw.get('confirmed') is True,
                    'duration_ms': raw.get('duration_ms'), 'arguments': arguments,
                    'summary': '[PRIVATE RESULT]' if private else raw.get('message'),
                    'error': ('Private tool execution failed.' if private else raw.get('error')) if raw.get('error') else None,
                    'source': raw.get('source'),
                }
                rows.append(safe_value(row))
            except (ValueError, TypeError):
                continue
    except OSError:
        return {'available': False, 'events': [], 'reason': 'Tool audit could not be read.'}
    return {'available': True, 'events': list(reversed(rows[-limit:])), 'reason': None}
