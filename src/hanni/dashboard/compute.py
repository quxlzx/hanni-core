"""Fixed desktop compute controls through the original audited permissions."""
from threading import RLock
from uuid import UUID

from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult


class ComputeControls:
    def __init__(self, features, scheduler, shutdown_event=None):
        self.features = features
        self.scheduler = scheduler
        self.shutdown_event = shutdown_event
        self.lock = RLock()
        self.receipts = {}

    def execute(self, body):
        if (not isinstance(body, dict) or set(body) != {'id', 'worker_id', 'operation', 'data', 'confirmed'}
                or not isinstance(body['data'], dict) or type(body['confirmed']) is not bool):
            raise ValueError('Choose a registered worker, request ID and fixed compute operation.')
        try:
            key = str(UUID(body['id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Compute controls require a UUID request ID.') from None
        worker = self.scheduler.registry.worker(body['worker_id'])
        operation, payload = body['operation'], body['data']
        if operation not in {'configure', 'start'} or operation == 'start' and payload or operation == 'configure' and (
                not payload or set(payload) - {'enabled', 'concurrency'}):
            raise ValueError('Only registered worker controls are supported.')
        with self.lock:
            if self.shutdown_event is not None and self.shutdown_event.is_set():
                raise RuntimeError('This dashboard is shutting down.')
            previous = self.receipts.get(key)
            if previous:
                if previous['body'] != body:
                    raise ValueError('This compute request ID belongs to another operation.')
                return previous['result']
            if len(self.receipts) >= 128:
                raise RuntimeError('Compute control session limit reached. Refresh status before more actions.')
            registry = self.features.registry
            name = 'compute.desktop_' + operation
            if name not in {definition.name for definition in registry.definitions()}:
                def handler(arguments, _context, _request):
                    request = arguments['payload']
                    current = self.scheduler.registry.worker(request['worker_id'])
                    result = (self.scheduler.transport.start(current) if request['operation'] == 'start'
                              else self.scheduler.registry.configure_worker(current['worker_id'], **request['data']))
                    return ToolResult(name, True, 'Registered compute control completed.', {'result': result})
                registry.register(ToolDefinition(name, 'Explicit local desktop compute control.',
                    3 if operation == 'start' else 2, 3 if operation == 'start' else 2,
                    {'payload': dict}, {'result': 'object'}, handler,
                    side_effect='reversible_write', background_allowed=False))
            # Original registry enforces the active profile, stop state, audit
            # and confirmation. Neither the frontend nor remote workers grant authority.
            result = registry.execute(ToolRequest(name, {'payload': body}, confirmed=body['confirmed'],
                source='desktop-compute', correlation_id=key))
            if not result.ok:
                raise RuntimeError(result.message)
            self.receipts[key] = {'body': dict(body), 'result': result.data['result']}
            return result.data['result']
