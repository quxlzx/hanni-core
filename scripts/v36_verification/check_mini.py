"""Actual native Mini/window bridge checks; no assistant request is submitted."""
from __future__ import annotations
import argparse
import ctypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v36_verification'))
from check_native import frame_capture
sys.path.insert(0,str(ROOT/'scripts/desktop_review'))
from capture_native import wait_window
import win32api
import win32con
import win32gui
from playwright.sync_api import sync_playwright,expect

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();origin=args.url.rstrip('/');output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));debug=sock.getsockname()[1]
    result={'checks':[],'frames':[],'errors':[],'javascript_errors':[],
            'disclosure':__doc__,'model_requests':0,'native_preference_only_writes':[]}
    def check(name,passed):
        result['checks'].append({'name':name,'passed':bool(passed)})
        if not passed:result['errors'].append(name)
    title='HANNI OS V3.6 Independent Mini Review';process=None;hwnd=None
    log=(output/'native-launch.log').open('w',encoding='utf8')
    try:
        process=subprocess.Popen([str(ROOT/'dist/HANNI OS/HANNI OS.exe'),'--url',origin,'--attach-only',
            '--state-dir',str(output/'native-state'),'--debug-port',str(debug),'--title',title],stdout=log,stderr=subprocess.STDOUT)
        hwnd=wait_window(title)
        with sync_playwright() as pw:
            browser=None
            for _ in range(100):
                try:browser=pw.chromium.connect_over_cdp(f'http://127.0.0.1:{debug}',timeout=1000);break
                except Exception:time.sleep(.1)
            if browser is None:raise RuntimeError('Native CDP unavailable')
            page=mini=None
            for _ in range(200):
                pages=[p for c in browser.contexts for p in c.pages]
                page=next((p for p in pages if p.url.startswith(origin) and 'view=mini' not in p.url),None)
                mini=next((p for p in pages if p.url.startswith(origin) and 'view=mini' in p.url),None)
                if page and mini:break
                if pages:pages[0].wait_for_timeout(100)
                else:browser.new_browser_cdp_session().send('Target.getTargets')
            if not mini:raise RuntimeError('Native Mini page unavailable')
            mini.on('pageerror',lambda exc:result['javascript_errors'].append(str(exc)))
            for _ in range(100):
                ready=mini.evaluate('Boolean(window.pywebview?.api?.get_state)')
                if ready:break
                mini.wait_for_timeout(100)
            if not ready:raise RuntimeError('Native Mini bridge missing')
            state=mini.evaluate('async()=>await window.pywebview.api.get_state()')
            result['initial_window_state']=state
            check('Actual native bridge reports a registered global shortcut',bool(state.get('shortcut')) and not state.get('error'))
            if state.get('shortcut')!='Ctrl+Shift+Space':raise RuntimeError('Unexpected owned default accelerator; refusing arbitrary keys')
            win32gui.SetForegroundWindow(hwnd)
            for key in [win32con.VK_CONTROL,win32con.VK_SHIFT,win32con.VK_SPACE]:win32api.keybd_event(key,0,0,0)
            for key in [win32con.VK_SPACE,win32con.VK_SHIFT,win32con.VK_CONTROL]:win32api.keybd_event(key,0,win32con.KEYEVENTF_KEYUP,0)
            mini_hwnd=wait_window('HANNI Mini')
            for _ in range(80):
                if win32gui.IsWindowVisible(mini_hwnd):break
                mini.wait_for_timeout(100)
            check('Registered global shortcut opens actual Mini window',bool(win32gui.IsWindowVisible(mini_hwnd)))
            expect(mini.locator('textarea')).to_be_visible(timeout=10000)
            for width,height in [(640,460),(520,380),(420,320),(900,650)]:
                win32gui.SetWindowPos(mini_hwnd,win32con.HWND_TOP,0,0,width,height,0)
                mini.wait_for_timeout(250)
                result['frames'].append(frame_capture(mini_hwnd,output/f'mini-{width}x{height}-native.png'))
                layout=mini.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})')
                check(f'Mini {width} no horizontal overflow',layout['scrollWidth']<=layout['width']+1)
            mini.get_by_role('button',name='Pin',exact=True).click()
            mini.wait_for_timeout(200)
            check('Mini actual pin preference persists',mini.evaluate('async()=>await window.pywebview.api.get_state()')['pinned'] is True)
            mini.get_by_role('button',name='Pinned',exact=True).click()
            mini.get_by_role('button',name='Shortcut',exact=True).click()
            expect(mini.get_by_role('region',name='Mini preferences')).to_be_visible()
            result['frames'].append(frame_capture(mini_hwnd,output/'mini-shortcut-native.png'))
            check('Mini shortcut UI reflects actual registration',mini.get_by_label('Global shortcut').input_value()=='Ctrl+Shift+Space')
            mini.get_by_role('button',name='Shortcut',exact=True).click()
            mini.locator('textarea').fill('/file.read')
            expect(mini.get_by_role('region',name='Registered file and app tools')).to_be_visible()
            check('Mini slash search uses current registered tools','file.read' in mini.inner_text('body').lower())
            result['frames'].append(frame_capture(mini_hwnd,output/'mini-capability-search-native.png'))
            mini.locator('textarea').fill('')
            mini.keyboard.press('Escape');mini.wait_for_timeout(250)
            check('Escape dismisses actual Mini window',not win32gui.IsWindowVisible(mini_hwnd))
            result['native_preference_only_writes']=['mini_pinned toggled true then false under owned temporary native state']
            browser.close()
    except Exception as exc:result['errors'].append(f'{type(exc).__name__}: {exc}')
    finally:
        if process and process.poll() is None:
            try:
                if hwnd:win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
                process.wait(timeout=15)
            except Exception:process.terminate();process.wait(timeout=10)
        log.close();check('Owned Mini/full desktop process closed',process is not None and process.poll() is not None)
        check('No Mini JavaScript errors',not result['javascript_errors'])
        result['passed']=not result['errors']
        (output/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='utf8')
        print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'frames':len(result['frames']),'errors':result['errors']}))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
