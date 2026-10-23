"""Same controlled original-pipeline workflows against an explicit source tree.

No host.call or registry authorization mocks. Synthetic diagnostic/launch
handlers stand in for OS boundaries. File/task/note/memory stores are genuine
isolated originals. Google uses its existing injected transport; MCP uses the
official SDK fixture. This measures execution reliability, not live-model IQ.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
STAGES = ('intent', 'retrieval', 'selection', 'arguments', 'authorization', 'execution', 'outcome', 'final_answer')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()/'src'))
    spec = importlib.util.spec_from_file_location('development_workflow_cases', ROOT/'tests/fixtures/reliability_workflows.py')
    cases_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(cases_module)
    from hanni.config.loader import load_config
    from hanni.tools.registry import build_default_registry
    from hanni.tools.base import ToolRequest, ToolResult
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    from hanni.models.client import ModelTurn, ModelToolCall, ModelProtocolError
    from hanni.core.shutdown import StopSource
    from hanni.core.identity import Actor
    from hanni.tools.google_identity import scopes_for, GoogleAccessError

    class Fallback:
        history = ()
        def stream_response(self, prompt, **kwargs): yield 'No controlled tool evidence was obtained.'
        def record_turn(self, prompt, response): pass

    class Model:
        def __init__(self, targets, arguments, fixture):
            self.targets, self.arguments, self.fixture = targets, arguments, fixture
            self.calls, self.menus, self.round = [], [], 0
        def complete_with_tools(self, messages, tools, **kwargs):
            self.round += 1
            names = [tool['function']['name'] for tool in tools]; self.menus.append(names)
            if self.fixture == 'parse_after_write' and self.round > 1:
                raise ModelProtocolError('Controlled parse failure')
            if self.round <= len(self.targets) or self.fixture == 'duplicate_write':
                target = self.targets[min(self.round-1, len(self.targets)-1)]
                name = McpHost._wire_name(target)
                if name not in names:
                    return ModelTurn('No matching controlled capability was exposed.')
                arguments = self.arguments.get(target, {})
                self.calls.append({'capability': target, 'arguments': arguments})
                return ModelTurn('', (ModelToolCall(str(self.round), name, arguments),))
            results = []
            for message in messages:
                if message.get('role') == 'tool':
                    try: results.append(json.loads(message['content']))
                    except (ValueError, KeyError): pass
            if self.fixture in {'duplicate_write', 'malformed', 'app_missing', 'app_denied', 'calendar_wrong'}:
                return ModelTurn('Everything succeeded and was independently verified.')
            # Generic controlled-client rendering of actual text evidence; a
            # file read's receipt message alone is not its requested content.
            return ModelTurn(' '.join(str(result.get('message') or '') + ' ' + str((result.get('data') or {}).get('text') or '') for result in results).strip())
        def chat(self, messages, **kwargs):
            return 'Everything succeeded and was independently verified.'

    results = []
    for identifier, query_template, capability, fixture in cases_module.CASES:
        started = time.perf_counter()
        row = {'id': identifier, 'query': query_template, 'fixture': fixture, 'stages': {}, 'passed': False,
               'actual_tools': [], 'handler_calls': [], 'tool_results': [], 'errors': [], 'trace_observed': False,
               'expected_outcome_kind': 'safe_refusal' if fixture in {'app_denied','mcp_disabled','mcp_changed','mcp_unknown','voice_inactive','voice_stopped','screen','screen_privacy'}
                 else 'expected_failure' if fixture in {'app_missing','file_missing','calendar_no_id','calendar_wrong','calendar_timeout','duplicate_write','malformed','unavailable','multi_partial','stop_between'}
                 else 'unverified_receipt' if fixture in {'app_running','app_accepted','app_exited','parse_after_write'} else 'positive'}
        with tempfile.TemporaryDirectory(prefix='hanni-workflow-') as temporary, ExitStack() as stack:
            root = Path(temporary); config = load_config(ROOT/'config', data_dir=root/'state', env={})
            registry = build_default_registry(config, data_dir=root/'state')
            service = getattr(registry.context, 'reliability', None)
            if service: stack.callback(service.close)
            source = root/'benchmark-results.json'; target = root/'saved-results.txt'; missing = root/'missing.txt'
            source.write_text('{"models":[{"name":"fixture-A","score":91},{"name":"fixture-B","score":83}]}', encoding='utf-8')
            query = query_template.format(source=source, target=target, missing=missing)
            row['query'] = query
            arguments = {'app.open': {'app': 'Notepad'}, 'file.read': {'path': str(missing if fixture == 'file_missing' else source)},
                'file.write': {'path': str(target), 'text': 'first\nsecond\n'},
                'file.copy': {'source': str(source), 'destination': str(target)},
                'file.move': {'source': str(source), 'destination': str(target)},
                'file.delete': {'path': str(source)}, 'process.top_cpu': {'limit': 5}, 'process.top_memory': {'limit': 5},
                'todo.add': {'title': 'Fixture homework', 'due': '2026-10-10T15:00:00', 'course': 'Fixture course'},
                'note.append': {'text': 'Benchmark review saved in isolated fixture', 'tag': 'review'}}
            original_execute = registry.execute
            actual_results = []
            def observed_execute(request):
                row['actual_tools'].append(request.name)
                try:
                    result = original_execute(request)
                    actual_results.append(result)
                    verification = getattr(result,'verification',None) or {}
                    row['tool_results'].append({'capability':result.name,'ok':result.ok,'error_code':(result.error or {}).get('code'),
                        'verification_status':verification.get('status'),'verification_scope':verification.get('scope')})
                    return result
                except Exception as exc:
                    row['errors'].append(type(exc).__name__); raise
            registry.execute = observed_execute
            def install(name, handler):
                original = registry.get(name)
                def observed_handler(values, context, request):
                    row['handler_calls'].append({'capability': name, 'arguments': dict(values), 'profile': request.actor_profile, 'confirmed': request.confirmed})
                    return handler(values, context, request)
                registry.unregister(name, expected=original)
                registry.register(replace(original, handler=observed_handler))
            measurements = {'system.stats': {'cpu_percent': 21, 'ram_percent': 43},
                'process.top_memory': {'processes': [{'name': 'fixture-editor.exe', 'rss_mb': 800.0, 'memory_percent': 5.0}]},
                'process.top_cpu': {'processes': [{'name': 'fixture-worker.exe', 'cpu_percent': 28.0}]},
                'disk.usage': {'free_gb': 100, 'total_gb': 500}, 'disk.free_space': {'free_gb': 100, 'total_gb': 500}, 'gpu.memory': {'available': False}}
            counts = {}
            def measured(name):
                def run(values, context, request):
                    counts[name] = counts.get(name, 0)+1
                    if fixture in {'retry', 'calendar_retry'} and name == 'system.stats' and counts[name] == 1:
                        return ToolResult(name, False, 'Transient read failed.', error={'code': 'NETWORK_ERROR', 'retryable': True})
                    if fixture == 'multi_partial' and name == 'process.top_memory':
                        return ToolResult(name, False, 'Process evidence unavailable.', error={'code': 'AUTH_REQUIRED', 'retryable': False})
                    if fixture == 'stop_between' and name == 'system.stats':
                        context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('fixture'))
                    data = {'cpu_percent': 'invalid', 'ram_percent': None} if fixture == 'malformed' and name == 'system.stats' else measurements[name]
                    message = {'system.stats':'Measured CPU 21%, RAM 43%.',
                        'process.top_memory':'fixture-editor.exe uses 800 MB RAM.',
                        'process.top_cpu':'fixture-worker.exe uses 28% CPU.',
                        'disk.usage':'100 GB free of 500 GB.', 'disk.free_space':'100 GB free of 500 GB.',
                        'gpu.memory':'GPU memory readings are unavailable.'}[name]
                    return ToolResult(name, True, message, data)
                return run
            for name in measurements: install(name, measured(name))
            def app(values, context, request):
                if fixture in {'app_missing', 'duplicate_write'}:
                    return ToolResult('app.open', False, 'Launch outcome unknown.', error={'code': 'TIMEOUT', 'retryable': True})
                if fixture == 'app_denied':
                    return ToolResult('app.open', False, 'App launch is unavailable.', error={'code': 'PERMISSION_DENIED', 'retryable': False})
                if fixture in {'app_accepted', 'parse_after_write'}:
                    return ToolResult('app.open', True, 'Windows accepted the launch request.', {'app': values['app'], 'outcome': 'accepted', 'verified': False})
                return ToolResult('app.open', True, 'Started Notepad.', {'app': values['app'], 'outcome': 'process_started',
                    'process_id': os.getpid() if fixture == 'app_running' else 2147483647, 'verified': False})
            install('app.open', app)
            for name in ('file.read','file.write','file.copy','file.move','file.delete','todo.add','todo.complete','note.append'):
                original_handler = registry.get(name).handler
                install(name, original_handler)
            event_bodies = []; stored_event = {}; provider_reads = []
            class Vault:
                def get(self, account): return {'email': 'fixture@example.invalid','credentials': {'token_uri':'https://oauth2.googleapis.com/token','scopes':list(scopes_for(('calendar.read','calendar.write')))},'calendar_ids':['primary']}
                def set(self, *args): pass
                def labels(self): return ('personal',)
                def preferences(self): return {'default_google_account':'personal'}
            access = registry.google_access; access._vault = Vault()
            def provider(account, path, params, body=None, **kwargs):
                if body is not None:
                    event_bodies.append(deepcopy(body))
                    if fixture == 'calendar_timeout': raise TimeoutError('ambiguous provider write')
                    data = {**body, 'id':'fixture-event-id'}
                    if fixture == 'calendar_no_id': data.pop('id')
                    if fixture == 'calendar_wrong': data['end'] = {'dateTime':'2030-01-01T00:00:00+00:00'}
                    stored_event.update(data); return data
                provider_reads.append(path)
                if fixture == 'calendar_retry' and len(provider_reads) == 1:
                    raise GoogleAccessError('Controlled transient calendar read failure', 'api_error')
                return dict(stored_event) if path.endswith('/fixture-event-id') else {'items': [{'id':'fixture-agenda-id','summary':'Fixture appointment','start':{'dateTime':'2026-10-10T15:00:00-04:00'},'end':{'dateTime':'2026-10-10T16:00:00-04:00'}}]} if fixture == 'calendar_retry' else {'items': []}
            access.transport = provider
            for name in ('google_calendar.create','google_calendar.agenda'):
                original_handler = registry.get(name).handler; install(name, original_handler)
            targets = [capability] if capability else []
            if fixture in {'multi_reads','multi_partial','stop_between'}: targets = ['system.stats','process.top_memory']
            host = McpHost(registry, read_only=False, max_tools=8, allowed_actions=('app.open','google_calendar.create'))
            model = None
            try:
                if fixture.startswith('mcp_'):
                    from hanni.mcp.manager import MCPManager
                    manager = MCPManager(root/'state', registry=registry); stack.callback(manager.close)
                    control, ledger = root/'control.json', root/'ledger.jsonl'; control.write_text('{}')
                    added = manager.add({'name':'Workflow SDK fixture','transport':'stdio','command':sys.executable,
                        'args':[str(ROOT/'tests/fixtures/mcp_hub_mock.py'),'--control',str(control),'--ledger',str(ledger)],'timeout_seconds':2})
                    server = added; manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
                    server = manager.snapshot()['servers'][0]
                    original_name = 'mock.create_record' if fixture == 'mcp_unknown' else 'mock.echo'
                    external = next(tool for tool in server['tools'] if tool['original_name'] == original_name)
                    manager.approve_tools(server['id'], [{'original_name': original_name,'definition_hash':external['definition_hash'],'classification':'unknown' if fixture == 'mcp_unknown' else 'read_only'}])
                    capability = external['internal_id']; targets = [capability]; arguments[capability] = {'title':'fixture'} if fixture == 'mcp_unknown' else {'message':'fixture evidence'}
                    if fixture == 'mcp_disabled': manager.disable_tools(server['id'], [original_name])
                    if fixture == 'mcp_changed':
                        spec_mock = importlib.util.spec_from_file_location('sdk_workflow_fixture', ROOT/'tests/fixtures/mcp_hub_mock.py')
                        mock = importlib.util.module_from_spec(spec_mock); spec_mock.loader.exec_module(mock)
                        tools = deepcopy(mock.TOOLS); tools[1]['description'] = 'Changed fixture echo definition'
                        control.write_text(json.dumps({'tools':tools})); manager.refresh(server['id'])
                    if fixture == 'mcp_unknown': control.write_text(json.dumps({'delay':4}))
                if fixture in {'voice_inactive','voice_stopped'}:
                    from hanni.dashboard.voice import VoiceControl
                    voice = VoiceControl()
                    if fixture == 'voice_stopped':
                        registry.context.emergency_stop.trip(source=StopSource.INTERNAL,requested_by=Actor.internal('fixture'))
                        voice.bind(SimpleNamespace(closed=False,paused=False),SimpleNamespace(classify=lambda _:None),registry,'Hanni')
                    try: voice.execute({'id':str(uuid4()),'action':'listen'})
                    except Exception as exc: row['errors'].append(type(exc).__name__)
                    answer = 'Voice capture was not started.'
                    row['stages'] = {key:None for key in STAGES}; row['stages'].update(intent=True,authorization=bool(row['errors']),execution=True,outcome=True,final_answer=True)
                elif fixture.startswith('screen'):
                    from hanni.dashboard.features import DesktopFeatures
                    state = DesktopFeatures(config,registry=registry).awareness()
                    answer = state['reason']
                    row['stages'] = {key:None for key in STAGES}; row['stages'].update(intent=True,authorization=not state['actions']['analyze'],execution=not state['capture_active'],outcome=not state['context_available'],final_answer='No screen is being captured' in answer)
                elif fixture == 'memory_store':
                    from hanni.memory.store import MemoryStore
                    from hanni.memory.session import MemoryAwareSession
                    store = MemoryStore(root/'state'/'memory.sqlite3')
                    answer = ''.join(MemoryAwareSession(Fallback(),store,registry=registry).stream_response(query))
                    saved = store.list()
                    row['stages'] = {key:None for key in STAGES}; row['stages'].update(intent=True,authorization=True,execution=bool(saved),outcome=bool(saved),final_answer='remember' in answer.lower())
                elif fixture in {'file_delete','todo_add','todo_complete','note'}:
                    if fixture == 'todo_complete':
                        prior = original_execute(ToolRequest('todo.add',arguments['todo.add'],confirmed=True)); arguments['todo.complete'] = {'id':prior.data['id']}
                    from hanni.tools.session import ToolAwareSession
                    assistant = ToolAwareSession(Fallback(),registry)
                    request = ToolRequest(capability,arguments[capability],source='test')
                    answer = ''.join(assistant._execute(request))
                    if getattr(assistant,'_pending_confirmation',None): answer += ' '+''.join(assistant.stream_response('yes'))
                    row['stages'] = {key:None for key in STAGES}; row['stages'].update(intent=True,arguments=True,authorization=True,execution=capability in row['actual_tools'],outcome=bool(row['handler_calls']),final_answer='Everything succeeded' not in answer)
                    row['boundary'] = 'Exact structured CLI/ToolAware request; retrieval and model choice are not applicable.'
                else:
                    routed = host.route(query)
                    menu = [tool.capability_id for tool in routed.tools]
                    if fixture == 'disk' and 'disk.free_space' in menu:
                        capability = 'disk.free_space'; targets = [capability]
                    row['candidate_menu'] = menu
                    model = Model(targets,arguments,fixture); assistant = McpToolSession(Fallback(),model,host,max_rounds=4)
                    answer = ''.join(assistant.stream_response(query))
                    active_expected = fixture not in {'mcp_disabled','mcp_changed','mcp_unknown'}
                    selected = [call['capability'] for call in model.calls]
                    if fixture.startswith('calendar'):
                        selected = [call['capability'] for call in row['handler_calls'] if call['capability']=='google_calendar.create'] or selected
                    actual_handlers = [call['capability'] for call in row['handler_calls']]
                    if fixture == 'mcp_read':
                        actual_handlers = [capability] if ledger.exists() and any(json.loads(line).get('event')=='call' for line in ledger.read_text().splitlines()) else []
                    success_expected = fixture not in {'app_missing','app_denied','file_missing','calendar_no_id','calendar_wrong','calendar_timeout','duplicate_write','malformed','unavailable','mcp_disabled','mcp_changed','mcp_unknown','multi_partial','stop_between'}
                    action_calls = [call for call in row['handler_calls'] if call['capability']=='app.open']
                    no_duplicates = fixture != 'duplicate_write' or len(action_calls)==1
                    final_safe = 'Everything succeeded' not in answer if not success_expected or fixture=='parse_after_write' else True
                    if fixture == 'calendar_wrong': final_safe = 'could not verify' in answer.lower() or 'couldn\'t verify' in answer.lower()
                    outcome = capability in actual_handlers if active_expected else capability not in actual_handlers
                    if fixture == 'file_write': outcome = target.exists() and target.read_bytes()==arguments['file.write']['text'].replace('\n',os.linesep).encode()
                    if fixture == 'file_copy': outcome = target.exists() and target.read_bytes()==source.read_bytes()
                    if fixture == 'file_move': outcome = target.exists() and not source.exists()
                    if fixture == 'calendar': outcome = len(event_bodies)==1 and bool(stored_event.get('id'))
                    if fixture == 'calendar_timeout': outcome = len(event_bodies)==1
                    if fixture == 'retry': outcome = counts.get('system.stats')==2
                    row['stages'] = dict(intent=all(target in menu for target in targets) if active_expected else capability not in menu,retrieval=all(target in menu for target in targets) if active_expected else capability not in menu,
                        selection=all(target in selected for target in targets) if active_expected and not fixture.startswith('calendar') else True,
                        arguments=all(call['arguments']==arguments.get(call['capability'],call['arguments']) for call in row['handler_calls'] if call['capability'] in arguments),
                        authorization=all(call['profile']=='owner' for call in row['handler_calls']),execution=outcome and no_duplicates,
                        outcome=outcome,final_answer=final_safe)
                    if service:
                        row['trace_observed']=bool(service.snapshot()['tasks'])
                        row['observed_verification']=(getattr(assistant,'last_trace',None) or {}).get('verification_status')
                row['answer'] = answer
                if model is None:
                    row['stages']['intent'] = None
                if fixture == 'file_delete': row['stages']['outcome'] = not source.exists()
                if fixture in {'todo_add','todo_complete'}:
                    from hanni.tools.todos import TodoStore
                    saved = TodoStore(root/'state').list({'status':'completed' if fixture=='todo_complete' else 'open'})
                    row['stages']['outcome'] = len(saved)==1
                if fixture == 'note': row['stages']['outcome']=any('Benchmark review saved' in path.read_text() for path in (root/'state'/'notes').glob('*.md'))
                # Independent fixture oracles below replace handler-entry and
                # unconditional final-answer checks. Intent understanding is not
                # measured by a deterministic client or an exact request.
                row['stages']['intent'] = None
                row['stage_boundaries'] = {'intent':'Not measured: deterministic client/exact boundary request.',
                    'outcome':'Controlled OS measurement, provider ledger or genuine isolated local state; not a live cloud/desktop outcome.'}
                selected_results = [result for result in actual_results if result.name in targets]
                successful = [result for result in selected_results if result.ok]
                data_by_name = {result.name:result.data for result in successful}
                lower = answer.lower()
                if model is not None:
                    row['stages']['arguments'] = (all(call['arguments']==arguments[call['capability']]
                        for call in row['handler_calls'] if call['capability'] in arguments)
                        if row['handler_calls'] else None)
                    row['stages']['authorization'] = (all(call['profile']=='owner' for call in row['handler_calls'])
                        if row['handler_calls'] else None)
                    row['stages']['execution'] = any(call['capability'] in targets for call in row['handler_calls']) or bool(selected_results) if active_expected else not selected_results
                    if fixture.startswith('calendar'):
                        # The existing calendar fast path plans the request;
                        # there is no model capability choice to grade.
                        row['stages']['selection'] = None
                outcome = row['stages'].get('outcome')
                final = None
                if fixture in {'stats','memory','cpu','disk','retry','multi_reads'}:
                    outcome = all(data_by_name.get(name)==measurements[name] for name in targets)
                    tokens = {'system.stats':('21','43'), 'process.top_memory':('fixture-editor.exe','800'),
                        'process.top_cpu':('fixture-worker.exe','28'), 'disk.usage':('100','500'), 'disk.free_space':('100','500')}
                    final = all(all(token in lower for token in tokens[name]) for name in targets)
                elif fixture in {'malformed','unavailable'}:
                    outcome = bool(successful) and (not any(type(data_by_name.get('system.stats',{}).get(key)) in (float,int)
                        for key in ('cpu_percent','ram_percent')) if fixture=='malformed' else data_by_name.get('gpu.memory',{}).get('available') is False)
                    final = ('could not' in lower or "couldn't" in lower or 'unavailable' in lower) and 'everything succeeded' not in lower and 'independently verified' not in lower
                elif fixture in {'multi_partial','stop_between'}:
                    outcome = data_by_name.get('system.stats')==measurements['system.stats'] and (
                        any(not result.ok for result in selected_results) if fixture=='multi_partial' else bool(row['errors']) and not any(call['capability']=='process.top_memory' for call in row['handler_calls']))
                    final = '21' in lower and ('unavailable' in lower if fixture=='multi_partial' else 'stop' in lower) and 'everything succeeded' not in lower
                elif fixture == 'file_read':
                    outcome = bool(successful) and data_by_name.get('file.read',{}).get('text')==source.read_text()
                    final = 'fixture-a' in lower and '91' in lower and 'fixture-b' in lower and '83' in lower
                elif fixture == 'file_missing':
                    outcome = not missing.exists() and not successful
                    final = 'everything succeeded' not in lower and ('not found' in lower or 'could not' in lower or "couldn't" in lower or 'unavailable' in lower)
                elif fixture in {'file_write','file_copy','file_move','file_delete'}:
                    if fixture=='file_write': outcome=target.exists() and target.read_bytes()==arguments['file.write']['text'].replace('\n',os.linesep).encode()
                    if fixture=='file_copy': outcome=target.exists() and target.read_bytes()==source.read_bytes()
                    if fixture=='file_move': outcome=target.exists() and not source.exists() and b'fixture-A' in target.read_bytes()
                    if fixture=='file_delete': outcome=not source.exists() and any(call['confirmed'] for call in row['handler_calls'])
                    final=bool(outcome) and ('saved-results.txt' in lower if fixture=='file_write' else 'benchmark-results.json' in lower)
                elif fixture.startswith('calendar'):
                    if fixture=='calendar_retry':
                        outcome = len(provider_reads)>=2 and any(result.ok and any(event.get('id')=='fixture-agenda-id' for event in result.data.get('events',[])) for result in selected_results)
                        final = 'fixture appointment' in lower
                    else:
                        request_call=next((call for call in row['handler_calls'] if call['capability']=='google_calendar.create'),None)
                        requested=request_call['arguments'] if request_call else {}
                        valid_resource=bool(event_bodies) and stored_event.get('id')=='fixture-event-id' and stored_event.get('summary','').lower()=='dentist' and (
                            stored_event.get('start',{}).get('dateTime')==requested.get('start') and stored_event.get('end',{}).get('dateTime')==requested.get('end'))
                        outcome = valid_resource if fixture=='calendar' else len(event_bodies)==1 and (not stored_event.get('id') if fixture=='calendar_no_id' else not valid_resource if fixture=='calendar_wrong' else not stored_event)
                        final = ('dentist' in lower and ('added' in lower or 'created' in lower)) if fixture=='calendar' else ('could not' in lower or "couldn't" in lower or 'unknown' in lower or 'ambiguous' in lower or 'failed' in lower or 'timeout' in lower) and 'everything succeeded' not in lower
                        row['stages']['arguments'] = bool(request_call) and bool(requested.get('start')) and bool(requested.get('end')) and requested.get('summary','').lower()=='dentist'
                elif fixture in {'todo_add','todo_complete'}:
                    outcome=len(saved)==1 and saved[0]['title']=='Fixture homework' and saved[0]['course']=='Fixture course' and saved[0]['status']==('completed' if fixture=='todo_complete' else 'open')
                    final = outcome and ('task' in lower or 'completed' in lower)
                elif fixture=='note': final=bool(outcome) and 'benchmark review saved in isolated fixture' in lower
                elif fixture=='memory_store':
                    outcome=len(saved)==1 and saved[0].content=='my review day is Friday'
                    final=outcome and 'my review day is friday' in lower and 'remember' in lower
                elif fixture.startswith('app') or fixture in {'parse_after_write','duplicate_write'}:
                    outcome = len([call for call in row['handler_calls'] if call['capability']=='app.open'])==1
                    if fixture in {'app_running','app_accepted','app_exited','parse_after_write'}:
                        outcome=outcome and bool(successful)
                        final='notepad' in lower or 'launch request' in lower
                        if fixture!='app_running': final=final and ('could not verify' in lower or "couldn't verify" in lower or 'accepted' in lower) and 'independently verified' not in lower
                    else:
                        outcome=outcome and any(not result.ok for result in selected_results)
                        final=('unknown' in lower or 'unavailable' in lower or 'denied' in lower) and 'everything succeeded' not in lower
                elif fixture.startswith('mcp_'):
                    ledger_calls=[json.loads(line) for line in ledger.read_text().splitlines() if json.loads(line).get('event')=='call'] if ledger.exists() else []
                    outcome=len(ledger_calls)==1 and bool(successful) if fixture=='mcp_read' else not ledger_calls
                    final=('fixture evidence' in lower and 'was independently verified' not in lower and 'everything succeeded' not in lower) if fixture=='mcp_read' else ('could not' in lower or "couldn't" in lower or "can't" in lower) and 'everything succeeded' not in lower
                elif fixture.startswith('voice') or fixture.startswith('screen'):
                    # There is no generated assistant response at these fixed
                    # boundary adapters; hard-coded harness prose is not scored.
                    final=None
                row['stages']['outcome'] = bool(outcome)
                row['stages']['final_answer'] = final
                row['independent_outcome_check'] = bool(outcome)
                if actual_results and not row.get('observed_verification'):
                    row['observed_verification']=(getattr(actual_results[-1],'verification',None) or {}).get('status')
                row['passed'] = all(value is not False for value in row['stages'].values())
                row['objective_completed'] = row['expected_outcome_kind']=='positive' and row['stages'].get('outcome') is True
                row['verified_completion'] = row['objective_completed'] and row['stages'].get('final_answer') is True and row.get('observed_verification')=='VERIFIED'
                row['recovery_required'] = fixture in {'retry','calendar_retry'}
                row['recovery_success'] = bool(row['stages']['outcome'] and row['stages'].get('final_answer') is True) if row['recovery_required'] else None
                row['side_effect_attempts'] = len([call for call in row['handler_calls'] if call['capability']=='app.open']) if fixture.startswith('app') or fixture in {'parse_after_write','duplicate_write'} else len(event_bodies) if fixture.startswith('calendar') else len([call for call in row['handler_calls'] if call['capability'] in {'file.write','file.copy','file.move','file.delete','todo.add','todo.complete','note.append'}])
                row['duplicate_side_effects'] = max(0,row['side_effect_attempts']-1) if fixture in {'duplicate_write','calendar_timeout'} else 0
                row['read_retry_attempts'] = max(0,counts.get('system.stats',0)-1) if fixture == 'retry' else max(0,len(provider_reads)-1) if fixture=='calendar_retry' else 0
            except Exception as exc:
                row['harness_error'] = f'{type(exc).__name__}: {exc}'
            row['latency_ms'] = round((time.perf_counter()-started)*1000,3)
        results.append(row)
        print(f"{identifier}: {'PASS' if row['passed'] else 'FAIL'}",flush=True)
    output = args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    report = {'source_root':str(args.source_root.resolve()),'case_sha256':hashlib.sha256((ROOT/'tests/fixtures/reliability_workflows.py').read_bytes()).hexdigest(),
        'count':len(results),'passed':sum(row['passed'] for row in results),'results':results,
        'conditions':'Controlled DEVELOPMENT deterministic model; samecase/config/hardware; original gates/host/session. No live model/cloud/provider/audio/screen/user-data.',
        'latency_ms':{'p50':statistics.median(row['latency_ms'] for row in results),'p95':sorted(row['latency_ms'] for row in results)[int(.95*(len(results)-1))]},
        'stage_success':{key:{'passed':sum(row['stages'].get(key) is True for row in results),'applicable':sum(row['stages'].get(key) is not None for row in results)} for key in STAGES}}
    (output/'workflows.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'count':report['count'],'output':str(output)}))
    return 0

if __name__=='__main__': raise SystemExit(main())
