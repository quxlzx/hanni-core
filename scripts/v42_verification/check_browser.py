"""Independent Edge review of real UI assets with explicitly synthetic telemetry.

No display fixture is a model benchmark, GPU observation, or response-quality proof.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/desktop_review')]
from phase_fixture import PhaseReviewFixture
from hanni.reliability.execution import close_service
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    result={'display_fixture':True,'headless':True,'browser':'Microsoft Edge','native_app_reviewed':False,
            'disclosure':__doc__,'checks':[],'javascript_errors':[],'external_requests':[],'screenshots':[],
            'visual_score':None,'assets_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [ROOT/'src/hanni/dashboard/static/app.js',ROOT/'src/hanni/dashboard/static/style.css',ROOT/'frontend/src/model_performance.tsx']}}
    fixture=PhaseReviewFixture();fixture.__enter__()
    try:
        rich=deepcopy(fixture.server.model_routing.snapshot());now=time.time()
        original=rich['endpoints'][0]
        rows=[]
        for i,label in enumerate(('Local 4B (display fixture)','P6000 (display fixture)','P40 (display fixture)','Strata (display fixture)')):
            row=deepcopy(original)
            row.update(endpoint_id='local:supervisor' if i==0 else 'worker:display_'+str(i),label=label,
                local=i==0,enabled=True,health='healthy' if i!=2 else 'unhealthy',legacy_default=i==0,
                model_id='Synthetic display model '+str(i),configured_model='Synthetic display model '+str(i),
                last_heartbeat=now if i!=2 else now-3600,resource_sampled_at=now-300 if i<2 else None,max_context_verified=[16384,32768,None,8192][i],
                current_requests=0 if i!=1 else 1,queue_depth=None if i==2 else 0,
                ram_available_bytes=None if i==2 else 8*1024**3,vram_free_bytes=None if i==2 else 3*1024**3,
                profiles={},blocked_reasons=['display_fixture_unknown_resources'] if i==2 else [])
            history=[{'sampled_at':now-60*(40-j),'latency_ms':200+j*17 if j!=30 else None,
                    'ttft_ms':80+j,'generation_tps':75,'prompt_tps':1000,'queue_ms':0,'error':j==34} for j in range(40)]
            perf={'sample_count':40,'recent_failures':1,'window_seconds':3600,'last_latency_ms':863,
                'p50_latency_ms':531,'p95_latency_ms':830,'ttft_ms':119,'generation_tps':75,'prompt_tps':1000,
                'queue_ms':0,'history':history,'last_sampled_at':now-120,'last_verified_success':None}
            if i==1:
                perf.update(sample_count=1,recent_failures=0,history=[history[-1]],ttft_ms=None,prompt_tps=None)
            if i>=2:
                perf.update(sample_count=0,recent_failures=0,history=[],last_latency_ms=None,
                    p50_latency_ms=None,p95_latency_ms=None,ttft_ms=None,generation_tps=None,prompt_tps=None,queue_ms=None)
            row['performance']=perf
            row['gpu_measurement']=None if i>=2 else {'vram_total_bytes':8*1024**3,'vram_free_bytes':3*1024**3,
                'utilization_percent':37,'sampled_at':now,'last_sampled_at':now}
            rows.append(row)
        rich.update(endpoints=rows,decisions=[],controller_attached=False,reason='Synthetic performance display only; no model work executes in this review.')
        state={'outage':False}
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':900})
            page.on('pageerror',lambda error:result['javascript_errors'].append(str(error)))
            page.on('request',lambda req:result['external_requests'].append(req.url) if req.url.startswith(('http:','https:')) and not req.url.startswith(fixture.url) else None)
            def display(route):
                if route.request.method!='GET':route.continue_();return
                if state['outage']:
                    route.fulfill(status=503,content_type='application/json',body='{"error":"Controlled preview connection failed"}');return
                route.fulfill(status=200,content_type='application/json',body=json.dumps(rich))
            page.route('**/api/model-routing**',display)
            page.goto(fixture.url+'#model-routing',wait_until='domcontentloaded')
            expect(page.locator('.routing-performance')).to_have_count(4)
            for width,height in [(1440,900),(900,650),(640,700)]:
                page.set_viewport_size({'width':width,'height':height})
                first=page.locator('.routing-performance').first;first.scroll_into_view_if_needed()
                name=f'performance-{width}x{height}.png';page.screenshot(path=str(output/name),full_page=True)
                result['screenshots'].append(name)
                result['checks'].append({'name':f'No document horizontal overflow at {width}','passed':not page.evaluate('document.documentElement.scrollWidth > innerWidth')})
            first=page.locator('.routing-performance').first
            result['checks'].append({'name':'Bounded history excludes records before latest32','passed':'Last 31' in first.inner_text() or 'Last 32' in first.inner_text()})
            geometry=first.locator('.routing-history-line').get_attribute('d') or ''
            result['checks'].append({'name':'Unknown history gaps are not connected as observations','passed':geometry.count('M')==2 and first.locator('.routing-history-sample,.routing-history-failure').count()==31})
            result['checks'].append({'name':'Measured failure marker present','passed':first.locator('.routing-history-failure').count()==1})
            result['checks'].append({'name':'Independent GPU and response sample timestamps retain separate ages','passed':'Last response sample: 1 min ago' in first.inner_text() and 'GPU sample age: 5 min ago' in first.inner_text()})
            second=page.locator('.routing-performance').nth(1)
            result['checks'].append({'name':'Single observation has explicit history wait and unknown TTFT','passed':second.get_by_text('History appears after two recorded response times.',exact=True).count()==1 and 'Not measured' in second.inner_text()})
            unknown=page.locator('.routing-performance').nth(2)
            result['checks'].append({'name':'Unavailable zero-sample endpoint retains unknowns and no fake failure count','passed':'No recent performance measurements' in unknown.inner_text() and 'Failures not measured' in unknown.inner_text() and 'Not measured' in unknown.inner_text()})
            result['checks'].append({'name':'Health stale status disclosed','passed':'Historical samples; endpoint health is not current' in unknown.inner_text()})
            result['checks'].append({'name':'Response order or sample-time semantics labeled','passed':'order' in first.inner_text().lower() or 'time' in first.inner_text().lower() or 'samples' in first.inner_text().lower()})
            page.set_viewport_size({'width':1440,'height':900});unknown.scroll_into_view_if_needed()
            page.screenshot(path=str(output/'performance-unknown.png'),full_page=True)
            state['outage']=True
            expect(page.get_by_role('alert').filter(has_text='Controlled preview connection failed')).to_be_visible(timeout=10000)
            result['checks'].append({'name':'Transport outage retains previous measurements and disables policy writes','passed':page.locator('.routing-performance').count()==4 and page.get_by_role('button',name='Apply policy',exact=True).is_disabled()})
            result['checks'].append({'name':'Each retained panel explicitly marks refresh-failed performance stale','passed':all('Displayed performance may be stale; refresh failed' in text for text in page.locator('.routing-performance').all_inner_texts()) and page.get_by_text('Last recorded health',exact=True).count()==4})
            page.screenshot(path=str(output/'performance-stale-error.png'),full_page=True)
            state['outage']=False;page.get_by_role('button',name='Retry loading',exact=True).click()
            expect(page.get_by_role('alert').filter(has_text='Controlled preview connection failed')).to_have_count(0)
            rich['endpoints']=[]
            page.reload(wait_until='domcontentloaded');expect(page.get_by_text('No inference endpoints available',exact=True)).to_be_visible()
            result['checks'].append({'name':'No endpoint empty state is explicit','passed':True})
            page.screenshot(path=str(output/'performance-empty.png'),full_page=True)
            result['font_family']=page.locator('body').evaluate('el=>getComputedStyle(el).fontFamily')
            result['checks'].append({'name':'Geist font preserved without external requests','passed':'Geist' in result['font_family'] and not result['external_requests']})
            result['checks'].append({'name':'No browser JavaScript errors','passed':not result['javascript_errors']})
            browser.close()
    finally:
        fixture.server.shutdown();fixture.server.server_close();fixture.thread.join(3)
        close_service(fixture.config.paths.data_dir)
        fixture.hub.close();fixture.hub.db.close();fixture.temporary.cleanup()
        (output/'results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
