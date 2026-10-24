"""Startup reconnects reuse exact consent and perform discovery only."""
import json
from unittest.mock import Mock
import pytest
from hanni.mcp.autoconnect import AutoConnections
from hanni.mcp.manager import MCPManager
from hanni.mcp.security import MCPConfigurationError

class Connection:

    def __init__(self, *a, **kw):
        self.closed = False
        self.calls = []

    def wait_ready(self):
        pass

    def close(self):
        self.closed = True

    def request(self, operation, *a):
        self.calls.append(operation)
        assert operation == 'list', 'Startup must never invoke a tool.'
        return [{'name': 'inspect', 'description': 'Read status', 'inputSchema': {'type': 'object', 'properties': {}}}]

@pytest.fixture
def approved(tmp_path):
    factory = Mock(side_effect=Connection)
    manager = MCPManager(tmp_path, connection_factory=factory)
    server = manager.add({'name': 'Owner server', 'transport': 'streamable_http', 'url': 'http://127.0.0.1:8090/mcp', 'allow_local_http': True})
    manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
    manager.disconnect(server['id'])
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps({'version': 1, 'servers': [{'id': server['id'], 'config_hash': server['config_hash']}]}))
    auto = AutoConnections(manager, path, lambda: None)
    yield (manager, auto, server, factory)
    auto.close()
    manager.close()

def test_startup_discovers_without_granting_tool_approval(approved):
    manager, auto, server, factory = approved
    auto.tick()
    s = manager.snapshot()['servers'][0]
    assert s['state'] == 'connected'
    assert s['enabled_count'] == 0
    assert s['tools'][0]['approval'] is None
    assert factory.return_value is not None
    assert manager.connections[server['id']].calls == ['list']
    count = factory.call_count
    auto.tick()
    assert factory.call_count == count


def test_pin_persists_ui_selected_startup_consent_and_disconnect_pauses_it(tmp_path):
    manager = Mock()
    manager.snapshot.return_value = {'servers': []}
    path = tmp_path / 'mcp' / 'auto-connect.json'
    auto = AutoConnections(manager, path, lambda: None)
    try:
        auto.pin('a' * 32, 'b' * 64)
        assert auto.policy() == [{'id': 'a' * 32, 'config_hash': 'b' * 64}]
        assert auto.thread.is_alive()
        auto.pause('a' * 32)
        assert auto.policy() == []
        manager.reconnect_approved.assert_not_called()
    finally:
        auto.close()

def test_live_connection_loss_reconnects_only_same_approved_config(approved):
    manager, auto, server, factory = approved
    auto.tick()
    manager.connections[server['id']].closed = True
    auto.tick()
    assert manager.snapshot()['servers'][0]['state'] == 'connected'
    assert factory.call_count == 3
    assert manager.snapshot()['servers'][0]['enabled_count'] == 0

def test_revoked_approval_blocks_before_transport_start(approved):
    manager, auto, server, factory = approved
    manager.servers[server['id']]['connection_approval_hash'] = None
    count = factory.call_count
    auto.tick()
    assert factory.call_count == count
    assert 'revoked' in auto.snapshot()['connections'][server['id']]

def test_disabled_or_changed_config_is_never_reenabled(approved):
    manager, auto, server, factory = approved
    manager.disable_server(server['id'])
    count = factory.call_count
    auto.tick()
    assert factory.call_count == count
    assert not manager.servers[server['id']]['enabled']
    config = dict(server['config'])
    config['url'] = 'http://127.0.0.1:8091/mcp'
    manager.update(server['id'], config, expected_config_hash=server['config_hash'])
    auto.tick()
    assert factory.call_count == count

def test_owner_disconnect_pauses_policy_persistently(approved):
    manager, auto, server, factory = approved
    auto.pause(server['id'])
    manager.disconnect(server['id'])
    auto.tick()
    assert auto.policy() == []
    assert factory.call_count == 1

def test_stop_guard_and_retry_bound(tmp_path):
    item = {'id': 'a' * 32, 'config_hash': 'b' * 64}
    p = tmp_path / 'policy.json'
    p.write_text(json.dumps({'version': 1, 'servers': [item]}))
    manager = Mock()
    manager.snapshot.return_value = {'servers': [{**item, 'enabled': True, 'state': 'failed'}]}
    manager.reconnect_approved.side_effect = RuntimeError('Unavailable')
    auto = AutoConnections(manager, p, lambda: None)
    for _ in range(12):
        auto.tick()
        auto.retries[item['id'], item['config_hash']] = (auto.retries[item['id'], item['config_hash']][0], 0)
    assert manager.reconnect_approved.call_count == 8
    assert auto.snapshot()['connections'][item['id']] == 'retry limit reached'
    auto.guard = Mock(side_effect=RuntimeError('Emergency stop'))
    auto.tick()
    assert manager.reconnect_approved.call_count == 8

def test_revocation_during_connect_closes_new_connection(approved):
    manager, auto, server, factory = approved
    guard = Mock(side_effect=[None, RuntimeError('Permission revoked')])
    with pytest.raises(RuntimeError, match='revoked'):
        manager.reconnect_approved(server['id'], server['config_hash'], guard=guard)
    assert server['id'] not in manager.connections
    assert manager.snapshot()['servers'][0]['state'] == 'disconnected'

def test_process_restart_reuses_saved_consent_without_tool_execution(approved):
    manager, auto, server, factory = approved
    root = auto.path.parent
    manager.close()
    restarted = MCPManager(root, connection_factory=factory)
    reconnect = AutoConnections(restarted, auto.path, lambda: None)
    try:
        reconnect.tick()
        state = restarted.snapshot()['servers'][0]
        assert state['state'] == 'connected'
        assert state['enabled_count'] == 0
        assert restarted.connections[server['id']].calls == ['list']
    finally:
        reconnect.close()
        restarted.close()

def test_failed_connect_result_is_not_reported_as_connected(approved):
    manager, auto, server, factory = approved

    class Unavailable(Connection):

        def wait_ready(self):
            raise OSError('unavailable')
    factory.side_effect = Unavailable
    auto.tick()
    assert 'unavailable' in auto.snapshot()['connections'][server['id']]
    assert manager.snapshot()['servers'][0]['state'] == 'failed'
