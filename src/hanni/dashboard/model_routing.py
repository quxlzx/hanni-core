"""Private routing visibility and audited, fixed policy controls.

The desktop can change selection preferences. It cannot supply capability
evidence, authorize data sharing, start a model, or invoke an inference request.
"""
from copy import deepcopy
from threading import RLock
from uuid import UUID

from hanni.core.shutdown import FileStopStateStore
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult


def routing_snapshot(server, *, refresh=False):
    engine = getattr(server, 'model_routing', None)
    if engine is None:
        reason = 'Model routing requires a configured local HANNI session.'
        return {'available': False, 'enabled': False, 'reason': reason,
                'sampled_at': 0, 'policy': 'balanced', 'manual_endpoint_id': None,
                'controller_attached': False, 'endpoints': [], 'decisions': [],
                'controls': {'configure': {'enabled': False, 'reason': reason},
                             'refresh': {'enabled': False, 'reason': reason},
                             'supported_policies': []}}
    shutting_down = server.shutdown_event is not None and server.shutdown_event.is_set()
    if not shutting_down:
        engine.start_monitor()
        if refresh:
            engine.request_refresh()
    result = deepcopy(engine.snapshot())
    reason = ('This dashboard is shutting down.' if shutting_down else
              'Routing policy changes are blocked while HANNI is in Safe Mode.'
              if FileStopStateStore.for_data_dir(engine.data_dir).load() is not None else None)
    if reason:
        result['controls']['configure'] = {'enabled': False, 'reason': reason}
    if shutting_down:
        result['controls']['refresh'] = {'enabled': False, 'reason': reason}
    return result


class ModelRoutingControls:
    def __init__(self, features, engine, shutdown_event=None):
        self.features = features
        self.engine = engine
        self.shutdown_event = shutdown_event
        self.lock = RLock()
        self.receipts = {}

    def execute(self, body):
        if (not isinstance(body, dict)
                or set(body) != {'id', 'policy', 'manual_endpoint_id', 'confirmed'}
                or type(body['confirmed']) is not bool
                or not isinstance(body['policy'], str)
                or body['policy'] not in {'balanced', 'fast', 'quality', 'manual', 'resident_first', 'measured_work'}
                or (body['manual_endpoint_id'] is not None
                    and not isinstance(body['manual_endpoint_id'], str))):
            raise ValueError('Choose a supported model policy and a registered manual endpoint.')
        try:
            key = str(UUID(body['id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Routing policy changes require a UUID request ID.') from None
        with self.lock:
            if self.engine is None:
                raise RuntimeError('Model routing is unavailable in this session.')
            if self.engine.closed:
                raise RuntimeError('Model routing is closed.')
            if self.shutdown_event is not None and self.shutdown_event.is_set():
                raise RuntimeError('This dashboard is shutting down.')
            if body['policy'] != 'manual' and body['manual_endpoint_id'] is not None:
                raise ValueError('A manual endpoint requires the manual policy.')
            if body['policy'] == 'manual' and body['manual_endpoint_id'] not in {
                    row['endpoint_id'] for row in self.engine.snapshot()['endpoints']}:
                raise ValueError('Manual overrides require a registered endpoint.')
            previous = self.receipts.get(key)
            if previous is not None:
                if previous['body'] != body:
                    raise ValueError('This request ID belongs to another policy change.')
                return deepcopy(previous['result'])
            if len(self.receipts) >= 128:
                raise RuntimeError('Routing control session limit reached. Refresh before more changes.')
            registry = self.features.registry
            name = 'model_routing.desktop_configure'
            if name not in {definition.name for definition in registry.definitions()}:
                def configure(arguments, _context, _request):
                    request = arguments['payload']
                    result = self.engine.configure(policy=request['policy'],
                        manual_endpoint_id=request['manual_endpoint_id'])
                    return ToolResult(name, True, 'Model selection policy saved.', {'result': result})
                registry.register(ToolDefinition(name, 'Change a local model selection preference.',
                    2, 2, {'payload': dict}, {'result': 'object'}, configure,
                    side_effect='reversible_write', background_allowed=False))
            result = registry.execute(ToolRequest(name, {'payload': body},
                confirmed=body['confirmed'], source='desktop-model-routing', correlation_id=key))
            if not result.ok:
                raise RuntimeError(result.message)
            receipt = {'body': deepcopy(body), 'result': deepcopy(result.data['result'])}
            self.receipts[key] = receipt
            return deepcopy(receipt['result'])
