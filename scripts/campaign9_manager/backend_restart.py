"""Restart only two recorded disposable backend processes over synthetic state."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch
import uuid
import psutil
from .preflight import ROOT, runtime

def publish(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def child(root, restore=False):
    from scripts.campaign8_ui.backend import original_backend
    from hanni.dashboard.chat import ChatHub
    if root.name not in {'server-one', 'server-two'} or not root.parent.is_relative_to(ROOT / 'data/campaign9-manager/development'):
        raise ValueError('Only named C9-owned disposable backends are allowed.')
    if (root.parent / 'OWNED.txt').read_text(encoding='utf-8') != 'C9 disposable backend restart fixture':
        raise ValueError('Missing owned-fixture marker.')
    init = ChatHub.__init__

    def restored_init(instance, path=None):
        expected = root / 'campaign-chat.sqlite3'
        if Path(path).resolve() != expected:
            raise ValueError('Restore target must be this fresh owned chat database.')
        shutil.copyfile(root.parent / 'server-one/campaign-chat.sqlite3', expected)
        init(instance, path)
    with ExitStack() as stack:
        if restore:
            stack.enter_context(patch.object(ChatHub, '__init__', restored_init))
        with original_backend(root) as backend:
            backend.chat.activate()
            publish(root / 'READY.json', backend.ready())
            backend.stop.wait(90)
            backend.close()
            publish(root / 'CLOSED.json', {'owned_http_closed': not backend.thread.is_alive(), 'chat_closed': backend.chat.closed, 'generation_requests': 0})

def request(ready, path, *, token=None, body=None):
    from urllib.parse import urlsplit
    target = urlsplit(ready['url'])
    if target.hostname != '127.0.0.1' or target.port in {8080, 8765}:
        raise ValueError('Recorded disposable endpoint required.')
    headers = {'Origin': ready['url']}
    if token is not None:
        headers['X-Hanni-Token'] = token
    wire = None if body is None else json.dumps(body)
    if wire is not None:
        headers['Content-Type'] = 'application/json'
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=5)
    try:
        connection.request('POST' if body is not None else 'GET', path, body=wire, headers=headers)
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

def process_identity(proc):
    return {'pid': proc.pid, 'created': proc.create_time(), 'command_sha256': hashlib.sha256('\x00'.join(proc.cmdline()).encode()).hexdigest()}

def launch(out, name, restore=False):
    target = out / name
    arguments = [sys.executable, '-X', 'utf8', '-m', 'scripts.campaign9_manager.backend_restart', '--child', str(target)]
    if restore:
        arguments.append('--restore')
    child_env = {key: value for key, value in os.environ.items() if key.upper() in {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP'}}
    child_env['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + str(ROOT)
    stdout = (out / (name + '.stdout')).open('w', encoding='utf-8')
    stderr = (out / (name + '.stderr')).open('w', encoding='utf-8')
    process = subprocess.Popen(arguments, cwd=ROOT, env=child_env, stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    identity = {'launcher': process_identity(psutil.Process(process.pid)), 'worker': None}
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Owned backend failed startup; retain stderr.')
            if (target / 'READY.json').exists():
                ready = json.loads((target / 'READY.json').read_text(encoding='utf-8'))
                worker = psutil.Process(ready['pid'])
                if worker.pid != process.pid and process.pid not in [parent.pid for parent in worker.parents()]:
                    raise RuntimeError('Backend is not the recorded launcher or its own child.')
                identity['worker'] = process_identity(worker)
                if ready['create_time'] != identity['worker']['created'] or Path(ready['root']) != target:
                    raise RuntimeError('Owned backend identity mismatch.')
                return (process, identity, ready, stdout, stderr)
            time.sleep(0.05)
        raise TimeoutError('Owned backend startup deadline.')
    except Exception:
        stop_owned(process, identity)
        stdout.close()
        stderr.close()
        raise

def stop_owned(process, identity):
    worker = identity.get('worker')
    if worker is not None and worker['pid'] != process.pid and psutil.pid_exists(worker['pid']):
        owned_worker = psutil.Process(worker['pid'])
        if process_identity(owned_worker) != worker:
            raise RuntimeError('Refusing backend worker termination after identity changed.')
        owned_worker.terminate()
        owned_worker.wait(timeout=10)
    if process.poll() is None:
        if process_identity(psutil.Process(process.pid)) != identity['launcher']:
            raise RuntimeError('Refusing process termination after identity changed.')
        process.terminate()
        process.wait(timeout=10)

def execute(out):
    if out.exists() or not out.is_relative_to(ROOT / 'data/campaign9-manager/development'):
        raise ValueError('A fresh C9-owned evidence directory is required.')
    out.mkdir(parents=True)
    (out / 'OWNED.txt').write_text('C9 disposable backend restart fixture', encoding='utf-8')
    before = runtime()
    children = []
    results = {}
    try:
        first = launch(out, 'server-one')
        children.append(first)
        old, old_identity, ready, _, _ = first
        old_token = request(ready, '/api/chat?before=1')[1]['token']
        key = str(uuid.uuid4())
        prompt = 'C9 ordinary disposable request awaiting a controller.'
        status, _ = request(ready, '/api/chat', token=old_token, body={'id': key, 'message': prompt})
        assert status == 202
        queued = request(ready, '/api/chat', token=old_token)[1]
        assert queued['queued'] == 1 and len(queued['messages']) == 1
        stop_owned(old, old_identity)
        assert old.poll() is not None
        second = launch(out, 'server-two', restore=True)
        children.append(second)
        new, _, reopened, _, _ = second
        snapshot = request(reopened, '/api/chat')[1]
        new_token = snapshot['token']
        assert new_token != old_token
        assert snapshot['queued'] == 0 and snapshot['busy'] is False
        assert len(snapshot['messages']) == 1 and snapshot['messages'][0]['status'] == 'interrupted'
        assert request(reopened, '/api/productivity', token=old_token)[0] == 403
        assert request(reopened, '/api/productivity', token=new_token)[0] == 200
        assert request(reopened, '/api/chat', token=new_token, body={'id': key, 'message': prompt})[0] == 202
        replay = request(reopened, '/api/chat', token=new_token)[1]
        assert replay['queued'] == 0 and len(replay['messages']) == 1
        assert request(reopened, '/api/shutdown', token=new_token, body={}) == (202, {'stopping': True})
        new.wait(timeout=15)
        assert new.returncode == 0
        closed = json.loads((out / 'server-two/CLOSED.json').read_text(encoding='utf-8'))
        assert closed['owned_http_closed'] and closed['chat_closed']
        after = runtime()
        unchanged = before['ports'] == after['ports'] and before['processes'] == after['processes']
        assert unchanged
        results = {'scope': 'ACTUAL owned Windows backend process interruption/relaunch; original HTTP/ChatHub, copied closed disposable SQLite snapshot, no inference consumer', 'passed': True, 'queued_before': 1, 'queued_after_restart': 0, 'restored_messages': 1, 'restored_status': 'interrupted', 'replay_queue_entries': 0, 'old_token_status': 403, 'new_token_status': 200, 'graceful_shutdown_status': 202, 'owner_process_identities_unchanged': unchanged, 'owned_children': [x[1] for x in children], 'real_credentials_or_owner_stores_used': False, 'model_generation_requests': 0, 'actual_real_windows_restart': False, 'synthetic_restore_leaf': 'copy closed owned chat SQLite into a fresh original backend before ChatHub initialization'}
    except Exception as error:
        results = {'passed': False, 'scope': 'CONTROLLED owned backend process restart', 'error_type': type(error).__name__, 'error': str(error)}
        raise
    finally:
        for process, identity, _, stdout, stderr in children:
            stop_owned(process, identity)
            stdout.close()
            stderr.close()
        results['owned_children_closed'] = all((item[0].poll() is not None and (item[1]['worker'] is None or not psutil.pid_exists(item[1]['worker']['pid'])) for item in children))
        publish(out / 'RESULTS.json', results)
    print(json.dumps(results))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--child', type=Path)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    if args.child:
        child(args.child.resolve(), args.restore)
    else:
        execute(args.out.resolve())
if __name__ == '__main__':
    main()
