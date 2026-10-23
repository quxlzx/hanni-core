"""Actual HWND captures with separately labelled WebView scale emulation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.session import NativeSession
from scripts.campaign8_native.development import authenticated_readback
from scripts.campaign8_native.navigation import navigate, reset_capture_scroll
ROUTE_APIS = {'home': ['/api/state', '/api/workspace', '/api/chat'], 'chat': ['/api/chat'], 'voice': ['/api/voice'], 'planner': ['/api/productivity'], 'tasks': ['/api/productivity'], 'calendar': ['/api/calendar'], 'projects': ['/api/productivity'], 'memory': ['/api/memory/explorer?limit=30'], 'mission': ['/api/state'], 'models': ['/api/model-lab'], 'agents': ['/api/agents'], 'cluster': ['/api/cluster'], 'activity': ['/api/activity'], 'screen': ['/api/awareness'], 'notifications': ['/api/notifications'], 'settings': ['/api/workspace'], 'mcp': ['/api/mcp'], 'workflows': ['/api/workflows'], 'model-routing': ['/api/model-routing']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    assert ready['evidence_class'] == 'CONTROLLED'
    assert psutil.Process(ready['pid']).create_time() == ready['create_time']
    with NativeSession(url=ready['url'], output=args.output) as session:
        session.report['backend_receipt'] = {k: ready[k] for k in ['url', 'pid', 'create_time', 'scope', 'evidence_class']}
        session.report['original_route_projections'] = []
        for route in session.report['declared_routes']:
            navigation = navigate(session, route)
            reset_capture_scroll(session)
            session.report['original_route_projections'].append({'route': route, 'navigation': navigation, 'dom': session.dom(), 'original_api_readbacks': [authenticated_readback(session, path) for path in ROUTE_APIS[route]], 'window': session.window_state(session.main)})
            session.save()
        session.report['scale_cases'] = []
        session.execute({'id': 'home-route', 'action': 'route', 'route': 'home'})
        for size in [[1536, 960], [1100, 700]]:
            label = 'physical-home-' + 'x'.join(map(str, size))
            session.execute({'id': label + '-resize', 'action': 'resize', 'size': size})
            session.report['scale_cases'].append({'id': label, 'method': 'Actual physical window resize', 'windows_scaling_changed': False, 'dom': session.dom(), 'window': session.window_state(session.main), 'screenshot': session.capture(label)})
        session.execute({'id': 'scale-size', 'action': 'resize', 'size': [1366, 860]})
        cdp = session.page.context.new_cdp_session(session.page)
        try:
            for route in ['home', 'memory', 'cluster']:
                cdp.send('Emulation.clearDeviceMetricsOverride')
                session.execute({'id': route + '-route', 'action': 'route', 'route': route})
                baseline = session.dom()['viewport']
                for scale in [1.5, 2.0]:
                    override = {'width': round(baseline['width'] * baseline['devicePixelRatio'] / scale), 'height': round(baseline['height'] * baseline['devicePixelRatio'] / scale), 'deviceScaleFactor': scale, 'mobile': False}
                    cdp.send('Emulation.setDeviceMetricsOverride', override)
                    session.page.wait_for_timeout(200)
                    label = route + '-cdp-emulated-' + str(round(scale * 100))
                    session.report['scale_cases'].append({'id': label, 'method': 'WebView2 CDP device metrics emulation; not physical Windows scaling', 'override': override, 'windows_scaling_changed': False, 'actual_windows_dpi': session.window_state(session.main)['dpi'], 'baseline_viewport': baseline, 'dom': session.dom(), 'fonts': session.platform_fonts(), 'screenshot': session.capture(label)})
                    session.save()
        finally:
            cdp.send('Emulation.clearDeviceMetricsOverride')
            cdp.detach()
            session.report['emulated_override_cleared'] = True
        session.report['complete'] = True
if __name__ == '__main__':
    main()
