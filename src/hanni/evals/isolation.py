"""Evaluation registries contain schemas and metadata, never executable handlers."""
from dataclasses import replace

from hanni.mcp.host import McpHost
from hanni.tools.base import ToolRegistry


def deny_execution(*args, **kwargs):
    raise AssertionError('Capability execution is forbidden in evaluation')


class MetadataRegistry(ToolRegistry):
    execute = deny_execution
    _execute = deny_execution

    def register(self, definition):
        super().register(replace(definition, handler=deny_execution,
                                 requires_confirmation_if=deny_execution if definition.requires_confirmation_if else None))


def isolated_host(host: McpHost, *, allowed_actions=None) -> McpHost:
    registry = MetadataRegistry(host.registry.context)
    # Routing evals assume a synthetic authorized connection. Never consult the
    # operator's credential vault to decide whether a schema is reachable.
    class FixtureGoogleAccess:
        def resolve_account(self, requested=None, service=None): return requested or 'personal'
        def has_capability(self, account, capability): return True
    registry.google_access = FixtureGoogleAccess()
    for definition in host.registry.definitions():
        registry.register(definition)
    return McpHost(registry, read_only=host.read_only, max_tools=host.max_tools,
                   allowed_actions=tuple(host.allowed_actions if allowed_actions is None else allowed_actions),
                   timezone_name=host.timezone_name)
