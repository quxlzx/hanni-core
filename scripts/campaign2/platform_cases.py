"""Prospective semantic cases for all actual built-in platform definitions.

Enter ``deps`` before copying args or reading ``query``: process.stop binds the
PID of its newly created owned helper. Call verify before leaving the context.
``controlled=True`` additionally supplies rich read-only OS data; those runs
are MOCK, even when the ordinary case uses live local diagnostic reads.
"""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
import importlib
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
import psutil
from scripts.campaign2.platform_fixtures import ENV_NAME, ENV_VALUE, MODULE_NAMES, PLAN_B, PlatformState, Proxy, audio_sdk, owned_helper, owned_listener, windows_sdk

def definitions():
    return tuple((definition for name in MODULE_NAMES for definition in importlib.import_module('hanni.tools.' + name).definitions()))
MUTATION_MOCKS = {'folder.open', 'app.open', 'browser.open_url', 'service.control', 'audio.status', 'audio.set_volume', 'audio.mute', 'display.brightness', 'power.set_plan', 'power.set_idle', 'power.battery_report'}

def arguments(name, root):
    values = {'process.inspect': {'pid': os.getpid()}, 'process.list': {'limit': 7}, 'process.top_memory': {'limit': 5}, 'process.top_cpu': {'limit': 5}, 'process.top_disk_io': {'limit': 5}, 'gpu.top_processes': {'limit': 5}, 'process.stop': {'pid': 0}, 'folder.open': {'path': str(root)}, 'app.open': {'app': str(root / 'fixture-app.txt')}, 'browser.open_url': {'url': 'http://127.0.0.1:9/campaign2-fixture'}, 'ui.focus_window': {'title': 'Campaign Two Fixture'}, 'app.list_installed': {'query': 'Python', 'limit': 7}, 'service.list': {'query': '', 'status': 'running', 'limit': 7}, 'service.control': {'name': 'Campaign2FixtureSvc', 'action': 'start'}, 'startup.list': {'limit': 7}, 'process.uptime': {'pid': os.getpid()}, 'audio.set_volume': {'percent': 36}, 'audio.mute': {'muted': True}, 'display.brightness': {'percent': 35}, 'spotify.search': {'query': 'amber observatory'}, 'spotify.open_uri': {'uri': 'spotify:track:CampaignTwoSynthetic'}, 'spotify.volume': {'percent': 31}, 'net.info': {'include_down': True}, 'net.ping': {'host': '127.0.0.1', 'count': 2}, 'net.dns_lookup': {'host': 'localhost'}, 'net.ports': {'limit': 100, 'loopback_only': True}, 'net.throughput': {'seconds': 1}, 'power.set_plan': {'guid': PLAN_B}, 'power.set_idle': {'target': 'sleep', 'minutes': 11}, 'power.battery_report': {'destination': str(root / 'battery-report.html')}, 'security.updates': {'limit': 7}, 'system.event_errors': {'hours': 1, 'limit': 5, 'log': 'Application'}, 'ui.windows_detailed': {'query': 'Campaign Two Fixture'}, 'ui.window_state': {'title': 'Campaign Two Fixture', 'state': 'maximize'}, 'ui.close_window': {'title': 'Campaign Two Fixture', 'all_matches': False}, 'env.list': {'query': 'HANNI_CAMPAIGN2', 'limit': 7}, 'env.get': {'name': ENV_NAME}, 'env.which': {'command': 'python.exe' if os.name == 'nt' else 'python'}}
    return values.get(name, {})

def prompt(name, args):
    text = {'process.inspect': f"Check whether the process with PID {args.get('pid')} is still running.", 'system.stats': 'Show measured CPU, RAM, and available GPU usage on this computer.', 'system.battery': "What is this computer's battery percentage and charging state?", 'process.list': 'List the seven processes using the largest share of memory.', 'process.top_memory': 'Which five applications currently consume the most resident RAM?', 'process.top_cpu': 'Which five applications currently use the most CPU?', 'process.top_disk_io': 'Which five processes currently have the highest disk read and write rates?', 'gpu.top_processes': 'Which five processes use the most GPU or dedicated GPU memory?', 'process.stop': f"Stop only my disposable audit helper with PID {args.get('pid')}.", 'folder.open': f"Open the existing audit directory {args.get('path')} in File Explorer.", 'app.open': f"Ask Windows to open the audit fixture file {args.get('app')}.", 'browser.open_url': f"Open {args.get('url')} in my default browser.", 'ui.active_window': 'What is the foreground window and which process owns it?', 'ui.list_windows': 'List the visible window titles on this computer.', 'ui.focus_window': 'Bring the window titled Campaign Two Fixture to the foreground.', 'app.list_installed': 'List up to seven installed programs matching Python and their versions.', 'service.list': 'List up to seven Windows services that are running.', 'service.control': 'Start the Windows service named Campaign2FixtureSvc; I confirm this service action.', 'startup.list': 'List up to seven programs configured to start when Windows starts.', 'system.os_info': 'Show the operating system version, architecture, CPU count, and hostname.', 'system.uptime': 'How long has this computer been running since its last boot?', 'process.uptime': f"How long has process {args.get('pid')} been running?", 'audio.status': 'Read the exact system volume and mute state if available.', 'audio.set_volume': 'Set the system volume to 36 percent; I confirm this change.', 'audio.mute': 'Mute system audio; I confirm this change.', 'media.play_pause': 'Send one system media play or pause key.', 'media.next_track': 'Send the system media next-track key.', 'media.previous_track': 'Send the system media previous-track key.', 'media.stop': 'Send the system media stop key.', 'display.info': 'List active display resolutions and refresh rates.', 'display.brightness': 'Set the built-in display brightness to 35 percent; I confirm this change.', 'spotify.status': 'What track and artist does the local Spotify window report?', 'spotify.launch': 'Start the Spotify desktop application if it is not running.', 'spotify.play_pause': 'Toggle playback once in the local Spotify client.', 'spotify.next': 'Skip to the next track in the local Spotify client.', 'spotify.previous': 'Go back to the previous track in the local Spotify client.', 'spotify.focus': 'Bring Spotify to the foreground.', 'spotify.search': 'Open a Spotify search for amber observatory without starting playback.', 'spotify.open_uri': f"Open the exact Spotify URI {args.get('uri')} in the desktop client.", 'spotify.volume': "Set Spotify's own application volume to 31 percent; I confirm this change.", 'net.info': 'Show my local network adapters and IP addresses, including adapters that are down.', 'net.wifi': 'Show my current Wi-Fi signal percentage and connection details.', 'net.ping': 'Send two ping probes to 127.0.0.1 and report measured latency and packet loss.', 'net.dns_lookup': 'Resolve localhost to its IP addresses.', 'net.ports': 'List up to 100 listening sockets bound to loopback and their owning processes.', 'net.throughput': "Measure this computer's network byte rates over one second without a speed test.", 'power.battery_detail': 'Read battery percentage, charging state, and estimated remaining time.', 'power.plans': 'List available Windows power plans and identify the active one.', 'power.set_plan': f"Activate power plan {args.get('guid')}; I confirm this change.", 'power.idle_settings': 'Read the AC screen-off and sleep timeouts in minutes.', 'power.set_idle': 'Set the AC sleep timeout to eleven minutes; I confirm this change.', 'power.battery_report': f"Generate a battery health report at {args.get('destination')}.", 'security.defender': 'Read Microsoft Defender real-time protection and signature freshness.', 'security.firewall': 'Read the status of every Windows Firewall profile.', 'security.bitlocker': 'Read BitLocker volume protection status without reading recovery keys.', 'security.updates': 'List the seven most recent installed Windows hotfixes.', 'security.pending_reboot': 'Is a Windows restart pending, and for which measured reasons?', 'system.event_errors': 'Show up to five Application log errors from the last hour.', 'device.audio': 'List audio endpoint devices and identify those reporting a working state.', 'device.bluetooth': 'List Bluetooth devices and identify connected ones.', 'device.usb': 'List USB devices and identify present devices reporting a problem.', 'device.printers': 'List installed printers and identify the default printer.', 'device.disk_health': 'Read physical disk health and report any hardware health warnings.', 'ui.windows_detailed': 'List windows matching Campaign Two Fixture with their owner process and minimized state.', 'ui.minimize_all': 'Minimize all visible windows to show the desktop.', 'ui.window_state': 'Maximize the window whose title contains Campaign Two Fixture.', 'ui.close_window': 'Politely close the Campaign Two Fixture window, allowing any save prompt.', 'env.list': 'List up to seven environment variables whose names contain HANNI_CAMPAIGN2.', 'env.get': f"Read the environment variable {args.get('name')} with normal credential redaction.", 'env.which': f"Which executable path resolves for {args.get('command')}?", 'env.path': 'Inspect PATH entries for duplicate and missing directories.', 'env.user_folders': 'Resolve the standard user folders and report which directories exist.'}
    return text[name]

def unavailable_error(*args, **kwargs):
    raise OSError('campaign2 controlled dependency unavailable')

@dataclass
class PlatformCase:
    definition: Any
    root: Path
    args: dict[str, Any]
    mode: str
    state: PlatformState | None = field(default=None, init=False)
    observations: list[dict[str, Any]] = field(default_factory=list, init=False)

    @property
    def query(self):
        return prompt(self.definition.name, self.args)

    @contextmanager
    def deps(self, args, unavailable=False, *, controlled=False, noop=False):
        name = self.definition.name
        module = importlib.import_module(self.definition.handler.__module__)
        state = PlatformState(self.root, name, unavailable=unavailable, noop=noop)
        state.controlled = controlled or self.mode == 'MOCK'
        self.state = state
        with ExitStack() as stack:
            if name.startswith(('ui.', 'spotify.', 'media.', 'audio.')):
                stack.enter_context(windows_sdk(state))
            if name.startswith(('spotify.', 'media.')) or name == 'ui.close_window':
                stack.enter_context(patch.object(module, 'time', Proxy(time, sleep=lambda _: None)))
            if name.startswith('audio.') or name == 'spotify.volume':
                stack.enter_context(audio_sdk(state, unavailable=unavailable))
            if state.controlled or unavailable:
                if hasattr(module, 'run_powershell'):
                    stack.enter_context(patch.object(module, 'run_powershell', state.shell))
                if hasattr(module, 'run_powershell_json'):
                    stack.enter_context(patch.object(module, 'run_powershell_json', state.shell_json))
            if name in {'folder.open', 'app.open'}:

                def popen(argv, **kwargs):
                    if unavailable:
                        unavailable_error()
                    state.calls.append(('Popen', list(argv)))
                    return SimpleNamespace(pid=45010)
                stack.enter_context(patch.object(module, 'subprocess', Proxy(subprocess, Popen=popen)))

                def startfile(path, *a, **kwargs):
                    if unavailable:
                        unavailable_error()
                    state.calls.append(('startfile', str(path)))
                stack.enter_context(patch.object(module, 'os', Proxy(os, startfile=startfile)))
            if name == 'browser.open_url':

                def open_url(url, **kwargs):
                    state.calls.append(('webbrowser.open', url, kwargs))
                    return not unavailable
                stack.enter_context(patch.object(module, 'webbrowser', Proxy(module.webbrowser, open=open_url)))
            if name == 'process.stop':
                stack.enter_context(owned_helper(state, args))
                if unavailable:

                    def absent(pid):
                        raise psutil.NoSuchProcess(pid)
                    stack.enter_context(patch.object(module, 'psutil', Proxy(psutil, Process=absent)))
            if name == 'net.ports' and (not unavailable):
                stack.enter_context(owned_listener(state))
            if name in {'env.list', 'env.get'}:
                environment = dict(os.environ)
                if unavailable:
                    environment.pop(ENV_NAME, None)
                else:
                    environment[ENV_NAME] = ENV_VALUE
                stack.enter_context(patch.object(module, 'os', Proxy(os, environ=environment)))
            if unavailable:
                overrides = {'system.battery': {'sensors_battery': lambda: None}, 'power.battery_detail': {'sensors_battery': lambda: None}, 'process.inspect': {'pid_exists': lambda _: False}, 'process.list': {'process_iter': unavailable_error}, 'process.top_memory': {'process_iter': unavailable_error}, 'process.top_cpu': {'process_iter': unavailable_error}, 'process.top_disk_io': {'process_iter': unavailable_error}, 'system.os_info': {'boot_time': unavailable_error}, 'system.uptime': {'boot_time': unavailable_error}, 'process.uptime': {'process_iter': lambda _: []}, 'net.info': {'net_if_stats': unavailable_error}, 'net.ports': {'net_connections': unavailable_error}, 'net.throughput': {'net_io_counters': unavailable_error}}.get(name)
                if overrides:
                    stack.enter_context(patch.object(module, 'psutil', Proxy(psutil, **overrides)))
                if name == 'system.stats':
                    resources = importlib.import_module('hanni.models.resource_manager')
                    stack.enter_context(patch.object(resources, 'psutil', Proxy(psutil, virtual_memory=unavailable_error)))
                if name == 'gpu.top_processes':
                    stack.enter_context(patch.object(module, 'subprocess', Proxy(subprocess, run=unavailable_error)))
                if name == 'net.dns_lookup':

                    def no_dns(*_):
                        raise socket.gaierror(socket.EAI_NONAME, 'controlled name unavailable')
                    stack.enter_context(patch.object(module, 'socket', Proxy(socket, getaddrinfo=no_dns)))
                if name == 'env.which':
                    stack.enter_context(patch.object(module, 'shutil', Proxy(shutil, which=lambda _: None)))
                if name in {'env.path', 'env.list'}:
                    stack.enter_context(patch.object(module, 'os', Proxy(os, environ={})))
                if name == 'env.user_folders':
                    stack.enter_context(patch.object(module, 'Path', Proxy(Path, home=unavailable_error)))
            yield state

    def verify(self, result, args):
        """Independent observations plus semantic arithmetic, not a schema echo."""
        name, data, state = (self.definition.name, result.data, self.state)
        errors = []
        self.observations = []

        def check(condition, message, observed=None, expected=True):
            self.observations.append({'check': message, 'passed': bool(condition), 'observed': bool(condition) if observed is None else observed, 'expected': expected})
            if not condition:
                errors.append(message)

        def equal(key, value):
            check(data.get(key) == value, f'{key}: observed {data.get(key)!r}, expected {value!r}', observed=data.get(key), expected=value)
        check(result.name == name, 'result belongs to a different capability')
        check(isinstance(data, dict), 'structured result data is required')
        if state is None:
            return errors + ["verification must run inside this case's dependency context"]
        if state.unavailable:
            return self._verify_unavailable(result, errors)
        if name == 'process.inspect':
            equal('pid', args['pid'])
            equal('exists', psutil.pid_exists(args['pid']))
        elif name == 'process.stop':
            check(state.helper is not None and state.helper.pid == args['pid'], 'target must be the exact owned helper')
            check(state.helper.poll() is not None and (not psutil.pid_exists(args['pid'])), 'owned helper survived the stop')
        elif name == 'system.stats':
            memory = psutil.virtual_memory()
            check(abs(data.get('ram_total_gb', 0) - memory.total / 1024 ** 3) < 0.01, 'RAM total differs from independent psutil read')
            check(0 <= data.get('cpu_percent', -1) <= 100, 'CPU percentage is invalid')
            check(0 <= data.get('ram_used_gb', -1) <= data.get('ram_total_gb', -2), 'RAM used exceeds total')
        elif name in {'system.battery', 'power.battery_detail'}:
            battery = psutil.sensors_battery()
            equal('available' if name == 'system.battery' else 'present', battery is not None)
            if battery is not None:
                check(abs(data.get('percent', -1) - battery.percent) <= 1, 'battery percentage differs from independent sensor')
                equal('power_plugged' if name == 'system.battery' else 'plugged_in', bool(battery.power_plugged))
        elif name.startswith('process.top_') or name == 'process.list':
            rows = data.get('processes', [])
            check(len(rows) <= args['limit'], 'process result exceeded the requested limit')
            sortkey = {'process.list': 'memory_percent', 'process.top_memory': 'rss_mb', 'process.top_cpu': 'cpu_percent', 'process.top_disk_io': 'total_bytes_per_second'}[name]
            amounts = [row.get(sortkey, 0) for row in rows]
            check(amounts == sorted(amounts, reverse=True), 'process rankings are not ordered by measured usage')
            if name == 'process.top_memory':
                for row in rows:
                    check(row['instances'] == len(row['pids']), 'memory aggregation lost PID instances')
                    check(abs(row['rss_gb'] - row['rss_mb'] / 1024) < 0.02, 'memory units disagree')
            if name == 'process.top_cpu':
                for row in rows:
                    check(0 <= row['cpu_percent'] <= 100, 'normalized CPU exceeded Task Manager scale')
            if name == 'process.top_disk_io':
                for row in rows:
                    check(row.get('read_bytes_per_second', 0) >= 0 and row.get('write_bytes_per_second', 0) >= 0, 'I/O rate must never be negative')
        elif name == 'gpu.top_processes':
            check(len(data.get('processes', [])) <= args['limit'], 'GPU process result exceeded the requested limit')
            for row in data.get('processes', []):
                check(row.get('gpu_percent') is None or 0 <= row['gpu_percent'] <= 100, 'GPU percent is invalid')
                check(row.get('vram_mb') is None or row['vram_mb'] >= 0, 'VRAM may be unknown, never negative')
        elif name == 'folder.open':
            equal('path', str(Path(args['path']).resolve()))
            equal('directory_verified', True)
            equal('window_verified', False)
            check(any((call[0] == 'Popen' and call[1][-1] == str(Path(args['path']).resolve()) for call in state.calls)), 'Explorer OS launch did not receive the verified directory as its own argv element')
        elif name == 'app.open':
            check(('startfile', args['app']) in state.calls, 'Windows shell adapter never received the requested path')
            equal('verified', False)
            equal('target', args['app'])
        elif name == 'browser.open_url':
            equal('url', args['url'])
            check(any((call[:2] == ('webbrowser.open', args['url']) for call in state.calls)), 'browser handoff was not made')
        elif name.startswith('ui.'):
            self._verify_windows(name, data, args, state, check, equal)
        elif name in {'app.list_installed', 'service.list', 'startup.list'}:
            key = {'app.list_installed': 'programs', 'service.list': 'services', 'startup.list': 'items'}[name]
            rows = data.get(key, [])
            check(len(rows) <= args['limit'] and data.get('total', -1) >= len(rows), 'inventory limits/counts disagree')
            if name == 'app.list_installed':
                for row in rows:
                    check(args['query'].casefold() in (row['name'] + ' ' + row['publisher']).casefold(), 'installed-app filter mismatch')
                equal('found', bool(data['total']))
            if name == 'service.list':
                for row in rows:
                    check(row['status'] == 'running', 'service state filter leaked a stopped service')
                check(data['running'] == data['total'], 'running filtered service counts disagree')
        elif name == 'service.control':
            equal('status', state.service_status.casefold())
            check(state.service_status == 'Running', 'service did not reach requested state')
            check(len([call for call in state.calls if call[0] == 'powershell_json']) >= 2, 'service control lacks separate readback')
        elif name in {'system.os_info', 'system.uptime'}:
            check(abs(data['uptime_seconds'] - (time.time() - psutil.boot_time())) < 3, 'uptime differs from independent boot clock')
            if name == 'system.os_info':
                equal('hostname', platform.node())
                equal('machine', platform.machine())
            else:
                check(data['days'] * 86400 + data['hours'] * 3600 + data['minutes'] * 60 <= data['uptime_seconds'] < data['days'] * 86400 + data['hours'] * 3600 + data['minutes'] * 60 + 60, 'uptime component arithmetic disagrees')
        elif name == 'process.uptime':
            rows = data.get('processes', [])
            check(any((row['pid'] == args['pid'] for row in rows)), 'owned current process was omitted')
            for row in rows:
                check(abs(row['running_seconds'] - (time.time() - psutil.Process(row['pid']).create_time())) < 3, 'process uptime differs from independent process creation clock')
        elif name in {'audio.status', 'audio.set_volume', 'audio.mute', 'spotify.volume'}:
            if name == 'audio.mute':
                equal('muted', state.volume.GetMute())
                check(state.volume.GetMute() is True, 'endpoint mute did not change')
            else:
                observed = round(state.volume.GetMasterVolume() * 100)
                equal('percent', observed)
                if 'percent' in args:
                    check(observed == args['percent'], 'requested audio volume was not observed at the SDK leaf')
            equal('precise', True)
        elif name.startswith('media.'):
            key = {'media.next_track': 176, 'media.previous_track': 177, 'media.stop': 178, 'media.play_pause': 179}[name]
            events = [call for call in state.calls if call[0] == 'keybd_event']
            check(events == [('keybd_event', key, 0), ('keybd_event', key, 2)], 'media command was not one matching press/release pair')
            equal('sent', True)
        elif name == 'display.brightness':
            equal('percent', state.brightness)
            check(state.brightness == args['percent'], 'panel brightness never reached requested level')
        elif name == 'display.info':
            rows = data.get('displays', [])
            equal('active_count', sum((bool(row['width']) for row in rows)))
            for row in rows:
                check(row['resolution'] == (f"{row['width']}x{row['height']}" if row['width'] and row['height'] else ''), 'display dimensions disagree')
            if state.controlled:
                check(any((row['refresh_hz'] == 75 and row['width'] == 1920 for row in rows)), 'controlled display observation lost')
        elif name.startswith('spotify.'):
            self._verify_spotify(name, data, args, state, check, equal)
        elif name == 'net.info':
            equal('online', None)
            equal('internet_verified', False)
            current = psutil.net_if_addrs()
            for row in data['adapters']:
                check(row['name'] in current, 'network adapter is absent from independent inventory')
                check(set(row['ipv4']) == {address.address for address in current[row['name']] if address.family == socket.AF_INET}, 'IPv4 observation differs')
        elif name == 'net.wifi':
            check(0 <= data['signal_percent'] <= 100, 'Wi-Fi signal is outside percentage range')
            if state.controlled:
                equal('ssid', 'Campaign2 Lab')
                equal('signal_percent', 83)
                equal('quality', 'strong')
        elif name == 'net.ping':
            equal('host', args['host'])
            equal('sent', args['count'])
            check(0 <= data['received'] <= data['sent'], 'ping reply count exceeded sent probes')
            equal('loss_percent', round((data['sent'] - data['received']) / data['sent'] * 100, 1))
            if state.controlled:
                equal('average_ms', 4)
                equal('min_ms', 2)
                equal('max_ms', 6)
        elif name == 'net.dns_lookup':
            equal('addresses', sorted({row[4][0] for row in socket.getaddrinfo(args['host'], None)}))
            equal('resolved', True)
        elif name == 'net.ports':
            rows = data.get('listeners', [])
            check(any((row['port'] == state.port and row['pid'] == os.getpid() for row in rows)), 'owned loopback listener was not observed')
            check(all((row['address'] in {'127.0.0.1', '::1'} for row in rows)), 'loopback filter leaked an external bind')
        elif name == 'net.throughput':
            equal('seconds', args['seconds'])
            equal('download_mbps', round(data['bytes_received'] / args['seconds'] / 125000, 2))
            equal('upload_mbps', round(data['bytes_sent'] / args['seconds'] / 125000, 2))
            check(data['bytes_received'] >= 0 and data['bytes_sent'] >= 0, 'network byte deltas became negative')
            check('not a speed test' in data['note'], 'local throughput is falsely described as internet capacity')
        elif name.startswith('power.'):
            self._verify_power(name, data, args, state, check, equal)
        elif name.startswith('security.') or name == 'system.event_errors':
            self._verify_security(name, data, args, state, check, equal)
        elif name.startswith('device.'):
            self._verify_devices(name, data, state, check, equal)
        elif name.startswith('env.'):
            self._verify_env(name, data, args, check, equal)
        else:
            errors.append('no semantic oracle for capability')
        return errors

    def _verify_windows(self, name, data, args, state, check, equal):
        if name == 'ui.active_window':
            row = state.windows[state.foreground]
            equal('hwnd', state.foreground)
            equal('title', row['title'])
            equal('process', row['process'])
        if name in {'ui.list_windows', 'ui.windows_detailed'}:
            expected = [row['title'] for row in state.windows.values() if not args.get('query') or args['query'].casefold() in row['title'].casefold()]
            check(sorted((row['title'] for row in data['windows'])) == sorted(expected), 'original Win32 callbacks omitted or invented a window')
        if name == 'ui.focus_window':
            check(state.foreground == 1001 and any((call[0] == 'SetForegroundWindow' for call in state.calls)), 'target window was never made foreground')
        if name == 'ui.minimize_all':
            equal('minimized', len(state.windows))
            check(all((row['minimized'] for row in state.windows.values())), 'one or more windows stayed visible')
        if name == 'ui.window_state':
            check(state.windows[1001]['state'] == args['state'], 'window SDK state does not match claimed applied state')
            equal('matched', 1)
        if name == 'ui.close_window':
            check(1001 not in state.windows, 'polite fixture window close was not observed')
            equal('still_open', [])
            check(any((call[0] == 'PostMessageW' for call in state.calls)), 'close message was not sent')

    def _verify_spotify(self, name, data, args, state, check, equal):
        if name == 'spotify.status':
            equal('running', True)
            equal('track', 'Amber Observatory')
            equal('artist', 'Fixture Artist')
            equal('playback_verified', False)
        elif name == 'spotify.launch':
            equal('started', state.spotify_running)
            equal('running', state.spotify_running)
            check(any((call[0] == 'powershell' and call[1] == name for call in state.calls)), 'client launch adapter was not invoked')
        elif name in {'spotify.play_pause', 'spotify.next', 'spotify.previous'}:
            equal('now_playing', state.windows[1002]['title'])
            check(any((call[0] == 'SendMessageTimeoutW' for call in state.calls)), 'no Spotify-specific playback message was sent')
            check(data['now_playing'] != 'Fixture Artist - Amber Observatory', 'fixture transport left the client title unchanged')
        elif name == 'spotify.focus':
            check(state.foreground == 1002, 'Spotify never became the foreground window')
            equal('focused', state.foreground == 1002)
        elif name in {'spotify.search', 'spotify.open_uri'}:
            expected = 'spotify:search:amber%20observatory' if name == 'spotify.search' else args['uri']
            equal('uri', expected)
            check(any((call[0] == 'powershell' and expected in call[2] for call in state.calls)), 'URI handoff did not use requested URI')
            if name == 'spotify.search':
                equal('played', False)

    def _verify_power(self, name, data, args, state, check, equal):
        if name == 'power.plans':
            active = [row for row in data['plans'] if row['active']]
            equal('active', active[0]['name'] if active else '')
            check(data['causal_status'] != 'verified', 'power plan alone cannot prove a slowdown')
            if state.controlled:
                check(any((row['guid'] == state.active_plan and row['active'] for row in data['plans'])), 'active fixture plan was lost')
        elif name == 'power.set_plan':
            check(state.active_plan == args['guid'], 'active plan SDK state did not reach requested GUID')
            equal('guid', state.active_plan)
            equal('active', 'Power saver')
        elif name == 'power.idle_settings':
            if state.controlled:
                equal('screen_off_minutes', state.screen_minutes)
                equal('sleep_minutes', state.sleep_minutes)
            else:
                check(all((data[key] >= -1 for key in ('screen_off_minutes', 'sleep_minutes'))), 'timeout measurement is invalid')
        elif name == 'power.set_idle':
            observed = state.screen_minutes if args['target'] == 'screen' else state.sleep_minutes
            check(observed == args['minutes'], 'idle timeout OS state never reached the requested value')
            equal('minutes', observed)
        elif name == 'power.battery_report':
            path = Path(args['destination'])
            equal('written', path.is_file())
            check(path.is_file() and 'Campaign2 synthetic battery health report' in path.read_text(encoding='utf-8'), 'report payload was not generated under isolated root')
            equal('size_kb', round(path.stat().st_size / 1024, 1))

    def _verify_security(self, name, data, args, state, check, equal):
        if name == 'security.defender':
            if state.controlled:
                equal('realtime_protection', True)
                equal('signature_version', '1.2.3')
            check(bool(data['signature_version']), 'Defender signature measurement unavailable')
        elif name == 'security.firewall':
            equal('all_enabled', all((row['enabled'] for row in data['profiles'])))
            equal('disabled_profiles', [row['profile'] for row in data['profiles'] if not row['enabled']])
            check(bool(data['profiles']), 'empty profile inventory cannot establish enabled firewall')
            if state.controlled:
                equal('disabled_profiles', ['Public'])
        elif name == 'security.bitlocker':
            equal('protected_volumes', [row['mount_point'] for row in data['volumes'] if row['protected']])
            if state.controlled:
                equal('protected_volumes', ['F:'])
        elif name == 'security.updates':
            check(len(data['updates']) <= args['limit'] and len(data['updates']) <= data['total'], 'hotfix limits/counts disagree')
            if state.controlled:
                check(data['updates'][0]['id'] == 'KB-C2', 'hotfix identity was lost')
        elif name == 'security.pending_reboot':
            equal('pending', bool(data['reasons']))
            if state.controlled:
                equal('pending', True)
                equal('reasons', ['windows update'])
        elif name == 'system.event_errors':
            equal('log', args['log'])
            equal('hours', args['hours'])
            check(len(data['events']) <= args['limit'] and len(data['events']) <= data['total'], 'event limits/counts disagree')
            if state.controlled:
                equal('providers', ['Campaign2Provider'])
                check(data['events'][0]['id'] == 17, 'event identity lost')

    def _verify_devices(self, name, data, state, check, equal):
        if name in {'device.audio', 'device.bluetooth', 'device.usb'}:
            rows = data['devices']
            selected = [row['name'] for row in rows if (row['present'] and (not row['connected']) if name == 'device.usb' else row['connected'])]
            equal({'device.audio': 'working', 'device.bluetooth': 'connected', 'device.usb': 'problem_devices'}[name], selected)
            if state.controlled:
                check(selected == (['Fixture broken'] if name == 'device.usb' else ['Fixture endpoint']), 'device state interpretation differs from fixture')
        elif name == 'device.printers':
            equal('default', next((row['name'] for row in data['printers'] if row['default']), ''))
            if state.controlled:
                equal('default', 'Fixture printer')
        elif name == 'device.disk_health':
            expected = [row['name'] for row in data['disks'] if row['health'].casefold() not in {'healthy', '0', ''}]
            equal('unhealthy', expected)
            if state.controlled:
                equal('unhealthy', ['Warning disk'])
                check(any((row['size_gb'] == 128 for row in data['disks'])), 'disk size conversion differs from source bytes')

    def _verify_env(self, name, data, args, check, equal):
        if name == 'env.get':
            equal('value', ENV_VALUE)
            equal('set', True)
        elif name == 'env.list':
            check(any((row['name'] == ENV_NAME and row['value'] == ENV_VALUE for row in data['variables'])), 'scoped fixture environment value was omitted')
            check(all((args['query'].casefold() in row['name'].casefold() for row in data['variables'])), 'environment name filter mismatch')
        elif name == 'env.which':
            equal('path', shutil.which(args['command']) or '')
            equal('found', bool(shutil.which(args['command'])))
        elif name == 'env.path':
            check(len({row['path'].casefold() for row in data['entries']}) == len(data['entries']), 'PATH duplicate was retained')
            for row in data['entries']:
                check(row['exists'] == Path(row['path']).is_dir(), 'PATH existence differs from filesystem')
            equal('missing', [row['path'] for row in data['entries'] if not Path(row['path']).is_dir()])
        elif name == 'env.user_folders':
            equal('home', str(Path.home()))
            for row in data['folders'].values():
                check(row['exists'] == Path(row['path']).is_dir(), 'standard folder existence differs from filesystem')
            equal('present', [name for name, row in data['folders'].items() if Path(row['path']).is_dir()])

    def _verify_unavailable(self, result, errors):
        data, name = (result.data, self.definition.name)

        def check(condition, message):
            self.observations.append({'check': message, 'passed': bool(condition), 'observed': bool(condition), 'expected': True})
            if not condition:
                errors.append(message)
        if name == 'audio.status':
            check(data.get('muted') is None and data.get('percent') == -1, 'missing audio measurement became a precise state')
        elif name == 'audio.set_volume':
            check(data.get('precise') is False, 'missing endpoint became exact volume')
        elif name == 'audio.mute':
            check(not result.ok and data.get('muted') is None, 'unknown endpoint was falsely muted')
        elif name == 'spotify.volume':
            check(not result.ok and data.get('percent') == -1, 'missing Spotify session became measured volume')
        elif name == 'system.battery':
            check(data.get('available') is False, 'missing battery was not disclosed')
        elif name == 'power.battery_detail':
            check(data.get('present') is False, 'missing battery was not disclosed')
        elif name == 'process.inspect':
            check(data.get('exists') is False, 'missing process was falsely present')
        elif name == 'process.uptime':
            check(not result.ok and data.get('found') is False, 'missing process became measured uptime')
        elif name == 'spotify.status':
            check(data.get('running') is False, 'absent client was reported running')
        elif name == 'gpu.top_processes':
            check(data.get('processes') == [], 'missing GPU measurements invented process usage')
        elif name in {'ui.list_windows', 'ui.windows_detailed'}:
            check(data.get('windows') == [], 'missing windows invented inventory')
        elif name == 'ui.minimize_all':
            check(data.get('minimized') == 0, 'missing windows became minimized count')
        elif name in {'ui.window_state', 'ui.close_window', 'browser.open_url', 'env.get', 'env.which', 'net.dns_lookup'}:
            check(not result.ok, 'unavailable target was claimed successful')
        elif name == 'env.list':
            check(data.get('variables') == [], 'absent environment invented variables')
        elif name == 'env.path':
            check(data.get('entries') == [], 'absent PATH invented entries')
        else:
            check(not result.ok, 'dependency failure was claimed successful')
        return errors

def case(definition, root):
    """Build one case from the dynamically enumerated original definition."""
    if definition.handler.__module__.rsplit('.', 1)[-1] not in MODULE_NAMES:
        raise KeyError(definition.name)
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / 'fixture-app.txt').write_text('Campaign2 isolated shell fixture\n', encoding='utf-8')
    name = definition.name
    mode = 'MOCK' if name in MUTATION_MOCKS or name.startswith(('ui.', 'media.', 'spotify.')) else 'LIVE'
    if name == 'process.stop' or name in {'env.list', 'env.get'}:
        mode = 'ISOLATED'
    return PlatformCase(definition, root, arguments(name, root), mode)
