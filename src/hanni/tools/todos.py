"""Owner-requested assignment/tasks, separate from the ephemeral execution TODO."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from hanni.memory.privacy import validate_memory_text
from hanni.tools.base import ToolDefinition, ToolResult
from hanni.tools.whenparse import parse_when


class TodoStore:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "todos.sqlite3"

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('''CREATE TABLE IF NOT EXISTS todos (
                id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL, course TEXT NOT NULL, due TEXT NOT NULL,
                all_day INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)''')
            yield db

    def add(self, args):
        title = validate_memory_text(str(args.get('title') or ''), max_chars=300)
        if not title.strip():
            raise ValueError('title is required')
        course = str(args.get('course') or '').strip()
        if course:
            course = validate_memory_text(course, max_chars=120)
        phrase = str(args.get('due') or '').strip()
        if not phrase:
            raise ValueError('due is required; ask for the assignment due date')
        parsed = parse_when(phrase, default_minutes=0)
        due = parsed.start.isoformat()
        key = hashlib.sha256(json.dumps([title.casefold(), course.casefold(), due, parsed.all_day]).encode()).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO todos VALUES (?,?,?,?,?,?,?,?)',
                       (uuid4().hex, key, title, course, due, int(parsed.all_day), 'open',
                        datetime.now().astimezone().isoformat()))
            return dict(db.execute('SELECT * FROM todos WHERE request_key=?', (key,)).fetchone())

    def get(self, item_id):
        if not isinstance(item_id, str) or not item_id:
            raise ValueError('id is required; use todo.list to find it')
        with self.connect() as db:
            row = db.execute('SELECT * FROM todos WHERE id=?', (item_id,)).fetchone()
            if row is None:
                raise ValueError('No task with that exact ID')
            return dict(row)

    def complete(self, item_id):
        self.get(item_id)
        with self.connect() as db:
            db.execute("UPDATE todos SET status='completed' WHERE id=?", (item_id,))
        return self.get(item_id)

    def list(self, args, *, due_only=False):
        status = args.get('status') or 'open'
        if status not in {'open', 'completed', 'all'}:
            raise ValueError('status must be open, completed or all')
        limit = args.get('limit', 30)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be 1..100')
        where, params = [], []
        if status != 'all':
            where.append('status=?'); params.append(status)
        if args.get('course'):
            where.append('course=?'); params.append(args['course'])
        if due_only:
            days = args.get('days', 7)
            if type(days) is not int or not 1 <= days <= 366:
                raise ValueError('days must be 1..366')
            # Additive desktop tasks can be undated; they are not overdue.
            where.append("due<>'' AND due<?")
            params.append((datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                           + timedelta(days=days)).isoformat())
        sql = 'SELECT * FROM todos' + (' WHERE ' + ' AND '.join(where) if where else '')
        with self.connect() as db:
            rows = db.execute(sql + ' ORDER BY due, id LIMIT ?', (*params, limit)).fetchall()
        return [dict(r) for r in rows]


def definitions(data_dir):
    store = TodoStore(data_dir)
    def run(name):
        def handler(args, context, request):
            if name == 'todo.add':
                row = store.add(args)
            elif name == 'todo.complete':
                row = store.complete(args.get('id'))
            elif name == 'todo.get':
                row = store.get(args.get('id'))
            else:
                rows = store.list(args, due_only=name == 'todo.due')
                return ToolResult(name, True, f'{len(rows)} task(s) returned.', {'tasks': rows, 'count': len(rows)})
            return ToolResult(name, True, 'Local task record available.', {'task': row, 'id': row['id']})
        return handler
    specs = [
        ('todo.add', 'Save a named assignment or task with its due date locally; exact duplicates return the existing ID. No Google sync.', 2,
         {'title': str, 'due': str, 'course': str}, ('homework', 'assignment', 'deadline', 'task', 'add')),
        ('todo.list', 'List saved tasks, optionally by course and status; defaults to open.', 0,
         {'course': str, 'status': str, 'limit': int}, ('tasks', 'homework', 'list', 'assignments')),
        ('todo.get', 'Read back one local task by exact ID to verify its saved fields.', 0,
         {'id': str}, ('task', 'readback', 'verify')),
        ('todo.complete', 'Mark one task completed by its exact ID; read back with todo.get.', 2,
         {'id': str}, ('task', 'assignment', 'finish', 'complete')),
        ('todo.due', 'List open tasks due in the next N calendar days, including overdue work.', 0,
         {'days': int, 'course': str, 'limit': int}, ('due', 'deadlines', 'overdue', 'homework')),
    ]
    return tuple(ToolDefinition(name, desc, level, level, schema,
                                {'task': 'object', 'id': 'string'} if name in {'todo.add', 'todo.get', 'todo.complete'}
                                else {'tasks': 'array', 'count': 'integer'},
                                run(name), side_effect='read' if level == 0 else 'reversible_write', tags=tags)
                 for name, desc, level, schema, tags in specs)
