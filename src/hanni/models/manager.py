"""Process ownership and leases for pinned and on-demand local model servers.

Loading is synchronous in the requesting worker, never under a global state
lock. Idle eviction only stops owned, unused servers. External servers are
observed but never terminated by this manager.
"""
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
import logging
import os
import threading
import time
import psutil

from hanni.models.client import LlamaCppClient, ModelUnavailableError
from hanni.models.runtime import model_command
from hanni.models.resource_manager import snapshot_resources

log = logging.getLogger(__name__)
_current = None


def install(manager):
    global _current
    _current = manager


def current(spec=None):
    manager = _current
    if manager is not None and spec is not None:
        entry = manager.entries.get(spec.id)
        if entry is None or entry.spec.endpoint != spec.endpoint: return None
    return manager


def inference_lease(spec):
    manager = current(spec)
    return manager.lease(spec.id) if manager else nullcontext()


@dataclass
class Entry:
    spec: object
    process: object = None
    state: str = 'STOPPED'
    active: int = 0
    last_used: float = 0.
    loaded_at: float = 0.
    retry_after: float = 0.
    startup_seconds: float | None = None
    error: str | None = None
    command: list = field(default_factory=list)
    lock: object = field(default_factory=threading.RLock)


class ModelManager:
    def __init__(self, config, *, launch=None, stop=None, health=None, resources=None,
                 clock=time.monotonic, startup_timeout=900, model_files=None, shutdown_event=None):
        self.config, self.clock = config, clock
        if len(config.models.models) != 1:
            raise ValueError("HANNI assistant runtime requires exactly one configured model")
        self.entries = {config.models.supervisor.id: Entry(config.models.supervisor)}
        self._launch = launch or self._default_launch
        self._stop = stop or self._default_stop
        self._health = health or (lambda spec: LlamaCppClient(spec, max_attempts=1).health().ok)
        self.resources = resources or snapshot_resources
        self.startup_timeout = startup_timeout
        self.files = dict(model_files or {})
        self.shutdown_event = shutdown_event
        self.lock = threading.RLock()
        self.gpu_load_lock = threading.Lock()
        self.closed = False
        self.signal = threading.Event()
        self.worker = None
        self.last_resources = None
        self.last_resources_sampled_at = None

    def _default_launch(self, spec):
        from hanni.dashboard.launcher import start_model
        return start_model(self.config, model_id=spec.id, timeout=self.startup_timeout,
                           command=self.entries[spec.id].command,
                           shutdown_event=self.shutdown_event)

    @staticmethod
    def _default_stop(process):
        from hanni.dashboard.launcher import stop_owned
        stop_owned(process)

    def start(self):
        self.worker = threading.Thread(target=self._monitor, name='hanni-model-residency', daemon=True)
        self.worker.start()

    def _state(self, entry, state):
        with self.lock: entry.state = state
        log.info('[ModelManager] %s %s context=%s pinned=%s', entry.spec.id, state,
                 entry.spec.context_length, entry.spec.keep_loaded)

    def _capture_resources(self):
        resources = self.resources()
        with self.lock:
            self.last_resources = resources
            self.last_resources_sampled_at = time.time()
        return resources

    def _admit(self, entry):
        resources = self._capture_resources()
        spec = entry.spec
        available = (resources.ram_total_gb-resources.ram_used_gb)*1024
        if available < spec.ram_budget_mb+self.config.models.ram_reserve_mb:
            raise ModelUnavailableError(f'{spec.id}: insufficient available RAM for budget and reserve')
        # GPU inventory is best effort. Unknown readings do not masquerade as free VRAM.
        # Device matching uses the same explicit names as command generation.
        hints = spec.device_name_hints
        matches = [gpu for gpu in resources.gpus if any(h.casefold() in gpu.name.casefold() for h in hints)]
        budget = spec.vram_budget_mb
        if hints and not matches and spec.fallback_device_name_hints:
            hints = spec.fallback_device_name_hints
            matches = [gpu for gpu in resources.gpus if any(h.casefold() in gpu.name.casefold() for h in hints)]
            # Configured budget is a conservative full-offload estimate even for fallback.
        if spec.gpu_layers and budget and matches:
            free = sum(gpu.memory_total_mb-gpu.memory_used_mb for gpu in matches)
            if free < budget+self.config.models.vram_reserve_mb:
                raise ModelUnavailableError(f'{spec.id}: insufficient reported VRAM for budget and reserve')

    def ensure_loaded(self, model_id):
        entry = self.entries[model_id]
        with entry.lock:
            if self.shutdown_event is not None and self.shutdown_event.is_set():
                raise ModelUnavailableError('HANNI is shutting down')
            if self.closed: raise ModelUnavailableError('Model manager is shutting down')
            if entry.state in {'READY','BUSY'}:
                if (entry.process is None or entry.process.poll() is None) and self._health(entry.spec):
                    entry.last_used = self.clock()
                    entry.state = 'BUSY' if entry.active else 'READY'
                    return entry
                self._state(entry, 'UNHEALTHY')
            if self.clock() < entry.retry_after:
                raise ModelUnavailableError(entry.error or f'{model_id}: model startup cooldown')
            # Healthy externally managed endpoints are never adopted as owned processes.
            if entry.process is None and self._health(entry.spec):
                if entry.spec.gpu_layers and entry.spec.gpu_selection in {'most_vram', 'smallest_8gb'}:
                    log.warning('%s: reusing an external server; GPU placement is unverified. '
                                'Restart that server through HANNI to apply automatic GPU selection.', model_id)
                entry.last_used = entry.loaded_at = self.clock()
                self._state(entry, 'BUSY' if entry.active else 'READY')
                return entry
            if entry.process is not None and entry.process.poll() is None:
                raise ModelUnavailableError(f'{model_id}: owned server is unhealthy; active work is not terminated')
            gate = self.gpu_load_lock if entry.spec.gpu_layers else nullcontext()
            with gate:
                started = self.clock()
                self._state(entry, 'STARTING')
                try:
                    self._admit(entry)
                    model_file = self.files.get(model_id) or os.getenv('HANNI_MODEL_FILE')
                    routing_path = (self.config.paths.data_dir/'gpu-routing.json'
                                    if entry.spec.id == self.config.models.supervisor.id else None)
                    entry.command = model_command(entry.spec, model_file, reserve_mb=self.config.models.vram_reserve_mb,
                                                  routing_path=routing_path)
                    entry.process = self._launch(entry.spec)
                    entry.startup_seconds = self.clock()-started
                    entry.loaded_at = entry.last_used = self.clock()
                    entry.error = None
                    self._state(entry, 'BUSY' if entry.active else 'READY')
                    return entry
                except Exception as exc:
                    entry.error = str(exc)
                    entry.retry_after = self.clock()+entry.spec.retry_cooldown_seconds
                    self._state(entry, 'UNHEALTHY')
                    log.warning('[ModelManager] %s degraded: %s', model_id, exc)
                    raise ModelUnavailableError(str(exc)) from exc

    @contextmanager
    def lease(self, model_id):
        entry = self.entries[model_id]
        with self.lock:
            if self.closed: raise ModelUnavailableError('Model manager is shutting down')
            entry.active += 1
        try:
            self.ensure_loaded(model_id)
            yield
        finally:
            with self.lock:
                entry.active -= 1
                entry.last_used = self.clock()
                if entry.state == 'BUSY' and not entry.active: entry.state = 'READY'
            if self.closed: self._evict(entry, force=True)

    def _evict(self, entry, *, force=False):
        if not entry.lock.acquire(blocking=False): return False
        try:
            with self.lock:
                if entry.active or entry.process is None: return False
                if not force and entry.spec.keep_loaded: return False
                process = entry.process
                entry.state = 'STOPPING'
            # New leases wait on this model's lock; other models remain responsive.
            self._stop(process)
            with self.lock:
                entry.process = None
                entry.state = 'STOPPED'
                entry.retry_after = self.clock() + (0 if force else entry.spec.retry_cooldown_seconds)
            log.info('[ModelManager] %s stopped; owned server memory released', entry.spec.id)
            return True
        finally:
            entry.lock.release()

    def sweep(self):
        resources = self._capture_resources()
        pressure = resources.ram_percent >= self.config.models.critical_ram_percent
        now = self.clock()
        for entry in self.entries.values():
            if entry.process is not None and entry.process.poll() is not None:
                entry.error = 'Owned model server exited'
                self._state(entry, 'UNHEALTHY')
            if entry.spec.keep_loaded: continue
            old_enough = now-entry.loaded_at >= entry.spec.minimum_residency_seconds
            idle = now-entry.last_used >= entry.spec.idle_unload_seconds
            if pressure or old_enough and idle:
                if self._evict(entry) and pressure:
                    log.warning('[ModelManager] memory pressure: evicted idle %s', entry.spec.id)
                    resources = self._capture_resources()
                    pressure = resources.ram_percent >= self.config.models.critical_ram_percent

    def snapshot(self):
        # Never acquire a model startup lock from UI or job status queries.
        result = {}
        with self.lock:
            for key, entry in self.entries.items():
                rss = None
                if entry.process is not None:
                    try: rss = psutil.Process(entry.process.pid).memory_info().rss/2**20
                    except (psutil.Error, TypeError): pass
                command = entry.command
                device = command[command.index('--device')+1] if '--device' in command else None
                result[key] = dict(model=entry.spec.model_file, role=entry.spec.role, endpoint=entry.spec.endpoint,
                    state=entry.state, resident=entry.state in {'READY','BUSY'}, pinned=entry.spec.keep_loaded,
                    owned=entry.process is not None, pid=getattr(entry.process, 'pid', None), device=device,
                    active_inferences=entry.active, last_used=entry.last_used, startup_seconds=entry.startup_seconds,
                    context=entry.spec.context_length, parallel=entry.spec.parallel,
                    ram_budget_mb=entry.spec.ram_budget_mb, vram_budget_mb=entry.spec.vram_budget_mb,
                    process_ram_mb=rss, idle_timeout=entry.spec.idle_unload_seconds, error=entry.error)
        return result

    def _monitor(self):
        while not self.signal.wait(5):
            try: self.sweep()
            except Exception: log.exception('[ModelManager] residency monitor failed')

    def close(self):
        self.closed = True
        self.signal.set()
        if self.worker: self.worker.join(timeout=1)
        for entry in self.entries.values(): self._evict(entry, force=True)
