"""Actual packaged Windows Mini/hotkey review with an isolated synthetic backend.

Global shortcuts are sent while a separate benign native Tk application is in
the foreground. No real microphone, model, tool, node power or terminal is used.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import win32api
import win32con
import win32gui
import win32process
import psutil
from playwright.sync_api import sync_playwright, expect

from capture_native import ROOT, frame_capture, wait_window
from fixture import ReviewFixture


def chord(*keys):
    for key in keys:
        win32api.keybd_event(key, 0, 0, 0)
    time.sleep(.07)
    for key in reversed(keys):
        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)


def wait_for(page, predicate, message, timeout=15):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        page.wait_for_timeout(100)
    raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace-fixture', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    state = args.output/'isolated-native-state'
    state.mkdir(exist_ok=True)
    title, other_title = 'HANNI OS Independent Mini Review', 'Independent Foreground Application'
    result = {'passed':False, 'checks':[], 'defects':[], 'screenshots':[],
              'dpi':ctypes.windll.user32.GetDpiForSystem(),
              'exe_sha256':hashlib.sha256(args.exe.read_bytes()).hexdigest(),
              'disclosure':'Actual executable/native Mini/global shortcuts from another foreground native Tk process. Existing ChatHub, synthetic response/device telemetry; no live model, microphone, machine tool or remote power operation. Transport success does not prove live assistant routing.'}
    result['artifact_sha256'] = {
        'exe': result['exe_sha256'],
        **{name: hashlib.sha256((ROOT/'src/hanni/dashboard/static'/name).read_bytes()).hexdigest()
           for name in ('app.js', 'style.css')},
    }
    app_process = other_process = None
    reserved = False
    factory = ReviewFixture
    if args.workspace_fixture:
        from phase_fixture import PhaseReviewFixture
        factory = PhaseReviewFixture
        result['disclosure'] += ' Real isolated workspace stores; explicit empty offline Google vault; voice inactive/unbound.'
    with factory() as fixture:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            debug_port = sock.getsockname()[1]
        log = (args.output/'native-launch.log').open('w', encoding='utf-8')
        try:
            app_process = subprocess.Popen([str(args.exe.resolve()), '--url', fixture.url,
                '--attach-only', '--state-dir', str(state), '--debug-port', str(debug_port),
                '--title', title], stdout=log, stderr=subprocess.STDOUT)
            main_hwnd = wait_window(title)
            mini_hwnd = wait_window('HANNI Mini')
            assert win32process.GetWindowThreadProcessId(main_hwnd)[1] == win32process.GetWindowThreadProcessId(mini_hwnd)[1], 'Mini belongs to a different application; refusing to drive it'
            other_process = subprocess.Popen([sys.executable, '-c',
                'import tkinter as tk; w=tk.Tk(); w.title("Independent Foreground Application"); '
                'w.geometry("480x240+80+80"); tk.Label(w,text="Independent native foreground application",padx=24,pady=24).pack(); w.mainloop()'])
            other_hwnd = wait_window(other_title)
            other_native_pid=win32process.GetWindowThreadProcessId(other_hwnd)[1]
            assert other_process.pid in {other_native_pid, *(p.pid for p in psutil.Process(other_native_pid).parents())}, 'Foreground helper is outside the launched process tree'
            with sync_playwright() as playwright:
                browser = None
                for _ in range(100):
                    try:
                        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                        break
                    except Exception:
                        time.sleep(.1)
                if browser is None:
                    raise RuntimeError('Actual Mini WebView CDP unavailable')
                pages = []
                for _ in range(300):
                    pages = [p for c in browser.contexts for p in c.pages]
                    candidates = [p for p in pages if p.url.startswith(fixture.url)]
                    if any('?view=mini' in p.url for p in candidates) and any('?view=mini' not in p.url for p in candidates):
                        break
                    if pages:
                        pages[0].wait_for_timeout(100)
                    else:
                        browser.new_browser_cdp_session().send('Target.getTargets')
                mini = next(p for p in pages if p.url.startswith(fixture.url) and '?view=mini' in p.url)
                main_page = next(p for p in pages if p.url.startswith(fixture.url) and '?view=mini' not in p.url)
                expect(mini.locator('[data-mini-input]')).to_be_visible()
                wait_for(mini, lambda:mini.evaluate('Boolean(window.pywebview?.api?.get_state)'), 'Mini bridge unavailable')
                state_before = mini.evaluate('window.pywebview.api.get_state()')
                assert state_before['shortcut'] == 'Ctrl+Shift+Space' and not state_before['error'], state_before
                main_keys = main_page.evaluate('Object.keys(window.pywebview?.api || {})')
                mini_keys = mini.evaluate('Object.keys(window.pywebview?.api || {})')
                assert not main_keys and set(mini_keys) == {'get_state','dismiss','pin','expand','configure_hotkey'}, (main_keys,mini_keys)
                result['checks'].append('Main has no native bridge; Mini exposes only five allowlisted window preference methods')
                unauthenticated = mini.evaluate('''async () => {
                    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({id:crypto.randomUUID(),message:'Unauthorized Mini test'})});
                    return r.status;
                }''')
                assert unauthenticated == 403 and not fixture.hub.queue and not fixture.writes
                invalid = mini.evaluate('''async () => {
                    try { await window.pywebview.api.configure_hotkey('cmd.exe'); return false; }
                    catch { return true; }
                }''')
                assert invalid
                result['checks'].append('Mini rejects unauthorized chat writes and nonallowlisted shortcut')
                result['screenshots'].append(frame_capture(other_hwnd,args.output/'foreground-other-native.png'))
                chord(win32con.VK_CONTROL,win32con.VK_SHIFT,win32con.VK_SPACE)
                wait_for(mini,lambda:win32gui.IsWindowVisible(mini_hwnd),'Global hotkey did not show Mini')
                wait_for(mini,lambda:win32gui.GetForegroundWindow()==mini_hwnd,'Hotkey did not activate Mini from another application')
                assert mini.evaluate('document.activeElement?.matches("[data-mini-input]")')
                result['checks'].append('Genuine Ctrl+Shift+Space from another native foreground process opens/focuses Mini input')
                startup_text = mini.locator('body').inner_text()
                result['startup_body'] = startup_text
                if 'is not a function' in startup_text or 'TypeError' in startup_text:
                    result['defects'].append('Actual initial Mini retains a raw native bridge startup error after API readiness: ' + startup_text)
                else:
                    result['checks'].append('Actual initial Mini has no visible raw bridge error after native API readiness')
                if args.workspace_fixture:
                    expect(mini.locator('.mini-voice-actions')).to_be_visible()
                    for button in mini.locator('.mini-voice-actions button').all():
                        expect(button).to_be_disabled()
                    result['checks'].append('Unbound Mini voice controls remain visibly disabled without microphone capture')
                result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-idle-native.png'))
                original_rect=win32gui.GetWindowRect(mini_hwnd)
                for width,height in [(782,528),(640,480),(600,420),(900,650)]:
                    win32gui.SetWindowPos(mini_hwnd,0,80,80,width,height,win32con.SWP_NOZORDER)
                    mini.wait_for_timeout(250)
                    layout=mini.evaluate('({width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,viewportWidth:document.documentElement.clientWidth})')
                    capture=frame_capture(mini_hwnd,args.output/f'mini-idle-{width}x{height}-native.png')
                    capture['layout']=layout
                    result['screenshots'].append(capture)
                    assert capture['window_size']==[width,height] and layout['documentWidth']<=layout['viewportWidth']+1,capture
                win32gui.SetWindowPos(mini_hwnd,0,original_rect[0],original_rect[1],original_rect[2]-original_rect[0],original_rect[3]-original_rect[1],win32con.SWP_NOZORDER)
                result['checks'].append('Actual Mini rendered at four compact physical sizes without horizontal document overflow')
                chord(win32con.VK_ESCAPE)
                wait_for(mini,lambda:not win32gui.IsWindowVisible(mini_hwnd),'Native Escape did not hide Mini')
                result['checks'].append('Native keyboard Escape dismisses secondary window without stopping backend')
                frame_capture(other_hwnd,args.output/'foreground-other-repeat-native.png')
                chord(win32con.VK_CONTROL,win32con.VK_SHIFT,win32con.VK_SPACE)
                wait_for(mini,lambda:win32gui.IsWindowVisible(mini_hwnd),'Mini did not reopen')
                frame_capture(other_hwnd,args.output/'foreground-other-refocus-native.png')
                chord(win32con.VK_CONTROL,win32con.VK_SHIFT,win32con.VK_SPACE)
                wait_for(mini,lambda:win32gui.IsWindowVisible(mini_hwnd) and win32gui.GetForegroundWindow()==mini_hwnd,'Hotkey failed to refocus already-open Mini from another foreground application')
                result['checks'].append('Global shortcut refocuses an already-open Mini behind another foreground application')
                expect(mini.get_by_role('button',name='Pin',exact=True)).to_be_enabled()
                mini.get_by_role('button',name='Pin',exact=True).click()
                try:
                    wait_for(mini,lambda:bool(win32gui.GetWindowLong(mini_hwnd,win32con.GWL_EXSTYLE)&win32con.WS_EX_TOPMOST),'Pin did not set native always-on-top')
                except RuntimeError:
                    result['pin_failure']={'body':mini.locator('body').inner_text(),'exstyle':win32gui.GetWindowLong(mini_hwnd,win32con.GWL_EXSTYLE),
                        'bridge_state':mini.evaluate('({href:location.href,base:document.baseURI,api:typeof window.pywebview?.api?.get_state})')}
                    result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-pin-failure-native.png'))
                    raise
                assert mini.evaluate('window.pywebview.api.get_state()')['pinned']
                result['checks'].append('Pin changes native WS_EX_TOPMOST and persisted preference')
                mini.get_by_role('button',name='Pinned',exact=True).click()
                wait_for(mini,lambda:not win32gui.GetWindowLong(mini_hwnd,win32con.GWL_EXSTYLE)&win32con.WS_EX_TOPMOST,'Unpin did not clear native always-on-top')
                mini.locator('[data-mini-input]').fill('/')
                expect(mini.get_by_role('region',name='Registered file and app tools')).to_be_visible()
                result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-tool-discovery-native.png'))
                for width,height in [(782,528),(640,480),(600,420),(900,650)]:
                    win32gui.SetWindowPos(mini_hwnd,0,80,80,width,height,win32con.SWP_NOZORDER)
                    mini.wait_for_timeout(250)
                    discovery=mini.evaluate('''() => ({
                        height:innerHeight,
                        input:(() => {const r=document.querySelector('[data-mini-input]').getBoundingClientRect();return {top:r.top,bottom:r.bottom};})(),
                        send:(() => {const r=document.querySelector('.mini-composer button').getBoundingClientRect();return {top:r.top,bottom:r.bottom};})(),
                        historyVisible:Array.from(document.querySelectorAll('.mini-history')).some(e=>e.getBoundingClientRect().height>0),
                        scrollAreas:Array.from(document.querySelectorAll('.mini-history,.mini-capabilities')).filter(e=>e.getBoundingClientRect().height>0 && e.scrollHeight>e.clientHeight+2).map(e=>e.className)
                    })''')
                    capture=frame_capture(mini_hwnd,args.output/f'mini-discovery-{width}x{height}-native.png')
                    capture['discovery_layout']=discovery
                    result['screenshots'].append(capture)
                    assert not discovery['historyVisible'] and len(discovery['scrollAreas'])<=1,discovery
                    assert discovery['input']['top']>=0 and discovery['input']['bottom']<=discovery['height']+1 and discovery['send']['bottom']<=discovery['height']+1,discovery
                win32gui.SetWindowPos(mini_hwnd,0,original_rect[0],original_rect[1],original_rect[2]-original_rect[0],original_rect[3]-original_rect[1],win32con.SWP_NOZORDER)
                result['checks'].append('Tool discovery replaces history with one results scroll area and keeps composer/Send visible at four compact sizes')
                mini.locator('[data-mini-input]').press('ArrowDown')
                mini.locator('[data-mini-input]').press('Enter')
                assert mini.locator('[data-mini-input]').input_value().startswith('Help me use ')
                assert not fixture.hub.queue and not fixture.writes
                result['checks'].append('Keyboard registered file/app discovery prepares a draft and executes no action before Send')
                prompt = 'Independent Mini shared-channel transport check'
                mini.locator('[data-mini-input]').fill(prompt)
                mini.locator('[data-mini-input]').press('Enter')
                wait_for(mini,lambda:len(fixture.hub.queue)==1,'Mini did not submit to existing ChatHub')
                assert fixture.hub.take()==prompt
                row = fixture.hub.begin(prompt,'browser')
                fixture.hub.update(row,'Synthetic verification reply through the existing shared ChatHub.','complete')
                expect(mini.get_by_text('Synthetic verification reply through the existing shared ChatHub.',exact=True)).to_be_visible()
                snapshot=fixture.hub.snapshot()
                assert len([m for m in snapshot['messages'] if m['role']=='user' and m['content']==prompt])==1
                result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-shared-conversation-native.png'))
                mini.get_by_role('button',name='Expand',exact=True).click()
                wait_for(main_page,lambda:not win32gui.IsWindowVisible(mini_hwnd),'Expand did not hide Mini')
                expect(main_page.locator('.screen-chat')).to_be_visible()
                expect(main_page.get_by_text('Synthetic verification reply through the existing shared ChatHub.',exact=True).first).to_be_visible()
                result['screenshots'].append(frame_capture(main_hwnd,args.output/'mini-expanded-shared-chat-native.png'))
                result['checks'].append('Exactly one Mini submission reaches existing ChatHub and expands into the same full conversation')
                frame_capture(other_hwnd,args.output/'foreground-other-conflict-native.png')
                chord(win32con.VK_CONTROL,win32con.VK_SHIFT,win32con.VK_SPACE)
                wait_for(mini,lambda:win32gui.IsWindowVisible(mini_hwnd),'Mini unavailable for conflict check')
                reserved=bool(ctypes.windll.user32.RegisterHotKey(None,0x4B31,0x0002|0x0001|0x4000,0x20))
                if not reserved:
                    raise RuntimeError('Unable to reserve test alternate shortcut; conflict test cannot be graded')
                conflict=mini.evaluate('window.pywebview.api.configure_hotkey("Ctrl+Alt+Space")')
                assert conflict['shortcut']=='Ctrl+Shift+Space' and conflict['error'],conflict
                mini.get_by_role('button',name='Shortcut',exact=True).click()
                expect(mini.get_by_text('is in use by another application',exact=False)).to_be_visible(timeout=6000)
                result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-hotkey-conflict-native.png'))
                ctypes.windll.user32.UnregisterHotKey(None,0x4B31)
                reserved=False
                alternative=mini.evaluate('window.pywebview.api.configure_hotkey("Ctrl+Alt+Space")')
                assert alternative['shortcut']=='Ctrl+Alt+Space' and not alternative['error'],alternative
                mini.evaluate('window.pywebview.api.dismiss()')
                frame_capture(other_hwnd,args.output/'foreground-other-alternate-native.png')
                chord(win32con.VK_CONTROL,win32con.VK_MENU,win32con.VK_SPACE)
                wait_for(mini,lambda:win32gui.IsWindowVisible(mini_hwnd),'Changed global shortcut did not activate Mini')
                mini.evaluate('window.pywebview.api.configure_hotkey("Ctrl+Shift+Space")')
                result['checks'].append('Actual RegisterHotKey conflict is visible and preserves old shortcut; a free alternative registers and activates')
                if fixture.writes:
                    raise RuntimeError(f'Mini unexpectedly invoked machine/settings write handlers: {fixture.writes}')
                fixture.hub.ready=False
                expect(mini.get_by_text('Assistant offline',exact=True)).to_be_visible(timeout=6000)
                mini.locator('[data-mini-input]').fill('Draft retained while offline')
                expect(mini.get_by_role('button',name='Send',exact=True)).to_be_disabled()
                result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-offline-draft-native.png'))
                result['checks'].append('Backend offline disables Send and preserves draft with honest status')
                fixture.hub.ready=True
                expect(mini.get_by_text('Assistant offline',exact=True)).not_to_be_visible(timeout=6000)
                hits = []
                class UntrustedHandler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass
                    def do_GET(self):
                        hits.append(self.path)
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'untrusted')
                foreign = ThreadingHTTPServer(('127.0.0.1',0),UntrustedHandler)
                threading.Thread(target=foreign.serve_forever,daemon=True).start()
                try:
                    target = f'http://127.0.0.1:{foreign.server_port}'
                    before = mini.url
                    page_count = sum(len(c.pages) for c in browser.contexts)
                    mini.evaluate('(url) => { window.open(url,"_blank"); }',target+'/popup')
                    mini.wait_for_timeout(600)
                    mini.evaluate('(url) => { window.location.assign(url); }',target+'/navigation')
                    mini.wait_for_timeout(2500)
                    availability=mini.evaluate('({href:location.href,base:document.baseURI,api:typeof window.pywebview?.api?.get_state})')
                    result['post_navigation_availability']=availability
                    assert not hits and mini.url == before and sum(len(c.pages) for c in browser.contexts)==page_count, (hits,mini.url)
                    assert availability['href']==before and availability['base'].startswith(fixture.url) and availability['api']=='function',availability
                    healthy=mini.evaluate('Promise.race([window.pywebview.api.get_state(),new Promise(resolve=>setTimeout(()=>resolve("bridge timeout"),2000))])')
                    assert isinstance(healthy,dict) and healthy['shortcut']=='Ctrl+Shift+Space',healthy
                    expect(mini.get_by_text('Assistant offline',exact=True)).not_to_be_visible()
                    result['screenshots'].append(frame_capture(mini_hwnd,args.output/'mini-after-blocked-navigation-native.png'))
                finally:
                    foreign.shutdown()
                    foreign.server_close()
                result['checks'].append('Foreign popup/navigation receives zero HTTP requests and preserves trusted Mini bridge, document/base URL and backend availability')
                result['passed']=True
        except Exception as error:
            result['defects'].append(f'{type(error).__name__}: {error}')
            result['traceback']=traceback.format_exc()
        finally:
            if reserved:
                ctypes.windll.user32.UnregisterHotKey(None,0x4B31)
            for process in (app_process,other_process):
                if process is not None and process.poll() is None:
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        result['defects'].append('Review process failed to terminate')
            log.close()
            result['passed']=result['passed'] and not result['defects']
            (args.output/'mini-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'checks':result['checks'],'defects':result['defects']}))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
