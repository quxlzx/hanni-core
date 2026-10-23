"""Read-only child-row viewport proof; earlier parent-only frames stay intact."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.development import authenticated_readback
from scripts.campaign8_native.session import NativeSession
VISIBLE_CHILD = 'e=>{const r=e.getBoundingClientRect();let clips=[];\n let visible=r.width>0&&r.height>0&&r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;\n for(let p=e.parentElement;p;p=p.parentElement){let s=getComputedStyle(p),b=p.getBoundingClientRect();\n   const x=/(auto|scroll|hidden|clip)/.test(s.overflowX),y=/(auto|scroll|hidden|clip)/.test(s.overflowY);\n   if(x||y){let contained=(!x||(r.left>=b.left&&r.right<=b.right))&&(!y||(r.top>=b.top&&r.bottom<=b.bottom));\n     clips.push({tag:p.tagName,class:p.className,contained,rect:{x:b.x,y:b.y,width:b.width,height:b.height}});visible=visible&&contained;}}\n const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);\n let unobstructed=Boolean(hit&&(hit===e||e.contains(hit)));\n return {visible:visible&&unobstructed,unobstructed,rect:{x:r.x,y:r.y,width:r.width,height:r.height},clips,\n   text:e.innerText,selectorEvidence:e.className||e.tagName};}'

def capture_child(session, identifier, selector, api_path):
    child = session.page.locator(selector).first
    child.wait_for(state='visible', timeout=5000)
    child.evaluate("e=>e.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'})")
    session.page.wait_for_timeout(150)
    bounds = child.evaluate(VISIBLE_CHILD)
    if not bounds['visible']:
        raise RuntimeError('Target child row is not fully visible and unobstructed in its scroll panes.')
    return {'id': identifier, 'selector': selector, 'child_viewport_proof': bounds, 'api': authenticated_readback(session, api_path), 'screenshot': session.capture(identifier), 'dom': session.dom()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if psutil.Process(ready['pid']).create_time() != ready['create_time']:
        raise RuntimeError('Original owned backend identity changed.')
    with NativeSession(url=ready['url'], output=args.output, maximum_seconds=120) as session:
        session.report['child_row_captures'] = []
        session.execute({'id': 'rows-size', 'action': 'resize', 'size': [1280, 800]})
        session.execute({'id': 'rows-workflows', 'action': 'route', 'route': 'workflows'})
        session.execute({'id': 'rows-completed', 'action': 'select', 'role': 'combobox', 'name': 'Workflow status', 'value': 'completed'})
        session.execute({'id': 'rows-detail', 'action': 'click', 'selector': '.workflow-row'})
        session.execute({'id': 'rows-history', 'action': 'click', 'selector': '.workflow-history summary'})
        session.report['child_row_captures'].append(capture_child(session, 'visible-original-checkpoint-child', '.workflow-history > ol:first-of-type > li', '/api/workflows'))
        session.execute({'id': 'rows-activity', 'action': 'route', 'route': 'activity'})
        session.execute({'id': 'rows-activity-search', 'action': 'fill', 'selector': 'input[aria-label="Search activity and capabilities"]', 'value': 'workspace.task'})
        session.report['child_row_captures'].append(capture_child(session, 'visible-original-search-history-child', '.execution-list > .execution-record > summary', '/api/agents'))
        session.execute({'id': 'rows-activity-failed', 'action': 'select', 'role': 'combobox', 'name': 'Filter execution status', 'value': 'failed'})
        selector = '.execution-list > .execution-record > summary'
        if not session.page.locator(selector).count():
            selector = '.execution-list > .feature-empty'
        session.report['child_row_captures'].append(capture_child(session, 'visible-original-status-history-child', selector, '/api/agents'))
        session.report['scope_note'] = 'Original seeded and UI-produced durable rows; no live planning, model or scheduler claim. Empty filter is explicitly captured as empty when no original row exists.'
        session.report['complete'] = True
if __name__ == '__main__':
    main()
