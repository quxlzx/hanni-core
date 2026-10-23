"""Original shipped UI, isolated headless browser, synthetic API state only.

The browser's page screenshots are UI review artifacts. They do not exercise
HANNI screen capture, image retention, image analysis or voice hardware.
"""
from contextlib import contextmanager
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import threading
import time
REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / 'src/hanni/dashboard/static'
EDGE = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
CASES = [{'id': 'screen-unimplemented', 'view': 'screen', 'operation': 'screen', 'checks': {'analyze_disabled': True, 'capture_inactive': True}}, {'id': 'voice-disconnect-cached', 'view': 'voice', 'operation': 'voice_disconnect', 'checks': {'disconnected': True, 'voice_controls_disabled': True, 'no_current_voice_claim': True}}, {'id': 'voice-reconnect', 'view': 'voice', 'operation': 'voice_reconnect', 'checks': {'speaking': True, 'voice_controls_enabled': True}}, {'id': 'workspace-stale', 'view': 'home', 'operation': 'stale', 'checks': {'no_current_voice_claim': True, 'input_level_zero': True}}, {'id': 'workspace-sample-error', 'view': 'home', 'operation': 'sample_error', 'checks': {'no_current_voice_claim': True, 'input_level_zero': True}}, {'id': 'mini-stale', 'view': 'mini', 'operation': 'stale', 'checks': {'no_current_voice_claim': True, 'input_level_zero': True}}, {'id': 'mini-sample-error', 'view': 'mini', 'operation': 'sample_error', 'checks': {'no_current_voice_claim': True, 'input_level_zero': True}}]

@contextmanager
def static_server():

    class Handler(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ASSETS), **kwargs)

        def log_message(self, *_):
            pass
    service = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{service.server_port}'
    finally:
        service.shutdown()
        service.server_close()
        thread.join(5)

def fixture_state():
    now = time.time()
    return {'chat': {'messages': [], 'ready': True, 'busy': False, 'queued': 0, 'token': 'campaign-owned-synthetic-token', 'epoch': 'campaign7', 'saved': False, 'has_more': False}, 'state': {'sampled_at': now, 'error': None, 'model_status': 'unavailable', 'safe_mode': False, 'model': {'file': 'synthetic-text-model.gguf', 'quantization': 'unknown', 'context': 4096}, 'model_residency': {}, 'resources': None, 'activity': {'speaking': True, 'microphone_active': True, 'input_level': 0.6}, 'interaction': {'response_in_progress': False, 'tts_speaking': True, 'voice_engaged': True, 'active_background_jobs': 0}}, 'workspace': {'version': 1, 'transport': 'controlled UI projections', 'screens': ['home', 'voice', 'screen'], 'features': {'audio_devices': False}, 'timezone': 'UTC', 'models': [], 'capabilities': []}, 'activity': {'available': True, 'events': []}, 'voice': {'available': True, 'state': 'speaking', 'active': True, 'muted': False, 'microphone_active': True, 'input_level': 0.6, 'speaking': True, 'processing': False, 'actions': {'listen': True, 'mute': True, 'unmute': False, 'interrupt': True}, 'metrics': {'wake_to_listening_ms': None, 'end_to_response_ms': None, 'first_audible_ms': None, 'interrupt_ms': None, 'audio_failures': 0}, 'reason': None}}

def run(output):
    from urllib.parse import urlsplit
    from playwright.sync_api import sync_playwright
    from hanni.config.loader import load_config
    from hanni.dashboard.features import DesktopFeatures
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Never overwrite earlier UI evidence.')
    output.mkdir(parents=True)
    serialized = json.dumps(CASES, indent=2) + '\n'
    (output / 'prospective-cases.json').write_text(serialized, encoding='utf8', newline='\n')
    sources = [ASSETS / 'app.js', ASSETS / 'style.css', REPO / 'frontend/src/awareness.tsx', REPO / 'frontend/src/mini.tsx', REPO / 'frontend/src/workspace.tsx']
    before = {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    config = load_config(REPO / 'config', data_dir=output / 'isolated-config', env={})
    actual_status = DesktopFeatures(config).awareness()
    rows = []
    with static_server() as origin, sync_playwright() as driver:
        browser = driver.chromium.launch(executable_path=str(EDGE), headless=True, args=['--disable-gpu', '--disable-background-networking', '--no-first-run'])
        try:
            for case in CASES:
                context = browser.new_context(viewport={'width': 460 if case['view'] == 'mini' else 1366, 'height': 660 if case['view'] == 'mini' else 900}, reduced_motion='reduce')
                page = context.new_page()
                state = fixture_state()
                phase = {'value': 'healthy'}
                requests = []
                violations = []
                if case['operation'] == 'stale':
                    state['state']['sampled_at'] = time.time() - 120
                if case['operation'] == 'sample_error':
                    state['state']['error'] = 'Synthetic telemetry sample failed.'

                def route(request_route):
                    request = request_route.request
                    url = urlsplit(request.url)
                    if not request.url.startswith(origin + '/'):
                        violations.append({'kind': 'non-owned-origin', 'method': request.method})
                        request_route.abort()
                        return
                    if not url.path.startswith('/api/'):
                        request_route.continue_()
                        return
                    requests.append({'path': url.path, 'method': request.method, 'phase': phase['value']})
                    if request.method != 'GET':
                        violations.append({'kind': 'mutation-attempt', 'path': url.path})
                        request_route.fulfill(status=403, json={'error': 'This UI evidence forbids mutations.'})
                    elif url.path == '/api/voice' and phase['value'] == 'disconnected':
                        request_route.fulfill(status=503, json={'error': 'Synthetic voice projection disconnected.'})
                    else:
                        data = actual_status if url.path == '/api/awareness' else state.get(url.path.split('/')[-1], {})
                        request_route.fulfill(status=200, json=deepcopy(data))
                page.route('**/*', route)
                destination = origin + ('/?view=mini' if case['view'] == 'mini' else '/#' + case['view'])
                page.goto(destination, wait_until='domcontentloaded', timeout=15000)
                if case['view'] == 'screen':
                    page.get_by_role('heading', name='Screen awareness', exact=True).wait_for()
                    page.get_by_text('Screen capture and visual analysis are unavailable in this session.', exact=False).wait_for()
                elif case['view'] == 'voice':
                    page.locator('.voice-state-label').filter(has_text='speaking').wait_for()
                    if case['operation'] == 'voice_disconnect':
                        phase['value'] = 'disconnected'
                        page.locator('.voice-state-label').filter(has_text='Disconnected').wait_for(timeout=5000)
                    elif case['operation'] == 'voice_reconnect':
                        phase['value'] = 'disconnected'
                        page.locator('.voice-state-label').filter(has_text='Disconnected').wait_for(timeout=5000)
                        phase['value'] = 'healthy'
                        page.locator('.voice-state-label').filter(has_text='speaking').wait_for(timeout=5000)
                else:
                    page.wait_for_timeout(700)
                if case['view'] == 'home':
                    page.get_by_role('button', name='Show voice details', exact=True).click()
                region = page.locator('.voice-controls-panel' if case['view'] == 'voice' else '.voice-dock' if case['view'] == 'home' else '.mini-status' if case['view'] == 'mini' else '.awareness-status')
                text = region.inner_text()
                observation = {'text': text, 'body': page.locator('body').inner_text(), 'buttons': [{'text': b.inner_text(), 'disabled': b.is_disabled()} for b in region.get_by_role('button').all()], 'input_levels': page.get_by_role('meter').evaluate_all('(elements)=>elements.map(e=>e.value)'), 'requests': requests, 'violations': violations}
                if case['view'] == 'mini':
                    observation['input_levels'] = page.locator('.mini-meter i').evaluate_all('(elements)=>elements.map(e=>parseFloat(e.style.width || "0") / 100)')
                checks = []
                for name, expected in case['checks'].items():
                    if name == 'analyze_disabled':
                        observed = page.get_by_role('button', name='Analyze current screen', exact=True).is_disabled()
                    elif name == 'capture_inactive':
                        observed = 'No screen image is being collected' in observation['body']
                    elif name == 'disconnected':
                        observed = page.locator('.voice-state-label').inner_text() == 'Disconnected'
                    elif name == 'voice_controls_disabled':
                        observed = all((b['disabled'] for b in observation['buttons']))
                    elif name == 'voice_controls_enabled':
                        observed = any((not b['disabled'] for b in observation['buttons']))
                    elif name == 'speaking':
                        observed = 'Speaking' in text
                    elif name == 'no_current_voice_claim':
                        observed = not any((word in text for word in ('Speaking', 'Listening', 'Active')))
                    elif name == 'input_level_zero':
                        observed = bool(observation['input_levels']) and all((value == 0 for value in observation['input_levels']))
                    checks.append({'check': name, 'observed': observed, 'expected': expected, 'passed': observed == expected})
                page.screenshot(path=str(output / (case['id'] + '.png')), full_page=True)
                rows.append({'id': case['id'], 'passed': all((c['passed'] for c in checks)) and (not violations), 'checks': checks, 'observation': observation})
                context.close()
        finally:
            browser.close()
    after = {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    result = {'scope': 'Actual shipped UI, headless owned browser, synthetic API projections. No physical capture or audio.', 'source_before': before, 'source_after': after, 'case_sha256': hashlib.sha256(serialized.encode()).hexdigest(), 'cases': rows, 'browser_closed': True, 'server_closed': True, 'source_unchanged': before == after}
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({'cases': len(result['cases']), 'passed': sum((c['passed'] for c in result['cases'])), 'failures': [c['id'] for c in result['cases'] if not c['passed']], 'source_unchanged': result['source_unchanged']}))
