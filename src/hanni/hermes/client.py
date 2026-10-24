"""Private loopback bridge client and original-registry execution authority."""
from contextvars import ContextVar
import http.client
import json
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlsplit
from uuid import uuid4

from .state import digest, Conflict

_controls = {}
_payload = ContextVar('hermes_owner_operation', default=None)
_proposal = ContextVar('hermes_scoped_proposal', default=None)
_reviewed_read = ContextVar('hermes_reviewed_read', default=None)


class BridgeUnavailable(RuntimeError):
    pass


class Client:
    def __init__(self, config):
        parts = urlsplit(config['endpoint'])
        if parts.scheme != 'http' or parts.hostname != '127.0.0.1' or not parts.port or parts.path not in {'', '/'} or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Hermes bridge must use a managed Windows loopback forward.')
        self.parts, self.config = parts, config
        path=Path(config['token_file'])
        if path.is_file():
            from hanni.logs.redaction import register_secret
            register_secret('HANNI_HERMES_BRIDGE',path.read_text().strip())

    def request(self, method, path, body=None):
        try:
            token = Path(self.config['token_file']).read_text().strip()
        except OSError:
            raise BridgeUnavailable('Hermes bridge authentication reference is unavailable.') from None
        from hanni.logs.redaction import register_secret
        register_secret('HANNI_HERMES_BRIDGE',token)
        if len(token) < 32:
            raise BridgeUnavailable('Hermes bridge authentication reference is unavailable.')
        connection = http.client.HTTPConnection(self.parts.hostname, self.parts.port, timeout=5)
        try:
            headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
            connection.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse()
            wire = response.read(2097153)
            if response.status == 409:
                raise Conflict('Remote state changed; refresh before retrying.')
            if response.status != 200 or len(wire) > 2097152:
                raise BridgeUnavailable('Hermes bridge unavailable or authentication rejected. No task was replayed.')
            result = json.loads(wire)
            if not isinstance(result, dict):
                raise BridgeUnavailable('Hermes bridge returned an invalid protocol response; no task was replayed.')
            return result
        except (OSError, http.client.HTTPException, json.JSONDecodeError):
            raise BridgeUnavailable('Karina connection unavailable. Saved task IDs remain available for review.') from None
        finally:
            connection.close()


class HermesControl:
    def __init__(self, root, hub, shutdown_event=None):
        self.root, self.hub = Path(root) if root is not None else None, hub
        self.shutdown_event = shutdown_event
        self.lock = threading.RLock()
        self.registry = None
        self.closed = False
        self.db = None
        self.client = None
        self.tunnel = None
        self.config = {}
        from .inventory import InventoryCache
        self.inventory = InventoryCache(self.root) if self.root is not None else None
        self.stop = threading.Event()
        self.monitor = None
        self.stop_listener = None
        self.cancelled_tasks = set()
        self.turn_cancellations = {}
        path = self.root/'hermes'/'config.json' if self.root is not None else None
        if path is not None and path.exists():
            self.config = json.loads(path.read_text())
            self.client = Client(self.config)
            self.db = sqlite3.connect(self.root/'hermes'/'client.sqlite3', check_same_thread=False)
            self.db.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,payload TEXT)')
            self.db.execute('CREATE TABLE IF NOT EXISTS dispatch(id TEXT PRIMARY KEY,state TEXT,receipt TEXT)')
            self.db.execute('CREATE TABLE IF NOT EXISTS announcements(id TEXT PRIMARY KEY)')
            self.db.execute('CREATE TABLE IF NOT EXISTS submissions(key TEXT PRIMARY KEY,payload TEXT,state TEXT)')
            self.db.execute('CREATE TABLE IF NOT EXISTS cancellations(id TEXT PRIMARY KEY)')
            self.cancelled_tasks = {row[0] for row in self.db.execute('SELECT id FROM cancellations')}
            self.db.execute("UPDATE dispatch SET state='uncertain' WHERE state='dispatching'")
            self.db.commit()
            if self.config.get('tunnel'):
                from .tunnel import ManagedTunnel
                self.tunnel = ManagedTunnel(self.config['tunnel'])
                self.tunnel.start()
        if self.root is not None:
            _controls[str(self.root.resolve())] = self
        if self.client:
            self.monitor = threading.Thread(target=self.watch, name='hanni-hermes-progress', daemon=True)
            self.monitor.start()

    def bind(self, registry):
        self.registry = registry
        if self.config.get('attachment_roots'):
            from hanni.tools.base import ToolDefinition, ToolResult
            name = 'hermes.attachment.transfer'
            if name not in {d.name for d in registry.definitions()}:
                def transfer(arguments, context, request):
                    from .attachments import prepare
                    payload = prepare(arguments['path'], self.config['attachment_roots'])
                    receipt = self.require().request('POST', '/attachments', payload)
                    return ToolResult(name, bool(receipt['ok']), 'Transferred explicitly approved attachment bytes.', receipt,
                                      verification=receipt['verification'])
                registry.register(ToolDefinition(name, 'Transfer one explicitly authorized file to Karina for document/OCR/transcription tools.',
                    2, 3, {'path': str}, {'container_path': 'string', 'sha256': 'string'}, transfer,
                    side_effect='external_action', background_allowed=False))
        if self.stop_listener is None:
            def listener(change, record):
                if change == 'tripped':
                    # Local emergency stop never waits for a network call.
                    threading.Thread(target=self.cancel_all, daemon=True).start()
            self.stop_listener = listener
            registry.context.emergency_stop.add_listener(listener)

    def cancel_all(self):
        if self.db is None or self.client is None:
            return
        with self.lock:
            rows = self.db.execute('SELECT id FROM tasks').fetchall()
            with self.db:
                self.db.executemany('INSERT OR IGNORE INTO cancellations VALUES(?)', rows)
            self.cancelled_tasks.update(row[0] for row in rows)
        try:
            self.client.request('POST', '/tasks/cancel_many', {'ids': [row[0] for row in rows]})
        except (RuntimeError, OSError):
            pass

    def request_cancel(self, task_id):
        """Owned cancellation reduces authority and remains available in Safe Mode."""
        self._owned_task(task_id)
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO cancellations VALUES(?)', (task_id,))
            self.cancelled_tasks.add(task_id)
        registry = self.registry or self.hub.controller_registry or self.hub.features.registry
        from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
        definition = ToolDefinition('hermes.task.cancel', 'Reduce authority by cancelling an owned task.',
            0, 0, {'task_id':str}, {'cancel_requested':'boolean'}, lambda *_:None,
            side_effect='external_action')
        registry.context.audit.write(definition,ToolRequest(definition.name,{'task_id':task_id},source='hermes-owned-cancellation'),
            {'task_id':task_id},result=ToolResult(definition.name,True,'Cancellation intent saved; remote acknowledgment pending.',
                                               {'cancel_requested':True,'effects_undone':False}))
        def propagate():
            try:
                self.client.request('POST', '/tasks/'+task_id+'/cancel', {})
            except (RuntimeError, OSError):
                pass
        threading.Thread(target=propagate,name='hanni-hermes-cancel',daemon=True).start()
        return {'cancel_requested':True,'effects_undone':False}

    def watch(self):
        from .state import TERMINAL
        last_revision = None
        while not self.stop.wait(2):
            try:
                self.guard()
                if not self.config.get('connection_only', False):
                    catalog = self.client.request('GET', '/catalog')
                    if catalog['revision'] != last_revision:
                        self.reconcile()
                        last_revision = catalog['revision']
                if self.registry is None:
                    continue
                with self.lock:
                    pending = self.db.execute("SELECT key,payload FROM submissions WHERE state!='submitted'").fetchall()
                for key, request in pending:
                    try:
                        recovered = self.client.request('GET', '/submissions/'+key)
                    except BridgeUnavailable:
                        continue
                    if recovered['request'] != json.loads(request):
                        raise Conflict('Recovered submission changed; inspect manually.')
                    with self.lock, self.db:
                        self.db.execute('INSERT OR IGNORE INTO tasks VALUES(?,?)', (recovered['id'], request))
                        self.db.execute("UPDATE submissions SET state='submitted' WHERE key=?", (key,))
                with self.lock:
                    tasks = [r[0] for r in self.db.execute('SELECT id FROM tasks')]
                    announced = {r[0] for r in self.db.execute('SELECT id FROM announcements')}
                for task_id in tasks:
                    if task_id in announced:
                        continue
                    task = self.client.request('GET', '/tasks/'+task_id)
                    event = self.turn_cancellations.get(task_id)
                    if event is not None and event.is_set():
                        self.request_cancel(task_id)
                    if task_id in self.cancelled_tasks:
                        self.client.request('POST', '/tasks/'+task_id+'/cancel', {})
                        continue
                    for action in task['actions']:
                        if (self.enabled and action['state']=='pending' and action['spec']['target']=='windows'
                                and action['spec']['remote'].get('retry_read') is True):
                            self.act(task_id,action['id'],digest(action),auto_read=True)
                            continue
                        # Only exact owner-reviewed remote read definitions can auto-run.
                        if (self.enabled and action['state'] == 'pending' and action['spec']['target'] == 'karina'
                                and action['spec']['hash'] in self.config.get('remote_read_hashes', [])):
                            self.authorize_reviewed_read(task_id, action)
                    if task['state'] not in TERMINAL:
                        continue
                    self.guard()
                    self.turn_cancellations.pop(task_id, None)
                    from .presentation import receipt_answer
                    summary = (receipt_answer(self.local_receipts(task)) if task['state'] == 'review_required' else
                               'Hermes did not complete the task. Its saved state and any completed effects are available in the Hermes tab.')
                    if task['state'] == 'cancelled':
                        summary = None
                    with self.lock, self.db:
                        self.db.execute('INSERT OR IGNORE INTO announcements VALUES(?)', (task_id,))
                    if summary:
                        from hanni.dashboard.chat import current_hub
                        chat = current_hub()
                        if chat and not chat.closed:
                            # Add an independent notification, never overwrite a foreground turn.
                            with chat.lock:
                                # Route from the locally saved owner request, not
                                # from a remote result's untrusted routing claims.
                                saved = self._owned_task(task_id)
                                reference = saved.get('context', {}).get('conversation_reference_untrusted') or {}
                                conversation = reference.get('conversation_id', 'default')
                                chat._add(task_id, 'assistant', summary, 'hermes', 'complete', conversation=chat._conversation(conversation))
                        from hanni.core.interaction import interaction
                        self.guard()
                        latest = self.client.request('GET', '/tasks/'+task_id)
                        with interaction.condition:
                            self.guard()
                            if latest['state'] != 'cancelled' and task_id not in self.cancelled_tasks:
                                interaction.completion(summary, lambda: None)
            except (RuntimeError, OSError, ValueError, sqlite3.Error):
                pass  # Status UI reports outages. Saved operations remain pending.

    @property
    def enabled(self):
        return self.client is not None and self.config.get('enabled') is True and not self.closed

    def guard(self):
        if self.closed or self.shutdown_event is not None and self.shutdown_event.is_set():
            raise RuntimeError('HANNI is stopping.')
        registry = self.registry or self.hub.controller_registry or self.hub.features.registry
        registry.context.emergency_stop.guard('Hermes orchestration')
        owner = registry.context.permissions.owner
        if owner.chat_only or owner.max_auto_approve_level < 0:
            raise RuntimeError('The current owner permission profile forbids orchestration.')
        return registry

    def require(self):
        self.guard()
        if self.client is None:
            raise BridgeUnavailable('Hermes bridge is not configured. Complete the private setup first.')
        return self.client

    def snapshot(self):
        inventory = self.inventory.snapshot() if self.inventory is not None else None
        direct_mcp = self.hub.snapshot() if self.config.get('direct_mcp', False) else None
        if self.client is None:
            return {'configured': False, 'enabled': False, 'tasks': [], 'catalog': None, 'inventory': inventory,
                    'reason': 'Hermes integration is not configured.', 'honcho': 'Recall errors remain; bridge does not use Honcho.'}
        try:
            health = self.client.request('GET', '/health')
            if health.get('protocol') != 1:
                raise BridgeUnavailable('Unsupported Hermes bridge protocol.')
            tasks = self.client.request('GET', '/tasks')['tasks']
            # Dashboard sees only this HANNI installation's tasks.
            with self.lock:
                owned = {row[0] for row in self.db.execute('SELECT id FROM tasks')}
            tasks = [task for task in tasks if task['id'] in owned]
            approval_hashes = {action['id']:digest(action) for task in tasks for action in task['actions']}
            tasks = [self.local_receipts(task) for task in tasks]
            for task in tasks:
                task['local_cancel_requested'] = task['id'] in self.cancelled_tasks
                for action in task['actions']:
                    action['approval_hash'] = approval_hashes[action['id']]
            catalog = None
            if not self.config.get('connection_only', False):
                catalog = self.client.request('GET', '/catalog')
                catalog['hanni_schema_status'] = {server['name']:{'connection':server['state'],
                    'tools':[{'name':tool['original_name'],'definition_hash':tool['definition_hash'],
                              'enabled':tool['enabled'],'approval':tool['approval']} for tool in server['tools']]}
                    for server in self.hub.require().snapshot()['servers']}
                from .catalog import connection_hash
                catalog['discovery_review'] = [{'name':item['name'],'expected_hash':connection_hash(item),
                    'approved':catalog.get('connection_approvals',{}).get(item['name'])==connection_hash(item)}
                    for item in catalog['entries'] if not item['deleted']]
            return {'configured': True, 'enabled': self.enabled, 'health': health, 'tasks': tasks,
                    'inventory': inventory,
                    'direct_mcp': direct_mcp,
                    'endpoint': self.config['endpoint'],
                    'connection_only': self.config.get('connection_only', False),
                    'catalog': catalog,
                    'scope': {'windows_roots':self.config.get('windows_roots', []),
                              'windows_capabilities':self.config.get('windows_capabilities', [])},
                    'tunnel': self.tunnel.snapshot() if self.tunnel else None,
                    'honcho': 'Recall errors remain; no shared-memory quality claim.'}
        except (RuntimeError, OSError):
            with self.lock:
                saved = [{'id': row[0], 'state': 'unavailable', 'events': [], 'actions': [], 'result': None,
                          'error': 'Remote state unavailable; effects and cancellation are not verified.'}
                         for row in self.db.execute('SELECT id FROM tasks')]
            return {'configured': True, 'enabled': self.enabled, 'tasks': saved, 'catalog': None,
                    'inventory': inventory,
                    'direct_mcp': direct_mcp,
                    'endpoint': self.config['endpoint'],
                    'connection_only': self.config.get('connection_only', False),
                    'reason': 'Karina is unavailable or authentication failed. Task IDs are retained; no paid fallback.',
                    'tunnel': self.tunnel.snapshot() if self.tunnel else None, 'saved_tasks': saved}

    def submit(self, prompt, registry, *, key=None, prior_task=None, conversation_context=None):
        self.guard()
        if not self.enabled:
            raise BridgeUnavailable('Automatic Hermes delegation is disabled.')
        key = key or uuid4().hex
        with self.lock:
            stored = self.db.execute('SELECT payload FROM submissions WHERE key=?',(key,)).fetchone()
        if stored:
            original = json.loads(stored[0])
            if original['prompt'] != prompt:
                raise Conflict('Owner request ID reused for a different task.')
            recovered = self.require().request('GET','/submissions/'+key)
            if recovered['request'] != original:
                raise Conflict('Recovered task contract changed; no task was replayed.')
            with self.lock,self.db:
                self.db.execute('INSERT OR IGNORE INTO tasks VALUES(?,?)',(recovered['id'],stored[0]))
            return recovered
        from hanni.logs.redaction import redact_text
        if redact_text(prompt) != prompt:
            raise ValueError('Task contains credential-like content; remove it before sharing.')
        from hanni.mcp.host import McpHost
        from hanni.workflows.policy import definition_fingerprint
        allowed = self.config.get('windows_capabilities', [])
        host = McpHost(registry, read_only=False, max_tools=8, allowed_actions=allowed)
        menu = [tool for tool in host.select_tools(prompt) if tool.capability_id in allowed]
        # The owner-configured scope is small; include missing scoped operations
        # so compound research+save requests are not shortened by first-pass retrieval.
        for name in allowed:
            if len(menu) >= 8:
                break
            if name not in {tool.capability_id for tool in menu}:
                try:
                    menu.append(host._as_tool(registry.get(name)))
                except (KeyError, RuntimeError):
                    pass
        specs = []
        for tool in menu:
            definition = registry.get(tool.capability_id)
            schema = tool.openai_schema()
            if tool.capability_id == 'app.open':
                apps = self.config.get('windows_apps', [])
                if not apps:
                    continue
                schema['function']['parameters']['properties']['app'] = {'type':'string','enum':apps}
            specs.append({'name': tool.wire_name, 'target': 'windows', 'hash': definition_fingerprint(definition),
                          'schema': schema, 'remote': {'capability_id': tool.capability_id,
                          'fixed_arguments': dict(tool.fixed_arguments),
                          'retry_read':definition.permission_level==definition.risk_level==0 and definition.side_effect in {None,'read'}
                              and definition.requires_confirmation_if is None and definition.background_allowed}})
        context = {'windows_execution_scope':{'authorized_roots':self.config.get('windows_roots', [])[:8],
                    'approved_app_names':self.config.get('windows_apps', [])[:12]},
                   'authority_notice':'This metadata proposes no action and grants no execution approval.'}
        if conversation_context is not None:
            # Explicit delegation may carry bounded text from this conversation.
            # Never include clipboard buffers, screenshots, audio, or all memory.
            from hanni.logs.redaction import redact_text
            serialized = json.dumps(conversation_context, ensure_ascii=False)
            if len(serialized) > 8000 or redact_text(serialized) != serialized:
                raise ValueError('Delegation context is too large or contains credential-like text.')
            context['conversation_reference_untrusted'] = conversation_context
        if prior_task:
            self._owned_task(prior_task)
            previous = self.require().request('GET', '/tasks/'+prior_task)
            # Same-owner task context only. No broad history, Honcho, screens or audio.
            from hanni.logs.redaction import redact_value
            context.update(redact_value({'prior_task_id':prior_task, 'prior_prompt':previous['request']['prompt'][:1000],
                                     'prior_model_report_unverified':str((previous.get('result') or {}).get('model_claims',''))[:2000],
                                     'prior_state':previous['state']}))
        request = {'prompt': prompt, 'windows_tools': specs, 'origin': 'hanni', 'context': context}
        from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
        name = 'hermes.task.propose'
        with self.lock:
            if name not in {definition.name for definition in registry.definitions()}:
                def handler(arguments, context, invocation):
                    payload = _proposal.get()
                    if payload is None or invocation.source != 'hanni-hermes-ingress':
                        raise ValueError('Task proposals can originate only from the enabled HANNI ingress.')
                    self.guard()
                    result = self.send_proposal(arguments['key'], payload)
                    return ToolResult(name, True, 'Scoped Hermes task submission acknowledged; execution is not verified.', {'task': result})
                registry.register(ToolDefinition(name, 'Submit one scoped, opt-in Hermes proposal; this grants no tool execution authority.',
                    1, 2, {'key':str}, {'task':'object'}, handler, side_effect='external_action', background_allowed=False))
        token = _proposal.set(request)
        try:
            result = registry.execute(ToolRequest(name, {'key':key}, source='hanni-hermes-ingress', correlation_id=key))
            return result.data['task']
        finally:
            _proposal.reset(token)

    def send_proposal(self, key, request):
        # Durable local submission intent precedes a possibly uncertain network acknowledgment.
        with self.lock, self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS submissions(key TEXT PRIMARY KEY,payload TEXT,state TEXT)')
            previous = self.db.execute('SELECT payload FROM submissions WHERE key=?', (key,)).fetchone()
            if previous and json.loads(previous[0]) != request:
                raise Conflict('Submission ID changed.')
            if not previous and self.db.execute('SELECT count(*) FROM submissions').fetchone()[0] >= 256:
                raise ValueError('Submission retention limit reached; review and archive explicitly.')
            self.db.execute('INSERT OR IGNORE INTO submissions VALUES(?,?,?)', (key, json.dumps(request), 'submitting'))
        result = self.require().request('POST', '/tasks', {'key': key, 'task': request})
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO tasks VALUES(?,?)', (result['id'], json.dumps(request)))
            self.db.execute("UPDATE submissions SET state='submitted' WHERE key=?", (key,))
        return result

    def reconcile(self):
        if self.config.get('connection_only', False):
            return {}  # Hermes owns its MCPs; never import them into HANNI.
        catalog = self.require().request('GET', '/catalog')
        path = self.root/'hermes'/'hub-ownership.json'
        owned = json.loads(path.read_text()) if path.exists() else {}
        from .catalog import reconcile_hanni
        manager = self.hub.require()
        backups=self.root/'hermes'/'backups'
        backups.mkdir(exist_ok=True)
        backup=backups/f"hub-revision-{catalog['revision']}.sqlite3"
        if not backup.exists():
            with manager.store.lock:
                destination=sqlite3.connect(backup)
                try:
                    manager.store.db.backup(destination)
                finally:
                    destination.close()
        try:
            result = reconcile_hanni(catalog, manager, owned)
            if self.tunnel:
                bridge_pair = next((pair for pair in self.config['tunnel']['forwards'] if pair[0] == self.client.parts.port), None)
                if bridge_pair is None:
                    raise ValueError('The bridge forward must remain explicitly configured.')
                forwards = [bridge_pair]+[[urlsplit(item['endpoints']['hanni']).port, urlsplit(item['endpoints']['hermes']).port]
                    for item in catalog['entries'] if item['enabled'] and not item['deleted']]
                if sorted(forwards) != sorted(self.config['tunnel']['forwards']):
                    self.tunnel.close()
                    from .tunnel import ManagedTunnel
                    self.config['tunnel']['forwards'] = forwards
                    self.tunnel = ManagedTunnel(self.config['tunnel'])
                    self.tunnel.start()
                    config_path = self.root/'hermes'/'config.json'
                    tmp_config = config_path.with_suffix('.tmp')
                    tmp_config.write_text(json.dumps(self.config, indent=2))
                    tmp_config.replace(config_path)
            return result
        finally:
            # Persist each successful registration even when another entry conflicts.
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(owned))
            tmp.replace(path)

    def _owned_task(self, task_id):
        with self.lock:
            row = self.db.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None:
            raise ValueError('This HANNI installation does not own the task.')
        return json.loads(row[0])

    def local_receipts(self, task):
        from copy import deepcopy
        result = deepcopy(task)
        local = {}
        with self.lock:
            for action in result.get('actions', []):
                if action['spec']['target'] != 'windows':
                    continue
                row = self.db.execute('SELECT state,receipt FROM dispatch WHERE id=?',(action['id'],)).fetchone()
                if row and row[0]=='fulfilled' and row[1]:
                    local[action['id']] = json.loads(row[1])
                    action['local_receipt_matches'] = digest(action.get('receipt')) == digest(local[action['id']])
                    action['receipt'] = local[action['id']]
                else:
                    action['local_receipt_matches'] = False
                    action['receipt'] = {'ok':False,'message':'No corresponding local execution receipt. Remote success claims are unverified.'}
        result['local_execution_receipts'] = local
        return result

    def authorize_reviewed_read(self, task_id, action):
        registry = self.guard()
        from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
        name = 'hermes.remote.authorize_read'
        with self.lock:
            if name not in {d.name for d in registry.definitions()}:
                def handler(arguments, context, request):
                    candidate = _reviewed_read.get()
                    if candidate is None or request.source != 'hermes-reviewed-read':
                        raise ValueError('Read authorization requires the trusted scoped orchestration policy.')
                    self.guard()
                    self._owned_task(arguments['task_id'])
                    if (not self.enabled or arguments['task_id'] in self.cancelled_tasks
                            or candidate['spec']['target'] != 'karina'
                            or candidate['spec']['hash'] not in self.config.get('remote_read_hashes', [])
                            or digest(candidate) != arguments['expected_hash']):
                        raise ValueError('Remote definition has no applicable owner read approval.')
                    result = self.client.request('POST', '/actions/'+candidate['id'], {'state':'dispatching'})
                    return ToolResult(name, True, 'Authorized one exact owner-reviewed remote read; execution is not yet verified.', {'action_id':result['id']})
                registry.register(ToolDefinition(name, 'Authorize one exact-hash remote definition explicitly classified read-only by the owner.',
                    1, 2, {'task_id':str,'expected_hash':str}, {'action_id':'string'}, handler,
                    side_effect='external_action', background_allowed=True))
        token = _reviewed_read.set(action)
        try:
            return registry.execute(ToolRequest(name, {'task_id':task_id,'expected_hash':digest(action)},
                source='hermes-reviewed-read',correlation_id=action['id']))
        finally:
            _reviewed_read.reset(token)

    def act(self, task_id, action_id, expected_hash, *, reject=False, auto_read=False, reason=None):
        registry = self.guard()
        request = self._owned_task(task_id)
        task = self.require().request('GET', '/tasks/'+task_id)
        action = next(a for a in task['actions'] if a['id'] == action_id)
        if digest(action) != expected_hash:
            raise Conflict('Action changed; review the current request.')
        if task_id in self.cancelled_tasks:
            raise Conflict('Cancellation was requested locally; no further actions are authorized.')
        if reject:
            return self.client.request('POST', '/actions/'+action_id,
                {'state': 'rejected', 'expected_hash': expected_hash,
                 'receipt': {'ok': False, 'error': 'Owner rejected this action.' + (' ' + reason if reason else '')}})
        if action['spec']['target'] == 'karina':
            # Owner confirmation is limited to this exact definition and arguments.
            return self.client.request('POST', '/actions/'+action_id, {'state': 'dispatching', 'expected_hash': expected_hash})
        spec = action['spec']
        if spec not in request['windows_tools']:
            raise ValueError('Remote action escaped the HANNI-selected capability scope.')
        if auto_read and spec['remote'].get('retry_read') is not True:
            raise ValueError('Automatic execution is limited to original-registry read capabilities.')
        arguments = {**action['arguments'], **spec['remote']['fixed_arguments']}
        if spec['remote']['capability_id']=='app.open' and str(arguments.get('app','')).casefold() not in {app.casefold() for app in self.config.get('windows_apps',[])}:
            raise ValueError('Application is outside the owner-configured launcher whitelist.')
        if spec['remote']['capability_id'].startswith('file.'):
            from hanni.tools.sensitive_paths import is_sensitive_path
            roots = [Path(root).resolve() for root in self.config.get('windows_roots', [])]
            if spec['remote']['capability_id'] in {'file.locate', 'file.search'} and not arguments.get('root'):
                raise ValueError('Hermes file discovery requires an explicit authorized root.')
            for key in ('path', 'source', 'destination', 'directory', 'root'):
                if key in arguments:
                    candidate = Path(arguments[key]).expanduser().resolve()
                    if is_sensitive_path(candidate) or not any(candidate.is_relative_to(root) for root in roots):
                        raise ValueError('File operation is outside owner-configured Hermes Windows roots.')
        with self.lock, self.db:
            previous = self.db.execute('SELECT state,receipt FROM dispatch WHERE id=?', (action_id,)).fetchone()
            if previous:
                if previous[0] == 'fulfilled':
                    return self.client.request('POST', '/actions/'+action_id,
                        {'state': 'fulfilled', 'receipt': json.loads(previous[1])})
                raise Conflict('Windows dispatch acknowledgment is uncertain; automatic replay is prohibited.')
            self.db.execute('INSERT INTO dispatch VALUES(?,?,NULL)', (action_id, 'dispatching'))
        self.client.request('POST', '/actions/'+action_id, {'state': 'dispatching', 'expected_hash': expected_hash})
        from hanni.tools.base import ToolRequest
        from hanni.reliability.execution import ReliabilityService
        service = getattr(registry.context, 'reliability', None) or ReliabilityService()
        def guard():
            self.guard()
            event=self.turn_cancellations.get(task_id)
            if task_id in self.cancelled_tasks or event is not None and event.is_set():
                raise RuntimeError('Local task cancellation prevents dispatch.')
            current = self.client.request('GET', '/tasks/'+task_id)
            if current['state'] in {'cancelled', 'interrupted', 'uncertain', 'failed'}:
                raise RuntimeError('Task stopped before Windows execution.')
        try:
            from hanni.tools.base import _BACKGROUND_CALL
            token = _BACKGROUND_CALL.set(auto_read)
            try:
                if auto_read:
                    from hanni.core.interaction import interaction
                    if not interaction.yield_background(interrupted=lambda: self.closed or task_id in self.cancelled_tasks):
                        raise RuntimeError('Read cancelled before background admission.')
                with service.task('hermes.windows'):
                    result = registry.execute(ToolRequest(spec['remote']['capability_id'], arguments,
                        confirmed=not auto_read, source='hermes-scoped-read' if auto_read else 'hermes-owner-approved', correlation_id=action_id,
                        expected_definition_hash=spec['hash'], execution_guard=guard))
            finally:
                _BACKGROUND_CALL.reset(token)
            from hanni.logs.redaction import redact_value
            receipt = redact_value(result.to_dict())
            if isinstance((receipt.get('data') or {}).get('text'),str) and len(receipt['data']['text'])>12000:
                receipt['data']['text']=receipt['data']['text'][:12000]
                receipt['data']['truncated']=True
            if len(json.dumps(receipt))>48000:
                receipt={'ok':False,'error':'RESULT_LIMIT','message':'Result exceeds the bridge evidence budget. Inspect the local audit; no action was replayed.'}
        except Exception as exc:
            receipt = {'ok': False, 'error': type(exc).__name__, 'message': 'Windows action failed or was blocked; inspect local audit.'}
        with self.lock, self.db:
            self.db.execute('UPDATE dispatch SET state=?,receipt=? WHERE id=?', ('fulfilled', json.dumps(receipt), action_id))
        return self.client.request('POST', '/actions/'+action_id, {'state': 'fulfilled', 'receipt': receipt})

    def mutate(self, body):
        if set(body) != {'id', 'operation', 'data', 'confirmed'} or body['confirmed'] is not True:
            raise ValueError('Explicit owner confirmation is required.')
        if body['operation'] == 'cancel' and set(body['data']) == {'task_id'}:
            return self.request_cancel(body['data']['task_id'])
        registry = self.guard()
        from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
        name = 'workspace.hermes.manage'
        with self.lock:
            if name not in {tool.name for tool in registry.definitions()}:
                def handler(args, context, request):
                    payload = _payload.get()
                    if payload is None or request.source != 'desktop-hermes':
                        raise ValueError('Hermes management is restricted to the authenticated desktop.')
                    return ToolResult(name, True, 'Owner operation returned.', {'result': self.operation(args['operation'], payload)})
                registry.register(ToolDefinition(name, 'Scoped Hermes owner operations.', 2, 3,
                    {'operation': str}, {'result': 'object'}, handler, side_effect='external_action', background_allowed=False))
        token = _payload.set(body['data'])
        try:
            result = registry.execute(ToolRequest(name, {'operation': body['operation']}, confirmed=True,
                source='desktop-hermes', correlation_id=body['id']))
            return result.data['result']
        finally:
            _payload.reset(token)

    def operation(self, operation, data):
        if self.config.get('connection_only', False) and operation in {'sync', 'catalog', 'connection'}:
            raise ValueError('Manage MCP servers in Hermes; HANNI is configured for connection only.')
        if operation == 'enable' and set(data) == {'enabled'} and type(data['enabled']) is bool:
            if self.client is None:
                raise ValueError('Configure private bridge references first.')
            self.config['enabled'] = data['enabled']
            if not data['enabled']:
                threading.Thread(target=self.cancel_all, daemon=True).start()
            path = self.root/'hermes'/'config.json'
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.config, indent=2))
            tmp.replace(path)
            return {'enabled': self.enabled}
        if operation == 'sync' and not data:
            self.require().request('POST','/catalog/retry',{})
            return {'owned': self.reconcile()}
        if operation == 'connection' and set(data)=={'name','expected_hash','approve'} and type(data['approve']) is bool:
            result = self.require().request('POST','/catalog/connection',data)
            self.reconcile()
            owned_path=self.root/'hermes'/'hub-ownership.json'
            owned=json.loads(owned_path.read_text())
            server=next(server for server in self.hub.require().snapshot()['servers'] if server['id']==owned[data['name']]['id'])
            if data['approve']:
                self.hub.require().connect(server['id'],approved=True,expected_config_hash=server['config_hash'])
            else:
                self.hub.require().disconnect(server['id'])
            return result
        if operation == 'catalog' and set(data) == {'revision', 'entries'}:
            result = self.require().request('POST', '/catalog', {**data, 'id': uuid4().hex})
            self.reconcile()
            return result
        if operation == 'approve' and set(data) in ({'task_id', 'action_id', 'expected_hash', 'reject'}, {'task_id', 'action_id', 'expected_hash', 'reject', 'reason'}) and type(data['reject']) is bool:
            reason = data.get('reason')
            if reason is not None and (not isinstance(reason, str) or len(reason) > 500 or not data['reject']):
                raise ValueError('A denial reason must be text of at most 500 characters.')
            return self.act(data['task_id'], data['action_id'], data['expected_hash'], reject=data['reject'], reason=reason)
        if operation == 'cancel' and set(data) == {'task_id'}:
            self._owned_task(data['task_id'])
            with self.lock, self.db:
                self.db.execute('INSERT OR IGNORE INTO cancellations VALUES(?)', (data['task_id'],))
                self.cancelled_tasks.add(data['task_id'])
            return self.require().request('POST', '/tasks/'+data['task_id']+'/cancel', {})
        raise ValueError('Unsupported Hermes operation.')

    def close(self):
        if self.inventory is not None:
            self.inventory.close()
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        if self.stop_listener and self.registry:
            self.registry.context.emergency_stop.remove_listener(self.stop_listener)
        if self.monitor:
            self.monitor.join(timeout=16)
        if self.client is not None and self.db is not None:
            # Best effort; failure is retained, never described as remote rollback.
            self.cancel_all()
        if self.tunnel:
            self.tunnel.close()
        if self.db:
            self.db.close()
        if self.root is not None:
            _controls.pop(str(self.root.resolve()), None)


def current(root):
    return _controls.get(str(Path(root).resolve()))
