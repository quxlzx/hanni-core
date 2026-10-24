"""Task-local knowledge, progressive skills and isolated background jobs."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from ..hermes.state import TERMINAL, digest
from .skill_store import SkillStore


def agent_tool_specs():
    def spec(name, description, properties, required=()):
        return {'name': name, 'target': 'local', 'hash': 'native-agent-v1', 'remote': {},
                'schema': {'type': 'function', 'function': {'name': name, 'description': description,
                    'parameters': {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}}}}
    short = {'type': 'string', 'minLength': 1, 'maxLength': 500}
    tools = [
        spec('schedule_task', 'Create a persistent repeating task. Use for daily updates, hourly checks, or weekly reports; no workspace inspection is needed. '
             'Defaults to 09:00 in the configured timezone for daily/weekly schedules. Returns schedule ID and next run. '
             'Future runs may use read-only tools automatically; other actions need approval. Results return to this conversation while HANNI runs.',
             {'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 8000},
              'title': {'type': 'string', 'minLength': 1, 'maxLength': 120},
              'frequency': {'enum': ['hourly', 'daily', 'weekly', 'interval']},
              'at_time': {'type': 'string', 'pattern': '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$'},
              'timezone': short, 'weekday': {'type': 'integer', 'minimum': 0, 'maximum': 6},
              'interval_seconds': {'type': 'integer', 'minimum': 60, 'maximum': 31536000}}, ['prompt', 'title', 'frequency']),
        spec('scheduled_tasks', 'List, pause, resume, or delete saved repeating tasks by exact schedule ID. Pausing/deleting leaves already-submitted runs intact.',
             {'operation': {'enum': ['list', 'pause', 'resume', 'delete']}, 'id': short}, ['operation']),
        spec('skill_read', 'Load a named skill or its Markdown reference only when relevant. Returns its revision.',
             {'name': short, 'resource': short}, ['name']),
        spec('skill_save', 'Save or correct a reusable procedure after verification. Requires normal write approval. Read revision before updating; use empty revision to create. Evidence is a claim, not runtime verification.',
             {'name': short, 'description': short, 'instructions': {'type': 'string', 'maxLength': 20000},
              'triggers': {'type': 'array', 'maxItems': 12, 'items': short}, 'expected_revision': {'type': 'string', 'maxLength': 64},
              'verification': short, 'correction': short},
             ['name', 'description', 'instructions', 'triggers', 'expected_revision', 'verification', 'correction']),
        spec('memory_search', 'Search persistent personal/environment notes. Optional provider explicitly queries a configured, registered read-only MCP memory provider; never sends memories automatically.',
             {'query': short, 'scope': {'enum': ['all', 'user', 'environment']}, 'provider': short}, ['query']),
        spec('history_search', 'Retrieve older conversations separately from personal notes and current task state.', {'query': short}, ['query']),
        spec('session_search', 'Search detailed saved conversation history; facts belong in memory, reusable procedures in skills.', {'query': short}, ['query']),
        spec('working_state', 'Read or update this task journal: goals, constraints, completed work, blockers, next steps. Does not save personal memories or claim effects.',
             {key: {'type': 'string', 'maxLength': 3000} for key in ['goal', 'constraints', 'completed', 'blockers', 'next_steps']}),
        spec('delegate_task', 'Start a background subagent with separate messages and terminal working directory. Pass only relevant context and a subset of currently scoped tool names. Returns job ID; use agent_job to retrieve its final summary. Subagents cannot delegate again.',
             {'task': {'type': 'string', 'minLength': 1, 'maxLength': 4000}, 'context': {'type': 'string', 'maxLength': 6000},
              'tools': {'type': 'array', 'maxItems': 24, 'uniqueItems': True, 'items': short}}, ['task', 'tools']),
        spec('agent_job', 'Inspect or cancel a child owned by this task. Finished children return final summaries and receipt IDs, not their full transcript.',
             {'id': short, 'action': {'enum': ['status', 'result', 'cancel']}}, ['id']),
        spec('execute_code', 'Run bounded Python that can import hanni_tools.call(name, arguments). Calls use this task registry and normal approvals; only printed output is returned. Not an OS sandbox. No recursive orchestration.',
             {'code': {'type': 'string', 'minLength': 1, 'maxLength': 20000}}, ['code'])]
    staged = deepcopy(next(tool for tool in tools if tool['name'] == 'skill_save'))
    staged['name'] = staged['schema']['function']['name'] = 'skill_propose'
    staged['schema']['function']['description'] = ('Stage a reusable procedure learned from actual tool results, error recovery or owner corrections. '
        'Include working commands, tool names, pitfalls and verification. Read existing skills and patch rather than duplicate. '
        'Returns a reviewable diff; does not activate instructions or grant action permissions. Owner reviews it in Skills.')
    tools.append(staged)
    return tools


class AgentTools:
    def __init__(self, store, task, specs, *, cancelled):
        self.store, self.task, self.specs = store, task, specs
        self.root = store.path.parent
        self.skills = SkillStore(self.root)
        self.cancelled = cancelled
        self.runtime = None
        self.workspace = self.root / 'workspace'
        if task['request']['context'].get('parent_task_id'):
            self.workspace = self.workspace / 'sessions' / task['id']
        self.workspace.mkdir(parents=True, exist_ok=True)

    def execute(self, name, args, call_id):
        if name == 'schedule_task':
            if self.task['request']['context'].get('scheduled_job_id'):
                raise ValueError('This is an existing scheduled run. Perform its task once; do not create another repeating task.')
            from .scheduling import create_schedule
            job = create_schedule(self.root, args, conversation=self.task['request']['context'].get('conversation_id', 'default'),
                                  request_key=self.task['id'] + ':' + call_id)
            return {'ok': True, 'data': job, 'message': 'Repeating task saved. Next run: ' + job['next_run_local'] +
                    ' (' + job['timezone'] + '). ' + job['delivery']}
        if name == 'scheduled_tasks':
            from .scheduling import manage_schedules
            return {'ok': True, 'data': manage_schedules(self.root, args['operation'], args.get('id'))}
        if name == 'skill_read':
            return {'ok': True, 'data': self.skills.read(**args, source=self.task['id'] + ':' + str(call_id))}
        if name == 'skill_propose':
            proposal = self.skills.stage(args, source='task:' + self.task['id'])
            return {'ok': True, 'data': {'proposal_id': proposal['id'], 'status': proposal['status']},
                    'message': 'Skill diff staged for owner review in Skills. No instructions or model weights changed.'}
        if name == 'skill_save':
            return self.skills.save(**args, source='task:' + self.task['id'])
        if name == 'working_state':
            with self.store.transaction():
                previous = self.store.checkpoint(self.task['id']) or {}
                journal = previous.get('journal') or {'goal': self.task['request']['prompt']}
                journal.update(args)
                previous['journal'] = journal
                self.store.checkpoint(self.task['id'], previous)
            return {'ok': True, 'data': journal}
        if name == 'memory_search':
            provider = args.get('provider', 'local')
            if provider != 'local':
                config_path = self.root / 'memory-providers.json'
                providers = json.loads(config_path.read_text()) if config_path.exists() else {}
                configured = providers.get(provider) or {}
                tool = configured.get('tool')
                spec = next((s for s in self.specs if s['name'] == tool), None)
                if not spec or spec['target'] != 'mcp' or spec['remote'].get('classification') != 'read_only':
                    return {'ok': False, 'error_code': 'provider_unavailable', 'error': 'Memory provider requires an available approved read-only MCP tool.', 'effects': 'none'}
                return self.runtime.call(tool, {configured.get('query_parameter', 'query'): args['query']}, call_id + ':provider')
            from ..memory.store import MemoryStore
            memory = MemoryStore(self.root / 'memory.sqlite3')
            types = {'environment': {'device', 'project', 'workflow', 'environment'},
                     'user': {'preference', 'fact', 'decision', 'correction'}}.get(args.get('scope'))
            results = memory.search(args['query'], limit=12)
            records = [r.record.to_dict() for r in results if not types or r.record.memory_type in types]
            return {'ok': True, 'data': {'store': 'persistent_notes', 'records': records[:8]}}
        if name in {'history_search', 'session_search'}:
            path = self.root / 'dashboard-chat.sqlite3'
            if not path.exists():
                return {'ok': True, 'data': {'store': 'conversation_history', 'matches': []}}
            with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
                rows = db.execute("SELECT conversation,role,content,created FROM messages WHERE instr(lower(content), lower(?))>0 ORDER BY id DESC LIMIT 12", (args['query'],)).fetchall()
            return {'ok': True, 'data': {'store': 'conversation_history', 'matches': [
                {'conversation': row[0], 'role': row[1], 'text': row[2][:1200], 'created': row[3]} for row in rows]}}
        if name == 'delegate_task':
            if self.task['request']['context'].get('parent_task_id'):
                raise ValueError('Nested delegation is unavailable.')
            children = [t for t in self.store.active() if t['request']['context'].get('parent_task_id') == self.task['id']]
            if len(children) >= 2:
                raise ValueError('Two children are already active; inspect their results first.')
            allowed = {s['name'] for s in self.specs} - {'delegate_task'}
            if not set(args['tools']) <= allowed:
                raise ValueError('Child tools must be a subset of the parent registry.')
            context = {'parent_task_id': self.task['id'], 'allowed_tools': args['tools'],
                       'delegated_context': args.get('context', '')}
            # Copy the parent's authorization policy, never add privileges.
            if 'local_runtime' in self.task['request']['context']:
                context['local_runtime'] = deepcopy(self.task['request']['context']['local_runtime'])
            payload = {'prompt': args['task'], 'origin': 'hanni',
                       'windows_tools': self.task['request']['windows_tools'], 'context': context}
            child = self.store.submit('child-' + digest([self.task['id'], call_id]), payload)
            return {'ok': True, 'data': {'job_id': child['id'], 'state': child['state'],
                    'delivery': 'durable_job_result; retrieve with agent_job or /jobs result', 'separate_context': True}}
        if name == 'agent_job':
            child = self.store.get(args['id'])
            if child['request']['context'].get('parent_task_id') != self.task['id']:
                raise ValueError('Job is not owned by this parent task.')
            if args.get('action') == 'cancel':
                child = self.store.cancel(child['id'])
            result = child.get('result') or {}
            return {'ok': True, 'data': {'job_id': child['id'], 'state': child['state'], 'finished': child['state'] in TERMINAL,
                    'summary': result.get('model_claims', '')[:12000], 'error': child.get('error'),
                    'receipts': [a['id'] for a in child['actions']]}}
        if name == 'execute_code':
            from .code_execution import run_code
            return run_code(args['code'], runtime=self.runtime, call_id=call_id,
                            workspace=self.workspace, cancelled=self.cancelled)
        raise ValueError('Unknown agent capability.')
