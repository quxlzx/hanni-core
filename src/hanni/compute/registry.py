"""Private deployment configuration and measured, durable inference receipts."""
from __future__ import annotations

from copy import deepcopy
import ipaddress
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from urllib.parse import urlsplit


class ComputeError(ValueError):
    pass


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ComputeError('Choose a registered compute identifier.')
    return value


def integer(value, minimum, maximum, field):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ComputeError(f'Invalid compute {field}.')
    return value


def loopback_url(value):
    try:
        parts = urlsplit(value)
        host = ipaddress.ip_address(parts.hostname)
        port = parts.port
    except (TypeError, ValueError):
        raise ComputeError('Inference URLs must use a literal loopback address.') from None
    if (parts.scheme != 'http' or not host.is_loopback or not port
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ('', '/', '/v1', '/v1/')):
        raise ComputeError('Inference URLs must use an authenticated local SSH tunnel or loopback server.')
    return value.rstrip('/').removesuffix('/v1')


def validate_deployment(raw):
    if not isinstance(raw, dict) or set(raw) - {'version', 'enabled', 'nodes', 'workers', 'policy'}:
        raise ComputeError('Invalid private compute deployment fields.')
    if raw.get('version') != 1 or type(raw.get('enabled', False)) is not bool:
        raise ComputeError('Unsupported compute deployment version.')
    nodes = raw.get('nodes', [])
    workers = raw.get('workers', [])
    if not isinstance(nodes, list) or len(nodes) > 32 or not isinstance(workers, list) or len(workers) > 32:
        raise ComputeError('Compute inventory exceeds its configured limit.')
    ids = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ComputeError('Invalid compute node.')
        key = identifier(node.get('id'))
        if key in ids:
            raise ComputeError('Duplicate compute node.')
        ids.add(key)
        for field in ('lan_ip', 'tailscale_ip'):
            if node.get(field) is not None:
                try:
                    address = ipaddress.ip_address(node[field])
                except ValueError:
                    raise ComputeError('Invalid private node address.') from None
                if not (address.is_private or address in ipaddress.ip_network('100.64.0.0/10')):
                    raise ComputeError('Compute node addresses must remain private.')
        username = node.get('username')
        if username is not None and (not isinstance(username, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}', username)):
            raise ComputeError('Invalid SSH account.')
    seen = set()
    for worker in workers:
        if not isinstance(worker, dict) or set(worker) - {
            'worker_id', 'node_id', 'label', 'gpu', 'model_id', 'protocol', 'enabled',
            'local_url', 'remote_port', 'concurrency', 'interactive_reserve', 'capabilities',
            'allowed_categories', 'context_configured', 'model_context_limit', 'startup', 'api_key_env', 'auth_config_file', 'identity_model_roots'}:
            raise ComputeError('Invalid inference worker fields.')
        key = identifier(worker.get('worker_id'))
        if key in seen or worker.get('node_id') not in ids | {'local'}:
            raise ComputeError('Duplicate worker or unknown node.')
        seen.add(key)
        if worker.get('protocol', 'openai') not in {'openai', 'llama_cpp', 'strata_openai'}:
            raise ComputeError('Unsupported inference protocol.')
        if type(worker.get('enabled', False)) is not bool:
            raise ComputeError('Worker enabled must be boolean.')
        integer(worker.get('concurrency', 1), 1, 4, 'concurrency')
        integer(worker.get('interactive_reserve', 0), 0, worker.get('concurrency', 1), 'interactive reserve')
        if worker.get('node_id') == 'local':
            loopback_url(worker.get('local_url'))
        else:
            integer(worker.get('remote_port'), 1, 65535, 'remote port')
        for field in ('context_configured', 'model_context_limit'):
            if worker.get(field) is not None:
                integer(worker[field], 1, 1048576, field)
        categories = worker.get('allowed_categories', [])
        if not isinstance(categories, list) or not set(categories) <= {'synthetic', 'project', 'conversation', 'memory', 'screen', 'sensitive'}:
            raise ComputeError('Unsupported context-sharing categories.')
        caps = worker.get('capabilities', ['analysis'])
        if not isinstance(caps, list) or not caps or not set(caps) <= {'analysis', 'structured_json'}:
            raise ComputeError('Only bounded model inference is a supported worker operation.')
        if worker.get('api_key_env') is not None and (not isinstance(worker['api_key_env'], str)
                or not re.fullmatch(r'HANNI_COMPUTE_[A-Z0-9_]{1,80}', worker['api_key_env'])):
            raise ComputeError('Authentication must reference a compute-specific environment variable.')
        if worker.get('auth_config_file') is not None and (worker['node_id'] == 'local'
                or not isinstance(worker['auth_config_file'], str) or not worker['auth_config_file'].startswith('/')
                or any(c in worker['auth_config_file'] for c in '\x00\n\r')):
            raise ComputeError('Authentication must reference a protected existing remote configuration.')
        roots = worker.get('identity_model_roots', [])
        if not isinstance(roots, list) or len(roots) > 4:
            raise ComputeError('Runtime identity requires bounded approved model directories.')
        from pathlib import PurePosixPath
        for root in roots:
            if (not isinstance(root, str) or not root.startswith('/') or any(char in root for char in '\x00\n\r')
                    or '..' in PurePosixPath(root).parts or len(PurePosixPath(root).parts) < 5):
                raise ComputeError('Runtime identity must use an explicit narrow existing model directory.')
    policy = raw.get('policy', {})
    if not isinstance(policy, dict) or set(policy) - {'max_queue', 'timeout_seconds', 'max_retries', 'fallback_local', 'workflow_categories'}:
        raise ComputeError('Invalid compute scheduling policy.')
    integer(policy.get('max_queue', 16), 1, 128, 'queue limit')
    integer(policy.get('timeout_seconds', 30), 1, 300, 'timeout')
    integer(policy.get('max_retries', 1), 0, 1, 'retry count')
    if type(policy.get('fallback_local', True)) is not bool:
        raise ComputeError('Invalid local fallback policy.')
    if policy.get('workflow_categories', ['project']) != ['project']:
        raise ComputeError('Workflow sources are classified as project context by the controller.')
    return deepcopy(raw)


class ComputeRegistry:
    def __init__(self, data_dir, *, clock=time.time):
        self.root = Path(data_dir).resolve() / 'compute' if data_dir is not None else None
        self.clock = clock
        self.lock = threading.RLock()
        self.config_error = None
        self.deployment = {'version': 1, 'enabled': False, 'nodes': [], 'workers': [], 'policy': {}}
        self.observations = {}
        self.active = {}
        self.db = None
        self.owned_jobs = set()
        self.reload()
        self._load_measurements()

    def _guard_root(self):
        if self.root is None:
            raise ComputeError('Protected compute storage is unavailable.')
        try:
            if self.root.is_symlink() or self.root.resolve() != self.root:
                raise ComputeError('Compute storage cannot escape the protected data directory.')
        except (OSError, RuntimeError):
            raise ComputeError('Protected compute storage cannot be safely resolved.') from None

    def _worker_identity(self, worker, *, allocation=True):
        fields = {name: worker.get(name) for name in ('worker_id', 'node_id', 'gpu', 'model_id', 'local_url',
                  'remote_port', 'context_configured', 'model_context_limit', 'protocol')}
        startup = worker.get('startup') or {}
        fields['runtime'] = {name: startup.get(name) for name in ('model_file', 'executable', 'gpu_device',
                             'context', 'cache_type_k', 'cache_type_v', 'installation_dir', 'config_file', 'python_executable')}
        if worker.get('node_id') != 'local':
            node = self.node(worker['node_id'])
            fields['source'] = {name: node.get(name) for name in ('id', 'lan_ip', 'tailscale_ip', 'username')}
        if worker.get('api_key_env') or worker.get('auth_config_file'):
            fields['authentication_source'] = {name: worker.get(name) for name in ('api_key_env', 'auth_config_file')}
        if worker.get('identity_model_roots'):
            fields['identity_model_roots'] = worker['identity_model_roots']
        if not allocation:
            fields.pop('context_configured', None)
            fields['runtime'].pop('context', None)
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()

    def prior_verified_context(self, key):
        """Prior-stage proof can authorize growth, never advertise new capacity."""
        worker = self.worker(key)
        if self.root is None:
            return 0
        self._guard_root()
        path = self.root / 'context-measurements.json'
        try:
            if path.is_symlink() or not path.exists():
                return 0
            proof = json.loads(path.read_text())['measurements'].get(key, {})
            verified = proof.get('max_context_verified')
            if (proof.get('stage_identity') == self._worker_identity(worker, allocation=False)
                    and type(verified) is int and proof.get('retrieval_passed') is True
                    and proof.get('loaded_model_id') == worker.get('model_id')):
                return verified
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return 0

    def _load_measurements(self):
        if self.root is None:
            return
        try:
            self._guard_root()
        except ComputeError:
            return
        path = self.root / 'context-measurements.json'
        try:
            if not path.exists() or path.is_symlink() or path.stat().st_size > 262144:
                return
            raw = json.loads(path.read_text(encoding='utf-8'))
            if raw.get('version') != 1:
                return
            for worker in self.workers():
                proof = raw.get('measurements', {}).get(worker['worker_id'], {})
                verified = proof.get('max_context_verified')
                if (proof.get('worker_identity') == self._worker_identity(worker) and type(verified) is int
                        and 0 < verified <= 131072 and proof.get('retrieval_passed') is True
                        and type(proof.get('observed_prompt_tokens')) is int
                        and .9 * verified <= proof['observed_prompt_tokens'] <= verified
                        and proof.get('loaded_model_id') == worker.get('model_id')):
                    self.observations.setdefault(worker['worker_id'], {}).update(
                        model_id=proof['loaded_model_id'], max_context_verified=verified,
                        context_verification=proof)
        except (OSError, ValueError, TypeError, AttributeError):
            return  # Malformed proof never enables a worker.

    def record_context_verified(self, key, *, target_tokens, prompt_tokens, model_id, prompt_sha256, response_sha256):
        with self.lock:
            worker = self.worker(key)
            integer(target_tokens, 1, 131072, 'verified context')
            if (type(prompt_tokens) is not int or not .9 * target_tokens <= prompt_tokens <= target_tokens
                    or not model_id or model_id != worker.get('model_id')):
                raise ComputeError('Context proof must match the measured model and near-limit token count.')
            if self.root is None:
                raise ComputeError('Protected context measurement storage is unavailable.')
            self._guard_root()
            path = self.root / 'context-measurements.json'
            temp = self.root / 'context-measurements.pending.json'
            if path.is_symlink() or temp.is_symlink():
                raise ComputeError('Context proof storage cannot be a symbolic link.')
            try:
                raw = json.loads(path.read_text()) if path.exists() else {'version': 1, 'measurements': {}}
            except (OSError, ValueError):
                raise ComputeError('Existing context proof storage is invalid and was preserved.') from None
            proof = {'worker_identity': self._worker_identity(worker), 'loaded_model_id': model_id,
                'stage_identity': self._worker_identity(worker, allocation=False),
                'max_context_verified': target_tokens, 'observed_prompt_tokens': prompt_tokens,
                'retrieval_passed': True, 'prompt_sha256': prompt_sha256, 'response_sha256': response_sha256,
                'verified_at': self.clock()}
            observed = self.observations.get(key, {})
            if observed.get('runtime_files_identity'):
                proof['runtime_binding'] = {'runtime_identity': observed.get('runtime_identity'),
                                            'runtime_files_identity': observed['runtime_files_identity']}
            previous = raw['measurements'].get(key)
            if previous and previous.get('worker_identity') == proof['worker_identity'] and previous.get('max_context_verified', 0) > target_tokens:
                proof = previous
            raw['measurements'][key] = proof
            self.root.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(raw, indent=2), encoding='utf-8')
            if os.name != 'nt':
                temp.chmod(0o600)
            temp.replace(path)
            self.observe(key, model_id=model_id, max_context_verified=proof['max_context_verified'], context_verification=proof)

    def _invalidate_measurement(self, key):
        if self.root is None:
            return
        self._guard_root()
        path = self.root / 'context-measurements.json'
        if not path.exists() or path.is_symlink():
            return
        try:
            raw = json.loads(path.read_text())
            if key not in raw.get('measurements', {}):
                return
            raw['measurements'].pop(key)
            temp = self.root / 'context-measurements.pending.json'
            if temp.is_symlink():
                raise ComputeError('Context proof storage cannot be a symbolic link.')
            temp.write_text(json.dumps(raw, indent=2), encoding='utf-8')
            if os.name != 'nt':
                temp.chmod(0o600)
            temp.replace(path)
        except (OSError, ValueError, TypeError):
            pass

    def reload(self):
        with self.lock:
            try:
                if self.root is not None:
                    self._guard_root()
            except ComputeError as exc:
                self.config_error = str(exc)
                self.deployment = {'version': 1, 'enabled': False, 'nodes': [], 'workers': [], 'policy': {}}
                self.observations.clear()
                return
            if self.root is None or not (self.root / 'deployment.json').exists():
                self.deployment = {'version': 1, 'enabled': False, 'nodes': [], 'workers': [], 'policy': {}}
                self.observations.clear()
                return
            path = self.root / 'deployment.json'
            try:
                if path.is_symlink() or path.resolve().parent != self.root:
                    raise ComputeError('Compute deployment must remain in the protected data directory.')
                if path.stat().st_size > 262144:
                    raise ComputeError('Compute deployment exceeds its limit.')
                previous = {worker['worker_id']: self._worker_identity(worker) for worker in self.workers()}
                self.deployment = validate_deployment(json.loads(path.read_text(encoding='utf-8-sig')))
                registered = {worker['worker_id'] for worker in self.workers()}
                for key in set(self.observations) - registered:
                    self.observations.pop(key, None)
                for worker in self.deployment.get('workers', []):
                    key = worker['worker_id']
                    if key in previous and previous[key] != self._worker_identity(worker):
                        # These are current source observations, not history.
                        # Durable proofs are retained but cannot bind this source.
                        self.observations[key] = {}
                    observed = self.observations.get(worker['worker_id'], {})
                    proof = observed.get('context_verification', {})
                    if proof and proof.get('worker_identity') != self._worker_identity(worker):
                        observed.pop('max_context_verified', None)
                        observed.pop('context_verification', None)
                self.config_error = None
            except (OSError, ValueError, TypeError) as exc:
                self.config_error = str(exc) if isinstance(exc, ComputeError) else 'Private compute deployment is unavailable.'
                self.deployment = {'version': 1, 'enabled': False, 'nodes': [], 'workers': [], 'policy': {}}
                self.observations.clear()

    @property
    def enabled(self):
        self.reload()
        self._load_measurements()
        return self.deployment['enabled'] and self.config_error is None

    def workers(self):
        return deepcopy(self.deployment.get('workers', []))

    def worker(self, key):
        identifier(key)
        for item in self.workers():
            if item['worker_id'] == key:
                return item
        raise ComputeError('Worker is not registered.')

    def node(self, key):
        for item in self.deployment.get('nodes', []):
            if item['id'] == key:
                return deepcopy(item)
        raise ComputeError('Compute node is not registered.')

    def observe(self, key, **values):
        with self.lock:
            self.worker(key)
            current = self.observations.setdefault(key, {})
            # Offline responses cannot discard the last bound runtime identity.
            # A future healthy runtime with a different fingerprint will fail
            # the adaptive registry's capability/performance identity checks.
            if values.get('runtime_identity') is None and current.get('runtime_identity'):
                values = dict(values, runtime_identity=current['runtime_identity'])
            previous_model = current.get('model_id') or current.get('context_verification', {}).get('loaded_model_id')
            if 'status' in values and 'last_heartbeat' in values:
                if values['status'] == 'healthy':
                    current['last_healthy_at'] = values['last_heartbeat']
                    current['consecutive_health_failures'] = 0
                elif values['status'] == 'unhealthy':
                    current['consecutive_health_failures'] = current.get('consecutive_health_failures', 0) + 1
            if (values.get('model_id') is not None and previous_model is not None
                    and values['model_id'] != previous_model
                    or values.get('context_reported') is not None and current.get('context_reported') is not None
                    and values['context_reported'] != current['context_reported']
                    or values.get('runtime_identity') is not None and current.get('runtime_identity') is not None
                    and values['runtime_identity'] != current['runtime_identity']
                    or values.get('runtime_files_identity') is not None and current.get('runtime_files_identity') is not None
                    and values['runtime_files_identity'] != current['runtime_files_identity']):
                current.pop('max_context_verified', None)
                current.pop('context_verification', None)
                self._invalidate_measurement(key)
            current.update(values)

    def _connect(self):
        if self.root is None:
            raise ComputeError('Compute storage is unavailable.')
        self._guard_root()
        if self.db is None:
            self.root.mkdir(parents=True, exist_ok=True)
            if os.name != 'nt':
                self.root.chmod(0o700)
            path = self.root / 'jobs.sqlite3'
            if path.is_symlink():
                raise ComputeError('Compute storage cannot be a symbolic link.')
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, payload TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS job_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, payload TEXT NOT NULL)')
            self.db.commit()
            if os.name != 'nt':
                path.chmod(0o600)
            # Opening a read-only dashboard projection never withdraws another
            # controller's live jobs. Recovery belongs to WorkflowStore's lease.
        return self.db

    def receipt(self, job):
        # Deliberately retains hashes/references and metrics, never prompts or output text.
        with self.lock:
            if set(job) - {'job_id', 'workflow_id', 'step_id', 'invocation_id', 'worker_id', 'model_id',
                           'state', 'created_at', 'updated_at', 'started_at', 'finished_at', 'timeout_seconds',
                           'attempt', 'input_sha256', 'output_sha256', 'output_ref', 'verification_status',
                           'selection_reason', 'latency_ms', 'queue_ms', 'tokens', 'performance', 'error', 'retry_safe'}:
                raise ComputeError('Unsupported compute receipt fields.')
            metrics = job.get('performance')
            if metrics is not None:
                import math
                if (not isinstance(metrics, dict) or set(metrics) - {'prompt_tps', 'generation_tps'}
                        or any(type(value) not in (int, float) or not math.isfinite(value)
                            or not 0 <= value <= 10**9 for value in metrics.values())):
                    raise ComputeError('Unsupported numeric compute performance observation.')
            db = self._connect()
            db.execute('INSERT INTO jobs VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                       (job['job_id'], job['workflow_id'], json.dumps(job, allow_nan=False)))
            db.execute('INSERT INTO job_events(job_id,payload) VALUES(?,?)',
                       (job['job_id'], json.dumps(job, allow_nan=False)))
            db.execute('DELETE FROM job_events WHERE job_id=? AND sequence NOT IN '
                       '(SELECT sequence FROM job_events WHERE job_id=? ORDER BY sequence DESC LIMIT 64)',
                       (job['job_id'], job['job_id']))
            # Bounded terminal receipt retention, never prune active jobs.
            for key, payload in list(db.execute('SELECT id,payload FROM jobs ORDER BY rowid DESC LIMIT -1 OFFSET 500')):
                if json.loads(payload)['state'] in {'VERIFIED', 'FAILED', 'CANCELLED', 'BLOCKED', 'LOST_CONNECTION'}:
                    db.execute('DELETE FROM job_events WHERE job_id=?', (key,))
                    db.execute('DELETE FROM jobs WHERE id=?', (key,))
            db.commit()
            self.owned_jobs.add(job['job_id'])

    def jobs(self, workflow_id=None, limit=100):
        with self.lock:
            if self.root is not None:
                self._guard_root()
            if self.root is None or not (self.root / 'jobs.sqlite3').exists():
                return []
            db = self._connect()
            rows = db.execute('SELECT payload FROM jobs' + (' WHERE workflow_id=?' if workflow_id else '') + ' ORDER BY rowid DESC LIMIT ?',
                              (workflow_id, limit) if workflow_id else (limit,))
            result = [json.loads(row[0]) for row in rows]
            for job in result:
                job['events'] = [json.loads(row[0]) for row in db.execute(
                    'SELECT payload FROM job_events WHERE job_id=? ORDER BY sequence', (job['job_id'],))]
            return result

    def reconcile_workflows(self, store, lease):
        """Only the authoritative current workflow lease reconciles crash state."""
        from hanni.workflows.types import WorkflowError
        store.assert_lease(lease)
        for job in self.jobs():
            if job['state'] not in {'QUEUED', 'ASSIGNED', 'RUNNING', 'COMPLETED', 'VERIFYING'}:
                continue
            try:
                history = store.history(job['workflow_id'])
            except WorkflowError:
                continue  # Standalone diagnostics have no original workflow.
            try:
                invocation = next((row for row in history['invocations'] if row['invocation_id'] == job['invocation_id']), None)
                if invocation is None:
                    continue  # Controlled standalone probes are not workflows.
                state = invocation['state']
                if state == 'dispatched':
                    continue  # A live current owner still holds authority.
                changes = None
                if state in {'abandoned', 'uncertain'}:
                    changes = {'state': 'LOST_CONNECTION', 'error': 'Original workflow recovery recorded an interrupted invocation; remote inference may still be running.'}
                elif state == 'finished':
                    step = next(row for row in store.steps(job['workflow_id']) if row['step_id'] == job['step_id'])
                    verified = step['status'] == 'verified' and (step.get('verification') or {}).get('status') == 'VERIFIED'
                    changes = {'state': 'VERIFIED' if verified else 'FAILED',
                               'verification_status': 'VERIFIED' if verified else 'UNVERIFIED'}
                if changes:
                    store.assert_lease(lease)
                    job.pop('events', None)
                    job.update(changes, updated_at=self.clock())
                    self.receipt(job)
            except (KeyError, StopIteration):
                continue

    def snapshot(self):
        with self.lock:
            enabled = self.enabled
            now = self.clock()
            rows = []
            for config in self.workers():
                key = config['worker_id']
                observed = self.observations.get(key, {})
                stamp = observed.get('last_heartbeat')
                fresh = type(stamp) in (int, float) and math.isfinite(stamp) and 0 <= now - stamp <= 30
                rows.append({
                    'worker_id': key, 'node_id': config['node_id'], 'label': config.get('label', key),
                    'gpu': config.get('gpu'), 'model_id': observed.get('model_id'), 'configured_model': config.get('model_id'),
                    'protocol': config.get('protocol', 'openai'), 'enabled': config.get('enabled', False),
                    'capabilities': config.get('capabilities', ['analysis']),
                    'allowed_categories': config.get('allowed_categories', []),
                    'context_configured': config.get('context_configured'),
                    'context_reported': observed.get('context_reported'),
                    'max_context_verified': observed.get('max_context_verified'),
                    'status': observed.get('status', 'unknown') if fresh else 'unknown',
                    'last_heartbeat': stamp, 'current_jobs': self.active.get(key, 0),
                    'last_healthy_at': observed.get('last_healthy_at'),
                    'consecutive_health_failures': observed.get('consecutive_health_failures', 0),
                    'queue_depth': observed.get('queue_depth'), 'vram_free_bytes': observed.get('vram_free_bytes'),
                    'ram_available_bytes': observed.get('ram_available_bytes'),
                    'latency_ms': observed.get('latency_ms'), 'throughput_tps': observed.get('throughput_tps'),
                    'health_latency_ms': observed.get('health_latency_ms'),
                    'node_hardware': observed.get('node_hardware'), 'gpu_measurement': observed.get('gpu_measurement'),
                    'resource_sampled_at': observed.get('resource_sampled_at'),
                    'endpoint_contract': deepcopy(observed.get('endpoint_contract')),
                    'concurrency': config.get('concurrency', 1), 'interactive_reserve': config.get('interactive_reserve', 0),
                    'error': observed.get('error'),
                    'start_supported': bool(config.get('startup', {}).get('authorized', False)),
                })
            return {'available': self.root is not None, 'enabled': enabled, 'reason': self.config_error,
                    'sampled_at': now, 'workers': rows, 'jobs': self.jobs(), 'policy': deepcopy(self.deployment.get('policy', {}))}

    def configure_worker(self, key, *, enabled=None, concurrency=None):
        with self.lock:
            worker = self.worker(key)
            if enabled is not None:
                if type(enabled) is not bool:
                    raise ComputeError('Worker enabled must be boolean.')
                worker['enabled'] = enabled
            if concurrency is not None:
                integer(concurrency, 1, 4, 'concurrency')
                if concurrency < self.active.get(key, 0) or concurrency < worker.get('interactive_reserve', 0):
                    raise ComputeError('Concurrency cannot be lower than current reservations.')
                worker['concurrency'] = concurrency
            candidate = deepcopy(self.deployment)
            candidate['workers'] = [worker if row['worker_id'] == key else row for row in candidate['workers']]
            validate_deployment(candidate)
            if self.root is None:
                raise ComputeError('Protected compute configuration is unavailable.')
            self._guard_root()
            path = self.root / 'deployment.json'
            temp = self.root / 'deployment.pending.json'
            if path.is_symlink() or temp.is_symlink():
                raise ComputeError('Protected compute configuration cannot be symbolic links.')
            temp.write_text(json.dumps(candidate, indent=2), encoding='utf-8')
            if os.name != 'nt':
                temp.chmod(0o600)
            temp.replace(path)
            self.deployment = candidate
            return self.snapshot()

    def close(self):
        with self.lock:
            if self.db is not None:
                # Releasing this writer's transport is an actual lost connection,
                # not a read-side guess about another running controller.
                for key in self.owned_jobs:
                    row = self.db.execute('SELECT payload FROM jobs WHERE id=?', (key,)).fetchone()
                    if row:
                        payload = json.loads(row[0])
                        if payload['state'] in {'QUEUED', 'ASSIGNED', 'RUNNING', 'COMPLETED', 'VERIFYING'}:
                            payload.update(state='LOST_CONNECTION', updated_at=self.clock(),
                                error='Owning dispatcher closed before verification; remote inference may still be running.')
                            self.db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), key))
                            self.db.execute('INSERT INTO job_events(job_id,payload) VALUES(?,?)', (key, json.dumps(payload)))
                self.db.commit()
                self.db.close()
                self.db = None
                self.owned_jobs.clear()
