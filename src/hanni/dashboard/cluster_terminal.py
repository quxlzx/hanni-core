"""Open a visible, interactive SSH terminal for a fixed owner-supplied node."""
import base64
import os
import shutil
import subprocess
import threading
from uuid import UUID

from hanni.core.shutdown import FileStopStateStore
from hanni.dashboard.cluster import NODES, _tailscale_executable


def _ps_literal(value):
    return "'" + value.replace("'", "''") + "'"


def terminal_command(node, row, *, which=shutil.which):
    if os.name != 'nt':
        raise RuntimeError('SSH terminal launch currently requires a Windows dashboard host.')
    tailscale = _tailscale_executable() if row.get('tailscale_ssh_enabled') and row.get('connection') != 'lan' else None
    address = node.lan_ip if row.get('connection') == 'lan' else node.tailscale_ip
    if not address:
        raise ValueError('The node’s SSH address is not configured.')
    destination = f'{node.username}@{address}'
    executable = tailscale or which('ssh.exe')
    if not executable:
        raise RuntimeError('Install the OpenSSH client to open a node terminal.')
    options = ['-o', 'ClearAllForwardings=yes', '-o', 'ConnectTimeout=10',
               '-o', 'StrictHostKeyChecking=yes']
    identity = os.environ.get('HANNI_CLUSTER_SSH_IDENTITY', '').strip()
    if identity:
        options += ['-i', identity, '-o', 'IdentitiesOnly=yes']
    # Tailscale checks keys against the coordination server. Regular OpenSSH
    # requires an already verified host key and allows interactive authentication.
    ssh = [executable, 'ssh', destination] + options if tailscale else [executable] + options + [destination]
    script = '& ' + ' '.join(_ps_literal(arg) for arg in ssh)
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    powershell = which('powershell.exe')
    if not powershell:
        raise RuntimeError('Windows PowerShell is not available on this dashboard host.')
    console = [powershell, '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand', encoded]
    wt = which('wt.exe')
    return ([wt, '-w', 'new', 'new-tab', '--title', f'{node.name} SSH'] + console if wt else console), console, bool(wt)


class ClusterTerminal:
    def __init__(self, monitor, data_dir, *, popen=subprocess.Popen, which=shutil.which):
        self.monitor, self.data_dir = monitor, data_dir
        self.nodes = getattr(monitor, 'nodes', NODES)
        self._popen, self._which = popen, which
        self._lock = threading.Lock()
        self._requests, self._children = {}, []

    def project(self, snapshot):
        installed = os.name == 'nt' and self._which('powershell.exe') and self._which('ssh.exe')
        for row in snapshot['nodes']:
            reason = ('Under repair; SSH address is not configured.' if row['maintenance'] else
                      'SSH address and account are not configured.' if not row.get('username') or not (row.get('lan_ip') or row.get('tailscale_ip')) else
                      'SSH terminal launch requires a Windows dashboard host with OpenSSH and PowerShell.' if not installed else
                      'Terminal launch is unavailable in this dashboard session.' if self.data_dir is None else
                      'Checking SSH connection details.' if row.get('checked_at') is None else None)
            row['terminal'] = {'enabled': reason is None, 'reason': reason}
        return snapshot

    def execute(self, data):
        if not isinstance(data, dict) or set(data) != {'id','node'} or not isinstance(data['node'], str):
            raise ValueError('Expected a request ID and a roster node.')
        try:
            key = str(UUID(data['id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('A valid request UUID is required.')
        node = next((node for node in self.nodes if node.id == data['node']), None)
        if node is None or node.maintenance or not node.username or not (node.tailscale_ip or node.lan_ip):
            raise ValueError('This node is unknown, under repair or lacks an SSH address.')
        if self.data_dir is None:
            raise RuntimeError('Terminal launch is unavailable in this dashboard session.')
        if FileStopStateStore.for_data_dir(self.data_dir).load() is not None:
            raise RuntimeError('Terminal launch is blocked while HANNI is in Safe Mode.')
        with self._lock:
            if key in self._requests:
                if self._requests[key]['node'] != node.id:
                    raise ValueError('This request ID belongs to another node.')
                return dict(self._requests[key])
            if len(self._requests) >= 128:
                raise RuntimeError('Terminal request limit reached. Restart the dashboard before opening more windows.')
            row = next(row for row in self.project(self.monitor.snapshot())['nodes'] if row['id'] == node.id)
            if not row['terminal']['enabled']:
                raise RuntimeError(row['terminal']['reason'])
            command, console, wt = terminal_command(node, row, which=self._which)
            try:
                try:
                    child = self._popen(command, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if wt else getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
                except OSError:
                    if not wt:
                        raise
                    child = self._popen(console, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
                    wt = False
            except OSError:
                raise RuntimeError('The terminal could not be opened. Check the local terminal installation.')
            self._children = [process for process in self._children if process.poll() is None] + [child]
            result = {'id': key, 'node': node.id, 'opened': True,
                      'message': f'Opened {"Windows Terminal" if wt else "PowerShell"} for {node.name}. SSH login runs in that window.'}
            self._requests[key] = result
            return dict(result)
