"""Independent real-service fixture adapter; no replacement workflow executor.

Do not run until the Service implementation is coherently frozen. Only the model
reply interface, resource probe, clocks and original-handler observers are seams.
Original configuration loading, host routing/argument preparation, registry
permissions, private SQLite and actual local handlers remain production code.
"""
from collections import deque
from copy import deepcopy
import json
from pathlib import Path
import threading
from uuid import uuid4

from hanni.config.loader import load_config
from hanni.core.interaction import InteractionState
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry

from .fixtures import HandlerLedger


class EmptyProviderVault:
    """No credential-manager access in an isolated engineering fixture."""

    def get(self, _account):
        return None

    def labels(self):
        return ()

    def preferences(self):
        return {}

    def set(self, *_):
        raise AssertionError('A fixture cannot write provider credentials.')

    def delete(self, *_):
        raise AssertionError('A fixture cannot delete provider credentials.')


class QueuedStructuredClient:
    """Scripted engineering responses through the attached original client API."""

    def __init__(self, *responses):
        self._responses = deque(responses)
        self._lock = threading.Lock()
        self.calls = []

    def enqueue(self, *responses):
        with self._lock:
            self._responses.extend(responses)

    def chat(self, messages, **kwargs):
        with self._lock:
            self.calls.append({'response_format': deepcopy(kwargs.get('response_format')),
                               'temperature': kwargs.get('temperature')})
            if not self._responses:
                raise AssertionError('The real service requested an unscripted model response.')
            response = self._responses.popleft()
        if callable(response):
            response = response(deepcopy(messages), deepcopy(kwargs))
        return json.dumps(response, ensure_ascii=False, allow_nan=False)


class ServiceFixture:
    """Use a new isolated data root; never production settings or private stores."""

    def __init__(self, root, *, client=None, limits=None, clock=None, monotonic=None,
                 observer=None, resource_probe=None, extra_allowed_actions=()):
        from hanni.workflows import WorkflowService
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        config_dir = Path(__file__).resolve().parents[2] / 'config'
        self.config = load_config(config_dir, data_dir=self.root / 'state', env={})
        self.registry = build_default_registry(self.config)
        # The original adapters keep their original permission/scope behavior,
        # but there is genuinely no connected provider in this fixture.
        self.registry.google_access._vault = EmptyProviderVault()
        configured = self.config.hanni.mcp
        self.extra_allowed_actions = tuple(extra_allowed_actions)
        self.host = McpHost(self.registry, read_only=configured.read_only,
                           max_tools=configured.max_tools_per_turn,
                           allowed_actions=tuple(dict.fromkeys(
                               (*configured.allowed_actions, *self.extra_allowed_actions))))
        self.client = client or QueuedStructuredClient()
        self.interaction = InteractionState()
        self.ledger = HandlerLedger(self.root / 'handler-ledger.jsonl')
        self.notifications = []
        self.resources = {'allowed': True, 'ram_percent': 20.0,
                          'cpu_percent': 5.0, 'gpu': None}
        options = {'protected_roots': (config_dir,)}
        if limits is not None:
            options['limits'] = limits
        if clock is not None:
            options['clock'] = clock
        if monotonic is not None:
            options['monotonic'] = monotonic
        if observer is not None:
            options['observer'] = observer
        self.service = WorkflowService(self.config.paths.data_dir, **options)
        self.service.attach(self.registry, self.client, host=self.host,
                            interaction=self.interaction,
                            resource_probe=resource_probe or (lambda: deepcopy(self.resources)),
                            notification_sink=lambda event: self.notifications.append(deepcopy(event)))

    def start(self):
        self.service.start()
        return self

    def observe(self, *capabilities, before=None, after=None):
        for capability in capabilities:
            self.ledger.observe(self.registry, capability, before=before, after=after)

    def mutate(self, operation, data, *, request_id=None, actor_profile='owner', scope=None):
        body = {'id': request_id or str(uuid4()), 'operation': operation, 'data': deepcopy(data)}
        return self.service.mutate(body, actor_profile=actor_profile, scope=scope)

    def submit(self, goal, mode='assisted', *, request_id=None, scope=None):
        return self.mutate('goal.submit', {'goal': goal, 'mode': mode},
                           request_id=request_id, scope=scope)['workflow_id']

    def detail(self, key):
        return self.service.detail(key)

    def await_state(self, key, *states, timeout=10):
        result = self.service.wait(key, timeout=timeout,
                                   predicate=lambda detail: detail['status'] in states)
        assert result['status'] in states, f'Expected {states}; observed {result["status"]}'
        return result

    @staticmethod
    def bound_data(detail, approval=None):
        data = {'workflow_id': detail['workflow_id'], 'expected_revision': detail['revision']}
        if approval is not None:
            data.update({field: approval.get(field) for field in
                         ('approval_id', 'step_id', 'plan_hash', 'argument_hash', 'definition_hash')})
        return data

    def control(self, key, operation, *, approval=None, **extra):
        detail = self.detail(key)
        if operation in {'approve_plan', 'start'}:
            data = self.bound_data(detail)
            data['plan_hash'] = (approval or detail)['plan_hash']
        elif operation == 'revoke':
            if approval is None:
                raise AssertionError('Revocation requires an explicitly selected grant.')
            data = {**self.bound_data(detail), 'approval_id': approval['approval_id']}
        else:
            data = self.bound_data(detail, approval)
        data.update(extra)
        return self.mutate(operation, data)

    def close(self):
        try:
            self.service.close()
        finally:
            try:
                self.interaction.close()
            finally:
                if self.registry.context.reliability is not None:
                    self.registry.context.reliability.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
