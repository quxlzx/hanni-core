"""Dashboard panel: native bridge proxy, agent cron, and skills inventory.

The Hanni OS UI talks to these routes; they forward to the native bridge
(tasks, approvals) or read local stores (cron.sqlite3, skills dir).
"""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path


def bridge_url() -> str:
    return os.environ.get("HANNI_BRIDGE_URL", "http://127.0.0.1:8097")


def bridge_token() -> str:
    path = os.environ.get("HANNI_BRIDGE_TOKEN_FILE",
                          str(Path.home() / "hanni-cron" / "state" / "bridge.token"))
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def bridge_proxy(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        bridge_url() + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {bridge_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return {"error": f"bridge HTTP {exc.code}",
                "detail": (exc.read() or b"")[:300].decode(errors="replace")}
    except Exception as exc:
        return {"error": "bridge unreachable", "detail": str(exc)[:200]}


def cron_root() -> Path:
    default = (Path(os.environ["HANNI_BRIDGE_TOKEN_FILE"]).parent
               if os.environ.get("HANNI_BRIDGE_TOKEN_FILE") else Path.home() / "hanni-cron" / "state")
    return Path(os.environ.get("HANNI_CRON_ROOT", str(default)))


def bridge_decision(action_id: str, body: dict) -> dict:
    if set(body) != {"state"} or body['state'] not in {'dispatching', 'rejected'}:
        raise ValueError('Approve or deny the action; execution receipts come from the worker.')
    action = bridge_proxy('GET', '/actions/' + action_id)
    if action.get('error'):
        return action
    if body['state'] == 'dispatching' and action['spec']['target'] not in {'local', 'mcp'}:
        raise ValueError('This capability requires its registered HANNI execution controller.')
    return bridge_proxy('POST', '/actions/' + action_id, body)


def cron_jobs() -> dict:
    db = cron_root() / "cron.sqlite3"
    if not db.is_file():
        return {"jobs": [], "note": "no cron store on this machine"}
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    jobs = [dict(row) for row in con.execute("SELECT * FROM jobs ORDER BY created_at")]
    con.close()
    for job in jobs:
        job["auto_approve"] = json.loads(job["auto_approve"])
    return {"jobs": jobs}


def cron_set(job_id: str, enabled: bool) -> dict:
    db = cron_root() / "cron.sqlite3"
    if not db.is_file():
        return {"error": "no cron store"}
    if not job_id or not job_id.replace("-", "").isalnum():
        return {"error": "invalid job id"}
    con = sqlite3.connect(db)
    cur = con.execute("UPDATE jobs SET enabled=? WHERE id=?", (1 if enabled else 0, job_id))
    con.commit()
    con.close()
    return {"updated": cur.rowcount}


def skills_list() -> dict:
    from hanni.native.skill_store import SkillStore
    return {"skills": [{"name": s["name"], "description": s["description"],
                        "triggers": s["triggers"][:8]} for s in SkillStore(cron_root()).catalog()]}
