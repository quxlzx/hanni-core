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
import json
import sqlite3
import time
import uuid
from pathlib import Path

DEFAULT_INTERVAL = 3600


class CronStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        with self._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, prompt TEXT NOT NULL, interval_seconds INTEGER NOT NULL,
                auto_approve TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 1,
                next_run REAL NOT NULL, last_task_id TEXT, created_at REAL NOT NULL)""")

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

    def add(self, prompt: str, interval: int = DEFAULT_INTERVAL, auto_approve=()) -> str:
        if not 1 <= len(prompt) <= 8000 or interval < 60:
            raise ValueError("Prompt required; interval must be >= 60 seconds.")
        job_id = uuid.uuid4().hex[:12]
        with self._tx() as db:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",
                       (job_id, prompt, int(interval), json.dumps(list(auto_approve)),
                        1, time.time() + interval, None, time.time()))
        return job_id

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

    def due(self, now: float) -> list[dict]:
        return [j for j in self.list() if j["enabled"] and j["next_run"] <= now]

    def advance(self, job_id: str, slot: float, task_id: str) -> None:
        with self._tx() as db:
            row = db.execute("SELECT interval_seconds FROM jobs WHERE id=?", (job_id,)).fetchone()
            db.execute("UPDATE jobs SET next_run=?, last_task_id=? WHERE id=?",
                       (max(time.time(), slot) + row[0], task_id, job_id))


def submit_due(store: CronStore, tasks, now: float) -> list[str]:
    """Submit every due job as a task; returns task ids. Idempotent per slot."""
    from ..hermes.state import TaskStore
    submitted = []
    for job in store.due(now):
        payload = {"prompt": job["prompt"], "windows_tools": [], "origin": "hanni",
                   "context": {"local_runtime": {"auto_approve": job["auto_approve"]}}}
        task = tasks.submit(f"cron-{job['id']}-{int(job['next_run'])}", payload)
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
