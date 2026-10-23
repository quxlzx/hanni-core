"""Exposed development-only actual native tab keyboard observations."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.session import NativeSession
from .final_runner import process_identity, sha, write
TAB_STATE = "() => ({tabs:[...document.querySelectorAll('[role=tab]')].map(e=>({name:e.innerText,selected:e.getAttribute('aria-selected'),tabIndex:e.tabIndex,focused:e===document.activeElement,top:e.getBoundingClientRect().top})),focused:{name:document.activeElement.innerText,role:document.activeElement.getAttribute('role')},scroll:[...document.querySelectorAll('*')].filter(e=>e.scrollTop).map(e=>({className:e.className,scrollTop:e.scrollTop}))})"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-out', type=Path, required=True)
    args = parser.parse_args()
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if ready['evidence_class'] != 'CONTROLLED' or process_identity(ready['pid'])['create_time'] != ready['create_time']:
        raise RuntimeError('Disposable original backend identity required')
    if args.out.exists():
        raise FileExistsError('Fresh development output required')
    args.out.mkdir(parents=True)
    source = Path('frontend/src/memory.tsx')
    report = {'scope': 'Independent actual native exposed development; original memory tabs, no private cases or HTTP mutation', 'source_sha256': sha(source), 'steps': []}
    write(args.out / 'RESULTS.json', report)
    with NativeSession(url=ready['url'], output=args.native_out, maximum_seconds=90) as session:
        session.execute({'id': 'memory-development-route', 'action': 'route', 'route': 'memory'})
        session.native('resize', size=[900, 650])
        tab = session.page.get_by_role('tab', name='Stored memories', exact=True)
        tab.focus()
        report['steps'].append({'action': 'focus-first', 'observed': session.page.evaluate(TAB_STATE)})
        report['before_capture'] = session.capture('memory-tabs-before')
        for key in ['ArrowRight', 'Home', 'End']:
            session.page.keyboard.press(key)
            session.page.wait_for_timeout(100)
            report['steps'].append({'action': key, 'observed': session.page.evaluate(TAB_STATE)})
        report['after_capture'] = session.capture('memory-tabs-after-end')
        cdp = session.page.context.new_cdp_session(session.page)
        try:
            report['actual_accessibility_tree'] = cdp.send('Accessibility.getFullAXTree')
        finally:
            cdp.detach()
        session.report['complete'] = True
    native = json.loads((args.native_out / 'RESULTS.json').read_text(encoding='utf8'))
    report.update(source_unchanged=sha(source) == report['source_sha256'], native_cleanup=native['owned_native_cleanup'], javascript_errors=native['javascript_errors'], http_mutations=sum((r['method'] != 'GET' for r in native['network'])), native_receipt_sha256=sha(args.native_out / 'RESULTS.json'))
    write(args.out / 'RESULTS.json', report)
    print(json.dumps({'path': str(args.out / 'RESULTS.json'), 'sha256': sha(args.out / 'RESULTS.json'), 'source_unchanged': report['source_unchanged'], 'cleanup': report['native_cleanup']}))
if __name__ == '__main__':
    main()
