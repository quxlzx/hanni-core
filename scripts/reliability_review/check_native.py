"""Independent original-server Activity review; screenshots are Win32 pixels.

Telemetry is synthetic and inactive. Registry time/system/file handlers are real;
custom receipt/timeout handlers and endpoint outages are disclosed test seams.
No live model, provider, voice, SSH, or remote power action runs.
"""
from __future__ import annotations
import ctypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/desktop_review'))
from fixture import ReviewFixture
from capture_native import SIZES, frame_capture, wait_window
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
from hanni.reliability.context import request_scope
from hanni.reliability.execution import ReliabilityService
from hanni.tools.session import ToolAwareSession

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def runtime_manifest():
    """Hash real runtime/config bytes, never read evaluation or sealed cases."""
    files=list((ROOT/'src/hanni').rglob('*.py'))
    files.extend(path for path in (ROOT/'config').rglob('*') if path.is_file() and path.suffix in {'.yaml','.yml','.json','.toml'})
    entries={str(path.relative_to(ROOT)).replace('\\','/'):digest(path) for path in sorted(files)}
    encoded=json.dumps(entries,sort_keys=True,separators=(',',':')).encode()
    return {'sha256':hashlib.sha256(encoded).hexdigest(),'files':entries,
            'scope':'All src/hanni Python runtime (including cli.py) and repository YAML/JSON/TOML config; no evaluation/private holdout files.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--exe',type=Path,default=ROOT/'dist/HANNI OS/HANNI OS.exe')
    args=parser.parse_args(); output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    paths={'exe':args.exe,'app.js':ROOT/'src/hanni/dashboard/static/app.js',
           'style.css':ROOT/'src/hanni/dashboard/static/style.css',
           'execution.py':ROOT/'src/hanni/reliability/execution.py',
           'base.py':ROOT/'src/hanni/tools/base.py','files.py':ROOT/'src/hanni/tools/files.py'}
    result={'passed':False,'checks':[],'screenshots':[],'errors':[], 'javascript_errors':[],
            'artifact_sha256':{name:digest(path) for name,path in paths.items()},
            'runtime_manifest':runtime_manifest(),
            'disclosure':__doc__,'production_actions':[],'controlled_seams':[
                'HTTP 503 after original private-token gate, for first-fetch/stale UI checks',
                'custom.action_receipt and custom.timeout registry handlers',
                'GeneratorExit in actual service.task for cancellation',
                'synthetic inactive telemetry outside real execution records']}
    process=None
    with ReviewFixture() as fixture:
        fixture.sample['activity']={'input_level':0,'speaking':False,'microphone_active':False}
        registry=fixture.server.features.registry; service=registry.context.reliability
        fixture.trace_outage=True
        original=fixture.server.RequestHandlerClass
        class AvailabilityHandler(original):
            def do_GET(self):
                if self.path.split('?',1)[0]=='/api/executions' and fixture.trace_outage:
                    if not self._allowed():return
                    if self.headers.get('X-Hanni-Token') != fixture.hub.token:
                        return self._send(403,b'{"error":"Dashboard token required"}')
                    return self._send(503,b'{"error":"Controlled execution endpoint unavailable"}')
                return super().do_GET()
        fixture.server.RequestHandlerClass=AvailabilityHandler
        def api(token):
            req=urllib.request.Request(fixture.url+'api/executions',headers={'X-Hanni-Token':token})
            try:
                with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as error:return error.code,None
        def check(name,passed):
            result['checks'].append({'name':name,'passed':bool(passed)})
            if not passed:result['errors'].append(name)
        check('No-token execution GET rejected before outage seam',api('')[0]==403)
        check('Incorrect-token execution GET rejected',api('wrong-independent-token')[0]==403)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        title='HANNI OS Independent Reliability Review'
        log=(output/'native-launch.log').open('w',encoding='utf8')
        try:
            process=subprocess.Popen([str(args.exe.resolve()),'--url',fixture.url,'--attach-only',
                '--state-dir',str(output/'native-state'),'--debug-port',str(port),'--title',title],
                stdout=log,stderr=subprocess.STDOUT)
            hwnd=wait_window(title)
            with sync_playwright() as playwright:
                browser=None
                for _ in range(100):
                    try:browser=playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=1000);break
                    except Exception:time.sleep(.1)
                if browser is None:raise AssertionError('Native CDP unavailable')
                page=None
                for _ in range(300):
                    pages=[p for c in browser.contexts for p in c.pages]
                    matches=[p for p in pages if p.url.startswith(fixture.url) and '?view=mini' not in p.url]
                    if matches:page=matches[0];break
                    if pages:pages[0].wait_for_timeout(100)
                    else:browser.new_browser_cdp_session().send('Target.getTargets')
                if page is None:raise AssertionError('Actual native backend page unavailable')
                page.on('pageerror',lambda error:result['javascript_errors'].append(str(error)))
                page.evaluate('location.hash="activity"')
                panel=page.locator('.execution-traces')
                expect(panel).to_be_visible(timeout=30000)
                def capture(state,sizes=SIZES,target=None):
                    for width,height in sizes:
                        win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
                        win32gui.SetWindowPos(hwnd,0,0,0,width,height,win32con.SWP_NOZORDER)
                        page.wait_for_timeout(250)
                        if target:target.evaluate('(e)=>e.scrollIntoView({block:"start"})')
                        else:page.locator('.main-content').evaluate('(e)=>e.scrollTop=0')
                        page.wait_for_timeout(120)
                        meta=frame_capture(hwnd,output/f'{state}-{width}x{height}-native.png')
                        meta.update(state=state,dpi=ctypes.windll.user32.GetDpiForWindow(hwnd),
                            layout=page.evaluate('({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth})'),
                            text=panel.inner_text())
                        result['screenshots'].append(meta)
                        check(f'{state} actual {width}x{height} frame',meta['window_size']==[width,height])
                        check(f'{state} {width}x{height} no document overflow',meta['layout']['scroll']<=meta['layout']['width']+1)
                    win32gui.SetWindowPos(hwnd,0,0,0,1920,1080,win32con.SWP_NOZORDER)
                    page.wait_for_timeout(100)
                expect(panel.locator('.feature-error')).to_be_visible(timeout=15000)
                capture('initial-fetch-error')
                check('First-fetch error does not assert empty trace history',
                    'No task traces recorded yet.' not in panel.inner_text())
                fixture.trace_outage=False
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel.locator('.feature-error')).to_have_count(0,timeout=15000)
                expect(panel).to_contain_text('No task traces recorded yet.')
                capture('empty')
                service.error=True
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel).to_contain_text('Execution trace storage is unavailable',timeout=15000)
                capture('initial-storage-unavailable')
                check('Unavailable storage does not assert empty history',
                    'No task traces recorded yet.' not in panel.inner_text())
                service.error=False
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel.locator('.feature-error')).to_have_count(0,timeout=15000)
                for index in range(14):
                    with request_scope(uuid4(),'dashboard'):
                        registry.execute(ToolRequest('time.now' if index%2 else 'system.stats'))
                try:
                    registry.execute(ToolRequest('file.write',{'path':str(Path(fixture.temporary.name)/'must-not-exist.txt'),'text':'blocked'},actor_profile='everyone_else',confirmed=True))
                except Exception as error:result['denial_class']=type(error).__name__
                try:
                    with service.task('dashboard'):raise GeneratorExit()
                except GeneratorExit:pass
                registry.register(ToolDefinition('custom.timeout','Controlled timeout fixture.',0,0,{}, {},
                    lambda *args:ToolResult('custom.timeout',False,'Controlled timeout.',{},error={'code':'TIMEOUT','retryable':False}),side_effect='read'))
                registry.execute(ToolRequest('custom.timeout'))
                destination=Path(fixture.temporary.name)/'verified-native-review.txt'
                write=registry.execute(ToolRequest('file.write',{'path':str(destination),'text':'Independent native evidence\n'},confirmed=True))
                check('Real temp file write and independent content oracle',destination.read_text()=='Independent native evidence\n')
                result['file_write_verification']=write.verification
                registry.register(ToolDefinition('custom.action_receipt','Controlled unverified mutation receipt.',1,1,{}, {},
                    lambda *args:ToolResult('custom.action_receipt',True,'Receipt only.',{'received':True}),side_effect='reversible_write'))
                receipt=registry.execute(ToolRequest('custom.action_receipt',confirmed=True))
                check('Unknown mutation receipt remains unverified',receipt.verification['status']=='UNVERIFIED')
                check('Actual authenticated API returns recorded tasks',api(fixture.hub.token)[0]==200)
                result['recorded_tasks']=service.snapshot()
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel.locator('.trace-record')).to_have_count(19,timeout=20000)
                capture('recorded')
                record=panel.locator('.trace-record').filter(has=page.locator('summary strong',has_text='file.write')).first
                record.locator('summary').first.click();expect(record).to_have_attribute('open','')
                capture('expanded-file-evidence',target=record)
                capture('expanded-evidence-bottom',sizes=[(1366,768),(900,650)],target=record.locator('.trace-evidence').last)
                class Fallback:
                    def stream_response(self,*args,**kwargs):yield 'No action requested.'
                    def record_turn(self,*args,**kwargs):pass
                retained=Path(fixture.temporary.name)/'retained-after-restart.txt'
                retained.write_text('Keep this file.',encoding='utf8')
                assistant=ToolAwareSession(Fallback(),registry)
                ''.join(assistant._execute(ToolRequest('file.delete',{'path':str(retained)})))
                service.close()
                service=ReliabilityService(fixture.config.paths.data_dir)
                registry.context.reliability=service
                reloaded=service.snapshot()['tasks'][0]
                check('Actual restarted approval is inactive and cannot execute',
                    reloaded['execution_status']=='approval_unavailable' and reloaded['approval_active'] is False and retained.exists())
                ''.join(ToolAwareSession(Fallback(),registry).stream_response('yes'))
                check('Fresh session yes does not replay historical deletion',retained.read_text()=='Keep this file.')
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel.locator('.trace-record')).to_have_count(20,timeout=20000)
                capture('historical-approval')
                panel.get_by_label('Filter task execution outcome').select_option('rejected')
                expect(panel.locator('.trace-record')).to_have_count(1)
                capture('rejected-filter')
                panel.get_by_label('Search execution traces').fill('no-such-independent-record')
                expect(panel).to_contain_text('No task traces match this filter.')
                capture('no-filter-match')
                panel.get_by_label('Search execution traces').fill('')
                panel.get_by_label('Filter task execution outcome').select_option('all')
                fixture.trace_outage=True
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel).to_contain_text('Displayed traces may be stale.',timeout=15000)
                check('Unavailable refresh retains real loaded records',panel.locator('.trace-record').count()==20)
                capture('stale-refresh')
                fixture.trace_outage=False;service.error=True
                panel.get_by_role('button',name='Refresh task traces',exact=True).click()
                expect(panel).to_contain_text('Execution trace storage is unavailable',timeout=15000)
                capture('unavailable-storage')
                result['passed']=not result['errors'] and not result['javascript_errors']
                browser.close()
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
        finally:
            if process and process.poll() is None:
                try:win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0);process.wait(timeout=15)
                except Exception:process.terminate();process.wait(timeout=10)
            log.close();service.close()
            result['artifact_sha256_after']={name:digest(path) for name,path in paths.items()}
            result['runtime_manifest_after']=runtime_manifest()
            check('Runtime/config/frontend bytes remain frozen during native inspection',
                result['artifact_sha256']==result['artifact_sha256_after'] and
                result['runtime_manifest']['sha256']==result['runtime_manifest_after']['sha256'])
            result['passed']=result['passed'] and not result['errors'] and not result['javascript_errors']
            (output/'results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'passed':result['passed'],'frames':len(result['screenshots']),'checks':len(result['checks']),'errors':result['errors']}))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
