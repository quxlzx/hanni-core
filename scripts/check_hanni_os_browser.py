"""Exercise the shipped browser bundle with synthetic state and in-memory chat.

Requires: pip install playwright; Chrome installed (or playwright install chromium).
No model, cloud connection, real tool execution, or microphone access.
"""
from __future__ import annotations
import argparse
import json
import tempfile
import threading
import time
from urllib.parse import urlsplit
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright, expect
from hanni.config.loader import load_config
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.server import DashboardServer
from hanni.dashboard.cluster import ClusterMonitor

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data/hanni-os-review')
    parser.add_argument('--channel', default='chrome', help='Chrome channel; use chromium for a Playwright browser')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hanni-os-browser-') as temporary:
        config = load_config(ROOT/'config', data_dir=Path(temporary), env={})
        model = config.models.supervisor
        sample = {
            'sampled_at': time.time(), 'model_status': 'ready', 'error': None,
            'model': {'file': model.model_file, 'quantization': model.quantization, 'context': model.context_length},
            'model_residency': {model.id: {'model': model.model_file, 'role': model.role, 'state': 'READY',
                'pinned': True, 'resident': True, 'active_inferences': 0, 'process_ram_mb': 2480,
                'device': 'test-gpu', 'context': model.context_length, 'endpoint': 'http://127.0.0.1:8000'}},
            'activity': {'input_level': .12, 'speaking': False, 'microphone_active': True},
            'interaction': {'response_in_progress': False, 'tts_speaking': False, 'voice_engaged': False, 'active_background_jobs': 0},
            'safe_mode': False, 'uptime_seconds': 27300, 'battery': None,
            'disk': {'percent': 42.8, 'used_gb': 438, 'total_gb': 1024},
            'network': {'receive_bps': 40960, 'send_bps': 10240},
            'resources': {'cpu_percent': 12.4, 'ram_percent': 38.2, 'ram_used_gb': 12.2, 'ram_total_gb': 32,
                'gpus': [{'name': 'Browser test GPU', 'memory_used_mb': 3072, 'memory_total_mb': 8192,
                          'utilization_percent': None, 'temperature_c': None}], 'gpu_note': 'Estimated memory'},
        }
        gpu = {'mode': 'auto', 'devices': [{'id': 'test-gpu', 'name': 'Browser test GPU', 'total_mb': 8192, 'auto_eligible': True}],
               'selected_device_name': 'Browser test GPU', 'selected_device_id': 'test-gpu',
               'current_device_id': 'test-gpu', 'restart_required': False}
        audio = {'input_id': 'default', 'output_id': 'default', 'inputs': [{'id': '1', 'name': 'Browser test microphone', 'hostapi': 'WASAPI'}],
                 'outputs': [{'id': 'test-speaker', 'name': 'Browser test speaker'}], 'input_error': None, 'output_error': None}
        hub = ChatHub(); hub.ready = True
        shutdown = threading.Event()
        cluster_mode = ['ready']
        def node_sample(node, peer):
            now = time.time()
            ready = node.id == 'hanni' and cluster_mode[0] == 'ready'
            result = {'status': 'online' if node.id != 'haerin' else 'offline',
                    'checked_at': now, 'sampled_at': now if ready else None,
                    'metrics': {'cpu_percent': 12.5, 'ram_percent': 50., 'ram_used_bytes': 8*1024**3, 'ram_total_bytes': 16*1024**3} if ready else None,
                    'address': node.tailscale_ip, 'connection': 'tailscale', 'availability_source': 'telemetry' if ready else 'tailscale',
                    'message': None if ready else 'SSH host key needs verification.',
                    'uptime_seconds': 90123 if ready else None,
                    'processes': [{'name': 'llama-server', 'cpu_percent': 125., 'ram_percent': 30.}] if ready else None}
            return result
        cluster_monitor = ClusterMonitor(probe=node_sample, tailnet=lambda: {'state': 'connected', 'peers': {}})
        cluster_monitor.sample_once()
        cluster_monitor.sample_once()
        def cluster_snapshot():
            cluster_monitor.sample_once()
            return cluster_monitor.snapshot()
        cluster_fake = SimpleNamespace(start=lambda: None, close=lambda: None, snapshot=cluster_snapshot)
        power_writes, power_operations = [], {}
        power_mode = ['accepted']
        def project_power(snapshot):
            for node in snapshot['nodes']:
                enabled = node['id'] == 'hanni' and node['metrics'] is not None
                node['power'] = {'actions': {action: {'enabled': enabled, 'reason': None if enabled else 'Power controls unavailable.'} for action in ['sleep','reboot']},
                                 'last_operation': power_operations.get(node['id'])}
            return snapshot
        def execute_power(data):
            power_writes.append(data)
            operation = {**{key:data[key] for key in ['id','node','action']}, 'requested_at':time.time(),
                         'status':power_mode[0], 'message':'Synthetic power request accepted.' if power_mode[0]=='accepted' else 'Synthetic node rejected the request.'}
            power_operations[data['node']] = operation
            return operation
        power_fake = SimpleNamespace(start=lambda:None, close=lambda:None, project=project_power, execute=execute_power)
        terminal_writes=[]
        def project_terminal(snapshot):
            for node in snapshot['nodes']:
                node['terminal']={'enabled':not node['maintenance'],'reason':'Under repair' if node['maintenance'] else None}
            return snapshot
        def execute_terminal(data):
            terminal_writes.append(data)
            return {'id':data['id'],'node':data['node'],'opened':True,'message':'Opened a synthetic SSH terminal.'}
        terminal_fake=SimpleNamespace(project=project_terminal,execute=execute_terminal)
        server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {**sample, 'sampled_at': time.time()}), hub, shutdown_event=shutdown, cluster=cluster_fake, cluster_power=power_fake,cluster_terminal=terminal_fake)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        errors, writes, external_requests, csp_errors = [], [], [], []
        def setting_route(route):
            is_audio = route.request.url.endswith('/api/audio-devices')
            data = audio if is_audio else gpu
            if route.request.method == 'POST':
                writes.append((route.request.url, route.request.post_data_json))
                if is_audio: data.update(route.request.post_data_json)
                else: data.update(route.request.post_data_json, requested_device_id='test-gpu')
            route.fulfill(json=data)
        def layout(page, width):
            page.set_viewport_size({'width': width, 'height': 940})
            page.wait_for_timeout(70)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Page overflow at {width}px'
            assert page.locator('.main-content').evaluate('(el)=>el.scrollWidth <= el.clientWidth+1'), f'Workspace overflow at {width}px'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**({} if args.channel=='chromium' else {'channel':args.channel}), headless=True)
                loading = browser.new_page(viewport={'width':1600,'height':1000})
                pending = []
                loading.on('pageerror', lambda error: errors.append(str(error)))
                loading.route('**/api/chat', lambda route: pending.append(route))
                loading.goto(f'http://127.0.0.1:{server.server_port}/#chat')
                expect(loading.locator('.message-log .skeleton-group')).to_be_visible()
                expect(loading.locator('#chat-input')).to_be_disabled()
                loading.screenshot(path=str(args.output/'loading-desktop.png'))
                for route in pending: route.fulfill(json=hub.snapshot())
                loading.unroute('**/api/chat')
                expect(loading.locator('#chat-input')).to_be_enabled()
                loading.close()
                page = browser.new_page(viewport={'width': 1600, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda req: external_requests.append(req.url) if urlsplit(req.url).scheme in {'http','https'} and urlsplit(req.url).hostname not in {'127.0.0.1','localhost'} else None)
                page.on('console', lambda msg: csp_errors.append(msg.text) if msg.type=='error' and 'content security policy' in msg.text.lower() else None)
                page.route('**/api/gpu-routing', setting_route);page.route('**/api/audio-devices', setting_route)
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                expect(page.locator('.screen-home h1')).to_be_visible()
                expect(page.locator('#chat-input')).to_be_enabled()
                page.screenshot(path=str(args.output/'home-desktop.png'))
                for screen in ['home','chat','mission','cluster','settings']:
                    page.evaluate('(screen)=>location.hash=screen',screen)
                    expect(page.locator(f'.screen-{screen}')).to_be_visible()
                    for width in [1920,1600,1440,1280,1100,960,840,720,600,440,390,320]:
                        layout(page,width)
                        if width>1100 and not page.locator('.inspector').count():
                            page.get_by_role('button',name='Show inspector',exact=True).first.click()
                            layout(page,width)
                    page.set_viewport_size({'width':1600,'height':1000})
                    page.get_by_role('button',name='Show inspector',exact=True).first.click()
                    page.screenshot(path=str(args.output/f'{screen}-desktop.png'))
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path=str(args.output/f'{screen}-mobile.png'))
                page.set_viewport_size({'width':1600,'height':1000})
                page.evaluate("location.hash='cluster'")
                expect(page.locator('.cluster-node')).to_have_count(9)
                expect(page.locator('.cluster-refresh')).to_have_text('Live updates every 1 second')
                detail = page.locator('.cluster-detail')
                def select_node(node_id):
                    if detail.count():
                        page.get_by_role('button', name='‹ Back to nodes', exact=True).click()
                    page.locator(f'[data-node="{node_id}"]').click()
                search = page.get_by_role('searchbox', name='Search nodes')
                search.fill('192.0.2.28')
                expect(page.locator('.cluster-node')).to_have_count(1)
                expect(page.locator('[data-node="hanni"]')).to_be_visible()
                search.fill('no matching node')
                expect(page.locator('.cluster-node')).to_have_count(0)
                search.fill('')
                page.get_by_label('Filter node status', exact=True).select_option('maintenance')
                expect(page.locator('.cluster-node')).to_have_count(1)
                expect(page.locator('[data-node="yunjin"]')).to_be_visible()
                page.get_by_label('Filter node status', exact=True).select_option('all')
                page.get_by_label('Sort nodes', exact=True).select_option('cpu')
                expect(page.locator('.cluster-node').first).to_have_attribute('data-node', 'hanni')
                page.get_by_label('Sort nodes', exact=True).select_option('name')
                expect(page.locator('.cluster-node')).to_have_count(9)
                select_node('hanni')
                expect(detail.get_by_label('HANNI CPU usage',exact=True)).to_have_text('12.5%')
                expect(detail.get_by_label('HANNI Memory usage',exact=True)).to_have_text('50.0%')
                expect(detail.get_by_label('HANNI uptime',exact=True)).to_contain_text('1d 1h 2m')
                expect(detail.get_by_label('HANNI current activity',exact=True)).to_contain_text('llama-server')
                expect(detail.locator('.cluster-process-table strong')).to_have_text('125.0%')
                select_node('yunjin')
                expect(page.get_by_role('button',name='Reboot Yunjin',exact=True)).to_be_disabled()
                expect(page.get_by_role('button',name='Open SSH terminal for Yunjin',exact=True)).to_be_disabled()
                expect(page.get_by_role('button',name='Sleep Yunjin',exact=True)).to_be_disabled()
                select_node('hanni')
                page.get_by_role('button',name='Open SSH terminal for HANNI',exact=True).click()
                expect(detail.locator('.cluster-terminal-result')).to_contain_text('Opened')
                assert len(terminal_writes)==1 and terminal_writes[0]['node']=='hanni' and set(terminal_writes[0])=={'id','node'}
                select_node('haerin')
                expect(page.get_by_role('button',name='Open SSH terminal for Haerin',exact=True)).to_be_enabled()
                expect(page.get_by_role('button',name='Reboot Haerin',exact=True)).to_be_disabled()
                select_node('hanni')
                page.get_by_role('button',name='Reboot HANNI',exact=True).click()
                expect(page.get_by_role('dialog',name='Reboot HANNI?')).to_be_visible()
                assert not power_writes
                page.get_by_role('dialog').get_by_role('button',name='Cancel',exact=True).click()
                assert not power_writes
                page.get_by_role('button',name='Reboot HANNI',exact=True).click()
                page.keyboard.press('Escape')
                expect(page.get_by_role('dialog')).to_have_count(0)
                assert not power_writes
                page.get_by_role('button',name='Reboot HANNI',exact=True).click()
                page.get_by_role('dialog').get_by_role('button',name='Reboot HANNI',exact=True).click()
                expect(detail.locator('.cluster-power-result')).to_contain_text('accepted')
                assert len(power_writes)==1 and power_writes[0]['node']=='hanni' and power_writes[0]['action']=='reboot' and power_writes[0]['confirmed'] is True
                power_mode[0]='failed'
                page.get_by_role('button',name='Sleep HANNI',exact=True).click()
                expect(page.get_by_role('dialog')).to_contain_text('Waking it may require physical access')
                page.get_by_role('dialog').get_by_role('button',name='Sleep HANNI',exact=True).click()
                expect(detail.locator('.cluster-power-result')).to_contain_text('rejected')
                assert len(power_writes)==2 and power_writes[1]['action']=='sleep'
                page.get_by_role('button', name='‹ Back to nodes', exact=True).click()
                expect(page.locator('[data-node="haerin"] .node-status')).to_have_text('Offline')
                expect(page.locator('[data-node="yunjin"] .member-emoji')).to_have_text('🪼')
                expect(page.locator('[data-node="yunjin"] .node-status')).to_have_text('Under repair')
                hanni_box = page.locator('[data-node="hanni"]').bounding_box()
                next_box = page.locator('[data-node="jeongyeon"]').bounding_box()
                assert hanni_box and next_box and hanni_box['x'] == next_box['x'] and next_box['y'] > hanni_box['y']
                page.locator('[data-node="yunjin"]').scroll_into_view_if_needed()
                expect(page.locator('[data-node="yunjin"]')).to_be_in_viewport()
                select_node('wonyoung')
                expect(detail.locator('.cluster-notice')).to_contain_text('host key')
                select_node('yunjin')
                assert detail.locator('.cluster-resource').count() == 0
                select_node('hanni')
                for chart in detail.locator('.cluster-chart').all():
                    expect(chart).to_be_visible()
                    # A legitimate flat SVG polyline has a zero-height box;
                    # its stroke is painted, but Playwright calls it "hidden".
                    expect(chart.locator('polyline, circle').first).to_be_attached()
                detail.locator('.cluster-connection summary').click()
                expect(detail.locator('.cluster-connection code')).to_have_text('ssh athena@192.0.2.28')
                cluster_mode[0] = 'missing'
                expect(detail.get_by_label('HANNI CPU usage',exact=True)).to_have_text('Unavailable',timeout=10000)
                expect(detail.locator('.cluster-resource-caption').first).to_contain_text('Last known history')
                page.route('**/api/cluster',lambda route: route.abort())
                expect(page.locator('.cluster-error')).to_be_visible(timeout=10000)
                expect(detail.locator('.node-status')).to_have_text('Status stale')
                expect(page.get_by_role('button',name='Reboot HANNI',exact=True)).to_be_disabled()
                page.unroute('**/api/cluster')
                cluster_mode[0] = 'ready'
                expect(detail.get_by_label('HANNI CPU usage',exact=True)).to_have_text('12.5%',timeout=10000)
                expect(page.locator('.cluster-error')).to_have_count(0)
                page.evaluate("location.hash='chat'")
                expect(page.locator('.conversation-empty h2')).to_have_text('Start a conversation')
                page.locator('#chat-input').fill('Browser check <script>window.bad = true</script>')
                page.locator('#chat-input').press('Enter')
                expect(page.locator('.chat-message.user p')).to_contain_text('<script>')
                prompt=hub.take();assert prompt
                row=hub.begin(prompt,'browser')
                expect(page.locator('.chat-message.assistant .skeleton-group')).to_be_visible()
                expect(page.locator('#chat-clear')).to_be_disabled()
                hub.update(row,'This is a synthetic test reply.','working')
                expect(page.locator('.chat-message.assistant p')).to_have_text('This is a synthetic test reply.')
                hub.update(row,'This is a synthetic test reply.','complete')
                assert page.evaluate('window.bad') is None
                page.reload();expect(page.locator('.chat-message.assistant')).to_have_count(1)
                page.locator('#chat-clear').click()
                expect(page.get_by_role('dialog')).to_be_visible()
                page.get_by_role('button',name='Cancel',exact=True).click()
                expect(page.locator('.chat-message.assistant')).to_have_count(1)
                page.locator('#chat-clear').click()
                page.get_by_role('dialog').get_by_role('button',name='Clear history',exact=True).click()
                expect(page.locator('.conversation-empty')).to_be_visible()
                page.keyboard.press('Control+k')
                expect(page.locator('#workspace-search')).to_be_focused()
                page.locator('#workspace-search').fill('NoSuchCapabilityOrScreen')
                expect(page.get_by_role('dialog').get_by_text('No matches',exact=True)).to_be_visible()
                page.keyboard.press('Escape');expect(page.get_by_role('dialog')).to_have_count(0)
                page.evaluate("location.hash='settings'")
                expect(page.locator('#microphone-device')).to_be_visible()
                page.locator('#microphone-device').select_option('1')
                page.locator('#audio-apply').click()
                expect(page.get_by_text('Audio choices saved. Restart the voice session to apply them.')).to_be_visible()
                page.locator('#gpu-route').select_option('test-gpu');page.locator('#gpu-apply').click()
                expect(page.get_by_text('Routing saved. Restart the model to move an already loaded model.')).to_be_visible()
                assert len(writes)==2
                page.emulate_media(reduced_motion='reduce')
                expect(page.locator('#motion')).to_have_attribute('aria-pressed','true')
                page.wait_for_timeout(100)
                frozen=page.locator('.voice-orb').evaluate('(canvas)=>canvas.toDataURL()')
                sample['activity']['input_level']=.9
                page.wait_for_timeout(600)
                assert page.locator('.voice-orb').evaluate('(canvas)=>canvas.toDataURL()')==frozen
                sample['activity']['speaking']=True
                expect(page.locator('.voice-toggle strong')).to_have_text('Speaking')
                page.get_by_role('button', name='Show voice details', exact=True).click()
                expect(page.locator('.voice-detail-panel')).to_contain_text('Output levels are unavailable')
                page.get_by_role('button', name='Hide voice details', exact=True).click()
                sample['activity']['speaking']=False
                page.evaluate("location.hash='chat'")
                page.locator('#chat-input').fill('Keep this draft')
                page.route('**/api/chat',lambda route:route.abort());page.route('**/api/state',lambda route:route.abort())
                expect(page.locator('#chat-input')).to_be_disabled()
                expect(page.locator('#chat-input')).to_have_value('Keep this draft')
                expect(page.locator('.conversation-empty h2')).to_have_text('Waiting for HANNI')
                page.screenshot(path=str(args.output/'offline-mobile.png'))
                page.unroute('**/api/chat');page.unroute('**/api/state')
                expect(page.locator('#chat-input')).to_be_enabled()
                expect(page.locator('#chat-input')).to_have_value('Keep this draft')
                hub.ready=False
                expect(page.locator('#chat-input')).to_be_disabled()
                expect(page.locator('.conversation-empty h2')).to_have_text('Assistant starting')
                hub.ready=True;expect(page.locator('#chat-input')).to_be_enabled()
                page.set_viewport_size({'width':1600,'height':1000})
                if not page.locator('.inspector').count():
                    page.get_by_role('button',name='Show inspector',exact=True).first.click()
                page.get_by_role('button',name='Hide inspector',exact=True).first.click()
                expect(page.locator('.inspector')).to_have_count(0)
                page.reload();expect(page.locator('.inspector')).to_have_count(0)
                page.get_by_role('button',name='Show inspector',exact=True).first.click()
                expect(page.locator('.inspector')).to_be_visible()
                log=Path(temporary)/'logs/tool_audit.jsonl';log.parent.mkdir()
                log.write_text(json.dumps({'tool':'system.stats','ok':True,'timestamp':'2026-10-09T12:00:00Z',
                    'duration_ms':20,'arguments':{'password':'never-show-this'},'message':'Measured system statistics.'})+'\n')
                page.evaluate("location.hash='mission'")
                expect(page.locator('.main-content .tool-events strong')).to_have_text('system.stats')
                page.locator('.main-content .tool-events summary').click()
                expect(page.locator('.main-content .tool-events pre')).to_contain_text('[REDACTED]')
                assert 'never-show-this' not in page.content()
                assert not errors,errors
                assert not external_requests,external_requests
                assert not csp_errors,csp_errors
                page.evaluate("location.hash='settings'")
                page.locator('#shutdown').click()
                page.get_by_role('dialog').get_by_role('button',name='Cancel',exact=True).click()
                assert not shutdown.is_set()
                page.locator('#shutdown').click()
                page.get_by_role('dialog').get_by_role('button',name='Stop HANNI',exact=True).click()
                expect(page.locator('#shutdown')).to_have_text('Stopping HANNI')
                assert shutdown.wait(1)
                browser.close()
            result={'passed':True,'screens':['home','chat','mission','cluster','settings'],'widths':[1920,1600,1440,1280,1100,960,840,720,600,440,390,320],
                'javascript_errors':errors,'external_requests':external_requests,'csp_errors':csp_errors,'checks':['initial loading skeleton','chat submission and streamed snapshots','reply skeleton','plain-text HTML safety',
                'history reload and clear confirmation','command palette focus and Escape','audio and GPU settings','reduced motion and frozen visual',
                'honest playback state','disconnection and recovery','draft preservation','assistant unavailable','inspector persistence',
                'redacted real audit projection','cluster graphs and availability','repair node and jellyfish emoji','vertical node layout and scroll',
                'cluster missing readings and stale connection recovery','one-second refresh, uptime and measured process activity',
                'node power dialogs cancel/Escape, accepted/failed simulated requests, disabled nodes',
                'per-node SSH terminal request and disabled repair node',
                'cluster search by address, empty search, status filter and measured CPU sort',
                'selected node details with preserved graphs, diagnostics and controls','shutdown cancel and confirmed request']}
            (args.output/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result,indent=2))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3);hub.close();hub.db.close()

if __name__=='__main__':
    main()
