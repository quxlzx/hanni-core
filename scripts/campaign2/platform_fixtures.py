"""OS/SDK dependency fixtures for the original platform capability handlers.

No ToolDefinition or registered handler is replaced. Win32 callbacks, audio
COM, PowerShell transport and module-local psutil access terminate at explicit
fixtures. These are MOCK evidence, never evidence of a host mutation.
"""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
import ctypes
import importlib
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import psutil
MODULE_NAMES = ('system', 'windows', 'apps', 'media', 'spotify', 'net', 'power', 'security', 'devices', 'uiextra', 'envtools')
PLAN_A = '381b4222-f694-41f0-9685-ff5bb260df2e'
PLAN_B = 'a1841308-3541-4fab-bc81-f71556f20b4a'
ENV_NAME = 'HANNI_CAMPAIGN2_FIXTURE'
ENV_VALUE = 'amber observatory'

class Proxy:
    """Override a module dependency locally without editing its global module."""

    def __init__(self, original, **overrides):
        self.original, self.overrides = (original, overrides)

    def __getattr__(self, key):
        return self.overrides[key] if key in self.overrides else getattr(self.original, key)

class Function:
    """A Python Win32 leaf callable with assignable ctypes signatures."""

    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)

def integer(value):
    return int(getattr(value, 'value', value) or 0)

class Volume:

    def __init__(self, state):
        self.state, self.level, self.muted = (state, 0.57, False)

    def GetMasterVolumeLevelScalar(self):
        return self.level

    def GetMasterVolume(self):
        return self.level

    def GetMute(self):
        return self.muted

    def SetMasterVolumeLevelScalar(self, level, _):
        self.state.calls.append(('endpoint.volume', level))
        if not self.state.noop:
            self.level = level

    def SetMasterVolume(self, level, _):
        self.state.calls.append(('spotify.volume', level))
        if not self.state.noop:
            self.level = level

    def SetMute(self, muted, _):
        self.state.calls.append(('endpoint.mute', bool(muted)))
        if not self.state.noop:
            self.muted = bool(muted)

class PlatformState:

    def __init__(self, root: Path, name: str, *, unavailable=False, noop=False):
        self.root, self.name, self.unavailable, self.noop = (root, name, unavailable, noop)
        self.calls = []
        self.volume = Volume(self)
        self.active_plan, self.screen_minutes, self.sleep_minutes = (PLAN_A, 5, 30)
        self.brightness, self.service_status = (68, 'Stopped')
        self.foreground, self.helper, self.listener = (1001, None, None)
        self.spotify_running = name != 'spotify.launch' and (not unavailable)
        self.windows = {1001: {'title': 'Campaign Two Fixture Window', 'pid': 45001, 'process': 'campaign2-fixture.exe', 'minimized': False, 'state': 'restore'}, 1002: {'title': 'Fixture Artist - Amber Observatory', 'pid': 45002, 'process': 'spotify.exe', 'minimized': False, 'state': 'restore'}} if not unavailable else {}
        self.user32 = self._user32()

    def _user32(self):

        def enum(callback, data):
            for hwnd in list(self.windows):
                callback(hwnd, data)
            return 1

        def text(hwnd, buffer, length):
            buffer.value = self.windows[integer(hwnd)]['title'][:integer(length) - 1]
            return len(buffer.value)

        def pid(hwnd, pointer):
            pointer._obj.value = self.windows[integer(hwnd)]['pid']
            return 1

        def show(hwnd, flag):
            self.calls.append(('ShowWindow', integer(hwnd), integer(flag)))
            if not self.noop:
                row = self.windows[integer(hwnd)]
                row['minimized'] = integer(flag) == 6
                row['state'] = {3: 'maximize', 6: 'minimize', 9: 'restore'}[integer(flag)]
            return 1

        def foreground(hwnd):
            self.calls.append(('SetForegroundWindow', integer(hwnd)))
            if self.noop or self.unavailable:
                return 0
            self.foreground = integer(hwnd)
            return 1

        def close(hwnd, message, *_):
            self.calls.append(('PostMessageW', integer(hwnd), integer(message)))
            assert integer(message) == 16, 'only the polite close message is permitted'
            if not self.noop:
                self.windows.pop(integer(hwnd), None)
            return 0 if self.unavailable else 1

        def transport(hwnd, message, source, command, flags, timeout, result):
            self.calls.append(('SendMessageTimeoutW', integer(hwnd), integer(command) >> 16))
            if self.unavailable:
                return 0
            if not self.noop:
                row = self.windows[integer(hwnd)]
                row['title'] = {11: 'Fixture Artist - Next Aurora', 12: 'Fixture Artist - Prior Solstice', 14: 'Spotify'}[integer(command) >> 16]
            return 1

        def keybd(key, scan, flags, extra):
            if self.unavailable:
                raise OSError('controlled keyboard dependency unavailable')
            self.calls.append(('keybd_event', integer(key), integer(flags)))
        return SimpleNamespace(EnumWindows=Function(enum), GetForegroundWindow=Function(lambda: self.foreground if self.windows else 0), IsWindowVisible=Function(lambda hwnd: integer(hwnd) in self.windows), GetWindowTextLengthW=Function(lambda hwnd: len(self.windows[integer(hwnd)]['title'])), GetWindowTextW=Function(text), GetWindowThreadProcessId=Function(pid), IsIconic=Function(lambda hwnd: self.windows[integer(hwnd)]['minimized']), IsZoomed=Function(lambda hwnd: self.windows[integer(hwnd)]['state'] == 'maximize'), ShowWindow=Function(show), SetForegroundWindow=Function(foreground), PostMessageW=Function(close), SendMessageTimeoutW=Function(transport), keybd_event=Function(keybd))

    def process(self, pid):
        wanted = integer(pid)
        row = next((row for row in self.windows.values() if row['pid'] == wanted), None)
        if row is None:
            raise psutil.NoSuchProcess(wanted)
        return SimpleNamespace(pid=wanted, name=lambda: row['process'], info={'pid': wanted, 'name': row['process'], 'create_time': time.time() - 120})

    def processes(self, attrs):
        if not self.spotify_running:
            return []
        return [self.process(45002)]

    def shell(self, command, **kwargs):
        capability = kwargs.get('capability')
        self.calls.append(('powershell', capability, command))
        if self.unavailable:
            raise OSError('controlled PowerShell dependency unavailable')
        if capability == 'power.plans':
            return '\n'.join((f"Power Scheme GUID: {guid} ({title}){(' *' if self.active_plan == guid else '')}" for guid, title in ((PLAN_A, 'Balanced'), (PLAN_B, 'Power saver'))))
        if capability == 'power.set_plan':
            assert command.startswith('powercfg /setactive ')
            guid = command.split()[-1].strip("'")
            if not self.noop:
                self.active_plan = guid
            return ''
        if capability == 'power.idle_settings':
            return '\n'.join((f'Current AC Power Setting Index: 0x{value * 60:08x}' for value in (self.screen_minutes, self.sleep_minutes)))
        if capability == 'power.set_idle':
            match = re.fullmatch('powercfg /change (monitor|standby)-timeout-ac (\\d+)', command)
            assert match, 'unexpected power mutation template'
            if not self.noop:
                setattr(self, 'screen_minutes' if match[1] == 'monitor' else 'sleep_minutes', int(match[2]))
            return ''
        if capability == 'power.battery_report':
            prefix = 'powercfg /batteryreport /output '
            assert command.startswith(prefix)
            path = Path(command[len(prefix):].strip("'").replace("''", "'"))
            assert path.resolve().is_relative_to(self.root.resolve()), 'report escaped fixture root'
            if not self.noop:
                path.write_text('<html><body>Campaign2 synthetic battery health report</body></html>', encoding='utf-8')
            return ''
        if capability and capability.startswith('spotify.'):
            assert command.startswith("Start-Process -FilePath 'spotify:")
            if not self.noop:
                self.spotify_running = True
            return ''
        if capability == 'net.wifi':
            return 'State : connected\nSSID : Campaign2 Lab\nSignal : 83%\nRadio type : 802.11ax'
        raise AssertionError(f'unhandled controlled shell request {capability}: {command}')

    def shell_json(self, command, **kwargs):
        capability = kwargs.get('capability')
        self.calls.append(('powershell_json', capability, command))
        if self.unavailable:
            raise OSError('controlled PowerShell dependency unavailable')
        if capability == 'service.control':
            assert 'Campaign2FixtureSvc' in command
            if not self.noop:
                if 'Start-Service' in command or 'Restart-Service' in command:
                    self.service_status = 'Running'
                if 'Stop-Service' in command:
                    self.service_status = 'Stopped'
            return {'Name': 'Campaign2FixtureSvc', 'Status': self.service_status}
        if capability == 'display.brightness':
            if 'WmiSetBrightness' in command:
                match = re.search('WmiSetBrightness\\(1, (\\d+)\\)', command)
                assert match
                if not self.noop:
                    self.brightness = int(match[1])
                return {'ok': True}
            return {'CurrentBrightness': self.brightness}
        if capability == 'audio.status':
            return [{'Name': 'Fixture output', 'Status': 'OK'}]
        values = {'app.list_installed': [{'DisplayName': 'Python Campaign2 Editor', 'DisplayVersion': '2.7', 'Publisher': 'Campaign2 Labs'}, {'DisplayName': 'Unrelated App', 'DisplayVersion': '1.0', 'Publisher': 'Other'}], 'service.list': [{'Name': 'Campaign2FixtureSvc', 'DisplayName': 'Fixture service', 'Status': 4, 'StartType': 2}, {'Name': 'OtherSvc', 'DisplayName': 'Other', 'Status': 1, 'StartType': 3}], 'startup.list': [{'Name': 'Fixture autostart', 'Command': 'fixture.exe', 'Location': 'Fixture', 'User': 'synthetic'}], 'display.info': [{'Name': 'Fixture display', 'CurrentHorizontalResolution': 1920, 'CurrentVerticalResolution': 1080, 'CurrentRefreshRate': 75, 'AdapterRAM': 2 * 1024 ** 3}], 'net.ping': [{'latency': 2}, {'latency': 6}], 'security.defender': {'AMServiceEnabled': True, 'AntivirusEnabled': True, 'RealTimeProtectionEnabled': True, 'AntivirusSignatureVersion': '1.2.3', 'AntivirusSignatureLastUpdated': '2026-10-09T12:00:00'}, 'security.firewall': [{'Name': 'Domain', 'Enabled': True, 'DefaultInboundAction': 4}, {'Name': 'Public', 'Enabled': False, 'DefaultInboundAction': 2}], 'security.bitlocker': [{'MountPoint': 'F:', 'VolumeStatus': 'FullyEncrypted', 'ProtectionStatus': 'On', 'EncryptionPercentage': 100}], 'security.updates': [{'HotFixID': 'KB-C2', 'Description': 'Synthetic hotfix', 'InstalledOn': '2026-10-09'}], 'security.pending_reboot': {'cbs': False, 'wu': True, 'rename': False}, 'system.event_errors': [{'TimeCreated': '2026-10-09T12:00:00', 'Id': 17, 'ProviderName': 'Campaign2Provider', 'LevelDisplayName': 'Error', 'Message': 'Synthetic hardware event'}], 'device.printers': [{'Name': 'Fixture printer', 'PrinterStatus': 'Normal', 'Default': True, 'PortName': 'fixture:'}], 'device.disk_health': [{'FriendlyName': 'Fixture SSD', 'MediaType': 'SSD', 'HealthStatus': 'Healthy', 'OperationalStatus': 'OK', 'Size': 128 * 1024 ** 3}, {'FriendlyName': 'Warning disk', 'MediaType': 'HDD', 'HealthStatus': 'Unhealthy', 'OperationalStatus': 'Degraded', 'Size': 64 * 1024 ** 3}]}
        if capability in {'device.audio', 'device.bluetooth', 'device.usb'}:
            return [{'FriendlyName': 'Fixture endpoint', 'Status': 'OK', 'Present': True, 'InstanceId': 'C2:A'}, {'FriendlyName': 'Fixture broken', 'Status': 'Error', 'Present': True, 'InstanceId': 'C2:B'}]
        if capability in values:
            return values[capability]
        raise AssertionError(f'unhandled controlled JSON request {capability}: {command}')

@contextmanager
def windows_sdk(state):
    """Drive original Win32 enumeration and control through synthetic OS leaves."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(ctypes.windll, 'user32', state.user32))
        original = ctypes.WinDLL
        stack.enter_context(patch.object(ctypes, 'WinDLL', lambda library, *a, **k: state.user32 if str(library).casefold() == 'user32' else original(library, *a, **k)))
        for name in ('windows', 'spotify', 'uiextra'):
            module = importlib.import_module('hanni.tools.' + name)
            stack.enter_context(patch.object(module, 'psutil', Proxy(psutil, Process=state.process, process_iter=state.processes)))
        yield

@contextmanager
def audio_sdk(state, *, unavailable=False):
    """Fake optional COM SDK; original imports, endpoint lookup and handlers run."""
    package, sdk, comtypes = (ModuleType('pycaw'), ModuleType('pycaw.pycaw'), ModuleType('comtypes'))
    endpoint_interface = type('IAudioEndpointVolume', (), {'_iid_': 'fixture-interface'})
    session_interface = type('ISimpleAudioVolume', (), {})
    sdk.IAudioEndpointVolume, sdk.ISimpleAudioVolume = (endpoint_interface, session_interface)

    def speakers():
        if unavailable:
            raise OSError('controlled endpoint unavailable')
        return SimpleNamespace(Activate=lambda *_: state.volume)
    sessions = [] if unavailable else [SimpleNamespace(Process=SimpleNamespace(name=lambda: 'spotify.exe'), _ctl=SimpleNamespace(QueryInterface=lambda *_: state.volume))]
    sdk.AudioUtilities = SimpleNamespace(GetSpeakers=speakers, GetAllSessions=lambda: sessions)
    package.pycaw, comtypes.CLSCTX_ALL = (sdk, 23)
    original_cast, original_pointer = (ctypes.cast, ctypes.POINTER)

    def pointer(kind):
        return kind if kind in (endpoint_interface, session_interface) else original_pointer(kind)

    def cast(value, kind):
        return value if kind in (endpoint_interface, session_interface) else original_cast(value, kind)
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules, {'pycaw': package, 'pycaw.pycaw': sdk, 'comtypes': comtypes}))
        stack.enter_context(patch.object(ctypes, 'cast', cast))
        stack.enter_context(patch.object(ctypes, 'POINTER', pointer))
        yield

@contextmanager
def owned_helper(state, arguments):
    """The only real process mutation: create and close this exact owned Popen."""
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'], cwd=state.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state.helper = process
    arguments['pid'] = process.pid
    try:
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

@contextmanager
def owned_listener(state):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    state.listener = listener
    state.port = listener.getsockname()[1]
    try:
        yield
    finally:
        listener.close()
