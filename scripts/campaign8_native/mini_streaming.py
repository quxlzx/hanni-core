"""One native Mini request and original owned-history Cancel/Confirm controls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
import time
from scripts.campaign8_native.development import authenticated_readback
from scripts.campaign8_native.session import NativeSession, ROOT

def mini_completion_readback(page):
    return page.evaluate("() => {\n      const rows=[...document.querySelectorAll('.mini-history .mini-message:not(.from-user)')];\n      const row=rows.at(-1);\n      return {message_exists:!!row, rendered_content:row?.querySelector('p')?.textContent??null,\n        message_status:row?.querySelector('div span')?.textContent?.trim()??null,\n        mini_state:document.querySelector('.mini-status>span')?.textContent?.trim()??null};\n    }")

def mini_completion_matches(observed, message):
    return message.get('role') == 'assistant' and message.get('status') == 'complete' and isinstance(message.get('content'), str) and bool(message['content']) and (observed.get('message_exists') is True) and (observed.get('rendered_content') == message['content']) and (observed.get('message_status') == '') and (observed.get('mini_state') == 'Ready')

def owned_chat_rows(root):
    root = Path(root).resolve()
    if not root.is_relative_to((ROOT / 'data/campaign8-ui').resolve()):
        raise ValueError('Read-only chat evidence must belong to the disposable campaign backend.')
    path = root / 'campaign-chat.sqlite3'
    if not path.is_file():
        raise FileNotFoundError('The original owned chat database is missing.')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute('SELECT id,turn,role,content,channel,status,created FROM messages ORDER BY id LIMIT 100')]

def execute_steps(session, case, *, mini=False):
    if mini:
        session.execute({'id': case['id'] + '-owned-mini-setup', 'action': 'show', 'view': 'mini'})
    else:
        session.execute({'id': case['id'] + '-route', 'action': 'route', 'route': case['route']})
    session.execute({'id': case['id'] + '-size', 'action': 'resize', 'view': 'mini' if mini else 'main', 'size': case['window_size']})
    receipts = []
    for index, step in enumerate(case['steps']):
        if step['action'] not in {'click', 'fill'}:
            raise ValueError('The sealed Mini/history controls use only original click/fill actions.')
        receipt = session.execute({'id': case['id'] + '-step-' + str(index), **step, 'view': 'mini' if mini else 'main'})
        receipt['screenshot'] = session.capture(case['id'] + '-step-' + str(index), mini=mini)
        receipts.append(receipt)
    return receipts

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prospective-inputs', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    process = psutil.Process(ready['pid'])
    if process.create_time() != ready['create_time'] or 'scripts.campaign8_ui.streaming' not in process.cmdline() or ready.get('streaming', {}).get('max_generation_requests') != 1:
        raise RuntimeError('The original MAX1 streaming producer ownership was not verified.')
    cases = json.loads(args.prospective_inputs.read_text(encoding='utf8'))
    if [case['id'] for case in cases] != ['mini-extension-one-genuine-send', 'mini-extension-main-clear-cancel', 'mini-extension-main-clear-confirm'] or cases[0]['steps'][0].get('value') != ready['streaming']['prompt']:
        raise ValueError('Use the sealed three-control plan and sole original producer prompt.')
    with NativeSession(url=ready['url'], output=args.output, maximum_seconds=180) as session:
        session.report['backend_receipt'] = {k: ready[k] for k in ['url', 'pid', 'create_time', 'root', 'scope', 'evidence_class']}
        session.report['mini_genuine_request'] = {'scope': 'Actual native Mini controls over unchanged original MAX1 controller; no semantic quality claim', 'observations': [], 'native_completion_confirmed': False}
        evidence = session.report['mini_genuine_request']
        session.execute({'id': 'shared-main-conversation-setup', 'action': 'route', 'route': 'chat'})
        evidence['before'] = authenticated_readback(session, '/api/chat')
        if evidence['before']['data'].get('busy') or evidence['before']['data'].get('messages'):
            raise RuntimeError('The original isolated conversation must be fresh and idle before the sole send.')
        started = time.monotonic()
        evidence['input'] = cases[0]
        evidence['steps'] = execute_steps(session, cases[0], mini=True)
        until = started + 60
        captured = set()
        target = None
        while time.monotonic() < until:
            session.check_budget()
            api = authenticated_readback(session, '/api/chat')
            data = api['data']
            assistant = [m for m in data.get('messages', []) if m.get('role') == 'assistant']
            working = data.get('busy') or any((m.get('status') == 'working' for m in assistant))
            finished = bool(assistant) and (not working) and (not data.get('queued'))
            phase = 'complete' if finished else 'partial' if any((m.get('content') for m in assistant)) else 'working'
            row = {'elapsed_seconds': time.monotonic() - started, 'phase_scope': 'Original backend status; native completion measured separately', 'phase': phase, 'api': api}
            if phase not in captured:
                row['dom'] = session.dom(mini=True)
                row['screenshot'] = session.capture('mini-backend-' + phase, mini=True)
                captured.add(phase)
            evidence['observations'].append(row)
            session.save()
            if finished:
                target = next((m for m in reversed(assistant) if m.get('status') == 'complete' and isinstance(m.get('content'), str) and m['content']), None)
                break
            session.mini_page.wait_for_timeout(100)
        evidence['native_settle_observations'] = []
        if target is not None:
            until = time.monotonic() + 10
            while time.monotonic() < until:
                session.check_budget()
                observed = mini_completion_readback(session.mini_page)
                evidence['native_settle_observations'].append(observed)
                if mini_completion_matches(observed, target):
                    session.mini_page.wait_for_timeout(150)
                    painted = mini_completion_readback(session.mini_page)
                    evidence['native_after_paint'] = painted
                    if mini_completion_matches(painted, target):
                        evidence['native_completion_confirmed'] = True
                        break
                session.mini_page.wait_for_timeout(100)
        evidence['final_api'] = authenticated_readback(session, '/api/chat')
        evidence['persisted_original_rows_before_clear'] = owned_chat_rows(ready['root'])
        evidence['final_dom'] = session.dom(mini=True)
        evidence['final_screenshot'] = session.capture('mini-final-native-complete' if evidence['native_completion_confirmed'] else 'mini-final-unverified', mini=True)
        session.save()
        session.report['owned_history_controls'] = []
        for case in cases[1:]:
            before = authenticated_readback(session, '/api/chat')
            old_token = session.page.request.get(session.url + '/api/chat').json().get('token')
            row = {'input': case, 'before': before, 'steps': execute_steps(session, case), 'after': authenticated_readback(session, '/api/chat'), 'persisted_original_rows_after': owned_chat_rows(ready['root']), 'dom': session.dom(), 'screenshot': session.capture(case['id'])}
            if case['id'].endswith('-confirm'):
                new_token = session.page.request.get(session.url + '/api/chat').json().get('token')
                if not isinstance(old_token, str) or not isinstance(new_token, str):
                    raise RuntimeError('Original owned token-rotation authority is unavailable.')
                row['token_rotation'] = {'changed': old_token != new_token, 'old_status': session.page.request.get(session.url + '/api/mcp', headers={'X-Hanni-Token': old_token, 'Origin': session.url}).status, 'new_status': session.page.request.get(session.url + '/api/mcp', headers={'X-Hanni-Token': new_token, 'Origin': session.url}).status, 'tokens_persisted': False}
            session.report['owned_history_controls'].append(row)
            session.save()
        session.report['complete'] = True
    session.report['backend_preserved_after_native_exit'] = process.create_time() == ready['create_time']
    session.save()
if __name__ == '__main__':
    main()
