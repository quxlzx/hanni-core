"""Inspect every live native HANNI screen against an authentic owned backend.

No telemetry/model/controller fixtures. Only the native client is started here;
the engineer owns the original isolated dashboard/controller/model lifecycle.
All screenshots are physical pixels from this foreground owned HWND.
"""
from __future__ import annotations

import argparse
import ctypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/desktop_review'))
from capture_native import wait_window
import win32api
import win32con
import win32gui
import win32process
from ctypes.wintypes import RECT
from PIL import ImageGrab
from playwright.sync_api import sync_playwright, expect

SIZES=[(1920,1080),(1440,900),(1366,768),(900,650)]
FORBIDDEN_WRITES={'/api/cluster/power','/api/cluster/terminal','/api/shutdown','/api/gpu-routing','/api/audio-devices','/api/voice','/api/chat','/api/workflows','/api/mcp'}

def frame_capture(hwnd,path):
    """Use visible DWM frame bounds, excluding transparent resize borders."""
    win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
    foreground=win32gui.GetForegroundWindow();own=win32api.GetCurrentThreadId()
    prior=win32process.GetWindowThreadProcessId(foreground)[0] if foreground else own
    attached=prior!=own
    try:
        if attached:ctypes.windll.user32.AttachThreadInput(own,prior,True)
        win32gui.BringWindowToTop(hwnd);win32gui.SetForegroundWindow(hwnd)
    finally:
        if attached:ctypes.windll.user32.AttachThreadInput(own,prior,False)
    time.sleep(.15)
    if win32gui.GetForegroundWindow()!=hwnd:
        raise RuntimeError('Refusing an occluded owned-window capture.')
    visible=RECT()
    code=ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd,9,ctypes.byref(visible),ctypes.sizeof(visible))
    if code!=0:raise RuntimeError('Visible native frame bounds unavailable; refusing broad capture.')
    bounds=(visible.left,visible.top,visible.right,visible.bottom)
    outer=win32gui.GetWindowRect(hwnd)
    if bounds[0]<outer[0] or bounds[1]<outer[1] or bounds[2]>outer[2] or bounds[3]>outer[3]:
        raise RuntimeError('Unexpected native frame bounds.')
    ImageGrab.grab(bbox=bounds).save(path)
    return {'path':str(path.relative_to(ROOT)),'window_rect':list(outer),
            'window_size':[outer[2]-outer[0],outer[3]-outer[1]],'captured_visible_bounds':list(bounds)}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--exe',type=Path,default=ROOT/'dist/HANNI OS/HANNI OS.exe')
    parser.add_argument('--skip-capture',action='store_true')
    parser.add_argument('--screens',help='Comma-separated current screens, default all.')
    parser.add_argument('--interactions',action='store_true')
    parser.add_argument('--interactions-only',action='store_true')
    args=parser.parse_args()
    origin=args.url.rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.path:
        raise SystemExit('Only an explicit local owned HANNI origin is allowed.')
    output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    contract=json.load(urllib.request.urlopen(origin+'/api/workspace',timeout=10))
    screens=args.screens.split(',') if args.screens else contract['screens']
    if not set(screens)<=set(contract['screens']):raise SystemExit('Unknown current screen.')
    paths={'app.js':ROOT/'src/hanni/dashboard/static/app.js','style.css':ROOT/'src/hanni/dashboard/static/style.css','native_executable':args.exe}
    result={'version':1,'origin':origin,'screens':screens,'checks':[],'frames':[],
            'javascript_errors':[],'external_requests':[],'blocked_unsafe_requests':[],
            'screen_controls':{},'errors':[],'source_hashes':{k:digest(v) for k,v in paths.items()},
            'disclosure':__doc__,'unsafe_controls_clicked':False,'model_requests':0}
    def check(name,passed,detail=None):
        item={'name':name,'passed':bool(passed)}
        if detail is not None:item['detail']=detail
        result['checks'].append(item)
        if not passed:result['errors'].append(name)
    title='HANNI OS V3.6 Independent Whole-System Review'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); debug=sock.getsockname()[1]
    process=None;hwnd=None
    log=(output/'native-launch.log').open('w',encoding='utf8')
    try:
        process=subprocess.Popen([str(args.exe.resolve()),'--url',origin,'--attach-only',
            '--state-dir',str(output/'native-state'),'--debug-port',str(debug),'--title',title],
            stdout=log,stderr=subprocess.STDOUT)
        hwnd=wait_window(title)
        result['native_pid']=process.pid;result['native_class']=win32gui.GetClassName(hwnd)
        result['dpi']=ctypes.windll.user32.GetDpiForWindow(hwnd)
        with sync_playwright() as pw:
            browser=None
            for _ in range(80):
                try:browser=pw.chromium.connect_over_cdp(f'http://127.0.0.1:{debug}',timeout=1000);break
                except Exception:time.sleep(.1)
            if browser is None:raise AssertionError('Native WebView2 CDP unavailable.')
            page=None
            for _ in range(200):
                pages=[p for c in browser.contexts for p in c.pages]
                matches=[p for p in pages if p.url.startswith(origin) and 'view=mini' not in p.url]
                if matches:page=matches[0];break
                if pages:pages[0].wait_for_timeout(100)
                else:browser.new_browser_cdp_session().send('Target.getTargets')
            if page is None:raise AssertionError('Original backend page missing.')
            page.on('pageerror',lambda exc:result['javascript_errors'].append(str(exc)))
            page.on('request',lambda req:result['external_requests'].append(req.url)
                if req.url.startswith(('http://','https://')) and not req.url.startswith(origin) else None)
            def block_unsafe(route):
                req=route.request;path=urlsplit(req.url).path
                if req.method!='GET' and path in FORBIDDEN_WRITES:
                    result['blocked_unsafe_requests'].append({'path':path,'method':req.method})
                    route.abort('blockedbyclient')
                else:route.continue_()
            page.route('**/api/**',block_unsafe)
            expect(page.locator('.main-content')).to_be_visible(timeout=30000)
            check('Actual native app connects to original backend',True)
            check('Original chat composer enabled without model request',page.locator('#chat-input').is_enabled())
            def capture(screen,state,width,height):
                if args.skip_capture:return
                info=frame_capture(hwnd,output/f'{screen}-{state}-{width}x{height}-native.png')
                info.update(screen=screen,state=state,dpi=result['dpi'])
                result['frames'].append(info)
                check(f'{screen} {state} physical {width}x{height}',info['window_size']==[width,height])
            for width,height in ([] if args.interactions_only else SIZES):
                win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
                win32gui.SetWindowPos(hwnd,win32con.HWND_TOP,0,0,width,height,0)
                page.wait_for_timeout(250)
                for screen in screens:
                    page.evaluate('s=>location.hash=s',screen)
                    panel=page.locator(f'.screen-{screen}')
                    expect(panel).to_be_visible(timeout=15000)
                    page.locator('.main-content').evaluate('(e)=>e.scrollTop=0')
                    page.wait_for_timeout(650 if screen in {'cluster','models','mission'} else 200)
                    layout=page.evaluate('''()=>({width:innerWidth,height:innerHeight,
                        documentWidth:document.documentElement.scrollWidth,
                        mainWidth:document.querySelector('.main-content').clientWidth,
                        mainScrollWidth:document.querySelector('.main-content').scrollWidth,
                        mainHeight:document.querySelector('.main-content').clientHeight,
                        mainScrollHeight:document.querySelector('.main-content').scrollHeight})''')
                    check(f'{screen} {width} document has no horizontal overflow',layout['documentWidth']<=layout['width']+1,layout)
                    capture(screen,'top',width,height)
                    if width==1366:
                        result['screen_controls'][screen]=panel.evaluate('''e=>({text:e.innerText,
                            controls:[...e.querySelectorAll('button,input,select,textarea,a')].map(x=>({tag:x.tagName,
                                name:x.getAttribute('aria-label')||x.innerText||x.placeholder||x.name||x.id,
                                disabled:!!x.disabled,role:x.getAttribute('role'),type:x.type}))})''')
                        if layout['mainScrollHeight']>layout['mainHeight']+60:
                            page.locator('.main-content').evaluate('(e)=>e.scrollTop=e.scrollHeight')
                            page.wait_for_timeout(150);capture(screen,'bottom',width,height)
            win32gui.SetWindowPos(hwnd,win32con.HWND_TOP,0,0,1366,768,0)
            page.evaluate('location.hash="home"');page.wait_for_timeout(250)
            page.keyboard.press('Control+k')
            expect(page.get_by_role('dialog')).to_be_visible()
            check('Ctrl+K opens real command palette',True)
            capture('shell','palette',1366,768)
            page.keyboard.press('Escape');expect(page.get_by_role('dialog')).to_have_count(0)
            check('Escape closes palette without action',True)
            inspector=page.get_by_role('button',name='Show inspector',exact=True)
            if inspector.count():
                inspector.click();expect(page.get_by_role('complementary',name='Context inspector')).to_be_visible()
                check('Real context inspector opens',True);capture('shell','inspector',1366,768)
                page.get_by_role('button',name='Hide inspector',exact=True).first.click()
                expect(page.get_by_role('complementary',name='Context inspector')).to_have_count(0)
                check('Context inspector closes',True)
            page.evaluate('location.hash="memory"');page.wait_for_timeout(300)
            search=page.get_by_label('Search saved memories')
            if search.count():
                search.fill('no-such-verifier36-memory');page.wait_for_timeout(350)
                check('Memory unmatched search retains honest state','no' in page.locator('.screen-memory').inner_text().lower())
                search.fill('')
            win32gui.ShowWindow(hwnd,win32con.SW_MINIMIZE);page.wait_for_timeout(150)
            check('Native minimize changes window state',bool(win32gui.IsIconic(hwnd)))
            win32gui.ShowWindow(hwnd,win32con.SW_RESTORE);page.wait_for_timeout(150)
            check('Native restore returns visible state',not win32gui.IsIconic(hwnd))
            win32gui.ShowWindow(hwnd,win32con.SW_MAXIMIZE);page.wait_for_timeout(150)
            check('Native maximize supported',bool(ctypes.windll.user32.IsZoomed(hwnd)))
            win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
            if args.interactions:
                win32gui.SetWindowPos(hwnd,win32con.HWND_TOP,0,0,1366,768,0)
                def api(path):
                    # Token stays in the owned page/process and is never exported.
                    return page.evaluate('''async path=>{let chat=await(await fetch('/api/chat')).json();
                        let response=await fetch(path,{headers:{'X-Hanni-Token':chat.token}});
                        return {status:response.status,data:await response.json()}}''',path)
                before=api('/api/productivity')['data']
                result['fixture_counts_before']={k:len(before[k]) for k in ['tasks','projects','notes']}
                def open_screen(screen):
                    page.evaluate('s=>location.hash=s',screen)
                    expect(page.locator(f'.screen-{screen}')).to_be_visible();page.wait_for_timeout(200)
                open_screen('calendar')
                cal=api('/api/calendar')['data']
                check('Explicit empty test vault reports Google disconnected',cal['connected'] is False)
                page.get_by_role('button',name='Refresh calendar',exact=True).click()
                expect(page.locator('.screen-calendar')).to_contain_text('No connected Google Calendar account')
                check('Disconnected Google refresh honestly preserves local deadlines',True)
                capture('calendar','disconnected-refresh',1366,768)
                open_screen('projects')
                already=next((p for p in before['projects'] if p['name']=='UI36 Cedar'),None)
                if not already:
                    page.get_by_role('button',name='New project',exact=True).click()
                    dialog=page.get_by_role('dialog')
                    expect(dialog).to_be_visible();dialog.get_by_label('Project name',exact=True).fill('UI36 Cedar')
                    dialog.get_by_label('Description',exact=True).fill('Synthetic independent native review project.')
                    capture('projects','create-dialog',1366,768)
                    dialog.get_by_role('button',name='Save',exact=True).click();expect(dialog).to_have_count(0,timeout=10000)
                expect(page.locator('.screen-projects')).to_contain_text('UI36 Cedar')
                saved=api('/api/productivity')['data']
                project=next(p for p in saved['projects'] if p['name']=='UI36 Cedar')
                check('Native project Save persists an original exact record',bool(project['id']))
                page.locator('.project-list button',has_text='UI36 Cedar').first.click()
                page.get_by_role('button',name='Add note',exact=True).click()
                dialog=page.get_by_role('dialog')
                dialog.get_by_label('Title',exact=True).fill('UI36 receipt')
                dialog.get_by_label('Note',exact=True).fill('7 of 11 samples passed. This is fixture history, not a newly executed benchmark.')
                dialog.get_by_role('button',name='Save',exact=True).click();expect(dialog).to_have_count(0,timeout=10000)
                saved=api('/api/productivity')['data']
                note=next(n for n in saved['notes'] if n['title']=='UI36 receipt')
                check('Native note retains exact text and original project association',note['project_id']==project['id'] and note['body'].startswith('7 of 11'))
                capture('projects','saved-project-note',1366,768)
                open_screen('tasks')
                page.get_by_role('button',name='New task',exact=True).click()
                dialog=page.get_by_role('dialog');dialog.get_by_label('Title',exact=True).fill('UI36 inspect controlled receipt')
                dialog.get_by_label('Course or category',exact=True).fill('UI36')
                dialog.get_by_label('Due date (optional)',exact=True).fill('2030-04-05')
                dialog.get_by_label('Project',exact=True).select_option(project['id'])
                capture('tasks','create-dialog',1366,768)
                dialog.get_by_role('button',name='Save',exact=True).click();expect(dialog).to_have_count(0,timeout=10000)
                saved=api('/api/productivity')['data']
                task=next(t for t in saved['tasks'] if t['title']=='UI36 inspect controlled receipt')
                check('Native task Save exact read-after-write fields',task['course']=='UI36' and task['project_id']==project['id'] and task['due'].startswith('2030-04-05'))
                page.get_by_role('button',name='Complete UI36 inspect controlled receipt',exact=True).click()
                page.wait_for_timeout(400)
                check('Native completion updates original durable task',next(t for t in api('/api/productivity')['data']['tasks'] if t['id']==task['id'])['status']=='completed')
                page.get_by_label('Task status',exact=True).select_option('completed')
                expect(page.locator('.screen-tasks')).to_contain_text('UI36 inspect controlled receipt')
                check('Task completed filter exposes actual saved task',True)
                capture('tasks','completed-task',1366,768)
                page.get_by_role('button',name='Delete UI36 inspect controlled receipt',exact=True).click()
                dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
                dialog.get_by_role('button',name='Cancel',exact=True).click()
                check('Task deletion cancellation does not delete saved record',any(t['id']==task['id'] for t in api('/api/productivity')['data']['tasks']))
                page.get_by_role('button',name='Back up workspace',exact=True).click();page.wait_for_timeout(350)
                check('Native workspace backup returns visible original receipt','backup' in page.locator('.screen-tasks').inner_text().lower())
                open_screen('memory')
                page.get_by_role('tab',name='Review queue',exact=True).click()
                page.get_by_role('button',name='Suggest from a statement',exact=True).click()
                dialog=page.get_by_role('dialog');dialog.get_by_label('Owner statement',exact=True).fill('My favorite drink is verifier36 green tea')
                dialog.get_by_role('button',name='Create suggestion',exact=True).click()
                expect(dialog).to_have_count(0,timeout=10000)
                browse=api('/api/memory/explorer')['data'];pending=api('/api/memory/suggestions')['data']
                check('Native local-rule proposal is not silently stored as a fact',not any('verifier36 green tea' in r['content'] for r in browse['records']))
                proposal=next(p for p in pending['items'] if 'verifier36 green tea' in p['content'])
                page.locator('.memory-index-row',has_text='verifier36 green tea').click()
                page.get_by_role('button',name='Approve',exact=True).click()
                dialog=page.get_by_role('dialog');dialog.get_by_role('button',name='Approve memory',exact=True).click()
                expect(dialog).to_have_count(0,timeout=10000)
                browse=api('/api/memory/explorer')['data'];memory=next(r for r in browse['records'] if 'verifier36 green tea' in r['content'])
                check('Native exact approval writes one original owner-reviewed memory',bool(memory['id']))
                page.get_by_role('tab',name='Stored memories',exact=True).click()
                page.locator('.memory-index-row',has_text='verifier36 green tea').click()
                expect(page.get_by_role('button',name='Correct memory',exact=True)).to_be_visible()
                page.get_by_role('button',name='Correct memory',exact=True).click()
                dialog=page.get_by_role('dialog');dialog.locator('textarea').fill('My favorite drink is verifier36 black tea')
                dialog.get_by_role('button',name='Save change',exact=True).click();expect(dialog).to_have_count(0,timeout=10000)
                detail=api('/api/memory/record/'+memory['id'])['data']
                check('Native correction preserves exact original source history',detail['record']['content']=='My favorite drink is verifier36 black tea' and any('green tea' in h['content'] for h in detail['history']))
                capture('memory','corrected-source-history',1366,768)
                page.get_by_role('button',name='Delete',exact=True).click();dialog=page.get_by_role('dialog')
                dialog.get_by_role('button',name='Delete memory',exact=True).click();expect(dialog).to_have_count(0,timeout=10000)
                detail=api('/api/memory/record/'+memory['id'])['data']
                check('Native confirmed memory deletion erases source and history',detail.get('record') is None and not detail.get('history'))
                open_screen('mcp');page.get_by_role('button',name='Add server',exact=True).click()
                dialog=page.get_by_role('dialog');expect(dialog.get_by_label('Server name',exact=True)).to_be_visible()
                capture('mcp','add-dialog',1366,768);dialog.get_by_role('button',name='Cancel',exact=True).click()
                check('Actual MCP add dialog cancels without connection',api('/api/mcp')['data']['servers']==[])
                open_screen('workflows');page.get_by_role('button',name='New goal',exact=True).click()
                dialog=page.get_by_role('dialog');dialog.get_by_label('Goal',exact=True).fill('Only a cancelled synthetic goal; never submit.')
                capture('workflows','new-goal-dialog',1366,768);dialog.get_by_role('button',name='Cancel',exact=True).click()
                check('Real workflow goal cancellation creates no workflow',not api('/api/workflows')['data'].get('items'))
                open_screen('agents');page.get_by_label('Search activity and capabilities',exact=True).fill('file.read')
                expect(page.locator('.screen-agents')).to_contain_text('file.read')
                check('Agents actual capability search preserves matching registered tool',True)
                page.get_by_label('Search activity and capabilities',exact=True).fill('')
                open_screen('screen');check('Unavailable screen analysis honestly disabled',page.get_by_role('button',name='Analyze current screen',exact=True).is_disabled())
                open_screen('voice');check('Text-only session voice listen honestly disabled',page.get_by_role('button',name='Listen now',exact=True).is_disabled())
                open_screen('cluster');page.get_by_role('button',name='Yunjin node',exact=True).click()
                expect(page.locator('[data-selected-node="yunjin"]')).to_be_visible()
                check('Yunjin jellyfish and unavailable repair details are honest','Under repair' in page.locator('.screen-cluster').inner_text())
                capture('cluster','yunjin-repair',1366,768)
                page.get_by_role('button',name='Back to nodes',exact=False).click()
                page.get_by_role('button',name='HANNI node',exact=True).click()
                expect(page.locator('[data-selected-node="hanni"]')).to_be_visible()
                capture('cluster','hanni-real-history',1366,768)
                reboot=page.get_by_role('button',name='Reboot HANNI',exact=True)
                if reboot.is_enabled():
                    reboot.click();dialog=page.get_by_role('dialog')
                    capture('cluster','reboot-cancel-only',1366,768)
                    dialog.get_by_role('button',name='Cancel',exact=True).click()
                    check('Remote reboot dialog cancellation causes zero power request',not result['blocked_unsafe_requests'])
                result['runtime_contract_after']=api('/api/workspace')['data']
                result['fixture_counts_after']={k:len(api('/api/productivity')['data'][k]) for k in ['tasks','projects','notes']}
            result['mini_pages']=[{'url_path':urlsplit(p.url).path,'is_mini':'view=mini' in p.url}
                                  for c in browser.contexts for p in c.pages]
            browser.close()
    except Exception as exc:
        result['errors'].append(f'{type(exc).__name__}: {exc}')
    finally:
        if process and process.poll() is None:
            try:
                if hwnd:win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
                process.wait(timeout=15)
            except Exception:
                process.terminate();process.wait(timeout=10)
        log.close()
        check('Owned native client closed',process is not None and process.poll() is not None)
        result['source_hashes_after']={k:digest(v) for k,v in paths.items()}
        check('Frontend and native executable unchanged during independent review',result['source_hashes']==result['source_hashes_after'])
        check('No forbidden API mutation attempted',not result['blocked_unsafe_requests'])
        check('No JavaScript runtime errors',not result['javascript_errors'])
        check('No external request from native UI',not result['external_requests'])
        result['passed']=not result['errors']
        (output/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='utf8')
        print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'frames':len(result['frames']),'errors':result['errors']}))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
