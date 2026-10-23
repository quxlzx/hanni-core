"""Actual native backend loss/reconnect against exact owned original processes."""
from __future__ import annotations
import argparse
import http.client
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit
from scripts.campaign8_native.session import NativeSession, ROOT

def authority(ready):
    import psutil
    process = psutil.Process(ready['pid'])
    if process.create_time() != ready['create_time']:
        raise RuntimeError('Owned original backend process identity changed.')
    command = process.cmdline()
    if 'scripts.campaign8_ui.backend' not in command or '--root' not in command:
        raise RuntimeError('Backend was not started by the campaign-owned helper.')
    supplied_root = Path(command[command.index('--root') + 1])
    if not supplied_root.is_absolute():
        supplied_root = Path(process.cwd()) / supplied_root
    if supplied_root.resolve() != Path(ready['root']).resolve():
        raise RuntimeError('Original backend root provenance differs.')
    url = urlsplit(ready['url'])
    if url.hostname != '127.0.0.1' or url.port in {8080, 8765}:
        raise RuntimeError('Only an owned disposable loopback endpoint is permitted.')
    return (process, url)

def request(ready, path, *, token=None, method='GET'):
    unused, url = authority(ready)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=8)
    headers = {'Origin': ready['url']}
    if token is not None:
        headers['X-Hanni-Token'] = token
    if method == 'POST':
        headers['Content-Type'] = 'application/json'
    try:
        connection.request(method, path, body='{}' if method == 'POST' else None, headers=headers)
        response = connection.getresponse()
        body = response.read()
        return (response.status, json.loads(body) if body else None)
    finally:
        connection.close()

def stop_owned(ready):
    process, unused = authority(ready)
    status, chat = request(ready, '/api/chat')
    if status != 200 or not isinstance(chat.get('token'), str):
        raise RuntimeError('Original owned session authority unavailable.')
    status, unused = request(ready, '/api/shutdown', token=chat['token'], method='POST')
    if status != 202:
        raise RuntimeError('Original owned shutdown did not acknowledge.')
    process.wait(timeout=15)
    return {'pid': ready['pid'], 'create_time': ready['create_time'], 'status': status, 'closed_receipt_exists': (Path(ready['root']) / 'CLOSED.json').is_file(), 'tokens_persisted': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replacement-root', type=Path, required=True)
    args = parser.parse_args()
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    authority(ready)
    replacement_root = args.replacement_root.resolve()
    if not replacement_root.is_relative_to((ROOT / 'data/campaign8-ui').resolve()) or replacement_root.exists():
        raise ValueError('Use a fresh campaign-owned replacement backend directory.')
    child = replacement = log = None
    try:
        with NativeSession(url=ready['url'], output=args.output, maximum_seconds=180) as session:
            session.report['reconnect'] = {'scope': 'Actual native attachment and original owned backend replacement; fresh disposable stores', 'original_backend': {k: ready[k] for k in ['url', 'pid', 'create_time', 'root']}}
            unused, old_chat = request(ready, '/api/chat')
            old_token = old_chat['token']
            session.report['reconnect']['before'] = {'dom': session.dom(), 'window': session.window_state(session.main), 'screenshot': session.capture('before-backend-loss'), 'epoch': old_chat['epoch']}
            session.report['reconnect']['owned_shutdown'] = stop_owned(ready)
            deadline = time.monotonic() + 15
            offline_seen = False
            disconnected_seen = False
            while time.monotonic() < deadline:
                session.check_budget()
                body = session.page.locator('body').inner_text()
                offline_seen = 'Connect to your workspace' in body
                disconnected_seen = session.page.locator('.connection').count() > 0 and session.page.locator('.connection').inner_text().strip() == 'Disconnected'
                if offline_seen or disconnected_seen:
                    break
                session.page.wait_for_timeout(200)
            session.report['reconnect']['loss'] = {'native_offline_document_observed': offline_seen, 'original_loaded_ui_disconnected_observed': disconnected_seen, 'dom': session.dom(), 'body_text': session.page.locator('body').inner_text(), 'screenshot': session.capture('actual-backend-loss')}
            command = [str(ROOT / '.venv/Scripts/python.exe'), '-X', 'utf8', '-m', 'scripts.campaign8_ui.backend', '--root', str(replacement_root), '--port', str(urlsplit(ready['url']).port), '--timeout', '180']
            log = (session.output / 'replacement-backend.log').open('w', encoding='utf8')
            child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            import psutil
            launcher = psutil.Process(child.pid)
            launcher_identity = {'pid': child.pid, 'create_time': launcher.create_time()}
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                session.check_budget()
                path = replacement_root / 'READY.json'
                if path.is_file():
                    candidate = json.loads(path.read_text(encoding='utf8'))
                    actual, unused_url = authority(candidate)
                    if candidate['url'] != ready['url'] or Path(candidate['root']).resolve() != replacement_root or launcher.create_time() != launcher_identity['create_time'] or (actual.pid != child.pid and actual.ppid() != child.pid):
                        raise RuntimeError('Replacement original backend owned launcher/child provenance or endpoint differs.')
                    replacement = candidate
                    session.report['reconnect']['replacement_launcher_provenance'] = {'launcher': launcher_identity, 'actual_backend_pid': actual.pid, 'actual_backend_create_time': actual.create_time(), 'actual_parent_pid': actual.ppid(), 'same_or_immediate_owned_child': True}
                    break
                if child.poll() is not None:
                    raise RuntimeError('Owned replacement backend exited before readiness.')
                time.sleep(0.1)
            if replacement is None:
                raise TimeoutError('Owned replacement original backend did not become ready.')
            unused, new_chat = request(replacement, '/api/chat')
            old_status, unused = request(replacement, '/api/model-lab', token=old_token)
            new_status, unused = request(replacement, '/api/model-lab', token=new_chat['token'])
            deadline = time.monotonic() + 20
            reconnected = False
            while time.monotonic() < deadline:
                session.check_budget()
                if session.page.url.startswith(ready['url'] + '/') and session.page.get_by_role('button', name='Search workspace', exact=True).count() and session.page.locator('.connection').count() and (session.page.locator('.connection').inner_text().strip() == 'Connected'):
                    reconnected = True
                    break
                session.page.wait_for_timeout(200)
            session.report['reconnect']['recovery'] = {'original_loaded_ui_connection_restored': reconnected, 'native_reload_not_required': True, 'replacement_backend': {k: replacement[k] for k in ['url', 'pid', 'create_time', 'root']}, 'epoch_changed': old_chat['epoch'] != new_chat['epoch'], 'token_changed': old_token != new_chat['token'], 'old_token_status': old_status, 'new_token_status': new_status, 'tokens_persisted': False, 'fresh_original_chat_ready': new_chat['ready'], 'dom': session.dom(), 'screenshot': session.capture('actual-reconnected-dashboard')}
            session.report['complete'] = True
        authority(replacement)
        session.report['reconnect']['backend_preserved_after_native_exit'] = child.poll() is None
        session.report['reconnect']['replacement_shutdown'] = stop_owned(replacement)
        child.wait(timeout=10)
        session.report['reconnect']['replacement_exit_code'] = child.returncode
        session.save()
    finally:
        if child is not None and child.poll() is None:
            if replacement is not None:
                stop_owned(replacement)
                child.wait(timeout=10)
            else:
                child.terminate()
                child.wait(timeout=10)
        if log is not None:
            log.close()
if __name__ == '__main__':
    main()
