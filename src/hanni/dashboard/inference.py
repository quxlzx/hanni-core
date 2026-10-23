"""Native desktop adapter for the imported HANNI Cluster Control deployment.

The existing Linux controller owns service lifecycle, GPU admission, exact model
readiness, history and stream accounting. The Windows desktop authenticates over
the owner's configured SSH path; credentials never reach the browser or disk.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from hanni.core.shutdown import FileStopStateStore
from hanni.logs.redaction import redact_text, register_secret

MODEL_IDS = frozenset({'flash-next', 'swift-1.5', 'nex-n2-mini', 'mellum-2.1'})


class InferenceError(RuntimeError):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class InferenceControl:
    def __init__(self, compute, data_dir, shutdown_event=None):
        self.compute = compute
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self.shutdown_event = shutdown_event
        self.lock = threading.RLock()
        self.credential = None
        self.binding = None
        self.closed = False

    def _connection(self):
        with self.lock:
            if self.closed or self.data_dir is None:
                raise InferenceError('Inference control requires a configured Hanni session.')
            self.compute.registry.reload()
            node = self.compute.registry.node('hanni')
            address = node.get('tailscale_ip') or node.get('lan_ip')
            if not address:
                raise InferenceError('Configure the HANNI host in the private compute deployment.')
            binding = self.compute.transport._node_binding(node)
            secret = os.environ.get('HANNI_CONTROL_TOKEN', '')
            if binding != self.binding:
                self.credential = None
                self.binding = binding
            if not secret and self.credential is None:
                username = node.get('username')
                if not username or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}', username):
                    raise InferenceError('A configured SSH account is required for inference control.')
                # Fixed source, never browser-supplied paths, destinations or commands.
                path = f'/home/{username}/hanni-control/.env'
                program = ('import pathlib,sys; rows=pathlib.Path(' + repr(path) + ').read_text().splitlines(); '
                           'sys.stdout.write(next((r.split("=",1)[1] for r in rows '
                           'if r.startswith("HANNI_TOKEN=")),""))')
                try:
                    transport = self.compute.transport
                    result = subprocess.run(transport._ssh(node, transport._address(node)) +
                        ['python3 -c ' + shlex.quote(program)], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    value = result.stdout.decode('utf-8').strip().strip('\"\'')
                    if result.returncode or not 32 <= len(value) <= 256:
                        raise InferenceError('The existing control-center credential is unavailable. Check SSH or HANNI_CONTROL_TOKEN.')
                    self.credential = value
                except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
                    raise InferenceError('The existing control-center credential could not be read through trusted SSH.') from None
            secret = secret or self.credential
            if not secret or not 32 <= len(secret) <= 256:
                raise InferenceError('The control-center access token is unavailable.')
            register_secret('HANNI_CONTROL_TOKEN', secret)
            return f'http://{address}:8200', {'Authorization': 'Bearer ' + secret}

    @staticmethod
    def route(method, path):
        parts = urlsplit(path)
        route = parts.path.removeprefix('/api/inference')
        if route in {'/models', '/hosts'} and method == 'GET' and not parts.query:
            return '/api' + route
        match = re.fullmatch(r'/models/([a-z0-9.-]+)(?:/([a-z]+))?', route)
        if match and match[1] in MODEL_IDS:
            action = match[2]
            allowed = (method == 'GET' and action in {None, 'health', 'logs', 'metrics', 'history'}
                       or method == 'POST' and action in {'start', 'stop', 'restart', 'chat', 'cancel'}
                       or method in {'PUT', 'DELETE'} and action == 'history')
            if allowed:
                query = parse_qs(parts.query, keep_blank_values=True)
                if query and (action != 'logs' or method != 'GET' or set(query) != {'lines'}
                              or len(query['lines']) != 1 or not query['lines'][0].isdigit()
                              or not 1 <= int(query['lines'][0]) <= 1000):
                    raise InferenceError('Invalid inference query.', 400)
                return '/api' + route + ('?' + parts.query if parts.query else '')
        if method == 'GET' and route in {'/hosts/hanni/metrics', '/hosts/wonyoung/metrics'} and not parts.query:
            return '/api' + route
        raise InferenceError('Unknown inference operation.', 404)

    def guard(self, method, path):
        action = urlsplit(path).path.rsplit('/', 1)[-1]
        if method in {'GET', 'DELETE', 'PUT'} or action == 'cancel':
            return
        if self.closed or self.shutdown_event is not None and self.shutdown_event.is_set():
            raise InferenceError('Hanni is shutting down.', 409)
        if self.data_dir is None or FileStopStateStore.for_data_dir(self.data_dir).load() is not None:
            raise InferenceError('Inference actions are blocked while Hanni is in Safe Mode.', 423)
        if action in {'stop', 'restart'} and '/flash-next/' in path:
            raise InferenceError('Flash-Next stop/restart remains protected by the imported controller.', 423)

    @staticmethod
    def validate_body(method, route, body):
        action = urlsplit(route).path.rsplit('/', 1)[-1]
        if action == 'chat' or method == 'PUT':
            from pydantic import BaseModel, ConfigDict, Field, ValidationError
            class Message(BaseModel):
                model_config = ConfigDict(extra='forbid')
                role: str = Field(pattern='^(system|user|assistant)$')
                content: str = Field(max_length=1500000)
            class History(BaseModel):
                model_config = ConfigDict(extra='forbid')
                messages: list[Message] = Field(max_length=200)
            class Chat(History):
                messages: list[Message] = Field(min_length=1, max_length=200)
                temperature: float = Field(default=.7, ge=0, le=2, allow_inf_nan=False)
                top_p: float = Field(default=.95, gt=0, le=1, allow_inf_nan=False)
                max_tokens: int = Field(default=512, ge=1, le=8192, strict=True)
                reasoning: bool | None = Field(default=None, strict=True)
                reasoning_budget: int | None = Field(default=None, ge=0, le=4096, strict=True)
            try:
                return (Chat if action == 'chat' else History).model_validate(body).model_dump(exclude_none=True)
            except ValidationError:
                raise InferenceError('Choose valid chat parameters and messages.', 422) from None
        if body not in (None, {}):
            raise InferenceError('This inference operation takes no arguments.', 400)
        return None

    def audit(self, route, status):
        if self.data_dir is None:
            return
        path = self.data_dir / 'inference-control' / 'audit.sqlite'
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=5) as db:
            db.execute('CREATE TABLE IF NOT EXISTS operations (time REAL, route TEXT, status INTEGER)')
            db.execute('INSERT INTO operations VALUES (?,?,?)', (time.time(), route, status))

    def request(self, method, path, body=None):
        route = self.route(method, path)
        self.guard(method, path)
        payload = self.validate_body(method, route, body)
        url, headers = self._connection()
        try:
            with httpx.Client(timeout=25, trust_env=False, follow_redirects=False) as client:
                self.guard(method, path)
                response = client.request(method, url + route, headers=headers, json=payload)
                if response.is_redirect:
                    raise InferenceError('Inference redirects are refused.', 502)
                data = response.json()
                if method != 'GET':
                    self.audit(route, response.status_code)
                if response.is_error:
                    if response.status_code == 401:
                        with self.lock:
                            self.credential = None
                    error = data.get('error', {})
                    raise InferenceError(redact_text(error.get('message', 'Inference operation failed.')),
                                         response.status_code)
                # Legacy deployed servers remain readable; new evidence frames
                # are validated as data and never alter task/privacy authority.
                from hanni.models.endpoint_contract import validate
                for row in data if isinstance(data,list) else [data]:
                    if isinstance(row,dict) and 'endpoint_contract' in row:
                        frame=row['endpoint_contract']
                        validate(frame)
                        if frame['endpoint_id']!=row.get('id') or frame['model_id']!=row.get('model'):
                            raise ValueError('Controller endpoint evidence does not match its registry row.')
                return data
        except (httpx.HTTPError, ValueError):
            raise InferenceError('The private inference controller is unavailable; saved conversations were retained.') from None

    def stream(self, path, body):
        route = self.route('POST', path)
        self.guard('POST', path)
        payload = self.validate_body('POST', route, body)
        url, headers = self._connection()
        return _InferenceStream(self, url + route, headers, payload, path)

    def close(self):
        self.closed = True
        self.credential = None


class _InferenceStream:
    """Open upstream before sending headers; closing a tab closes upstream too."""
    def __init__(self, owner, url, headers, payload, path):
        self.owner, self.path = owner, path
        owner.guard('POST', path)
        self.entered = False
        self.client = httpx.Client(timeout=httpx.Timeout(30, connect=5), trust_env=False)
        self.context = self.client.stream('POST', url, headers=headers, json=payload)
        try:
            self.response = self.context.__enter__()
            self.entered = True
            if self.response.status_code != 200:
                data = json.loads(self.response.read())
                raise InferenceError(redact_text(data.get('error', {}).get('message', 'Inference failed.')),
                                     self.response.status_code)
            if 'text/event-stream' not in self.response.headers.get('content-type', ''):
                raise InferenceError('The inference controller returned an invalid stream.', 502)
        except Exception:
            self.close()
            raise

    def chunks(self):
        for chunk in self.response.iter_bytes():
            if self.owner.closed:
                break
            try:
                self.owner.guard('POST', self.path)
            except InferenceError:
                # Emergency stop withdraws the stream and triggers upstream cancellation.
                break
            yield chunk

    def close(self):
        if self.entered:
            self.context.__exit__(None, None, None)
            self.entered = False
        self.client.close()
