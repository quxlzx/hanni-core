"""Owned fixture setup and controlled dependency handlers after real gates."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from datetime import datetime
from threading import RLock
from unittest.mock import patch
from types import SimpleNamespace
import json
import re
import zipfile
from hanni.tools.base import ToolResult
from hanni.tools.google_identity import ALLOWED_SCOPES
PURE = {'calc.evaluate', 'unit.convert', 'text.stats', 'text.hash', 'text.normalize', 'time.now', 'time.convert', 'time.elapsed', 'id.generate', 'random.number', 'random.pick'}
_CLOCK_LOCK = RLock()

def original_time_with_clock(definition, arguments, context, request, fixture):
    """Use original parsing/timezone/date logic; change this module's clock only."""
    from hanni.tools import timekeep
    instant = datetime.fromisoformat(fixture.get('fixed_clock', fixture.get('now', '2026-10-12T10:15:00-04:00')))
    original_datetime = timekeep.datetime
    original_time = timekeep.time

    class EvaluationDateTime(original_datetime):

        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz is not None else instant.astimezone().replace(tzinfo=None)

    class EvaluationTime:

        @staticmethod
        def time():
            return instant.timestamp()

        def __getattr__(self, name):
            return getattr(original_time, name)
    with _CLOCK_LOCK, patch.object(timekeep, 'datetime', EvaluationDateTime), patch.object(timekeep, 'time', EvaluationTime()):
        return definition.handler(arguments, context, request)

def original_process_with_inventory(definition, arguments, context, request, fixture, inventory):
    """Original query/PID semantics, observing only a predeclared inventory."""
    from hanni.tools import overview, system
    instant = datetime.fromisoformat(fixture.get('fixed_clock', fixture.get('now', '2026-10-12T10:15:00-04:00')))
    if definition.name == 'process.find':
        rows = [SimpleNamespace(info={'pid': row['pid'], 'name': row['name'], 'memory_info': SimpleNamespace(rss=row['memory_gb'] * 1024 ** 3), 'create_time': instant.timestamp() - row['running_minutes'] * 60}) for row in inventory]
        proxy = SimpleNamespace(process_iter=lambda attributes: iter(rows))
        with _CLOCK_LOCK, patch.object(overview, 'psutil', proxy), patch.object(overview, 'time', SimpleNamespace(time=lambda: instant.timestamp())):
            return definition.handler(arguments, context, request)
    proxy = SimpleNamespace(pid_exists=lambda pid: any((row['pid'] == pid for row in inventory)))
    with _CLOCK_LOCK, patch.object(system, 'psutil', proxy):
        return definition.handler(arguments, context, request)
OWNED = {'file.read', 'file.stat', 'file.list_dir', 'file.search', 'file.grep', 'file.head', 'file.tail', 'file.compare', 'file.locate', 'file.composition', 'file.recent', 'file.duplicates', 'file.empty_folders', 'file.write', 'file.copy', 'file.move', 'file.mkdir', 'folder.list', 'folder.search', 'archive.list', 'archive.zip', 'archive.unzip', 'note.append', 'note.search', 'note.list', 'note.days', 'todo.list', 'todo.due', 'todo.add', 'todo.complete', 'todo.get'}
PATH_KEYS = {'path', 'source', 'destination', 'root', 'directory', 'folder', 'archive', 'output', 'target', 'file', 'left', 'right', 'paths', 'archive_path', 'destination_path', 'source_path', 'output_path', 'folder_path'}

class FixtureVault:

    def __init__(self, sources=None):
        declared = (sources or {}).get('tools', {}).get('google.accounts', {}).get('data', {}).get('accounts', [])
        self._labels = tuple((row['name'] for row in declared)) if (sources or {}).get('schema_version', 1) >= 2 else ('personal', 'school')
        if not self._labels:
            raise ValueError('The controlled source must declare its synthetic account roster.')

    def labels(self):
        return self._labels

    def preferences(self):
        return {'default_google_account': 'personal' if 'personal' in self._labels else self._labels[0]}

    def get(self, label):
        if label not in self.labels():
            return None
        return {'email': label + '@example.invalid', 'calendar_ids': ['primary'], 'credentials': {'scopes': list(ALLOWED_SCOPES)}}

def substitute(value, root):
    if isinstance(value, str):
        return value.replace('{fixture_root}', str(root)).replace('C:\\EvalFixture', str(root))
    if isinstance(value, list):
        return [substitute(v, root) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, root) for k, v in value.items()}
    return value

def setup(case, root, state, sources):
    root.mkdir(parents=True, exist_ok=False)
    state.mkdir(parents=True, exist_ok=True)
    fixture = case['fixture']
    files = fixture.get('files', {})
    if not files:
        files = {'brief.txt': sources.get('file_text_by_basename', {}).get('brief.txt', 'Owned fixture text.'), **sources.get('file_text_by_basename', {}), 'repo/README.txt': 'Disposable repository fixture'}
        for q in case.get('turns') or [case['query']]:
            for match in re.finditer('C:\\\\EvalFixture\\\\([\\w.\\\\ /-]+)', q):
                relative = match.group(1).strip(' .,:;!?')
                if Path(relative).suffix.lower() in {'.txt', '.json', '.csv', '.md'}:
                    files.setdefault(relative, sources.get('file_text_by_basename', {}).get(Path(relative).name, 'Owned fixture text.'))
    for name, text in files.items():
        target = (root / name).resolve()
        assert target.is_relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf8')
    for name in fixture.get('empty_directories', []):
        target = (root / name).resolve()
        assert target.is_relative_to(root.resolve())
        target.mkdir(parents=True, exist_ok=True)
    archive = root / 'bundle.zip'
    archive_source = (root / fixture.get('zip_source', '.')).resolve()
    assert archive_source.is_relative_to(root.resolve())
    with zipfile.ZipFile(archive, 'w') as z:
        for target in sorted(archive_source.rglob('*.txt')):
            z.write(target, target.relative_to(root))
    for note in fixture.get('notes', []):
        target = state / 'notes' / f"{note['date']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('- 10:15 ' + note['text'] + '\n', encoding='utf8')
    todos = fixture.get('todos', sources.get('todo_inventory', []) if sources.get('schema_version', 1) >= 2 else [])
    if todos:
        from hanni.tools.todos import TodoStore
        store = TodoStore(state)
        with store.connect() as connection:
            for task in todos:
                connection.execute('INSERT INTO todos(id,request_key,title,course,due,all_day,status,created_at) VALUES (?,?,?,?,?,?,?,?)', (str(task['id']), 'fixture-' + str(task['id']), task['title'], task.get('course', ''), task.get('due', ''), task.get('all_day', 1), task.get('status', 'completed' if task.get('completed') else 'open'), fixture.get('fixed_clock', fixture.get('now', '2026-10-12T10:15:00-04:00'))))
    return {'fixture_root': str(root), 'files': [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()], 'provider_scope': 'synthetic account metadata only; no owner credentials or live provider calls'}

def set_path(data, path, value):
    keys = path.strip('/').split('/')
    cursor = data
    for key in keys[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(key)]
        else:
            cursor = cursor.setdefault(key, {})
    if isinstance(cursor, list):
        cursor[int(keys[-1])] = value
    else:
        cursor[keys[-1]] = value

def install_seams(registry, case, root, state, sources, receipt):
    """Replace providers, never schema/permission/confirmation metadata."""
    registry.google_access._vault = FixtureVault(sources)
    profile = case['fixture'].get('profile', case['fixture'].get('routing_profile', 'owner'))
    real_owned = case['scope'] == 'isolated final' or bool(case['fixture'].get('real_side_effects_allowed'))
    process_inventory = deepcopy(sources.get('process_inventory', []))
    for original in registry.definitions():
        name = original.name
        if getattr(original.handler, '_campaign1_seam', False):
            continue
        seed = sources['tools'].get(name)
        use_original = name in PURE or (real_owned and name in OWNED) or (sources.get('schema_version', 1) >= 2 and name.startswith('todo.'))

        def handler(arguments, context, request, *, definition=original, seed=seed, use_original=use_original):
            checked = definition.validate_arguments(arguments)
            receipt({'kind': 'validated_handler_arguments', 'tool': definition.name, 'arguments': checked, 'scope': 'after original registry authorization and validation', 'actor_profile': request.actor_profile, 'confirmed': request.confirmed, 'permission_level': definition.permission_level, 'risk_level': definition.risk_level, 'side_effect': definition.side_effect, 'request_source': request.source})
            if use_original:
                if definition.name in {'time.now', 'time.convert', 'time.elapsed'}:
                    receipt({'kind': 'fixture_handler', 'tool': definition.name, 'arguments': checked, 'evidence_kind': 'actual_original_handler_with_controlled_clock', 'scope': 'only hanni.tools.timekeep clock symbols controlled; original timezone/parser/date logic and process-global clocks retained'})
                    return original_time_with_clock(definition, checked, context, request, case['fixture'])
                path_fields = set(definition.input_schema).intersection(PATH_KEYS)
                if definition.name.startswith(('file.', 'folder.', 'archive.')) and (not path_fields or any((not isinstance(checked.get(key), str) or not checked[key].strip() for key in path_fields))):
                    return ToolResult(definition.name, False, 'An explicit owned fixture path is required; no default owner directory was accessed.', {}, error={'code': 'MISSING_OWNED_FIXTURE_PATH', 'retryable': False})
                for key, value in checked.items():
                    if key in PATH_KEYS and value is not None:
                        values = value if isinstance(value, list) else [value]
                        for path in values:
                            owned_note_read = definition.name == 'file.read' and request.source == 'tool.verification' and isinstance(path, str) and Path(path).resolve().is_relative_to((state / 'notes').resolve())
                            if not isinstance(path, str) or not (Path(path).resolve().is_relative_to(root.resolve()) or owned_note_read):
                                return ToolResult(definition.name, False, 'Evaluation boundary rejected a path outside the owned fixture.', {}, error={'code': 'OUTSIDE_OWNED_FIXTURE', 'retryable': False})
                receipt({'kind': 'fixture_handler', 'tool': definition.name, 'arguments': checked, 'evidence_kind': 'actual_original_owned_handler'})
                return definition.handler(checked, context, request)
            if seed is None:
                return ToolResult(definition.name, False, 'No controlled dependency is registered; execution was blocked.', {}, error={'code': 'UNSEEDED_DEPENDENCY', 'retryable': False})
            data = substitute(deepcopy(seed.get('data', {})), root)
            if definition.name in {'process.find', 'process.inspect'} and sources.get('schema_version', 1) >= 2:
                receipt({'kind': 'fixture_handler', 'tool': definition.name, 'arguments': checked, 'evidence_kind': 'actual_original_handler_with_controlled_process_inventory', 'scope': 'module-local process and clock providers; no owner process state queried'})
                return original_process_with_inventory(definition, checked, context, request, case['fixture'], process_inventory)
            if definition.name == 'env.get' and checked.get('name') in case['fixture'].get('environment', {}):
                data.update(name=checked['name'], value=case['fixture']['environment'][checked['name']], set=True)
            for binding in seed.get('bindings', []):
                if binding['argument'] in checked:
                    set_path(data, binding['data_path'], checked[binding['argument']])
            receipt({'kind': 'fixture_handler', 'tool': definition.name, 'arguments': checked, 'evidence_kind': 'controlled_dependency', 'scope': seed.get('effect_scope'), 'data': data})
            return ToolResult(definition.name, seed.get('ok', True), seed.get('message', 'Controlled dependency source.'), data, error=seed.get('error'))
        handler._campaign1_seam = True
        assert registry.unregister(name, expected=original)
        registry.register(replace(original, handler=handler))
