"""Guided setup for the bundled, folder-scoped Office-file MCP."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import sys

from hanni.mcp.office import READ_TOOLS, office_root
from hanni.mcp.security import normalize_config

NAME = 'HANNI Office files'
CLOUD_NAME = 'Microsoft 365 Work IQ'


def cloud_status(hub):
    existing = next((item for item in hub.snapshot()['servers'] if item['name'] == CLOUD_NAME), None)
    command = existing['config']['command'] if existing else shutil.which('workiq') or ''
    # An already running desktop may predate npm's PATH update.
    if not command and os.name == 'nt' and os.environ.get('APPDATA'):
        candidate = Path(os.environ['APPDATA']) / 'npm' / 'workiq.cmd'
        if candidate.is_file(): command = str(candidate)
    return {'command': command, 'installed': bool(command and Path(command).is_file()),
            'auto_connect': existing['config']['auto_connect'] if existing else False}


def status(hub):
    hub.require()
    missing = [package for package in ('docx', 'pptx', 'openpyxl') if importlib.util.find_spec(package) is None]
    existing = next((item for item in hub.snapshot()['servers'] if item['name'] == NAME), None)
    folder = str(hub.root / 'office-documents')
    if existing:
        args = existing['config']['args']
        if args[:3] == ['-m', 'hanni.mcp.office', '--root'] and len(args) == 4:
            folder = args[3]
    return {'available': not missing, 'default_folder': folder, 'missing_packages': missing,
            'server_id': existing['id'] if existing else None,
            'auto_connect': existing['config']['auto_connect'] if existing else False,
            'enable_read_tools': READ_TOOLS.issubset({tool['original_name'] for tool in existing['tools'] if tool['enabled']}) if existing else True,
            'reason': 'Run SETUP_HANNI.cmd to install the Office file dependencies, then restart HANNI.' if missing else '',
            'cloud': cloud_status(hub)}


def setup_cloud(hub, data):
    hub._keys(data, {'command', 'auto_connect'})
    if type(data['auto_connect']) is not bool or not isinstance(data['command'], str):
        raise ValueError('Choose the installed Work IQ executable and startup preference.')
    command = Path(data['command']).expanduser()
    if (not command.is_absolute() or not command.is_file()
            or command.name.casefold() not in {'workiq', 'workiq.exe', 'workiq.cmd'}):
        raise ValueError('Install Microsoft Work IQ first, then enter the full path to workiq.cmd, workiq.exe, or workiq. Do not include arguments.')
    config = normalize_config({'name': CLOUD_NAME, 'transport': 'stdio', 'command': str(command.resolve()),
                              'args': ['mcp'], 'auto_connect': data['auto_connect'], 'timeout_seconds': 60})
    manager = hub.require()
    existing = next((item for item in manager.snapshot()['servers'] if item['name'].casefold() == CLOUD_NAME.casefold()), None)
    if existing and existing['config'] != config:
        raise ValueError('Microsoft 365 Work IQ is already configured with different settings. Edit that server or remove it before setting it up again.')
    server = existing or manager.add(config)
    if server['state'] != 'connected':
        snapshot = manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
        server = next(item for item in snapshot['servers'] if item['id'] == server['id'])
    if server['state'] != 'connected':
        raise ValueError('Work IQ settings were saved, but connection failed. Check installation and sign-in, then retry. ' + server['error'])
    # Work IQ can delegate actions. Never infer permissions from tool names or
    # auto-enable its EULA acceptance, authentication, or natural-language tools.
    if hub.auto_connections and config['auto_connect']:
        hub.auto_connections.pin(server['id'], server['config_hash'])
    return {'server_id': server['id'], 'connected': True, 'account_verified': False}


def setup(hub, data):
    hub._keys(data, {'folder', 'enable_read_tools', 'auto_connect'})
    if type(data['enable_read_tools']) is not bool or type(data['auto_connect']) is not bool:
        raise ValueError('Choose whether to enable reading and reconnect on startup.')
    readiness = status(hub)
    if not readiness['available']:
        raise ValueError(readiness['reason'])
    folder = office_root(data['folder'])
    config = normalize_config({'name': NAME, 'transport': 'stdio', 'command': sys.executable,
                              'args': ['-m', 'hanni.mcp.office', '--root', str(folder)],
                              'auto_connect': data['auto_connect'], 'timeout_seconds': 30})
    manager = hub.require()
    existing = next((item for item in manager.snapshot()['servers'] if item['name'].casefold() == NAME.casefold()), None)
    if existing and existing['config'] != config:
        raise ValueError('HANNI Office files is already configured with different settings. Edit that server or remove it before setting up another folder.')
    # Retrying a partial connection failure reuses the saved configuration.
    # Nothing runs until the authenticated MCP management policy allows setup.
    folder.mkdir(parents=True, exist_ok=True)
    server = existing or manager.add(config)
    if server['state'] != 'connected':
        snapshot = manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
        server = next(item for item in snapshot['servers'] if item['id'] == server['id'])
    if server['state'] != 'connected':
        raise ValueError('Office MCP settings were saved, but connection failed. Retry setup or use Reconnect on the saved server. ' + server['error'])
    if data['enable_read_tools']:
        tools = [tool for tool in server['tools'] if tool['original_name'] in READ_TOOLS]
        if {tool['original_name'] for tool in tools} != READ_TOOLS:
            raise ValueError('Office MCP connected without its expected reading tools. Review its discovered tools before enabling them.')
        manager.approve_tools(server['id'], [
            {'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': 'read_only'}
            for tool in tools])
    else:
        enabled_reads = [tool['original_name'] for tool in server['tools'] if tool['enabled'] and tool['original_name'] in READ_TOOLS]
        if enabled_reads:
            manager.disable_tools(server['id'], enabled_reads)
    if hub.auto_connections and config['auto_connect']:
        hub.auto_connections.pin(server['id'], server['config_hash'])
    return {'server_id': server['id'], 'folder': str(folder), 'connected': True}
