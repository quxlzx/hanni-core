"""Inventory uses real parsing and cached read-only transport; no model inference."""
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from hanni.hermes.inventory import InventoryCache, collect, inspect_sources

def sources(home):
    root = home / '.hermes/hermes-agent'
    (root / 'hermes_cli').mkdir(parents=True)
    (root / 'tools').mkdir()
    (root / 'toolsets.py').write_text("_HERMES_CORE_TOOLS=['read_file']\nTOOLSETS={'file':_ts('File tools',['read_file']), 'hermes-cli':_bundle('CLI')}\nraise RuntimeError('Never import me')\n")
    (root / 'hermes_cli/commands.py').write_text("COMMAND_REGISTRY: list = [CommandDef('status','Inspect session','Session',aliases=('info',),cli_only=True)]\nnoise=CommandDef('fake','Not registered','Other')\n")
    (root / 'tools/file.py').write_text("SCHEMA={'name':'read_file','description':'Read a file','parameters':{'type':'object','properties':{'path':{'type':'string','description':'Owner path','default':'DO_NOT_EXPORT'}},'required':['path']}}\nregistry.register(name='read_file',toolset='file',schema=SCHEMA,handler=dangerous,check_fn=credentials_check)\nregistry.register(name=dynamic_name, toolset='dynamic')\n")
    return root

def test_installed_registry_parsing_does_not_execute_source(tmp_path):
    result = inspect_sources(sources(tmp_path))
    assert [c['name'] for c in result['commands']] == ['status']
    assert result['commands'][0]['cli_only'] is True
    assert result['toolsets'][1]['tools'] == ['read_file']
    assert result['tools'][0]['parameters'][0]['required'] is True
    assert result['tools'][0]['availability'] == 'not_checked'
    assert 'DO_NOT_EXPORT' not in json.dumps(result)
    assert any(('Dynamic registration' in item for item in result['limitations']))

def test_inventory_configuration_filters_credentials_and_stdio_arguments(tmp_path, monkeypatch):
    sources(tmp_path)
    (tmp_path / '.hermes/config.yaml').write_text('model: resident\nplatform_toolsets:\n  cli: [hermes-cli]\nmcp_servers:\n  private:\n    url: https://user:SECRET@private.example:443/mcp?token=SECRET\n    headers: {Authorization: SECRET}\n  github:\n    command: server\n    args: [SECRET]\n    env: {TOKEN: SECRET}\n')
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(stdout='active\n'))
    result = collect(tmp_path)
    assert 'SECRET' not in json.dumps(result)
    assert result['mcp_servers'][0]['endpoint'] == 'https://private.example:443/mcp'
    assert result['mcp_servers'][1]['transport'] == 'stdio'
    assert result['services']['hermes-gateway.service'] == 'active'

def test_snapshot_starts_one_background_refresh_and_never_waits_for_ssh(tmp_path, monkeypatch):
    threads = []
    monkeypatch.setattr('hanni.hermes.inventory.threading.Thread', lambda **k: threads.append(k) or Mock())
    cache = InventoryCache(tmp_path)
    assert cache.snapshot()['loading']
    assert cache.snapshot()['loading']
    assert len(threads) == 1
    cache.close()

def test_unavailable_ssh_preserves_previous_inventory_as_stale(tmp_path, monkeypatch):
    from hanni.dashboard import cluster
    monkeypatch.setattr(cluster, 'load_nodes', lambda root: [])
    cache = InventoryCache(tmp_path)
    cache.value = {'checked_at': 0, 'commands': [{'name': 'status'}]}
    cache.refresh()
    state = cache.snapshot()
    assert state['stale'] and state['error']
    assert state['data']['commands'][0]['name'] == 'status'
    assert not state['loading']
    cache.close()

def test_revoked_node_reference_never_contacts_remote(tmp_path, monkeypatch):
    from hanni.dashboard import cluster
    monkeypatch.setattr(cluster, 'load_nodes', lambda root: [SimpleNamespace(id='karina', maintenance=True)])
    run = Mock()
    monkeypatch.setattr(cluster, '_run', run)
    cache = InventoryCache(tmp_path)
    cache.refresh()
    run.assert_not_called()
    assert cache.snapshot()['error']
    cache.close()

def test_inventory_requires_matching_explicit_private_tunnel_reference(tmp_path, monkeypatch):
    from hanni.dashboard import cluster
    node = SimpleNamespace(id='karina', maintenance=False, username='owner', tailscale_ip='' + '.'.join(('100', '64', '0', '88')) + '')
    monkeypatch.setattr(cluster, 'load_nodes', lambda root: [node])
    monkeypatch.setattr(cluster, '_ssh_prefix', lambda *a, **k: ['verified-ssh'])
    monkeypatch.setattr(cluster, '_tailscale_executable', lambda: None)
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps({'checked_at': time.time()})))
    monkeypatch.setattr(cluster, '_run', run)
    (tmp_path / 'hermes').mkdir()
    config = tmp_path / 'hermes/config.json'
    config.write_text(json.dumps({'enabled': True, 'tunnel': {'destination': f'{node.username}@{node.tailscale_ip}'}}))
    cache = InventoryCache(tmp_path)
    cache.refresh()
    assert cache.value and cache.error is None and (run.call_count == 1)
    config.write_text(json.dumps({'enabled': True, 'tunnel': {'destination': 'someone@' + '.'.join(('100', '64', '0', '99')) + ''}}))
    cache.refresh()
    assert cache.error and run.call_count == 1
    cache.close()
