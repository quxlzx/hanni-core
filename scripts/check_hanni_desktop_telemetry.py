"""Read real telemetry in a packaged native window using an isolated owned monitor.

No assistant/model is started, no microphone is opened and no node action is
submitted. Existing external model/backend processes are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/desktop_review'))
sys.path.insert(0, str(ROOT))
from capture_native import wait_window, frame_capture
from desktop.main import request_json
import psutil
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect


def free_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


def models():
    return {p.pid for p in psutil.process_iter(['name'])
            if (p.info['name'] or '').lower() == 'llama-server.exe'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=ROOT/'dist/HANNI OS/HANNI OS.exe')
    parser.add_argument('--output', type=Path, default=ROOT/'data/hanni-desktop-review/live-telemetry')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    initial_models = models()
    result = {'passed': False, 'disclosure': 'Real packaged native window and local/node telemetry; isolated runtime data; dashboard-only owned monitor; no chat, settings, power, SSH terminal or model/voice actions.'}
    result['executable_sha256'] = hashlib.sha256(args.exe.read_bytes()).hexdigest()
    result['initial_external_model_pids'] = sorted(initial_models)
    process = window = monitor_pid = None
    with tempfile.TemporaryDirectory(prefix='hanni-native-live-') as temporary:
        sandbox = Path(temporary)
        state = sandbox/'native-state'
        environment = os.environ.copy()
        environment.update(HANNI_DATA_DIR=str(sandbox/'runtime'), HANNI_CHAT_HISTORY='session')
        url = f'http://127.0.0.1:{free_port()}'
        debug_port = free_port()
        title = 'HANNI OS Live Telemetry Check'
        command = [str(args.exe.resolve()), '--url', url, '--repo-root', str(ROOT),
                   '--state-dir', str(state), '--debug-port', str(debug_port), '--title', title]
        try:
            process = subprocess.Popen(command, env=environment)
            window = wait_window(title)
            until = time.monotonic() + 60
            metadata = None
            while time.monotonic() < until:
                ready = list(state.glob('monitor-ready-*.json'))
                if ready:
                    metadata = json.loads(ready[0].read_text(encoding='utf-8'))
                    break
                if process.poll() is not None:
                    raise RuntimeError('Native app exited before monitor readiness.')
                time.sleep(.2)
            assert metadata is not None, 'Owned monitor did not publish readiness.'
            url, monitor_pid = metadata['url'], metadata['pid']
            result['owned_monitor_pid'] = monitor_pid
            result['actual_origin'] = url
            result['runtime_isolation'] = str(sandbox/'runtime')
            with sync_playwright() as playwright:
                browser = None
                until = time.monotonic() + 30
                while time.monotonic() < until:
                    try:
                        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                        break
                    except Exception:
                        time.sleep(.2)
                assert browser is not None, 'Native WebView2 debug connection did not become ready.'
                page = None
                until = time.monotonic() + 30
                while time.monotonic() < until:
                    pages = [p for context in browser.contexts for p in context.pages]
                    matches = [p for p in pages if p.url.startswith(url)
                               and '?view=mini' not in p.url]
                    if matches:
                        page = matches[0]
                        break
                    if pages:
                        pages[0].wait_for_timeout(100)
                    else:
                        browser.new_browser_cdp_session().send('Target.getTargets')
                assert page is not None, 'Native primary workspace did not load.'
                errors, external, csp = [], [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda req: external.append(req.url) if req.url.startswith(('http://','https://')) and not req.url.startswith(url) else None)
                page.on('console', lambda msg: csp.append(msg.text) if msg.type == 'error' and 'content security policy' in msg.text.lower() else None)
                win32gui.SetWindowPos(window, win32con.HWND_TOP, 0, 32, 1440, 900, 0)
                page.evaluate("location.hash='mission'")
                until = time.monotonic() + 40
                sample = None
                while time.monotonic() < until:
                    sample = request_json(url, '/api/state', timeout=5)
                    if sample.get('sampled_at') and sample.get('resources'):
                        break
                    page.wait_for_timeout(200)
                assert sample and sample.get('resources') and sample.get('sampled_at')
                assert 0 <= sample['resources']['cpu_percent'] <= 100
                assert 0 <= sample['resources']['ram_percent'] <= 100
                expect(page.locator('.mission-metrics > div').first.locator('strong')).not_to_have_text('Unavailable', timeout=15000)
                result['local_readings'] = {key: sample['resources'][key] for key in ['cpu_percent','ram_percent','ram_used_gb','ram_total_gb']}
                result['local_sampled_at'] = sample['sampled_at']
                result['mission_screenshot'] = frame_capture(window, args.output/'mission-real-telemetry-native.png')
                page.evaluate("location.hash='cluster'")
                expect(page.locator('.cluster-node')).to_have_count(9, timeout=15000)
                until = time.monotonic() + 40
                cluster = None
                while time.monotonic() < until:
                    cluster = request_json(url, '/api/cluster', timeout=5)
                    if all(node.get('metrics') for node in cluster['nodes'] if not node['maintenance']):
                        break
                    page.wait_for_timeout(500)
                assert cluster and len(cluster['nodes']) == 9
                measured = [node for node in cluster['nodes'] if node.get('metrics')]
                assert measured, 'No live node reading arrived; diagnostics are retained, no zeroes fabricated.'
                repair = next(node for node in cluster['nodes'] if node['id'] == 'yunjin')
                assert repair['maintenance'] and repair['sampled_at'] is None and repair['metrics'] is None
                result['measured_nodes'] = [{key: node.get(key) for key in ['id','status','sampled_at','uptime_seconds','metrics']} for node in measured]
                # API samples alone do not prove the rendered native interface
                # consumed them. Wait for actual percentages in every measured
                # row before capturing the window, while pumping CDP events.
                for node in measured:
                    row = page.locator(f'.cluster-node[data-node="{node["id"]}"]')
                    expect(row.locator('.node-usage strong').first).to_have_text(
                        re.compile(r'^\d+(?:\.\d+)?%$'), timeout=15000)
                result['rendered_measured_nodes'] = [node['id'] for node in measured]
                result['cluster_screenshot'] = frame_capture(window, args.output/'cluster-real-telemetry-native.png')
                assert not errors and not external and not csp, (errors, external, csp)
                result.update(javascript_errors=errors, external_requests=external, csp_errors=csp)
                win32gui.PostMessage(window, win32con.WM_CLOSE, 0, 0)
                process.wait(timeout=30)
                assert not psutil.pid_exists(monitor_pid), 'Owned dashboard monitor survived native close.'
                assert models() == initial_models, 'An external model process changed during read-only verification.'
                result['checks'] = ['Real local resource readings in native Mission Control', 'Real node metrics and nine-member roster in native Cluster', 'Repair node unprobed and metrics unavailable', 'Owned readiness identity and same-origin connection', 'Native close gracefully stopped only owned monitor', 'External model processes preserved', 'No model/voice/action launch']
                result['passed'] = True
        except Exception as error:
            result['passed'] = False
            result['error'] = repr(error)
            raise
        finally:
            if process is not None and process.poll() is None:
                if window and win32gui.IsWindow(window):
                    win32gui.PostMessage(window, win32con.WM_CLOSE, 0, 0)
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            result['final_external_model_pids'] = sorted(models())
            (args.output/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': result.get('checks'), 'measured_nodes': [node['id'] for node in result.get('measured_nodes',[])]}, indent=2))


if __name__ == '__main__':
    main()
