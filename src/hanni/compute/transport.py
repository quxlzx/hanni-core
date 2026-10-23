"""Fixed inference operations through strict SSH loopback forwarding.

Remote model text never becomes a command. Only protected deployment values
configure tunnels or the bounded, owner-authorized model-server launcher.
"""
from __future__ import annotations

from copy import deepcopy
import ipaddress
import hashlib
import json
import math
import os
import shlex
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .registry import ComputeError, integer, loopback_url


RESOURCE_SAMPLE = r'''
import csv,json,pathlib,platform,shutil,subprocess,os
root=pathlib.Path('/proc')
mem={line.split(':')[0]:int(line.split()[1])*1024 for line in (root/'meminfo').read_text().splitlines() if len(line.split())>=2}
gpus=[]
try:
 x=subprocess.run(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
 if x.returncode==0:
  for row in csv.reader(x.stdout.splitlines()):
   gpus.append({'id':row[0].strip(),'name':row[1].strip(),'vram_total_bytes':int(row[2])*1024**2,'vram_free_bytes':int(row[3])*1024**2,'utilization_percent':int(row[4])})
except (OSError,ValueError,subprocess.TimeoutExpired):pass
if not gpus:
 for card in pathlib.Path('/sys/class/drm').glob('card[0-9]*/device'):
  try:
   total=int((card/'mem_info_vram_total').read_text());used=int((card/'mem_info_vram_used').read_text())
   gpus.append({'id':card.resolve().name,'name':None,'vram_total_bytes':total,'vram_free_bytes':max(0,total-used),'utilization_percent':None})
  except (OSError,ValueError):pass
cpu=None
for line in (root/'cpuinfo').read_text().splitlines():
 if line.startswith('model name'):cpu=line.split(':',1)[1].strip();break
print(json.dumps({'os':platform.system(),'cpu':cpu,'logical_cpu_count':os.cpu_count(),'ram_total_bytes':mem.get('MemTotal'),'ram_available_bytes':mem.get('MemAvailable'),'gpus':gpus,'storage_free_bytes':shutil.disk_usage('/').free,'python_version':platform.python_version()}))
'''


class InferenceTransport:
    def __init__(self, registry, *, relay_only=False):
        if type(relay_only) is not bool:
            raise ComputeError('Relay selection requires an explicit trusted boolean.')
        self.relay_only = relay_only
        self.registry = registry
        self.lock = threading.RLock()
        self.tunnels = {}
        self.endpoint_locks = {}
        self.closed = False
        self.clients = {}
        self.owned = {}
        self.addresses = {}
        self.auth = {}
        self.resource_cache = {}
        self.identity_sources = {}
        self.identity_file_cache = {}

    @staticmethod
    def _node_binding(node):
        # Cache identity is the protected source, never just its display ID.
        fields = {name: node.get(name) for name in ('id', 'lan_ip', 'tailscale_ip', 'username')}
        fields['ssh_identity'] = os.environ.get('HANNI_CLUSTER_SSH_IDENTITY', '').strip()
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()

    def _worker_binding(self, worker, node):
        fields = {'node': self._node_binding(node), **{name: worker.get(name) for name in
                  ('worker_id', 'node_id', 'remote_port', 'protocol', 'api_key_env', 'auth_config_file')}}
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _resource_frame(raw):
        """Project bounded, internally consistent measurements or unknowns."""
        if not isinstance(raw, dict) or not isinstance(raw.get('gpus', []), list):
            return {}
        if len(raw.get('gpus', [])) > 32 or any(not isinstance(item, dict) for item in raw.get('gpus', [])):
            return {}
        def text(value, limit=256):
            return value if isinstance(value, str) and len(value) <= limit and all(c.isprintable() for c in value) else None
        def capacity(value, *, positive=False):
            return value if type(value) is int and (value > 0 if positive else value >= 0) else None
        frame = {name: text(raw.get(name)) for name in ('os', 'cpu', 'python_version')}
        frame['logical_cpu_count'] = capacity(raw.get('logical_cpu_count'), positive=True)
        frame['storage_free_bytes'] = capacity(raw.get('storage_free_bytes'))
        total = capacity(raw.get('ram_total_bytes'), positive=True)
        available = capacity(raw.get('ram_available_bytes'))
        valid_ram = total is not None and available is not None and available <= total
        frame.update(ram_total_bytes=total if valid_ram else None,
                     ram_available_bytes=available if valid_ram else None)
        frame['gpus'] = []
        for item in raw.get('gpus', []):
            identifier = text(item.get('id'))
            total = capacity(item.get('vram_total_bytes'), positive=True)
            free = capacity(item.get('vram_free_bytes'))
            utilization = item.get('utilization_percent')
            valid_utilization = (utilization is None or type(utilization) in (int, float)
                                 and math.isfinite(utilization) and 0 <= utilization <= 100)
            if identifier and total is not None and free is not None and free <= total and valid_utilization:
                frame['gpus'].append({'id': identifier, 'name': text(item.get('name')),
                    'vram_total_bytes': total, 'vram_free_bytes': free,
                    'utilization_percent': utilization})
        # An empty/malformed response never establishes a current sample.
        return frame if valid_ram or frame['gpus'] else {}

    def runtime_files(self, worker):
        """Hash only configured model/backend files through the original SSH path.

        Full digests are cached by complete stat identity. The small follow-up
        stat request notices ordinary same-name weight/backend replacements.
        No configuration contents, process command lines or credentials leave
        the node. Files supplied by engineering must already be installation
        paths validated by the adaptive registry.
        """
        startup = worker.get('startup') or {}
        sources = self.identity_sources.get(worker['worker_id'], {})
        models = sources.get('model_files') or ([startup['model_file']] if startup.get('model_file') else [])
        backends = sources.get('backend_files') or ([startup['executable']] if startup.get('executable') else [])
        if not models or not backends:
            return None
        node = self.registry.node(worker['node_id'])
        source = self._node_binding(node)
        files = [{'path': value, 'model': True} for value in models] + [{'path': value, 'model': False} for value in backends]
        for item in files:
            value = item['path']
            if not isinstance(value, str) or not value.startswith('/') or any(char in value for char in '\x00\n\r'):
                raise ComputeError('Runtime identity requires explicit existing absolute file paths.')
        known = {item['path']: self.identity_file_cache.get((source, item['path'])) for item in files}
        parameters = json.dumps({'files': files, 'known': known,
            'approved_model_roots': worker.get('identity_model_roots', []),
            'installation_dir': startup.get('installation_dir')}, allow_nan=False)
        program = '''import hashlib,json,pathlib
p=json.loads(PARAMETERS)
for value in p['approved_model_roots']:
 root=pathlib.Path(value)
 if not root.is_dir() or root.is_symlink() or root.resolve()!=root:raise SystemExit(6)
out=[]
for item in p['files']:
 path=pathlib.Path(item['path'])
 if path.is_symlink() or not path.is_file() or path.resolve()!=path:raise SystemExit(3)
 stat=path.stat(); stamp=[stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino]
 known=p['known'].get(item['path'])
 if known and known.get('stat')==stamp:
  digest=known['sha256']
 else:
  h=hashlib.sha256()
  with path.open('rb') as stream:
   if item['model']:
    magic=stream.read(4)
    if magic!=b'GGUF':raise SystemExit(4)
    h.update(magic)
   while True:
    chunk=stream.read(1024**2)
    if not chunk:break
    h.update(chunk)
  end=path.stat()
  if [end.st_size,end.st_mtime_ns,end.st_ctime_ns,end.st_ino]!=stamp:raise SystemExit(5)
  digest=h.hexdigest()
 out.append({'path':item['path'],'model':item['model'],'stat':stamp,'sha256':digest})
print(json.dumps({'files':out}))
'''.replace('PARAMETERS', repr(parameters))
        try:
            result = subprocess.run(self._ssh(node, self._address(node)) + ['python3 -'], input=program.encode(),
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=300,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode or len(result.stdout) > 65536:
                raise ComputeError('Exact model/backend file identity could not be measured.')
            raw = json.loads(result.stdout)
            if len(raw['files']) != len(files): raise ValueError('Missing identity files.')
            for item in raw['files']:
                self.identity_file_cache[(source, item['path'])] = item
            return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            raise ComputeError('Exact model/backend file identity could not be measured.') from None

    def resources(self, worker):
        if worker['node_id'] == 'local':
            return {'ram_available_bytes': None, 'vram_free_bytes': None}
        node = self.registry.node(worker['node_id'])
        binding = self._node_binding(node)
        cached = self.resource_cache.get(node['id'])
        if cached and cached[3] == binding and 0 <= time.monotonic() - cached[0] < 10:
            raw = cached[1]
        else:
            try:
                result = subprocess.run(self._ssh(node, self._address(node)) + ['python3 -'],
                    input=RESOURCE_SAMPLE.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                raw = self._resource_frame(json.loads(result.stdout)) if result.returncode == 0 and len(result.stdout) < 65536 else {}
            except (OSError, ValueError, subprocess.TimeoutExpired):
                raw = {}
            self.resource_cache[node['id']] = (time.monotonic(), raw, time.time() if raw else None, binding)
        gpu = None
        expected = (worker.get('startup') or {}).get('gpu_device')
        if expected is not None:
            gpu = next((item for item in raw.get('gpus', []) if item.get('id') == expected), None)
        elif worker.get('gpu'):
            # Exact, unique configured GPU name; ambiguous same-name cards remain unknown.
            matches=[item for item in raw.get('gpus',[]) if item.get('name')==worker['gpu']]
            if len(matches)==1: gpu=matches[0]
        elif worker.get('protocol') == 'strata_openai' and len(raw.get('gpus', [])) == 1:
            gpu = raw['gpus'][0]
        if gpu is None and expected is None and worker.get('protocol')=='strata_openai' and len(raw.get('gpus',[]))==1:
            gpu=raw['gpus'][0]
        ram = raw.get('ram_available_bytes')
        vram = gpu.get('vram_free_bytes') if gpu else None
        return {'ram_available_bytes': ram if type(ram) is int and ram >= 0 else None,
                'vram_free_bytes': vram if type(vram) is int and vram >= 0 else None,
                'node_hardware': raw or None, 'gpu_measurement': gpu,
                'resource_sampled_at': self.resource_cache[node['id']][2]}

    def _ssh(self, node, address, *, forward=None):
        if not shutil.which('ssh'):
            raise ComputeError('OpenSSH is unavailable. Configure verified SSH keys or existing Tailscale SSH.')
        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=3', '-o', 'ConnectionAttempts=1',
                '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
                '-o', 'RequestTTY=no', '-o', 'ExitOnForwardFailure=yes']
        identity = os.environ.get('HANNI_CLUSTER_SSH_IDENTITY', '').strip()
        if identity:
            args += ['-i', identity, '-o', 'IdentitiesOnly=yes']
        if forward is None:
            args += ['-o', 'ClearAllForwardings=yes']
        else:
            args += ['-N', '-L', forward]
        username = node.get('username')
        if not username:
            raise ComputeError('A verified SSH account is not configured for this node.')
        destination = f'{username}@{address}'
        if address == node.get('tailscale_ip'):
            from hanni.dashboard.cluster import _tailscale_executable, tailscale_snapshot
            from types import SimpleNamespace
            tailnet = tailscale_snapshot([SimpleNamespace(tailscale_ip=address)])
            native = _tailscale_executable()
            if native and tailnet['peers'].get(address, {}).get('ssh_enabled'):
                # Existing Tailscale authentication and coordination-signed host
                # keys; the wrapper still receives strict OpenSSH options.
                return [native, 'ssh', destination] + args[1:]
        return args + [destination]

    def _address(self, node):
        binding = self._node_binding(node)
        cached = self.addresses.get(node['id'])
        if cached and cached[2] == binding and 0 <= time.monotonic() - cached[1] < 60:
            return cached[0]
        for field in ('lan_ip', 'tailscale_ip'):
            address = node.get(field)
            if not address:
                continue
            try:
                with socket.create_connection((address, 22), timeout=.5):
                    pass
                # TCP connectivity alone is not verified authentication. A
                # failed LAN host/key check falls back to the signed tailnet.
                result = subprocess.run(self._ssh(node, address) + ['true'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode == 0:
                    self.addresses[node['id']] = (address, time.monotonic(), binding)
                    return address
            except (OSError, subprocess.TimeoutExpired):
                continue
        raise ComputeError('Node SSH is unreachable over the configured LAN and Tailscale paths.')

    def endpoint(self, worker):
        key = worker['worker_id']
        with self.lock:
            if self.closed:
                raise ComputeError('Inference transport is closed.')
            if worker['node_id'] == 'local':
                return loopback_url(worker['local_url'])
            lock = self.endpoint_locks.setdefault(key, threading.RLock())
        # A stalled SSH handshake on one worker must not hold the lock that
        # protects every other worker's tunnel and heartbeat.
        with lock:
            node = self.registry.node(worker['node_id'])
            binding = self._worker_binding(worker, node)
            with self.lock:
                if self.closed:
                    raise ComputeError('Inference transport is closed.')
                current = self.tunnels.get(key)
                if current and current.get('binding') == binding and current['process'].poll() is None:
                    return current['url']
                self.tunnels.pop(key, None)
            if current and current['process'].poll() is None:
                from hanni.dashboard.cluster import _stop_process
                _stop_process(current['process'])
            address = self._address(node)
            with self.lock:
                if self.closed:
                    raise ComputeError('Inference transport closed during connection.')
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            command = self._ssh(node, address, forward=f'127.0.0.1:{port}:127.0.0.1:{worker["remote_port"]}')
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=os.name != 'nt',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            published = False
            try:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise ComputeError('Verified SSH forwarding failed; configure host trust and authentication.')
                    with self.lock:
                        if self.closed:
                            raise ComputeError('Inference transport closed during connection.')
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            url = f'http://127.0.0.1:{port}'
                            with self.lock:
                                if self.closed:
                                    raise ComputeError('Inference transport closed during connection.')
                                self.tunnels[key] = {'process': process, 'url': url, 'binding': binding}
                                published = True
                            return url
                    except OSError:
                        time.sleep(.05)
                raise ComputeError('SSH forwarding timed out.')
            finally:
                if not published:
                    from hanni.dashboard.cluster import _stop_process
                    _stop_process(process)

    def request(self, worker, method, path, *, payload=None, timeout=3, cancel=None):
        worker = deepcopy(worker)
        paths = {'/health', '/v1/models', '/props', '/v1/chat/completions', '/tokenize'}
        if worker.get('protocol') == 'strata_openai':
            paths |= {'/v1/messages/count_tokens', '/v1/messages'}
        if path not in paths:
            raise ComputeError('Unsupported inference operation.')
        if cancel is not None and cancel.is_set():
            raise ComputeError('Inference was cancelled before dispatch.')
        node, binding, authority_flags, url = None, None, None, None
        if worker['node_id'] != 'local':
            self.registry.reload()
            node = self.registry.node(worker['node_id'])
            binding = self._worker_binding(worker, node)
            registered = self.registry.worker(worker['worker_id'])
            authority_flags = (self.registry.deployment['enabled'], registered['enabled'])

        def check_source():
            if cancel is not None and cancel.is_set():
                raise ComputeError('Inference was cancelled; the request was withdrawn.')
            if node is not None:
                self.registry.reload()
                current = self.registry.worker(worker['worker_id'])
                current_node = self.registry.node(current['node_id'])
                if self._worker_binding(current, current_node) != binding:
                    raise ComputeError('Protected inference source changed; the request was withdrawn.')
                # Stable disabled endpoints may still answer passive health.
                # A request cannot survive a change in its captured authority.
                if (self.registry.deployment['enabled'], current['enabled']) != authority_flags:
                    raise ComputeError('Protected inference authority changed; the request was withdrawn.')
                if url is not None:
                    with self.lock:
                        tunnel = self.tunnels.get(worker['worker_id'])
                        if tunnel and (tunnel.get('binding') != binding or tunnel.get('url') != url):
                            raise ComputeError('Inference forwarding source changed; the request was withdrawn.')

        check_source()
        if self.relay_only and node is not None:
            return self._relay_request(worker, node, method, path, payload, timeout, cancel, check_source)
        url = self.endpoint(worker)
        check_source()
        headers = {}
        secret = os.environ.get(worker.get('api_key_env', ''))
        if worker.get('auth_config_file'):
            if node is None:
                raise ComputeError('File-based authentication requires a registered remote source.')
            key = (worker['worker_id'], binding)
            # Withdraw the old source's retained credential before rebinding.
            self.auth = {scope: value for scope, value in self.auth.items() if scope[0] != worker['worker_id'] or scope == key}
            if key not in self.auth:
                script = 'python3 -c ' + shlex.quote('import json,pathlib,sys; v=json.loads(pathlib.Path(' +
                    repr(worker['auth_config_file']) + ').read_text()).get("api_key"); '
                    'sys.stdout.write(v if isinstance(v,str) else "")')
                result = subprocess.run(self._ssh(node, self._address(node)) + [script],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode or len(result.stdout) > 4096:
                    raise ComputeError('Existing worker authentication could not be read securely.')
                self.auth[key] = result.stdout.decode('utf-8')
            secret = self.auth[key]
        check_source()
        if worker.get('api_key_env') and not secret:
            raise ComputeError('The protected compute authentication environment is unavailable.')
        if secret:
            headers['Authorization'] = 'Bearer ' + secret
        with httpx.Client(timeout=httpx.Timeout(timeout), trust_env=False, follow_redirects=False) as client:
            with self.lock:
                self.clients[id(client)] = (worker['worker_id'], client, cancel)
            try:
                check_source()
                response = client.request(method, url + path, json=payload, headers=headers)
                if response.is_redirect:
                    raise ComputeError('Inference redirects are refused at the worker trust boundary.')
                response.raise_for_status()
                if len(response.content) > 1048576:
                    raise ComputeError('Inference response exceeds the bounded result limit.')
                data = response.json()
                if not isinstance(data, dict):
                    raise ComputeError('Inference endpoint returned an invalid response.')
                if cancel is not None and cancel.is_set():
                    raise ComputeError('Inference returned after cancellation; result was discarded.')
                check_source()
                return data
            except (httpx.HTTPError, ValueError) as exc:
                if isinstance(exc, ComputeError):
                    raise
                raise ComputeError('Inference endpoint failed, timed out, or returned invalid JSON.') from None
            finally:
                with self.lock:
                    self.clients.pop(id(client), None)

    def _relay_request(self, worker, node, method, path, payload, timeout, cancel, check_source):
        """Opted SSH stdio relay to the registered loopback API; opens no listener.

        Auth files remain on their configured host. Closing this owned SSH helper
        requests cancellation; it does not guarantee that upstream inference stops.
        """
        if method not in {'GET', 'POST'} or path not in {'/health','/v1/models','/props','/tokenize','/v1/chat/completions'}:
            raise ComputeError('Relay operation is unavailable.')
        from hanni.workflows.types import canonical_json
        canonical_json(payload, maximum=262144)
        secret = os.environ.get(worker.get('api_key_env', ''))
        if worker.get('api_key_env') and not secret:
            raise ComputeError('The protected authentication environment is unavailable.')
        envelope = {'method':method,'url':'http://127.0.0.1:'+str(worker['remote_port'])+path,
                    'payload':payload,'timeout':timeout,'auth_file':worker.get('auth_config_file'), 'key':secret}
        script = r'''import json,sys,urllib.request,pathlib
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw): return None
x=json.load(sys.stdin)
try:
 key=json.loads(pathlib.Path(x['auth_file']).read_text()).get('api_key') if x.get('auth_file') else x.get('key')
 headers={'Content-Type':'application/json'}
 if key: headers['Authorization']='Bearer '+key
 data=json.dumps(x['payload']).encode() if x['payload'] is not None else None
 req=urllib.request.Request(x['url'],data=data,headers=headers,method=x['method'])
 with urllib.request.build_opener(NoRedirect).open(req,timeout=x['timeout']) as response:
  body=response.read(1048577)
 if len(body)>1048576: raise ValueError()
 value=json.loads(body)
 if not isinstance(value,dict): raise ValueError()
 sys.stdout.write(json.dumps(value))
except Exception:
 sys.exit(2)
'''
        check_source()
        process = subprocess.Popen(self._ssh(node,self._address(node))+['python3 -c '+shlex.quote(script)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        class Handle:
            def close(self):
                if process.poll() is None: process.kill()
        handle = Handle()
        with self.lock: self.clients[id(handle)] = (worker['worker_id'],handle,cancel)
        deadline = time.monotonic()+timeout+5
        first = True
        try:
            while True:
                check_source()
                if time.monotonic() >= deadline: raise ComputeError('Inference relay timed out; outcome is unavailable.')
                try:
                    output,_ = process.communicate(json.dumps(envelope).encode() if first else None,timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    first=False
            check_source()
            if process.returncode or len(output)>1048576:
                raise ComputeError('Registered inference relay failed; no valid response was received.')
            value=json.loads(output)
            if not isinstance(value,dict): raise ComputeError('Invalid relay response.')
            return value
        except (OSError,ValueError) as exc:
            if isinstance(exc,ComputeError): raise
            raise ComputeError('Inference relay failed safely.') from None
        finally:
            try:
                handle.close()
                # Windows SSH descendants can retain inherited pipe handles
                # after the owned parent exits. Do not let drain timeout hide
                # cancellation or leave an active request in the registry.
                try:
                    process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            finally:
                with self.lock: self.clients.pop(id(handle),None)

    def cancel(self, worker_id=None, event=None):
        # Closing an owned socket requests transport cancellation. The remote
        # server may still finish pure inference; its process is never killed.
        with self.lock:
            for key, client, cancel in list(self.clients.values()):
                if (worker_id is None or key == worker_id) and (event is None or cancel is event):
                    if cancel is not None:
                        cancel.set()
                    try:
                        client.close()
                    except Exception:
                        pass

    def health(self, worker):
        started = time.monotonic()
        try:
            health = self.request(worker, 'GET', '/health')
            if health.get('status') not in {'ok', 'ready', 'healthy'}:
                raise ComputeError('Model server is not ready.')
            models = self.request(worker, 'GET', '/v1/models')
            entries = models.get('data')
            if not isinstance(entries, list) or not entries:
                raise ComputeError('Worker has no loaded model.')
            model_id = entries[0].get('id') if isinstance(entries[0], dict) else None
            if not isinstance(model_id, str) or not model_id:
                raise ComputeError('Worker did not report a model identifier.')
            expected = worker.get('model_id')
            if expected and expected != model_id:
                raise ComputeError('Loaded model differs from the registered model. Scheduling is blocked.')
            reported = None
            runtime_identity = None
            architecture = quantization = None
            try:
                props = self.request(worker, 'GET', '/props')
                settings = props.get('default_generation_settings', {})
                candidate = settings.get('n_ctx') if isinstance(settings, dict) else None
                if type(candidate) is int and candidate > 0:
                    reported = candidate
                metadata = props.get('model_meta') or {}
                runtime_identity = hashlib.sha256(json.dumps({
                    'model_id': model_id, 'model_path': props.get('model_path'),
                    'model_ftype': props.get('model_ftype'), 'build_info': props.get('build_info'),
                    'chat_template': props.get('chat_template'), 'modalities': props.get('modalities'),
                    'architecture': metadata.get('general.architecture'),
                }, sort_keys=True).encode()).hexdigest()
                value = metadata.get('general.architecture')
                architecture = value if isinstance(value, str) else None
                value = props.get('model_ftype', metadata.get('general.file_type'))
                quantization = str(value) if type(value) in (str, int) else None
            except ComputeError:
                pass  # OpenAI-compatible APIs need not implement llama.cpp props.
            files_identity = self.runtime_files(worker) if worker['node_id'] != 'local' else None
            from hanni.models.endpoint_contract import build
            contract = build(endpoint_id=worker['worker_id'],model_id=expected or model_id,
                loaded_model_id=model_id,binding={'worker':self.registry._worker_identity(worker),
                    'runtime':runtime_identity,'files':files_identity},configured_context=worker.get('context_configured'),
                reported_context=reported,status='healthy',sampled_at=self.registry.clock(),
                concurrency=worker.get('concurrency',1),auth_kind='protected_file' if worker.get('auth_config_file')
                    else 'environment' if worker.get('api_key_env') else 'ssh' if worker['node_id']!='local' else 'none',
                auth_name='configured_worker_auth' if worker.get('auth_config_file') else worker.get('api_key_env',''),
                advertised=('chat','structured_output') if 'structured_json' in worker.get('capabilities',[]) else ('chat',))
            return {'status': 'healthy', 'model_id': model_id, 'context_reported': reported,
                    'last_heartbeat': self.registry.clock(), 'health_latency_ms': (time.monotonic() - started) * 1000,
                    'queue_depth': None,
                    'runtime_identity': runtime_identity, 'architecture': architecture, 'quantization': quantization,
                    'runtime_files_identity': files_identity,
                    'endpoint_contract':contract,
                    'error': None}
        except ComputeError as exc:
            return {'status': 'unhealthy', 'last_heartbeat': self.registry.clock(), 'error': str(exc),
                    'model_id': None, 'context_reported': None, 'queue_depth': None}

    def start(self, worker):
        with self.lock:
            return self._start(worker)

    def _start(self, worker):
        config = worker.get('startup') or {}
        if config.get('authorized') is not True:
            raise ComputeError('Model-server startup requires explicit protected deployment authorization.')
        if worker['node_id'] == 'local':
            raise ComputeError('Use the original local model manager for local server lifecycle.')
        # Readiness check prevents duplicates, including independently owned servers.
        if self.health(worker)['status'] == 'healthy':
            return {'status': 'already_running', 'owned': False}
        # A loading, mismatched or unsupported service may already own this port.
        # SSH's forwarded listener is always local; check the actual remote port.
        node = self.registry.node(worker['node_id'])
        remote_check = ('python3 -c ' + shlex.quote('import socket,sys; s=socket.socket(); s.settimeout(1); '
            + f'r=s.connect_ex(("127.0.0.1",{worker["remote_port"]})); s.close(); sys.exit(0 if r==0 else 3)'))
        check = subprocess.run(self._ssh(node, self._address(node)) + [remote_check],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if check.returncode != 3:
            raise ComputeError('The server port is occupied or occupancy cannot be verified; duplicate startup refused.')
        if config.get('kind') == 'strata':
            from .strata import launch_program
            nonce = uuid4().hex
            context = config.get('context', 8192)
            if context > 8192 and self.registry.prior_verified_context(worker['worker_id']) < context // 2:
                raise ComputeError('Verify the preceding Strata context stage before increasing allocation.')
            script = launch_program(config, port=worker['remote_port'], nonce=nonce)
            result = subprocess.run(self._ssh(node, self._address(node)) + ['python3 -'],
                input=script.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                receipt = json.loads(result.stdout)
                pid = receipt['pid']
            except (ValueError, KeyError, TypeError):
                raise ComputeError('Existing Strata did not return an owned process receipt.') from None
            if result.returncode or type(pid) is not int or pid <= 1:
                raise ComputeError('The authorized Strata server could not be launched.')
            self.owned[worker['worker_id']] = {'pid': pid, 'nonce': nonce, 'node': node, **receipt}
            return {'status': 'starting', 'owned': True, 'pid': pid, 'context_configured': context,
                    'maximum_runtime_seconds': config.get('max_runtime_seconds', 600)}
        if config.get('kind') != 'llama_cpp' or set(config) - {
            'authorized', 'kind', 'executable', 'model_file', 'gpu_device', 'context', 'cache_type_k', 'cache_type_v'}:
            raise ComputeError('Only a verified llama.cpp worker launch is supported. Existing Strata launchers remain unchanged.')
        executable, model = config.get('executable'), config.get('model_file')
        for value in (executable, model):
            if not isinstance(value, str) or not value.startswith('/') or '\x00' in value or '\n' in value:
                raise ComputeError('A verified absolute remote binary and existing model are required.')
        device = config.get('gpu_device')
        if not isinstance(device, str) or not __import__('re').fullmatch(r'GPU-[0-9A-Fa-f-]{8,64}', device):
            raise ComputeError('Use a discovered GPU UUID for explicit single-GPU assignment.')
        context = integer(config.get('context', 8192), 1024, 131072, 'launch context')
        if context > 8192 and self.registry.prior_verified_context(worker['worker_id']) < context // 2:
            raise ComputeError('Verify the preceding context stage before increasing allocation.')
        caches = [config.get('cache_type_k', 'f16'), config.get('cache_type_v', 'f16')]
        if caches != ['f16', 'f16']:
            raise ComputeError('Quantized KV caches require independently verified Pascal compatibility before deployment.')
        nonce = uuid4().hex
        args = [executable, '-m', model, '--host', '127.0.0.1', '--port', str(worker['remote_port']),
                '-c', str(context), '-np', '1', '-ngl', '99', '--flash-attn', 'off']
        # Fixed generated shell operation; all configuration values are quoted.
        script = 'set -eu\n' + f'test -x {shlex.quote(executable)}\ntest -f {shlex.quote(model)}\n' + \
            f'log=$(mktemp "${{TMPDIR:-/tmp}}/hanni-compute-{nonce}.XXXXXX")\n' + \
            f'CUDA_VISIBLE_DEVICES={shlex.quote(device)} HANNI_COMPUTE_OWNER={nonce} nohup ' + \
            shlex.join(args) + ' </dev/null >"$log" 2>&1 &\nprintf "%s\\n" "$!"\n'
        command = self._ssh(node, self._address(node)) + ['sh -s']
        result = subprocess.run(command, input=script.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            pid = int(result.stdout.strip())
        except ValueError:
            raise ComputeError('The authorized server did not return an owned process receipt.') from None
        if result.returncode or pid <= 1:
            raise ComputeError('The authorized server could not be launched.')
        self.owned[worker['worker_id']] = {'pid': pid, 'nonce': nonce, 'node': node}
        return {'status': 'starting', 'owned': True, 'pid': pid, 'context_configured': context}

    def close(self):
        with self.lock:
            self.closed = True
        self.cancel()
        with self.lock:
            for record in self.tunnels.values():
                process = record['process']
                if process.poll() is None:
                    from hanni.dashboard.cluster import _stop_process
                    _stop_process(process)
            self.tunnels.clear()
        for record in list(self.owned.values()):
            try:
                # Only an exact manager nonce grants ownership of the remote PID.
                script = (f'python3 -c {shlex.quote("import os,pathlib,signal; p=" + str(record["pid"]) + "; token=b\"HANNI_COMPUTE_OWNER=" + record["nonce"] + "\"; env=pathlib.Path(f\"/proc/{p}/environ\").read_bytes().split(b\"\\0\"); token in env and os.kill(p,signal.SIGTERM)")}')
                subprocess.run(self._ssh(record['node'], self._address(record['node'])) + [script],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass  # A disconnected owned server is reported for manual reconciliation.
        self.owned.clear()
        self.auth.clear()
        self.addresses.clear()
        self.resource_cache.clear()
        self.identity_file_cache.clear()
