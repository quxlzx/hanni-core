"""Authenticated read-only projection of the original executor's task traces."""
from __future__ import annotations


def execution_snapshot(server, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Choose an execution history limit from 1 to 100.')
    features = server.features
    if features.root is None:
        return {'available': False, 'tasks': [],
                'reason': 'Execution traces are unavailable in this session.'}
    # Use the actual controller registry when attached, as the MCP Hub does.
    # Dashboard-only sessions use their existing fixed desktop registry.
    registry = server.mcp.controller_registry
    if registry is None:
        registry = features.registry
    service = getattr(registry.context, 'reliability', None)
    if service is None:
        return {'available': False, 'tasks': [],
                'reason': 'Execution tracing is unavailable in this controller.'}
    return service.snapshot(limit=limit)
