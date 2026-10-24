#!/usr/bin/env python3
"""HANNI Homework Tracker — web UI + local MCP on one port.
SQLite store; REST API for the browser UI; MCP tools for the agent.
Proven working: systemd unit + hermes config set mcp_servers.homework.url."""
import json, os, sqlite3, time
from pathlib import Path
from fastmcp import FastMCP
from starlette.responses import JSONResponse, HTMLResponse

DB = Path(os.getenv("HOMEWORK_DB", str(Path(__file__).parent / "homework.db")))
mcp = FastMCP("hanni-homework")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS assignments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, course TEXT DEFAULT '', due TEXT DEFAULT '',
            status TEXT DEFAULT 'todo', priority INTEGER DEFAULT 2,
            notes TEXT DEFAULT '', created TEXT DEFAULT (datetime('now','localtime')))""")
init()

def row_json(r):
    return {k: r[k] for k in r.keys()}

def _list(status="", course="", overdue=False):
    with db() as c:
        q, a = "SELECT * FROM assignments WHERE 1=1", []
        if status: q += " AND status=?"; a.append(status)
        if course: q += " AND course LIKE ?"; a.append(f"%{course}%")
        q += " ORDER BY CASE WHEN due='' THEN 9 ELSE 0 END, due ASC, priority ASC"
        rows = [row_json(r) for r in c.execute(q, a)]
    today = time.strftime("%Y-%m-%d")
    for r in rows:
        r["overdue"] = bool(r["due"]) and r["due"] < today and r["status"] != "done"
    if overdue:
        rows = [r for r in rows if r["overdue"]]
    return rows

@mcp.tool(name="homework_list")
def homework_list(status: str = "", course: str = "", overdue_only: bool = False) -> str:
    """List assignments. Filters: status (todo/doing/done), course substring, overdue_only."""
    return json.dumps(_list(status, course, overdue_only), indent=1)

@mcp.tool(name="homework_add")
def homework_add(title: str, course: str = "", due: str = "", priority: int = 2, notes: str = "") -> str:
    """Add an assignment. due format YYYY-MM-DD. priority 1=high 2=med 3=low."""
    with db() as c:
        cur = c.execute("INSERT INTO assignments(title,course,due,priority,notes) VALUES(?,?,?,?,?)",
                        (title, course, due, priority, notes))
        return json.dumps(row_json(c.execute("SELECT * FROM assignments WHERE id=?", (cur.lastrowid,)).fetchone()))

@mcp.tool(name="homework_update")
def homework_update(id: int, title: str = "", course: str = "", due: str = "",
                    status: str = "", priority: int = 0, notes: str = "") -> str:
    """Update fields on an assignment (only non-empty fields change). status: todo/doing/done."""
    sets, a = [], []
    for k, v in [("title", title), ("course", course), ("due", due), ("status", status),
                 ("priority", priority or None), ("notes", notes)]:
        if v != "" and v is not None:
            sets.append(f"{k}=?"); a.append(v)
    if not sets: return json.dumps({"error": "nothing to update"})
    a.append(id)
    with db() as c:
        c.execute(f"UPDATE assignments SET {','.join(sets)} WHERE id=?", a)
        r = c.execute("SELECT * FROM assignments WHERE id=?", (id,)).fetchone()
        return json.dumps(row_json(r) if r else {"error": "not found"})

@mcp.tool(name="homework_complete")
def homework_complete(id: int) -> str:
    """Mark an assignment done."""
    with db() as c:
        c.execute("UPDATE assignments SET status='done' WHERE id=?", (id,))
        r = c.execute("SELECT * FROM assignments WHERE id=?", (id,)).fetchone()
        return json.dumps(row_json(r) if r else {"error": "not found"})

@mcp.tool(name="homework_delete")
def homework_delete(id: int) -> str:
    with db() as c:
        n = c.execute("DELETE FROM assignments WHERE id=?", (id,)).rowcount
        return json.dumps({"deleted": n})

@mcp.tool(name="homework_stats")
def homework_stats() -> str:
    """Counts by status, overdue count, and what's due in the next 7 days."""
    rows = _list()
    today = time.strftime("%Y-%m-%d")
    week = time.strftime("%Y-%m-%d", time.localtime(time.time() + 7 * 86400))
    return json.dumps({
        "total": len(rows),
        "todo": sum(1 for r in rows if r["status"] == "todo"),
        "doing": sum(1 for r in rows if r["status"] == "doing"),
        "done": sum(1 for r in rows if r["status"] == "done"),
        "overdue": sum(1 for r in rows if r["overdue"]),
        "due_this_week": [f'{r["title"]} ({r["course"]}) due {r["due"]}' for r in rows
                          if r["due"] and today <= r["due"] <= week and r["status"] != "done"]}, indent=1)

# ---- REST + UI for the browser ----
@mcp.custom_route("/api/assignments", methods=["GET"])
async def api_list(request):
    return JSONResponse(_list(request.query_params.get("status", ""),
                              request.query_params.get("course", "")))

@mcp.custom_route("/api/assignments", methods=["POST"])
async def api_add(request):
    b = await request.json()
    return JSONResponse(json.loads(homework_add(b.get("title", ""), b.get("course", ""),
                                                b.get("due", ""), int(b.get("priority", 2)),
                                                b.get("notes", ""))))

@mcp.custom_route("/api/assignments/{id}", methods=["PATCH"])
async def api_patch(request):
    b = await request.json()
    return JSONResponse(json.loads(homework_update(int(request.path_params["id"]),
        **{k: b.get(k, "") for k in ("title", "course", "due", "status", "notes")},
        priority=int(b.get("priority", 0) or 0))))

@mcp.custom_route("/api/assignments/{id}", methods=["DELETE"])
async def api_del(request):
    return JSONResponse(json.loads(homework_delete(int(request.path_params["id"]))))

UI = """<!doctype html><meta charset=utf-8><title>HANNI Homework</title>
<style>body{font-family:system-ui;background:#15161c;color:#e8e8ef;max-width:860px;margin:2em auto;padding:0 1em}
h1{font-size:1.3em}table{width:100%;border-collapse:collapse}td,th{padding:.5em;border-bottom:#2c2e3a 1px solid;text-align:left}
.done{text-decoration:line-through;opacity:.5}.overdue{color:#ff7b7b}.due{color:#8fd08f}
button{background:#2c2e3a;color:#e8e8ef;border:0;border-radius:6px;padding:.35em .7em;cursor:pointer}
input,select{background:#22232c;color:#e8e8ef;border:1px solid #3a3c4a;border-radius:6px;padding:.35em}
#add{display:flex;gap:.5em;flex-wrap:wrap;margin:1em 0}</style>
<h1>📚 Homework Tracker <small style="opacity:.6">HANNI ✦</small></h1>
<div id=add><input id=t placeholder="title"><input id=c placeholder="course"><input id=d type=date>
<select id=p><option value=1>high</option><option value=2 selected>med</option><option value=3>low</option></select>
<button onclick="add()">Add</button><span id=stats style="opacity:.7"></span></div>
<table><thead><tr><th>✓</th><th>Title</th><th>Course</th><th>Due</th><th>Pri</th><th></th></tr></thead><tbody id=tb></tbody></table>
<script>
const f=async(u,o)=>(await fetch(u,o)).json();
async function draw(){const rows=await f('/api/assignments');tb.innerHTML=rows.map(r=>`<tr class="${r.status=='done'?'done':''}">
<td><button onclick="tog(${r.id},'${r.status=='done'?'todo':'done'}')">${r.status=='done'?'✔':'○'}</button></td>
<td>${r.title}</td><td>${r.course}</td><td class="${r.overdue?'overdue':r.due?'due':''}">${r.due||'—'}${r.overdue?' ⚠':''}</td>
<td>${'!! ! '[r.priority-1]||''}</td><td><button onclick="del(${r.id})">✕</button></td></tr>`).join('');
const s=await f('/api/assignments');const od=s.filter(r=>r.overdue).length;
stats.textContent=`${s.filter(r=>r.status!='done').length} open · ${od} overdue`;}
async function add(){if(!t.value)return;await f('/api/assignments',{method:'POST',headers:{'content-type':'application/json'},
body:JSON.stringify({title:t.value,course:c.value,due:d.value,priority:p.value})});t.value=c.value=d.value='';draw();}
async function tog(id,st){await f('/api/assignments/'+id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({status:st})});draw();}
async function del(id){await f('/api/assignments/'+id,{method:'DELETE'});draw();}
draw();setInterval(draw,15000);</script>"""

@mcp.custom_route("/", methods=["GET"])
async def ui(request):
    return HTMLResponse(UI)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("PORT", "8096")), path="/mcp")
