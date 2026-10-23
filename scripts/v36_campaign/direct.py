"""Resumable real-registry campaign. Only dependency leaves are simulated.

Raw evidence stays in ignored data. Each mutation is scoped to this campaign's
directory or an explicit fake OS/provider dependency. Production handlers,
argument validators, authorization, confirmation, audit and stop stay intact.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hanni.config.loader import load_config
from hanni.tools.base import ToolRequest, ToolValidationError, ToolPermissionError
from hanni.tools.registry import build_default_registry
from scripts.v36_engineering.fixtures import GoogleProvider, GoogleVault, prepare_files

OS_MOCKS = {
    'app.open', 'browser.open_url', 'clipboard.read', 'clipboard.write',
    'audio.mute', 'audio.set_volume', 'file.open', 'folder.open', 'notify.toast',
    'timer.set',
    'power.set_idle', 'power.set_plan', 'service.control',
    'ui.active_window', 'ui.close_window', 'ui.focus_window', 'ui.list_windows',
    'ui.minimize_all', 'ui.window_state', 'ui.windows_detailed',
    'media.next_track', 'media.play_pause', 'media.previous_track', 'media.stop',
    'spotify.focus', 'spotify.launch', 'spotify.next', 'spotify.open_uri',
    'spotify.play_pause', 'spotify.previous', 'spotify.search', 'spotify.volume',
}
ISOLATED_PREFIXES = ('file.', 'archive.', 'note.', 'todo.', 'git.', 'text.',
                     'calc.', 'unit.', 'random.', 'id.', 'project.')


def arguments(f):
    """Frozen ordinary scenario definitions; literal objectives precede execution."""
    folder, sample = f['folder'], f['file']
    tomorrow = datetime.now().astimezone().date() + timedelta(days=1)
    calendar = {'account': 'personal'}
    agenda = dict(calendar, start_date=tomorrow.isoformat(), days=1)
    create = dict(calendar, calendar_id='primary', summary='V36 direct event',
                  all_day=False, start=f'{tomorrow}T16:00:00-04:00',
                  end=f'{tomorrow}T17:00:00-04:00')
    values = {
        'app.list_installed': {'query': 'Python', 'limit': 20},
        'app.open': {'app': sample},
        'archive.list': {'archive': f['zip']},
        'archive.unzip': {'archive': f['zip'], 'destination': f['extract']},
        'archive.zip': {'source': folder, 'destination': f['newzip']},
        'audio.mute': {'muted': True}, 'audio.set_volume': {'percent': 32},
        'browser.open_url': {'url': 'http://127.0.0.1/'},
        'calc.evaluate': {'expression': '23% of 840'},
        'clipboard.write': {'text': 'cobalt lighthouse'},
        'disk.cleanup_temp': {'apply': False, 'older_than_days': 30},
        'disk.folder_size': {'path': folder},
        'disk.free_space': {'drive': 'C', 'needed_gb': 2},
        'disk.largest_files': {'root': folder, 'limit': 3, 'min_mb': 0},
        'disk.largest_folders': {'root': folder}, 'disk.usage': {'drive': 'C'},
        'display.brightness': {},
        'env.get': {'name': 'HANNI_V36_FIXTURE'},
        'env.list': {'query': 'HANNI_V36'}, 'env.which': {'command': 'git'},
        'file.compare': {'left': sample, 'right': f['other']},
        'file.composition': {'root': folder},
        'file.copy': {'source': sample, 'destination': f['copy']},
        'file.delete': {'path': f['delete']},
        'file.duplicates': {'root': folder, 'min_kb': 0},
        'file.empty_folders': {'root': folder},
        'file.grep': {'root': folder, 'query': 'cobalt lighthouse'},
        'file.head': {'path': sample, 'lines': 2},
        'file.list_dir': {'path': folder},
        'file.locate': {'name': 'sample.txt', 'root': folder},
        'file.mkdir': {'path': f['newfolder']},
        'file.move': {'source': f['copy'], 'destination': f['moved']},
        'file.open': {'path': sample}, 'file.read': {'path': sample},
        'file.recent': {'root': folder, 'hours': 24},
        'file.search': {'root': folder, 'query': 'sample'},
        'file.stat': {'path': sample, 'hash': True},
        'file.tail': {'path': sample, 'lines': 2},
        'file.write': {'path': f['written'], 'text': 'cobalt lighthouse'},
        'folder.open': {'path': folder},
        'gpu.top_processes': {'limit': 5},
        'hanni.audit_tail': {'limit': 5},
        'hanni.capabilities': {'goal': 'inspect files', 'limit': 5},
        'id.generate': {'kind': 'uuid4'},
        'net.dns_lookup': {'host': 'localhost'},
        'net.info': {'include_down': True}, 'net.ping': {'host': '127.0.0.1', 'count': 1},
        'net.ports': {'limit': 10, 'loopback_only': True},
        'net.throughput': {'seconds': 1},
        'note.append': {'text': 'V36 direct cobalt lighthouse', 'tag': 'v36'},
        'note.days': {'limit': 10},
        'note.list': {'limit': 10}, 'note.search': {'query': 'cobalt lighthouse'},
        'notify.toast': {'title': 'V36 fixture', 'message': 'cobalt lighthouse'},
        'power.battery_report': {'destination': f['battery']},
        'power.set_idle': {'target': 'sleep', 'minutes': 10},
        'power.set_plan': {'guid': '381b4222-f694-41f0-9685-ff5bb260df2e'},
        'powershell.run': {'command': "Write-Output 'HANNI_V36_BENIGN'", 'timeout': 5},
        'process.find': {'name': 'python', 'limit': 10},
        'process.inspect': {'pid': os.getpid()},
        'process.list': {'limit': 10}, 'process.top_cpu': {'limit': 5},
        'process.top_disk_io': {'limit': 5}, 'process.top_memory': {'limit': 5},
        'process.uptime': {'pid': os.getpid()},
        'project.format': {'root': f['project'], 'apply': False, 'timeout': 10},
        'project.lint': {'root': f['project'], 'timeout': 10},
        'project.test': {'root': f['project'], 'target': 'test_sample.py', 'timeout': 20},
        'python.env_info': {'query': 'pytest'},
        'random.number': {'minimum': 1, 'maximum': 4},
        'random.pick': {'options': ['cobalt', 'teal', 'white'], 'count': 2},
        'schedule.list_tasks': {'limit': 10}, 'security.updates': {'limit': 5},
        'service.control': {'name': 'HanniV36FixtureService', 'action': 'start'},
        'service.list': {'query': 'Audio', 'limit': 5},
        'spotify.open_uri': {'uri': 'spotify:track:v36synthetic'},
        'spotify.search': {'query': 'cobalt lighthouse'},
        'spotify.volume': {'percent': 32},
        'startup.list': {'limit': 5},
        'system.event_errors': {'hours': 1, 'limit': 5, 'log': 'Application'},
        'text.hash': {'text': 'cobalt lighthouse', 'algorithm': 'sha256'},
        'text.normalize': {'text': 'Cobalt   Lighthouse!', 'mode': 'slug'},
        'text.stats': {'text': 'Cobalt lighthouse. Rehearsal Friday.'},
        'time.convert': {'when': '2026-10-09T16:00:00', 'from_timezone': 'America/New_York', 'to_timezone': 'UTC'},
        'time.elapsed': {'since': (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()},
        'time.now': {'timezone': 'UTC'},
        'timer.set': {'duration': '5 seconds', 'label': 'V36 fixture'},
        'todo.add': {'title': 'V36 direct cobalt lighthouse', 'due': 'tomorrow'},
        'todo.complete': {'id': f['todo']}, 'todo.due': {'days': 7},
        'todo.get': {'id': f['todo']}, 'todo.list': {'status': 'all'},
        'ui.close_window': {'title': 'HANNI V36 fixture'},
        'ui.focus_window': {'title': 'HANNI V36 fixture'},
        'ui.window_state': {'title': 'HANNI V36 fixture', 'state': 'maximize'},
        'ui.windows_detailed': {'query': 'HANNI V36 fixture'},
        'unit.convert': {'value': 32, 'from_unit': 'f', 'to_unit': 'c'},
    }
    for name in ('branches', 'diff', 'log', 'status'):
        values['git.'+name] = {'root': f['git']}
    for name in ('google.calendar.events', 'google_calendar.agenda'):
        values[name] = dict(agenda)
    values['google.calendar.availability'] = dict(agenda, availability_start='14:00', availability_end='15:00')
    for name in ('google.calendar.list_calendars', 'google.calendar.next', 'google_calendar.list', 'google_calendar.next'):
        values[name] = dict(calendar)
    for name in ('google.calendar.create', 'google_calendar.create'):
        values[name] = dict(create)
    for name in ('google.calendar.read', 'google.calendar.delete', 'google.calendar.update'):
        values[name] = dict(calendar, calendar_id='primary', id='event-v36')
    values['google.calendar.update']['summary'] = 'V36 revised event'
    for name in ('gmail.read', 'google.gmail.read', 'email.read'):
        values[name] = dict(calendar, id='message-v36')
    for name in ('gmail.search', 'google.gmail.search', 'email.search'):
        values[name] = dict(calendar, query='rehearsal', limit=5)
    values['google.gmail.thread'] = dict(calendar, id='thread-v36')
    values['google.gmail.recent'] = dict(calendar, limit=5)
    for name in ('google.drive.list', 'google.drive.recent'):
        values[name] = dict(calendar, limit=5)
    values['google.drive.search'] = dict(calendar, query='Rehearsal', limit=5)
    for name in ('google.drive.metadata', 'google.docs.read'):
        values[name] = dict(calendar, id='doc-v36')
    values['google.tasks.list'] = dict(calendar, tasklist_id='list-v36')
    values['google.tasks.create'] = dict(calendar, tasklist_id='list-v36', title='V36 direct task')
    values['google.tasks.complete'] = dict(calendar, tasklist_id='list-v36', id='task-v36')
    return values


class Volume:
    def __init__(self):
        self.level, self.muted = .5, False
    def GetMasterVolumeLevelScalar(self): return self.level
    def SetMasterVolumeLevelScalar(self, value, _): self.level = value
    def GetMute(self): return self.muted
    def SetMute(self, value, _): self.muted = bool(value)
    def GetMasterVolume(self): return self.level
    def SetMasterVolume(self, value, _): self.level = value


class Fn:
    def __init__(self, function): self.function = function
    def __call__(self, *args): return self.function(*args)


class TimerFixture:
    """Scheduling boundary: no background thread can emit a real notification."""
    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.daemon, self.started = seconds, callback, False, False
    def start(self): self.started = True
    def cancel(self): self.started = False


class OSFixture:
    def __init__(self):
        self.events, self.clipboard, self.volume = [], 'cobalt lighthouse', Volume()
        self.window = {'hwnd': 12345, 'title': 'HANNI V36 fixture', 'pid': os.getpid(), 'process': 'python.exe', 'minimized': False}
        self.spotify = {'hwnd': 12345, 'title': 'Fixture Artist - Cobalt Lighthouse'}
        self.closed = False
        self.timer = None
        self.user32 = SimpleNamespace(
            ShowWindow=Fn(self.window_state), PostMessageW=Fn(self.close_window),
            SetForegroundWindow=Fn(lambda hwnd: self.event('focus', hwnd)),
            GetForegroundWindow=Fn(lambda: 12345),
            GetWindowTextLengthW=Fn(lambda hwnd: len(self.window['title'])),
            GetWindowTextW=Fn(self.window_text),
            GetWindowThreadProcessId=Fn(self.process_id),
            IsWindowVisible=Fn(lambda hwnd: True),
            IsIconic=Fn(lambda hwnd: False), EnumWindows=Fn(self.enum_windows),
            SendMessageTimeoutW=Fn(self.media_message))
    def event(self, *args): self.events.append(args); return 1
    def window_state(self, hwnd, flag): return self.event('window_state', hwnd, flag)
    def close_window(self, *args): self.closed = True; return self.event('close', *args)
    def window_text(self, hwnd, buffer, length): buffer.value = self.window['title']; return len(buffer.value)
    def process_id(self, hwnd, pointer): pointer._obj.value = os.getpid(); return 1
    def enum_windows(self, callback, extra): callback(12345, extra); return 1
    def media_message(self, *args):
        self.spotify['title'] = 'Fixture Artist - Next Cobalt Track'
        return self.event('media_message', *args[:6])
    def schedule(self, seconds, callback):
        self.timer = TimerFixture(seconds, callback)
        return self.timer
    def powershell(self, command, **kw):
        capability = kw.get('capability')
        self.events.append(('powershell', capability, command))
        if capability == 'clipboard.read': return self.clipboard
        if capability == 'clipboard.write':
            self.clipboard = command.split("-Value '", 1)[1].rsplit("'", 1)[0].replace("''", "'")
        if capability in {'power.set_plan', 'power.plans'}:
            return 'Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e (Balanced) *'
        return ''
    def powershell_json(self, command, **kw):
        self.events.append(('powershell_json', kw.get('capability'), command))
        if kw.get('capability') == 'service.control': return {'Name': 'HanniV36FixtureService', 'Status': 'Running'}
        raise AssertionError('Unspecified OS JSON fixture')


@contextmanager
def seams(name, fixture):
    """Patch only consequential external OS calls, never definitions/handlers."""
    with ExitStack() as stack:
        if name in {'clipboard.read', 'clipboard.write'}:
            stack.enter_context(patch('hanni.tools.content.run_powershell', fixture.powershell))
        if name in {'power.set_idle', 'power.set_plan'}:
            stack.enter_context(patch('hanni.tools.power.run_powershell', fixture.powershell))
        if name == 'service.control':
            stack.enter_context(patch('hanni.tools.apps.run_powershell_json', fixture.powershell_json))
        if name in {'audio.mute', 'audio.set_volume'}:
            stack.enter_context(patch('hanni.tools.media._endpoint_volume', lambda: fixture.volume))
        if name.startswith('media.'):
            stack.enter_context(patch('hanni.tools.media.press_key', lambda code, **kw: fixture.event('media_key', code)))
        if name == 'notify.toast':
            stack.enter_context(patch('hanni.tools.timekeep.run_powershell', fixture.powershell))
        if name == 'timer.set':
            stack.enter_context(patch('hanni.tools.timekeep.threading.Timer', fixture.schedule))
            stack.enter_context(patch('hanni.tools.timekeep.run_powershell', fixture.powershell))
        if name == 'browser.open_url':
            stack.enter_context(patch('hanni.tools.windows.webbrowser.open', lambda *a, **kw: fixture.event('browser', *a)))
        if name == 'app.open':
            stack.enter_context(patch('hanni.tools.windows._start_file', lambda path: fixture.event('start_file', str(path))))
        if name == 'folder.open':
            stack.enter_context(patch('hanni.tools.windows.subprocess.Popen', lambda *a, **kw: fixture.event('popen', *a)))
        if name == 'file.open':
            stack.enter_context(patch('os.startfile', lambda path: fixture.event('start_file', path)))
        if name.startswith('ui.') or (name.startswith('spotify.') and name != 'spotify.status'):
            stack.enter_context(patch('ctypes.windll.user32', fixture.user32))
            stack.enter_context(patch('ctypes.WinDLL', lambda *a, **kw: fixture.user32))
        if name.startswith('ui.'):
            stack.enter_context(patch('hanni.tools.uiextra._windows_with_processes', lambda: [] if fixture.closed else [dict(fixture.window)]))
        if name.startswith('spotify.') and name != 'spotify.status':
            stack.enter_context(patch('hanni.tools.spotify._client_processes', lambda: [{'pid': os.getpid(), 'name': 'Spotify.exe'}]))
            stack.enter_context(patch('hanni.tools.spotify._client_window', lambda: dict(fixture.spotify)))
            stack.enter_context(patch('hanni.tools.spotify.run_powershell', fixture.powershell))
        if name == 'spotify.volume':
            import ctypes
            class SimpleAudioInterface(ctypes.Structure):
                _fields_=[]
            package=ModuleType('pycaw');package.__path__=[]
            api=ModuleType('pycaw.pycaw')
            session=SimpleNamespace(Process=SimpleNamespace(name=lambda:'Spotify.exe'),
                _ctl=SimpleNamespace(QueryInterface=lambda _:fixture.volume))
            api.AudioUtilities=SimpleNamespace(GetAllSessions=lambda:[session])
            api.ISimpleAudioVolume=SimpleAudioInterface
            stack.enter_context(patch.dict(sys.modules,{'pycaw':package,'pycaw.pycaw':api}))
            stack.enter_context(patch('ctypes.cast',lambda value,_:value))
        yield


def contract_errors(definition, result):
    types = {'array': list, 'object': dict, 'string': str, 'boolean': bool,
             'integer': int, 'number': (int, float)}
    errors = []
    for key, description in definition.output_schema.items():
        if 'optional' in description: continue
        if key not in result.data:
            errors.append('missing:'+key)
        elif description in types:
            value = result.data[key]
            if not isinstance(value, types[description]) or (description in {'integer', 'number'} and isinstance(value, bool)):
                errors.append('type:'+key)
    return errors


def verify(name, result, f, fixture):
    """Outcome assertions independent of result.ok. Not an output-only smoke test."""
    data = result.data
    if name == 'calc.evaluate': assert abs(data['value']-193.2) < 1e-9
    elif name == 'unit.convert': assert abs(data['converted']) < 1e-9
    elif name == 'text.hash': assert data['digest'] == hashlib.sha256(b'cobalt lighthouse').hexdigest()
    elif name == 'text.normalize': assert data['result'] == 'cobalt-lighthouse'
    elif name == 'text.stats': assert data['words'] == 4 and data['characters'] == len('Cobalt lighthouse. Rehearsal Friday.')
    elif name == 'random.number': assert 1 <= data['value'] <= 4
    elif name == 'random.pick': assert len(set(data['picked'])) == 2 and set(data['picked']) <= {'cobalt', 'teal', 'white'}
    elif name == 'id.generate': assert uuid.UUID(data['value']).version == 4
    elif name == 'file.read': assert data['text'] == Path(f['file']).read_text(encoding='utf-8')
    elif name == 'file.head': assert data['lines'] == Path(f['file']).read_text().splitlines()[:2]
    elif name == 'file.tail': assert data['lines'] == Path(f['file']).read_text().splitlines()[-2:]
    elif name == 'file.stat': assert data['sha256'] == hashlib.sha256(Path(f['file']).read_bytes()).hexdigest()
    elif name == 'file.compare': assert not data['identical'] and any('Saturday' in line for line in data['diff'])
    elif name == 'file.copy': assert Path(f['copy']).read_bytes() == Path(f['file']).read_bytes()
    elif name == 'file.move': assert not Path(f['copy']).exists() and Path(f['moved']).read_bytes() == Path(f['file']).read_bytes()
    elif name == 'file.delete': assert not Path(f['delete']).exists()
    elif name == 'file.write': assert Path(f['written']).read_text() == 'cobalt lighthouse'
    elif name == 'file.mkdir': assert Path(f['newfolder']).is_dir()
    elif name == 'file.search': assert any('sample.txt' in str(row) for row in data['matches'])
    elif name == 'file.locate': assert len(data['matches']) == 1 and Path(data['matches'][0]['path']).resolve() == Path(f['file']).resolve()
    elif name == 'file.grep': assert data['match_count'] >= 2 and all('cobalt lighthouse' in str(row) for row in data['matches'])
    elif name == 'file.duplicates': assert any(row['copies'] >= 2 for row in data['groups'])
    elif name == 'file.empty_folders': assert any(Path(row).name == 'empty' for row in data['folders'])
    elif name == 'archive.list': assert data['entry_count'] == 1
    elif name == 'archive.unzip': assert (Path(f['extract'])/'sample.txt').read_bytes() == Path(f['file']).read_bytes()
    elif name == 'archive.zip':
        with ZipFile(f['newzip']) as archive:
            assert any(Path(name).name == 'sample.txt' for name in archive.namelist())
    elif name == 'disk.largest_files': assert data['files'] and Path(data['files'][0]['path']).name == 'data.bin'
    elif name == 'env.get': assert data['value'] == 'cobalt lighthouse'
    elif name == 'net.dns_lookup': assert data['resolved'] and bool({'127.0.0.1', '::1'} & set(data['addresses']))
    elif name == 'net.ping': assert data['received'] == 1
    elif name == 'time.convert': assert datetime.fromisoformat(data['converted_iso']) == datetime(2026,10,9,20,tzinfo=timezone.utc)
    elif name == 'process.inspect': assert data['exists'] and data['pid'] == os.getpid()
    elif name == 'process.stop': assert f['_helper'].poll() is not None
    elif name == 'project.test': assert data['exit_code'] == 0 and (Path(f['project'])/'verified.marker').read_text() == 'cobalt lighthouse'
    elif name == 'audio.mute': assert fixture.volume.muted is True
    elif name == 'audio.set_volume': assert fixture.volume.level == .32 and data['percent'] == 32
    elif name == 'spotify.volume': assert fixture.volume.level == .32 and data['percent'] == 32 and data['changed'] is True
    elif name == 'clipboard.write': assert fixture.clipboard == 'cobalt lighthouse'
    elif name == 'clipboard.read': assert data['text'] == 'cobalt lighthouse'
    elif name == 'timer.set':
        assert fixture.timer.started and fixture.timer.seconds == 5 and data['seconds'] == 5
        fixture.timer.callback()
        assert any(call[0] == 'powershell' and call[1] == 'notify.toast' for call in fixture.events)
    elif name in OS_MOCKS: assert fixture.events or name.startswith('spotify.') or name.startswith('ui.')
    else:
        # Variable live telemetry is checked for structure and meaningful data;
        # it is not compared with a second sample of a changing counter.
        assert isinstance(data, dict) and data
    return 'artifact/readback or fixed arithmetic oracle; declared fields/types; error and authority gates'


def save(path, row):
    with path.open('a', encoding='utf-8') as out:
        out.write(json.dumps(row, ensure_ascii=True, default=str)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'data/v36-campaign/direct-cycle1')
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args()
    output = options.output.resolve()
    assert output.is_relative_to((ROOT/'data').resolve())
    output.mkdir(parents=True, exist_ok=True)
    journal = output/'results.jsonl'
    done = set()
    if options.resume and journal.exists():
        done = {json.loads(line)['capability_id'] for line in journal.read_text().splitlines()}
    elif journal.exists(): raise SystemExit('Existing journal: use --resume or a new output directory')
    f = prepare_files(output, os.getpid())
    # Ensure the known project is formatted for both real developer tool checks.
    Path(f['project'], 'test_sample.py').write_text('from pathlib import Path\n\n\ndef test_sample():\n    assert 2 + 3 == 5\n    Path("verified.marker").write_text("cobalt lighthouse")\n', encoding='utf-8')
    Path(f['folder'], 'duplicate-large.dat').write_bytes(b'V36 synthetic duplicate\n'*100)
    Path(f['folder'], 'nested/duplicate-large.dat').write_bytes(Path(f['folder'], 'duplicate-large.dat').read_bytes())
    os.environ['HANNI_V36_FIXTURE'] = 'cobalt lighthouse'
    config = load_config(config_dir=ROOT/'config', data_dir=output/'state', env={})
    registry = build_default_registry(config, data_dir=output/'state')
    registry.google_access._vault = GoogleVault()
    registry.google_access.transport = GoogleProvider()
    values = arguments(f)
    values['email.search']['query'] = 'Find emails about rehearsal'
    defs = tuple(registry.definitions())
    for d in defs:
        if not d.input_schema: values.setdefault(d.name, {})
    values['process.stop'] = {'pid': -1}
    missing = sorted({d.name for d in defs}-values.keys())
    assert not missing, missing
    # A sole owned child is used for process.stop; never infer a PID from user data.
    helper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    values['process.stop'] = {'pid': helper.pid}
    f['_helper'] = helper
    (output/'owned-helper.json').write_text(json.dumps({'pid': helper.pid, 'created': time.time()}), encoding='utf-8')
    manifest = [{'id': d.name, 'args': values[d.name], 'invalid_args': {'v36_unexpected_field': True},
                 'expected': 'ordinary success with declared contract and independent outcome assertion',
                 'environment': 'mock' if d.name in OS_MOCKS or d.name.startswith(('google', 'gmail.', 'email.')) else 'isolated' if d.name.startswith(ISOLATED_PREFIXES) or d.name == 'process.stop' else 'live'} for d in defs]
    sealed = output/'cases.json'
    if not sealed.exists(): sealed.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding='utf-8')
    print('Sealed cases', len(manifest), hashlib.sha256(sealed.read_bytes()).hexdigest(), flush=True)
    try:
        for d in defs:
            name = d.name
            if name in done or (options.only and name not in options.only): continue
            case = next(c for c in manifest if c['id'] == name)
            args = values[name]
            fixture = OSFixture()
            if name.startswith(('google', 'gmail.', 'email.')):
                # Independence between ordinary provider writes and later reads.
                registry.google_access.transport = GoogleProvider()
            row = {'test_id': 'v36-A-'+name, 'capability_id': name, 'category': 'A_direct',
                   'input_request': args, 'expected_behavior': case['expected'],
                   'environment_type': case['environment'], 'model_configuration': None,
                   'fix_reference': None, 'verification_status': 'AWAITING_INDEPENDENT_VERIFIER',
                   'live_status': 'UNSAFE_TO_RUN' if name in OS_MOCKS else 'ELIGIBLE'}
            before = time.perf_counter()
            try:
                with seams(name, fixture):
                    try:
                        invalid = registry.execute(ToolRequest(name, {'v36_unexpected_field': True}, source='v36-direct'))
                    except ToolValidationError as exc:
                        invalid_record = {'exception_type': type(exc).__name__, 'message': str(exc)}
                    else:
                        raise AssertionError('Unknown argument accepted: '+str(invalid.to_dict()))
                    try:
                        denied = registry.execute(ToolRequest(name, args, actor_profile='everyone_else', source='v36-direct'))
                    except ToolPermissionError as exc:
                        denied_record = {'exception_type': type(exc).__name__, 'message': str(exc)}
                    else:
                        raise AssertionError('Untrusted profile accepted: '+str(denied.to_dict()))
                    result = registry.execute(ToolRequest(name, args, confirmed=True, source='v36-direct'))
                    row['actual_response'] = result.to_dict()
                    row['invalid_result'] = invalid_record
                    row['permission_result'] = denied_record
                    row['actual_tool_calls'] = [{'name': name, 'args': args}]
                    row['dependency_calls'] = fixture.events
                    row['contract_errors'] = contract_errors(d, result) if result.ok else []
                    if not result.ok:
                        raise RuntimeError(result.message)
                    row['outcome_verification'] = verify(name, result, f, fixture)
                    if row['contract_errors']:
                        raise AssertionError('Output contract: '+', '.join(row['contract_errors']))
                    row['outcome'] = {'live': 'LIVE_PASS', 'isolated': 'ISOLATED_PASS', 'mock': 'MOCK_PASS'}[case['environment']]
                    row['failure_category'] = None
            except Exception as exc:
                row['outcome'] = 'BLOCKED' if any(word in str(exc).lower() for word in ('not installed', 'no module named', 'no active audio session', 'optional pycaw', 'access is denied', 'access denied', 'requires administrator', 'is not recognized')) else 'FAIL'
                row['failure_category'] = 'dependency_or_authority' if row['outcome'] == 'BLOCKED' else 'execution_or_contract_or_objective'
                row['failure'] = str(exc)
            row['latency_seconds'] = round(time.perf_counter()-before, 4)
            save(journal, row)
            print(name, row['outcome'], row.get('failure', '')[:180], flush=True)
    finally:
        if helper.poll() is None:
            helper.terminate()
        helper.wait(timeout=5)
        # No delayed mock timer may fall through into a real notification.
        from hanni.core.shutdown import LocalStopControls
        try:
            LocalStopControls(output/'state').trip('V36 fixture cleanup')
        except Exception:
            pass
        registry.context.reliability.close()


if __name__ == '__main__': main()
