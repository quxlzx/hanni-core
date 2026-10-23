"""Fresh actual Windows HANNI OS navigation/readback evidence, no browser preview."""
import argparse
import json
from pathlib import Path
import time
from scripts.campaign10_manager.native_session import NativeSession
from scripts.campaign8_native.development import authenticated_readback
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign10-native/current-desktop-cycle1'
READBACK = {'home': '/api/workspace', 'chat': '/api/workspace', 'activity': '/api/activity', 'agents': '/api/agents', 'workflows': '/api/workflows', 'memory': '/api/memory', 'mcp': '/api/mcp', 'cluster': '/api/cluster', 'models': '/api/model-lab', 'calendar': '/api/calendar', 'tasks': '/api/productivity', 'notifications': '/api/notifications', 'settings': '/api/awareness', 'voice': '/api/voice', 'screen': '/api/awareness', 'planner': '/api/calendar', 'projects': '/api/productivity', 'mission': '/api/workspace', 'model-routing': '/api/model-routing'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycle', default='current-desktop-cycle2')
    parser.add_argument('--routes', nargs='*')
    parser.add_argument('--widths', nargs='*', type=int, default=[1280, 1000])
    args = parser.parse_args()
    output = ROOT / 'data/campaign10-native' / args.cycle
    rows = []
    with NativeSession(url='http://127.0.0.1:8766', output=output, maximum_seconds=300, evidence_class='ACTUAL_WINDOWS_CURRENT_BACKEND_ISOLATED_STATE') as session:
        for width in args.widths:
            size = [width, 850 if width == 1280 else 700]
            session.native('resize', size=size)
            for route in session.report['declared_routes']:
                if args.routes and route not in args.routes:
                    continue
                start = time.perf_counter()
                try:
                    observed = session.execute({'id': str(size[0]) + '-' + route, 'action': 'route', 'route': route, 'settle_ms': 450})
                    capture = session.capture(str(size[0]) + '-' + route)
                    path = READBACK.get(route)
                    readback = authenticated_readback(session, path) if path else None
                    rows.append({'route': route, 'size': size, 'dom': session.dom(), 'screenshot': capture, 'backend_readback': readback, 'duration_ms': (time.perf_counter() - start) * 1000})
                except Exception as exc:
                    rows.append({'route': route, 'size': size, 'error': {'type': type(exc).__name__, 'message': str(exc)}})
        session.report['current_route_readbacks'] = rows
        session.execute({'id': 'keyboard-home', 'action': 'route', 'route': 'home', 'settle_ms': 800})
        session.native('focus')
        session.page.keyboard.press('Tab')
        session.report['keyboard_focus'] = {'dom': session.dom(), 'screenshot': session.capture('keyboard-focus')}
        session.report['lower_scroll'] = []
        for route in ('home', 'cluster', 'settings', 'models'):
            session.execute({'id': 'lower-' + route, 'action': 'route', 'route': route, 'settle_ms': 800})
            session.page.evaluate("() => {for(const e of document.querySelectorAll('*')) {const s=getComputedStyle(e); if(/auto|scroll/.test(s.overflowY)&&e.scrollHeight>e.clientHeight) e.scrollTop=e.scrollHeight;}}")
            session.page.wait_for_timeout(400)
            session.report['lower_scroll'].append({'route': route, 'dom': session.dom(), 'screenshot': session.capture('lower-' + route)})
        session.report['minimize'] = session.native('minimize')
        session.report['restore'] = session.native('restore')
        session.native('focus')
        session.page.wait_for_timeout(1200)
        session.report['restore_resize'] = session.native('resize', size=[size[0] + 1, size[1]])
        session.page.wait_for_timeout(1200)
        session.capture('restored-window')
        session.report['complete'] = True
        session.save()
    (output / 'ROUTES.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'routes': len(rows), 'errors': sum(('error' in r for r in rows)), 'output': str(output)}))
if __name__ == '__main__':
    main()
