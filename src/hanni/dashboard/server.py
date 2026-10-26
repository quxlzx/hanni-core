"""Loopback dashboard with same-origin chat through the existing assistant loop."""
from __future__ import annotations

import json
import os
import threading
import time
import secrets
import sqlite3
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil

from hanni.logs.redaction import redact_text
from hanni.core.activity import activity
from hanni.core.shutdown import EMERGENCY_STOP_FILENAME, FileStopStateStore
from hanni.models.registry import create_client
from hanni.models.resource_manager import snapshot_resources
from hanni.models.runtime import (gpu_inventory, gpu_routing_path, gpu_routing_state,
                                  save_gpu_routing)
from hanni.core.interaction import interaction

ASSETS = Path(__file__).parent / 'static'

class Telemetry:
    def __init__(self, config):
        self.config = config
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.data = {'sampled_at': None, 'model_status': 'checking', 'resources': None,
                     'error': None, 'safe_mode': None}
        self.worker = None

    def start(self):
        self.worker = threading.Thread(target=self._run, name='hanni-telemetry', daemon=True)
        self.worker.start()

    def _run(self):
        previous = None
        client = create_client(self.config)
        store = FileStopStateStore(self.config.paths.data_dir / EMERGENCY_STOP_FILENAME)
        # GPU/model probes can take seconds. Keep them off HTTP and speech threads.
        while not self.stop.is_set():
            try:
                resources = snapshot_resources(cpu_interval=0.1).to_dict()
                now = time.monotonic()
                network = psutil.net_io_counters()
                rates = {'receive_bps': None, 'send_bps': None}
                if previous and network:
                    elapsed = max(0.001, now - previous[0])
                    rates = {'receive_bps': max(0, network.bytes_recv - previous[1]) / elapsed,
                             'send_bps': max(0, network.bytes_sent - previous[2]) / elapsed}
                if network:
                    previous = (now, network.bytes_recv, network.bytes_sent)
                disk = psutil.disk_usage(Path.cwd().anchor)
                try:
                    battery = psutil.sensors_battery()
                except (OSError, RuntimeError):
                    battery = None
                native_model = None
                if os.environ.get('HANNI_BRIDGE_URL'):
                    from hanni.dashboard.bridge_panel import bridge_proxy
                    native_model = bridge_proxy('GET', '/model')
                    from types import SimpleNamespace
                    health = SimpleNamespace(state=native_model.get('state', 'unreachable'))
                else:
                    health = client.health()
                try:
                    safe_mode = store.load() is not None
                except Exception:
                    # A damaged emergency-stop state must fail closed without
                    # suppressing all otherwise-valid dashboard telemetry.
                    safe_mode = True
                data = {'sampled_at': time.time(), 'resources': resources,
                        'model_status': health.state, 'error': None,
                        'safe_mode': safe_mode,
                        'disk': {'percent': disk.percent, 'used_gb': disk.used / 1024**3,
                                 'total_gb': disk.total / 1024**3},
                        'network': rates, 'uptime_seconds': time.time() - psutil.boot_time(),
                        'battery': None if battery is None else
                        {'percent': battery.percent, 'plugged': battery.power_plugged}}
                if native_model:
                    data['model'] = {key: native_model.get(key) for key in ('file', 'context', 'quantization', 'context_verified')}
                    data['model_detail'] = native_model.get('detail') or native_model.get('error')
                with self.lock:
                    self.data = data
            except Exception:
                with self.lock:
                    self.data = {**self.data, 'error': 'Telemetry sample unavailable'}
            self.stop.wait(2)

    def snapshot(self):
        from hanni.models.manager import current
        manager = current()
        with self.lock:
            data = dict(self.data)
        return {**data, 'activity': activity.snapshot(),
                'model_residency': manager.snapshot() if manager else {},
                'interaction': interaction.snapshot(),
                'roles': {'assistant': self.config.models.supervisor.id},
                'model': data.get('model') or {'file': self.config.models.supervisor.model_file,
                          'quantization': self.config.models.supervisor.quantization,
                          'context': self.config.models.supervisor.context_length}}

    def close(self):
        self.stop.set()
        if self.worker:
            self.worker.join(timeout=20)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = False
    allow_reuse_address = False

    def __init__(self, port, telemetry, chat=None, *, shutdown_event=None, restart_event=None, cluster=None, cluster_power=None, cluster_terminal=None, features=None, workflows=None):
        from hanni.dashboard.chat import ChatHub
        self.telemetry = telemetry
        self.chat = chat or ChatHub()
        self.shutdown_event = shutdown_event
        self.restart_event = restart_event
        self.lifecycle_lock = threading.Lock()
        self.lifecycle_action = None
        from hanni.native.model_settings import ModelSettings
        self.model_settings = ModelSettings.from_env()
        from hanni.dashboard.gateway import workspace_contract
        from hanni.config.schema import AppConfig
        config = getattr(telemetry, 'config', None)
        self.workspace = workspace_contract(config if isinstance(config, AppConfig) else None)
        from hanni.dashboard.features import DesktopFeatures
        self.features = features if features is not None else DesktopFeatures(config if isinstance(config, AppConfig) else None)
        from hanni.dashboard.tool_access import ToolAccessControls
        self.tool_access = ToolAccessControls(self.features, self.chat)
        from hanni.dashboard.google_accounts import GoogleAccounts
        self.google_accounts = GoogleAccounts(self.features)
        from hanni.dashboard.teams import TeamsControls
        self.teams = TeamsControls(self)
        from hanni.dashboard.commands import ChatCommands
        self.chat_commands = ChatCommands(self)
        from hanni.dashboard.learning import LearningControls
        self.learning = LearningControls(self)
        from hanni.dashboard.cluster import ClusterMonitor
        self.cluster = cluster if cluster is not None else ClusterMonitor(data_dir=config.paths.data_dir if isinstance(config, AppConfig) else None)
        from hanni.dashboard.cluster_power import ClusterPower
        data_dir = config.paths.data_dir if isinstance(config, AppConfig) else None
        self.cluster_power = cluster_power if cluster_power is not None else ClusterPower(self.cluster, data_dir)
        from hanni.dashboard.cluster_terminal import ClusterTerminal
        self.cluster_terminal = cluster_terminal if cluster_terminal is not None else ClusterTerminal(self.cluster, data_dir)
        super().__init__(('127.0.0.1', port), Handler)
        from hanni.dashboard.mcp_hub import MCPHub
        self.mcp = MCPHub(config if isinstance(config, AppConfig) else None, self.features)
        from hanni.dashboard.native_mcp import NativeMCP
        self.native_mcp = NativeMCP(self.mcp)
        self.native_mcp.attach()
        from hanni.hermes.client import HermesControl
        self.hermes = HermesControl(data_dir, self.mcp, self.shutdown_event)
        from hanni.dashboard.workflows import WorkflowHub
        from hanni.compute import ComputeRegistry, ComputeScheduler
        from hanni.models.adaptive import AdaptiveModelEngine, current as current_model_routing, install as install_model_routing
        self.model_routing = current_model_routing(config) if isinstance(config, AppConfig) else None
        shared_compute = self.model_routing.compute if self.model_routing is not None else None
        self._owns_compute = shared_compute is None
        self.compute = shared_compute if shared_compute is not None else ComputeScheduler(ComputeRegistry(data_dir))
        from hanni.dashboard.inference import InferenceControl
        self.inference = InferenceControl(self.compute, data_dir, self.shutdown_event)
        self._owns_model_routing = False
        if self.model_routing is None and isinstance(config, AppConfig):
            self.model_routing = AdaptiveModelEngine(config, compute_scheduler=self.compute)
            install_model_routing(self.model_routing)
            self._owns_model_routing = True
        elif self.model_routing is not None and self.model_routing.compute is None:
            self.model_routing.compute = self.compute
        from hanni.dashboard.model_routing import ModelRoutingControls
        self.model_routing_controls = ModelRoutingControls(self.features, self.model_routing, self.shutdown_event)
        from hanni.evals.model_lab import ModelLab
        from hanni.dashboard.model_lab import ModelLabControls
        self.model_lab = ModelLab(config if isinstance(config, AppConfig) else None, self.model_routing,
            registry=lambda: self.features.registry, shutdown_event=self.shutdown_event)
        self.model_lab_controls = ModelLabControls(self.features, self.model_lab)
        from hanni.dashboard.compute import ComputeControls
        self.compute_controls = ComputeControls(self.features, self.compute, self.shutdown_event)
        self.workflows = workflows if workflows is not None else WorkflowHub(
            config if isinstance(config, AppConfig) else None, self.features, telemetry, compute=self.compute)
        self.mcp.workflows = self.workflows
        self.features.memory_explorer.workflow_reader = self.workflows.detail
        from hanni.tools.reminders import ReminderDelivery
        self.reminder_delivery = ReminderDelivery(self.features)
        self.reminder_delivery.start()
        if self.mcp.root is not None:
            from hanni.mcp.runtime import install
            install(self.mcp)

    def workspace_snapshot(self):
        result = dict(self.workspace)
        result['features'] = {**result['features'], 'restart': self.restart_event is not None,
                              'attachments': bool(self.chat.native_mode)}
        registry = self.mcp.controller_registry
        if registry is not None:
            result['capabilities'] = [
                {'name': tool.name, 'permission_level': tool.permission_level,
                 'risk_level': tool.risk_level} for tool in registry.definitions()]
            result['capability_revision'] = registry.revision
        return result

    def server_close(self):
        teams = getattr(self, 'teams', None)
        if teams is not None:
            teams.close()
        learning = getattr(self, 'learning', None)
        if learning is not None:
            learning.close()
        google = getattr(self, 'google_accounts', None)
        if google is not None:
            google.close()
        reminders = getattr(self, 'reminder_delivery', None)
        if reminders is not None:
            reminders.close()
        commands = getattr(self, 'chat_commands', None)
        if commands is not None:
            commands.close()
        hermes = getattr(self, 'hermes', None)
        if hermes is not None:
            hermes.close()
        # HTTPServer invokes this during a failed bind, before Hub construction.
        # The original launcher's occupied-port fallback must remain usable.
        inference = getattr(self, 'inference', None)
        if inference is not None:
            inference.close()
        model_lab = getattr(self, 'model_lab', None)
        if model_lab is not None:
            model_lab.close()
        model_routing = getattr(self, 'model_routing', None)
        if model_routing is not None and getattr(self, '_owns_model_routing', False):
            model_routing.close()
            from hanni.models.adaptive import uninstall
            uninstall(model_routing)
        workflows = getattr(self, 'workflows', None)
        from hanni.dashboard.workflows import close_workflows_for_cleanup
        close_workflows_for_cleanup(workflows)
        compute = getattr(self, 'compute', None)
        if compute is not None and getattr(self, '_owns_compute', True):
            compute.close()
        mcp = getattr(self, 'mcp', None)
        if mcp is not None:
            mcp.close()
        self.cluster_power.close()
        self.cluster.close()
        super().server_close()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _discard_small_body(self):
        # Windows can reset a connection on close when a rejected POST body
        # remains unread, dropping the error response. Never read unbounded data.
        try:
            size = int(self.headers.get('Content-Length', '0'))
            self.connection.settimeout(.5)
            if 0 < size <= 20000 and not self.headers.get('Transfer-Encoding'):
                self.rfile.read(size)
        except (ValueError, OSError):
            pass

    def _send(self, status, body, content_type='application/json', *, headers=None):
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; font-src 'self' data:; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True  # Tab closed/poll canceled, including WinError 10053.

    def _send_error(self, status, error):
        # Validation/dependency errors are displayed by the frontend. They must
        # obey the same loaded-secret and token redaction boundary as log sinks.
        return self._send(status, json.dumps({'error': redact_text(str(error))},
                                            allow_nan=False).encode())

    def _allowed(self, *, write=False):
        def deny(body):
            # Drain only a small, already-declared body before rejecting it.
            # Closing a Windows socket with unread POST data can discard the
            # error response with WinError 10053. Nothing here executes input.
            if write:
                self._discard_small_body()
            self._send(403, body)
            return False
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in hosts:
            return deny(b'{"error":"Invalid host"}')
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{host}' for host in hosts}:
            return deny(b'{"error":"Invalid origin"}')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return deny(b'{"error":"Cross-site request denied"}')
        if write and (origin != 'http://' + self.headers.get('Host', '') or
                      not secrets.compare_digest(self.headers.get('X-Hanni-Token', ''), self.server.chat.token)):
            return deny(b'{"error":"Reload the dashboard before sending a message."}')
        return True

    def _gpu_state(self):
        config = self.server.telemetry.config
        path = gpu_routing_path(config.paths.data_dir)
        primary_spec = config.models.supervisor
        state = gpu_routing_state(primary_spec, reserve_mb=config.models.vram_reserve_mb,
                                  routing_path=path)
        try:
            from hanni.models.manager import current
            manager = current()
            primary = config.models.supervisor.id
            current_device = (manager.snapshot().get(primary, {}).get('device') if manager else None)
        except Exception:
            current_device = None
        target = state['selected_device_id']
        state['current_device_id'] = current_device
        state['restart_required'] = bool(current_device and current_device != 'none' and target and current_device != target)
        return state

    def do_PUT(self):
        if not self._allowed(write=True): return
        if self.path.startswith('/api/inference/'):
            return self._inference_request('PUT')
        self._discard_small_body()
        return self._send(404, b'{"error":"Not found"}')

    def do_DELETE(self):
        if not self._allowed(write=True): return
        if self.path.startswith('/api/inference/'):
            return self._inference_request('DELETE')
        self._discard_small_body()
        return self._send(404, b'{"error":"Not found"}')

    def _inference_request(self, method):
        from hanni.dashboard.inference import InferenceError
        import httpx
        if not secrets.compare_digest(self.headers.get('X-Hanni-Token', ''), self.server.chat.token):
            return self._send(403, b'{"error":"Reload the dashboard before reading model data."}')
        stream = None
        streaming = False
        try:
            self.server.inference.route(method, self.path)
            data = None
            if method in {'POST', 'PUT'}:
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or size > 4 * 1024 * 1024 or size < 0:
                    self.close_connection = True
                    return self._send(413, b'{"error":"Inference request exceeds 4 MiB."}')
                if size:
                    if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                        self._discard_small_body()
                        return self._send(415, b'{"error":"JSON required"}')
                    self.connection.settimeout(5)
                    raw = self.rfile.read(size)
                    if len(raw) != size: raise ValueError('Incomplete inference request')
                    data = json.loads(raw)
                    if not isinstance(data, dict): raise ValueError('JSON object required')
            if method == 'POST' and self.path.endswith('/chat'):
                stream = self.server.inference.stream(self.path, data)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Connection', 'close')
                self.end_headers()
                streaming = True
                self.close_connection = True
                for chunk in stream.chunks():
                    self.wfile.write(chunk)
                    self.wfile.flush()
                return
            result = self.server.inference.request(method, self.path, data)
            if self.path.split('?', 1)[0].endswith('/logs'):
                result = {'text': redact_text(result.get('text', ''))}
            return self._send(200, json.dumps(result, allow_nan=False).encode())
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        except (InferenceError, httpx.HTTPError, ValueError, OSError, sqlite3.Error) as exc:
            if streaming:
                self.close_connection = True
            else:
                self._send_error(getattr(exc, 'status', 503), exc)
        finally:
            if stream is not None:
                stream.close()

    def do_GET(self):
        if not self._allowed(): return
        route = self.path.split('?', 1)[0]
        if route == '/api/chat/file':
            if not secrets.compare_digest(self.headers.get('X-Hanni-Token', ''), self.server.chat.token):
                return self._send(403, b'{"error":"Reload the dashboard before reading files."}')
            try:
                query = parse_qs(urlsplit(self.path).query)
                with self.server.chat.lock:
                    conversation = self.server.chat._conversation(query.get('conversation', ['default'])[0])
                    name, content = self.server.chat.files.read(query.get('id', [''])[0], conversation)
                from urllib.parse import quote
                return self._send(200, content, 'application/octet-stream',
                    headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(name, safe='')})
            except ValueError as exc:
                return self._send_error(400, exc)
            except sqlite3.Error:
                return self._send(503, b'{"error":"Local file storage is unavailable."}')
        if route == '/api/native-mcp/tools':
            if not self.native_mcp_authorized(): return
            try:
                return self._send(200, json.dumps(self.server.native_mcp.tools()).encode())
            except (ValueError, RuntimeError, OSError) as exc:
                return self._send_error(503, exc)
        if route.startswith('/api/inference/'):
            return self._inference_request('GET')
        private_routes = {'/api/learning', '/api/google/accounts', '/api/integrations/teams', '/api/tool-access', '/api/chat/commands', '/api/chat/command', '/api/model-settings', '/api/model-output', '/api/model-reasoning', '/api/productivity', '/api/memory', '/api/calendar',
                          '/api/agents', '/api/awareness', '/api/voice', '/api/notifications',
                          '/api/mcp', '/api/mcp/export', '/api/mcp/office', '/api/hermes', '/api/executions', '/api/tasks', '/api/workflows', '/api/compute', '/api/model-routing', '/api/model-lab',
                          '/api/bridge/tasks', '/api/bridge/tools', '/api/cron/jobs', '/api/skills',
                          '/api/learning/journey', '/api/learning/source', '/api/learning/skill', '/api/learning/batches', '/api/learning/export'}
        if route in private_routes or route.startswith(('/api/tasks/', '/api/workflows/', '/api/memory/', '/api/model-lab/', '/api/bridge/task/')):
            if not secrets.compare_digest(self.headers.get('X-Hanni-Token', ''), self.server.chat.token):
                return self._send(403, b'{"error":"Reload the dashboard before reading personal workspace data."}')
            try:
                query = {key: values[0] for key, values in parse_qs(urlsplit(self.path).query,
                    keep_blank_values=route == '/api/model-lab/preflight').items()}
                feature = self.server.features
                if route == '/api/chat/commands':
                    from hanni.dashboard.commands import CATALOG
                    result = {'commands': CATALOG}
                elif route == '/api/chat/command': result = self.server.chat_commands.result(query.get('id'))
                elif route == '/api/model-settings': result = self.server.model_settings.snapshot()
                elif route == '/api/model-output': result = self.server.model_settings.output_snapshot()
                elif route == '/api/model-reasoning': result = self.server.model_settings.reasoning_snapshot()
                elif route == '/api/tool-access': result = self.server.tool_access.snapshot()
                elif route == '/api/google/accounts': result = self.server.google_accounts.snapshot()
                elif route == '/api/integrations/teams': result = self.server.teams.snapshot()
                elif route == '/api/productivity': result = feature.productivity()
                elif route == '/api/memory': result = feature.memories(query.get('q', ''))
                elif route == '/api/memory/explorer': result = feature.memory_explorer.browse(query)
                elif route == '/api/memory/suggestions': result = feature.memory_explorer.suggestions(query)
                elif route.startswith('/api/memory/record/'):
                    result = feature.memory_explorer.detail(route.removeprefix('/api/memory/record/'), query)
                elif route.startswith('/api/memory/project/'):
                    result = feature.memory_explorer.project(route.removeprefix('/api/memory/project/'))
                elif route.startswith('/api/memory/'):
                    return self._send(404, b'{"error":"Unknown memory view"}')
                elif route == '/api/calendar': result = feature.calendar(query)
                elif route == '/api/agents': result = feature.agents(self.server.chat.snapshot(), self.server.workspace_snapshot())
                elif route == '/api/mcp': result = self.server.mcp.snapshot()
                elif route == '/api/mcp/office': result = self.server.mcp.office_status()
                elif route == '/api/bridge/tools':
                    from hanni.dashboard.bridge_panel import bridge_proxy
                    result = bridge_proxy('GET', '/tools')
                elif route == '/api/bridge/tasks':
                    from hanni.dashboard.bridge_panel import bridge_proxy
                    result = bridge_proxy('GET', '/tasks')
                elif route.startswith('/api/bridge/task/'):
                    from hanni.dashboard.bridge_panel import bridge_task_detail
                    result = bridge_task_detail(route.removeprefix('/api/bridge/task/'))
                elif route == '/api/cron/jobs':
                    from hanni.dashboard.bridge_panel import cron_jobs
                    result = cron_jobs()
                elif route == '/api/skills':
                    from hanni.dashboard.bridge_panel import skills_list
                    result = skills_list()
                elif route == '/api/learning': result = self.server.learning.snapshot()
                elif route == '/api/learning/journey': result = self.server.learning.journey()
                elif route in {'/api/learning/source', '/api/learning/skill'}:
                    engine = self.server.learning.engine
                    if not engine: raise RuntimeError('Learning is unavailable.')
                    result = engine.source(query.get('id', '')) if route.endswith('/source') else engine.skills.detail(query.get('name', ''), track=True)
                elif route in {'/api/learning/batches', '/api/learning/export'}:
                    from hanni.native.training import TrainingStore
                    if not feature.root: raise RuntimeError('Training data is unavailable.')
                    training = TrainingStore(feature.root)
                    result = training.batches() if route.endswith('/batches') else training.export(query.get('batch', ''), query.get('format', 'trajectory'))
                elif route == '/api/hermes': result = self.server.hermes.snapshot()
                elif route == '/api/mcp/export': result = self.server.mcp.export_configs()
                elif route in {'/api/workflows', '/api/tasks'}:
                    result = self.server.workflows.snapshot(limit=int(query.get('limit', '50')))
                elif route == '/api/model-routing':
                    from hanni.dashboard.model_routing import routing_snapshot
                    result = routing_snapshot(self.server, refresh=query.get('refresh') == '1')
                elif route == '/api/model-lab':
                    if query.get('refresh') == '1' and self.server.model_routing is not None:
                        self.server.model_routing.request_refresh()
                    if self.server.model_routing is not None:
                        self.server.model_routing.start_monitor()
                    result = self.server.model_lab.snapshot(query)
                elif route.startswith('/api/model-lab/run/'):
                    result = self.server.model_lab.detail(route.removeprefix('/api/model-lab/run/'),
                        offset=int(query.get('offset', '0')), limit=int(query.get('limit', '100')))
                elif route.startswith('/api/model-lab/export/'):
                    if set(query) - {'offset', 'limit', 'representation'}:
                        raise ValueError('Invalid export page.')
                    result = self.server.model_lab.export(route.removeprefix('/api/model-lab/export/'),
                        offset=int(query.get('offset', '0')), limit=int(query.get('limit', '500')),
                        representation=query.get('representation'))
                elif route == '/api/model-lab/compare':
                    result = self.server.model_lab.compare(query.get('ids', '').split(','))
                elif route == '/api/model-lab/preflight':
                    if set(query) != {'suite_id', 'endpoint_id', 'max_cases', 'max_tokens'}:
                        raise ValueError('Invalid preflight fields.')
                    result = self.server.model_lab.preflight(query['suite_id'], query['endpoint_id'] or None,
                        int(query['max_cases']), int(query['max_tokens']))
                elif route.startswith('/api/model-lab/'):
                    return self._send(404, b'{"error":"Unknown Model Lab view"}')
                elif route == '/api/compute':
                    self.server.compute.start_monitor()
                    if query.get('refresh') == '1':
                        self.server.compute.request_refresh()
                    result = self.server.compute.registry.snapshot()
                    root = self.server.compute.registry.root
                    result['control_blocked_reason'] = ('This dashboard is shutting down.' if self.server.shutdown_event is not None and self.server.shutdown_event.is_set()
                        else 'Compute controls are blocked while HANNI is in Safe Mode.' if root is not None and FileStopStateStore.for_data_dir(root.parent).load() is not None else None)
                elif route.startswith(('/api/workflows/', '/api/tasks/')):
                    result = self.server.workflows.detail(route.removeprefix('/api/workflows/').removeprefix('/api/tasks/'))
                elif route == '/api/executions':
                    from hanni.dashboard.executions import execution_snapshot
                    result = execution_snapshot(self.server, limit=int(query.get('limit', '50')))
                elif route == '/api/awareness': result = feature.awareness()
                elif route == '/api/voice':
                    from hanni.dashboard.voice import voice_control
                    result = voice_control.snapshot()
                else:
                    result = feature.notifications(telemetry=self.server.telemetry.snapshot(),
                        cluster=self.server.cluster.snapshot(), contract=self.server.workspace_snapshot())
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            except (ValueError, TypeError):
                return self._send(400, b'{"error":"Choose valid workspace fields and refresh before retrying."}')
            except (OSError, RuntimeError, sqlite3.Error):
                return self._send(503, b'{"error":"The local workspace feature is unavailable. Existing data was retained."}')
        if route == '/api/chat/conversations':
            try:
                return self._send(200, json.dumps({'conversations': self.server.chat.conversations()}).encode())
            except sqlite3.Error:
                return self._send(503, b'{"error":"Local conversation storage is unavailable."}')
        if route == '/api/chat':
            try:
                query = parse_qs(urlsplit(self.path).query)
                before = int(query.get('before', ['0'])[0])
                if not 0 <= before < 2**63: raise ValueError()
                snapshot = self.server.chat.snapshot(before, conversation=query.get('conversation', [None])[0])
            except ValueError:
                return self._send(400, b'{"error":"Invalid conversation or history cursor"}')
            return self._send(200, json.dumps(snapshot, allow_nan=False).encode())
        if route == '/api/state':
            return self._send(200, json.dumps(self.server.telemetry.snapshot(), allow_nan=False).encode())
        if route == '/api/workspace':
            return self._send(200, json.dumps(self.server.workspace_snapshot(), allow_nan=False).encode())
        if route == '/api/cluster':
            self.server.cluster.start()
            self.server.cluster_power.start()
            state = self.server.cluster_power.project(self.server.cluster.snapshot())
            state = self.server.cluster_terminal.project(state)
            return self._send(200, json.dumps(state, allow_nan=False).encode())
        if route == '/api/activity':
            from hanni.dashboard.gateway import activity_snapshot
            config = getattr(self.server.telemetry, 'config', None)
            data_dir = config.paths.data_dir if config else None
            return self._send(200, json.dumps(activity_snapshot(data_dir), allow_nan=False).encode())
        if route == '/api/gpu-routing':
            try:
                return self._send(200, json.dumps(self._gpu_state(), allow_nan=False).encode())
            except (OSError, RuntimeError, ValueError) as exc:
                return self._send_error(503, exc)
        if route == '/api/audio-devices':
            try:
                from hanni.speech.audio_devices import routing_state
                state = routing_state(self.server.telemetry.config.paths.data_dir)
                return self._send(200, json.dumps(state, allow_nan=False).encode())
            except (OSError, RuntimeError, ValueError) as exc:
                return self._send_error(503, exc)
        files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css',
                 '/THIRD_PARTY_NOTICES.txt': 'THIRD_PARTY_NOTICES.txt'}
        if route not in files:
            return self._send(404, b'{"error":"Not found"}')
        path = ASSETS / files[route]
        mime = {'app.js': 'text/javascript', 'style.css': 'text/css', 'index.html': 'text/html',
                'THIRD_PARTY_NOTICES.txt': 'text/plain'}
        self._send(200, path.read_bytes(), mime[path.name] + '; charset=utf-8')

    def _sandbox_inference(self):
        # Same existing loopback listener/Host protection; restricted task token
        # replaces owner UI credentials only for this pure-inference route.
        if not self._allowed(): return
        try:
            registry = self.server.workflows.registry
            config = self.server.telemetry.config
            if registry is None or self.server.model_routing is None:
                raise ValueError('The original controller is unavailable.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('JSON required')
            size = int(self.headers.get('Content-Length', '0'))
            if self.headers.get('Transfer-Encoding') or not 0 < size <= 131072:
                raise ValueError('Sandbox inference payload exceeds its bound.')
            self.connection.settimeout(5)
            raw = self.rfile.read(size)
            if len(raw) != size: raise ValueError('Incomplete inference request')
            authorization = self.headers.get('Authorization', '')
            if not authorization.startswith('Bearer '): raise ValueError('Task credential required')
            from hanni.compute.harnesses import SandboxJobs
            result = SandboxJobs(config.paths.data_dir).gateway(authorization[7:], json.loads(raw),
                engine=self.server.model_routing,
                guard=lambda: registry.context.emergency_stop.guard('sandbox inference'))
            return self._send(200, json.dumps(result, allow_nan=False).encode())
        except (ValueError, RuntimeError, OSError, sqlite3.Error, AttributeError) as exc:
            return self._send_error(403, exc)

    def native_mcp_authorized(self):
        if not self.server.native_mcp.authorized(self.headers.get('Authorization')):
            self._discard_small_body()
            self._send(403, b'{"error":"Native MCP requires the owning agent credential."}')
            return False
        return True

    def native_mcp_call(self):
        if not self._allowed() or not self.native_mcp_authorized(): return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.headers.get('Transfer-Encoding') or not 0 < length <= 1024:
                raise ValueError('Invalid native MCP request.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or set(body) != {'action_id'} or not isinstance(body['action_id'], str):
                raise ValueError('Supply one authorized MCP action ID.')
            result = self.server.native_mcp.call(body['action_id'])
            return self._send(200, json.dumps(result).encode())
        except (ValueError, KeyError, RuntimeError) as exc:
            return self._send_error(409, exc)
        except (OSError, sqlite3.Error) as exc:
            return self._send_error(503, exc)

    def do_POST(self):
        if self.path == '/api/native-mcp/call':
            return self.native_mcp_call()
        if self.path == '/api/sandbox/v1/chat/completions':
            return self._sandbox_inference()
        if not self._allowed(write=True): return
        if self.path.startswith('/api/inference/'):
            return self._inference_request('POST')
        if self.path.startswith('/api/bridge/') or self.path.startswith('/api/cron/job/') or self.path == '/api/cron/jobs':
            if not secrets.compare_digest(self.headers.get('X-Hanni-Token', ''),
                                          getattr(self.server, 'chat', None) and self.server.chat.token or ''):
                return self._send(403, b'{"error":"Reload the dashboard before authorizing actions."}')
            from hanni.dashboard.bridge_panel import bridge_proxy, bridge_decision, cron_set, cron_create, cron_root
            try:
                length = int(self.headers.get('Content-Length') or 0)
                if self.headers.get('Transfer-Encoding') or not 0 < length <= 65536:
                    return self._send(413, b'{"error":"Message too large or missing length"}')
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                if self.path == '/api/cron/jobs':
                    if not self.server.chat.native_mode:
                        raise ValueError('Repeating agent tasks require the native chat launcher.')
                    result = cron_create(body, self.server.chat)
                elif self.path.startswith('/api/bridge/action/'):
                    result = bridge_decision(self.path.removeprefix('/api/bridge/action/'), body)
                elif self.path == '/api/bridge/submit':
                    result = bridge_proxy('POST', '/tasks', body)
                elif self.path.startswith('/api/bridge/cancel/'):
                    result = bridge_proxy('POST', '/tasks/' + self.path.removeprefix('/api/bridge/cancel/') + '/cancel', {})
                elif self.path.startswith('/api/cron/job/'):
                    parts = self.path.split('/')
                    if len(parts) != 6 or parts[5] not in {'enable', 'disable', 'delete'}:
                        raise ValueError('Unknown cron operation')
                    if parts[5] == 'delete':
                        from hanni.native.scheduling import manage_schedules
                        result = manage_schedules(cron_root(), 'delete', parts[4])
                    else:
                        result = cron_set(parts[4], parts[5] == 'enable')
                else:
                    return self._send(404, b'{"error":"Unknown bridge operation"}')
            except (ValueError, KeyError) as exc:
                return self._send_error(400, exc)
            return self._send(502 if result.get('error') else 200, json.dumps(result, default=str).encode())
        if self.path not in {'/api/learning', '/api/google/accounts', '/api/integrations/teams', '/api/tool-access', '/api/chat/files', '/api/chat/command', '/api/model-settings', '/api/model-output', '/api/model-reasoning', '/api/chat', '/api/chat/conversations', '/api/chat/clear', '/api/gpu-routing', '/api/audio-devices', '/api/shutdown', '/api/restart', '/api/cluster/power', '/api/cluster/terminal', '/api/productivity', '/api/memory', '/api/notifications', '/api/voice', '/api/mcp', '/api/hermes', '/api/workflows', '/api/tasks', '/api/compute', '/api/model-routing', '/api/model-lab'}:
            self._discard_small_body()
            return self._send(404, b'{"error":"Not found"}')
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self._discard_small_body()
            return self._send(415, b'{"error":"JSON required"}')
        data = {}
        try:
            size = int(self.headers.get('Content-Length', '0'))
            limit = 12 * 1024 * 1024 if self.path == '/api/chat/files' else 262144 if self.path == '/api/mcp' else 65536 if self.path in {'/api/learning', '/api/google/accounts', '/api/integrations/teams', '/api/workflows', '/api/tasks'} else 20000
            if self.headers.get('Transfer-Encoding') or not 0 < size <= limit:
                return self._send(413, b'{"error":"Message too large or missing length"}')
            self.connection.settimeout(5)
            raw = self.rfile.read(size)
            if len(raw) != size: raise ValueError('Incomplete request')
            data = json.loads(raw)
            if not isinstance(data, dict): raise ValueError('JSON object required')
            if self.path == '/api/learning':
                result = self.server.learning.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False, default=str).encode())
            if self.path == '/api/integrations/teams':
                result = self.server.teams.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/google/accounts':
                result = self.server.google_accounts.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/tool-access':
                result = self.server.tool_access.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/chat/files':
                if not self.server.chat.native_mode:
                    raise RuntimeError('Start native chat with START_BRAIN.cmd to attach files.')
                conversation = data.get('conversation', 'default')
                with self.server.chat.lock:
                    self.server.chat._conversation(conversation)
                    if self.server.chat.closed or self.server.chat.stopping:
                        raise RuntimeError('Chat is stopping. Files were not uploaded.')
                if data.get('operation') == 'add' and set(data) == {'operation', 'id', 'conversation', 'name', 'data'}:
                    result = self.server.chat.files.add(data['id'], conversation, data['name'], data['data'])
                    return self._send(201, json.dumps(result).encode())
                if data.get('operation') == 'remove' and set(data) == {'operation', 'id', 'conversation'}:
                    self.server.chat.files.remove(data['id'], conversation)
                    return self._send(200, b'{"removed":true}')
                raise ValueError('Choose a valid file upload or removal.')
            if self.path == '/api/chat/command':
                result = self.server.chat_commands.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/model-output':
                with self.server.lifecycle_lock:
                    if self.server.lifecycle_action:
                        raise RuntimeError('The assistant is restarting or stopping.')
                    result = self.server.features.ledger.execute(data.get('id'), data,
                        lambda: self.server.model_settings.save_output(data))
                return self._send(200, json.dumps(result).encode())
            if self.path == '/api/model-reasoning':
                with self.server.lifecycle_lock:
                    if self.server.lifecycle_action:
                        raise RuntimeError('The assistant is restarting or stopping.')
                    result = self.server.features.ledger.execute(data.get('id'), data,
                        lambda: self.server.model_settings.save_reasoning(data))
                return self._send(200, json.dumps(result).encode())
            if self.path == '/api/model-settings':
                with self.server.lifecycle_lock, self.server.chat.lock:
                    self.server.chat_commands.require_no_compression()
                    if self.server.lifecycle_action:
                        raise RuntimeError('The assistant is restarting or stopping.')
                    if self.server.chat.snapshot()['busy'] or self.server.chat.queue:
                        raise RuntimeError('Wait for the current conversation to finish before changing models.')
                    from hanni.dashboard.bridge_panel import bridge_proxy
                    from hanni.hermes.state import TERMINAL
                    tasks = bridge_proxy('GET', '/tasks')
                    if tasks.get('error'):
                        raise RuntimeError('Cannot verify active tasks. Reconnect to the agent before changing models.')
                    if any(task.get('state') not in TERMINAL for task in tasks.get('tasks', [])):
                        raise RuntimeError('Finish or cancel active tasks before changing models.')
                    result = self.server.model_settings.execute(data)
                    if self.server.model_settings.pending():
                        self.server.chat.ready = False
                return self._send(200, json.dumps(result).encode())
            if self.path == '/api/model-routing':
                result = self.server.model_routing_controls.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/model-lab':
                result = self.server.model_lab_controls.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/compute':
                result = self.server.compute_controls.execute(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path in {'/api/workflows', '/api/tasks'}:
                if self.server.shutdown_event is not None and self.server.shutdown_event.is_set():
                    raise RuntimeError('This dashboard is shutting down.')
                result = self.server.workflows.mutate(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/mcp':
                if self.server.shutdown_event is not None and self.server.shutdown_event.is_set():
                    raise RuntimeError('This dashboard is shutting down.')
                result = self.server.mcp.mutate(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/hermes':
                result = self.server.hermes.mutate(data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path in {'/api/productivity', '/api/memory', '/api/notifications', '/api/voice'}:
                if self.server.shutdown_event is not None and self.server.shutdown_event.is_set():
                    raise RuntimeError('This dashboard is shutting down.')
                if self.path == '/api/voice':
                    from hanni.dashboard.voice import voice_control
                    result = voice_control.execute(data)
                else:
                    result = self.server.features.mutate(self.path.removeprefix('/api/'), data)
                return self._send(200, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/cluster/terminal':
                if self.server.shutdown_event is not None and self.server.shutdown_event.is_set():
                    raise RuntimeError('This dashboard is shutting down.')
                result = self.server.cluster_terminal.execute(data)
                return self._send(202, json.dumps(result, allow_nan=False).encode())
            if self.path == '/api/cluster/power':
                if self.server.shutdown_event is not None and self.server.shutdown_event.is_set():
                    raise RuntimeError('This dashboard is shutting down.')
                result = self.server.cluster_power.execute(data)
                return self._send(200 if result['status'] == 'failed' else 202,
                                  json.dumps(result, allow_nan=False).encode())
            if self.path in {'/api/shutdown', '/api/restart'}:
                if data: raise ValueError('No arguments expected')
                if self.server.shutdown_event is None:
                    return self._send(503, b'{"error":"This dashboard cannot stop the launcher."}')
                restarting = self.path == '/api/restart'
                if restarting and self.server.restart_event is None:
                    return self._send(503, b'{"error":"This dashboard cannot restart the launcher."}')
                with self.server.lifecycle_lock:
                    if self.server.shutdown_event.is_set():
                        if self.server.lifecycle_action != self.path:
                            return self._send(409, b'{"error":"A session change is already in progress."}')
                    else:
                        self.server.lifecycle_action = self.path
                        if restarting:
                            self.server.restart_event.set()
                        self.server.chat.request_shutdown()
                        self.server.shutdown_event.set()
                    self._send(202, b'{"restarting":true}' if restarting else b'{"stopping":true}')
                return
            if self.path == '/api/gpu-routing':
                mode = data.get('mode')
                config = self.server.telemetry.config
                path = gpu_routing_path(config.paths.data_dir)
                if mode == 'auto' and set(data) == {'mode'}:
                    save_gpu_routing(path, mode='auto')
                elif mode == 'manual' and set(data) == {'mode', 'device_id'} and isinstance(data.get('device_id'), str):
                    devices = gpu_inventory()
                    matches = [device for device in devices if device.id == data['device_id']]
                    if len(matches) != 1:
                        raise ValueError('Selected GPU is no longer available')
                    save_gpu_routing(path, mode='manual', device=matches[0])
                else:
                    raise ValueError('Expected AUTO or a detected GPU device')
                return self._send(200, json.dumps(self._gpu_state(), allow_nan=False).encode())
            if self.path == '/api/audio-devices':
                if set(data) != {'input_id', 'output_id'}:
                    raise ValueError('Choose a detected microphone and speaker')
                from hanni.speech.audio_devices import routing_path, routing_state, save_selection
                root = self.server.telemetry.config.paths.data_dir
                save_selection(routing_path(root), input_id=data['input_id'], output_id=data['output_id'])
                return self._send(200, json.dumps(routing_state(root), allow_nan=False).encode())
            if self.path == '/api/chat/clear':
                if data: raise ValueError('No arguments expected')
                self.server.chat.clear()
                return self._send(200, b'{"cleared":true}')
            if self.path == '/api/chat/conversations':
                if set(data) != {'id'}: raise ValueError('Expected conversation ID')
                key = self.server.chat.create_conversation(data['id'])
                return self._send(201, json.dumps({'id': key}).encode())
            if not {'id', 'message'} <= set(data) or set(data) - {'id', 'message', 'conversation', 'attachments'}:
                raise ValueError('Expected id and message')
            if data.get('attachments') and not self.server.chat.native_mode:
                raise ValueError('Files require native chat. Start HANNI with START_BRAIN.cmd.')
            if data.get('attachments'):
                with self.server.chat.lock:
                    identifiers = self.server.chat.files.validate(data['attachments'], data.get('conversation', 'default'), data['id'])
                    images = any(self.server.chat.db.execute('SELECT media_type FROM chat_files WHERE id=?', (key,)).fetchone()[0].startswith('image/') for key in identifiers)
                    accepted = self.server.chat.db.execute('SELECT 1 FROM messages WHERE turn=? LIMIT 1', (data['id'],)).fetchone()
                if images and not accepted:
                    from hanni.native.provider import NativeClient
                    status = NativeClient(self.server.model_settings.reasoning_model()).status()
                    if not status.get('ready'):
                        raise ValueError('Connect the selected model before sending images. Your attached images have been kept.')
                    if status.get('image_input_supported') is False:
                        raise ValueError('The selected model does not accept images. Choose an image-capable model in Models, then send again. Your attached images have been kept.')
            key = self.server.chat.submit(data['id'], data['message'], data.get('conversation'), data.get('attachments'))
            return self._send(202, json.dumps({'id':key, 'accepted':True}).encode())
        except ValueError as exc:
            if self.path in {'/api/learning', '/api/google/accounts', '/api/integrations/teams', '/api/tool-access', '/api/chat/files', '/api/chat/command', '/api/model-settings', '/api/gpu-routing', '/api/audio-devices', '/api/cluster/power', '/api/cluster/terminal', '/api/productivity', '/api/memory', '/api/notifications', '/api/voice', '/api/mcp', '/api/workflows', '/api/tasks', '/api/compute', '/api/model-lab'} or (self.path == '/api/chat' and isinstance(data, dict) and 'attachments' in data):
                return self._send_error(400, exc)
            return self._send(400, b'{"error":"Enter a valid message (maximum 4000 characters)."}')
        except UnicodeError:
            return self._send(400, b'{"error":"Enter a valid message (maximum 4000 characters)."}')
        except RuntimeError as exc:
            return self._send_error(409, exc)
        except sqlite3.Error:
            return self._send(503, b'{"error":"Local storage is unavailable. No automatic reset or retry was performed."}')
        except (OSError, TimeoutError):
            self.close_connection = True
