"""Measured model placement alongside the original controller and compute queue.

No prompt, memory, credential or model response is retained in routing storage.
Capability and context proofs come from bounded engineering evaluations, not
server claims, model confidence or parameter counts. Remote inference continues
to use the original ComputeScheduler; tools continue to use the original host.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
import time
from uuid import uuid4

from hanni.compute import ComputeError
from hanni.models.client import LlamaCppClient, ModelClientError, ModelProtocolError, ModelIdentityError
from hanni.models.performance import recent_performance

POLICIES = ('balanced', 'fast', 'quality', 'manual', 'resident_first', 'measured_work')
CATEGORIES = frozenset({'conversation', 'tool_selection', 'computer_diagnostics', 'planning',
                        'coding', 'analysis', 'long_context', 'memory', 'structured_output'})
PRIVACY = frozenset({'synthetic', 'project', 'conversation', 'memory', 'screen', 'sensitive'})
CAPABILITIES = frozenset({'text', 'structured_json', 'tool_calling', 'vision'})
RESOURCE_FIELDS = ('ram_available_bytes', 'vram_free_bytes', 'current_requests', 'queue_depth')
_scope = ContextVar('hanni_model_request', default=None)
_engines = {}
_current_lock = threading.RLock()


class ModelSelectionError(ModelClientError):
    pass


class _ModelAdmissionWithdrawn(ModelSelectionError):
    """A withdrawn controller boundary is not a failed inference endpoint."""


class _BoundedInferenceClient(LlamaCppClient):
    """Local callbacks inherit the same output budget as endpoint admission."""
    def _bounded(self, options):
        budget = options.get('max_tokens')
        if budget is None:
            options['max_tokens'] = self.spec.max_tokens
        elif type(budget) is not int or not 1 <= budget <= self.spec.max_tokens:
            raise ModelSelectionError('A local callback exceeded its admitted output budget.')
        return options

    def stream_chat(self, messages, **options):
        return super().stream_chat(messages, **self._bounded(options))

    def complete_with_tools(self, messages, *, tools, **options):
        return super().complete_with_tools(messages, tools=tools, **self._bounded(options))

    def chat(self, messages, **options):
        if getattr(self, '_inference_usage', None) is not None and options.get('usage') is None:
            options['usage'] = self._inference_usage
        return super().chat(messages, **self._bounded(options))


def install(engine):
    with _current_lock:
        if engine is None:
            _engines.clear()
        else:
            key = str(engine.data_dir).casefold()
            existing = _engines.get(key)
            if existing is not None and existing is not engine and not existing.closed:
                raise ModelSelectionError('This data directory already has an active routing engine.')
            _engines[key] = engine


def uninstall(engine):
    with _current_lock:
        key = str(engine.data_dir).casefold()
        if _engines.get(key) is engine:
            _engines.pop(key)


def current(config=None):
    with _current_lock:
        if config is None:
            values = [engine for engine in _engines.values() if not engine.closed]
            return values[0] if len(values) == 1 else None
        engine = _engines.get(str(Path(config.paths.data_dir).resolve()).casefold())
        if engine is None or engine.closed:
            return None
        return engine


@dataclass(frozen=True)
class ModelRequest:
    task_category: str = 'conversation'
    complexity: str = 'normal'
    context_tokens: int = 0
    capabilities: frozenset = frozenset({'text'})
    privacy_categories: frozenset = frozenset({'conversation', 'sensitive'})
    local_only: bool = False
    output_tokens: int = 768
    allow_legacy_default: bool = False
    schema_tokens: int = 0
    response_format: str | None = None
    tool_calling_format: str | None = None
    interactive: bool = True

    def __post_init__(self):
        if (self.task_category not in CATEGORIES or self.complexity not in {'simple', 'normal', 'complex'}
                or type(self.context_tokens) is not int or not 0 <= self.context_tokens <= 1048576
                or type(self.output_tokens) is not int or not 1 <= self.output_tokens <= 8192
                or type(self.schema_tokens) is not int or not 0 <= self.schema_tokens <= 262144
                or self.response_format not in {None, 'json_object', 'json_schema'}
                or self.tool_calling_format not in {None, 'openai_function'}
                or not self.capabilities or not set(self.capabilities) <= CAPABILITIES
                or not self.privacy_categories or not set(self.privacy_categories) <= PRIVACY
                or type(self.local_only) is not bool or type(self.allow_legacy_default) is not bool
                or type(self.interactive) is not bool):
            raise ModelSelectionError('Invalid trusted model request requirements.')


@contextmanager
def model_request_scope(**requirements):
    """Controller-derived requirements; these never come from model text."""
    request = ModelRequest(**requirements)
    token = _scope.set(request)
    try:
        yield request
    finally:
        _scope.reset(token)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, default=str).encode()).hexdigest()


def _number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def _bounded_text(value, field, maximum=512):
    if not isinstance(value, str) or not value or len(value) > maximum or any(c in value for c in '\x00\n\r'):
        raise ModelSelectionError(f'Invalid measured {field}.')
    # Evaluation identifiers must describe a synthetic environment, never secrets.
    if re.search(r'(?i)(bearer\s|api[_-]?key\s*[:=]|password\s*[:=])', value):
        raise ModelSelectionError('Credentials are forbidden in routing evidence.')
    return value


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ModelSelectionError('Evidence must reference a SHA256 digest.')
    return value


def _lower_bound(successes, count):
    if not count:
        return None
    # Wilson 95% lower bound keeps small samples from looking authoritative.
    z = 1.96
    p = successes / count
    return (p + z*z/(2*count) - z * math.sqrt(p*(1-p)/count + z*z/(4*count*count))) / (1 + z*z/count)


class AdaptiveModelEngine:
    def __init__(self, config, *, compute_scheduler=None, data_dir=None, clock=time.time,
                 monotonic=time.monotonic, local_probe=None):
        self.config = config
        self.data_dir = Path(data_dir or config.paths.data_dir).resolve()
        self.root = self.data_dir / 'model-routing'
        self.compute = compute_scheduler
        self.clock, self.monotonic = clock, monotonic
        self.local_probe = local_probe
        self.lock = threading.RLock()
        self.observations = {}
        self.active = {}
        self.closed = False
        self.controller_attached = False
        self.halt = threading.Event()
        self.refresh_wake = threading.Event()
        self._file_hash_cache = {}
        self.thread = None
        self.db = None
        self.last_error = None
        self._collaboration = None
        self._profile_revision = None
        self._profile_cache = {}
        self._placement_history = {}
        self._connect()
        routing = config.hanni.model_routing
        with self.lock:
            db = self._connect()
            settings = self._settings()
            if settings.get('config_policy', 'balanced') != routing.policy:
                settings.update(policy=routing.policy, manual_endpoint_id=None)
            settings.update(config_policy=routing.policy, max_fallbacks=routing.max_fallbacks,
                max_queue_seconds=routing.max_queue_seconds, minimum_samples=routing.minimum_samples,
                minimum_accuracy_lower_bound=routing.minimum_accuracy_lower_bound)
            db.execute('UPDATE settings SET payload=? WHERE id=1', (json.dumps(settings),)); db.commit()

    def _guard(self):
        if self.root.is_symlink() or self.root.resolve() != self.root:
            raise ModelSelectionError('Routing storage must remain in the protected data directory.')
        for suffix in ('', '-wal', '-shm', '-journal'):
            path = self.root / ('profiles.sqlite3' + suffix)
            if path.is_symlink() or path.resolve().parent != self.root:
                raise ModelSelectionError('Routing storage contains an unsafe link.')

    def _connect(self):
        with self.lock:
            if self.closed:
                raise ModelSelectionError('Model routing is closed.')
            self._guard()
            if self.db is None:
                self.root.mkdir(parents=True, exist_ok=True)
                self.db = sqlite3.connect(self.root / 'profiles.sqlite3', check_same_thread=False)
                self.db.execute('PRAGMA busy_timeout=5000')
                self.db.executescript('''
                    CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS proofs (endpoint TEXT PRIMARY KEY, identity TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS measurements (id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, identity TEXT NOT NULL, category TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, created REAL NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS identity_sources (endpoint TEXT PRIMARY KEY, deployment_identity TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE INDEX IF NOT EXISTS idx_measurements_endpoint_identity ON measurements(endpoint,identity);
                    CREATE TEMP TABLE profile_cache_generation(value INTEGER NOT NULL);
                    INSERT INTO profile_cache_generation VALUES(0);
                    CREATE TEMP TRIGGER profile_cache_insert AFTER INSERT ON main.measurements
                      BEGIN UPDATE profile_cache_generation SET value=value+1; END;
                    CREATE TEMP TRIGGER profile_cache_update AFTER UPDATE ON main.measurements
                      BEGIN UPDATE profile_cache_generation SET value=value+1; END;
                    CREATE TEMP TRIGGER profile_cache_delete AFTER DELETE ON main.measurements
                      BEGIN UPDATE profile_cache_generation SET value=value+1; END;
                ''')
                self.db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (json.dumps({
                    'policy': 'balanced', 'manual_endpoint_id': None, 'max_fallbacks': 2,
                    'max_queue_seconds': 5, 'minimum_samples': 20, 'minimum_accuracy_lower_bound': .7}),))
                self.db.commit()
            return self.db

    def _settings(self):
        with self.lock:
            return json.loads(self._connect().execute('SELECT payload FROM settings WHERE id=1').fetchone()[0])

    def configure(self, *, policy, manual_endpoint_id=None):
        if policy not in POLICIES:
            raise ModelSelectionError('Choose a supported routing policy.')
        if policy == 'manual' and manual_endpoint_id not in {row['endpoint_id'] for row in self._inventory()}:
            raise ModelSelectionError('Manual override must reference a configured endpoint.')
        if policy != 'manual' and manual_endpoint_id is not None:
            raise ModelSelectionError('A manual endpoint requires the manual policy.')
        with self.lock:
            settings = self._settings()
            settings.update(policy=policy, manual_endpoint_id=manual_endpoint_id)
            db = self._connect()
            db.execute('UPDATE settings SET payload=? WHERE id=1', (json.dumps(settings),))
            db.commit()
        return self.snapshot()

    def _inventory(self):
        rows = []
        for spec in self.config.models.models:
            key = 'local:' + spec.id
            identity = _digest({'spec': {field: getattr(spec, field) for field in (
                'id', 'backend', 'model_file', 'api_model', 'endpoint', 'context_length', 'parallel',
                'kv_key_type', 'kv_value_type', 'gpu_layers', 'gpu_selection', 'gpu_preference',
                'thinking_enabled', 'jinja_enabled')}, 'runtime': self.observations.get(key, {}).get('runtime_identity')})
            rows.append({'endpoint_id': key, 'label': spec.id, 'local': True, 'enabled': True,
                'model_id': self.observations.get(key, {}).get('model_id'), 'configured_model': spec.api_model,
                'backend': spec.backend, 'identity': identity, 'context_configured': spec.context_length,
                'allowed_categories': sorted(PRIVACY), 'configured_capabilities': sorted(CAPABILITIES),
                'configured_ram_budget_bytes': spec.ram_budget_mb * 1024**2,
                'configured_vram_budget_bytes': spec.vram_budget_mb * 1024**2,
                'ram_requirement_bytes': None, 'vram_requirement_bytes': None,
                'concurrency': spec.parallel, 'legacy_default': spec.id == self.config.models.supervisor.id,
                'spec': spec})
        if self.compute is not None:
            self.compute.registry.reload()
            self.compute.registry._load_measurements()
            for worker in self.compute.registry.workers():
                key = 'worker:' + worker['worker_id']
                observed = self.compute.registry.observations.get(worker['worker_id'], {})
                rows.append({'endpoint_id': key, 'label': worker.get('label', worker['worker_id']),
                    'local': worker['node_id'] == 'local',
                    'enabled': self.compute.registry.enabled and worker.get('enabled', False),
                    'model_id': observed.get('model_id'), 'configured_model': worker.get('model_id'),
                    'backend': worker.get('protocol', 'openai'),
                    'identity': _digest({'deployment': self.compute.registry._worker_identity(worker),
                        'runtime': observed.get('runtime_identity'), 'files': observed.get('runtime_files_identity')}),
                    'context_configured': worker.get('context_configured'),
                    'allowed_categories': worker.get('allowed_categories', []),
                    'configured_capabilities': ['text'] + (['structured_json'] if 'structured_json' in worker.get('capabilities', []) else []),
                    'ram_requirement_bytes': None, 'vram_requirement_bytes': None,
                    'concurrency': worker.get('concurrency', 1),
                    'interactive_reserve': worker.get('interactive_reserve', 0),
                    'legacy_default': False, 'worker': worker})
        return rows

    def endpoint_identity(self, endpoint_id):
        row = next((row for row in self._inventory() if row['endpoint_id'] == endpoint_id), None)
        if row is None:
            raise ModelSelectionError('Model endpoint is not configured.')
        return row['identity']

    def register_identity_files(self, endpoint_id, *, model_files, backend_files, evidence_sha256, environment):
        """Engineering-only existing Strata installation identity, no OS setter."""
        if self.compute is None or not endpoint_id.startswith('worker:'):
            raise ModelSelectionError('Identity file registration requires a configured inference worker.')
        worker = self.compute.registry.worker(endpoint_id.removeprefix('worker:'))
        startup = worker.get('startup') or {}
        installation = startup.get('installation_dir')
        if worker['node_id'] == 'local' or not isinstance(installation, str) or not installation.startswith('/'):
            raise ModelSelectionError('Identity files must belong to an existing configured remote installation.')
        from pathlib import PurePosixPath
        root = PurePosixPath(installation)
        approved_models = [PurePosixPath(value) for value in worker.get('identity_model_roots', [])]
        for values, model in ((model_files, True), (backend_files, False)):
            if not isinstance(values, list) or not 1 <= len(values) <= 64:
                raise ModelSelectionError('Choose a bounded explicit existing identity file list.')
            for value in values:
                if not isinstance(value, str) or any(char in value for char in '\x00\n\r'):
                    raise ModelSelectionError('Invalid approved installation file.')
                path = PurePosixPath(value)
                allowed_roots = [root] + approved_models if model else [root]
                if '..' in path.parts or not path.is_absolute() or not any(allowed in path.parents for allowed in allowed_roots):
                    raise ModelSelectionError('Identity file is outside the configured installation.')
                if model and path.suffix.lower() != '.gguf':
                    raise ModelSelectionError('Model identity files must be actual GGUF files.')
                if not model and path.suffix.lower() not in {'.py', '.so', '.bin'} and path.name not in {'strata', 'llama-server'}:
                    raise ModelSelectionError('Backend identity must reference an existing installation program.')
        _sha(evidence_sha256); _bounded_text(environment, 'environment')
        payload = {'model_files': model_files, 'backend_files': backend_files,
                   'evidence_sha256': evidence_sha256, 'environment': environment}
        with self.lock:
            db = self._connect()
            db.execute('INSERT OR REPLACE INTO identity_sources VALUES(?,?,?)',
                (endpoint_id, self.compute.registry._worker_identity(worker), json.dumps(payload)))
            db.commit()
        self._sync_identity_sources()

    def _sync_identity_sources(self):
        if self.compute is None or not hasattr(self.compute.transport, 'identity_sources'): return
        with self.lock:
            sources = self._connect().execute('SELECT endpoint,deployment_identity,payload FROM identity_sources').fetchall()
        registered = {}
        for endpoint, identity, payload in sources:
            try:
                worker = self.compute.registry.worker(endpoint.removeprefix('worker:'))
                if identity == self.compute.registry._worker_identity(worker):
                    registered[worker['worker_id']] = json.loads(payload)
            except ComputeError:
                pass
        self.compute.transport.identity_sources = registered

    def record_capability_evidence(self, endpoint_id, *, identity, capabilities, evidence_sha256,
                                   environment, context_tokens=None, observed_prompt_tokens=None,
                                   retrieval_passed=False, metadata=None):
        if identity != self.endpoint_identity(endpoint_id):
            raise ModelSelectionError('Capability evidence does not match the current model/runtime allocation.')
        if not capabilities or not set(capabilities) <= CAPABILITIES:
            raise ModelSelectionError('Unsupported model capability evidence.')
        _sha(evidence_sha256)
        _bounded_text(environment, 'environment')
        metadata = metadata or {}
        if (not isinstance(metadata, dict) or set(metadata) - {'architecture', 'quantization', 'tool_calling_formats',
                'structured_output_formats', 'vision_input_formats', 'ram_requirement_bytes', 'vram_requirement_bytes'}):
            raise ModelSelectionError('Unsupported measured model metadata.')
        for field in ('architecture', 'quantization'):
            if field in metadata: _bounded_text(metadata[field], field, 128)
        for field, allowed in (('tool_calling_formats', {'openai_function'}),
                               ('structured_output_formats', {'json_object', 'json_schema'}),
                               ('vision_input_formats', {'openai_image_url'})):
            if field in metadata and (not isinstance(metadata[field], list) or not set(metadata[field]) <= allowed):
                raise ModelSelectionError('Unsupported measured model format.')
        for field in ('ram_requirement_bytes', 'vram_requirement_bytes'):
            if field in metadata and (type(metadata[field]) is not int or not 0 <= metadata[field] <= 2**50):
                raise ModelSelectionError('Invalid measured resource requirement.')
        if context_tokens is not None and (type(context_tokens) is not int or not 1 <= context_tokens <= 131072
                or type(observed_prompt_tokens) is not int or not .9 * context_tokens <= observed_prompt_tokens <= context_tokens
                or retrieval_passed is not True):
            raise ModelSelectionError('Context capability requires actual near-limit token accounting and exact retrieval.')
        with self.lock:
            db = self._connect()
            prior = db.execute('SELECT identity,payload FROM proofs WHERE endpoint=?', (endpoint_id,)).fetchone()
            proof = json.loads(prior[1]) if prior and prior[0] == identity else {'capabilities': [], 'max_context_verified': None, 'evidence': []}
            proof['capabilities'] = sorted(set(proof['capabilities']) | set(capabilities))
            proof['metadata'] = dict(proof.get('metadata', {}), **metadata)
            if context_tokens is not None:
                proof['max_context_verified'] = max(context_tokens, proof['max_context_verified'] or 0)
            proof['evidence'] = (proof['evidence'] + [{'sha256': evidence_sha256, 'environment': environment,
                'created_at': self.clock(), 'capabilities': sorted(capabilities), 'context_tokens': context_tokens}])[-32:]
            db.execute('INSERT OR REPLACE INTO proofs VALUES(?,?,?)', (endpoint_id, identity, json.dumps(proof)))
            db.commit()

    def record_evaluation(self, endpoint_id, *, identity, task_category, correct, verified_success,
                          latency_ms, evidence_sha256, environment, generation_tps=None,
                          prompt_tps=None, queue_ms=0, error=False, evaluation_id=None,
                          resource_observations=None, ttft_ms=None):
        if identity != self.endpoint_identity(endpoint_id) or task_category not in CATEGORIES:
            raise ModelSelectionError('Evaluation identity or task category does not match this endpoint.')
        if (correct is not None and type(correct) is not bool or verified_success is not None and type(verified_success) is not bool or type(error) is not bool):
            raise ModelSelectionError('Evaluation outcomes must be externally measured booleans or unknown.')
        if any(not _number(value) for value in (latency_ms, queue_ms)) or any(value is not None and not _number(value) for value in (generation_tps, prompt_tps)):
            raise ModelSelectionError('Evaluation timing must be finite and nonnegative.')
        if ttft_ms is not None and (not _number(ttft_ms) or ttft_ms > 86400000):
            raise ModelSelectionError('First-content timing must be finite, nonnegative and bounded.')
        _sha(evidence_sha256)
        _bounded_text(environment, 'environment')
        resources = {field: None for field in (*RESOURCE_FIELDS, 'sampled_at')}
        if resource_observations is not None:
            if not isinstance(resource_observations, Mapping) or set(resource_observations) - set(resources):
                raise ModelSelectionError('Unsupported measured resource observation.')
            resources.update(resource_observations)
        for field in RESOURCE_FIELDS:
            value = resources[field]
            limit = 2**50 if field.endswith('_bytes') else 1000000
            if value is not None and (type(value) is not int or not 0 <= value <= limit):
                raise ModelSelectionError('Resource observations must be bounded nonnegative integers or unknown.')
        if resources['sampled_at'] is not None and (not _number(resources['sampled_at']) or resources['sampled_at'] > 10**12):
            raise ModelSelectionError('Invalid measured resource observation timestamp.')
        evaluation_id = evaluation_id or uuid4().hex
        _bounded_text(evaluation_id, 'evaluation identifier', 128)
        payload = {'correct': correct, 'verified_success': verified_success, 'latency_ms': latency_ms,
            'queue_ms': queue_ms, 'generation_tps': generation_tps, 'prompt_tps': prompt_tps,
            'error': error, 'evidence_sha256': evidence_sha256, 'environment': environment, 'created_at': self.clock()}
        if resource_observations is not None:
            payload['resource_observations'] = resources
        if ttft_ms is not None:
            payload['ttft_ms'] = ttft_ms
        with self.lock:
            db = self._connect()
            existing = db.execute('SELECT endpoint,identity,category,payload FROM measurements WHERE id=?', (evaluation_id,)).fetchone()
            if existing:
                old = json.loads(existing[3]); old.pop('created_at', None)
                expected = dict(payload); expected.pop('created_at', None)
                if tuple(existing[:3]) != (endpoint_id, identity, task_category) or old != expected:
                    raise ModelSelectionError('Evaluation identifier already binds different evidence.')
                return
            db.execute('INSERT INTO measurements VALUES(?,?,?,?,?)', (evaluation_id, endpoint_id, identity, task_category, json.dumps(payload)))
            db.execute('DELETE FROM measurements WHERE rowid NOT IN (SELECT rowid FROM measurements ORDER BY rowid DESC LIMIT 5000)')
            db.commit()

    def _profile_entry(self, endpoint_id, identity):
        with self.lock:
            db = self._connect()
            minimum_samples = self._settings()['minimum_samples']
            revision = (db.execute('PRAGMA data_version').fetchone()[0],
                        db.execute('SELECT value FROM profile_cache_generation').fetchone()[0], minimum_samples)
            if revision != self._profile_revision:
                self._profile_cache.clear()
                self._profile_revision = revision
            key = (endpoint_id, identity)
            cacheable = not db.in_transaction
            if not cacheable:
                # TEMP trigger counters participate in rollback. Never keep an
                # uncommitted aggregate that could later share its generation.
                self._profile_cache.clear()
            if cacheable and key in self._profile_cache:
                return self._profile_cache[key]
            rows = db.execute('SELECT category,payload FROM measurements WHERE endpoint=? AND identity=? ORDER BY rowid',
                              key).fetchall()
            entry = self._aggregate_profiles(rows, minimum_samples)
            if not cacheable:
                return entry
            if len(self._profile_cache) >= 8:
                self._profile_cache.pop(next(iter(self._profile_cache)))
            self._profile_cache[key] = entry
            return entry

    def _profiles(self, endpoint_id, identity):
        # Only immutable numeric evidence is cached. Eligibility, authorization,
        # health, capabilities and endpoint identities are always rebuilt.
        return deepcopy(self._profile_entry(endpoint_id, identity)['profiles'])

    def _performance(self, endpoint_id, identity, category=None, *, window_seconds=3600):
        entry = self._profile_entry(endpoint_id, identity)
        samples = entry['samples'].get(category, []) if category else [
            row for values in entry['samples'].values() for row in values]
        return recent_performance(samples, self.clock(), window_seconds=window_seconds)

    @staticmethod
    def _aggregate_profiles(rows, minimum_samples):
        grouped = {}
        for category, payload in rows:
            grouped.setdefault(category, []).append(json.loads(payload))
        result = {}
        for category, samples in grouped.items():
            known = [row for row in samples if row['correct'] is not None]
            successes = sum(row['correct'] is True for row in known)
            def mean(field):
                values = [row[field] for row in samples if row[field] is not None]
                return sum(values) / len(values) if values else None
            resources = {}
            for field in RESOURCE_FIELDS:
                values = [row.get('resource_observations', {}).get(field) for row in samples]
                values = [value for value in values if value is not None]
                resources[field] = {'sample_count': len(values), 'mean': sum(values) / len(values) if values else None,
                    'min': min(values) if values else None, 'max': max(values) if values else None}
            result[category] = {'sample_count': len(samples), 'correctness_sample_count': len(known),
                'correct_count': successes, 'verified_success_count': sum(row['verified_success'] is True for row in samples),
                'error_count': sum(row['error'] for row in samples), 'mean_latency_ms': mean('latency_ms'),
                'mean_queue_ms': mean('queue_ms'), 'mean_generation_tps': mean('generation_tps'), 'mean_prompt_tps': mean('prompt_tps'),
                'accuracy': successes / len(known) if known else None, 'accuracy_lower_bound': _lower_bound(successes, len(known)),
                'evaluation_environment': sorted({row['environment'] for row in samples}),
                'resource_sample_count': sum(any(row.get('resource_observations', {}).get(field) is not None for field in RESOURCE_FIELDS) for row in samples),
                'resource_observations': resources,
                'confidence': 'measured' if len(known) >= minimum_samples else 'insufficient'}
        return {'profiles': result, 'samples': grouped}

    def _resource_observations(self, row):
        # Admission snapshots measure headroom/load, not per-process consumption
        # or peak requirements. Unknown measurements remain unknown.
        result = {}
        for field in RESOURCE_FIELDS:
            value = row.get(field)
            limit = 2**50 if field.endswith('_bytes') else 1000000
            result[field] = value if type(value) is int and 0 <= value <= limit else None
        stamp = row.get('last_heartbeat')
        result['sampled_at'] = stamp if _number(stamp) and stamp <= 10**12 else None
        return result

    def _rows(self):
        now = self.clock()
        result = []
        for row in self._inventory():
            key = row['endpoint_id']
            observed = (self.compute.registry.observations.get(row['worker']['worker_id'], {})
                        if 'worker' in row else self.observations.get(key, {}))
            stamp = observed.get('last_heartbeat')
            fresh = _number(stamp) and 0 <= now - stamp <= 30
            health = observed.get('status', 'unknown') if fresh else 'unknown'
            with self.lock:
                entry = self._connect().execute('SELECT identity,payload FROM proofs WHERE endpoint=?', (key,)).fetchone()
            proof = json.loads(entry[1]) if entry and entry[0] == row['identity'] else {}
            verified = proof.get('max_context_verified')
            prior_verified = None
            if 'worker' in row:
                durable = observed.get('context_verification') or {}
                if durable.get('worker_identity') == self.compute.registry._worker_identity(row['worker']):
                    prior_verified = durable.get('max_context_verified')
                    binding = durable.get('runtime_binding')
                    if binding and binding == {'runtime_identity': observed.get('runtime_identity'),
                                               'runtime_files_identity': observed.get('runtime_files_identity')}:
                        verified = max(verified or 0, prior_verified or 0) or None
            # Configured/reported allocation is an upper bound, never a proof.
            bounds = [value for value in (verified, row['context_configured'], observed.get('context_reported')) if type(value) is int and value > 0]
            verified = min(bounds) if verified and bounds else None
            caps = sorted(set(proof.get('capabilities', [])) & set(row['configured_capabilities']))
            row = dict(row, health=health, last_heartbeat=stamp, context_reported=observed.get('context_reported'),
                max_context_verified=verified, capabilities=caps,
                previous_max_context_verified=prior_verified,
                unverified_capabilities=sorted(set(row['configured_capabilities']) - set(caps)),
                ram_available_bytes=observed.get('ram_available_bytes'), vram_free_bytes=observed.get('vram_free_bytes'),
                current_requests=self.active.get(key, 0) + (self.compute.registry.active.get(row['worker']['worker_id'], 0) if 'worker' in row else 0),
                queue_depth=observed.get('queue_depth'), profiles=self._profiles(key, row['identity']), blocked_reasons=[])
            metadata = proof.get('metadata', {})
            for field in ('architecture', 'quantization', 'tool_calling_formats', 'structured_output_formats',
                          'vision_input_formats', 'ram_requirement_bytes', 'vram_requirement_bytes'):
                if field in metadata: row[field] = metadata[field]
            row.setdefault('tool_calling_formats', [])
            row.setdefault('structured_output_formats', [])
            row.setdefault('vision_input_formats', [])
            if not row['enabled']: row['blocked_reasons'].append('disabled')
            if health != 'healthy': row['blocked_reasons'].append('endpoint_not_healthy')
            if not verified: row['blocked_reasons'].append('context_not_verified')
            result.append(row)
        return result

    def _probe_local(self, row):
        if self.local_probe:
            return self.local_probe(row)
        from hanni.compute.transport import InferenceTransport
        from hanni.compute.registry import ComputeRegistry
        # The stateless loopback request uses the same redirect/size limits as
        # remote inference; it neither creates nor starts a model manager.
        registry = self.compute.registry if self.compute is not None else ComputeRegistry(None)
        transport = self.compute.transport if self.compute is not None else InferenceTransport(registry)
        spec = row['spec']
        worker = {'worker_id': spec.id, 'node_id': 'local', 'local_url': spec.endpoint,
                  'model_id': spec.api_model, 'protocol': 'llama_cpp'}
        try:
            observation = transport.health(worker)
            if observation['status'] == 'healthy':
                try:
                    props = transport.request(worker, 'GET', '/props')
                except ComputeError:
                    props = {}
                metadata = props.get('model_meta') or {}
                loaded_path = props.get('model_path')
                if isinstance(loaded_path, str) and loaded_path.replace('\\', '/').rsplit('/', 1)[-1].casefold() != spec.model_file.replace('\\', '/').rsplit('/', 1)[-1].casefold():
                    observation.update(status='unhealthy', model_id=None, error='Loaded model file differs from the configured resident model.')
                observation['runtime_identity'] = _digest({
                    'model_id': observation.get('model_id'),
                    'model_path': loaded_path,
                    'weights': self._weights_identity(loaded_path),
                    'model_ftype': props.get('model_ftype'),
                    'modalities': props.get('modalities'),
                    'chat_template_sha256': _digest(props.get('chat_template')),
                    'architecture': metadata.get('general.architecture'),
                    'file_type': metadata.get('general.file_type'),
                    'build_info': props.get('build_info'),
                })
                observation['architecture'] = metadata.get('general.architecture') if isinstance(metadata.get('general.architecture'), str) else None
                ftype = props.get('model_ftype', metadata.get('general.file_type'))
                observation['quantization'] = str(ftype) if type(ftype) in (str, int) else None
                observation['ram_available_bytes'] = __import__('psutil').virtual_memory().available
                from hanni.models.manager import current as manager_current
                manager = manager_current(spec)
                if manager:
                    with manager.lock:
                        resources = manager.last_resources
                        resource_stamp = getattr(manager, 'last_resources_sampled_at', None)
                else:
                    resources, resource_stamp = None, None
                matching = [gpu for gpu in getattr(resources, 'gpus', ()) if not spec.device_name_hints or any(
                    hint.casefold() in gpu.name.casefold() for hint in spec.device_name_hints)]
                observation['vram_free_bytes'] = max((gpu.memory_total_mb-gpu.memory_used_mb) * 1024**2 for gpu in matching) if len(matching) == 1 else None
                if len(matching) == 1:
                    gpu = matching[0]
                    observation['gpu_measurement'] = {'vram_total_bytes': gpu.memory_total_mb * 1024**2,
                        'vram_free_bytes': observation['vram_free_bytes'],
                        'utilization_percent': gpu.utilization_percent}
                    observation['resource_sampled_at'] = resource_stamp
                else:
                    observation['gpu_measurement'] = None
                    observation['resource_sampled_at'] = None
            return observation
        finally:
            if self.compute is None:
                transport.close(); registry.close()

    def _weights_identity(self, value):
        """Bind actual local GGUF contents without hashing gigabytes every poll."""
        if not isinstance(value, str) or not value.lower().endswith('.gguf'):
            return None
        try:
            path = Path(value).resolve()
            stat = path.stat()
            fingerprint = (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
            cached = self._file_hash_cache.get(str(path))
            if cached and cached[0] == fingerprint:
                return cached[1]
            digest = hashlib.sha256()
            with path.open('rb') as file:
                magic = file.read(4)
                if magic != b'GGUF': return None
                digest.update(magic)
                while chunk := file.read(1024**2): digest.update(chunk)
            after = path.stat()
            if (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino) != fingerprint[1:]:
                raise ModelSelectionError('Model weights changed while their identity was measured.')
            result = {'sha256': digest.hexdigest(), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
                      'ctime_ns': stat.st_ctime_ns, 'inode': stat.st_ino}
            self._file_hash_cache[str(path)] = (fingerprint, result)
            return result
        except (OSError, RuntimeError):
            return None

    def refresh(self):
        if self.closed:
            raise ModelSelectionError('Model routing is closed.')
        self._sync_identity_sources()
        # Unreachable remote checks can outlast the 30-second heartbeat lease.
        # Probe residents afterwards so callers receive genuinely recent local
        # health without extending or rewriting any observation's trust lease.
        if self.compute is not None:
            self.compute.refresh()
        for row in self._inventory():
            if 'spec' in row:
                observation = self._probe_local(row)
                with self.lock:
                    # Keep runtime binding when a server stops; unhealthy status
                    # blocks dispatch, while durable capability evidence survives.
                    previous = self.observations.get(row['endpoint_id'], {})
                    if observation.get('runtime_identity') is None:
                        observation = dict(observation, runtime_identity=previous.get('runtime_identity'))
                    self.observations[row['endpoint_id']] = observation
        return self.snapshot()

    def start_monitor(self):
        with self.lock:
            if self.thread is not None or self.closed:
                return
            self._sync_identity_sources()
            def run():
                while not self.halt.is_set():
                    try:
                        for row in self._inventory():
                            if 'spec' in row:
                                value = self._probe_local(row)
                                with self.lock:
                                    prior = self.observations.get(row['endpoint_id'], {})
                                    if not value.get('runtime_identity'):
                                        value = dict(value, runtime_identity=prior.get('runtime_identity'))
                                    self.observations[row['endpoint_id']] = value
                        if self.refresh_wake.is_set() and self.compute is not None:
                            self.compute.request_refresh()
                        self.last_error = None
                    except Exception:
                        self.last_error = 'Model discovery is temporarily unavailable.'
                    self.refresh_wake.clear()
                    self.refresh_wake.wait(10)
            self.thread = threading.Thread(target=run, name='hanni-model-routing', daemon=True)
            self.thread.start()
        if self.compute is not None:
            self.compute.start_monitor()

    def request_refresh(self):
        if self.closed: raise ModelSelectionError('Model routing is closed.')
        self.start_monitor()
        self.refresh_wake.set()
        if self.compute is not None: self.compute.request_refresh()
        return self.snapshot()

    def _reasons(self, row, request):
        reasons = list(row['blocked_reasons'])
        legacy = row['legacy_default'] and request.allow_legacy_default
        if row['model_id'] != row['configured_model']:
            reasons.append('model_identity_mismatch')
        if request.local_only and not row['local']: reasons.append('local_only')
        if not set(request.privacy_categories) <= set(row['allowed_categories']): reasons.append('privacy_not_authorized')
        required = request.context_tokens + request.output_tokens
        if not row['max_context_verified'] or required > row['max_context_verified']:
            if not legacy or row['max_context_verified'] or not row['context_configured'] or required > row['context_configured']:
                reasons.append('required_context_not_verified')
        if not set(request.capabilities) <= set(row['capabilities']):
            if not legacy or 'vision' in request.capabilities:
                reasons.append('required_capability_not_verified')
        if 'worker' in row and set(request.capabilities) & {'tool_calling', 'vision'}:
            reasons.append('transport_unsupported_tool_or_vision')
        if request.response_format and request.response_format not in row['structured_output_formats'] and not legacy:
            reasons.append('required_output_format_not_verified')
        if request.tool_calling_format and request.tool_calling_format not in row['tool_calling_formats'] and not legacy:
            reasons.append('required_tool_format_not_verified')
        if legacy:
            reasons = [reason for reason in reasons if reason != 'context_not_verified']
        # Unknown remote memory is not interpreted as available capacity.
        ram, vram = row['ram_available_bytes'], row['vram_free_bytes']
        if not row['local'] and (ram is None or vram is None): reasons.append('resource_measurement_unknown')
        if any(value is not None and not _number(value) for value in (ram, vram)):
            reasons.append('resource_measurement_invalid')
        if _number(ram) and ram < 2 * 1024**3: reasons.append('insufficient_ram_reserve')
        if _number(vram) and vram < 256 * 1024**2: reasons.append('insufficient_vram_reserve')
        capacity = row['concurrency'] - (0 if request.interactive else row.get('interactive_reserve', 0))
        if row['current_requests'] >= capacity: reasons.append('endpoint_busy')
        if row['queue_depth'] is not None and (not _number(row['queue_depth']) or row['queue_depth'] >= 16): reasons.append('excessive_queue')
        return sorted(set(reasons))

    def select(self, request, *, exclude=(), allowed_endpoint_ids=None):
        if not isinstance(request, ModelRequest) or self.closed:
            raise ModelSelectionError('Routing requires a valid trusted controller request.')
        settings = self._settings()
        rows = self._rows()
        exclusions, candidates = [], []
        for row in rows:
            reasons = self._reasons(row, request)
            if settings['policy'] in {'resident_first','measured_work'}:
                difficult = (settings['policy']=='measured_work' and request.complexity=='complex'
                             and request.task_category in {'planning','analysis','coding','structured_output'})
                if not row['legacy_default'] and not difficult:
                    reasons.append('resident_interaction_policy')
                if not row['local'] and difficult:
                    proof=row['profiles'].get(request.task_category,{})
                    if (proof.get('correctness_sample_count',0)<settings['minimum_samples']
                            or (proof.get('accuracy_lower_bound') or 0)<settings['minimum_accuracy_lower_bound']):
                        reasons.append('stronger_role_not_measured')
            if row['endpoint_id'] in exclude: reasons.append('previous_attempt_failed')
            if allowed_endpoint_ids is not None and row['endpoint_id'] not in allowed_endpoint_ids:
                reasons.append('outside_trusted_assignment')
            if settings['policy'] == 'manual' and row['endpoint_id'] != settings['manual_endpoint_id']: reasons.append('manual_override')
            if reasons:
                exclusions.append({'endpoint_id': row['endpoint_id'], 'reasons': sorted(set(reasons))})
            else:
                candidates.append(row)
        if not candidates:
            return {'endpoint': None, 'reason': 'No available model satisfies the measured context, capability, resource and privacy requirements.', 'excluded': exclusions}
        # Only measured accuracy can authorize a departure from conservative
        # default quality. Unscored live latency samples cannot raise accuracy.
        def rank(row):
            profile = row['profiles'].get(request.task_category, {})
            known = profile.get('correctness_sample_count', 0)
            reliable = known >= settings['minimum_samples'] and (profile.get('accuracy_lower_bound') or 0) >= settings['minimum_accuracy_lower_bound']
            quality = profile.get('accuracy_lower_bound') if reliable else -1
            latency = profile.get('mean_latency_ms') or 1e9
            primary = row['legacy_default']
            if settings['policy'] == 'quality' or request.complexity == 'complex':
                return (-int(reliable), -(quality or 0), -int(primary), latency, row['endpoint_id'])
            if settings['policy'] == 'fast':
                return (-int(reliable), -int(primary and not reliable), latency, row['endpoint_id'])
            return (-int(reliable), -int(primary and not reliable), -(quality or 0), latency, row['endpoint_id'])
        selected = min(candidates, key=rank)
        adaptation = None
        if settings['policy'] != 'manual':
            # Adapt only within the existing quality/default tier, and only
            # using recent observations for this exact trusted task category.
            tier = rank(selected)[:-2]
            peers = [row for row in candidates if rank(row)[:-2] == tier]
            selected, adaptation = self._recent_placement(request, peers, selected)
        profile = selected['profiles'].get(request.task_category, {})
        quality = profile.get('confidence') == 'measured'
        legacy = selected['legacy_default'] and request.allow_legacy_default and (
            not selected['max_context_verified']
            or not set(request.capabilities) <= set(selected['capabilities'])
            or request.response_format and request.response_format not in selected['structured_output_formats']
            or request.tool_calling_format and request.tool_calling_format not in selected['tool_calling_formats'])
        reason = (f'{settings["policy"]} policy; exact configured identity, permitted context categories and bounded load; '
                  + ('existing default path retained with unverified legacy capability/context/format; no adaptive capability upgrade' if legacy else f'verified context {selected["max_context_verified"]} and {", ".join(sorted(request.capabilities))}')
                  + ('; sufficient measured task-category evidence' if quality else '; insufficient category accuracy evidence, conservative default ordering'))
        if adaptation:
            reason += '; ' + adaptation
        return {'endpoint': selected, 'reason': reason, 'excluded': exclusions}

    def _recent_placement(self, request, candidates, default):
        key = (request.task_category, request.complexity, request.local_only,
               tuple(sorted(request.privacy_categories)), tuple(sorted(request.capabilities)),
               request.response_format, request.tool_calling_format, request.interactive)
        with self.lock:
            now = self.clock()
            previous = self._placement_history.get(key)
            if previous and now < previous[2]:
                previous = None  # Wall-clock rollback cannot extend a placement hold.
            incumbent = next((row for row in candidates if previous and
                (row['endpoint_id'], row['identity']) == previous[:2]), default)
            observed = {}
            for row in candidates:
                samples = self._profile_entry(row['endpoint_id'], row['identity'])['samples'].get(request.task_category, [])
                recent = sorted((sample for sample in samples if 0 <= now-sample['created_at'] <= 300),
                                key=lambda sample: sample['created_at'])[-100:]
                successful = [sample for sample in recent if not sample['error']
                              and sample['correct'] is not False and sample['verified_success'] is not False]
                data = recent_performance(successful, now, window_seconds=300)
                data['failure_count'] = len(recent)-len(successful)
                data['total_count'] = len(recent)
                data['repeated_failure'] = len(recent) >= 3 and all(sample not in successful for sample in recent[-3:])
                observed[row['endpoint_id']] = data
            def score(row):
                data = observed[row['endpoint_id']]
                if data['sample_count'] < 3 or data['p50_latency_ms'] is None or data['repeated_failure']:
                    return None
                return data['p50_latency_ms'] * (1 + data['failure_count'] / data['total_count'])
            current_score = score(incumbent)
            qualified = [row for row in candidates if score(row) is not None]
            chosen, reason = incumbent if current_score is not None else default, None
            if observed[incumbent['endpoint_id']]['repeated_failure'] and qualified:
                chosen = min(qualified, key=lambda row: (score(row), row['endpoint_id']))
                reason = '3 consecutive recent failures; healthy same-quality-tier peer with 3 or more fresh successful observations selected'
            elif current_score is not None and qualified:
                faster = min(qualified, key=lambda row: (score(row), row['endpoint_id']))
                hold_elapsed = not previous or now - previous[2] >= 30
                if (hold_elapsed and faster['endpoint_id'] != incumbent['endpoint_id']
                        and score(faster) <= .8 * current_score):
                    chosen = faster
                    reason = 'recent same-category latency improved at least 20% with 3 or more fresh samples; 30-second placement hold'
                elif not hold_elapsed:
                    reason = 'recent placement hold retained; fresh eligibility and quality rechecked'
            changed = previous is None or previous[:2] != (chosen['endpoint_id'], chosen['identity'])
            if len(self._placement_history) >= 64 and key not in self._placement_history:
                self._placement_history.pop(next(iter(self._placement_history)))
            self._placement_history[key] = (chosen['endpoint_id'], chosen['identity'],
                now if changed else previous[2])
            return chosen, reason

    def _save_decision(self, decision):
        with self.lock:
            db = self._connect()
            db.execute('INSERT OR REPLACE INTO decisions VALUES(?,?,?)', (decision['decision_id'], decision['created_at'], json.dumps(decision, allow_nan=False)))
            db.execute('DELETE FROM decisions WHERE id NOT IN (SELECT id FROM decisions ORDER BY created DESC LIMIT 200)')
            db.commit()

    def execute(self, messages, *, request, validator=None, admission=None, local_operation=None,
                workflow_id=None, step_id=None, invocation_id=None, cancellation=None, exclude=(),
                endpoint_id=None, max_fallbacks=None, telemetry=None, **options):
        if not isinstance(request, ModelRequest):
            raise ModelSelectionError('Model inference requires trusted bounded request requirements.')
        fallback_budget = self._settings()['max_fallbacks'] if max_fallbacks is None else max_fallbacks
        if type(fallback_budget) is not int or not 0 <= fallback_budget <= self._settings()['max_fallbacks']:
            raise ModelSelectionError('Trusted inference cannot increase the existing fallback budget.')
        if endpoint_id is not None and (not isinstance(endpoint_id, str) or not endpoint_id):
            raise ModelSelectionError('A trusted model assignment requires an endpoint identifier.')
        if telemetry is not None and not isinstance(telemetry, dict):
            raise ModelSelectionError('Inference telemetry requires a controller-owned mapping.')
        _validate_text_messages(messages)
        actual_output = options.get('max_tokens', request.output_tokens)
        if type(actual_output) is not int or not 1 <= actual_output <= 8192:
            raise ModelSelectionError('Invalid actual model output budget.')
        options['max_tokens'] = actual_output
        request = replace(request, output_tokens=max(request.output_tokens, actual_output))
        if options.get('response_format') is not None:
            response_format = options['response_format']
            if not isinstance(response_format, Mapping) or response_format.get('type') not in {'json_object', 'json_schema'}:
                raise ModelSelectionError('Unsupported actual model output format.')
            request = replace(request, capabilities=frozenset(set(request.capabilities) | {'structured_json'}),
                response_format=response_format['type'],
                schema_tokens=max(request.schema_tokens, len(json.dumps(response_format, allow_nan=False).encode())))
            if validator is None: validator = _json_validator(response_format)
        # Conservative byte bound includes structured tool schemas when present.
        encoded = json.dumps(messages, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 262144:
            raise ModelSelectionError('Model request exceeds its bounded payload budget.')
        request = replace(request, context_tokens=max(request.context_tokens, len(encoded.encode())) + request.schema_tokens,
                          schema_tokens=0)
        decision = {'decision_id': uuid4().hex, 'created_at': self.clock(), 'task_category': request.task_category,
            'policy': self._settings()['policy'], 'endpoint_id': None, 'model_id': None, 'reason': '', 'status': 'selecting',
            'privacy_categories': sorted(request.privacy_categories), 'required_context_tokens': request.context_tokens + request.output_tokens,
            'excluded': [], 'fallbacks': [], 'latency_ms': None}
        excluded = set(exclude)
        began = self.monotonic()
        for attempt in range(fallback_budget + 1):
            if cancellation is not None and cancellation.is_set():
                decision.update(status='cancelled'); self._save_decision(decision)
                raise ModelSelectionError('Model inference was cancelled before dispatch.')
            selection = self.select(request, exclude=excluded,
                allowed_endpoint_ids=None if endpoint_id is None else frozenset({endpoint_id}))
            decision['excluded'] = selection['excluded']; decision['reason'] = selection['reason']
            row = selection['endpoint']
            if row is None:
                decision['status'] = 'blocked'; self._save_decision(decision)
                raise ModelSelectionError(selection['reason'])
            key = row['endpoint_id']
            if decision['endpoint_id'] is not None:
                decision['fallbacks'][-1]['to_endpoint_id'] = key
            decision.update(endpoint_id=key, model_id=row['model_id'], status='running')
            self._save_decision(decision)
            started = self.monotonic()
            compute_job = None
            usage = {}
            performance = {}
            resource_observations = self._resource_observations(row)
            admission_failed = False

            def check_withdrawal():
                if self.closed:
                    raise _ModelAdmissionWithdrawn('Model routing closed before inference admission.')
                if cancellation is not None and cancellation.is_set():
                    raise _ModelAdmissionWithdrawn('Model inference was cancelled before admission.')

            def admit():
                nonlocal admission_failed
                check_withdrawal()
                if admission:
                    try:
                        admission()
                    except Exception:
                        admission_failed = True
                        raise
                check_withdrawal()

            def check_result():
                check_withdrawal()
                if 'spec' in row:
                    observed = self.observations.get(key, {})
                    stamp = observed.get('last_heartbeat')
                    if not _number(stamp) or not 0 <= self.clock() - stamp <= 30:
                        resident = next((candidate for candidate in self._inventory()
                                         if candidate['endpoint_id'] == key), None)
                        if resident is None:
                            raise _ModelAdmissionWithdrawn('The resident model was removed during inference.')
                        value = self._probe_local(resident)
                        with self.lock:
                            prior = self.observations.get(key, {})
                            if value.get('runtime_identity') is None:
                                value = dict(value, runtime_identity=prior.get('runtime_identity'))
                            self.observations[key] = value
                    latest = next((candidate for candidate in self._rows()
                                   if candidate['endpoint_id'] == key), None)
                    reasons = (set(self._reasons(latest, request)) - {'endpoint_busy', 'excessive_queue'}
                               if latest is not None else {'removed'})
                    if latest is None or latest['identity'] != row['identity'] or reasons:
                        raise _ModelAdmissionWithdrawn('Resident model eligibility changed before result admission.')
                check_withdrawal()

            try:
                admit()
                # Recheck protected authorization and identity immediately before
                # dispatch; model text cannot weaken any requirement.
                current_row = next((candidate for candidate in self._rows() if candidate['endpoint_id'] == key), None)
                if current_row is None or current_row['identity'] != row['identity'] or self._reasons(current_row, request):
                    raise ModelSelectionError('Endpoint eligibility changed before dispatch.')
                resource_observations = self._resource_observations(current_row)
                if 'spec' in row:
                    with self.lock:
                        if self.active.get(key, 0) >= row['concurrency']:
                            raise ModelSelectionError('Local endpoint became busy before inference admission.')
                        self.active[key] = self.active.get(key, 0) + 1
                    try:
                        client = _BoundedInferenceClient(replace(row['spec'], max_tokens=actual_output), max_attempts=1)
                        client._inference_usage = usage
                        client._inference_performance = performance
                        value = local_operation(client) if local_operation else client.chat(messages,
                            **dict(options, usage=usage))
                        if hasattr(value, 'usage'):
                            usage.update(value.usage)
                    finally:
                        with self.lock: self.active[key] = max(0, self.active.get(key, 0) - 1)
                else:
                    if set(request.capabilities) & {'tool_calling', 'vision'}:
                        raise ModelSelectionError('The existing worker transport supports bounded analysis, not native tool or visual turns.')
                    value, compute_job = self.compute.chat(messages, workflow_id=workflow_id or 'routing_' + decision['decision_id'],
                        step_id=step_id or 'model_inference', invocation_id=invocation_id or decision['decision_id'], categories=set(request.privacy_categories),
                        interactive=request.interactive, admission=admit, allowed_worker_ids=(row['worker']['worker_id'],),
                        max_retries_override=0, max_queue_seconds=self._settings()['max_queue_seconds'],
                        selection_reason=selection['reason'], cancellation=cancellation, **options)
                    usage = compute_job.get('tokens') or {}
                    performance = compute_job.get('performance') or {}
                if telemetry is not None:
                    telemetry.update(endpoint_id=key, model_id=row['model_id'], identity=row['identity'],
                        latency_ms=(self.monotonic()-started)*1000,
                        resource_observations=resource_observations,
                        performance=deepcopy(performance),
                        tokens={field: usage[field] for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                                if type(usage.get(field)) is int and usage[field] >= 0} or None,
                        compute_job_id=compute_job.get('job_id') if compute_job is not None else None)
                admit()
                check_result()
                if validator is not None and not validator(value):
                    raise ModelProtocolError('External structured-output or task verification rejected model output.')
                check_result()
                if compute_job is not None:
                    self.compute.finish(compute_job, {'status': 'VERIFIED' if validator is not None else 'UNVERIFIED'})
                elapsed = (self.monotonic() - started)*1000
                self.record_evaluation(key, identity=row['identity'], task_category=request.task_category,
                    correct=None, verified_success=None, latency_ms=elapsed,
                    evidence_sha256=_digest({'decision_id': decision['decision_id'], 'status': 'returned'}),
                    environment='controller-runtime; correctness unscored', evaluation_id=decision['decision_id'] + ':' + str(attempt),
                    resource_observations=resource_observations, ttft_ms=performance.get('ttft_ms'),
                    generation_tps=performance.get('generation_tps'), prompt_tps=performance.get('prompt_tps'),
                    queue_ms=compute_job.get('queue_ms', 0) if compute_job is not None else 0)
                decision.update(status='completed', latency_ms=(self.monotonic()-began)*1000)
                self._save_decision(decision)
                return value
            except _ModelAdmissionWithdrawn:
                if compute_job is not None:
                    self.compute.finish(compute_job, {'status': 'UNVERIFIED'})
                decision.update(status='cancelled' if cancellation is not None and cancellation.is_set() else 'blocked',
                    reason='Original inference admission was withdrawn; no endpoint failure or fallback was recorded.')
                self._save_decision(decision)
                raise
            except (ModelClientError, ComputeError, TimeoutError) as exc:
                if admission_failed or self.closed or cancellation is not None and cancellation.is_set():
                    if compute_job is not None:
                        self.compute.finish(compute_job, {'status': 'UNVERIFIED'})
                    decision.update(status='cancelled' if cancellation is not None and cancellation.is_set() else 'blocked',
                        reason='Original inference admission was withdrawn; no endpoint failure or fallback was recorded.')
                    self._save_decision(decision)
                    raise
                if compute_job is not None:
                    self.compute.finish(compute_job, {'status': 'UNVERIFIED'})
                rejected_output = isinstance(exc, ModelProtocolError) and not isinstance(exc, ModelIdentityError)
                trigger = ('model_identity_mismatch' if isinstance(exc, ModelIdentityError) else
                           'verification_failed' if rejected_output else 'endpoint_failed_or_timeout')
                excluded.add(key)
                decision['fallbacks'].append({'from_endpoint_id': key, 'to_endpoint_id': None, 'trigger': trigger})
                decision['status'] = 'fallback'; self._save_decision(decision)
                try:
                    self.record_evaluation(key, identity=row['identity'], task_category=request.task_category,
                        correct=False if rejected_output else None, verified_success=False,
                        latency_ms=(self.monotonic()-started)*1000, error=True,
                        evidence_sha256=_digest({'decision_id': decision['decision_id'], 'trigger': trigger}),
                        environment='controller-runtime; measurable failure', evaluation_id=decision['decision_id'] + ':' + str(attempt),
                        resource_observations=resource_observations)
                except ModelSelectionError:
                    pass  # Changed identities do not inherit measurements.
                if attempt == fallback_budget or self._settings()['policy'] == 'manual':
                    decision['status'] = 'failed'; self._save_decision(decision)
                    raise ModelSelectionError('Eligible model inference failed after bounded fallback.') from exc
            except Exception:
                decision.update(status='blocked', reason='Original controller admission or verification failed; no tool operation was replayed.')
                self._save_decision(decision)
                raise
        raise ModelSelectionError('Bounded model inference did not complete.')

    def wrap_client(self, client):
        if isinstance(client, AdaptiveModelClient) and client.engine is self:
            return client
        return AdaptiveModelClient(client, self)

    @property
    def collaboration(self):
        """Shared bounded inference comparison, under this router's authority."""
        from hanni.models.collaboration import CollaborationEngine
        with self.lock:
            if self._collaboration is None:
                self._collaboration = CollaborationEngine(self)
            return self._collaboration

    def snapshot(self):
        if self.closed:
            reason = 'Model routing is closed.'
            return {'available': False, 'enabled': False, 'reason': reason, 'sampled_at': self.clock(),
                'policy': 'balanced', 'manual_endpoint_id': None, 'controller_attached': False,
                'endpoints': [], 'decisions': [], 'controls': {'configure': {'enabled': False, 'reason': reason},
                    'refresh': {'enabled': False, 'reason': reason}, 'supported_policies': list(POLICIES)}}
        rows = self._rows()
        public = [{key: value for key, value in row.items() if key not in {'spec', 'worker', 'configured_capabilities', 'concurrency'}} for row in rows]
        for row in public:
            for field in ('model_id', 'configured_model'):
                if isinstance(row[field], str):
                    row[field] = row[field].replace('\\', '/').rsplit('/', 1)[-1]
            observed = self.observations.get(row['endpoint_id'], {})
            if row['endpoint_id'].startswith('worker:') and self.compute is not None:
                observed = self.compute.registry.observations.get(row['endpoint_id'].removeprefix('worker:'), {})
            row.setdefault('architecture', observed.get('architecture'))
            row.setdefault('quantization', observed.get('quantization'))
            row['performance'] = self._performance(row['endpoint_id'], row['identity'])
            stamp = observed.get('resource_sampled_at')
            row['resource_sampled_at'] = stamp if _number(stamp) and stamp <= self.clock() else None
            gpu = observed.get('gpu_measurement')
            if isinstance(gpu, Mapping):
                row['gpu_measurement'] = {field: gpu.get(field) if _number(gpu.get(field)) else None
                    for field in ('vram_total_bytes', 'vram_free_bytes', 'utilization_percent')}
                row['gpu_measurement']['sampled_at'] = row['resource_sampled_at']
            else:
                row['gpu_measurement'] = None
        with self.lock:
            decisions = [json.loads(row[0]) for row in self._connect().execute('SELECT payload FROM decisions ORDER BY created DESC LIMIT 50')]
        for decision in decisions:
            if isinstance(decision.get('model_id'), str):
                decision['model_id'] = decision['model_id'].replace('\\', '/').rsplit('/', 1)[-1]
        settings = self._settings()
        return {'available': not self.closed, 'enabled': not self.closed, 'reason': self.last_error,
            'sampled_at': self.clock(), 'policy': settings['policy'], 'manual_endpoint_id': settings['manual_endpoint_id'],
            'controller_attached': self.controller_attached, 'endpoints': public, 'decisions': decisions,
            'controls': {'configure': {'enabled': not self.closed, 'reason': None if not self.closed else 'Model routing is closed.'},
                         'refresh': {'enabled': not self.closed, 'reason': None if not self.closed else 'Model routing is closed.'},
                         'supported_policies': list(POLICIES)}}

    def close(self):
        self.closed = True; self.halt.set(); self.refresh_wake.set()
        if self.thread: self.thread.join(4)
        with self.lock:
            if self.db is not None:
                self.db.close(); self.db = None
        uninstall(self)


def _json_validator(response_format):
    if response_format is None:
        return None
    def validate(value):
        try:
            from hanni.workflows.verification import parse_evidence_json
            parsed = parse_evidence_json(value)
            if not isinstance(parsed, dict): return False
            if response_format.get('type') == 'json_schema':
                import jsonschema
                jsonschema.Draft202012Validator(response_format['json_schema']['schema']).validate(parsed)
            return True
        except (ValueError, TypeError, KeyError, RecursionError, __import__('jsonschema').ValidationError):
            return False
    return validate


def _validate_text_messages(messages):
    if not isinstance(messages, (list, tuple)) or not messages or len(messages) > 256:
        raise ModelSelectionError('Model inference requires a bounded message list.')
    for message in messages:
        if not isinstance(message, Mapping) or message.get('role') not in {'system', 'user', 'assistant', 'tool'}:
            raise ModelSelectionError('Model inference requires ordinary controller messages.')
        content = message.get('content')
        if content is not None and not isinstance(content, str):
            raise ModelSelectionError('Native image or multimodal inference is unsupported by this controller adapter; use the original screen capability and permission path.')


class AdaptiveModelClient:
    """Drop-in pure-inference adapter; never executes a selected tool call."""
    def __init__(self, original, engine):
        self.original, self.engine = original, engine
        self.spec = original.spec

    def _fresh_primary(self):
        key = 'local:' + self.spec.id
        observation = self.engine.observations.get(key, {})
        stamp = observation.get('last_heartbeat')
        if (observation.get('status') == 'healthy' and _number(stamp)
                and 0 <= self.engine.clock() - stamp <= 30):
            return
        row = next((row for row in self.engine._inventory() if row['endpoint_id'] == key), None)
        if row is not None:
            value = self.engine._probe_local(row)
            with self.engine.lock:
                if not value.get('runtime_identity'):
                    value = dict(value, runtime_identity=observation.get('runtime_identity'))
                self.engine.observations[key] = value

    def health(self):
        health = self.original.health()
        if health.ok: self._fresh_primary()
        return health

    def ensure_loaded(self):
        value = self.original.ensure_loaded()
        self._fresh_primary()
        return value

    def _request(self, options, *, tools=None):
        self._fresh_primary()
        request = _scope.get() or ModelRequest(allow_legacy_default=True)
        output = options.get('max_tokens') or self.spec.max_tokens
        capabilities = set(request.capabilities)
        if options.get('response_format') is not None: capabilities.add('structured_json')
        if tools is not None: capabilities.add('tool_calling')
        schemas = (len(json.dumps(tools).encode()) if tools else 0) + (len(json.dumps(options['response_format']).encode()) if options.get('response_format') else 0)
        return replace(request, output_tokens=output, capabilities=frozenset(capabilities),
                       schema_tokens=request.schema_tokens + schemas,
                       response_format=options['response_format'].get('type') if options.get('response_format') else request.response_format,
                       tool_calling_format='openai_function' if tools is not None else request.tool_calling_format)

    def chat(self, messages, **options):
        options = {key: value for key, value in options.items() if value is not None}
        request = self._request(options)
        return self.engine.execute(messages, request=request,
            validator=_json_validator(options.get('response_format')), **options)

    def chat_verified(self, messages, *, validator, request=None, admission=None, local_operation=None,
                      workflow_id=None, step_id=None, invocation_id=None, **options):
        options = {key: value for key, value in options.items() if value is not None}
        return self.engine.execute(messages, request=request or self._request(options), validator=validator,
            admission=admission, local_operation=local_operation, workflow_id=workflow_id,
            step_id=step_id, invocation_id=invocation_id, **options)

    def stream_chat(self, messages, **options):
        # Preserve real local streaming and never replay a request after output
        # has become visible. A remote response is bounded before being yielded.
        _validate_text_messages(messages)
        request = self._request(options)
        selection = self.engine.select(replace(request, context_tokens=max(request.context_tokens,
            len(json.dumps(messages, ensure_ascii=False).encode())) + request.schema_tokens, schema_tokens=0))
        row = selection['endpoint']
        if row is not None and 'spec' in row and options.get('response_format') is None:
            decision = {'decision_id': uuid4().hex, 'created_at': self.engine.clock(), 'task_category': request.task_category,
                'policy': self.engine._settings()['policy'], 'endpoint_id': row['endpoint_id'], 'model_id': row['model_id'],
                'reason': selection['reason'], 'status': 'running', 'privacy_categories': sorted(request.privacy_categories),
                'required_context_tokens': max(request.context_tokens, len(json.dumps(messages).encode())) + request.output_tokens,
                'excluded': selection['excluded'], 'fallbacks': [], 'latency_ms': None}
            self.engine._save_decision(decision)
            began = self.engine.monotonic(); yielded = False; reserved = False
            performance, usage = {}, {}
            resource_observations = self.engine._resource_observations(row)
            try:
                with self.engine.lock:
                    latest = next((candidate for candidate in self.engine._rows() if candidate['endpoint_id'] == row['endpoint_id']), None)
                    bounded = replace(request, context_tokens=max(request.context_tokens,
                        len(json.dumps(messages, ensure_ascii=False).encode())) + request.schema_tokens, schema_tokens=0)
                    if latest is None or latest['identity'] != row['identity'] or self.engine._reasons(latest, bounded):
                        raise ModelSelectionError('Endpoint eligibility changed before streaming admission.')
                    resource_observations = self.engine._resource_observations(latest)
                    if self.engine.active.get(row['endpoint_id'], 0) >= row['concurrency']:
                        raise ModelSelectionError('Local model became busy before streaming admission.')
                    self.engine.active[row['endpoint_id']] = self.engine.active.get(row['endpoint_id'], 0) + 1
                    reserved = True
                streaming_client = self.original if row['spec'].id == self.spec.id else LlamaCppClient(row['spec'], max_attempts=1)
                stream_options = dict(options)
                if isinstance(streaming_client, LlamaCppClient):
                    usage = options.get('usage') if options.get('usage') is not None else {}
                    stream_options.update(usage=usage, performance=performance)
                stream = streaming_client.stream_chat(messages, **stream_options)
                try:
                    for part in stream:
                        if not yielded and performance.get('ttft_ms') is None:
                            performance['ttft_ms'] = (self.engine.monotonic()-began)*1000
                        yielded = True
                        yield part
                finally:
                    close = getattr(stream, 'close', None)
                    if callable(close):
                        close()
                decision.update(status='completed', latency_ms=(self.engine.monotonic()-began)*1000)
                try:
                    self.engine.record_evaluation(row['endpoint_id'], identity=row['identity'], task_category=request.task_category,
                        correct=None, verified_success=None, latency_ms=decision['latency_ms'],
                        evidence_sha256=_digest({'decision_id': decision['decision_id'], 'status': 'returned'}),
                        environment='controller-runtime; streaming correctness unscored', evaluation_id=decision['decision_id'],
                        resource_observations=resource_observations, ttft_ms=performance.get('ttft_ms'),
                        generation_tps=performance.get('generation_tps'), prompt_tps=performance.get('prompt_tps'))
                except ModelSelectionError:
                    pass  # A changed runtime does not inherit this measurement.
            except ModelClientError:
                decision.update(status='failed_after_partial' if yielded else 'failed', latency_ms=(self.engine.monotonic()-began)*1000)
                try:
                    self.engine.record_evaluation(row['endpoint_id'], identity=row['identity'], task_category=request.task_category,
                        correct=None, verified_success=False, latency_ms=decision['latency_ms'], error=True,
                        evidence_sha256=_digest({'decision_id': decision['decision_id'], 'status': decision['status']}),
                        environment='controller-runtime; streaming measurable failure', evaluation_id=decision['decision_id'],
                        resource_observations=resource_observations)
                except ModelSelectionError:
                    pass
                if yielded: raise
                yield self.engine.execute(messages, request=request, exclude=(row['endpoint_id'],), **options)
            except GeneratorExit:
                decision.update(status='cancelled_after_partial' if yielded else 'cancelled',
                    latency_ms=(self.engine.monotonic()-began)*1000)
                try:
                    self.engine.record_evaluation(row['endpoint_id'], identity=row['identity'], task_category=request.task_category,
                        correct=None, verified_success=None, latency_ms=decision['latency_ms'],
                        evidence_sha256=_digest({'decision_id': decision['decision_id'], 'status': decision['status']}),
                        environment='controller-runtime; streaming cancelled unscored', evaluation_id=decision['decision_id'],
                        resource_observations=resource_observations)
                except ModelSelectionError:
                    pass
                raise
            finally:
                if reserved:
                    with self.engine.lock:
                        self.engine.active[row['endpoint_id']] = max(0, self.engine.active.get(row['endpoint_id'], 0) - 1)
                self.engine._save_decision(decision)
        else:
            yield self.chat(messages, **options)

    def complete_with_tools(self, messages, *, tools, **options):
        options = {key: value for key, value in options.items() if value is not None}
        request = self._request(options, tools=tools)
        options['max_tokens'] = request.output_tokens
        def validate(turn):
            import jsonschema
            schemas = {tool['function']['name']: tool['function'].get('parameters', {}) for tool in tools}
            try:
                for call in turn.tool_calls:
                    if call.name not in schemas or not isinstance(call.arguments, Mapping): return False
                    jsonschema.Draft202012Validator(schemas[call.name]).validate(dict(call.arguments))
                return len(turn.tool_calls) <= 1
            except jsonschema.ValidationError:
                return False
        return self.engine.execute(messages, request=request, validator=validate,
            local_operation=lambda client: client.complete_with_tools(messages, tools=tools, **options), **options)
