"""Once-only input collector for the owned native app; never opens oracles."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from desktop.main import request_json
from scripts.campaign8_native.session import NativeSession
from .validation import final_input_errors
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'data/campaign8-verifier/holdout'
GET_PATHS = frozenset({'/api/awareness', '/api/cluster', '/api/model-lab', '/api/model-routing', '/api/voice', '/api/workflows', '/api/mcp', '/api/calendar', '/api/state', '/api/workspace'})

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')

def freeze_manifest(directory):
    value = json.loads((Path(directory) / 'MANIFEST.json').read_text(encoding='utf8'))
    if not isinstance(value, dict) or not value:
        raise ValueError('Expected the complete path-to-SHA source manifest')
    for name, digest in value.items():
        target = (ROOT / name).resolve()
        if not target.is_relative_to(ROOT) or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('Invalid source manifest member')
    return value

def check_sources(manifest):
    changes = [name for name, digest in manifest.items() if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    if changes:
        raise RuntimeError('Frozen source changed: ' + ', '.join(changes[:5]))

def scrub(value):
    """Keep authoritative facts; never persist token/password/cookie fields."""
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.casefold() in {'token', 'password', 'secret', 'authorization', 'cookie', 'access_token', 'refresh_token', 'api_key'} else scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value

def process_identity(pid):
    import psutil
    process = psutil.Process(pid)
    return {'pid': process.pid, 'create_time': process.create_time(), 'parent_pid': process.ppid(), 'command_sha256': hashlib.sha256(json.dumps(process.cmdline(), ensure_ascii=False).encode()).hexdigest()}

def original_projection(backend, path):
    """Original private GET authorization; ephemeral token is never recorded."""
    if path not in GET_PATHS:
        raise ValueError('Unapproved GET projection path')
    if process_identity(backend['pid'])['create_time'] != backend['create_time']:
        raise RuntimeError('Original owned backend identity changed')
    token = request_json(backend['url'], '/api/chat?before=1', timeout=8).get('token')
    if not isinstance(token, str) or not 1 <= len(token) <= 512:
        raise RuntimeError('Original backend did not supply a valid authorization token')
    result = request_json(backend['url'], path, token=token, timeout=8)
    if process_identity(backend['pid'])['create_time'] != backend['create_time']:
        raise RuntimeError('Original owned backend identity changed')
    return scrub(result)

def owner_identity():
    """Whitelisted listening services only, with command hashes not command text."""
    import psutil
    identities = {}
    for connection in psutil.net_connections(kind='tcp'):
        if connection.status == psutil.CONN_LISTEN and connection.laddr.port in {8080, 8765} and connection.pid:
            row = process_identity(connection.pid)
            row['parent'] = process_identity(row['parent_pid']) if row['parent_pid'] else None
            identities[str(connection.laddr.port)] = row
    return identities
DOM_DETAILS = "() => {\n const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}};\n const visible=e=>{let s=getComputedStyle(e),r=e.getBoundingClientRect();return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};\n const main=document.querySelector('main')||document.querySelector('.mini-root')||document.body;\n const scroll=[...document.querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e);return visible(e)&&['auto','scroll'].includes(s.overflowY)&&e.scrollHeight>e.clientHeight+1});\n return {url:location.href,title:document.title,body_text:document.body.innerText,\n   primary:{tag:main.tagName,visible:visible(main),rect:rect(main),scrollHeight:main.scrollHeight,clientHeight:main.clientHeight},\n   root_overflow_px:Math.max(0,document.documentElement.scrollWidth-innerWidth),\n   viewport:{width:innerWidth,height:innerHeight,devicePixelRatio},\n   scroll_regions:scroll.map(e=>({tag:e.tagName,className:e.className,rect:rect(e),scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,scrollTop:e.scrollTop})),\n   fixed_regions:[...document.querySelectorAll('*')].filter(e=>visible(e)&&getComputedStyle(e).position==='fixed').map(e=>({tag:e.tagName,className:e.className,rect:rect(e)})),\n   headings:[...main.querySelectorAll('h1,h2,h3')].map(e=>({text:e.innerText,rect:rect(e),size:getComputedStyle(e).fontSize,weight:getComputedStyle(e).fontWeight,lineHeight:getComputedStyle(e).lineHeight})),\n   dialogs:[...document.querySelectorAll('dialog')].map(e=>({open:e.open,label:e.getAttribute('aria-label')||e.querySelector('h1,h2,h3')?.innerText,rect:rect(e)})),\n   focused:{tag:document.activeElement.tagName,id:document.activeElement.id,role:document.activeElement.getAttribute('role'),editable:document.activeElement.matches('input,textarea,[contenteditable=true]')},\n   controls:[...main.querySelectorAll('button,input,select,textarea,a')].map(e=>({tag:e.tagName,visible:visible(e),disabled:!!e.disabled,rect:rect(e),text:e.innerText,ariaLabel:e.getAttribute('aria-label'),title:e.getAttribute('title')}))};\n}"
PRIMARY_BOTTOM_SCROLL = "() => {\n const main=document.querySelector('main')||document.querySelector('.mini-root')||document.body;\n const eligible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return r.width>0&&r.height>0&&s.visibility!=='hidden'&&['auto','scroll'].includes(s.overflowY)&&e.scrollHeight>e.clientHeight+1&&e.clientHeight>100};\n let e=main;\n while(e&&!eligible(e))e=e.parentElement;\n if(!e)e=[...main.querySelectorAll('*')].filter(eligible).sort((a,b)=>b.clientWidth*b.clientHeight-a.clientWidth*a.clientHeight)[0];\n if(!e)return null;\n const before=e.scrollTop;e.scrollTop=e.scrollHeight;\n return {tag:e.tagName,className:e.className,scope:'primary content or its containing scroll region',before,after:e.scrollTop,max:e.scrollHeight-e.clientHeight};\n}"

def named_control(page, control):
    if not isinstance(control, dict) or set(control) - {'role', 'name', 'index'} or (not isinstance(control.get('role'), str)) or (not isinstance(control.get('name'), str)):
        raise ValueError('Use a bounded declared role/name control')
    index = control.get('index', 0)
    if type(index) is not int or not 0 <= index <= 20:
        raise ValueError('Invalid control index')
    return page.get_by_role(control['role'], name=control['name'], exact=True).nth(index)

def collect_case(case, session, backend):
    """Finite local actions + GET observations, independent of expected answers."""
    errors = final_input_errors(case)
    if errors:
        raise ValueError('; '.join(errors))
    started = time.monotonic()
    mini = case.get('surface') == 'mini'
    page = session.mini_page if mini else session.page
    window = session.mini if mini else session.main
    page.keyboard.press('Escape')
    size = case.get('viewport', {}).get('physical_window_size', [620, 640] if mini else [1366, 860])
    session.native('resize', mini=mini, size=size)
    if mini:
        session.native('show', mini=True)
    else:
        session.execute({'id': case['id'] + '-route', 'action': 'route', 'route': case['route']})
    before = session.window_state(window)
    before_dom = page.evaluate(DOM_DETAILS)
    request = case.get('request', {})
    op = case['operation']
    operation_result = None
    intermediate_captures = []
    if op == 'keyboard':
        keys = request.get('keys')
        if not isinstance(keys, list) or not keys or any((k not in {'Control+k', 'Escape', 'Tab', 'Shift+Tab'} for k in keys)):
            raise ValueError('Unsupported local keyboard sequence')
        states = []
        for key in keys:
            page.keyboard.press(key)
            page.wait_for_timeout(100)
            states.append(page.evaluate(DOM_DETAILS))
        operation_result = states
    elif op == 'fill_local':
        target = named_control(page, request.get('control'))
        value = request.get('value')
        if not isinstance(value, str) or len(value) > 4000:
            raise ValueError('Invalid local draft value')
        target.fill(value, timeout=3000)
        operation_result = {'value_readback': target.input_value()}
    elif op in {'open_dialog', 'close_dialog', 'click_local'}:
        target = named_control(page, request.get('control'))
        operation_result = {'visible_before': target.is_visible(), 'enabled_before': target.is_enabled()}
        if target.is_enabled():
            target.click(timeout=3000)
            page.wait_for_timeout(100)
            operation_result['after_click'] = page.evaluate(DOM_DETAILS)
        if op == 'close_dialog':
            named_control(page, request.get('close_control')).click(timeout=3000)
            page.wait_for_timeout(100)
    elif op == 'native_window':
        action = request.get('action')
        if action not in {'minimize_then_restore', 'maximize_then_restore', 'owned_mini_show_then_dismiss'}:
            raise ValueError('Unsupported owned-window action')
        if action == 'owned_mini_show_then_dismiss':
            visible = session.native('show', mini=True)
            intermediate_captures.append(session.capture(case['id'] + '-shown', mini=True))
            returned = session.execute({'id': case['id'] + '-dismiss', 'action': 'mini_bridge', 'view': 'mini', 'method': 'dismiss'})
            operation_result = {'shown': visible, 'dismiss_receipt': returned, 'after_dismiss': session.window_state(session.mini), 'scope': 'Original owned HWND/bridge adapter, not menu/tray/shortcut activation proof'}
        else:
            first = 'minimize' if action == 'minimize_then_restore' else 'maximize'
            intermediate = session.native(first)
            restored = session.native('restore')
            operation_result = {'intermediate': intermediate, 'restored': restored}
    elif op == 'read_projection':
        path = request.get('path')
        if path not in GET_PATHS:
            raise ValueError('Unapproved GET projection path')
        operation_result = {'path': path, 'original_api': original_projection(backend, path), 'authorization_scope': 'Original ephemeral token in memory only'}
    elif op != 'measure_layout':
        raise ValueError('Unsupported case operation')
    page.wait_for_timeout(100)
    observation = {'id': case['id'], 'family': case['family'], 'route': case['route'], 'surface': case['surface'], 'operation': op, 'evidence_class': 'CONTROLLED', 'before_window': before, 'after_window': session.window_state(window), 'before_dom': before_dom, 'after_dom': page.evaluate(DOM_DETAILS), 'operation_result': operation_result, 'original_dom_inventory': session.dom(mini=mini), 'platform_fonts': session.platform_fonts(mini=mini), 'screenshots': intermediate_captures, 'action_and_dom_ms': (time.monotonic() - started) * 1000, 'grading_performed': False, 'native_menu_or_tray_claim': False}
    cdp = page.context.new_cdp_session(page)
    try:
        observation['actual_accessibility_tree'] = cdp.send('Accessibility.getFullAXTree')
    finally:
        cdp.detach()
    observation['backend_process_identity_after'] = process_identity(backend['pid'])
    if observation['after_window']['visible'] and (not observation['after_window']['minimized']):
        observation['screenshots'].append(session.capture(case['id'], mini=mini))
    if op == 'measure_layout':
        scroll = page.evaluate(PRIMARY_BOTTOM_SCROLL)
        observation['bottom_scroll'] = scroll
        if scroll:
            page.wait_for_timeout(100)
            observation['bottom_dom'] = page.evaluate(DOM_DETAILS)
            observation['screenshots'].append(session.capture(case['id'] + '-bottom', mini=mini))
        page.evaluate("() => {for(const e of document.querySelectorAll('*')) if(e.scrollTop)e.scrollTop=0}")
    observation['elapsed_ms'] = (time.monotonic() - started) * 1000
    observation['elapsed_scope'] = 'Whole case actions, original API/DOM/AX observations and owned HWND captures; excludes native startup/teardown'
    return observation

def main():
    import argparse
    import psutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-out', type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT / 'data/campaign8-verifier') or output.exists():
        raise ValueError('Fresh private owned evidence directory required')
    manifest = freeze_manifest(args.freeze)
    check_sources(manifest)
    seal = json.loads((PRIVATE / 'SEAL.json').read_text(encoding='utf8'))
    for filename, key in (('inputs.json', 'input_sha256'), ('protocol.json', 'protocol_sha256')):
        if sha(PRIVATE / filename) != seal[key]:
            raise RuntimeError('Sealed input/protocol changed')
    inputs = json.loads((PRIVATE / 'inputs.json').read_text(encoding='utf8'))
    if len(inputs) != seal['case_count'] or any((final_input_errors(row) for row in inputs)):
        raise ValueError('Invalid sealed complete input set')
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if ready['evidence_class'] != 'CONTROLLED' or ready.get('model_generation') is not False:
        raise ValueError('Disposable original non-inference backend required')
    process = psutil.Process(ready['pid'])
    if process.create_time() != ready['create_time']:
        raise RuntimeError('Owned backend identity changed')
    request_json(ready['url'], '/api/workspace')
    claim = PRIVATE / 'CLAIM.json'
    with claim.open('x', encoding='utf8', newline='\n') as stream:
        json.dump({'at': datetime.now(timezone.utc).isoformat(), 'output': str(output), 'input_sha256': seal['input_sha256'], 'manifest_sha256': sha(args.freeze / 'MANIFEST.json'), 'case_count': len(inputs), 'no_retries': True}, stream, indent=2)
        stream.write('\n')
    output.mkdir()
    summary = {'started_at': datetime.now(timezone.utc).isoformat(), 'input_sha256': seal['input_sha256'], 'manifest_sha256': sha(args.freeze / 'MANIFEST.json'), 'source_member_count': len(manifest), 'backend_pid': ready['pid'], 'backend_create_time': ready['create_time'], 'case_count': len(inputs), 'attempted': 0, 'collected': 0, 'case_errors': 0, 'oracles_read': False, 'retries': 0, 'cases': [], 'complete': False}
    summary['python_cache_prefix'] = sys.pycache_prefix
    summary['interpreter'] = sys.executable
    summary['executor_sha256'] = sha(__file__)
    summary['owner_identity_before'] = owner_identity()
    write(output / 'PROGRESS.json', summary)
    failure = None
    try:
        with NativeSession(url=ready['url'], output=args.native_out, maximum_seconds=1200) as session:
            for case in inputs:
                check_sources(manifest)
                if psutil.Process(ready['pid']).create_time() != ready['create_time']:
                    raise RuntimeError('Original fixture backend identity changed')
                summary['attempted'] += 1
                start = time.monotonic()
                try:
                    row = collect_case(case, session, ready)
                    summary['collected'] += 1
                except Exception as error:
                    row = {'id': case['id'], 'family': case['family'], 'route': case['route'], 'surface': case['surface'], 'operation': case['operation'], 'error': {'type': type(error).__name__, 'message': str(error)[:400]}, 'elapsed_ms': (time.monotonic() - start) * 1000, 'grading_performed': False}
                    summary['case_errors'] += 1
                write(output / 'cases' / (case['id'] + '.json'), row)
                summary['cases'].append({'id': case['id'], 'receipt_sha256': sha(output / 'cases' / (case['id'] + '.json')), 'error': 'error' in row})
                write(output / 'PROGRESS.json', summary)
            session.report['complete'] = True
        check_sources(manifest)
        summary['complete'] = summary['attempted'] == len(inputs)
    except Exception as error:
        failure = {'type': type(error).__name__, 'message': str(error)[:400]}
    summary['finished_at'] = datetime.now(timezone.utc).isoformat()
    summary['owner_identity_after'] = owner_identity()
    summary['owner_identity_unchanged'] = summary['owner_identity_before'] == summary['owner_identity_after']
    summary['collection_failure'] = failure
    summary['source_unchanged'] = True
    try:
        check_sources(manifest)
    except Exception as error:
        summary['source_unchanged'] = False
        summary['source_failure'] = str(error)
    native_path = args.native_out.resolve() / 'RESULTS.json'
    if native_path.is_file():
        native = json.loads(native_path.read_text(encoding='utf8'))
        summary['native_receipt'] = {'path': str(native_path), 'sha256': sha(native_path)}
        summary['owned_native_cleanup'] = native['owned_native_cleanup']
        summary['javascript_errors'] = native['javascript_errors']
        summary['http_mutations'] = sum((row['method'] != 'GET' for row in native['network']))
        summary['external_http_requests'] = sum((not row['same_origin'] for row in native['network']))
    write(output / 'CLOSED.json', summary)
    print(json.dumps({'output': str(output), 'attempted': summary['attempted'], 'collected': summary['collected'], 'errors': summary['case_errors'], 'complete': summary['complete'], 'source_unchanged': summary['source_unchanged']}))
    if failure:
        raise RuntimeError('Once-only collection failed; preserve CLOSED.json, no retries')
if __name__ == '__main__':
    main()
