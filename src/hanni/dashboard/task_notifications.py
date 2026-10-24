"""Read durable native task transitions into the existing notification store.

No bridge requests, task writes, prompts, outputs, or automatic approvals.
"""
from datetime import datetime, timezone
from contextlib import closing
import logging
import sqlite3
import time


def collect(store, root):
    path = root / 'tasks.sqlite3'
    if not path.is_file():
        return []
    try:
        # Pin the first observation once. Old completed tasks are not replayed
        # at installation, but work completed while the app is closed survives.
        with store.connect() as db:
            db.execute("INSERT OR IGNORE INTO workspace_preferences VALUES ('native_notification_start', ?)", (str(time.time()),))
            started = float(db.execute("SELECT value FROM workspace_preferences WHERE key='native_notification_start'").fetchone()[0])
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.25)) as db:
            tasks = db.execute("SELECT id,key,json_extract(payload,'$.state'),json_extract(payload,'$.updated') "
                               "FROM tasks ORDER BY rowid DESC LIMIT 1000").fetchall()
            pending = db.execute("SELECT id,task,json_extract(payload,'$.expires') FROM actions "
                                 "WHERE json_extract(payload,'$.state')='pending' ORDER BY rowid DESC LIMIT 1000").fetchall()
        entries = []
        now = time.time()
        active = {task_id for task_id, _, state, _ in tasks if state == 'approval'}
        for action_id, task_id, expires in pending:
            if task_id in active and isinstance(expires, (int, float)) and expires > now:
                entries.append({'key': 'native:approval:' + action_id, 'category': 'approvals',
                    'priority': 'action_required', 'title': 'HANNI needs your approval',
                    'message': 'A task is waiting for an action decision. Open it to review the requested action.',
                    'target': {'screen': 'tasks', 'id': task_id}})
        for task_id, key, state, updated in tasks:
            if not isinstance(updated, (int, float)) or not started <= updated <= now + 60:
                continue
            scheduled = isinstance(key, str) and key.startswith('cron-')
            if state in {'completed', 'review_required'}:
                title = 'A scheduled task is ready' if scheduled else 'HANNI finished a task'
                priority, event = 'informational', 'finished'
                message = 'Open the task to review its result and execution receipts.'
            elif state in {'failed', 'interrupted', 'uncertain'}:
                title, priority, event = 'HANNI task needs attention', 'critical', 'attention'
                message = 'The task stopped or could not confirm an action. Review its status before retrying.'
            else:
                continue
            entries.append({'key': f'native:{task_id}:{event}', 'category': 'agents',
                'priority': priority, 'title': title, 'message': message,
                'created_at': datetime.fromtimestamp(updated, timezone.utc).isoformat(),
                'target': {'screen': 'tasks', 'id': task_id}})
        return entries
    except (OSError, sqlite3.Error, ValueError, OverflowError):
        logging.getLogger(__name__).debug('Native task notification records are temporarily unavailable.')
        return []
