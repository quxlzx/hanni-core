"""Owner learning controls over the existing permissions, history and memory stores."""
from hanni.dashboard.features import RequestLedger, request_id
from hanni.native.learning import LearningReview


class LearningControls:
    def __init__(self, server):
        self.server, self.features = server, server.features
        self.features.learning_controls = self
        self.ledger = RequestLedger()
        self.engine = (LearningReview(self.features.root, server.chat, memory_store=self.features.memory_store,
                       model_loader=server.chat_commands.native_model) if self.features.root else None)
        if self.engine: self.engine.start()

    def snapshot(self):
        if not self.engine:
            return {'available': False, 'skills': [], 'proposals': [], 'memories': [], 'runs': [], 'reason': 'Learning requires the local HANNI configuration.'}
        skills = []
        for row in self.engine.skills.inventory():
            fields = ('name', 'description', 'triggers', 'origin', 'state', 'pinned', 'views', 'uses', 'patches', 'last_use', 'last_view', 'last_patch')
            skills.append({**{k: row.get(k) for k in fields}, 'revision': self.engine.skills._read(row['name'], archived=True)['revision']})
        try:
            memories = [r.to_dict() for r in self.features.memory_store().suggestions(limit=100) if r.source == 'learning_review']
        except RuntimeError: memories = []
        return {'available': True, 'skills': skills, 'settings': self.engine.settings(),
                'proposals': self.engine.skills.proposals(), 'memories': memories, 'runs': self.engine.runs(), 'reason': None}

    def journey(self):
        if not self.engine: return {'items': [], 'message': 'Learning is unavailable.'}
        items = [{**r, 'kind': 'skill', 'text': r['name'] + ': ' + r['action']} for r in self.engine.skills.journey()]
        try:
            from datetime import datetime
            store = self.features.memory_store()
            for memory in store.list(limit=100):
                items.append({'id': memory.id, 'kind': 'memory', 'created': memory.updated_at.timestamp(),
                              'text': memory.content, 'action': 'saved' if memory.created_at == memory.updated_at else 'corrected', 'source': memory.source})
                for previous in store.history(memory.id, limit=5):
                    items.append({'id': previous['revision_id'], 'kind': 'memory',
                                  'created': datetime.fromisoformat(previous['original_updated_at']).timestamp(),
                                  'text': previous['content'], 'action': 'previous revision', 'source': previous['source']})
        except RuntimeError: pass
        items += [{'id': r['id'], 'kind': 'review', 'created': r['updated'], 'text': r['result'].get('message', 'Reviewing a separate snapshot.'), 'action': r['state']} for r in self.engine.runs()]
        return {'items': sorted(items, key=lambda i: i['created'], reverse=True)[:200],
                'message': 'Saved instructions and personal notes; model weights are unchanged.'}

    def execute(self, body):
        if not self.engine: raise RuntimeError('Learning requires the local HANNI configuration.')
        if set(body) != {'id', 'operation', 'data'} or not isinstance(body['operation'], str) or not isinstance(body['data'], dict):
            raise ValueError('Expected request ID, learning operation and data.')
        key = request_id(body['id'])
        allowed = {'refine', 'curator', 'configure', 'skill.stage', 'skill.revise', 'skill.review', 'skill.lifecycle', 'memory.review', 'batch', 'batch.cancel', 'cancel'}
        if body['operation'] not in allowed: raise ValueError('Choose a supported learning action.')
        if body['operation'] == 'cancel':
            if set(body['data']) != {'review_id'}: raise ValueError('Choose an exact review ID.')
            return self.engine.cancel(body['data']['review_id'])
        return self.ledger.execute(key, body, lambda: self.features._execute(
            'learning.desktop_' + body['operation'], {'id': key, 'data': body['data']}, confirmed=True))

    def handle(self, operation, data, *, request_id):
        engine = self.engine
        if operation == 'refine':
            if set(data) != {'conversation', 'focus'} or not isinstance(data['focus'], str) or len(data['focus']) > 500:
                raise ValueError('Choose a conversation and optional focus of at most 500 characters.')
            return engine.begin(data['conversation'], key=request_id, focus=data['focus'])
        if operation == 'curator':
            if set(data) != {'dry_run', 'consolidate'} or any(type(v) is not bool for v in data.values()): raise ValueError('Choose dry-run and consolidation settings.')
            return engine.curator(**data)
        if operation == 'configure':
            if set(data) != {'settings', 'expected_revision'}: raise ValueError('Inspect the current learning settings.')
            return engine.configure(data['settings'], data['expected_revision'])
        if operation == 'skill.stage':
            return engine.skills.stage(data, source='owner_edit:' + request_id)
        if operation == 'skill.revise':
            if set(data) != {'proposal_id', 'revision', 'payload'}: raise ValueError('Inspect the exact proposal before revising it.')
            original = next((p for p in engine.skills.proposals() if p['id'] == data['proposal_id']), None)
            if not original: raise ValueError('The proposal changed. Inspect it before revising.')
            return engine.skills.stage(data['payload'], source=original['source'], absorbs=original['data']['absorbs'],
                                       replaces=(data['proposal_id'], data['revision']))
        if operation == 'skill.review':
            if set(data) != {'proposal_id', 'revision', 'action'}: raise ValueError('Inspect the exact skill diff before reviewing.')
            return engine.skills.review(data['proposal_id'], data['revision'], data['action'], protected=engine.protected_skills())
        if operation == 'skill.lifecycle':
            if set(data) != {'name', 'revision', 'action'}: raise ValueError('Inspect the current skill before changing its state.')
            return engine.skills.lifecycle(data['name'], data['revision'], data['action'])
        if operation == 'memory.review':
            if set(data) != {'suggestion_id', 'expected_updated_at', 'action', 'edited_content'}: raise ValueError('Inspect the current memory suggestion.')
            store = self.features.memory_store()
            suggestion = store.get_suggestion(data['suggestion_id'])
            if not suggestion or suggestion.source != 'learning_review': raise ValueError('Choose a learning review suggestion.')
            return store.review_suggestion(data['suggestion_id'], data['action'], expected_updated_at=data['expected_updated_at'], edited_content=data['edited_content']).to_dict()
        from hanni.native.training import TrainingStore
        training = TrainingStore(self.features.root)
        if operation == 'batch':
            if set(data) != {'prompts'}: raise ValueError('Provide a bounded list of batch prompts.')
            return training.submit(request_id, data['prompts'])
        if operation == 'batch.cancel':
            if set(data) != {'id'}: raise ValueError('Choose an exact batch ID.')
            return training.cancel(data['id'])
        raise ValueError('Unknown learning operation.')

    def close(self):
        if self.engine: self.engine.close()
