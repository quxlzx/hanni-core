"""Validated capability facade shared by HANNI and its MCP server.

Discovery never executes. Model-facing payloads contain only semantic IDs,
schemas and evidence; execution always returns through ToolRegistry authority.
"""
from __future__ import annotations

from copy import deepcopy
import logging
import time
from collections.abc import Mapping

from hanni.core.shutdown import EmergencyStopActive
from hanni.tools.base import (ToolRequest, ToolResult, ToolError, ToolValidationError,
                              ToolPermissionError, ConfirmationRequired, UnknownToolError)
from hanni.tools.base import _BACKGROUND_CALL
from hanni.tools.capabilities import LocalCapabilityDiscovery, describe

log = logging.getLogger('hanni.capability')
HOT_IDS = ('process.top_cpu', 'system.stats', 'time.now', 'audio.set_volume', 'app.open')


def error_contract(exc):
    code = ('CONFIRMATION_REQUIRED' if isinstance(exc, ConfirmationRequired) else
            'SAFE_MODE' if isinstance(exc, EmergencyStopActive) else
            'UNKNOWN_CAPABILITY' if isinstance(exc, UnknownToolError) else
            'INVALID_ARGUMENTS' if isinstance(exc, (ToolValidationError, ValueError, TypeError)) else
            'PERMISSION_DENIED' if isinstance(exc, (ToolPermissionError, PermissionError)) else
            'NOT_FOUND' if isinstance(exc, (FileNotFoundError, ProcessLookupError)) else
            'TIMEOUT' if isinstance(exc, TimeoutError) else 'CAPABILITY_FAILED')
    return {'code': code, 'message': str(exc), 'retryable': False}


def risk_of(cap):
    if cap.risk_level >= 3 or cap.side_effect == 'destructive': return 'destructive'
    if cap.side_effect == 'external_action': return 'external_side_effect'
    if cap.permission_level > 0 or cap.side_effect != 'read': return 'write'
    return 'read_only'


class CapabilityAPI:
    def __init__(self, registry):
        self.registry = registry
        self.discovery = LocalCapabilityDiscovery(registry)
        self._revision = -1
        self._schemas, self._aliases = {}, {}

    def _refresh(self):
        if self._revision == self.registry.revision: return
        self._schemas, self._aliases = {}, {}
        for definition in self.registry.definitions():
            # Exact aliases only. Broad retrieval synonyms are never executable aliases.
            for alias in (*definition.aliases, definition.display_name):
                if alias:
                    key = alias.casefold().strip(' .?!')
                    self._aliases.setdefault(key, set()).add(definition.name)
        self._revision = self.registry.revision

    def resolve_id(self, value):
        if not isinstance(value, str): return None
        try:
            return self.registry.get(value).name
        except UnknownToolError:
            self._refresh()
            matches = self._aliases.get(value.casefold().strip(' .?!'), ())
            return next(iter(matches)) if len(matches) == 1 else None

    def get(self, capability_id):
        """Return a defensive copy of one complete model-facing contract."""
        self._refresh()
        definition = self.registry.get(capability_id)
        if capability_id not in self._schemas:
            cap = describe(definition)
            self._schemas[capability_id] = {
                'id': cap.name, 'name': cap.display_name, 'description': cap.description,
                'aliases': list(definition.aliases), 'categories': list(cap.categories),
                'family': cap.family, 'subfamily': cap.subfamily, 'state': cap.state,
                'source': cap.source, 'requires': list(cap.requires),
                'permission': cap.permission, 'read_write_class': cap.read_write_class,
                'priority': cap.priority, 'introduced_version': cap.introduced_version,
                'metadata_risk': cap.risk,
                'execution_class': cap.execution_class, 'risk': risk_of(cap),
                'confirmation': cap.risk_level >= 3 or bool(definition.requires_confirmation_if),
                'confirmation_policy': cap.confirmation_policy,
                'permission_level': cap.permission_level,
                'arguments': cap.argument_schema.get('properties', {}), 'input_schema': cap.argument_schema,
                'returns': deepcopy(definition.json_output_schema) if definition.json_output_schema is not None else {'type': 'object', 'properties': {
                    key: {'type': value} if value in {'object','array','string','integer','number','boolean','null'}
                    else {'description': value} for key, value in cap.output_contract.items()}},
                'timeout_seconds': cap.timeout_seconds, 'background_allowed': cap.background_allowed,
                'schema_version': cap.schema_version,
            }
            if definition.external_definition_hash:
                self._schemas[capability_id]['definition_hash'] = definition.external_definition_hash
        return deepcopy(self._schemas[capability_id])

    def search(self, query, *, limit=5):
        if not isinstance(query, str) or not query.strip() or len(query) > 8000:
            raise ToolValidationError('capability.search query must contain 1..8000 characters')
        if type(limit) is not int or not 1 <= limit <= 5:
            raise ToolValidationError('capability.search limit must be 1..5')
        matches = self.discovery.search(query, limit=limit)
        results = [{'id': m.capability.name, 'description': m.capability.description,
                    'risk': risk_of(m.capability), 'execution_class': m.capability.execution_class,
                    'score': round(m.score / (m.score + 10), 4)} for m in matches]
        # Log IDs/scores, never private owner queries or retrieved contents.
        log.info('[CapabilitySearch] %s', [(r['id'], r['score']) for r in results])
        return results

    def hot_catalog(self):
        return [self.model_schema(name) for name in HOT_IDS if self.resolve_id(name)]

    def model_schema(self, capability_id):
        schema = self.get(capability_id)
        return {key: schema[key] for key in ('id', 'description', 'input_schema', 'returns',
                'execution_class', 'risk', 'confirmation_policy', 'background_allowed')}

    def call(self, request, *, background=False):
        """Internal call: exceptions preserve exact confirmation/resume semantics."""
        if not isinstance(request, ToolRequest):
            raise ToolValidationError('capability.call requires a validated ToolRequest')
        definition = self.registry.get(request.name)
        cap = describe(definition)
        log.info('[Capability] class=%s risk=%s call %s', cap.execution_class, risk_of(cap), request.name)
        started = time.perf_counter()
        token = _BACKGROUND_CALL.set(background)
        try:
            result = self.registry.execute(request)
        finally:
            _BACKGROUND_CALL.reset(token)
        log.info('[Capability] completed %s ok=%s %.2fms', request.name, result.ok,
                 (time.perf_counter() - started) * 1000)
        return result

    def invoke(self, payload, *, actor_profile='owner', confirmed=False):
        """JSON operation boundary. Authority is supplied by the trusted caller only."""
        name = 'capability.call'
        try:
            if not isinstance(payload, Mapping) or set(payload) != {'id', 'arguments'}:
                raise ToolValidationError('capability.call accepts only id and arguments')
            name = payload['id']
            if not isinstance(name, str): raise ToolValidationError('id must be a string')
            return self.call(ToolRequest(name, payload['arguments'], actor_profile=actor_profile,
                                         confirmed=confirmed, source='capability.call')).to_dict()
        except Exception as exc:
            return ToolResult(str(name), False, str(exc), error=error_contract(exc)).to_dict()
