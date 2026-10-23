"""Owned SDK transport harness; original HANNI authority, no owner-store access."""
from __future__ import annotations
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
import uuid
import psutil
from hanni.config.loader import load_config
from hanni.mcp.manager import MCPManager
from hanni.tools.base import ToolRequest
from hanni.tools.registry import build_default_registry
from tests.helpers import write_config_dir
from scripts.campaign2.mcp_contracts import CLASSIFICATIONS, VALID, definitions
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'scripts/campaign2/mcp_fixture.py'

def eventually(predicate, *, seconds=6):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    raise AssertionError('Owned fixture condition did not become true within the bound.')

class EmptyVault:
    """Keep discovery away from the owner's OS credential store."""

    def labels(self):
        return ()

    def get(self, name):
        return None

    def prefs(self, name):
        return {}

class OwnedHub:

    def __init__(self, path, transport='stdio', *, approved=True, name='Quartz Bench'):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.transport, self.http_process, self.http_child_proof = (transport, None, None)
        self.control_path, self.ledger_path = (self.path / 'control.json', self.path / 'ledger.jsonl')
        self.control = {}
        self.change()
        config = load_config(write_config_dir(self.path / 'config'), data_dir=self.path / 'data', env={})
        self.registry = build_default_registry(config)
        self.registry.google_access._vault = EmptyVault()
        self.base_count = len(self.registry.definitions())
        self.manager = MCPManager(self.path / 'hub', self.registry, env={}, vault=EmptyVault())
        self.config = {'name': name, 'transport': transport, 'timeout_seconds': 3}
        arguments = [str(FIXTURE), '--control', str(self.control_path), '--ledger', str(self.ledger_path)]
        if transport == 'stdio':
            self.config.update(command=sys.executable, args=arguments)
        else:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            self.http_process = subprocess.Popen([sys.executable, *arguments, '--transport', 'http', '--port', str(port)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            url = f'http://127.0.0.1:{port}'
            self.config.update(url=url + '/mcp/', allow_local_http=True)
            opener = build_opener(ProxyHandler({}))

            def healthy():
                if self.http_process.poll() is not None:
                    raise AssertionError('Owned SDK HTTP child exited before initialization.')
                try:
                    with opener.open(url + '/health', timeout=0.3) as response:
                        return json.load(response) == {'owned_fixture': True}
                except OSError:
                    return False
            try:
                eventually(healthy, seconds=8)
                actual_pid = int(self.ledger_path.with_suffix('.pid').read_text(encoding='utf8'))
                actual = psutil.Process(actual_pid)
                assert actual_pid == self.http_process.pid or self.http_process.pid in {row.pid for row in actual.parents()}
                assert str(FIXTURE) in actual.cmdline()
                self.http_child_proof = (actual_pid, actual.create_time())
            except BaseException:
                self.close()
                raise
        self.saved = self.manager.add(self.config)
        self.server_id = self.saved['id']
        self.initialization = None
        if approved:
            self.connect()
            self.approve()

    def change(self, *, replace=False, notify=False, **fields):
        self.control = {} if replace else deepcopy(self.control)
        self.control.update(fields)
        if notify:
            self.control['revision'] = self.control.get('revision', 0) + 1
        temporary = self.control_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.control), encoding='utf8')
        os.replace(temporary, self.control_path)

    def events(self):
        return [json.loads(line) for line in self.ledger_path.read_text(encoding='utf8').splitlines()] if self.ledger_path.exists() else []

    def calls(self):
        return [row for row in self.events() if row['event'] == 'call']

    def snapshot(self):
        return next((row for row in self.manager.snapshot()['servers'] if row['id'] == self.server_id))

    def connect(self):
        self.manager.connect(self.server_id, approved=True, expected_config_hash=self.saved['config_hash'])
        server = self.snapshot()
        assert server['state'] == 'connected', server['error']
        self.initialization = self.manager.connections[self.server_id].ready.result()
        return server

    def approve(self, names=None, *, classification=None):
        rows = self.snapshot()['tools']
        wanted = set(names) if names is not None else {row['original_name'] for row in rows}
        self.manager.approve_tools(self.server_id, [{'original_name': row['original_name'], 'definition_hash': row['definition_hash'], 'classification': classification or CLASSIFICATIONS[row['original_name']]} for row in rows if row['original_name'] in wanted])

    def tool(self, name):
        return next((row for row in self.snapshot()['tools'] if row['original_name'] == name))

    def request(self, name, args=None, **fields):
        from hanni.workflows.policy import definition_fingerprint
        row = self.tool(name)
        return ToolRequest(row['internal_id'], deepcopy(VALID[name] if args is None else args), expected_definition_hash=definition_fingerprint(self.registry.get(row['internal_id'])), correlation_id='campaign2-' + uuid.uuid4().hex, **fields)

    def call(self, name, args=None, *, confirmed=True, **fields):
        if name == 'prism.erase_record':
            self.registry.execute(self.request('prism.create_record', confirmed=True))
        return self.registry.execute(self.request(name, args, confirmed=confirmed, **fields))

    def capture(self, label):
        destination = os.environ.get('CAMPAIGN2_MCP_ARTIFACT_ROOT')
        if not destination:
            return
        artifact = {'label': label, 'transport': self.transport, 'scope': 'actual_local_sdk_controlled_data', 'initialization': self.initialization, 'base_count': self.base_count, 'snapshot': self.manager.snapshot(), 'events': self.events(), 'registry_imports': [row.name for row in self.registry.definitions() if row.external_definition_hash]}
        folder = Path(destination) / 'transport_receipts'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (label + '-' + self.transport + '-' + uuid.uuid4().hex[:8] + '.json')).write_text(json.dumps(artifact, indent=2), encoding='utf8')

    def close(self):
        manager = getattr(self, 'manager', None)
        if manager is not None:
            manager.close()
        if self.http_child_proof is not None:
            pid, created = self.http_child_proof
            try:
                child = psutil.Process(pid)
                if child.create_time() == created and str(FIXTURE) in child.cmdline():
                    child.terminate()
                    child.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
        if self.http_process is not None and self.http_process.poll() is None:
            self.http_process.terminate()
            self.http_process.wait(timeout=5)
        registry = getattr(self, 'registry', None)
        if registry is not None and registry.context.reliability is not None:
            registry.context.reliability.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

def assert_schema_preserved(hub):
    raw = {row['name']: row for row in definitions()}
    for row in hub.snapshot()['tools']:
        source = raw[row['original_name']]
        assert row['input_schema'] == source['inputSchema']
        assert row['output_schema'] == source['outputSchema']
        definition = hub.registry.get(row['internal_id'])
        assert definition.argument_schema() == source['inputSchema']
        assert definition.json_output_schema == source['outputSchema']
        assert row['metadata']['_meta'] == source['_meta']
