"""Confirmed, fixed cluster power actions through existing SSH authorization.

The browser supplies a roster ID, never an address, account or shell command.
Power capabilities are checked read-only; no privilege policy is installed.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
import subprocess
import threading
import time
from uuid import UUID

from hanni.core.shutdown import FileStopStateStore
from hanni.dashboard.cluster import NODES, _run, _ssh_error, _ssh_prefix, _tailscale_executable, tailscale_snapshot
from hanni.dashboard.cluster_credentials import get_sudo_password


ACTIONS = {
    'reboot': '/usr/bin/systemctl -i reboot',
    'sleep': '/usr/bin/systemctl --no-ask-password --no-block --check-inhibitors=yes suspend',
}

CAPABILITY_SCRIPT = r'''
import json, os, subprocess
result = {'actions': {}, 'methods': {}}
for action, method, verb in [('reboot','CanReboot','reboot'),('sleep','CanSuspend','suspend')]:
    try:
        if action == 'reboot' and os.geteuid() == 0:
            allowed = os.path.isfile('/usr/bin/systemctl')
            result['actions'][action] = {'enabled': allowed, 'reason': None if allowed else 'systemctl is unavailable.'}
            result['methods'][action] = 'direct'
            continue
        probe = subprocess.run(['/usr/bin/busctl','call','org.freedesktop.login1',
            '/org/freedesktop/login1','org.freedesktop.login1.Manager',method],
            capture_output=True,text=True,timeout=2)
        state = probe.stdout.strip()
        allowed = probe.returncode == 0 and state == 's "yes"'
        execution = 'direct'
        if os.geteuid() != 0 and (action == 'reboot' or (not allowed and state == 's "challenge"')):
            arguments = ['-i','reboot'] if action == 'reboot' else [
                '--no-ask-password','--no-block','--check-inhibitors=yes',verb]
            sudo = subprocess.run(['sudo','-n','-l','--','/usr/bin/systemctl', *arguments],
                capture_output=True,timeout=2)
            allowed = sudo.returncode == 0
            execution = 'sudo'
        reason = None if allowed else ('Unavailable in this node’s power configuration.'
            if state in ('s "no"','s "na"') else 'The SSH account needs power-management authorization.')
        result['actions'][action] = {'enabled':allowed,'reason':reason}
        result['methods'][action] = execution
    except (OSError,subprocess.TimeoutExpired):
        result['actions'][action] = {'enabled':False,'reason':'Power-management support could not be checked.'}
print(json.dumps(result),flush=True)
'''


def check_power(node, row, peer, *, password=None):
    if node.maintenance or row.get('os') != 'linux' or not row.get('address'):
        return {'actions': {action: {'enabled': False, 'reason': 'A connected Linux node is required.'} for action in ACTIONS}, 'methods': {}, 'root': False}
    native = _tailscale_executable() if row['connection'] == 'tailscale' and peer.get('ssh_enabled') else None
    candidates = [(replace(node, username='root'), True), (node, False)] if native else [(node, False)]
    ssh_reason = None
    for account, root in candidates:
        try:
            result = _run(_ssh_prefix(account, row['address'], tailscale=native) + ['python3 -u -'],
                          input=CAPABILITY_SCRIPT, timeout=6)
            if result.returncode:
                if result.returncode == 255:
                    ssh_reason = _ssh_error(getattr(result, 'stderr', ''))
                continue
            raw = json.loads(result.stdout)
            actions, methods = {}, {}
            for action in ACTIONS:
                entry = raw['actions'][action]
                actions[action] = {'enabled': entry.get('enabled') is True,
                                   'reason': str(entry.get('reason') or '')[:160] or None}
                methods[action] = 'sudo' if raw.get('methods', {}).get(action) == 'sudo' else 'direct'
            if not root and password is not None:
                # sudo -l checks this exact command's policy, never executes it.
                authorization = _run(_ssh_prefix(account, row['address'], tailscale=native)
                                     + ["sudo -S -p '' -l -- " + ACTIONS['reboot']],
                                     input=password.reveal() + '\n', timeout=6)
                if authorization.returncode == 0:
                    actions['reboot'] = {'enabled': True, 'reason': None}
                    methods['reboot'] = 'sudo_password'
                else:
                    actions['reboot'] = {'enabled': False,
                        'reason': (_ssh_error(getattr(authorization, 'stderr', '')) if authorization.returncode == 255
                                   else 'The saved sudo credential could not authorize reboot.')}
            return {'actions': actions, 'methods': methods, 'root': root,
                    'native': bool(native), 'address': row['address'], 'checked_at': time.time()}
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            continue
    return {'actions': {action: {'enabled': False, 'reason': ssh_reason or 'SSH power authorization could not be verified.'} for action in ACTIONS}, 'methods': {}, 'root': False}


class ClusterPower:
    def __init__(self, monitor, data_dir, *, check=None, run=_run, tailnet=None,
                 password=get_sudo_password):
        self.monitor, self.data_dir = monitor, data_dir
        self._password = password
        self._check = check if check is not None else lambda node, row, peer: check_power(
            node, row, peer, password=self._password(node, self.data_dir))
        self._execute = run
        self.nodes = getattr(monitor, 'nodes', NODES)
        self._tailnet = tailnet if tailnet is not None else lambda: tailscale_snapshot(self.nodes)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker = None
        self._capabilities = {}
        self._operations = {}

    def start(self):
        if self.data_dir is None:
            return
        with self._lock:
            if self._worker is None and not self._stop.is_set():
                self._worker = threading.Thread(target=self._refresh, name='hanni-cluster-power', daemon=True)
                self._worker.start()

    def _refresh(self):
        while not self._stop.is_set():
            rows = {row['id']: row for row in self.monitor.snapshot()['nodes']}
            peers = self._tailnet()['peers']
            pending = []
            with self._lock:
                for node in self.nodes:
                    row, previous = rows[node.id], self._capabilities.get(node.id)
                    if not node.maintenance and row.get('metrics') is not None and (
                            previous is None or time.time()-previous.get('checked_at', 0) > 30):
                        pending.append((node, row, peers.get(node.tailscale_ip, {})))
            def check(args):
                node, row, peer = args
                result = self._check(node, row, peer)
                result['checked_at'] = time.time()
                with self._lock:
                    self._capabilities[node.id] = result
            if pending:
                with ThreadPoolExecutor(max_workers=8, thread_name_prefix='hanni-power-check') as pool:
                    list(pool.map(check, pending))
            self._stop.wait(2)

    def project(self, snapshot):
        now = time.time()
        with self._lock:
            capabilities, operations = deepcopy(self._capabilities), deepcopy(self._operations)
        for row in snapshot['nodes']:
            cap = capabilities.get(row['id'])
            reason = ('Power controls are unavailable in this dashboard session.' if self.data_dir is None else
                      'Under repair.' if row['maintenance'] else
                      'Awaiting a fresh SSH connection.' if not row.get('sampled_at') or now-row['sampled_at'] > 5 else
                      'Checking power permissions.' if not cap else
                      'Refreshing power permissions.' if now-cap.get('checked_at', 0) > 60 else None)
            recent = [op for op in operations.values() if op['node'] == row['id']]
            last = max(recent, key=lambda op: op['requested_at']) if recent else None
            if last and (last['status'] == 'sending' or (last['status'] in ('accepted', 'unknown') and now-last['requested_at'] < 60)):
                reason = 'A power request is pending. Wait for the node to settle.'
            row['power'] = {
                'actions': {action: {'enabled': False, 'reason': reason} if reason else cap['actions'][action] for action in ACTIONS},
                'last_operation': last,
            }
        return snapshot

    def execute(self, data):
        if not isinstance(data, dict) or set(data) != {'id', 'node', 'action', 'confirmed'}:
            raise ValueError('Expected a request ID, node, action and explicit confirmation.')
        if data['confirmed'] is not True or not isinstance(data['action'], str) or data['action'] not in ACTIONS or not isinstance(data['node'], str):
            raise ValueError('Confirm Sleep or Reboot for a roster node.')
        try:
            key = str(UUID(data['id']))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('A valid request UUID is required.')
        node = next((item for item in self.nodes if item.id == data['node']), None)
        if node is None or node.maintenance:
            raise ValueError('This node is unknown or under repair.')
        with self._lock:
            previous = self._operations.get(key)
            if previous:
                if (previous['node'], previous['action']) != (node.id, data['action']):
                    raise ValueError('This request ID belongs to a different power action.')
                return deepcopy(previous)
            if len(self._operations) >= 128:
                raise RuntimeError('Power request limit reached. Restart the dashboard before more actions.')
        if self._stop.is_set() or self.data_dir is None:
            raise RuntimeError('Power controls are unavailable in this dashboard session.')
        if FileStopStateStore.for_data_dir(self.data_dir).load() is not None:
            raise RuntimeError('Power controls are blocked while HANNI is in Safe Mode.')
        snapshot = self.project(self.monitor.snapshot())
        row = next(item for item in snapshot['nodes'] if item['id'] == node.id)
        allowed = row['power']['actions'][data['action']]
        if not allowed['enabled']:
            raise RuntimeError(allowed['reason'] or 'This power action is unavailable.')
        with self._lock:
            # Recheck under the reservation lock: simultaneous clicks/tab retries
            # must reserve one operation before any remote command is dispatched.
            previous = self._operations.get(key)
            if previous:
                if (previous['node'], previous['action']) != (node.id, data['action']):
                    raise ValueError('This request ID belongs to a different power action.')
                return deepcopy(previous)
            if len(self._operations) >= 128:
                raise RuntimeError('Power request limit reached. Restart the dashboard before more actions.')
            if any(op['node'] == node.id and (op['status'] == 'sending' or
                   (op['status'] in ('accepted','unknown') and time.time()-op['requested_at'] < 60)) for op in self._operations.values()):
                raise RuntimeError('A power request is already pending for this node.')
            cap = deepcopy(self._capabilities.get(node.id))
            if not cap or cap.get('address') not in {node.lan_ip, node.tailscale_ip}:
                raise RuntimeError('Power connection could not be verified.')
            if not cap['actions'][data['action']]['enabled'] or time.time()-cap.get('checked_at', 0) > 60:
                raise RuntimeError('Power authorization changed. Refresh the node before trying again.')
            password = None
            if cap['methods'].get(data['action']) == 'sudo_password':
                password = self._password(node, self.data_dir)
                if password is None:
                    raise RuntimeError('The saved sudo credential is unavailable. Configure it before rebooting.')
            operation = {'id': key, 'node': node.id, 'action': data['action'],
                         'requested_at': time.time(), 'status': 'sending', 'message': 'Sending power request.'}
            self._operations[key] = operation
        account = replace(node, username='root') if cap['root'] else node
        native = _tailscale_executable() if cap.get('native') else None
        command = ACTIONS[data['action']]
        if cap['methods'].get(data['action']) == 'sudo':
            command = 'sudo -n -- ' + command
        elif password is not None:
            command = "sudo -S -p '' -- " + command
        try:
            arguments = {'timeout': 8}
            if password is not None:
                arguments['input'] = password.reveal() + '\n'
            result = self._execute(_ssh_prefix(account, cap['address'], tailscale=native) + [command], **arguments)
            if result.returncode == 0:
                status, message = 'accepted', 'The node accepted the power request. Monitoring will reconnect when it becomes available.'
            elif result.returncode == 255:
                if 'tailscale ssh requires an additional check' in getattr(result, 'stderr', '').lower():
                    status, message = 'failed', _ssh_error(result.stderr)
                else:
                    status, message = 'unknown', 'SSH disconnected before confirmation. The action may have started. Check the node before trying again.'
            else:
                status, message = 'failed', ('The node rejected reboot. Check its sudo credential and power permissions.'
                    if data['action'] == 'reboot' else
                    'The node rejected sleep. Check its power permissions, sleep support or active shutdown inhibitors.')
        except subprocess.TimeoutExpired:
            status, message = 'unknown', 'Confirmation timed out. The action may have started. Check the node before trying again.'
        except OSError:
            status, message = 'failed', 'The local SSH client could not start the request.'
        with self._lock:
            operation.update(status=status, message=message)
            return deepcopy(operation)

    def close(self):
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=10)
