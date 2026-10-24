"""Authenticated owner controls, separate from model-facing capabilities."""
from hanni.dashboard.features import RequestLedger, request_id
from hanni.native.tool_access import ToolAccess


class ToolAccessControls:
    def __init__(self, features, chat):
        self.features, self.chat = features, chat
        self.settings = ToolAccess(features.root) if features.root else None
        self.ledger = RequestLedger()

    def snapshot(self):
        available = self.settings is not None and self.chat.native_mode
        return {'available': available,
                **(self.settings.snapshot() if self.settings else {}),
                'reason': None if available else 'Tool access controls require the native HANNI agent.'}

    def execute(self, body):
        if not self.snapshot()['available']:
            raise RuntimeError('Tool access controls require the native HANNI agent.')
        if (set(body) != {'id', 'mode', 'expected_revision'}):
            raise ValueError('Expected a request ID, access mode and current settings revision.')
        key = request_id(body['id'])
        def save():
            registry = self.features.registry
            profile = registry.context.permissions.owner
            if profile.chat_only or profile.max_auto_approve_level < 0:
                raise RuntimeError('The owner profile does not allow tool access changes.')
            from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
            definition = ToolDefinition('workspace.tool_access', 'Owner changed agent tool access.',
                2, 2, {'mode': str}, {}, lambda *_: None, side_effect='reversible_write')
            result = self.settings.save(body['mode'], body['expected_revision'])
            registry.context.audit.write(definition,
                ToolRequest(definition.name, {'mode': body['mode']}, confirmed=True,
                            source='desktop-settings', correlation_id=key), {'mode': body['mode']},
                result=ToolResult(definition.name, True, 'Agent tool access saved.'))
            return {**result, 'available': True, 'reason': None}
        return self.ledger.execute(key, body, save)
