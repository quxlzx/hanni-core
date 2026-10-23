"""Controller-owned advisory lifecycle; no model, SSH or secret discovery.

The ordinary factory keeps the independent model gate closed. A trusted core
can install a separately verified client; HTTP requests cannot change this gate.
"""
from __future__ import annotations

import atexit
import threading
from pathlib import Path

from hanni.laya.advisory import AdvisoryClient, from_config

_lock = threading.RLock()
_clients: dict[str, tuple[object, AdvisoryClient]] = {}


def _identity(config):
    data_root = Path(config.paths.data_dir).resolve()
    return str(data_root).casefold(), config.hanni.laya


def advisory_for_config(config, *, admission_guard=None):
    """Return the actual requested client, with production gates closed by default."""
    root, requested = _identity(config)
    with _lock:
        current = _clients.get(root)
        if current is not None and current[0] != requested:
            current[1].close()
            del _clients[root]
            current = None
        if current is None:
            client = from_config(config, quality_gate_passed=False, admission_guard=admission_guard)
            _clients[root] = (requested, client)
            return client
        client = current[1]
        if admission_guard is not None:
            # A second session cannot relax a previously installed controller's
            # admission guard for this same authoritative data root.
            previous = client.admission_guard
            if previous is None:
                client.admission_guard = admission_guard
            elif previous is not admission_guard:
                client.admission_guard = lambda: bool(previous()) and bool(admission_guard())
        return client


def current_advisory(config):
    """Read-only status access. It never constructs a client or starts inference."""
    root, requested = _identity(config)
    with _lock:
        current = _clients.get(root)
        return current[1] if current is not None and current[0] == requested else None


def install_advisory(config, client):
    """Trusted core binding for a separately verified client, unavailable over HTTP."""
    root, requested = _identity(config)
    if not isinstance(client, AdvisoryClient) or not requested.advisory_enabled or not client.enabled or not client._quality_gate_passed:
        raise ValueError('A separately verified, explicitly enabled advisory client is required')
    if client.url != requested.url or client.transport != requested.transport:
        raise ValueError('Installed advisory identity does not match requested configuration')
    with _lock:
        existing = _clients.pop(root, None)
        if existing is not None and existing[1] is not client:
            existing[1].close()
        _clients[root] = (requested, client)


def stop_advisory(config=None):
    with _lock:
        if config is None:
            clients = [client for _, client in _clients.values()]
            _clients.clear()
        else:
            current = _clients.pop(_identity(config)[0], None)
            clients = [current[1]] if current is not None else []
    for client in clients:
        client.close()


atexit.register(stop_advisory)
