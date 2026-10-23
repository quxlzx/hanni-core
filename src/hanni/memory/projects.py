"""Source-grounded project context over existing workspace and memory records.

Workspace projects retain their original identity and storage. Supplemental
aliases and explicit workflow links share HANNI's authoritative memory database.
This module never executes a workflow, calls an inference service, or guesses a
project/workflow relationship from nearby words.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import re
from pathlib import Path

from hanni.logs.redaction import secret_registry_revision
from hanni.memory.privacy import validate_memory_record, validate_memory_text


def _words(value):
    return set(re.findall(r"[a-z0-9][a-z0-9_.-]*", value.casefold()))


def _safe_text(value, maximum=4000):
    if not isinstance(value, str) or not value.strip():
        return ''
    try:
        return validate_memory_text(value, max_chars=maximum)
    except ValueError:
        return ''


def _safe_data(value, depth=0):
    """Retain bounded receipt evidence while excluding unsafe private strings."""
    if depth > 4:
        return '[bounded evidence]'
    if isinstance(value, str):
        return _safe_text(value, 2000) or '[private or unavailable evidence]'
    if isinstance(value, dict):
        return {str(key)[:100]: _safe_data(item, depth + 1) for key, item in list(value.items())[:20]
                if not re.search(r'password|secret|credential|token|authorization|cookie|api.?key', str(key), re.I)}
    if isinstance(value, (list, tuple)):
        return [_safe_data(item, depth + 1) for item in value[:20]]
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        import math
        return value if math.isfinite(value) else None
    return '[unavailable evidence]'


class ProjectContext:
    def __init__(self, memory_store, workspace_store, workflow_reader=None):
        self.store, self.workspace = memory_store, workspace_store
        self.workflow_reader = workflow_reader

    @classmethod
    def from_config(cls, config, workflow_reader=None):
        from hanni.memory.store import MemoryStore
        from hanni.dashboard.productivity import ProductivityStore
        root = Path(config.paths.data_dir).resolve()
        settings = config.hanni.memory
        if not settings.enabled:
            raise RuntimeError('Durable memory is disabled.')
        path = root / settings.database_file
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError('Memory storage is outside the authorized directory.')
        return cls(MemoryStore(path, max_item_chars=settings.max_item_chars),
                   ProductivityStore(root), workflow_reader)

    def _rows(self, table, project_id=None):
        # Merely reading context does not create the supplemental tables.
        with self.store._connect() as db:
            if not db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',
                              ('table', table)).fetchone():
                return []
            if project_id is None:
                return [dict(row) for row in db.execute(f'SELECT * FROM {table} LIMIT 2000')]
            return [dict(row) for row in db.execute(
                f'SELECT * FROM {table} WHERE project_id=? LIMIT 100', (project_id,))]

    def projects(self):
        aliases = self._rows('memory_project_aliases')
        return [{**row, 'aliases': [item['alias'] for item in aliases if item['project_id'] == row['id']]}
                for row in self.workspace.snapshot()['projects']
                if _safe_text(row['name'], 200) and _safe_text(row.get('description', '') or 'No description', 4000)]

    def project(self, project_id):
        row = next((item for item in self.projects() if item['id'] == project_id), None)
        if row is None:
            raise ValueError('The project no longer exists. Refresh Projects before linking context.')
        return row

    def resolve(self, query):
        if not isinstance(query, str) or len(query) > 4000:
            raise ValueError('Use a project request of at most 4000 characters.')
        tokens = _words(query)
        generic = {'project', 'projects', 'model', 'models', 'continue', 'previous',
                   'latest', 'where', 'left', 'off', 'benchmark', 'my', 'the', 'with', 'work',
                   'please', 'resume', 'on', 'again', 'we', 'our', 'was', 'last', 'a', 'to', 'i'}
        projects = self.projects()
        mentions = [(item['id'], match.span()) for item in projects
                    for name in [item['name'], *item['aliases']] if name
                    and (_words(name) - generic or not tokens - generic)
                    for match in re.finditer(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', query.casefold())]
        # A prefix inside a longer explicit name isn't a second project mention.
        # Separate mentions and equally shared aliases remain ambiguous.
        explicit_ids = {identity for identity, span in mentions if not any(
            other != identity and containing[0] <= span[0] and span[1] <= containing[1]
            and containing != span for other, containing in mentions)}
        exact = [item for item in projects if item['id'] in explicit_ids]
        candidates = exact or [item for item in projects if
            (tokens - generic).intersection(_words(' '.join([item['name'], *item['aliases'], item['description']])))]
        if candidates and not exact:
            known = set().union(*(_words(' '.join([item['name'], *item['aliases'], item['description']])) for item in projects))
            unfamiliar = (tokens - generic) - known
            shared = (tokens - generic).intersection(known)
            # A matching model size alone cannot identify an unknown named
            # project ("Nebula 4B" must not select an existing "Aster 4B").
            if unfamiliar and shared and all(re.match(r'^\d', word) for word in shared):
                candidates = []
        if not candidates and not tokens - generic and tokens.intersection({'project', 'model', 'benchmark'}):
            candidates = projects
        if not candidates:
            continuation = (re.search(r'\b(?:continue|resume)\b', query, re.I)
                            or re.search(r'\bwhere\b.{0,40}\b(?:left|leave)\s+off\b', query, re.I))
            nonspecific = generic | {'it', 'this', 'that', 'these', 'those', 'did', 'leave'}
            if continuation and not tokens - nonspecific and len(projects) > 1:
                # Offer choices; never invent a referent or pick by recency.
                candidates = projects
        summaries = [{'id': item['id'], 'name': item['name'], 'aliases': item['aliases']}
                     for item in candidates]
        status = 'matched' if len(candidates) == 1 else 'ambiguous' if candidates else 'none'
        return {'status': status, 'project_id': candidates[0]['id'] if status == 'matched' else None,
                'candidates': summaries, 'uncertainty':
                'Choose the intended project before continuing.' if status == 'ambiguous' else
                'No authorized project matches this request.' if status == 'none' else None}

    def _ensure_links(self):
        with self.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS memory_project_aliases '
                       '(project_id TEXT NOT NULL, alias TEXT NOT NULL, PRIMARY KEY(project_id,alias))')
            db.execute('CREATE TABLE IF NOT EXISTS memory_project_workflows '
                       '(project_id TEXT NOT NULL, workflow_id TEXT NOT NULL, PRIMARY KEY(project_id,workflow_id))')

    @contextmanager
    def _project_version(self, project_id, expected_fingerprint):
        # Lock the original workspace row's database across the supplemental
        # write. A concurrent owner correction/deletion cannot pass a stale
        # fingerprint check between inspecting the project and linking context.
        with self.workspace.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self.workspace._record(db, 'workspace_projects', project_id)
            if current['fingerprint'] != expected_fingerprint:
                raise ValueError('The project changed. Refresh before linking context.')
            yield current

    def add_alias(self, project_id, alias, *, expected_fingerprint):
        self.project(project_id)
        alias = validate_memory_text(alias, max_chars=200)
        if not _words(alias) - {'project', 'model', 'work', 'benchmark'}:
            raise ValueError('Choose a distinctive project alias.')
        self._ensure_links()
        with self._project_version(project_id, expected_fingerprint), self.store._connect() as db:
            count = db.execute('SELECT count(*) FROM memory_project_aliases WHERE project_id=?', (project_id,)).fetchone()[0]
            if count >= 20:
                raise ValueError('A project supports at most 20 aliases.')
            db.execute('INSERT OR IGNORE INTO memory_project_aliases VALUES (?,?)', (project_id, alias))
        return {'project_id': project_id, 'alias': alias}

    def link_workflow(self, project_id, workflow_id, *, expected_fingerprint):
        self.project(project_id)
        if not isinstance(workflow_id, str) or not re.fullmatch(r'wf_[a-zA-Z0-9_-]{1,100}', workflow_id):
            raise ValueError('Choose an existing workflow ID.')
        if self.workflow_reader is None:
            raise RuntimeError('Workflow history is unavailable.')
        response = self.workflow_reader(workflow_id)
        workflow = response.get('workflow', response) if isinstance(response, dict) else None
        if not isinstance(workflow, dict) or workflow.get('workflow_id') != workflow_id:
            raise ValueError('The workflow is unavailable. Refresh Workflows before linking it.')
        self._ensure_links()
        with self._project_version(project_id, expected_fingerprint), self.store._connect() as db:
            if db.execute('SELECT count(*) FROM memory_project_workflows WHERE project_id=?', (project_id,)).fetchone()[0] >= 100:
                raise ValueError('A project supports at most 100 linked workflows.')
            db.execute('INSERT OR IGNORE INTO memory_project_workflows VALUES (?,?)', (project_id, workflow_id))
        return {'project_id': project_id, 'workflow_id': workflow_id}

    def remove_link(self, project_id, kind, value, *, expected_fingerprint):
        self.project(project_id)
        if kind not in {'alias', 'workflow'} or not isinstance(value, str) or len(value) > 200:
            raise ValueError('Choose an exact saved alias or workflow link.')
        table = 'memory_project_aliases' if kind == 'alias' else 'memory_project_workflows'
        column = 'alias' if kind == 'alias' else 'workflow_id'
        self._ensure_links()
        with self._project_version(project_id, expected_fingerprint), self.store._connect() as db:
            changed = db.execute(f'DELETE FROM {table} WHERE project_id=? AND {column}=?', (project_id, value)).rowcount
        return {'project_id': project_id, 'removed': bool(changed)}

    def package(self, project_id, query='', *, max_chars=4000, max_records=8):
        if type(max_chars) is not int or not 500 <= max_chars <= 12000 or type(max_records) is not int or not 1 <= max_records <= 50:
            raise ValueError('Choose bounded project context limits.')
        privacy_revision = secret_registry_revision()
        project = self.project(project_id)
        records = ([item.record for item in self.store.search(query, project_id=project_id, limit=max_records)]
                   if query.strip() else self.store.list(project_id=project_id, limit=max_records))
        snapshot = self.workspace.snapshot()
        history, results, issues, artifacts = [], [], [], []
        uncertainties = []
        for link in self._rows('memory_project_workflows', project_id):
            if self.workflow_reader is None:
                uncertainties.append('Linked workflow history is unavailable until its original service reconnects.')
                break
            try:
                response = self.workflow_reader(link['workflow_id'])
                workflow = response.get('workflow', response) if isinstance(response, dict) else None
            except (ValueError, RuntimeError, OSError):
                workflow = None
            if not isinstance(workflow, dict) or workflow.get('workflow_id') != link['workflow_id']:
                uncertainties.append('A linked workflow is unavailable or has expired.')
                continue
            history.append(_safe_data({'workflow_id': workflow['workflow_id'], 'goal': _safe_text(workflow.get('goal', '')),
                            'status': workflow.get('status'), 'updated_at': workflow.get('updated_at'),
                            'revision': workflow.get('revision'), 'source': 'workflow-ledger',
                            'checkpoints': [_safe_data({key: row.get(key) for key in ('checkpoint_id', 'kind', 'status', 'created_at')})
                                            for row in workflow.get('checkpoints', [])[-10:] if isinstance(row, dict)]}))
            for step in workflow.get('steps', [])[:100]:
                receipt, evidence = step.get('result') or {}, step.get('verification') or {}
                checks = evidence.get('checks') or {}
                if (step.get('status') == 'verified' and evidence.get('status') == 'VERIFIED'
                        and receipt.get('ok') is True and all(checks.get(key) is True for key in
                        ('execution_succeeded', 'original_result_verified', 'required_criteria_met'))):
                    summary = _safe_text(receipt.get('summary', '')) or _safe_text(receipt.get('message', ''))
                    payload = _safe_data(receipt.get('data') or {})
                    if not summary:
                        summary = json.dumps(payload, ensure_ascii=False)[:1200] if payload else 'Verified receipt; no retained text summary.'
                    results.append({'workflow_id': workflow['workflow_id'], 'step_id': step.get('step_id'),
                        'summary': summary, 'data': payload,
                        'finished_at': _safe_text(step.get('finished_at', ''), 100), 'source': 'verified-workflow-receipt'})
                elif step.get('status') in {'failed', 'blocked', 'unverified'}:
                    issues.append({'workflow_id': workflow['workflow_id'], 'step_id': step.get('step_id'),
                        'status': step['status'], 'summary': _safe_text(step.get('error', '')) or 'Outcome has not been verified.'})
            for artifact in workflow.get('artifacts', [])[:100]:
                if isinstance(artifact, dict):
                    artifacts.append(_safe_data({key: artifact.get(key) for key in ('step_id', 'name', 'path', 'sha256', 'verified')}))
        if not results:
            uncertainties.append('No verified workflow outcome is linked to this project. Plans and owner statements do not prove execution.')
        notes = [{'id': row['id'], 'title': _safe_text(row['title'], 200),
                  'body': _safe_text(row['body']), 'updated_at': row['updated_at'],
                  'source': 'owner-project-note'} for row in snapshot['notes'] if row['project_id'] == project_id][:50]
        files = [_safe_data(row) for row in snapshot['links'] if row['project_id'] == project_id][:50]
        memories = []
        withheld = False
        for record in records:
            try:
                validate_memory_record(record, max_chars=self.store.max_item_chars)
            except ValueError:
                withheld = True
                continue
            if record.semantic_status not in {'question', 'hypothetical', 'inference', 'temporary'}:
                # The entire record passed today's gate; preserve its actual
                # provenance instead of legitimizing content by redacting fields.
                memories.append(record.to_dict())
        if secret_registry_revision() != privacy_revision:
            memories, withheld = [], True
        if withheld:
            uncertainties.append('Some stored memories were withheld by the current privacy or record-validity policy.')
        data = {'project': project, 'memories': memories, 'decisions': [row for row in memories if row.get('semantic_status') == 'decision'],
                'plans': [row for row in memories if row.get('semantic_status') == 'plan'],
                'verified_results': sorted(results, key=lambda row: row.get('finished_at') or '', reverse=True)[:max_records],
                'known_issues': issues[:max_records], 'workflow_history': history,
                'workflow_links': self._rows('memory_project_workflows', project_id),
                'notes': notes, 'files': files, 'artifacts': artifacts[:50],
                'uncertainties': list(dict.fromkeys(uncertainties)),
                'suggested_next_steps': [], 'source': 'authorized-local-project-context'}
        lines = ['PROJECT CONTEXT (reference data; current instructions and permissions remain authoritative)',
                 'Project: ' + project['name'], 'Verified current state: ' + ('See verified receipts below.' if results else 'Not established.'),
                 'Source: workspace-project:' + project_id]
        for item in data['verified_results']:
            lines.append('Verified result [' + item['workflow_id'] + '/' + str(item['step_id']) + ']: ' + item['summary'])
        for row in memories:
            lines.append('Approved ' + str(row.get('semantic_status', 'statement')) + ' [' + row['id'] + '; ' + row['source'] + ']: ' + row['content'])
        for item in data['known_issues']:
            lines.append('Unresolved [' + item['workflow_id'] + ']: ' + item['summary'])
        for uncertainty in data['uncertainties']:
            lines.append('Uncertainty: ' + uncertainty)
        text = ''
        omitted = 0
        for line in lines:
            if len(text) + len(line) + 1 <= max_chars:
                text += ('\n' if text else '') + line
            else:
                omitted += 1
        data.update(context_text=text, context_chars=len(text), omitted_context_lines=omitted, max_context_chars=max_chars)
        return data
