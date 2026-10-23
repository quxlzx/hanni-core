"""Durable desktop adapters for existing evaluations and model admission.

Development evidence is deliberately never published as a routing quality or
capability proof. Model calls use the shared AdaptiveModelEngine, pinned without
fallback; actual file reads use the original scoped registry and MCP session.
"""
from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from uuid import UUID, uuid4

from hanni.models.adaptive import ModelRequest, ModelSelectionError
from hanni.logs.redaction import redact_value

REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
ACTIVE = frozenset({'running', 'pausing', 'cancelling'})
SCHEMA = 1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False, default=str).encode()).hexdigest()


def redact(value):
    """Retain full bounded case evidence, redacting secrets at the storage edge."""
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if re.search(r'(?i)(password|api.?key|access.?token|refresh.?token|authorization|secret)', str(k))
                else redact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        # Huge uninterrupted encoded/token runs contain no readable case prose
        # and would trigger expensive backtracking in the shared token scrubber.
        value = re.sub(r'[\w-]{2048,}', '[REDACTED OVERSIZED TOKEN]', value[:262144])
        value = redact_value(value)
        return re.sub(r'(?i)(bearer\s+|(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*)[^\s,;"\]}]+',
                      r'\1[REDACTED]', value)[:262144]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def uid(value):
    if not isinstance(value, str):
        raise ValueError('A run UUID is required.')
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError('A run UUID is required.') from None


def suites():
    # These are public development corpora. No final holdout is loaded here.
    return [
        {'id': 'structured-development', 'name': 'Structured JSON · V4.2',
         'scope': 'Model-only · exact JSON oracle', 'categories': ['structured_output', 'long_context'],
         'model_required': True, 'native_tools': False, 'case_count': 2,
         'scoring': 'Parsed JSON must exactly equal the frozen expected object; 0 or 100.',
         'provenance': 'Existing V4.2 short and 400-line long prompts; exposed development corpus.'},
        {'id': 'llm-tools-development', 'name': 'LLM tool evaluation',
         'scope': 'Real model inference · synthetic MCP results',
         'categories': ['tool_selection', 'tool_arguments', 'response_grounding'],
         'model_required': True, 'native_tools': True,
         'scoring': 'Original llm_tools weighted 0–100 rubric and strict pass; lexical heuristics, synthetic outcomes.',
         'provenance': 'evals/llm_tools/cases.jsonl and original catalog; exposed development corpus.'},
        {'id': 'routing-development', 'name': 'Capability retrieval',
         'scope': 'Deterministic retrieval · no model inference or tool execution',
         'categories': ['capability_retrieval'], 'model_required': False, 'native_tools': False,
         'scoring': 'Original routing.evaluate_case rubric; score 0–100 and strict pass.',
         'provenance': 'evals/routing/cases.jsonl; exposed development corpus.'},
        {'id': 'file-read-development', 'name': 'Verified file read · V4.2',
         'scope': 'Real model + actual read-only MCP execution', 'categories': ['tool_selection', 'response_grounding'],
         'model_required': True, 'native_tools': True, 'case_count': 1,
         'scoring': 'Original file.read VERIFIED receipt on the fixed synthetic fixture, plus exact dispatch token in final answer.',
         'provenance': 'Existing V4.2 read-only synthetic file protocol; no arbitrary paths or tool menu.'},
    ]


def corpus(suite_id):
    if suite_id == 'llm-tools-development':
        from hanni.evals.llm_tools import load_scenarios
        return load_scenarios(REPO / 'evals/llm_tools/cases.jsonl')
    if suite_id == 'routing-development':
        return [json.loads(line) for line in (REPO / 'evals/routing/cases.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    if suite_id == 'structured-development':
        return [{'id': 'short', 'family': 'structured_output',
                 'prompt': 'Return only JSON: {"serial":8427,"available":false}.',
                 'expected': {'serial': 8427, 'available': False}},
                {'id': 'long', 'family': 'long_context',
                 'prompt': 'Synthetic ledger: ' + '\n'.join(f'line {i:04d}: neutral calibration placeholder.' for i in range(400))
                 + '\nAUTHORITATIVE_CODE=coral-8427\nReturn only {"code":"value"} using AUTHORITATIVE_CODE.',
                 'expected': {'code': 'coral-8427'}}]
    if suite_id == 'file-read-development':
        return [{'id': 'file-read', 'family': 'tool_selection', 'fixture': 'dispatch_code=coral-8427\nSynthetic verification.\n',
                 'expected': {'capability': 'file.read', 'verification': 'VERIFIED', 'dispatch_code': 'coral-8427'}}]
    raise ValueError('Choose an implemented development suite.')


def scorer_digest(suite_id):
    # Routing menus, MCP policies, system prompts and reviewed lexical checks are
    # all behavior, not just the final rubric function.
    files = [Path(__file__)]
    for folder in ('evals', 'mcp', 'tools', 'models'):
        files += list((PACKAGE / folder).glob('*.py'))
    files += [PACKAGE / 'core/orchestrator.py', PACKAGE / 'core/response_style.py']
    return digest({p.relative_to(PACKAGE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


class PinnedClient:
    """The evaluator's pure inference client; admission remains in the router."""
    def __init__(self, lab, run):
        self.lab, self.run = lab, run
        self.telemetry = []

    def _invoke(self, messages, tools=None, **options):
        self.lab._admit(self.run)
        settings = self.run['settings']
        measurement = {}
        request = ModelRequest(task_category='tool_selection' if tools is not None else 'structured_output',
            capabilities=frozenset({'text', 'tool_calling'} if tools is not None else {'text'}),
            privacy_categories=frozenset({'synthetic'}), output_tokens=settings['max_tokens'],
            schema_tokens=len(json.dumps(tools).encode()) if tools else 0,
            allow_legacy_default=True, interactive=False,
            tool_calling_format='openai_function' if tools is not None else None)
        fixed = {'temperature': 0, 'top_p': 1, 'max_tokens': settings['max_tokens']}
        value = self.lab.engine.execute(messages, request=request,
            endpoint_id=self.run['endpoint_id'], max_fallbacks=0, telemetry=measurement,
            admission=lambda: self.lab._admit(self.run),
            local_operation=(lambda client: client.complete_with_tools(messages, tools=tools, **fixed)) if tools is not None else None,
            **fixed)
        self.telemetry.append(measurement)
        return value

    def complete_with_tools(self, messages, *, tools, **options):
        return self._invoke(messages, tools=tools, **options)

    def chat(self, messages, **options):
        return self._invoke(messages, **options)

    def stream_chat(self, messages, **options):
        # Buffered original admission; no fabricated token-level TTFT.
        yield self.chat(messages, **options)


class ModelLab:
    def __init__(self, config, engine, *, registry=None, shutdown_event=None):
        self.config, self.engine, self.registry = config, engine, registry
        self.shutdown_event = shutdown_event
        self.root = Path(config.paths.data_dir).resolve() / 'model-lab' if config else None
        self.lock = threading.RLock()
        self.db = None
        self.thread = None
        self.closed = False
        self.active_run_id = None
        self.signal = None
        self.owner_file = None
        self.owns_storage = False
        self.storage_error = None
        if self.root is not None:
            try:
                self._claim()
                self._connect()
                if self.owns_storage:
                    with self.lock:
                        for key, raw in list(self.db.execute('SELECT id,payload FROM runs')):
                            row = json.loads(raw)
                            if row['status'] in ACTIVE:
                                row.update(status='interrupted', current_case=None, updated_at=time.time(),
                                           status_reason='Session ended; resume from the last committed case.')
                                self._save(row)
            except (OSError, RuntimeError, sqlite3.Error, ValueError, KeyError):
                self.storage_error = 'Private benchmark storage is unavailable; existing evidence was retained.'
                if self.db is not None:
                    self.db.close(); self.db = None
                self._release()

    def _claim(self):
        self._guard()
        self.root.mkdir(parents=True, exist_ok=True)
        owner = self.root / 'owner.lock'
        if owner.is_symlink() or owner.resolve().parent != self.root:
            raise RuntimeError('Unsafe benchmark ownership path.')
        stream = owner.open('a+b')
        try:
            if stream.seek(0, 2) == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            self.storage_error = 'Another Model Lab session owns these checkpoints; this view is read-only.'
            return
        self.owner_file, self.owns_storage = stream, True

    def _release(self):
        if self.owner_file is not None:
            self.owner_file.close(); self.owner_file = None
        self.owns_storage = False

    def _guard(self):
        if self.root is None:
            raise RuntimeError('Model Lab requires a configured local session.')
        if self.root.is_symlink() or self.root.resolve() != self.root:
            raise RuntimeError('Model Lab storage must remain in the private data directory.')
        for suffix in ('', '-wal', '-shm', '-journal'):
            p = self.root / ('runs.sqlite3' + suffix)
            if p.is_symlink() or p.resolve().parent != self.root:
                raise RuntimeError('Model Lab storage contains an unsafe link.')

    def _connect(self):
        self._guard()
        with self.lock:
            if self.db is None:
                if self.storage_error and not (self.root / 'runs.sqlite3').is_file():
                    raise RuntimeError(self.storage_error)
                self.root.mkdir(parents=True, exist_ok=True)
                if not self.owns_storage:
                    self.db = sqlite3.connect((self.root / 'runs.sqlite3').as_uri() + '?mode=ro', uri=True, check_same_thread=False)
                    return self.db
                self.db = sqlite3.connect(self.root / 'runs.sqlite3', check_same_thread=False)
                self.db.execute('PRAGMA journal_mode=WAL')
                self.db.execute('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS cases(run_id TEXT,ordinal INTEGER,payload TEXT NOT NULL,PRIMARY KEY(run_id,ordinal))')
                self.db.commit()
            return self.db

    def _save(self, run):
        self._guard()
        self.db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)', (run['id'], json.dumps(redact(run), allow_nan=False)))
        self.db.commit()

    def _check(self):
        if not self.owns_storage:
            raise RuntimeError(self.storage_error or 'The private benchmark store is not owned by this session.')
        if self.closed or self.shutdown_event is not None and self.shutdown_event.is_set():
            raise RuntimeError('This Model Lab session is shutting down.')
        from hanni.core.shutdown import FileStopStateStore
        if self.root is None:
            raise RuntimeError('Model Lab requires a configured local session.')
        if FileStopStateStore.for_data_dir(self.root.parent).load() is not None:
            raise RuntimeError('Benchmarks are blocked while HANNI is in Safe Mode.')
        self._guard()

    def inventory(self):
        if self.engine is None or self.engine.closed:
            return []
        snapshot = self.engine.snapshot()
        raw = {r['endpoint_id']: r for r in self.engine._inventory()}
        from hanni.models.manager import current
        manager = current()
        residency = manager.snapshot() if manager is not None else {}
        result = []
        for observed in snapshot['endpoints']:
            row = deepcopy(observed)
            source = raw[row['endpoint_id']]
            row.update(configured=True, installed=None, loaded=None, parameter_count=None,
                       endpoint=None, host='local' if row['local'] else source.get('worker', {}).get('node_id'),
                       assigned_gpu=None, configured_gpu=None, configured_quantization=None,
                       configured_model_file=None, benchmark_results=[])
            if 'spec' in source:
                spec = source['spec']
                row.update(endpoint=spec.endpoint, configured_quantization=spec.quantization,
                           configured_gpu=list(spec.device_name_hints), configured_model_file=spec.model_file.replace('\\', '/').rsplit('/', 1)[-1])
                entry = residency.get(spec.id, {})
                row['assigned_gpu'] = entry.get('device')
                candidates = [getattr(manager, 'files', {}).get(spec.id) if manager else None,
                              os.getenv('HANNI_MODEL_FILE'), spec.model_file if Path(spec.model_file).is_absolute() else None]
                verified = [Path(p) for p in candidates if p and Path(p).name == Path(spec.model_file).name]
                if verified:
                    row['installed'] = any(p.is_file() for p in verified)
                if entry:
                    row['loaded'] = bool(entry.get('resident'))
            else:
                worker = source['worker']
                row['configured_gpu'] = worker.get('startup', {}).get('gpu_device')
                configured_file = worker.get('startup', {}).get('model_file')
                if isinstance(configured_file, str):
                    row['configured_model_file'] = configured_file.replace('\\', '/').rsplit('/', 1)[-1]
                row['endpoint'] = ('127.0.0.1:' + str(worker['local_port'])) if worker.get('local_port') else None
            if row['health'] == 'healthy' and row.get('model_id'):
                row['loaded'] = True
            row['available'] = row['enabled'] and row['health'] == 'healthy' and row['model_id'] == row['configured_model']
            row['availability_reason'] = None if row['available'] else 'Endpoint unavailable, disabled, unknown, or serving another model.'
            row['benchmark_suites'] = []
            for suite in suites():
                if not suite['model_required']:
                    continue
                request = self._requirements(suite, 192)
                reasons = self.engine._reasons(source | observed, request)
                row['benchmark_suites'].append({'suite_id': suite['id'], 'enabled': not reasons, 'reasons': reasons})
            if self.db is not None:
                try:
                    with self.lock:
                        recent = self.db.execute("SELECT payload FROM runs WHERE json_extract(payload,'$.endpoint_id')=? ORDER BY json_extract(payload,'$.created_at') DESC LIMIT 5", (row['endpoint_id'],))
                        row['benchmark_results'] = [{k: r.get(k) for k in ('id', 'suite_name', 'status', 'created_at', 'completed', 'total', 'summary')}
                                                    for r in (json.loads(raw[0]) for raw in recent)]
                except (sqlite3.Error, ValueError):
                    pass
            result.append(redact(row))
        return result

    @staticmethod
    def _requirements(suite, output_tokens):
        return ModelRequest(task_category='tool_selection' if suite['native_tools'] else 'structured_output',
            capabilities=frozenset({'text', 'tool_calling'} if suite['native_tools'] else {'text'}),
            privacy_categories=frozenset({'synthetic'}), output_tokens=output_tokens,
            allow_legacy_default=True, interactive=False,
            tool_calling_format='openai_function' if suite['native_tools'] else None)

    def _configuration(self, endpoint_id):
        behavior = {'timezone': self.config.hanni.user.timezone, 'mcp': asdict(self.config.hanni.mcp),
                    'permissions': asdict(self.config.permissions), 'privacy': asdict(self.config.privacy),
                    'personality': asdict(self.config.hanni.personality)}
        if endpoint_id is None:
            return {'kind': 'deterministic', 'behavior': behavior}
        source = next((r for r in self.engine._inventory() if r['endpoint_id'] == endpoint_id), None)
        if source is None:
            raise ValueError('Choose a configured endpoint.')
        return redact({'model': asdict(source['spec']) if 'spec' in source else source['worker'], 'behavior': behavior})

    def _admit(self, run):
        self._check()
        if run['endpoint_id'] is not None:
            if self.engine.endpoint_identity(run['endpoint_id']) != run['model_identity']:
                raise ModelSelectionError('Model identity changed; create a new benchmark run.')
            if digest(self._configuration(run['endpoint_id'])) != run['configuration_sha256']:
                raise ModelSelectionError('Model configuration changed; create a new benchmark run.')

    def _protocol(self, suite_id, cases):
        from hanni.mcp.session import _TOOL_POLICY
        from hanni.core.orchestrator import DEFAULT_SYSTEM_PROMPT
        result = {'temperature': 0, 'top_p': 1, 'max_tool_calls': 8,
                  'owner_timezone': self.config.hanni.user.timezone,
                  'tool_policy_sha256': hashlib.sha256(_TOOL_POLICY.encode()).hexdigest(),
                  'system_prompt_sha256': hashlib.sha256(DEFAULT_SYSTEM_PROMPT.encode()).hexdigest(),
                  'admission': 'Original AdaptiveModelEngine; pinned endpoint; max_fallbacks=0; interactive=False.',
                  'holdout': False, 'development_exposed': True}
        if suite_id == 'llm-tools-development':
            from hanni.evals.llm_tools import audit_scenarios
            audit = audit_scenarios(self._host(), cases)
            result['routed_menus_sha256'] = audit['routed_menus_sha256']
        if suite_id == 'routing-development':
            from hanni.evals.routing import RoutingCase
            host = self._host()
            menus = []
            for raw in cases:
                c = RoutingCase.from_dict(raw)
                decision = host.route(c.query, history=c.history, now=c.now)
                menus.append({'id': c.id, 'tools': [t.openai_schema() for t in decision.tools]})
            result['routed_menus_sha256'] = digest(menus)
        return result

    def start(self, data):
        self._check()
        if not isinstance(data, dict) or set(data) != {'suite_id', 'endpoint_id', 'max_cases', 'repetitions', 'max_tokens', 'max_rounds'}:
            raise ValueError('Choose only supported benchmark settings.')
        suite = next((s for s in suites() if s['id'] == data['suite_id']), None)
        if suite is None:
            raise ValueError('Choose an implemented development suite.')
        for field, lower, upper in [('max_cases', 1, 10000), ('repetitions', 1, 5), ('max_tokens', 32, 1024), ('max_rounds', 1, 4)]:
            if type(data[field]) is not int or not lower <= data[field] <= upper:
                raise ValueError('Benchmark settings are outside their supported bounds.')
        if suite['model_required']:
            if not isinstance(data['endpoint_id'], str):
                raise ValueError('Select an available configured model.')
            selected = self.engine.select(self._requirements(suite, data['max_tokens']),
                                          allowed_endpoint_ids=frozenset({data['endpoint_id']}))
            if selected['endpoint'] is None:
                raise RuntimeError('Selected endpoint is not eligible for this suite; inspect Model Overview and routing exclusions.')
        elif data['endpoint_id'] is not None:
            raise ValueError('Capability retrieval does not use a model; leave the endpoint empty.')
        try:
            all_cases = corpus(suite['id'])
        except (OSError, ValueError, ImportError):
            raise RuntimeError('The selected development corpus is unavailable; other suites remain available.') from None
        if data['max_cases'] > len(all_cases):
            raise ValueError('The selected case count exceeds this suite.')
        selected_cases = all_cases[:data['max_cases']]
        preflight = self.preflight(data['suite_id'], data['endpoint_id'], data['max_cases'], data['max_tokens'])
        if not preflight['eligible']:
            raise ValueError(preflight['reason'])
        settings = {k: data[k] for k in ('max_cases', 'repetitions', 'max_tokens', 'max_rounds')}
        configuration = self._configuration(data['endpoint_id'])
        protocol = self._protocol(suite['id'], selected_cases)
        endpoint = next((r for r in self.inventory() if r['endpoint_id'] == data['endpoint_id']), None)
        run = {'id': str(uuid4()), 'schema_version': SCHEMA, 'suite_id': suite['id'], 'suite_name': suite['name'],
               'scope': suite['scope'], 'scoring': suite['scoring'], 'provenance': suite['provenance'],
               'integrity': 'exposed-development', 'holdout': False, 'contaminated': True,
               'endpoint_id': data['endpoint_id'], 'model': endpoint, 'configuration': configuration,
               'configuration_sha256': digest(configuration), 'model_identity': self.engine.endpoint_identity(data['endpoint_id']) if data['endpoint_id'] else None,
               'dataset_sha256': digest(all_cases), 'selection_sha256': digest(selected_cases),
               'scorer_sha256': scorer_digest(suite['id']), 'settings': settings,
               'environment_sha256': digest(configuration['behavior']),
               'protocol': protocol, 'protocol_sha256': digest(protocol),
               'created_at': time.time(), 'updated_at': time.time(), 'status': 'running',
               'status_reason': None, 'current_case': None, 'completed': 0,
               'total': len(selected_cases) * settings['repetitions'], 'summary': {},
               'routing_publication': 'None; development scores do not create capability or quality proofs.'}
        with self.lock:
            if self.active_run_id is not None:
                raise RuntimeError('Pause or cancel the active benchmark before starting another.')
            self._save(run)
            self._launch(run, selected_cases)
        return self.detail(run['id'])['run']

    def _launch(self, run, cases):
        self.active_run_id = run['id']
        self.signal = None
        self.thread = threading.Thread(target=self._run, args=(deepcopy(run), deepcopy(cases)), name='hanni-model-lab', daemon=True)
        self.thread.start()

    def control(self, action, data):
        self._check()
        if not isinstance(data, dict) or set(data) != {'run_id'}:
            raise ValueError('Choose a persisted run.')
        run = self.detail(data['run_id'])['run']
        with self.lock:
            if action == 'resume':
                if self.active_run_id is not None:
                    raise RuntimeError('Another benchmark is active.')
                if run['status'] not in {'paused', 'cancelled', 'interrupted', 'failed'} or run['completed'] >= run['total']:
                    raise ValueError('This checkpoint cannot be resumed.')
                self._admit(run)
                all_cases = corpus(run['suite_id'])
                if (digest(all_cases) != run['dataset_sha256']
                        or digest(all_cases[:run['settings']['max_cases']]) != run['selection_sha256']
                        or scorer_digest(run['suite_id']) != run['scorer_sha256']
                        or digest(self._configuration(run['endpoint_id'])) != run['configuration_sha256']):
                    raise RuntimeError('Dataset, scorer, or configuration changed; create a new run.')
                if digest(self._protocol(run['suite_id'], all_cases[:run['settings']['max_cases']])) != run['protocol_sha256']:
                    raise RuntimeError('Evaluation prompts or routed tool menus changed; create a new run.')
                run.update(status='running', status_reason=None, updated_at=time.time())
                self._save(run)
                self._launch(run, all_cases[:run['settings']['max_cases']])
            elif action in {'pause', 'cancel'}:
                if self.active_run_id != run['id'] or run['status'] not in ACTIVE:
                    raise ValueError('This run is not active.')
                if self.signal != 'cancel':
                    self.signal = action
                run.update(status='cancelling' if self.signal == 'cancel' else 'pausing',
                           status_reason='The in-flight case finishes before this request takes effect.', updated_at=time.time())
                self._save(run)
            else:
                raise ValueError('Choose a supported benchmark action.')
        return run

    def _host(self):
        from hanni.tools.registry import build_default_registry
        from hanni.mcp.host import McpHost
        from hanni.evals.isolation import isolated_host
        mcp = self.config.hanni.mcp
        return isolated_host(McpHost(build_default_registry(self.config), read_only=mcp.read_only,
            max_tools=mcp.max_tools_per_turn, allowed_actions=mcp.allowed_actions,
            timezone_name=self.config.hanni.user.timezone))

    def preflight(self, suite_id, endpoint_id, max_cases, max_tokens):
        suite = next((s for s in suites() if s['id'] == suite_id), None)
        if suite is None or type(max_cases) is not int or max_cases < 1 or type(max_tokens) is not int or not 32 <= max_tokens <= 1024:
            raise ValueError('Choose valid evaluation parameters for workload admission.')
        try:
            cases = corpus(suite_id)
        except (OSError, ValueError, ImportError):
            return {'eligible': False, 'reason': 'The selected development corpus is unavailable.', 'unsupported_cases': []}
        if max_cases > len(cases):
            raise ValueError('The selected case count exceeds this suite.')
        if not suite['model_required']:
            return {'eligible': endpoint_id is None, 'reason': None if endpoint_id is None else 'Capability retrieval does not use a model.', 'unsupported_cases': []}
        row = next((r for r in self.engine._rows() if r['endpoint_id'] == endpoint_id), None)
        if row is None:
            return {'eligible': False, 'reason': 'Choose a configured model endpoint.', 'unsupported_cases': []}
        unsupported = []
        if suite_id == 'structured-development':
            for c in cases[:max_cases]:
                request = self._requirements(suite, max_tokens)
                from dataclasses import replace
                messages = [{'role': 'user', 'content': c['prompt']}]
                request = replace(request, context_tokens=len(json.dumps(messages, ensure_ascii=False, allow_nan=False).encode()))
                reasons = self.engine._reasons(row, request)
                if reasons:
                    unsupported.append({'id': c['id'], 'reasons': reasons, 'required_context_upper_bound': request.context_tokens + max_tokens})
        else:
            reasons = self.engine._reasons(row, self._requirements(suite, max_tokens))
            if reasons:
                unsupported.append({'id': 'suite-admission', 'reasons': reasons})
        return {'eligible': not unsupported, 'unsupported_cases': unsupported,
                'reason': ('The selected workload exceeds original context admission or endpoint eligibility: ' +
                           '; '.join(c['id'] + ': ' + ', '.join(c['reasons']).replace('_', ' ') for c in unsupported)) if unsupported else None,
                'context_policy': 'Original conservative UTF-8 message-byte admission is preserved; prompts are never truncated.'}

    def _evaluate(self, run, case):
        suite_id = run['suite_id']
        if suite_id == 'routing-development':
            from hanni.evals.routing import RoutingCase, evaluate_case
            started = time.perf_counter()
            row = evaluate_case(self._host(), RoutingCase.from_dict(case)).to_dict()
            row.update(expected=case, latency_ms=(time.perf_counter()-started)*1000,
                       real_inference=False, tool_execution=False, verified_task_success=None)
            return row
        client = PinnedClient(self, run)
        started = time.perf_counter()
        if suite_id == 'llm-tools-development':
            from hanni.evals.llm_tools import evaluate_scenario
            row = evaluate_scenario(self._host(), client, case, max_rounds=run['settings']['max_rounds'])
            row.update(real_inference=bool(client.telemetry), tool_execution=False, verified_task_success=None)
        elif suite_id == 'structured-development':
            from hanni.workflows.verification import parse_evidence_json
            answer = client.chat([{'role': 'user', 'content': case['prompt']}])
            try:
                actual = parse_evidence_json(answer)
            except (ValueError, TypeError):
                actual = None
            passed = type(actual) is dict and actual == case['expected'] and all(type(actual[k]) is type(v) for k, v in case['expected'].items())
            row = {'id': case['id'], 'family': case['family'], 'query': case['prompt'], 'expected': case['expected'],
                   'actual': actual, 'final_answer': answer, 'passed': passed, 'score': 100 if passed else 0,
                   'failure_classification': [] if passed else ['EXACT_JSON_MISMATCH'],
                   'real_inference': True, 'tool_execution': False, 'verified_task_success': None}
        else:
            row = self._file_read(run, case, client)
        row.update(latency_ms=(time.perf_counter()-started)*1000, inference=client.telemetry)
        return row

    def _file_read(self, run, case, client):
        from hanni.tools.base import ToolRegistry
        from hanni.mcp.host import McpHost
        from hanni.mcp.session import McpToolSession
        from hanni.core.orchestrator import TextSession
        # The model may read only this owned, synthetic fixture. No frontend path
        # or tool name is accepted, and the original handler/authority is kept.
        source = self.root / 'fixture.txt'
        if source.is_symlink() or source.resolve().parent != self.root:
            raise RuntimeError('Unsafe benchmark fixture path.')
        source.write_text(case['fixture'], encoding='utf8')
        original = self.registry() if callable(self.registry) else self.registry
        if original is None:
            raise RuntimeError('The original desktop tool registry is unavailable.')
        registry = ToolRegistry(original.context)
        registry.register(original.get('file.read'))
        host = McpHost(registry, read_only=True, max_tools=1, allowed_actions=(), timezone_name=self.config.hanni.user.timezone)
        receipts = []
        call = host.call
        def read(tool, arguments, *args, **kwargs):
            if tool.capability_id != 'file.read' or set(arguments) != {'path'} or Path(arguments['path']).resolve() != source:
                raise ValueError('Benchmark tool requests must read the fixed synthetic fixture.')
            self._admit(run)
            result = call(tool, arguments, *args, **kwargs)
            receipts.append({'capability_id': tool.capability_id, 'result': result})
            return result
        host.call = read
        session = McpToolSession(TextSession(client), client, host, max_rounds=run['settings']['max_rounds'])
        answer = ''.join(session.stream_response(f'Read the file at {source} and tell me its dispatch_code value.'))
        verified = any(r['result'].get('ok') and r['result'].get('verification', {}).get('status') == 'VERIFIED' for r in receipts)
        passed = verified and 'coral-8427' in answer
        return {'id': case['id'], 'family': case['family'], 'expected': case['expected'], 'final_answer': answer,
                'original_receipts': receipts, 'trace': session.last_trace, 'passed': passed, 'score': 100 if passed else 0,
                'failure_classification': [] if passed else ['VERIFIED_READ_OR_FINAL_TOKEN_MISSING'],
                'real_inference': bool(client.telemetry), 'tool_execution': bool(receipts), 'verified_task_success': passed}

    def _run(self, run, cases):
        try:
            if digest(cases) != run['selection_sha256']:
                raise RuntimeError('Captured dataset integrity check failed.')
            for ordinal in range(run['completed'], run['total']):
                with self.lock:
                    if self.signal or self.closed:
                        break
                    run.update(current_case=cases[ordinal % len(cases)]['id'], updated_at=time.time())
                    self._save(run)
                self._admit(run)
                if scorer_digest(run['suite_id']) != run['scorer_sha256']:
                    raise RuntimeError('Evaluator source changed during execution; checkpoint retained without a model quality score.')
                case = cases[ordinal % len(cases)]
                began = time.perf_counter()
                try:
                    row = self._evaluate(run, case)
                    self._admit(run)
                except Exception as exc:
                    row = {'id': case['id'], 'family': case.get('family'), 'expected': case.get('expected', case.get('arguments')),
                           'passed': False, 'score': 0, 'runtime_error': str(exc), 'error_class': type(exc).__name__,
                           'failure_classification': ['EVALUATION_RUNTIME_ERROR'], 'verified_task_success': None,
                           'latency_ms': (time.perf_counter()-began)*1000}
                row = redact(row)
                row.update(ordinal=ordinal, repetition=ordinal // len(cases) + 1)
                row['evidence_sha256'] = digest(row)
                with self.lock:
                    self._guard()
                    self.db.execute('INSERT INTO cases VALUES(?,?,?)', (run['id'], ordinal, json.dumps(redact(row), allow_nan=False)))
                    run.update(completed=ordinal+1, updated_at=time.time(), current_case=None)
                    if self.signal:
                        run['status'] = 'cancelling' if self.signal == 'cancel' else 'pausing'
                    run['summary'] = self._summary(run['id'])
                    self._save(run)
                    if row.get('runtime_error'):
                        run.update(status='failed', status_reason='The endpoint or evaluator failed; evidence and checkpoint are retained.')
                        break
            with self.lock:
                if run['status'] != 'failed':
                    run['status'] = 'completed' if run['completed'] == run['total'] else 'cancelled' if self.signal == 'cancel' else 'paused'
                    run['status_reason'] = None if run['status'] == 'completed' else 'Stopped at a durable case boundary; resume is supported.'
                run.update(current_case=None, updated_at=time.time())
                self._save(run)
        except Exception as exc:
            with self.lock:
                run.update(status='failed', status_reason=redact(str(exc)), current_case=None, updated_at=time.time())
                self._save(run)
        finally:
            with self.lock:
                self.active_run_id = None
                if self.closed and self.db is not None:
                    self.db.close()
                    self.db = None
                    self._release()

    def _summary(self, run_id):
        rows = [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM cases WHERE run_id=? ORDER BY ordinal', (run_id,))]
        n = len(rows)
        latency = sorted(float(r['latency_ms']) for r in rows if isinstance(r.get('latency_ms'), (float, int)))
        def quantile(p):
            if not latency: return None
            if p == .95:
                return latency[max(0, math.ceil(p*len(latency))-1)]
            position = (len(latency)-1)*p
            lo = int(position); hi = min(lo+1, len(latency)-1)
            return latency[lo] + (latency[hi]-latency[lo])*(position-lo)
        def component(name):
            values = [r['component_scores'][name] for r in rows if name in r.get('component_scores', {})]
            return sum(values)/len(values) if values else None
        measured = [m for r in rows for m in r.get('inference', [])]
        def average(field):
            values = [m.get('performance', {}).get(field) for m in measured]
            values = [v for v in values if type(v) in (int, float) and math.isfinite(v)]
            return sum(values)/len(values) if values else None
        metric_samples = {field: sum(type(m.get('performance', {}).get(field)) in (int, float)
                         for m in measured) for field in ('generation_tps', 'prompt_tps', 'ttft_ms')}
        verified = [r for r in rows if type(r.get('verified_task_success')) is bool]
        return {'case_count': n, 'passed': sum(r.get('passed') is True for r in rows),
                'pass_rate_percent': 100*sum(r.get('passed') is True for r in rows)/n if n else None,
                'mean_score_100': sum(r.get('score', 0) for r in rows)/n if n else None,
                'error_rate_percent': 100*sum(bool(r.get('runtime_error')) for r in rows)/n if n else None,
                'latency_samples': len(latency), 'latency_p50_ms': quantile(.5), 'latency_p95_ms': quantile(.95),
                'tool_selection_percent': component('tool_selection'), 'argument_correctness_percent': component('argument_correctness'),
                'grounding_percent': component('evidence_grounding'), 'no_unsupported_claims_percent': component('no_unsupported_claims'),
                'verified_task_success_percent': 100*sum(r['verified_task_success'] for r in verified)/len(verified) if verified else None,
                'verified_task_samples': len(verified), 'inference_samples': len(measured),
                'mean_generation_tps': average('generation_tps'), 'mean_prompt_tps': average('prompt_tps'),
                'mean_ttft_ms': average('ttft_ms'), 'gpu_memory_peak_bytes': None,
                'metric_sample_counts': metric_samples,
                'percentile_convention': 'P50 median; P95 nearest rank ceil(0.95*n), matching V4.2.',
                'latency_scope': 'Full case wall time including routing, model turns, grading and any fixture reads.'}

    def detail(self, run_id, *, offset=0, limit=100):
        run_id = uid(run_id)
        if type(offset) is not int or not 0 <= offset <= 50000 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('Invalid result page.')
        with self.lock:
            db = self._connect()
            found = db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
            if not found:
                raise ValueError('Benchmark run was not found.')
            run = redact(json.loads(found[0]))
            rows = [self._public_case(json.loads(r[0])) for r in db.execute('SELECT payload FROM cases WHERE run_id=? ORDER BY ordinal LIMIT ? OFFSET ?', (run_id, limit, offset))]
            return {'run': run, 'cases': rows, 'offset': offset, 'limit': limit,
                    'has_more': offset+len(rows) < run['completed']}

    def export(self, run_id, *, offset=0, limit=500, representation=None):
        if representation not in (None, 'serialized'):
            raise ValueError('Choose a supported export representation.')
        result = self.detail(run_id, offset=offset, limit=limit)
        with self.lock:
            size = self.db.execute('SELECT SUM(length(payload)) FROM cases WHERE run_id=?', (uid(run_id),)).fetchone()[0] or 0
            if offset == 0 and size <= 8*1024**2:
                result['cases'] = [self._public_case(json.loads(r[0])) for r in self.db.execute('SELECT payload FROM cases WHERE run_id=? AND ordinal<? ORDER BY ordinal', (uid(run_id), result['run']['completed']))]
            else:
                exported, size = [], 0
                for raw in self.db.execute('SELECT payload FROM cases WHERE run_id=? AND ordinal<? ORDER BY ordinal LIMIT ? OFFSET ?', (uid(run_id), result['run']['completed'], limit, offset)):
                    if size + len(raw[0]) > 8*1024**2 and exported:
                        break
                    size += len(raw[0]); exported.append(self._public_case(json.loads(raw[0])))
                result['cases'] = exported
        next_offset = offset+len(result['cases'])
        public = redact({'format': 'hanni-model-lab-v1', 'run': result['run'], 'results': result['cases'],
                       'export_complete': next_offset >= result['run']['completed'],
                       'next_offset': next_offset if next_offset < result['run']['completed'] else None})
        if representation == 'serialized':
            # JavaScript parses 1500.0 as 1500. Preserve Python's original
            # numeric types in downloaded evidence and configuration manifests.
            # Redaction has already run on the objects, before serialization.
            serialized = {'format': public['format'],
                    'run_json': json.dumps(public['run'], ensure_ascii=False, allow_nan=False, separators=(',', ':')),
                    'results_json': [],
                    'export_complete': public['export_complete'], 'next_offset': public['next_offset']}
            # This counts the same escaped outer JSON encoding used by Handler.
            # Large nested case objects stay valid complete JSON strings; they
            # are never passed through scalar truncation after serialization.
            wire_size = len(json.dumps(serialized, allow_nan=False).encode())
            if wire_size > 16*1024**2:
                raise RuntimeError('The benchmark manifest exceeds its bounded export representation.')
            for row in public['results']:
                raw = json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
                additional = len(json.dumps(raw).encode()) + 2
                if wire_size + additional > 16*1024**2:
                    if not serialized['results_json']:
                        raise RuntimeError('An individual case exceeds the bounded export representation.')
                    serialized.update(export_complete=False, next_offset=offset+len(serialized['results_json']))
                    break
                wire_size += additional
                serialized['results_json'].append(raw)
            return serialized
        return public

    @staticmethod
    def _public_case(row):
        public = redact(row)
        expected = digest({k: v for k, v in public.items() if k != 'evidence_sha256'})
        if expected != public.get('evidence_sha256'):
            public['stored_evidence_sha256'] = public.pop('evidence_sha256', None)
            public['redaction_note'] = 'Current secret policy changed rendered evidence; stored digest binds the original redacted checkpoint.'
            public['evidence_sha256'] = digest(public)
        return public

    def compare(self, run_ids):
        if not isinstance(run_ids, list) or not 2 <= len(run_ids) <= 4 or len(set(run_ids)) != len(run_ids):
            raise ValueError('Choose two to four different runs.')
        runs = [self.detail(i)['run'] for i in run_ids]
        fields = ('suite_id', 'dataset_sha256', 'selection_sha256', 'scorer_sha256', 'environment_sha256', 'protocol_sha256', 'settings', 'scope')
        mismatches = [field for field in fields if any(r[field] != runs[0][field] for r in runs[1:])]
        if any(r['status'] != 'completed' for r in runs):
            mismatches.append('incomplete_run')
        return {'runs': runs, 'comparable': not mismatches, 'mismatches': mismatches,
                'conditions': 'Same suite, exact dataset/case selection, scorer, settings and completed workload required. Hardware and model configurations remain visible tradeoffs.',
                'automatic_ranking': False,
                'scales': {'pass_rate_percent': [0, 100], 'mean_score_100': [0, 100], 'error_rate_percent': [0, 100],
                           'latency_p50_ms': 'milliseconds; lower is faster', 'latency_p95_ms': 'milliseconds; lower is faster',
                           'mean_generation_tps': 'tokens per second', 'mean_prompt_tps': 'tokens per second',
                           'mean_ttft_ms': 'milliseconds; only measured first-token timing'}}

    def snapshot(self, query=None):
        query = query or {}
        if set(query) - {'q', 'status', 'suite_id', 'endpoint_id', 'refresh', 'offset', 'limit'}:
            raise ValueError('Unknown history filter.')
        if any(not isinstance(v, str) or len(v) > 200 for v in query.values()):
            raise ValueError('Invalid history filter.')
        offset, limit = int(query.get('offset', '0')), int(query.get('limit', '100'))
        if not 0 <= offset <= 1000000 or not 1 <= limit <= 100:
            raise ValueError('Invalid history page.')
        models = self.inventory()
        suite_rows = suites()
        for s in suite_rows:
            try:
                s['case_count'] = len(corpus(s['id']))
                s['enabled'] = True
            except (OSError, ValueError, ImportError):
                s.update(case_count=0, enabled=False, unavailable_reason='This development corpus is not installed in this environment.')
            s.update(holdout=False, integrity='exposed-development', pause='case boundary', resume=True,
                     settings={'max_cases': [1, s['case_count']], 'repetitions': [1, 5], 'max_tokens': [32, 1024], 'max_rounds': [1, 4], 'temperature': 0, 'top_p': 1})
        rows, count, total_count, active_run = [], 0, 0, None
        if self.root is not None:
            try:
                filters, values = [], []
                for field in ('status', 'suite_id', 'endpoint_id'):
                    if query.get(field):
                        filters.append(f"json_extract(payload,'$.{field}')=?")
                        values.append(query[field])
                if query.get('q'):
                    filters.append("lower(COALESCE(json_extract(payload,'$.id'),'') || ' ' || COALESCE(json_extract(payload,'$.suite_name'),'') || ' ' || COALESCE(json_extract(payload,'$.endpoint_id'),'') || ' ' || COALESCE(json_extract(payload,'$.model.configured_model'),'') || ' ' || COALESCE(json_extract(payload,'$.model.configured_model_file'),'') || ' ' || COALESCE(json_extract(payload,'$.status'),'')) LIKE ? ESCAPE '\\'")
                    escaped = query['q'].lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                    values.append('%' + escaped + '%')
                where = ' WHERE ' + ' AND '.join(filters) if filters else ''
                with self.lock:
                    db = self._connect()
                    total_count = db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
                    count = db.execute('SELECT COUNT(*) FROM runs' + where, values).fetchone()[0]
                    rows = [redact(json.loads(r[0])) for r in db.execute('SELECT payload FROM runs' + where +
                        " ORDER BY json_extract(payload,'$.created_at') DESC LIMIT ? OFFSET ?", values + [limit, offset])]
                    if self.active_run_id:
                        found = db.execute('SELECT payload FROM runs WHERE id=?', (self.active_run_id,)).fetchone()
                        active_run = redact(json.loads(found[0])) if found else None
            except (OSError, RuntimeError, sqlite3.Error, ValueError):
                self.storage_error = 'Private benchmark storage is unavailable; existing evidence was retained.'
        reason = None
        try:
            self._check()
        except (RuntimeError, OSError):
            reason = self.storage_error or 'Benchmarks are unavailable, shutting down, or blocked by Safe Mode.'
        return {'available': self.root is not None and not self.closed and self.storage_error is None, 'models': models, 'suites': suite_rows,
                'runs': rows, 'history_count': count, 'total_runs': total_count,
                'history_offset': offset, 'history_limit': limit, 'history_has_more': offset+len(rows) < count,
                'active_run_id': self.active_run_id, 'active_run': active_run,
                'controls': {'start': {'enabled': reason is None and self.active_run_id is None, 'reason': reason},
                             'pause': 'Finishes and commits the current case before pausing.',
                             'cancel': 'Finishes and commits the current case; never stops a model process.'},
                'integrity_notice': 'All offered datasets are exposed development data. Final holdouts are not opened; runs never publish routing quality or capability proofs.'}

    def close(self):
        with self.lock:
            self.closed = True
            self.signal = 'pause'
            running = self.thread is not None and self.thread.is_alive()
            if not running and self.db is not None:
                self.db.close()
                self.db = None
            if not running:
                self._release()
