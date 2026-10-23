"""Fresh native exposed-development reproduction; never opens private finals."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from desktop.main import request_json, validate_url
from scripts.campaign8_native.session import NativeSession

def main():
    import argparse
    import psutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.out.resolve()
    if not output.is_relative_to(root / 'data/campaign8-verifier') or output.exists():
        raise ValueError('A fresh independent evidence directory is required')
    ready = json.loads(args.ready.read_text(encoding='utf-8'))
    assert ready['evidence_class'] == 'CONTROLLED'
    assert psutil.Process(ready['pid']).create_time() == ready['create_time']
    url = validate_url(ready['url'])
    output.mkdir(parents=True)
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'evidence_class': 'CONTROLLED', 'scope': 'Independent actual native WebView2 against original isolated backend; no HTTP mutations or final cases', 'backend_pid': ready['pid'], 'backend_create_time': ready['create_time'], 'private_final_access': False, 'source': {}, 'observations': {}, 'errors': []}
    for filename in ('frontend/src/workspace.tsx', 'frontend/src/screens.tsx', 'src/hanni/dashboard/static/app.js', 'src/hanni/dashboard/static/style.css'):
        report['source'][filename] = hashlib.sha256((root / filename).read_bytes()).hexdigest()
    path = output / 'RESULTS.json'

    def save():
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    save()
    try:
        with NativeSession(url=url, output=args.native_out, maximum_seconds=180) as session:
            session.execute({'id': 'independent-home-route', 'action': 'route', 'route': 'home'})
            session.execute({'id': 'independent-wide', 'action': 'resize', 'size': [1366, 860]})
            session.page.wait_for_timeout(500)
            report['observations']['home_wide_capture'] = session.capture('independent-home-wide')
            chat = request_json(url, '/api/chat?before=1')
            state = request_json(url, '/api/state')
            workspace = request_json(url, '/api/workspace')
            report['observations']['original_backend'] = {'chat_ready': chat.get('ready'), 'chat_busy': chat.get('busy'), 'model_status': state.get('model_status'), 'model_names': [m.get('name') for m in workspace.get('models', [])], 'controller_attached': ready.get('chat_controller_attached')}
            report['observations']['home_ui'] = session.page.evaluate("() => {\n                const model=[...document.querySelectorAll('.facts dt')].find(e=>e.textContent==='Model')?.nextElementSibling;\n                const style=model?getComputedStyle(model):null,rect=model?.getBoundingClientRect();\n                return {placeholder:document.querySelector('textarea')?.getAttribute('placeholder'),\n                    model_text:model?.textContent,model_width:rect?.width,model_height:rect?.height,\n                    model_line_height:style?.lineHeight,model_font_family:style?.fontFamily,\n                    model_font_size:style?.fontSize,body_font_family:getComputedStyle(document.body).fontFamily};\n            }")
            session.execute({'id': 'independent-compact', 'action': 'resize', 'size': [900, 650]})
            session.execute({'id': 'independent-cluster-route', 'action': 'route', 'route': 'cluster'})
            report['observations']['compact_capture'] = session.capture('independent-cluster-compact')
            trigger = session.page.locator('.search-trigger')
            report['observations']['compact_search'] = {'visible': trigger.is_visible(), 'enabled': trigger.is_enabled(), 'matching_accessible_role_named_search': session.page.get_by_role('button', name='Search workspace', exact=True).count(), 'aria_label': trigger.get_attribute('aria-label'), 'title': trigger.get_attribute('title'), 'element': trigger.evaluate("e=>({text:e.innerText,rect:e.getBoundingClientRect().toJSON(),\n                    children:[...e.children].map(n=>({tag:n.tagName,display:getComputedStyle(n).display,\n                    aria_hidden:n.getAttribute('aria-hidden'),text:n.textContent}))})")}
            trigger.click()
            report['observations']['search_after_click'] = {'dialog_visible': session.page.get_by_role('dialog', name='Search workspace', exact=True).is_visible(), 'focus': session.page.evaluate('({tag:document.activeElement.tagName,id:document.activeElement.id})')}
            session.page.keyboard.press('Escape')
            report['observations']['escape_closed_search'] = session.page.get_by_role('dialog', name='Search workspace', exact=True).count() == 0
            session.report['complete'] = True
            save()
        report['native_receipt'] = (args.native_out.resolve() / 'RESULTS.json').as_posix()
        native = json.loads(Path(report['native_receipt']).read_text(encoding='utf-8'))
        report['native_cleanup'] = native['owned_native_cleanup']
        report['native_javascript_errors'] = native['javascript_errors']
        report['original_http_mutations'] = sum((r.get('method') != 'GET' for r in native['network']))
        report['after_source'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in report['source']}
        report['source_unchanged'] = report['source'] == report['after_source']
    except Exception as e:
        report['errors'].append({'type': type(e).__name__, 'message': str(e)[:400]})
        save()
        raise
    save()
    print(json.dumps({'path': path.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source_unchanged': report['source_unchanged'], 'native_cleanup': report['native_cleanup'], 'http_mutations': report['original_http_mutations']}))
if __name__ == '__main__':
    main()
