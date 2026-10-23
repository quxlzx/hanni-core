"""One sealed development prompt through actual native UI and original controller."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from scripts.campaign8_native.development import authenticated_readback
from scripts.campaign8_native.session import NativeSession

def native_completion_readback(page, message_id):
    return page.evaluate("id => {\n      const message = document.getElementById('message-' + String(id));\n      return {message_exists:!!message,\n        rendered_content:message?.querySelector('p')?.textContent ?? null,\n        aria_busy:message?.getAttribute('aria-busy') ?? null,\n        chat_state:document.querySelector('.chat-session-state')?.textContent?.trim() ?? null,\n        voice_state:document.querySelector('.voice-toggle strong')?.textContent?.trim() ?? null};\n    }", message_id)

def native_completion_matches(observed, message):
    return observed.get('message_exists') is True and observed.get('rendered_content') == message.get('content') and (observed.get('aria_busy') == 'false') and (observed.get('chat_state') == 'Ready when you are') and isinstance(observed.get('voice_state'), str) and bool(observed['voice_state']) and (observed['voice_state'] not in {'Processing', 'Responding'})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    process = psutil.Process(ready['pid'])
    if process.create_time() != ready['create_time'] or 'scripts.campaign8_ui.streaming' not in process.cmdline():
        raise RuntimeError('Original streaming backend ownership was not verified.')
    prompt = ready['streaming']['prompt']
    with NativeSession(url=ready['url'], output=args.output, maximum_seconds=120) as session:
        session.report['backend_receipt'] = {key: ready[key] for key in ['url', 'pid', 'create_time', 'scope', 'evidence_class']}
        session.report['actual_streaming'] = {'scope': 'Original isolated controller/stores and genuine existing local model; one sealed prompt submitted once', 'prompt': prompt, 'observations': [], 'no_cancellation_api_claimed': True}
        session.execute({'id': 'native-conversation-route', 'action': 'route', 'route': 'chat'})
        session.report['actual_streaming']['before'] = {'api': authenticated_readback(session, '/api/chat'), 'dom': session.dom(), 'screenshot': session.capture('before-genuine-model-message')}
        session.execute({'id': 'fill-sealed-native-prompt', 'action': 'fill', 'selector': '#chat-input', 'value': prompt})
        started = time.monotonic()
        session.execute({'id': 'send-one-sealed-native-prompt', 'action': 'click', 'role': 'button', 'name': 'Send message', 'settle_ms': 0})
        captured = set()
        deadline = started + 60
        while time.monotonic() < deadline:
            session.check_budget()
            receipt = authenticated_readback(session, '/api/chat')
            data = receipt['data']
            assistant = [message for message in data.get('messages', []) if message.get('role') == 'assistant']
            working = any((message.get('status') == 'working' for message in assistant)) or data.get('busy')
            partial = working and any((message.get('content') for message in assistant))
            finished = bool(assistant) and (not data.get('busy')) and (not data.get('queued')) and (not working)
            phase = 'complete' if finished else 'partial' if partial else 'working' if working else 'queued'
            entry = {'elapsed_seconds': time.monotonic() - started, 'phase': phase, 'phase_scope': 'Original backend snapshot, not native render completion', 'api': receipt}
            if phase not in captured:
                session.page.wait_for_timeout(100)
                entry['dom'] = session.dom()
                entry['screenshot'] = session.capture('genuine-model-backend-' + phase)
                captured.add(phase)
            session.report['actual_streaming']['observations'].append(entry)
            session.save()
            if finished:
                break
            session.page.wait_for_timeout(100)
        final_api = authenticated_readback(session, '/api/chat')
        completed = [message for message in final_api['data'].get('messages', []) if message.get('role') == 'assistant' and message.get('status') == 'complete' and isinstance(message.get('content'), str) and message['content']]
        settle = {'scope': 'Read-only native rendered paragraph equals original completed API reply; no injected text or DOM changes', 'bounded_wait_seconds': 10, 'observations': [], 'confirmed': False}
        if completed and (not final_api['data'].get('busy')) and (not final_api['data'].get('queued')):
            target = completed[-1]
            settle['target_message_id'] = target['id']
            until = time.monotonic() + 10
            while time.monotonic() < until:
                session.check_budget()
                observed = native_completion_readback(session.page, target['id'])
                observed['elapsed_seconds'] = time.monotonic() - started
                settle['observations'].append(observed)
                if native_completion_matches(observed, target):
                    session.page.wait_for_timeout(150)
                    painted = native_completion_readback(session.page, target['id'])
                    settle['after_renderer_settle'] = painted
                    if native_completion_matches(painted, target):
                        settle['confirmed'] = True
                        break
                session.page.wait_for_timeout(100)
        else:
            settle['reason'] = 'No complete, non-busy original assistant result; no extra generation requested.'
        session.report['actual_streaming']['native_completion'] = settle
        session.report['actual_streaming']['final'] = {'api': final_api, 'dom': session.dom(), 'native_completion_confirmed': settle['confirmed'], 'screenshot': session.capture('final-exact-native-response' if settle['confirmed'] else 'final-native-completion-unverified'), 'observed_phases': sorted(captured), 'elapsed_seconds': time.monotonic() - started}
        session.report['complete'] = True
    session.report['backend_preserved_after_native_exit'] = process.create_time() == ready['create_time']
    session.save()
if __name__ == '__main__':
    main()
