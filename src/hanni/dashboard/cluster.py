"""Bounded, read-only cluster monitoring over the owner's existing Tailscale/SSH.

No remote installation, interactive login, host-key acceptance, or browser-supplied
targets/commands. Samples and graph history remain in memory for this session.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import math
import ipaddress
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import threading
import time


REFRESH_SECONDS = 1
HISTORY_LENGTH = 60
TELEMETRY_STALE_SECONDS = 6
STREAM_IDLE_SECONDS = 15
TAILNET_REFRESH_SECONDS = 10
TAILNET_STALE_SECONDS = 25


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    emoji: str
    lan_ip: str | None
    tailscale_ip: str | None
    username: str | None
    maintenance: bool = False


NODES = (
    Node('hanni', 'HANNI', '🐰', None, None, None),
    Node('wonyoung', 'Wonyoung', '🐰', None, None, None),
    Node('haerin', 'Haerin', '🐱', None, None, None),
    Node('chaewon', 'Chaewon', '🐯', None, None, None),
    Node('minju', 'Minju', '🦊', None, None, None),
    Node('wonhee', 'Wonhee', '🐿️', None, None, None),
    Node('jeongyeon', 'Jeongyeon', '🐶', None, None, None),
    Node('karina', 'Karina', '🐈‍⬛', None, None, None),
    Node('yunjin', 'Yunjin', '🪼', None, None, None, maintenance=True),
)


def load_nodes(data_dir):
    """Deployment addresses belong only to the owner's protected local data."""
    if data_dir is None:
        return NODES
    root = Path(data_dir).resolve() / 'compute'
    path = root / 'deployment.json'
    if not path.exists():
        return NODES
    if path.is_symlink() or path.resolve().parent != root or path.stat().st_size > 262144:
        raise ValueError('Invalid protected cluster configuration.')
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    rows = raw.get('nodes', []) if isinstance(raw, dict) else None
    if not isinstance(rows, list) or len(rows) > 32:
        raise ValueError('Invalid configured node roster.')
    nodes = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {'id', 'name', 'emoji', 'lan_ip', 'tailscale_ip', 'username', 'maintenance'}:
            raise ValueError('Invalid configured node fields.')
        key = row.get('id')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key) or key in seen:
            raise ValueError('Invalid or duplicate configured node.')
        seen.add(key)
        name, emoji = row.get('name', key), row.get('emoji', '')
        if not isinstance(name, str) or not 1 <= len(name) <= 80 or not name.isprintable() or not isinstance(emoji, str) or len(emoji) > 16:
            raise ValueError('Invalid node display identity.')
        for field in ('lan_ip', 'tailscale_ip'):
            value = row.get(field)
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError('Invalid private node address.')
                address = ipaddress.ip_address(value)
                if address.is_multicast or address.is_unspecified or not (address.is_private or address in ipaddress.ip_network('100.64.0.0/10')):
                    raise ValueError('Node addresses must remain private.')
        username = row.get('username')
        if username is not None and (not isinstance(username, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}', username)):
            raise ValueError('Invalid SSH account.')
        maintenance = row.get('maintenance', False)
        if type(maintenance) is not bool:
            raise ValueError('Invalid maintenance state.')
        nodes.append(Node(key, name, emoji, row.get('lan_ip'), row.get('tailscale_ip'), username, maintenance))
    return tuple(nodes) if nodes else NODES

# Python standard library only, using the Python already installed on each node.
# Process CPU is measured over the same interval, not a lifetime-average ps value.
LINUX_SAMPLE = r'''
import json, os, pathlib, sys, time
root = pathlib.Path('/proc')
hz = os.sysconf('SC_CLK_TCK')
page_size = os.sysconf('SC_PAGE_SIZE')
def counters():
    cpu = [int(v) for v in (root/'stat').read_text().splitlines()[0].split()[1:9]]
    processes = {}
    for folder in root.iterdir():
        if not folder.name.isdigit() or int(folder.name) == os.getpid():
            continue
        try:
            stat = (folder/'stat').read_text()
            end = stat.rindex(')')
            fields = stat[end+2:].split()
            name = stat[stat.index('(')+1:end]
            processes[(int(folder.name), fields[19])] = (name, int(fields[11])+int(fields[12]), max(0,int(fields[21]))*page_size)
        except (OSError, ValueError, IndexError):
            pass
    return time.monotonic(), sum(cpu), cpu[3]+cpu[4], processes
previous = counters()
deadline = previous[0]+1
while True:
    time.sleep(max(0, deadline-time.monotonic()))
    current = counters()
    elapsed = max(.001, current[0]-previous[0])
    delta = current[1]-previous[1]
    cpu = max(0,min(100,100*(1-(current[2]-previous[2])/delta))) if delta>0 else None
    memory = {line.split(':')[0]:int(line.split()[1])*1024 for line in (root/'meminfo').read_text().splitlines() if len(line.split())>=2}
    total = memory['MemTotal']
    available = memory.get('MemAvailable', memory.get('MemFree',0)+memory.get('Buffers',0)+memory.get('Cached',0)+memory.get('SReclaimable',0)-memory.get('Shmem',0))
    used = max(0,min(total,total-available))
    processes = []
    for key, (name,ticks,rss) in current[3].items():
        old = previous[3].get(key)
        if old is not None:
            processes.append({'name':name, 'cpu_percent':max(0,100*(ticks-old[1])/hz/elapsed), 'ram_percent':100*rss/total})
    processes.sort(key=lambda p:(p['cpu_percent'],p['ram_percent']),reverse=True)
    print(json.dumps({'cpu_percent':cpu,'ram_percent':100*used/total,
        'ram_used_bytes':used,'ram_total_bytes':total,
        'uptime_seconds':float((root/'uptime').read_text().split()[0]),
        'processes':processes[:3]},allow_nan=False),flush=True)
    if len(sys.argv)>1 and sys.argv[1]=='once':
        break
    previous = current
    deadline = max(deadline+1,time.monotonic())
'''

WINDOWS_SAMPLE = r'''
$ErrorActionPreference = 'Stop'
$cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
$ram = Get-CimInstance Win32_OperatingSystem
$total = [double]$ram.TotalVisibleMemorySize * 1024
$used = $total - [double]$ram.FreePhysicalMemory * 1024
$processes = @(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process |
  Where-Object { $_.Name -notin @('_Total', 'Idle', 'powershell', 'sshd', 'ssh') } |
  Sort-Object PercentProcessorTime -Descending | Select-Object -First 3 |
  ForEach-Object { @{name=$_.Name; cpu_percent=[double]$_.PercentProcessorTime;
    ram_percent=100*[double]$_.WorkingSetPrivate/$total} })
@{cpu_percent=[double]$cpu.PercentProcessorTime; ram_percent=100*$used/$total;
  ram_used_bytes=$used; ram_total_bytes=$total;
  uptime_seconds=((Get-Date)-$ram.LastBootUpTime).TotalSeconds;
  processes=$processes} | ConvertTo-Json -Compress -Depth 4
'''


def _stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=1, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=1)


def _run(command, *, input=None, timeout=2.5):
    # Binary stdin preserves LF for remote POSIX shells; Windows text pipes
    # translate to CRLF and make `sh -s` reject otherwise-valid commands.
    with subprocess.Popen(command, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=os.name != 'nt',
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
        try:
            stdout, stderr = process.communicate(input.encode('utf-8') if input is not None else None, timeout=timeout)
        except subprocess.TimeoutExpired:
            # The Tailscale wrapper owns a child OpenSSH process. Stop that
            # owned tree as well so an unreachable node cannot accumulate SSHs.
            _stop_process(process)
            raise
        return subprocess.CompletedProcess(command, process.returncode,
                                           stdout.decode('utf-8', errors='replace'),
                                           stderr.decode('utf-8', errors='replace'))


def _tailscale_executable():
    executable = shutil.which('tailscale')
    if not executable and os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Tailscale/tailscale.exe'
        executable = str(candidate) if candidate.is_file() else None
    return executable


def tailscale_snapshot(nodes=None):
    """Project only roster availability/OS/SSH support; no users or public keys."""
    executable = _tailscale_executable()
    if not executable:
        return {'state': 'not-installed', 'peers': {}}
    try:
        result = _run([executable, 'status', '--json'])
        if result.returncode:
            return {'state': 'unavailable', 'peers': {}}
        raw = json.loads(result.stdout)
        running = raw.get('BackendState') == 'Running'
        peers = {}
        roster_ips = {node.tailscale_ip for node in (NODES if nodes is None else nodes) if node.tailscale_ip}
        entries = list((raw.get('Peer') or {}).values()) + [raw.get('Self') or {}]
        for peer in entries:
            for address in peer.get('TailscaleIPs', []):
                if address in roster_ips:
                    peers[address] = {
                        'online': peer.get('Online') if running and isinstance(peer.get('Online'), bool) else None,
                        'os': peer.get('OS') if peer.get('OS') in {'linux', 'windows', 'macOS'} else None,
                        'ssh_enabled': bool(peer.get('sshHostKeys')),
                    }
        return {'state': 'connected' if running else 'disconnected', 'peers': peers}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError):
        return {'state': 'unavailable', 'peers': {}}


def _ssh_prefix(node, address, *, tailscale=None):
    options = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'ConnectTimeout=2', '-o', 'ConnectionAttempts=1',
               '-o', 'ClearAllForwardings=yes', '-o', 'RequestTTY=no',
               '-o', 'ServerAliveInterval=2', '-o', 'ServerAliveCountMax=2']
    identity = os.environ.get('HANNI_CLUSTER_SSH_IDENTITY', '').strip()
    if identity:
        options += ['-i', identity, '-o', 'IdentitiesOnly=yes']
    destination = f'{node.username}@{address}'
    # Tailscale's wrapper verifies the host key against the coordination server
    # and uses the existing tailnet SSH policy. SSH options after the destination
    # are accepted by OpenSSH before its remote command argument.
    return [tailscale, 'ssh', destination] + options if tailscale else ['ssh'] + options + [destination]


def _ssh_error(stderr):
    error = stderr.lower()
    if 'tailscale ssh requires an additional check' in error:
        return 'Tailscale SSH needs a fresh sign-in. Open this node\'s SSH Terminal and complete the authentication check.'
    if 'host key verification failed' in error or 'host identification has changed' in error:
        return 'SSH host key needs verification. Connect from this Windows account after verifying the node fingerprint.'
    if 'permission denied' in error or 'authentication' in error:
        return 'SSH authentication is needed. Use an authorized key or this account’s SSH agent.'
    return 'SSH telemetry is unavailable. Check the node’s SSH service and supported operating system.'


def validate_sample(raw):
    fields = ('cpu_percent', 'ram_percent', 'ram_used_bytes', 'ram_total_bytes')
    values = {}
    for key in fields:
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError('Invalid telemetry')
        values[key] = float(value)
    if not all(0 <= values[k] <= 100 for k in fields[:2]):
        raise ValueError('Invalid utilization')
    if not 0 <= values['ram_used_bytes'] <= values['ram_total_bytes'] or values['ram_total_bytes'] <= 0:
        raise ValueError('Invalid memory capacity')
    if abs(100 * values['ram_used_bytes'] / values['ram_total_bytes'] - values['ram_percent']) > 1:
        raise ValueError('Inconsistent memory accounting')
    return values


def workload_sample(raw):
    uptime = raw.get('uptime_seconds')
    if isinstance(uptime, bool) or not isinstance(uptime, (int, float)) or not math.isfinite(uptime) or uptime < 0:
        uptime = None
    processes = raw.get('processes')
    safe = None
    if isinstance(processes, list):
        safe = []
        for row in processes[:3]:
            if not isinstance(row, dict) or not isinstance(row.get('name'), str):
                continue
            cpu, ram = row.get('cpu_percent'), row.get('ram_percent')
            if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or v < 0 for v in (cpu,ram)):
                continue
            if ram > 100:
                continue
            name = ''.join(c for c in row['name'][:80] if c.isprintable()).strip()
            if name:
                safe.append({'name': name, 'cpu_percent': cpu, 'ram_percent': ram})
    return {'uptime_seconds': uptime, 'processes': safe}


def probe_node(node, peer=None):
    peer = peer or {}
    row = {'checked_at': time.time(), 'sampled_at': None, 'metrics': None,
           'address': None, 'connection': None, 'availability_source': None,
           'tailscale_online': peer.get('online'), 'os': peer.get('os'), 'message': None,
           'uptime_seconds': None, 'processes': None, 'tailscale_ssh_enabled': peer.get('ssh_enabled') is True}
    if node.maintenance:
        return {**row, 'status': 'repair', 'message': 'Offline while under repair. Monitoring is paused.'}
    if not node.username or not (node.lan_ip or node.tailscale_ip):
        return {**row, 'status': 'unreachable', 'message': 'SSH addresses/account are not configured in the protected local node roster.'}
    row['status'] = 'online' if peer.get('online') is True else 'offline' if peer.get('online') is False else 'unreachable'
    row['availability_source'] = 'tailscale' if isinstance(peer.get('online'), bool) else 'network-probe'
    row['message'] = 'SSH port is not reachable over LAN or Tailscale. Resource readings are unavailable.'
    if not shutil.which('ssh'):
        return {**row, 'message': 'OpenSSH client is not installed on the dashboard computer.'}
    # A reachable port does not establish trust. Try the verified LAN connection
    # first, then the existing tailnet trust path if LAN authentication fails.
    for candidate, connection in [(node.lan_ip, 'lan'), (node.tailscale_ip, 'tailscale')]:
        if not candidate:
            continue
        try:
            with socket.create_connection((candidate, 22), timeout=.6):
                row.update(address=candidate, connection=connection)
        except OSError:
            continue
        if peer.get('online') is not True:
            row.update(status='reachable', availability_source='ssh-port')
        try:
            native = _tailscale_executable() if connection == 'tailscale' and peer.get('ssh_enabled') else None
            prefix = _ssh_prefix(node, candidate, tailscale=native)
            platform = peer.get('os')
            if platform is None:
                discovery = _run(prefix + ['uname -s'])
                if discovery.returncode == 255:
                    row['message'] = _ssh_error(discovery.stderr)
                    continue
                platform = 'linux' if discovery.stdout.strip() == 'Linux' else 'macOS' if discovery.stdout.strip() == 'Darwin' else 'windows'
            row['os'] = platform
            if platform == 'linux':
                result = _run(prefix + ['python3 -u - once'], input=LINUX_SAMPLE, timeout=4)
            elif platform == 'windows':
                encoded = base64.b64encode(WINDOWS_SAMPLE.encode('utf-16le')).decode('ascii')
                result = _run(prefix + [f'powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded}'])
            else:
                row['message'] = 'CPU/RAM collection currently supports Linux and Windows nodes.'
                continue
            if result.returncode:
                row['message'] = _ssh_error(result.stderr)
                continue
            raw = json.loads(result.stdout)
            metrics = validate_sample(raw)
            return {**row, 'status': 'online', 'availability_source': 'telemetry', 'message': None,
                    'sampled_at': time.time(), 'metrics': metrics, **workload_sample(raw)}
        except subprocess.TimeoutExpired:
            row['message'] = 'SSH telemetry timed out. The next sample will retry automatically.'
        except (OSError, ValueError, KeyError, TypeError):
            row['message'] = 'The node did not return valid CPU/RAM readings.'
    return row


class ClusterMonitor:
    def __init__(self, *, probe=probe_node, tailnet=None, nodes=None, data_dir=None):
        self.configuration_error = None
        try:
            self.nodes = tuple(nodes) if nodes is not None else load_nodes(data_dir)
        except (OSError, ValueError, TypeError):
            self.nodes = NODES
            self.configuration_error = 'Protected cluster configuration is invalid; SSH targets were not loaded.'
        self._probe = probe
        self._tailnet = tailnet if tailnet is not None else lambda: tailscale_snapshot(self.nodes)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker = None
        self._node_workers = []
        self._processes = {}
        self._stream_progress = {}
        self._peers = {}
        self._tailscale_state = 'checking'
        self._tailnet_checked_at = None
        self._checked_at = None
        self._rows = {
            node.id: {**asdict(node), 'status': 'repair' if node.maintenance else 'checking',
                      'message': 'Offline while under repair. Monitoring is paused.' if node.maintenance else 'Waiting for the first connection check.',
                      'checked_at': None, 'sampled_at': None, 'last_online_at': None,
                      'metrics': None, 'history': [], 'address': None, 'connection': None,
                      'uptime_seconds': None, 'processes': None,
                      'availability_source': None, 'tailscale_online': None, 'os': None}
            for node in self.nodes
        }

    def start(self):
        with self._lock:
            if self._worker is None and not self._stop.is_set():
                self._worker = threading.Thread(target=self._run, name='hanni-cluster', daemon=True)
                self._worker.start()

    def sample_once(self):
        tailnet = self._tailnet()
        with self._lock:
            self._tailscale_state = tailnet['state']
            self._peers = tailnet['peers']
            self._tailnet_checked_at = time.time()
        active = [node for node in self.nodes if not node.maintenance]
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(active))), thread_name_prefix='hanni-node') as pool:
            futures = {pool.submit(self._probe, node, tailnet['peers'].get(node.tailscale_ip)): node for node in active}
            for future in as_completed(futures):
                node = futures[future]
                try:
                    result = future.result()
                except Exception:
                    result = {'status': 'unreachable', 'checked_at': time.time(),
                              'sampled_at': None, 'metrics': None, 'address': None,
                              'connection': None, 'availability_source': None,
                              'tailscale_online': None, 'os': None, 'message': 'Node check could not be completed.'}
                self._record(node, result)
        with self._lock:
            self._checked_at = time.time()

    def _record(self, node, result):
        with self._lock:
            row = self._rows[node.id]
            row.update(uptime_seconds=None, processes=None)
            row.update(result)
            failures = row.get('connection_failures', 0)
            if result['status'] in {'offline', 'unreachable'}:
                failures += 1
                if failures == 1 and row.get('last_online_at') is not None:
                    row.update(status='checking', message='Connection check failed. Rechecking the node automatically.')
            elif result['status'] in {'online', 'reachable'}:
                failures = 0
            row['connection_failures'] = failures
            if result['status'] == 'online':
                row['last_online_at'] = result['checked_at']
            metrics = result['metrics']
            row['history'].append({'at': result['sampled_at'] or result['checked_at'],
                                   'cpu': metrics['cpu_percent'] if metrics else None,
                                   'ram': metrics['ram_percent'] if metrics else None})
            row['history'] = row['history'][-HISTORY_LENGTH:]
            self._checked_at = time.time()

    def _stream_node(self, node, initial, peer):
        native = _tailscale_executable() if initial['connection'] == 'tailscale' and peer.get('ssh_enabled') else None
        prefix = _ssh_prefix(node, initial['address'], tailscale=native)
        if initial['os'] == 'linux':
            command, script = prefix + ['python3 -u -'], LINUX_SAMPLE
        else:
            script = 'function Read-HanniSample {\n' + WINDOWS_SAMPLE + '\n}\nwhile ($true) {\n$watch = [Diagnostics.Stopwatch]::StartNew()\nRead-HanniSample\nStart-Sleep -Milliseconds ([Math]::Max(1,1000-$watch.ElapsedMilliseconds))\n}'
            encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
            command, script = prefix + [f'powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded}'], None
        with subprocess.Popen(command, stdin=subprocess.PIPE if script else subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              start_new_session=os.name != 'nt',
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
            try:
                with self._lock:
                    self._processes[node.id] = process
                    # Allow a new SSH stream its own handshake/first-frame
                    # budget, independent of the previous probe's timestamp.
                    self._stream_progress[node.id] = time.monotonic()
                if self._stop.is_set():
                    return
                if script:
                    process.stdin.write(script.encode('utf-8'))
                    process.stdin.close()
                while not self._stop.is_set():
                    line = process.stdout.readline(16385)
                    if not line:
                        break
                    if len(line) > 16384:
                        raise ValueError('Oversized telemetry frame')
                    raw = json.loads(line)
                    metrics = validate_sample(raw)
                    now = time.time()
                    with self._lock:
                        self._stream_progress[node.id] = time.monotonic()
                    yield {**initial, 'checked_at': now, 'sampled_at': now,
                           'metrics': metrics, **workload_sample(raw)}
            finally:
                _stop_process(process)
                with self._lock:
                    if self._processes.get(node.id) is process:
                        del self._processes[node.id]
                        self._stream_progress.pop(node.id, None)

    def _node_loop(self, node):
        while not self._stop.is_set():
            with self._lock:
                peer = dict(self._peers.get(node.tailscale_ip, {}))
            try:
                initial = self._probe(node, peer)
            except Exception:
                initial = {'status': 'unreachable', 'checked_at': time.time(),
                           'sampled_at': None, 'metrics': None, 'address': None,
                           'connection': None, 'availability_source': 'network-probe',
                           'tailscale_online': peer.get('online'), 'os': peer.get('os'),
                           'message': 'Connection check failed. Retrying automatically.'}
            # Connection timestamps describe the completed check, not the
            # beginning of a potentially slow LAN/Tailscale authentication.
            initial = {**initial, 'checked_at': time.time()}
            if self._stop.is_set():
                break
            self._record(node, initial)
            if initial['metrics'] is not None:
                try:
                    for result in self._stream_node(node, initial, peer):
                        if self._stop.is_set():
                            break
                        self._record(node, result)
                except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
                    pass
                if not self._stop.is_set():
                    self._record(node, {**initial, 'checked_at': time.time(), 'sampled_at': None,
                                       'metrics': None, 'uptime_seconds': None, 'processes': None,
                                       'status': 'checking',
                                       'availability_source': 'network-probe',
                                       'message': 'Telemetry connection interrupted. Reconnecting automatically.'})
            self._stop.wait(3)  # Reconnect backoff; healthy streams stay open.

    def _run(self):
        next_tailnet = 0.
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_tailnet:
                try:
                    tailnet = self._tailnet()
                except Exception:
                    tailnet = {'state': 'unavailable', 'peers': {}}
                with self._lock:
                    self._tailscale_state, self._peers = tailnet['state'], tailnet['peers']
                    self._tailnet_checked_at = time.time()
                next_tailnet = time.monotonic() + TAILNET_REFRESH_SECONDS
            if not self._node_workers and not self._stop.is_set():
                for node in self.nodes:
                    if not node.maintenance:
                        worker = threading.Thread(target=self._node_loop, args=(node,),
                                                  name=f'hanni-node-{node.id}', daemon=True)
                        self._node_workers.append(worker)
                        worker.start()
            with self._lock:
                stalled = [(node.id, self._processes[node.id]) for node in self.nodes
                           if node.id in self._processes and
                           time.monotonic() - self._stream_progress.get(node.id, time.monotonic()) > STREAM_IDLE_SECONDS]
            for node_id, process in stalled:
                with self._lock:
                    still_stalled = (self._processes.get(node_id) is process and
                        time.monotonic() - self._stream_progress.get(node_id, time.monotonic()) > STREAM_IDLE_SECONDS)
                if still_stalled:
                    _stop_process(process)
            self._stop.wait(1)

    def snapshot(self):
        with self._lock:
            rows = deepcopy(list(self._rows.values()))
            now = time.time()
            for row in rows:
                sampled = row.get('sampled_at')
                fresh = type(sampled) in (int, float) and math.isfinite(sampled) and 0 <= now - sampled <= TELEMETRY_STALE_SECONDS
                peer = self._peers.get(row.get('tailscale_ip'), {})
                stamp = self._tailnet_checked_at
                peer_fresh = stamp is not None and 0 <= now-stamp <= TAILNET_STALE_SECONDS
                row['tailscale_online'] = peer.get('online') if peer_fresh else None
                row['availability_checked_at'] = row.get('checked_at')
                row['availability_stale_seconds'] = TAILNET_STALE_SECONDS
                row['telemetry_stale'] = not fresh
                if row['maintenance']:
                    continue
                if not fresh:
                    row.update(metrics=None, uptime_seconds=None, processes=None)
                if fresh and row.get('metrics') is not None:
                    row.update(status='online', availability_source='telemetry',
                               availability_checked_at=sampled)
                elif peer_fresh and peer.get('online') is True:
                    row.update(status='online', availability_source='tailscale',
                               availability_checked_at=stamp)
                    if not row.get('message'):
                        row['message'] = 'SSH readings are delayed; Tailscale reports the node online.'
                elif row.get('status') == 'online' and row.get('availability_source') in {'telemetry', 'tailscale'}:
                    row.update(status='checking', availability_source='network-probe',
                               message='Connection evidence is stale; checking the node again.')
            return {'refresh_seconds': REFRESH_SECONDS, 'history_seconds': HISTORY_LENGTH * REFRESH_SECONDS,
                             'telemetry_stale_seconds': TELEMETRY_STALE_SECONDS,
                             'checked_at': self._checked_at, 'tailscale_state': self._tailscale_state,
                             'nodes': rows, **({'configuration_error': self.configuration_error} if self.configuration_error else {})}

    def close(self):
        self._stop.set()
        with self._lock:
            processes = list(self._processes.values())
        for process in processes:
            _stop_process(process)
        if self._worker:
            self._worker.join(timeout=3)
        deadline = time.monotonic() + 5
        for worker in self._node_workers:
            worker.join(timeout=max(0, deadline-time.monotonic()))
