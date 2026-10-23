"""Process-local seam between the dashboard and HANNI's original controller.

No client creation, connection, model routing or execution happens here. A
dashboard-owned hub is bound only to registries from the same data directory.
"""
from __future__ import annotations

from pathlib import Path
import threading

_lock = threading.RLock()
_hub = None


def install(hub) -> None:
    global _hub
    with _lock:
        _hub = hub


def uninstall(hub) -> None:
    global _hub
    with _lock:
        if _hub is hub:
            _hub = None


def attach_controller(config, registry, *, client=None, host=None) -> None:
    with _lock:
        hub = _hub
        if hub is not None and hub.root == Path(config.paths.data_dir).resolve():
            from hanni.hermes.client import current
            hermes = current(config.paths.data_dir)
            connection_only = bool(hermes and hermes.config.get('connection_only', False) and not hermes.config.get('direct_mcp', False))
            hub.attach_controller(registry, model_tools_enabled=config.hanni.mcp.enabled and not connection_only,
                                  external_tools_enabled=not connection_only,
                                  observe_first=config.hanni.mcp.read_only)
            workflows = getattr(hub, 'workflows', None)
            if workflows is not None and client is not None and host is not None:
                workflows.attach_controller(registry, client, host)


def detach_controller(registry) -> None:
    """Stop workflow admissions before their original controller is closed."""
    with _lock:
        hub = _hub
        workflows = getattr(hub, 'workflows', None)
        if workflows is not None:
            workflows.detach_controller(registry)


def workflow_hub(config):
    """Return only this backend's attached workflow facade, without starting it."""
    with _lock:
        hub = _hub
        if hub is not None and hub.root == Path(config.paths.data_dir).resolve():
            return getattr(hub, 'workflows', None)
        return None
