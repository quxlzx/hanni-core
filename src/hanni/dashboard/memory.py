"""Authenticated Memory Explorer projections and fixed owner-review actions.

All mutations run through DesktopFeatures' original registry and stop/permission
gates. LAYA proposals have no authority here; the displayed exact record or
suggestion version must be explicitly confirmed by the owner.
"""
from __future__ import annotations

from hanni.dashboard.features import request_id
from hanni.dashboard.gateway import safe_value
from hanni.memory.privacy import validate_memory_text
from hanni.memory.projects import ProjectContext


OPERATIONS = frozenset({'remember', 'correct', 'forget', 'review', 'analyze', 'consolidate', 'project.alias', 'project.workflow', 'project.unlink'})


def _row(record):
    value = record.to_dict() if hasattr(record, 'to_dict') else dict(record)
    for key in ('content', 'source', 'source_ref', 'reason', 'uncertainty'):
        if value.get(key):
            try:
                validate_memory_text(value[key], max_chars=4000)
            except ValueError:
                value[key] = '[Private source withheld]'
    if isinstance(value.get('related_ids'), tuple):
        value['related_ids'] = list(value['related_ids'])
    # Stored confidence is an extraction hint, not an independently calibrated
    # probability. Its numeric value is deliberately absent from this interface.
    value.pop('confidence', None)
    value['confidence_calibrated'] = False
    return safe_value(value)


def _integer(value, default, *, minimum=0, maximum=10000):
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError('Use a valid bounded page number.')
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError('Use a valid bounded page number.') from None
    if str(number) != str(value) or not minimum <= number <= maximum:
        raise ValueError('Use a valid bounded page number.')
    return number


class MemoryExplorer:
    def __init__(self, features, *, workflow_reader=None):
        self.features = features
        self.workflow_reader = workflow_reader

    def projects(self, store=None):
        return ProjectContext(store or self.features.memory_store(), self.features.store, self.workflow_reader)

    def status(self):
        from hanni.laya.manager import current_manager
        manager = current_manager()
        actual = getattr(manager, 'status', 'disabled')
        advisory = None
        try:
            from hanni.laya.runtime import current_advisory
            advisory = current_advisory(self.features.config) if self.features.config is not None else None
        except ImportError:
            pass
        requested = bool(self.features.config and self.features.config.hanni.laya.advisory_enabled)
        advisory_state = getattr(advisory, 'status', 'unavailable: independent model gate not verified' if requested else 'disabled')
        if advisory_state != 'disabled':
            actual = advisory_state
        mode = ('connecting' if actual == 'connecting' else 'shadow' if actual == 'shadow connected'
                else 'advisory' if actual == 'advisory' else 'production retrieval enabled' if actual == 'production retrieval enabled'
                else 'unavailable' if str(actual).startswith('unavailable') else 'disabled')
        return {'mode': mode, 'description': {
            'disabled': 'LAYA inference is disabled. Local deterministic memory remains available.',
            'connecting': 'Connecting to the explicitly enabled optional LAYA service.',
            'shadow': 'Observe-only inference. Predictions do not alter memory or context.',
            'advisory': 'Validated inference supplies untrusted proposals; owner review remains required.',
            'production retrieval enabled': 'Explicitly enabled validated ranking influences context; deterministic retrieval remains the fallback.',
            'unavailable': 'LAYA inference is unavailable. Local deterministic retrieval continues.'}[mode],
            'model_inference_active': mode in {'shadow', 'advisory', 'production retrieval enabled'},
            'production_retrieval_active': mode == 'production retrieval enabled',
            'deterministic_context_enabled': bool(self.features.config and self.features.config.hanni.memory.context_enabled),
            # This is the effective permission to transmit, not a claim that a
            # request occurred. Read the matching live client's original gates;
            # configured intent alone cannot enable a remote memory boundary.
            'remote_memory_transmission': bool(advisory is not None and advisory.transport == 'remote-ssh'
                                               and advisory._rank_allowed()),
            'semantic_search_available': False}

    def browse(self, query=None):
        query = query or {}
        if set(query) - {'q', 'type', 'project', 'offset', 'limit', 'sort'}:
            raise ValueError('Choose supported memory filters.')
        text = query.get('q', '')
        if not isinstance(text, str) or len(text) > 500:
            raise ValueError('Use a search query of at most 500 characters.')
        limit = _integer(query.get('limit'), 30, minimum=1, maximum=50)
        offset = _integer(query.get('offset'), 0)
        order = query.get('sort', 'updated')
        if order not in {'updated', 'created'}:
            raise ValueError('Choose a supported memory order.')
        filters = {'project_id': query.get('project') or None, 'memory_type': query.get('type') or None}
        if any(value is not None and (not isinstance(value, str) or len(value) > 100) for value in filters.values()):
            raise ValueError('Choose a valid project and memory type.')
        try:
            store = self.features.memory_store()
        except RuntimeError as exc:
            return {'available': False, 'records': [], 'projects': [], 'reason': str(exc), 'status': self.status()}
        projects = self.projects(store).projects()
        if filters['project_id'] and not any(item['id'] == filters['project_id'] for item in projects):
            raise ValueError('The selected project no longer exists.')
        records = ([item.record for item in store.search(text, limit=limit + 1, offset=offset, **filters)]
                   if text.strip() else store.list(limit=limit + 1, offset=offset, sort=order, **filters))
        rows = []
        for record in records[:limit]:
            try:
                validate_memory_text(record.content, max_chars=store.max_item_chars)
            except ValueError:
                continue
            rows.append(_row(record))
        return {'available': True, 'records': rows, 'projects': [safe_value(row) for row in projects],
                'total_stored': store.count(), 'filtered_count': store.count(**filters) if not text.strip() else None,
                'pending_suggestions': store.count_suggestions(status='pending'),
                'offset': offset, 'limit': limit, 'has_more': len(records) > limit,
                'reason': None, 'source': 'authoritative-memory', 'status': self.status(),
                'actions': {'correct': True, 'forget': True, 'review': True}}

    def detail(self, memory_id, query=None):
        query = query or {}
        if set(query) - {'offset', 'limit'}:
            raise ValueError('Choose supported correction history filters.')
        offset = _integer(query.get('offset'), 0)
        limit = _integer(query.get('limit'), 50, minimum=1, maximum=50)
        store = self.features.memory_store()
        record = store.get(memory_id)
        if record is None:
            return {'available': True, 'record': None, 'history': [], 'reason': 'This memory was deleted or is unavailable.'}
        validate_memory_text(record.content, max_chars=store.max_item_chars)
        history = []
        withheld = 0
        items = store.history(memory_id, limit=limit + 1, offset=offset)
        for item in items[:limit]:
            try:
                validate_memory_text(item['content'], max_chars=store.max_item_chars)
            except ValueError:
                withheld += 1
                continue
            history.append(_row({**item, 'updated_at': item['original_updated_at']}))
        project, missing = None, False
        if record.project_id:
            try:
                project = safe_value(self.projects(store).project(record.project_id))
            except ValueError:
                missing = True
        return {'available': True, 'record': _row(record), 'history': history,
                'history_count': store.count_history(memory_id), 'history_offset': offset, 'history_limit': limit,
                'history_withheld': withheld,
                'history_has_more': len(items) > limit,
                'project': project, 'project_missing': missing, 'reason': None}

    def suggestions(self, query=None):
        query = query or {}
        if set(query) - {'offset', 'limit', 'status'}:
            raise ValueError('Choose supported suggestion filters.')
        status = query.get('status', 'pending')
        if status not in {'pending', 'approved', 'rejected', 'dismissed'}:
            raise ValueError('Choose a supported suggestion state.')
        offset = _integer(query.get('offset'), 0)
        limit = _integer(query.get('limit'), 20, minimum=1, maximum=50)
        store = self.features.memory_store()
        rows = store.suggestions(status=status, limit=limit + 1, offset=offset)
        return {'available': True, 'items': [_row(row) for row in rows[:limit]],
                'offset': offset, 'limit': limit, 'has_more': len(rows) > limit,
                'total': store.count_suggestions(status=status), 'status': self.status(), 'reason': None}

    def project(self, project_id):
        package = self.projects().package(project_id, max_records=20, max_chars=8000)
        context = {key: ([safe_value(row) for row in value] if isinstance(value, list) else safe_value(value))
                   for key, value in package.items() if key != 'context_text'}
        # The package builder already privacy-checks each contributing source
        # and bounds this exact text. Generic audit redaction's 2K string cap
        # must not silently change the displayed context while retaining an
        # inaccurate character count.
        context['context_text'] = package['context_text']
        return {'available': True, 'context': context, 'reason': None}

    def mutate(self, body):
        self.features.require()
        if not isinstance(body, dict) or set(body) != {'id', 'operation', 'data', 'confirmed'}:
            raise ValueError('Expected request ID, fixed memory operation, data and explicit confirmation.')
        if body['confirmed'] is not True or not isinstance(body['data'], dict):
            raise ValueError('Confirm the displayed memory change before applying it.')
        if not isinstance(body['operation'], str) or body['operation'] not in OPERATIONS:
            raise ValueError('Unsupported memory operation.')
        key = request_id(body['id'])
        payload = {'id': key, 'data': body['data']}
        return self.features.ledger.execute(key, body, lambda: self.features._execute(
            'memory.desktop_' + body['operation'], payload,
            destructive=body['operation'] == 'forget', confirmed=True))

    def handle(self, operation, data, *, request_id=None):
        # Called only by the fixed audited registry handler after authorization.
        if operation == 'remember':
            expected = {'content'}
        elif operation == 'forget':
            expected = {'memory_id', 'expected_updated_at'}
        elif operation == 'correct':
            expected = {'memory_id', 'expected_updated_at', 'content', 'project_id', 'semantic_status'}
        elif operation == 'review':
            expected = {'suggestion_id', 'expected_updated_at', 'action', 'edited_content'}
        elif operation == 'project.alias':
            expected = {'project_id', 'expected_fingerprint', 'alias'}
        elif operation == 'project.workflow':
            expected = {'project_id', 'expected_fingerprint', 'workflow_id'}
        elif operation == 'project.unlink':
            expected = {'project_id', 'expected_fingerprint', 'kind', 'value'}
        elif operation == 'analyze':
            expected = {'content', 'project_id'}
        elif operation == 'consolidate':
            expected = {'project_id'}
        else:
            raise ValueError('Unsupported memory operation.')
        if set(data) != expected:
            raise ValueError('Inspect the exact current record and use its supported fields.')
        if operation.startswith('project.'):
            if not isinstance(data.get('project_id'), str) or not isinstance(data.get('expected_fingerprint'), str):
                raise ValueError('Select an exact current project version.')
            projects = self.projects()
            if operation == 'project.alias':
                return projects.add_alias(data['project_id'], data['alias'], expected_fingerprint=data['expected_fingerprint'])
            if operation == 'project.unlink':
                return projects.remove_link(data['project_id'], data['kind'], data['value'], expected_fingerprint=data['expected_fingerprint'])
            return projects.link_workflow(data['project_id'], data['workflow_id'], expected_fingerprint=data['expected_fingerprint'])
        store = self.features.memory_store()
        if operation == 'remember':
            if not isinstance(data['content'], str):
                raise ValueError('Enter a fact or preference to remember.')
            record, created = store.remember(data['content'], source='owner_explicit:command')
            return {'record': _row(record), 'duplicate': not created}
        if operation in {'analyze', 'consolidate'}:
            from hanni.laya.intelligence import analyze_statement, analyze_relationships
            if not isinstance(data['project_id'], str):
                raise ValueError('Choose a saved project or leave it unassigned.')
            if data['project_id']:
                self.projects(store).project(data['project_id'])
            if store.count_suggestions(status='pending') >= 500:
                raise ValueError('Review the existing pending suggestions before creating more.')
            if operation == 'analyze':
                if not isinstance(data['content'], str):
                    raise ValueError('Provide an explicit owner statement.')
                candidate = analyze_statement(data['content'], max_chars=store.max_item_chars,
                    source_ref='desktop-review-request:' + str(request_id))
                if candidate is None:
                    return {'created': 0, 'message': 'No conservative reusable memory candidate was found. Nothing was saved.'}
                suggestion = store.propose('add', candidate.content, source='owner_requested:local_rules',
                    source_ref=candidate.source_ref, project_id=data['project_id'], semantic_status=candidate.semantic_status,
                    reason=candidate.reason, uncertainty=candidate.uncertainty)
                return {'created': 1, 'suggestion': _row(suggestion), 'message': 'A local rule suggestion is awaiting your review. No fact was saved.'}
            records = store.list(limit=200, project_id=data['project_id'] or None)
            proposals = analyze_relationships(records, limit=50)
            by_id = {row.id: row for row in records}
            existing = {(row.kind, tuple(sorted(row.related_ids))) for row in store.suggestions(limit=500)}
            created = 0
            for proposal in proposals:
                if (proposal.kind, tuple(sorted(proposal.memory_ids))) in existing:
                    continue
                target = by_id[proposal.memory_ids[0]]
                store.propose(proposal.kind, target.content, source='owner_requested:local_rules',
                    source_ref='memory:' + ','.join(proposal.memory_ids), target_id=target.id,
                    expected_updated_at=target.updated_at.isoformat(), project_id=target.project_id,
                    semantic_status='statement', reason=proposal.reason, uncertainty=proposal.uncertainty,
                    related_ids=proposal.memory_ids)
                created += 1
            return {'created': created, 'scanned': len(records), 'message':
                    'Local relationship suggestions await explicit record review. No memory was changed or deleted.'}
        if not isinstance(data['expected_updated_at'], str) or not 1 <= len(data['expected_updated_at']) <= 100:
            raise ValueError('Inspect the current version before changing this record.')
        if operation == 'review':
            if (not isinstance(data['suggestion_id'], str) or not 1 <= len(data['suggestion_id']) <= 100
                    or not isinstance(data['action'], str) or data['action'] not in {'approve', 'reject', 'dismiss'}
                    or data['edited_content'] is not None and not isinstance(data['edited_content'], str)):
                raise ValueError('Choose a valid exact suggestion and review action.')
            suggestion = store.get_suggestion(data['suggestion_id'])
            if suggestion and suggestion.project_id and data['action'] == 'approve':
                self.projects(store).project(suggestion.project_id)
            result = store.review_suggestion(data['suggestion_id'], data['action'],
                expected_updated_at=data['expected_updated_at'], edited_content=data['edited_content'])
            return {'suggestion': _row(result)}
        if not isinstance(data['memory_id'], str) or not 1 <= len(data['memory_id']) <= 100:
            raise ValueError('Choose an exact memory record.')
        record = store.get(data['memory_id'])
        if record is None:
            raise ValueError('The memory no longer exists. Refresh before changing it.')
        if operation == 'forget':
            return {'deleted': store.delete(record.id, expected_updated_at=data['expected_updated_at'])}
        if data['project_id']:
            self.projects(store).project(data['project_id'])
        if (not isinstance(data['content'], str) or not isinstance(data['project_id'], str)
                or not isinstance(data['semantic_status'], str)
                or data['semantic_status'] not in {'statement', 'plan', 'decision', 'question', 'hypothetical', 'inference',
                                                   'completed_claim', 'historical', 'failed_claim', 'temporary'}):
            raise ValueError('Use supported text, project identity and statement type; outcome verification is controller-owned.')
        record = store.correct(record.id, data['content'], expected_updated_at=data['expected_updated_at'],
            project_id=data['project_id'], semantic_status=data['semantic_status'], source='owner_explicit:desktop-correction')
        return {'record': _row(record)}
