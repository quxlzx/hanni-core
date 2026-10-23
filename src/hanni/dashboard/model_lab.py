"""Fixed Model Lab controls through the existing desktop ToolRegistry."""
from hanni.dashboard.features import RequestLedger
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult


class ModelLabControls:
    def __init__(self, features, lab):
        self.features, self.lab = features, lab
        self.ledger = RequestLedger()

    def execute(self, body):
        if (not isinstance(body, dict) or set(body) != {'id', 'action', 'data', 'confirmed'}
                or not isinstance(body['action'], str) or body['action'] not in {'start', 'pause', 'cancel', 'resume'}
                or type(body['confirmed']) is not bool or not isinstance(body['data'], dict)):
            raise ValueError('Choose a fixed benchmark control and supported settings.')
        def action():
            self.lab._check()
            registry = self.features.registry
            name = 'model_lab.desktop_control'
            if name not in {d.name for d in registry.definitions()}:
                def control(arguments, _context, _request):
                    request = arguments['payload']
                    result = (self.lab.start(request['data']) if request['action'] == 'start'
                              else self.lab.control(request['action'], request['data']))
                    return ToolResult(name, True, 'Benchmark control accepted.', {'result': result})
                registry.register(ToolDefinition(name, 'Control a fixed local evaluation adapter.',
                    2, 2, {'payload': dict}, {'result': 'object'}, control,
                    side_effect='reversible_write', background_allowed=False))
            result = registry.execute(ToolRequest(name, {'payload': body}, confirmed=body['confirmed'],
                source='desktop-model-lab', correlation_id=body['id']))
            if not result.ok:
                raise RuntimeError(result.message)
            return result.data['result']
        return self.ledger.execute(body['id'], body, action)
