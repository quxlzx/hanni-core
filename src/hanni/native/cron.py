"""Agent cron: durable scheduled agent tasks.

A cron job is a prompt + interval + capability policy stored in
<root>/cron.sqlite3. The daemon submits each due job as a normal task
(idempotency key = job id + scheduled slot, so restarts never double-fire)
and the running bridge picks it up from the queue and spawns the native
worker. Local runtime tools are auto-approved per the job's policy — the
owner granted that policy when creating the job; receipts say so.

Usage:
  python -m hanni.native.cron --root DIR add --prompt "..." --interval 3600 \
      [--auto-approve local_terminal,local_read_file | --auto-approve-all]
  python -m hanni.native.cron --root DIR list
  python -m hanni.native.cron --root DIR disable --job ID
  python -m hanni.native.cron --root DIR daemon [--once]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_INTERVAL = 3600
READ_TOOLS = ('web_search', 'web_fetch', 'local_read_file', 'local_read_document',
              'local_list_dir', 'local_search_files', 'system_info')


def next_run(cadence, interval, at_time, zone, weekday, after, *, previous=None):
    if cadence == 'interval':
        return after + interval
    local = datetime.fromtimestamp(after, ZoneInfo(zone))
    hour, minute = map(int, at_time.split(':'))
    previous_day = datetime.fromtimestamp(previous, local.tzinfo).date() if previous is not None else None
    for offset in range(9):
        day = local.date() + timedelta(days=offset)
        if day == previous_day or cadence == 'weekly' and day.weekday() != weekday:
            continue
        candidate = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
        # If a wall time is skipped by DST, use the first valid minute after it.
        # Pick the first occurrence of an ambiguous time; never fire twice that day.
        for shift in range(181):
            wall = candidate + timedelta(minutes=shift)
            value = wall.replace(tzinfo=local.tzinfo, fold=0).timestamp()
            if datetime.fromtimestamp(value, local.tzinfo).replace(tzinfo=None) == wall:
                if value > after:
                    return value
                break
    raise ValueError('Could not resolve the next scheduled time.')


class CronStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, prompt TEXT NOT NULL, interval_seconds INTEGER NOT NULL,
                auto_approve TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 1,
                next_run REAL NOT NULL, last_task_id TEXT, created_at REAL NOT NULL)""")
            columns = {row[1] for row in db.execute('PRAGMA table_info(jobs)')}
            for name, definition in {'title': "TEXT NOT NULL DEFAULT 'Repeating task'",
                    'cadence': "TEXT NOT NULL DEFAULT 'interval'", 'at_time': "TEXT NOT NULL DEFAULT '09:00'",
                    'timezone': "TEXT NOT NULL DEFAULT 'UTC'", 'weekday': 'INTEGER NOT NULL DEFAULT 0',
                    'conversation': "TEXT NOT NULL DEFAULT 'default'"}.items():
                if name not in columns:
                    db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {definition}')
            db.execute('CREATE TABLE IF NOT EXISTS runs(task_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, '
                       'scheduled_for REAL NOT NULL, conversation TEXT NOT NULL, title TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE INDEX IF NOT EXISTS runs_delivery ON runs(delivered,scheduled_for)')
            db.execute('CREATE TABLE IF NOT EXISTS deleted_jobs(id TEXT PRIMARY KEY)')

    def _tx(self):
        class _Tx:
            def __enter__(inner):
                inner.db = sqlite3.connect(self.path, timeout=10)
                inner.db.execute("BEGIN IMMEDIATE")
                return inner.db

            def __exit__(inner, *exc):
                if exc[0] is None:
                    inner.db.commit()
                else:
                    inner.db.rollback()
                inner.db.close()
        return _Tx()

    def add(self, prompt: str, interval: int = DEFAULT_INTERVAL, auto_approve=(), *, title='Repeating task',
            cadence='interval', at_time='09:00', timezone='UTC', weekday=0, conversation='default', job_id=None) -> str:
        import re
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000 or type(interval) is not int or not 60 <= interval <= 31536000:
            raise ValueError('Prompt required; interval must be between 60 seconds and one year.')
        if (not isinstance(title, str) or not 1 <= len(title.strip()) <= 120 or not isinstance(cadence, str) or cadence not in {'interval', 'daily', 'weekly'}
                or not isinstance(at_time, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', at_time)
                or type(weekday) is not int or not 0 <= weekday <= 6):
            raise ValueError('Use a title, a supported repeat schedule, HH:MM time, and weekday 0 (Monday) to 6 (Sunday).')
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValueError('Choose an IANA timezone such as America/Chicago.') from None
        if (not isinstance(conversation, str) or not 1 <= len(conversation) <= 64
                or not isinstance(auto_approve, (list, tuple)) or len(auto_approve) > 32
                or any(not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_*.-]{1,100}', name) for name in auto_approve)):
            raise ValueError('Invalid conversation or tool policy.')
        job_id = job_id or uuid.uuid4().hex[:12]
        if not isinstance(job_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', job_id):
            raise ValueError('Invalid schedule ID.')
        values = (prompt.strip(), interval, json.dumps(list(auto_approve)), title.strip(), cadence, at_time, timezone, weekday, conversation)
        with self._tx() as db:
            if db.execute('SELECT 1 FROM deleted_jobs WHERE id=?', (job_id,)).fetchone():
                raise ValueError('This repeating task was deleted. Use a new request ID to create another schedule.')
            old = db.execute('SELECT prompt,interval_seconds,auto_approve,title,cadence,at_time,timezone,weekday,conversation FROM jobs WHERE id=?', (job_id,)).fetchone()
            if old:
                if old != values:
                    raise ValueError('Schedule request ID was already used for different settings.')
                return job_id
            if db.execute('SELECT count(*) FROM jobs').fetchone()[0] >= 100:
                raise ValueError('Up to 100 repeating tasks are supported. Delete an unused task first.')
            now = time.time()
            due = next_run(cadence, interval, at_time, timezone, weekday, now)
            db.execute('INSERT INTO jobs(id,prompt,interval_seconds,auto_approve,enabled,next_run,last_task_id,created_at,title,cadence,at_time,timezone,weekday,conversation) '
                       'VALUES(?,?,?,?,1,?,NULL,?,?,?,?,?,?,?)', (job_id, *values[:3], due, now, *values[3:]))
        return job_id

    def get(self, job_id):
        job = next((job for job in self.list() if job['id'] == job_id), None)
        if not job:
            raise ValueError('Repeating task not found.')
        return job

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        out = []
        for row in rows:
            job = dict(row)
            job["auto_approve"] = json.loads(job["auto_approve"])
            out.append(job)
        return out

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        with self._tx() as db:
            cur = db.execute("UPDATE jobs SET enabled=? WHERE id=?", (1 if enabled else 0, job_id))
        return cur.rowcount > 0

    def delete(self, job_id):
        with self._tx() as db:
            removed = db.execute('DELETE FROM jobs WHERE id=?', (job_id,)).rowcount > 0
            if removed:
                db.execute('INSERT OR IGNORE INTO deleted_jobs VALUES (?)', (job_id,))
            return removed

    def pending_runs(self):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM runs WHERE delivered=0 ORDER BY scheduled_for LIMIT 100')]

    def delivered(self, task_id):
        with self._tx() as db:
            db.execute('UPDATE runs SET delivered=1 WHERE task_id=?', (task_id,))

    def due(self, now: float) -> list[dict]:
        return [j for j in self.list() if j["enabled"] and j["next_run"] <= now]

    def advance(self, job_id: str, slot: float, task_id: str) -> None:
        with self._tx() as db:
            row = db.execute('SELECT interval_seconds,cadence,at_time,timezone,weekday FROM jobs WHERE id=? AND next_run=?', (job_id, slot)).fetchone()
            if row is None:
                return
            due = next_run(row[1], row[0], row[2], row[3], row[4], max(time.time(), slot), previous=slot)
            db.execute("UPDATE jobs SET next_run=?, last_task_id=? WHERE id=?",
                       (due, task_id, job_id))


def submit_due(store: CronStore, tasks, now: float) -> list[str]:
    """Submit every due job as a task; returns task ids. Idempotent per slot."""
    from ..hermes.state import TaskStore
    submitted = []
    for job in store.due(now):
        if job['last_task_id']:
            from hanni.hermes.state import TERMINAL
            try:
                if tasks.get(job['last_task_id'])['state'] not in TERMINAL:
                    continue  # One in-flight run per schedule; no unbounded backlog.
            except KeyError:
                pass
        payload = {"prompt": job["prompt"], "windows_tools": [], "origin": "hanni",
                   "context": {"local_runtime": {"auto_approve": job["auto_approve"]},
                               'scheduled_job_id': job['id'], 'conversation_id': job['conversation'],
                               'scheduled_for': job['next_run'], 'timezone': job['timezone']}}
        task = tasks.submit(f"cron-{job['id']}-{int(job['next_run'])}", payload)
        with store._tx() as db:
            db.execute('INSERT OR IGNORE INTO runs(task_id,job_id,scheduled_for,conversation,title) VALUES(?,?,?,?,?)',
                       (task['id'], job['id'], job['next_run'], job['conversation'], job['title']))
        store.advance(job["id"], job["next_run"], task["id"])
        submitted.append(task["id"])
    return submitted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("--prompt", required=True)
    add.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    add.add_argument("--auto-approve", default="", help="comma-separated local tool names")
    add.add_argument("--auto-approve-all", action="store_true")
    sub.add_parser("list")
    dis = sub.add_parser("disable")
    dis.add_argument("--job", required=True)
    daemon = sub.add_parser("daemon")
    daemon.add_argument("--once", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    store = CronStore(root / "cron.sqlite3")
    if args.cmd == "add":
        approvals = ["*"] if args.auto_approve_all else [a.strip() for a in args.auto_approve.split(",") if a.strip()]
        print("job:", store.add(args.prompt, args.interval, approvals))
    elif args.cmd == "list":
        print(json.dumps(store.list(), indent=1))
    elif args.cmd == "disable":
        print("ok" if store.set_enabled(args.job, False) else "no such job")
    elif args.cmd == "daemon":
        from ..hermes.state import TaskStore
        tasks = TaskStore(root / "tasks.sqlite3")
        while True:
            for task_id in submit_due(store, tasks, time.time()):
                print(f"{time.strftime('%H:%M:%S')} fired job -> task {task_id}")
            if args.once:
                return
            time.sleep(15)


if __name__ == "__main__":
    main()
