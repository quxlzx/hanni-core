"""Run original launcher with an explicitly empty external account vault.

The production Google vault is global Windows Credential Manager, not scoped by
HANNI_DATA_DIR. Native cycle one exposed that discovery boundary. This isolated
test entrypoint binds the documented GoogleAccess dependency seam before imports
of controller/desktop features; no original tool handler/controller is replaced.
"""
from __future__ import annotations

import atexit
from dataclasses import asdict
import json
import os
from pathlib import Path
import threading
import time
from unittest.mock import patch

from hanni.tools.google_access import GoogleAccess
from hanni.models.client import LlamaCppClient

_evidence_lock = threading.Lock()


class ActualRecordingClient(LlamaCppClient):
    """Observe original local-client inputs/outputs; do not alter any response."""
    def _save(self, record):
        directory = os.environ.get('HANNI_V36_EVIDENCE_DIR')
        if not directory:
            return
        path = Path(directory)/'actual-controller-model.jsonl'
        with _evidence_lock, path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=True, default=str)+'\n')

    def complete_with_tools(self, messages, **kwargs):
        record = {'kind':'tools', 'model':asdict(self.spec),
                  'messages':json.loads(json.dumps(messages)), 'kwargs':kwargs}
        started=time.perf_counter()
        try:
            result=super().complete_with_tools(messages, **kwargs)
            record['actual_output']=asdict(result)
            return result
        except Exception as error:
            record['error']={'class':type(error).__name__, 'message':str(error)}
            raise
        finally:
            record['latency_ms']=(time.perf_counter()-started)*1000
            self._save(record)

    def stream_chat(self, messages, **kwargs):
        record = {'kind':'stream_chat', 'model':asdict(self.spec),
                  'messages':json.loads(json.dumps(messages)), 'kwargs':kwargs}
        started, parts=time.perf_counter(), []
        try:
            for chunk in super().stream_chat(messages, **kwargs):
                parts.append(chunk)
                yield chunk
            record['actual_output']=''.join(parts)
        except Exception as error:
            record['partial_output']=''.join(parts)
            record['error']={'class':type(error).__name__, 'message':str(error)}
            raise
        finally:
            record['latency_ms']=(time.perf_counter()-started)*1000
            self._save(record)


class EmptyVault:
    def get(self, account):
        return None

    def labels(self):
        return ('personal', 'school')

    def preferences(self):
        return {}


class IsolatedGoogleAccess(GoogleAccess):
    def __init__(self, vault=None, transport=None, timezone_name=None):
        super().__init__(EmptyVault() if vault is None else vault, transport, timezone_name)


def main():
    with patch('hanni.tools.google_access.GoogleAccess', IsolatedGoogleAccess), patch('hanni.models.registry.LlamaCppClient', ActualRecordingClient):
        from hanni.dashboard.launcher import main as original_main
        from hanni.dashboard.server import DashboardServer
        from hanni.tools.capabilities import describe
        original_init = DashboardServer.__init__
        stopped = threading.Event()
        holders = []

        def export():
            for server in tuple(holders):
                config = getattr(server.telemetry, 'config', None)
                if config is None:
                    continue
                registry = getattr(server.mcp, 'controller_registry', None)
                desktop = getattr(server.features, '_registry', None)
                payload = {'version': 1,
                    'controller_registry': [] if registry is None else [describe(d).to_dict() for d in registry.definitions()],
                    'desktop_registry': [] if desktop is None else [describe(d).to_dict() for d in desktop.definitions()],
                    'disclosure': 'Read-only actual in-process registry descriptors only; no account identities, tokens, private stores or tool execution.'}
                path = Path(config.paths.data_dir).parent/'session-inventory.json'
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding='utf-8')
                temporary.replace(path)

        def init(server, *args, **kwargs):
            original_init(server, *args, **kwargs)
            holders.append(server)

        def periodically():
            while not stopped.wait(1):
                try:
                    export()
                except (OSError, RuntimeError, AttributeError):
                    pass

        watcher = threading.Thread(target=periodically, daemon=True, name='v36-registry-evidence')
        watcher.start()
        try:
            with patch.object(DashboardServer, '__init__', init):
                return original_main()
        finally:
            stopped.set()
            watcher.join(timeout=2)
            export()


if __name__ == '__main__':
    raise SystemExit(main())
