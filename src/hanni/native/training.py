"""Read-only batch tasks and portable, explicit trajectory exports. No trainer runs here."""
import argparse
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import time

from hanni.hermes.state import TaskStore, TERMINAL, digest
from hanni.logs.redaction import redact_text

BATCH_TOOLS = ('local_read_file', 'local_read_document', 'local_list_dir', 'local_search_files',
               'web_search', 'web_fetch', 'system_info', 'skill_read', 'session_search', 'history_search', 'memory_search', 'working_state')


class TrainingStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, fingerprint TEXT, tasks TEXT, created REAL)')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.root / 'training.sqlite3', timeout=10)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback(); raise
        finally: db.close()

    def submit(self, key, prompts):
        if not isinstance(key, str) or not 1 <= len(key) <= 64: raise ValueError('Use a bounded batch request ID.')
        if not isinstance(prompts, list) or not 1 <= len(prompts) <= 20 or any(not isinstance(p, str) or not p.strip() or len(p) > 8000 for p in prompts):
            raise ValueError('Provide 1-20 nonempty prompts, at most 8000 characters each.')
        fingerprint = digest(prompts)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT fingerprint,tasks FROM batches WHERE id=?', (key,)).fetchone()
            if old:
                if old[0] != fingerprint: raise ValueError('Batch ID was already used for different prompts.')
                return {'id': key, 'task_ids': json.loads(old[1]), 'message': 'Existing read-only batch; tasks were not replayed.'}
            store = TaskStore(self.root / 'tasks.sqlite3')
            ids = []
            try:
                if len(store.active()) + len(prompts) > 256: raise ValueError('Finish active tasks before submitting this batch.')
                with store.transaction():
                    for index, prompt in enumerate(prompts):
                        task = store.submit('training-' + digest([key, index]), {'prompt': prompt, 'windows_tools': [], 'origin': 'hanni',
                            'context': {'batch_id': key, 'allowed_tools': list(BATCH_TOOLS),
                                        'local_runtime': {'auto_approve': list(BATCH_TOOLS)}}})
                        ids.append(task['id'])
                db.execute('INSERT INTO batches VALUES(?,?,?,?)', (key, fingerprint, json.dumps(ids), time.time()))
            finally: store.close()
        return {'id': key, 'task_ids': ids, 'message': 'Read-only batch queued. Each task has its own conversation and working state; inspect /jobs for execution results.'}

    def batches(self):
        with self._db() as db: rows = db.execute('SELECT id,tasks,created FROM batches ORDER BY created DESC LIMIT 30').fetchall()
        store = TaskStore(self.root / 'tasks.sqlite3')
        try:
            return {'batches': [{'id': key, 'created': created, 'tasks': [{'id': t, 'state': store.get(t)['state']} for t in json.loads(ids)]} for key, ids, created in rows]}
        finally: store.close()

    def cancel(self, key):
        with self._db() as db: row = db.execute('SELECT tasks FROM batches WHERE id=?', (key,)).fetchone()
        if not row: raise ValueError('Batch not found.')
        store = TaskStore(self.root / 'tasks.sqlite3')
        try:
            for task in json.loads(row[0]): store.cancel(task)
        finally: store.close()
        return {'id': key, 'message': 'Batch cancellation requested. Existing receipts and completed effects remain.'}

    def export(self, batch='', format='trajectory'):
        if format not in {'trajectory', 'sharegpt'}: raise ValueError('Choose trajectory or sharegpt format.')
        store = TaskStore(self.root / 'tasks.sqlite3')
        try:
            if batch:
                with self._db() as db: row = db.execute('SELECT tasks FROM batches WHERE id=?', (batch,)).fetchone()
                if not row: raise ValueError('Batch not found.')
                ids = json.loads(row[0])
            else:
                ids = [r[0] for r in store.db.execute('SELECT id FROM tasks ORDER BY rowid DESC LIMIT 50')]
            records = [trajectory(store, key) for key in ids if store.get(key)['state'] in TERMINAL]
            records = [r for r in records if r['messages']]
        finally: store.close()
        if format == 'sharegpt':
            records = [{'id': row['id'], 'conversations': [
                {'from': {'user': 'human', 'assistant': 'gpt', 'tool': 'tool'}[m['role']],
                 'value': json.dumps(m, ensure_ascii=False) if m.get('tool_calls') or m['role'] == 'tool' else m.get('content', '')}
                for m in row['messages']], 'metadata': {k: row[k] for k in ('state', 'reward', 'verified_success', 'stats')}} for row in records]
        content = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in records)
        if len(content.encode()) > 8 * 1024 * 1024: raise ValueError('Export exceeds 8 MiB. Export one batch at a time.')
        return {'filename': 'hanni-' + format + '.jsonl', 'content': content, 'count': len(records),
                'message': 'Contains private task and tool content with credential redaction. Review before sharing. Reasoning and system prompts are excluded. No weights changed.'}


def _clean(value):
    if isinstance(value, str):
        if value.lstrip().startswith(('{', '[')):
            try: return json.dumps(_clean(json.loads(value)), ensure_ascii=False)
            except (ValueError, TypeError): pass
        return redact_text(value)
    if isinstance(value, list): return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if k.lower() not in {'reasoning', 'reasoning_content', 'analysis', 'api_key', 'token', 'refresh_token', 'client_secret', 'password', 'authorization'}}
    return value


def trajectory(store, key):
    task = store.get(key)
    checkpoint = store.checkpoint(key) or {}
    messages = []
    raw = checkpoint.get('messages') or []
    # Keep complete call/result groups together; omit interrupted orphan groups.
    index = 0
    while index < len(raw):
        item = raw[index]; index += 1
        role = item.get('role')
        if role not in {'user', 'assistant', 'tool'} or role == 'tool': continue
        message = {k: item[k] for k in ('role', 'content', 'tool_calls') if k in item}
        if role == 'assistant' and isinstance(message.get('content'), str):
            from .loop import strip_reasoning
            message['content'] = strip_reasoning(message['content'])
        calls = message.get('tool_calls')
        if calls:
            ids = [c.get('id') for c in calls]
            results = []
            while index < len(raw) and raw[index].get('role') == 'tool':
                results.append({k: raw[index][k] for k in ('role', 'content', 'tool_call_id') if k in raw[index]}); index += 1
            if None in ids or len(set(ids)) != len(ids) or {r.get('tool_call_id') for r in results} != set(ids) or len(results) != len(ids): continue
            messages += [message, *results]
        else: messages.append(message)
    result = task.get('result') or {}
    return _clean({'schema': 'hanni.trajectory.v1', 'id': key, 'state': task['state'], 'messages': messages,
                   'tools': [a['spec']['schema'] for a in task['actions']],
                   'receipts': [{'tool': a['spec']['name'], 'state': a['state'], 'receipt': a.get('receipt')} for a in task['actions']],
                   'stats': result.get('stats') or checkpoint.get('stats'), 'stop_reason': result.get('stop_reason'),
                   'reward': None, 'verified_success': False})


def atropos_group(records, labels, tokenizer):
    """Offline ScoredDataGroup bridge. Caller supplies reviewed rewards and a local tokenizer.

    No reward is inferred from an assistant claim or successful tool execution.
    Mask only the final assistant completion, leaving its actual tool context intact.
    Use a separate Atropos training environment for on-policy RL rollouts.
    """
    group = {'tokens': [], 'masks': [], 'scores': [], 'messages': []}
    for record in records:
        score = labels.get(record['id'])
        if type(score) not in (float, int) or not math.isfinite(score): raise ValueError('Each trajectory needs a finite explicit reviewed reward.')
        messages = record['messages']
        if not messages or messages[-1]['role'] != 'assistant' or messages[-1].get('tool_calls'): raise ValueError('A final assistant answer is required.')
        options = {'tokenize': True, 'tools': record.get('tools') or None}
        prefix = tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, **options)
        tokens = tokenizer.apply_chat_template(messages, add_generation_prompt=False, **options)
        if not isinstance(tokens, list) or not isinstance(prefix, list) or tokens[:len(prefix)] != prefix or len(tokens) <= len(prefix):
            raise ValueError('Tokenizer chat template must preserve the exact prompt prefix.')
        group['tokens'].append(tokens)
        group['masks'].append([-100] * len(prefix) + tokens[len(prefix):])
        group['scores'].append(float(score))
        group['messages'].append(messages)
    return group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    batch = sub.add_parser('batch'); batch.add_argument('input', type=Path); batch.add_argument('--id', required=True)
    sub.add_parser('list')
    cancel = sub.add_parser('cancel'); cancel.add_argument('id')
    export = sub.add_parser('export'); export.add_argument('--batch', default=''); export.add_argument('--format', choices=['trajectory', 'sharegpt'], default='trajectory'); export.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); store = TrainingStore(args.root)
    if args.command == 'batch':
        if args.input.stat().st_size > 200000: parser.error('Batch input exceeds 200 KB.')
        prompts = [json.loads(line)['prompt'] for line in args.input.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        result = store.submit(args.id, prompts)
    elif args.command == 'list': result = store.batches()
    elif args.command == 'cancel': result = store.cancel(args.id)
    else:
        result = store.export(args.batch, args.format)
        with args.output.open('x', encoding='utf-8') as output: output.write(result.pop('content'))
    print(json.dumps(result))


if __name__ == '__main__': main()
