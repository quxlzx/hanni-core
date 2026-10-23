"""Validated local tool execution primitives for H.A.N.N.I. Milestone 6."""

from __future__ import annotations

import json
import time
import threading
import math
from copy import deepcopy
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Literal

SideEffect = Literal["read", "reversible_write", "external_action", "destructive"]

from hanni.config.schema import PermissionsConfig
from hanni.core.events import Event, EventType
from hanni.core.shutdown import EmergencyStop, EmergencyStopActive

# All registries on this PC process share one mutation lane, including memory
# tools and notifications. Read-only observations may proceed concurrently.
_MUTATION_LOCK = threading.RLock()
_BACKGROUND_CALL = ContextVar('hanni_background_capability', default=False)


class ToolError(RuntimeError):
    """Base class for tool-layer failures."""


class UnknownToolError(ToolError):
    pass


class ToolValidationError(ToolError):
    pass


class ToolPermissionError(ToolError):
    pass


class ConfirmationRequired(ToolPermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ToolRequest:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    actor_profile: str = "owner"
    confirmed: bool = False
    source: str = "local"
    correlation_id: str | None = None
    expected_definition_hash: str | None = None
    # Trusted, transient workflow binding. Never a model-facing or persisted
    # payload: the registry must capture this exact approved definition object.
    expected_definition: ToolDefinition | None = field(default=None, repr=False, compare=False)
    execution_guard: Callable[[], None] | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    ok: bool
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Mapping[str, Any] | None = None
    verification: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "ok": self.ok,
            "message": self.message,
            "data": dict(self.data),
            "duration_ms": self.duration_ms,
        }
        if not self.ok:
            payload['error'] = dict(self.error or {
                'code': 'CAPABILITY_FAILED', 'message': self.message, 'retryable': False})
        if self.verification is not None:
            payload['verification'] = dict(self.verification)
        return payload


@dataclass(slots=True)
class ToolContext:
    permissions: PermissionsConfig
    emergency_stop: EmergencyStop
    audit: Any
    timezone_name: str | None = None
    reliability: Any = None


ToolHandler = Callable[[Mapping[str, Any], ToolContext, ToolRequest], ToolResult]
DynamicConfirmation = Callable[[Mapping[str, Any]], str | None]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    permission_level: int
    risk_level: int
    input_schema: Mapping[str, type | tuple[type, ...]]
    output_schema: Mapping[str, str]
    handler: ToolHandler
    timeout_seconds: int = 30
    retry_attempts: int = 1
    audit: bool = True
    requires_confirmation_if: DynamicConfirmation | None = None

    # Planner metadata is advisory; authorization continues to use the fields above.
    side_effect: SideEffect | None = None
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    execution_class: Literal['atomic', 'compound', 'workflow'] = 'atomic'
    background_allowed: bool = True
    schema_version: int = 1
    display_name: str = ''
    categories: tuple[str, ...] = ()
    argument_constraints: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    # External MCP adapters retain their original schema; built-ins keep the
    # existing Python-type contract and validation unchanged.
    json_input_schema: Mapping[str, Any] | None = None
    json_output_schema: Mapping[str, Any] | None = None
    external_definition_hash: str = ''
    retry_safe: bool = False
    # Assigned by the registry for runtime-bound implementations. A closure or
    # bound instance cannot preserve old workflow authority after replacement.
    workflow_binding_id: str = field(default='', repr=False, compare=False)

    def argument_schema(self) -> dict[str, Any]:
        """JSON schema derived from the same types/constraints used to validate."""
        if self.json_input_schema is not None:
            return deepcopy(dict(self.json_input_schema))
        names = {str: 'string', int: 'integer', float: 'number', bool: 'boolean',
                 dict: 'object', list: 'array', tuple: 'array', type(None): 'null'}
        properties, required = {}, []
        for key, kinds in self.input_schema.items():
            kinds = kinds if isinstance(kinds, tuple) else (kinds,)
            rule = dict(self.argument_constraints.get(key, {}))
            if rule.pop('required', False): required.append(key)
            types = list(dict.fromkeys(names[kind] for kind in kinds))
            if rule.pop('nullable', True) and 'null' not in types: types.append('null')
            properties[key] = {'type': types[0] if len(types) == 1 else types, **deepcopy(rule)}
        return {'type': 'object', 'properties': properties, 'required': required,
                'additionalProperties': False}

    def validate_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, Mapping):
            raise ToolValidationError("tool arguments must be a JSON object")
        if self.json_input_schema is not None:
            from hanni.mcp.adapter import validate_json_arguments
            return validate_json_arguments(self.json_input_schema, arguments)
        unknown = sorted(set(arguments) - set(self.input_schema))
        if unknown:
            raise ToolValidationError(f"unknown argument(s) for {self.name}: {', '.join(unknown)}")
        result = dict(arguments)
        for key, rule in self.argument_constraints.items():
            if key not in result:
                if 'default' in rule: result[key] = deepcopy(rule['default'])
                elif rule.get('required'): raise ToolValidationError(f'{self.name}.{key} is required')
        for key, expected in self.input_schema.items():
            if key not in result:
                continue
            value = result[key]
            rule = self.argument_constraints.get(key, {})
            if value is None:
                if not rule.get('nullable', True):
                    raise ToolValidationError(f'{self.name}.{key} cannot be null')
                continue
            kinds = expected if isinstance(expected, tuple) else (expected,)
            if isinstance(value, bool) and bool not in kinds:
                raise ToolValidationError(f"{self.name}.{key} must be {getattr(expected, '__name__', expected)!s}")
            if not isinstance(value, expected):
                label = "/".join(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__
                raise ToolValidationError(f"{self.name}.{key} must be {label}; got {type(value).__name__}")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(value): raise ToolValidationError(f'{self.name}.{key} must be finite')
                if 'minimum' in rule and value < rule['minimum'] or 'maximum' in rule and value > rule['maximum']:
                    raise ToolValidationError(f'{self.name}.{key} is outside the allowed range')
            if 'enum' in rule and value not in rule['enum']:
                raise ToolValidationError(f'{self.name}.{key} is not an allowed value')
            if isinstance(value, str):
                if len(value) < rule.get('minLength', 0) or len(value) > rule.get('maxLength', float('inf')):
                    raise ToolValidationError(f'{self.name}.{key} has an invalid length')
        return result


class ToolRegistry:
    """Register and execute tools behind permission, stop, validation and audit gates."""

    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self._tools: dict[str, ToolDefinition] = {}
        self._registry_lock = threading.RLock()
        self.revision = 0
        self._capability_api = None

    @property
    def capabilities(self):
        if self._capability_api is None:
            from hanni.tools.capability_api import CapabilityAPI
            self._capability_api = CapabilityAPI(self)
        return self._capability_api

    def register(self, definition: ToolDefinition) -> None:
        with self._registry_lock:
            self._register(definition)

    def _register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        if definition.execution_class not in {'atomic', 'compound', 'workflow'}:
            raise ValueError('invalid capability execution_class')
        if type(definition.background_allowed) is not bool or type(definition.schema_version) is not int or definition.schema_version < 1:
            raise ValueError('invalid capability metadata')
        if type(definition.retry_safe) is not bool:
            raise ValueError('retry_safe must be a boolean')
        if set(definition.argument_constraints) - set(definition.input_schema):
            raise ValueError('argument constraints must name registered arguments')
        # Snapshot mutable schema containers so the cached contract cannot drift.
        from dataclasses import replace
        from uuid import uuid4
        stateful_binding = any(
            function is not None and (
                getattr(function, '__closure__', None)
                or getattr(function, '__defaults__', None)
                or getattr(function, '__kwdefaults__', None)
                or getattr(function, '__self__', None) is not None
                or getattr(function, '__code__', None) is None)
            for function in (definition.handler, definition.requires_confirmation_if)
        )
        definition = replace(definition, input_schema=dict(definition.input_schema),
                             output_schema=dict(definition.output_schema),
                             argument_constraints=deepcopy(dict(definition.argument_constraints)),
                             json_input_schema=deepcopy(definition.json_input_schema),
                             json_output_schema=deepcopy(definition.json_output_schema),
                             workflow_binding_id=uuid4().hex if stateful_binding else '')
        self._tools[definition.name] = definition
        self.revision += 1

    def definitions(self) -> tuple[ToolDefinition, ...]:
        with self._registry_lock:
            return tuple(self._tools[name] for name in sorted(self._tools))

    def unregister(self, name: str, *, expected: ToolDefinition) -> bool:
        """Remove an exact owned definition, preserving unrelated registrations."""
        with self._registry_lock:
            if self._tools.get(name) is not expected:
                return False
            del self._tools[name]
            self.revision += 1
            return True

    def get(self, name: str) -> ToolDefinition:
        with self._registry_lock:
            try:
                return self._tools[name]
            except KeyError as exc:
                raise UnknownToolError(f"unknown tool: {name}") from exc

    def execute(self, request: ToolRequest) -> ToolResult:
        from hanni.reliability.context import _task, _step, _checking, current_correlation_id
        service = self.context.reliability or (_task.get().service if _task.get() else None)
        if service is None or _checking.get():
            return self._execute_locked(request)
        with service.task(source=request.source) as trace:
            from dataclasses import replace
            request = replace(request, correlation_id=request.correlation_id or current_correlation_id())
            step = trace.begin(request.name)
            token = _step.set(step)
            try:
                result = self._execute_locked(request)
                from hanni.reliability.verification import evidence
                trace.complete(step, result, result.verification or evidence())
                return result
            except Exception as exc:
                trace.failed(step, exc)
                raise
            finally:
                _step.reset(token)

    def _execute_locked(self, request: ToolRequest) -> ToolResult:
        definition = self.get(request.name)
        if definition.name != 'notify.toast' and (definition.permission_level > 0 or definition.side_effect not in {None, 'read'}):
            with _MUTATION_LOCK:
                return self._execute(request)
        return self._execute(request)

    def _execute(self, request: ToolRequest) -> ToolResult:
        definition = self.get(request.name)
        if definition.external_definition_hash and request.correlation_id is None:
            from dataclasses import replace
            from uuid import uuid4
            request = replace(request, correlation_id=uuid4().hex)
        args = definition.validate_arguments(request.arguments)
        started = time.perf_counter()
        requested_event = Event(
            EventType.TOOL_REQUESTED,
            source="tools.registry",
            payload={"tool": definition.name, "permission_level": definition.permission_level, "source": request.source},
        )
        _ = requested_event
        try:
            # These gates are intentionally inside the audited region so denied
            # or Safe-Mode-blocked tool attempts are visible without executing
            # the underlying action.
            if request.expected_definition is not None and definition is not request.expected_definition:
                raise ToolPermissionError('Tool definition changed before workflow dispatch; review the current plan.')
            if request.expected_definition_hash is not None:
                from hanni.workflows.policy import definition_fingerprint
                if (not isinstance(request.expected_definition_hash, str)
                        or definition_fingerprint(definition) != request.expected_definition_hash):
                    raise ToolPermissionError('Tool definition changed before workflow dispatch; review the current plan.')
            self.context.emergency_stop.guard(f"tool {definition.name}")
            self._authorize(definition, request, args)
            if _BACKGROUND_CALL.get() and not definition.background_allowed:
                raise ToolPermissionError(f'{definition.name} is foreground-only')
            if definition.execution_class == 'workflow' and not _BACKGROUND_CALL.get():
                raise ToolPermissionError(f'{definition.name} requires background workflow admission')
            if request.execution_guard is not None:
                if not callable(request.execution_guard):
                    raise ToolPermissionError('Workflow dispatch guard is invalid.')
                request.execution_guard()
                # The trusted guard may observe a cancellation or permission /
                # definition change. Do not dispatch on authority captured
                # before that final boundary.
                if self.get(request.name) is not definition:
                    raise ToolPermissionError('Tool definition changed before dispatch; review the current request.')
                self.context.emergency_stop.guard(f"tool {definition.name}")
                self._authorize(definition, request, args)
            from hanni.reliability.context import _task, _step, _checking
            trace, step = _task.get(), _step.get()
            if trace and not _checking.get():
                trace.authorized(step, request.confirmed)
            from hanni.core.responsiveness import phase
            with phase('tool_execution'):
                result = definition.handler(args, self.context, request)
            elapsed = (time.perf_counter() - started) * 1000
            if not isinstance(result, ToolResult):
                raise ToolError(f"tool {definition.name} returned invalid result type")
            verification = result.verification
            if trace and not _checking.get() and result.ok:
                trace.emit('TOOL_COMPLETED', step)
                trace.emit('VERIFYING', step)
                checking_token = _checking.set(True)
                try:
                    from hanni.reliability.verification import verify_action, evidence
                    with phase('registry_verification'):
                        verification = verify_action(self, definition, request, args, result)
                except Exception:
                    verification = evidence(scope='verification_unavailable')
                finally:
                    _checking.reset(checking_token)
            result = ToolResult(result.name, result.ok, result.message, result.data, elapsed, result.error, verification)
            if definition.audit:
                self.context.audit.write(definition, request, args, result=result)
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            if definition.audit:
                self.context.audit.write(definition, request, args, error=exc, duration_ms=elapsed)
            raise

    def _authorize(self, definition: ToolDefinition, request: ToolRequest, args: Mapping[str, Any]) -> None:
        if type(request.confirmed) is not bool:
            raise ToolPermissionError('Execution confirmation must be an explicit boolean.')
        try:
            profile = self.context.permissions.profiles[request.actor_profile]
        except KeyError as exc:
            raise ToolPermissionError(f"unknown permission profile: {request.actor_profile}") from exc
        if profile.chat_only or profile.max_auto_approve_level < 0:
            raise ToolPermissionError(f"profile {profile.name} has no tool access")
        dynamic_reason = definition.requires_confirmation_if(args) if definition.requires_confirmation_if else None
        requires_confirmation = (
            definition.permission_level > profile.max_auto_approve_level
            or definition.risk_level >= 3
            or dynamic_reason is not None
        )
        if requires_confirmation and not request.confirmed:
            reason = dynamic_reason or f"permission level {definition.permission_level} requires explicit confirmation"
            raise ConfirmationRequired(f"{definition.name}: {reason}")
