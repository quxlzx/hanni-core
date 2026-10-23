"""Bounded local startup/restart smoke check; synthetic content and disposable stores."""
from __future__ import annotations

import base64
import ctypes
import io
import json
from pathlib import Path
import socket
import subprocess
import time
import uuid

import psutil
import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT/'data/startup-repair'/('live-'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    state = output/'native-state'; state.mkdir()
    (state/'window.json').write_text(json.dumps(dict(width=1100, height=760,
        close_to_tray=False, minimize_to_tray=False, notifications=False,
        mini_shortcut='Ctrl+Shift+F11')), encoding='utf8')
    report = {'physical_audio': 'Not tested; hardware unavailable', 'checks': {}, 'outputs': {}}
    backend = native = browser = None
    url = 'http://127.0.0.1:8766'
    token = None
    deadline = time.monotonic()+360
    def budget():
        assert time.monotonic() < deadline, '360-second smoke-check budget exhausted'
        assert psutil.virtual_memory().available > 3*1024**3, 'RAM reserve exhausted'
    def wait(predicate, seconds=90):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            budget()
            try:
                result = predicate()
                if result: return result
            except (requests.RequestException, OSError):
                pass
            time.sleep(.25)
        raise TimeoutError('Original service did not become ready')
    def get(path):
        response = requests.get(url+path, timeout=3); response.raise_for_status()
        return response.json()
    def post(path, body, credential):
        return requests.post(url+path, json=body, timeout=10,
            headers={'Origin': url, 'X-Hanni-Token': credential})
    def model_pid():
        return next(c.pid for c in psutil.net_connections(kind='tcp')
            if c.status == 'LISTEN' and c.laddr.ip == '127.0.0.1' and c.laddr.port == 8080)
    try:
        budget()
        for port in (8080,8766,9334):
            with socket.socket() as check:
                assert check.connect_ex(('127.0.0.1',port)), f'Existing listener {port}; do not disrupt'
        from huggingface_hub import try_to_load_from_cache
        weights = try_to_load_from_cache('lmstudio-community/Qwen3.5-4B-GGUF','Qwen3.5-4B-Q4_K_M.gguf')
        assert isinstance(weights,str) and Path(weights).is_file()
        marker = output/'saved-preferences-fixture.json'
        marker.write_text('{"synthetic":"preserve me"}', encoding='utf8')
        with (output/'backend.log').open('w', encoding='utf8') as log:
            backend = subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'), '-X','utf8',
                '-m','hanni.dashboard.launcher','--text','--no-browser','--port','8766',
                '--data-dir',str(output),'--config-dir',str(ROOT/'config'),
                '--model-file',weights,'--startup-timeout','120'],
                cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        chat = wait(lambda: (s if (s:=get('/api/chat'))['ready'] else False),120)
        token, epoch = chat['token'],chat['epoch']
        pid = model_pid(); created = psutil.Process(pid).create_time()
        assert pid in {p.pid for p in psutil.Process(backend.pid).children(recursive=True)}
        report['checks']['language_and_vision_autostart'] = True
        report['outputs']['first_owned_model_pid'] = pid
        props = requests.get('http://127.0.0.1:8080/props',timeout=5).json()
        report['outputs']['model_modalities'] = props.get('modalities')
        assert props.get('modalities',{}).get('vision') is True, props.get('modalities')
        image = Image.new('RGB',(224,224),'white')
        ImageDraw.Draw(image).rectangle((45,45,180,180),fill='red')
        buffer = io.BytesIO(); image.save(buffer,format='PNG')
        image.save(output/'synthetic-red-square.png')
        started = time.monotonic()
        response = requests.post('http://127.0.0.1:8080/v1/chat/completions', timeout=75,
            json={'model':'supervisor','temperature':0,'max_tokens':64,
                'chat_template_kwargs':{'enable_thinking':False},
                'messages':[{'role':'user','content':[
                    {'type':'text','text':'What color and shape is the object in this synthetic image? Answer briefly.'},
                    {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()}}]}]})
        response.raise_for_status()
        answer = response.json()['choices'][0]['message']['content']
        report['outputs']['vision'] = {'answer':answer,'seconds':time.monotonic()-started,
                                      'usage':response.json().get('usage')}
        assert 'red' in answer.lower() and 'square' in answer.lower(), answer
        report['checks']['real_synthetic_vision_inference'] = True
        turn = str(uuid.uuid4())
        response = post('/api/chat',{'id':turn,'message':'Hello Hanni. Reply with a short greeting.'},token)
        response.raise_for_status()
        def completed():
            rows = get('/api/chat')['messages']
            return next((r for r in rows if r['turn']==turn and r['role']=='assistant'
                and r['status']=='complete'),None)
        reply = wait(completed,90)
        report['outputs']['actual_controller_reply'] = reply['content']
        assert reply['content'].strip()
        report['checks']['real_controller_language_response'] = True
        executable = ROOT/'dist/HANNI OS/HANNI OS.exe'
        title = 'HANNI Startup Repair '+uuid.uuid4().hex[:10]
        native = subprocess.Popen([str(executable),'--url',url,'--attach-only',
            '--state-dir',str(state),'--debug-port','9334','--title',title],cwd=ROOT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            wait(lambda: requests.get('http://127.0.0.1:9334/json/version',timeout=2).ok,45)
            browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:9334',no_defaults=True)
            def main_page():
                browser.new_browser_cdp_session().send('Target.getTargets')
                return next((p for c in browser.contexts for p in c.pages
                    if p.url.startswith(url+'/') and '?view=mini' not in p.url),None)
            page = wait(main_page,45)
            page.get_by_role('button',name='Settings',exact=True).click(timeout=15000)
            page.locator('#restart').wait_for(timeout=15000)
            assert page.locator('#restart').is_enabled()
            page.locator('#restart').scroll_into_view_if_needed()
            page.screenshot(path=str(output/'native-restart-before.png'))
            page.locator('#restart').click()
            page.get_by_role('dialog').get_by_role('button',name='Restart HANNI',exact=True).click()
            report['checks']['native_restart_button_called_original_backend'] = True
            chat2 = wait(lambda: (s if (s:=get('/api/chat'))['epoch']!=epoch and s['ready'] else False),120)
            token2 = chat2['token']
            assert post('/api/restart',{},token).status_code==403
            token = token2
            pid2 = model_pid()
            assert pid2 != pid and (not psutil.pid_exists(pid) or psutil.Process(pid).create_time()!=created)
            assert pid2 in {p.pid for p in psutil.Process(backend.pid).children(recursive=True)}
            assert any(r['turn']==turn and r['content']==reply['content'] for r in chat2['messages'])
            assert json.loads(marker.read_text()) == {'synthetic':'preserve me'}
            report['checks']['restart_rotates_token_and_owned_model'] = True
            report['checks']['saved_history_and_fixture_survive'] = True
            report['outputs']['second_owned_model_pid'] = pid2
            # Native reconnect can replace the document while the service starts.
            page = wait(main_page,30)
            page.get_by_role('button',name='Settings',exact=True).click(timeout=15000)
            page.locator('#restart').wait_for(timeout=15000)
            wait(lambda: page.locator('#restart').is_enabled(),15)
            page.locator('#restart').scroll_into_view_if_needed()
            page.screenshot(path=str(output/'native-restart-after.png'))
            assert 'Restarting HANNI' not in page.locator('#restart').inner_text()
            report['checks']['native_reconnected_and_restart_control_reset'] = True
        browser = None
        report['success'] = True
    except Exception as exc:
        report['success'] = False
        report['error'] = f'{type(exc).__name__}: {str(exc)[:400]}'
        raise
    finally:
        if native is not None and native.poll() is None:
            # Close only the uniquely titled window belonging to this owned child.
            handle = ctypes.windll.user32.FindWindowW(None,title)
            owner = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(handle,ctypes.byref(owner))
            owned = {native.pid}|{p.pid for p in psutil.Process(native.pid).children(recursive=True)}
            if handle and owner.value in owned:
                ctypes.windll.user32.PostMessageW(handle,0x0010,0,0)
            try: native.wait(timeout=10)
            except subprocess.TimeoutExpired:
                native.terminate(); native.wait(timeout=5)
            report['checks']['owned_native_closed'] = native.poll() is not None
        if backend is not None:
            if backend.poll() is None:
                try:
                    token = get('/api/chat')['token']
                    post('/api/shutdown',{},token).raise_for_status()
                except (requests.RequestException,KeyError):
                    if backend.stdin: backend.stdin.write(b'/exit\n'); backend.stdin.flush()
                try: backend.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    backend.terminate(); backend.wait(timeout=5)
            report['checks']['owned_backend_closed'] = backend.poll() is not None
        (output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'output':str(output),'success':report.get('success'),
                          'checks':report['checks'],'error':report.get('error')}),flush=True)


if __name__ == '__main__':
    main()
