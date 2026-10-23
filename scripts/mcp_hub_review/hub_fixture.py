"""Actual isolated Hub/store/registry/session; only model/sample content is synthetic.

No private Hub CRUD is mocked. SDK fixture processes/endpoints are added only by
explicit verification operations after approval. This never reads user secrets.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/desktop_review'))
from fixture import ReviewFixture
from phase_fixture import DisconnectedReviewVault

from hanni.core.orchestrator import TextSession
from hanni.cli import _wrap_mcp_session

# Loading the probe by file keeps this standalone harness independent of
# whether callers add the scripts directory as a package or an import path.
import importlib.util
_probe_spec = importlib.util.spec_from_file_location('independent_mcp_session_probe',
                                                  Path(__file__).with_name('session_probe.py'))
_probe = importlib.util.module_from_spec(_probe_spec)
sys.modules[_probe_spec.name] = _probe
_probe_spec.loader.exec_module(_probe)


class HubReviewFixture(ReviewFixture):
    def __enter__(self):
        super().__enter__()
        try:
            self.sample['activity'] = {'input_level': 0, 'speaking': False,
                                       'microphone_active': False}
            self.sample['interaction'].update(response_in_progress=False,
                                             tts_speaking=False, voice_engaged=False)
            self.registry = self.server.features.registry
            self.registry.google_access._vault = DisconnectedReviewVault()
            # Original CLI binding installs imported adapters in the same
            # registry used by the original bounded session. No model runtime.
            self.model_probe = _probe.ProbeClient('', {})
            self.controller = _wrap_mcp_session(self.config, TextSession(self.model_probe),
                client=self.model_probe, registry=self.registry)
            self.management_requests = []
            self.disclosure = ('Actual isolated DashboardServer/MCPHub/MCPManager/registry '
                'and original CLI-bound MCP session. Deterministic model client; '
                'synthetic telemetry/device/model samples. Voice inactive/unbound, '
                'Google vault explicitly empty. No private Hub CRUD mocked. '
                'Only explicitly approved local SDK mock servers may launch; '
                'no live model, microphone, provider, SSH or remote machine actions.')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def request(self, route='/api/mcp', *, data=None, token=True, origin=True):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Hanni-Token'] = self.hub.token
        if origin:
            headers['Origin'] = self.url.rstrip('/')
        request = urllib.request.Request(self.url.rstrip('/') + route,
            data=json.dumps(data).encode() if data is not None else None,
            method='POST' if data is not None else 'GET', headers=headers)
        with urllib.request.urlopen(request, timeout=130) as response:
            return json.load(response)

    def operation(self, operation, data, *, request_id=None, confirmed=True):
        body = {'id': request_id or str(uuid4()), 'operation': operation,
                'data': data, 'confirmed': confirmed}
        result = self.request(data=body)
        self.management_requests.append({'id': body['id'], 'operation': operation})
        return result

    def __exit__(self, *exc):
        hub = getattr(getattr(self, 'server', None), 'mcp', None)
        if hub is not None:
            hub.close()
        return super().__exit__(*exc)
