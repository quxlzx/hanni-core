"""Original-handler cases over owned fixtures and explicit dependency seams."""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import uuid
from zipfile import ZipFile
import psutil
from scripts.v36_engineering.fixtures import GoogleProvider, GoogleVault, prepare_files
from hanni.tools.base import ToolRequest
from hanni.tools.google_identity import GoogleAccessError

@dataclass
class Case:
    args: dict
    query: str
    mode: str
    deps: object
    verify: object
    dependency: str = 'external dependency'

class Timer:
    created = []

    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.started, self.cancelled = (seconds, callback, False, False)
        self.created.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

class RootFixtures:

    def __init__(self, root, registry):
        self.root, self.registry = (root, registry)
        self.fields = prepare_files(root, os.getpid())
        self.text = 'Amber telescope audit.\nSecond line.\nFinal line.\n'
        Path(self.fields['file']).write_text(self.text, encoding='utf8')
        Path(self.fields['other']).write_text('Amber telescope audit.\nChanged line.\nFinal line.\n', encoding='utf8')
        (Path(self.fields['folder']) / 'duplicate-a.txt').write_bytes(b'A' * 2048)
        (Path(self.fields['folder']) / 'duplicate-b.txt').write_bytes(b'A' * 2048)
        (root / 'project/check.py').write_text('print("amber audit verified")\n', encoding='utf8')
        self.google = GoogleProvider()
        self.google.document['name'] = 'Amber telescope notes'
        self.ledger = []
        self.observations = []
        self.now = datetime.now().astimezone()
        self.start = (self.now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)

    @contextmanager
    def dependencies(self, name, args, unavailable=False):
        module = importlib.import_module(self.registry.get(name).handler.__module__)
        self.ledger.clear()
        with ExitStack() as stack:

            def fail(*a, **kw):
                raise OSError('Campaign-owned dependency unavailable')

            def shell(*a, **kw):
                if unavailable:
                    return fail()
                self.ledger.append({'command': a[0], 'kwargs': kw})
                return SimpleNamespace(returncode=0, stdout='amber audit receipt', stderr='')
            if name.startswith(('google.', 'google_calendar.', 'gmail.', 'email.')):
                vault = GoogleVault()
                if unavailable:
                    vault.records = {}
                stack.enter_context(patch.object(self.registry.google_access, '_vault', vault))
                stack.enter_context(patch.object(self.registry.google_access, 'transport', self.google))
            elif name == 'file.open':

                def openfile(path):
                    if unavailable:
                        return fail()
                    self.ledger.append({'opened_path': str(path)})
                stack.enter_context(patch.object(module.os, 'startfile', openfile))
            elif name.startswith('clipboard.'):

                def clipboard(command, **kwargs):
                    if unavailable:
                        return fail()
                    self.ledger.append({'command': command})
                    return 'amber telescope'
                stack.enter_context(patch.object(module, 'run_powershell', clipboard))
            elif name in {'notify.toast', 'schedule.list_tasks', 'timer.set'}:
                stack.enter_context(patch.object(module, 'run_powershell', shell))
                stack.enter_context(patch.object(module, 'run_powershell_json', fail if unavailable else lambda *a, **kw: [{'TaskName': 'Amber audit', 'TaskPath': '\\Audit\\', 'State': 3}]))
                if name == 'timer.set':
                    Timer.created.clear()

                    class UnavailableTimer(Timer):

                        def start(self):
                            return fail()
                    stack.enter_context(patch.object(module, 'threading', SimpleNamespace(Timer=UnavailableTimer if unavailable else Timer, RLock=__import__('threading').RLock)))
            elif name == 'disk.cleanup_temp':
                cleanup = self.root / 'temp-only'
                cleanup.mkdir(exist_ok=True)
                old = cleanup / 'old.txt'
                old.write_text('owned stale data', encoding='utf8')
                os.utime(old, (1, 1))
                stack.enter_context(patch.object(module, '_temp_roots', fail if unavailable else lambda: [cleanup]))
            elif name == 'disk.recycle_bin_size':
                recycle = self.root / 'recycle-drive/$Recycle.Bin'
                recycle.mkdir(parents=True, exist_ok=True)
                (recycle / 'owned.bin').write_bytes(b'ABCD')
                proxy = SimpleNamespace(**{key: getattr(module.psutil, key) for key in dir(module.psutil) if not key.startswith('__')})
                proxy.disk_partitions = fail if unavailable else lambda **kw: [SimpleNamespace(mountpoint=str(recycle.parent))]
                stack.enter_context(patch.object(module, 'psutil', proxy))
            elif unavailable and name.startswith(('file.', 'archive.', 'disk.')):
                if name in {'file.write', 'file.mkdir'}:
                    stack.enter_context(patch.object(Path, 'mkdir', fail))
                elif name == 'disk.usage':
                    stack.enter_context(patch.object(module, 'psutil', SimpleNamespace(disk_partitions=fail)))
                elif name == 'disk.free_space':
                    stack.enter_context(patch.object(module, 'shutil', SimpleNamespace(disk_usage=fail)))
                else:
                    for key in ('path', 'root', 'source', 'archive', 'left'):
                        if key in args:
                            args[key] = str(self.root / 'never-existent-fixture')
            elif unavailable and name.startswith(('note.', 'todo.')):
                if name.startswith('note.'):
                    stack.enter_context(patch.object(module, '_notes_dir', fail))
                else:
                    stack.enter_context(patch.object(module.TodoStore, 'connect', fail))
            elif unavailable and name.startswith(('git.', 'project.')):
                target = '_git' if name.startswith('git.') else '_run_module' if name != 'project.test' else None
                if target:
                    stack.enter_context(patch.object(module, target, fail))
                else:
                    stack.enter_context(patch.object(module, 'subprocess', SimpleNamespace(run=fail)))
            elif name in {'project.lint', 'project.format'}:
                checker = Path(__file__).resolve().parents[2] / 'data/campaign2-manager/checker-env/Scripts/python.exe'
                if checker.is_file():
                    stack.enter_context(patch.object(module, 'sys', SimpleNamespace(executable=str(checker))))
            elif unavailable and name in {'system.performance', 'process.find'}:
                proxy = SimpleNamespace(**{key: getattr(module.psutil, key) for key in dir(module.psutil) if not key.startswith('__')})
                if name == 'system.performance':
                    proxy.cpu_percent = fail
                else:
                    proxy.process_iter = fail
                stack.enter_context(patch.object(module, 'psutil', proxy))
            elif unavailable and name == 'python.env_info':
                stack.enter_context(patch.object(module, 'subprocess', SimpleNamespace(run=fail)))
            elif unavailable and name == 'powershell.run':
                stack.enter_context(patch.object(module, 'subprocess', SimpleNamespace(run=fail)))
            elif unavailable and name == 'model.status':
                stack.enter_context(patch('hanni.models.registry.create_client', return_value=SimpleNamespace(health_url='http://127.0.0.1:1/health', health=lambda: SimpleNamespace(to_dict=lambda: {'ok': False, 'reachable': False}))))
            elif unavailable and name == 'hanni.audit_tail':
                stack.enter_context(patch.object(self.registry.context.audit, 'tail', fail))
            elif unavailable and name == 'gpu.memory':
                import hanni.tools.system as system
                stack.enter_context(patch.object(system, 'snapshot_resources', fail))
            yield

    def case(self, definition):
        name = definition.name
        f = self.fields
        args = {'file.stat': {'path': f['file'], 'hash': True}, 'file.read': {'path': f['file']}, 'file.list_dir': {'path': f['folder']}, 'file.locate': {'root': f['folder'], 'name': 'sample.txt'}, 'file.search': {'root': f['folder'], 'query': 'sample'}, 'file.write': {'path': f['written'], 'text': 'amber telescope'}, 'file.mkdir': {'path': f['newfolder']}, 'file.copy': {'source': f['file'], 'destination': f['copy']}, 'file.move': {'source': f['file'], 'destination': f['moved']}, 'file.delete': {'path': f['delete']}, 'file.head': {'path': f['file'], 'lines': 2}, 'file.tail': {'path': f['file'], 'lines': 2}, 'file.compare': {'left': f['file'], 'right': f['other']}, 'file.grep': {'root': f['folder'], 'query': 'Amber telescope'}, 'file.recent': {'root': f['folder']}, 'file.duplicates': {'root': f['folder'], 'min_kb': 1}, 'file.composition': {'root': f['folder']}, 'file.empty_folders': {'root': f['folder']}, 'file.open': {'path': f['file']}, 'archive.list': {'archive': f['zip']}, 'archive.zip': {'source': f['folder'], 'destination': f['newzip']}, 'archive.unzip': {'archive': f['zip'], 'destination': f['extract']}, 'disk.folder_size': {'path': f['folder']}, 'disk.largest_files': {'root': f['folder'], 'min_mb': 0}, 'disk.largest_folders': {'root': f['folder']}, 'disk.usage': {'drive': 'C'}, 'disk.free_space': {'drive': str(self.root), 'needed_gb': 0}, 'disk.cleanup_temp': {'apply': True, 'older_than_days': 1}, 'disk.recycle_bin_size': {}, 'git.status': {'root': f['git']}, 'git.log': {'root': f['git']}, 'git.diff': {'root': f['git']}, 'git.branches': {'root': f['git']}, 'python.env_info': {'query': 'pytest'}, 'project.lint': {'root': f['project'], 'tool': 'ruff'}, 'project.format': {'root': f['project'], 'apply': False}, 'project.test': {'root': f['project'], 'target': 'check.py', 'runner': 'script', 'expected_stdout': 'amber audit verified'}, 'powershell.run': {'command': "Write-Output 'amber audit verified'"}, 'calc.evaluate': {'expression': '17*23+9'}, 'unit.convert': {'value': 12, 'from_unit': 'in', 'to_unit': 'cm'}, 'text.stats': {'text': 'Amber telescope audit.'}, 'text.hash': {'text': 'amber telescope', 'algorithm': 'sha256'}, 'text.normalize': {'text': 'Amber Téléscope', 'mode': 'slug'}, 'id.generate': {'kind': 'uuid4'}, 'random.number': {'minimum': 4, 'maximum': 8}, 'random.pick': {'options': ['amber', 'teal'], 'count': 1}, 'time.now': {'timezone': 'UTC'}, 'time.convert': {'when': '2026-11-04T09:00:00', 'from_timezone': 'America/New_York', 'to_timezone': 'Europe/London'}, 'time.elapsed': {'since': (self.now - timedelta(hours=2)).isoformat()}, 'timer.set': {'duration': '5 seconds', 'label': 'amber audit'}, 'notify.toast': {'title': 'Audit', 'message': 'amber telescope'}, 'schedule.list_tasks': {'query': 'Amber'}, 'clipboard.read': {}, 'clipboard.write': {'text': 'amber telescope'}, 'note.append': {'text': 'Amber telescope observation'}, 'note.search': {'query': 'cobalt'}, 'note.list': {}, 'note.days': {}, 'todo.add': {'title': 'Amber telescope inspection', 'due': 'tomorrow'}, 'todo.get': {'id': f['todo']}, 'todo.complete': {'id': f['todo']}, 'todo.list': {}, 'todo.due': {'days': 7}, 'hanni.capabilities': {'goal': 'inspect a folder'}, 'hanni.audit_tail': {}, 'hanni.permissions': {}, 'hanni.stop_state': {}, 'model.status': {}, 'gpu.memory': {}, 'system.performance': {}, 'process.find': {'name': 'python'}}.get(name)
        if name.startswith(('google.', 'google_calendar.', 'gmail.', 'email.')):
            args = {'account': 'personal'}
            if name == 'google.accounts':
                args = {}
            elif name.endswith(('agenda', 'events', 'availability')):
                args.update(start_date=self.start.date().isoformat(), days=1)
                if name.endswith('availability'):
                    args.update(availability_start='14:00', availability_end='15:00')
            elif name.endswith('create'):
                if '.tasks.' in name:
                    args.update(title='Amber telescope task', tasklist_id='list-v36')
                else:
                    args.update(summary='Amber telescope review', all_day=False, calendar_id='primary', start=self.start.isoformat(), end=(self.start + timedelta(hours=1)).isoformat())
            elif name.endswith(('read', 'metadata', 'thread', 'complete', 'delete', 'update')):
                args['id'] = 'task-v36' if '.tasks.' in name else 'doc-v36' if '.drive.' in name or '.docs.' in name else 'event-v36' if '.calendar.' in name else 'thread-v36' if name.endswith('thread') else 'message-v36'
                if name.endswith('update'):
                    args['summary'] = 'Amber revised'
                if '.tasks.' in name:
                    args['tasklist_id'] = 'list-v36'
            elif name.endswith('search'):
                args['query'] = 'emails about rehearsal' if name == 'email.search' else 'rehearsal'
        if args is None:
            return None
        from scripts.v36_engineering.scenarios import REQUESTS
        query = REQUESTS.get(name, definition.description).format(**f)
        overrides = {'calc.evaluate': 'Calculate 17 times 23 plus 9.', 'unit.convert': 'Convert 12 inches to centimeters.', 'timer.set': 'Set a five-second timer called amber audit.', 'process.find': 'Find running Python processes and their memory usage.', 'file.move': f"Move {f['file']} to {f['moved']}.", 'text.hash': 'Compute the SHA256 of the exact text amber telescope.'}
        query = overrides.get(name, query)
        mode = 'original_mock_dependency' if name.startswith(('google.', 'google_calendar.', 'gmail.', 'email.', 'clipboard.')) or name in {'file.open', 'notify.toast', 'timer.set', 'schedule.list_tasks', 'disk.recycle_bin_size'} else 'isolated_original' if name.startswith(('file.', 'archive.', 'git.', 'project.', 'note.', 'todo.')) or name in {'disk.cleanup_temp', 'disk.folder_size', 'disk.largest_files', 'disk.largest_folders'} else 'live_read'
        dependency = 'none' if definition.handler.__module__ in {'hanni.tools.compute'} or name.startswith('time.') or name in {'hanni.permissions', 'hanni.stop_state', 'hanni.capabilities'} else 'dependency seam'
        return Case(args, query, mode, lambda arguments, unavailable=False: self.dependencies(name, arguments, unavailable), lambda result, arguments: self.verify(name, result, arguments), dependency)

    def verify(self, name, result, args):
        d = result.data
        errors = []
        self.observations.clear()

        def check(condition, label):
            self.observations.append({'check': label, 'passed': bool(condition), 'observed': bool(condition), 'expected': True})
            if not condition:
                errors.append(label)
        if not result.ok:
            return ['Valid original implementation did not return success: ' + result.message]
        if name == 'file.read':
            check(d['text'] == Path(args['path']).read_text(encoding='utf8'), 'exact disk text')
        elif name == 'file.stat':
            check(d['sha256'] == hashlib.sha256(Path(args['path']).read_bytes()).hexdigest(), 'actual digest')
        elif name == 'file.write':
            check(Path(args['path']).read_text(encoding='utf8') == args['text'], 'written disk text')
        elif name == 'file.mkdir':
            check(Path(args['path']).is_dir(), 'created directory')
        elif name in {'file.copy', 'file.move'}:
            check(Path(d['destination']).read_text(encoding='utf8') == self.text, 'destination content')
            if name == 'file.move':
                check(not Path(args['source']).exists(), 'source absence')
        elif name == 'file.delete':
            check(not Path(args['path']).exists(), 'deleted fixture absence')
        elif name == 'file.head':
            check(d['lines'] == self.text.splitlines()[:2], 'head content')
        elif name == 'file.tail':
            check(d['lines'] == self.text.splitlines()[-2:], 'tail content')
        elif name == 'file.grep':
            check(d['match_count'] >= 1, 'synthetic phrase found')
        elif name == 'file.list_dir':
            check({row['name'] for row in d['entries']} == {p.name for p in Path(args['path']).iterdir()}, 'actual directory entries')
        elif name == 'file.search':
            check(str(Path(args['root']) / 'sample.txt') in d['matches'], 'seeded filename match')
        elif name == 'file.recent':
            check(str(Path(args['root']) / 'sample.txt') in {row['path'] for row in d['files']}, 'recent fixture membership')
        elif name == 'file.composition':
            check(d['total_files'] == sum((p.is_file() for p in Path(args['root']).rglob('*'))), 'actual file count')
        elif name == 'file.duplicates':
            check(d['group_count'] >= 1, 'seeded duplicate hashes')
        elif name == 'file.compare':
            check(not d['identical'], 'changed comparison')
        elif name == 'file.empty_folders':
            check(str(Path(self.fields['folder']) / 'empty') in d['folders'], 'seeded empty folder')
        elif name == 'file.locate':
            check(any((r['path'] == args['root'] + '\\sample.txt' for r in d['matches'])), 'exact located fixture')
        elif name == 'archive.zip':
            with ZipFile(d['destination']) as z:
                check(any((p.endswith('sample.txt') for p in z.namelist())), 'archive disk entries')
        elif name == 'archive.unzip':
            check((Path(args['destination']) / 'sample.txt').is_file(), 'extracted disk file')
        elif name == 'archive.list':
            with ZipFile(args['archive']) as z:
                check(d['entry_count'] == len(z.infolist()), 'actual ZIP count')
        elif name == 'disk.cleanup_temp':
            check(not (self.root / 'temp-only/old.txt').exists() and d['removed_files'] == 1, 'owned stale file deletion')
        elif name == 'disk.recycle_bin_size':
            check(d['item_count'] == 1, 'synthetic recycle item count')
        elif name == 'disk.folder_size':
            check(d['file_count'] == sum((p.is_file() for p in Path(args['path']).rglob('*'))), 'actual disk file count')
        elif name == 'disk.largest_files':
            check(all((Path(row['path']).is_file() for row in d['files'])) and d['matches'] > 0, 'actual ranked file existence')
        elif name == 'disk.largest_folders':
            check(all((Path(row['path']).is_dir() for row in d['folders'])), 'actual ranked directory existence')
        elif name == 'disk.free_space':
            import shutil
            check(abs(d['free_gb'] - round(shutil.disk_usage(args['drive']).free / 1024 ** 3, 2)) < 0.05, 'independent free capacity')
        elif name == 'disk.usage':
            check(all((abs(row['total_gb'] - round(psutil.disk_usage(row['drive']).total / 1024 ** 3, 2)) < 0.02 for row in d['drives'])), 'independent mounted capacities')
        elif name == 'calc.evaluate':
            check(d['value'] == 400, 'independent arithmetic')
        elif name == 'unit.convert':
            check(abs(d['converted'] - 30.48) < 1e-08, 'reference inches factor')
        elif name == 'text.hash':
            check(d['digest'] == hashlib.sha256(b'amber telescope').hexdigest(), 'independent digest')
        elif name == 'text.stats':
            check(d['words'] == 3 and d['characters'] == 22, 'manual text counts')
        elif name == 'text.normalize':
            check(d['result'] == 'amber-telescope', 'expected Unicode slug')
        elif name == 'id.generate':
            check(uuid.UUID(d['value']).version == 4, 'UUID version')
        elif name == 'random.number':
            check(4 <= d['value'] <= 8, 'specified random range')
        elif name == 'random.pick':
            check(len(d['picked']) == 1 and d['picked'][0] in args['options'], 'provided option membership')
        elif name == 'time.convert':
            check(d['converted_iso'].startswith('2026-11-04T14:00'), 'IANA conversion')
        elif name == 'time.elapsed':
            check(7190 <= d['seconds'] <= 7210, 'independent elapsed clock')
        elif name == 'time.now':
            check(abs((datetime.fromisoformat(d['iso']) - datetime.now(timezone.utc)).total_seconds()) < 3, 'live clock proximity')
        elif name == 'timer.set':
            check(bool(Timer.created) and Timer.created[-1].started and (d['seconds'] == 5), 'original timer scheduling')
            Timer.created[-1].callback()
            check(bool(self.ledger), 'original callback invoked isolated notification dependency')
        elif name in {'notify.toast', 'clipboard.write', 'file.open'}:
            check(bool(self.ledger), 'controlled leaf operation receipt')
            if name == 'file.open':
                check(d.get('request_submitted') is True and d.get('display_verified') is False, 'file-open request receipt does not invent display proof')
            elif name == 'notify.toast':
                check(d.get('submitted') is True and d.get('shown') is None, 'notification request receipt preserves unknown visibility')
        elif name == 'clipboard.read':
            check(d['text'].strip() == 'amber telescope', 'controlled clipboard data')
        elif name == 'note.append':
            check(args['text'] in Path(d['path']).read_text(encoding='utf8'), 'note disk readback')
        elif name == 'note.list':
            check(any(('cobalt' in row for row in d['notes'])), 'seeded note readback')
        elif name == 'note.search':
            check(d['match_count'] > 0 and all(('cobalt' in row['text'] for row in d['matches'])), 'seeded note search')
        elif name == 'note.days':
            check(d['total'] > 0 and d['days'][0]['notes'] > 0, 'seeded note day count')
        elif name.startswith('todo.'):
            from hanni.tools.todos import TodoStore
            if name in {'todo.add', 'todo.get', 'todo.complete'}:
                row = TodoStore(self.root / 'state').get(d['id'])
                check(row == d['task'], 'SQLite readback')
                if name == 'todo.complete':
                    check(row['status'] == 'completed', 'stored completion state')
            else:
                check(d['count'] == len(d['tasks']), 'SQLite list count')
        elif name.startswith(('google.', 'google_calendar.', 'gmail.', 'email.')):
            if name == 'google.accounts':
                check(d['accounts'][0]['account'] == 'personal', 'isolated account identity')
            else:
                check(bool(self.google.calls), 'original Google adapter called mock HTTP boundary')
            if name.endswith('create') and '.tasks.' not in name:
                check(self.google.events[d['id']]['summary'] == args['summary'], 'mock event state readback')
            elif name == 'google.calendar.delete':
                check(args['id'] not in self.google.events, 'mock deleted state')
            elif name == 'google.calendar.update':
                check(self.google.events[args['id']]['summary'] == args['summary'], 'mock update state')
            elif name == 'google.tasks.complete':
                check(self.google.tasks[args['id']]['status'] == 'completed', 'mock task completion')
            elif name == 'google.tasks.create':
                check(any((r['title'] == args['title'] for r in self.google.tasks.values())), 'mock task creation')
        elif name == 'project.test':
            check(d['exit_code'] == 0 and d['stdout'].strip() == 'amber audit verified', 'actual child exit and output')
        elif name in {'project.lint', 'project.format'}:
            check(d['exit_code'] == 0, 'actual checker exit status')
        elif name == 'git.status':
            output = subprocess.check_output(['git', '-C', args['root'], 'status', '--porcelain'], text=True)
            check(d['changed_count'] == len(output.splitlines()), 'independent git status')
        elif name == 'git.log':
            head = subprocess.check_output(['git', '-C', args['root'], 'rev-parse', 'HEAD'], text=True).strip()
            check(bool(d['commits']) and any((head.startswith(str(v)) for v in d['commits'][0].values())), 'independent git HEAD')
        elif name == 'git.branches':
            check(d['current'] == subprocess.check_output(['git', '-C', args['root'], 'branch', '--show-current'], text=True).strip(), 'independent current branch')
        elif name == 'git.diff':
            check('fixture.txt' in d['diff'] and (not d['empty']), 'owned changed file diff')
        elif name == 'python.env_info':
            check(d['executable'] == __import__('sys').executable and all(('pytest' in row['name'].lower() for row in d['packages'])), 'active interpreter and filtered packages')
        elif name == 'powershell.run':
            check(d['exit_code'] == 0 and d['stdout'].strip() == 'amber audit verified', 'actual PowerShell receipt')
        elif name == 'hanni.stop_state':
            check(d['stopped'] is False, 'original stop readback')
        elif name == 'hanni.capabilities':
            check(all((row['name'] in {item.name for item in self.registry.definitions()} for row in d['capabilities'])), 'original registry IDs')
        elif name == 'hanni.permissions':
            check({row['profile'] for row in d['profiles']} == set(self.registry.context.permissions.profiles), 'original profile names')
        elif name == 'hanni.audit_tail':
            check(d['count'] == len(d['entries']) and all(('tool' in row for row in d['entries'])), 'actual isolated audit entries')
        elif name == 'model.status':
            check(d['reachable'] and (not d['placement_verified']), 'live endpoint and unowned placement disclosure')
        elif name == 'gpu.memory':
            check(abs(d['free_gb_total'] - round(sum((row['free_gb'] for row in d['gpus'])), 2)) < 0.02, 'per-device free memory aggregate')
        elif name == 'system.performance':
            check(d['ram_total_gb'] == round(psutil.virtual_memory().total / 1024 ** 3, 2) and 'excludes' in d['snapshot_scope'], 'independent installed RAM and partial measurement scope')
        elif name == 'schedule.list_tasks':
            check(d['total'] == 1 and d['tasks'][0]['name'] == 'Amber audit', 'mock scheduled-task identity')
        elif name == 'process.find':
            check(all((psutil.pid_exists(row['pid']) for row in d['processes'])), 'observed process existence')
        else:
            return ['NO_INDEPENDENT_READBACK']
        return errors
