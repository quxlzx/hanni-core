"""Loopback-only authenticated asynchronous task bridge, separate from messaging."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from .catalog import Catalog, SEED, reconcile_hermes, connection_hash
from .state import TaskStore, Conflict, TERMINAL


class Bridge:
    def __init__(self, root, hermes_config, token_file, *, python=sys.executable, shared_root=None, worker_command=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = TaskStore(self.root/'tasks.sqlite3', recover=True)
        self.catalog = Catalog(self.root/'catalog.sqlite3')
        self.config = Path(hermes_config)
        self.shared_root = shared_root
        self.token = Path(token_file).read_text().strip()
        if len(self.token) < 32:
            raise ValueError('Bridge authentication credential is too short.')
        self.python = python
        self.worker_command = worker_command or [python, '-m', 'hanni.hermes.worker']
        self.stop = threading.Event()
        self.child = None
        self.lock = threading.RLock()
        self.thread = threading.Thread(target=self.run_queue, name='hermes-task-worker', daemon=True)

    def run_queue(self):
        while not self.stop.wait(.25):
            rows = self.store.queued()
            for task in rows:
                if task['state'] != 'queued':
                    continue
                snapshot = self.root/'active-catalog.json'
                snapshot.write_text(json.dumps(self.catalog.snapshot()))
                with self.lock:
                    if self.stop.is_set() or self.store.get(task['id'])['state'] != 'queued':
                        break
                    werr = open(self.root/'worker-stderr.log', 'ab')
                    if os.name == 'nt':
                        self.child = subprocess.Popen([*self.worker_command,
                            str(self.root/'tasks.sqlite3'), task['id'], str(snapshot)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=werr,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                    else:
                        self.child = subprocess.Popen([*self.worker_command,
                            str(self.root/'tasks.sqlite3'), task['id'], str(snapshot)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=werr,
                            start_new_session=True)
                deadline = time.monotonic()+900
                while self.child.poll() is None:
                    if self.stop.wait(.2) or self.store.get(task['id'])['state'] in TERMINAL or time.monotonic() > deadline:
                        self.kill_child()
                        if self.store.get(task['id'])['state'] not in TERMINAL:
                            self.store.event(task['id'], 'Worker time limit reached.', state='uncertain', error='Review receipts; no effects replayed.')
                        break
                self.child.wait(timeout=5)
                if self.store.get(task['id'])['state'] not in TERMINAL:
                    self.store.event(task['id'], 'Worker exited without a final receipt.', state='interrupted')
                with self.lock:
                    self.child = None
                break

    def kill_child(self):
        with self.lock:
            if self.child is not None and self.child.poll() is None:
                if os.name == 'nt':
                    # kill the whole process tree; CREATE_NEW_PROCESS_GROUP roots it at the child
                    subprocess.run(['taskkill', '/T', '/F', '/PID', str(self.child.pid)],
                                   capture_output=True, timeout=5)
                else:
                    os.killpg(self.child.pid, signal.SIGTERM)
                try:
                    self.child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(self.child.pid, signal.SIGKILL)
                    self.child.wait(timeout=3)

    def dispatch(self, method, path, body):
        if method == 'POST' and path == '/tasks/cancel_many':
            if set(body) != {'ids'} or not isinstance(body['ids'], list) or len(body['ids']) > 256:
                raise ValueError('Invalid cancellation batch.')
            for task_id in body['ids']:
                self.store.cancel(task_id)
            return {'cancel_requested': len(body['ids']), 'effects_undone': False}
        if method == 'POST' and path == '/attachments':
            if self.shared_root is None:
                raise ValueError('Shared-file mapping has not been verified.')
            from .attachments import receive
            return receive(body, self.shared_root)
        if method == 'GET' and path == '/health':
            return {'protocol': 1, 'ready': not self.stop.is_set(), 'gateway_started': False}
        if method == 'GET' and path == '/tools':
            from ..native.local_tools import local_tool_specs
            return {'tools': [{'name': t['name'],
                               'description': t['schema']['function']['description']}
                              for t in local_tool_specs()]}
        if method == 'GET' and path == '/tasks':
            return {'tasks': self.store.list()}
        if method == 'GET' and path.startswith('/submissions/'):
            return self.store.submission(path.split('/')[2])
        if method == 'POST' and path == '/tasks':
            task = body['task']
            if os.environ.get('HANNI_AUTO_APPROVE') == '1':
                # Hermes-like: tools run without an approval freeze. The
                # denylist, workspace jail and SSRF guard still apply —
                # only the human-approval ceremony is skipped.
                ctx = task.setdefault('context', {})
                ctx.setdefault('local_runtime', {})['auto_approve'] = ['*']
            return self.store.submit(body['key'], task)
        if method == 'GET' and path.startswith('/tasks/'):
            return self.store.get(path.split('/')[2])
        if method == 'POST' and path.endswith('/cancel') and path.startswith('/tasks/'):
            return self.store.cancel(path.split('/')[2])
        if method == 'POST' and path.startswith('/actions/'):
            if body['state'] == 'dispatching':
                action = self.store.action(path.split('/')[2])
                if action['spec']['target'] == 'karina':
                    remote = action['spec']['remote']
                    snapshot = self.catalog.snapshot()
                    permitted = any(item['name'] == remote['server'] and item['enabled'] and not item['deleted']
                                    and item['endpoints']['hermes'] == remote['url']
                                    and snapshot['connection_approvals'].get(item['name']) == connection_hash(item) for item in snapshot['entries'])
                    if not permitted:
                        raise Conflict('Remote server disabled, removed, or changed; execution blocked.')
            return self.store.settle(path.split('/')[2], body['state'], body.get('receipt'))
        if path == '/catalog':
            if method == 'GET':
                return self.catalog.snapshot()
            if method == 'POST':
                catalog = self.catalog.change(body['revision'], body['entries'], body['id'])
                try:
                    status = reconcile_hermes(catalog, self.config, self.root/'ownership.json', adopt_seed=body.get('adopt_seed') is True)
                except (ValueError, OSError) as exc:
                    self.catalog.record_sync('hermes', {'status':'pending_conflict','error':str(exc)[:300]})
                    return {**catalog, 'sync_error': str(exc)[:300], 'activation': 'pending'}
                self.catalog.record_sync('hermes', {'status':'registered','activation':'pending','error':None})
                return {**catalog, **status}
        if method == 'POST' and path == '/catalog/connection':
            if set(body)!={'name','expected_hash','approve'} or type(body['approve']) is not bool:
                raise ValueError('Connection approval requires exact settings and an owner decision.')
            return self.catalog.approve_connection(body['name'],body['expected_hash'],approve=body['approve'])
        if method == 'POST' and path == '/catalog/retry':
            try:
                status = reconcile_hermes(self.catalog.snapshot(), self.config, self.root/'ownership.json')
            except (ValueError,OSError):
                self.catalog.record_sync('hermes',{'status':'pending_conflict','error':'Configuration conflict remains; existing settings preserved.'})
                raise
            self.catalog.record_sync('hermes',{'status':'registered','activation':'pending','error':None})
            return {**self.catalog.snapshot(), **status}
        raise KeyError('Unknown bridge operation.')

    def close(self):
        self.stop.set()
        self.kill_child()
        if self.thread.is_alive():
            self.thread.join(timeout=8)
        self.store.close()


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>HANNI — stick</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{background:#0d0f14;color:#e8e6f0;font-family:system-ui,sans-serif;margin:0;
      display:flex;flex-direction:column;height:100vh}
 header{padding:14px 20px;border-bottom:1px solid #23263a;font-weight:600}
 header span{color:#b794f6}
 #log{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
 .msg{max-width:72%;padding:10px 14px;border-radius:14px;white-space:pre-wrap;line-height:1.45}
 .me{align-self:flex-end;background:#3b3f5c}
 .hanni{align-self:flex-start;background:#1a1d2b;border:1px solid #2a2e45}
 .meta{font-size:12px;color:#8a8fa8;margin-top:6px}
 form{display:flex;gap:10px;padding:16px 20px;border-top:1px solid #23263a}
 input{flex:1;background:#1a1d2b;border:1px solid #2a2e45;color:#e8e6f0;
       padding:12px 14px;border-radius:10px;font-size:15px}
 button{background:#7c5cff;border:0;color:#fff;padding:0 22px;border-radius:10px;
        font-size:15px;cursor:pointer}
 button:disabled{opacity:.5}
 code{background:#262a40;padding:1px 5px;border-radius:5px;font-size:13px}
 a{color:#9db7ff}
</style></head><body>
<header>HANNI <span>· stick brain</span></header>
<div id="log"><div class="msg hanni">Plug-in HANNI is awake. Memories, skills and local
tools are live — ask me something.</div></div>
<form id="f"><input id="t" placeholder="Ask HANNI…" autocomplete="off">
<button id="b">Send</button></form>
<script>
const TOKEN='__TOKEN__', BASE=location.origin, hist=[];
const log=document.getElementById('log'), t=document.getElementById('t'),
      b=document.getElementById('b');
const api=(m,p,body)=>fetch(BASE+p,{method:m,headers:{Authorization:'Bearer '+TOKEN,
      'Content-Type':'application/json'},body:body?JSON.stringify(body):null})
      .then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});
function md(s){const esc=s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
 return esc.replace(/`([^`\n]+)`/g,'<code>$1</code>')
   .replace(/\*\*([^*\n]+)\*\*/g,'<b>$1</b>')
   .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g,'$1<i>$2</i>')
   .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')
   .replace(/\n/g,'<br>');}
function bubble(cls,text,meta){const d=document.createElement('div');d.className='msg '+cls;
      d.innerHTML=md(text);if(meta){const m=document.createElement('div');m.className='meta';
      m.textContent=meta;d.appendChild(m)}log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
async function send(ev){ev.preventDefault();const prompt=t.value.trim();if(!prompt)return;
 t.value='';bubble('me',prompt);hist.push({role:'user',text:prompt});
 const wait=bubble('hanni','queued…');
 try{
  const task=await api('POST','/tasks',{key:'ui-'+Date.now()+'-'+Math.random().toString(36).slice(2,6),task:{prompt,
    windows_tools:[],origin:'hanni',context:{local_runtime:{auto_approve:['*']},conversation:hist.slice(0,-1).slice(-10)}}});
  const deadline=Date.now()+600000;let st;
  while(Date.now()<deadline){st=await api('GET','/tasks/'+task.id);
    if(['review_required','failed','interrupted','uncertain'].includes(st.state))break;
    wait.textContent=(st.state==='running'?'working…':'queued…');
    await new Promise(r=>setTimeout(r,2000))}
  const r=st.result||{};
  const claim=(r.model_claims||'(no final claim)');
  wait.textContent=claim;hist.push({role:'assistant',text:claim});
  const rc=(r.receipts||[]).length;
  const m=document.createElement('div');m.className='meta';
  m.textContent=st.state+(rc?' · '+rc+' tool receipt'+(rc>1?'s':''):'');
  wait.appendChild(m);
 }catch(e){wait.textContent='bridge error: '+e.message}
 t.focus()}
document.getElementById('f').addEventListener('submit',send);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log credentials, prompts, arguments or result bodies.

    def handle_request(self, method):
        bridge = self.server.bridge
        if method == 'GET' and self.path in ('/', '/index.html'):
            # The stick's front door: a chat page with the token embedded.
            # The bridge binds loopback-only, so the page is reachable only
            # from the host that already holds the token file.
            page = INDEX_HTML.replace('__TOKEN__', bridge.token).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(page)
            return
        if os.environ.get('HANNI_BRIDGE_OPEN') == '1':
            # Open mode: loopback-only bridge with no token ceremony.
            pass
        else:
            expected = 'Bearer '+bridge.token
            supplied = self.headers.get('Authorization', '')
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                self.send_error(401)
                return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = 6*1024*1024 if self.path == '/attachments' else 1048576
            if not 0 <= length <= limit or self.headers.get('Transfer-Encoding'):
                raise ValueError('Body exceeds protocol limit.')
            self.connection.settimeout(5)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete body.')
            body = json.loads(raw) if raw else {}
            if not isinstance(body, dict):
                raise ValueError('An object is required.')
            result = bridge.dispatch(method, self.path, body)
            status = 200
        except Conflict:
            status, result = 409, {'error': 'CONFLICT', 'retryable': False}
        except KeyError:
            status, result = 404, {'error': 'NOT_FOUND', 'retryable': False}
        except (ValueError, TypeError):
            status, result = 400, {'error': 'INVALID_REQUEST', 'retryable': False}
        except Exception:
            status, result = 503, {'error': 'BRIDGE_UNAVAILABLE', 'retryable': False}
        wire = json.dumps(result, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(wire)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(wire)

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--hermes-config', type=Path, required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8092)
    parser.add_argument('--shared-root', type=Path)
    parser.add_argument('--worker-launcher', type=Path)
    parser.add_argument('--brain', choices=('hermes', 'native'), default='hermes',
                        help="loop engine: 'hermes' delegates to an installed Hermes AIAgent; "
                             "'native' runs HANNI's own loop against config/models.yaml")
    args = parser.parse_args()
    if args.worker_launcher:
        if args.brain == 'native':
            worker = [str(args.worker_launcher), '--run-module', 'hanni.native.worker']
        else:
            worker = [str(args.worker_launcher), '--run-module', 'hanni_hermes_adapter', 'worker']
    else:
        worker = None if args.brain == 'hermes' else [sys.executable, '-m', 'hanni.native.worker']
    bridge = Bridge(args.root, args.hermes_config, args.token_file, shared_root=args.shared_root, worker_command=worker)
    # POSIX: allow rebinding after restart. Windows: SO_REUSEADDR would let a
    # second bridge double-bind the same port (split-brain 401s) — refuse it.
    ThreadingHTTPServer.allow_reuse_address = (os.name != 'nt')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.bridge = bridge
    bridge.thread.start()
    def stopping(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stopping)
    signal.signal(signal.SIGINT, stopping)
    try:
        server.serve_forever(poll_interval=.2)
    finally:
        bridge.close()
        server.server_close()


if __name__ == '__main__':
    main()
