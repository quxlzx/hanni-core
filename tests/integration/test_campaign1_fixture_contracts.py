"""Original semantic handlers on isolated predeclared stores/providers."""
import json, time, tempfile, unittest
from datetime import datetime
from pathlib import Path
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.tools.base import ToolRequest
from hanni.tools import timekeep, overview, system
from hanni.tools.google_access import GoogleAccessError
from hanni.reliability.execution import close_service
from scripts.campaign1_verification.fixtures import setup, install_seams, FixtureVault
ROOT = Path(__file__).resolve().parents[2]

class FixtureContracts(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.state = self.base / 'state'
        self.files = self.base / 'files'
        self.events = []
        self.source = json.loads((ROOT / 'evals/campaign1/fixture-sources-v2.json').read_text(encoding='utf8'))
        self.case = {'scope': 'isolated development', 'query': 'Controlled semantic fixture', 'fixture': {'now': '2026-10-12T10:15:00-04:00'}}
        setup(self.case, self.files, self.state, self.source)
        cfg = load_config(ROOT / 'config', data_dir=self.state, env={})
        self.reg = build_default_registry(cfg, data_dir=self.state)
        install_seams(self.reg, self.case, self.files, self.state, self.source, self.events.append)

    def tearDown(self):
        close_service(self.state)
        self.tmp.cleanup()

    def call(self, name, args):
        return self.reg.execute(ToolRequest(name, args))

    def test_original_timezone_and_date_offset_use_fixed_instant(self):
        original_datetime = timekeep.datetime
        original_time = timekeep.time
        global_clock = time.time
        seoul = self.call('time.now', {'timezone': 'Asia/Seoul', 'kind': 'time'})
        self.assertEqual(seoul.data['iso'], '2026-10-12T23:15:00+09:00')
        tomorrow = self.call('time.now', {'timezone': 'America/New_York', 'kind': 'date', 'day_offset': 1})
        self.assertEqual(tomorrow.data['requested_date'], '2026-10-13')
        self.assertIn('October 13', tomorrow.message)
        self.assertIs(timekeep.datetime, original_datetime)
        self.assertIs(timekeep.time, original_time)
        self.assertIs(time.time, global_clock)
        with self.assertRaises(ValueError):
            self.call('time.now', {'timezone': 'invalid/timezone'})

    def test_elapsed_and_conversion_use_same_original_clock_scope(self):
        elapsed = self.call('time.elapsed', {'since': '2026-10-12T14:00:00+00:00'})
        self.assertEqual(elapsed.data['seconds'], 900)
        converted = self.call('time.convert', {'when': '10:15', 'from_timezone': 'America/New_York', 'to_timezone': 'Asia/Seoul'})
        self.assertEqual(converted.data['converted_iso'], '2026-10-12T23:15:00+09:00')

    def test_original_process_query_never_relabels_inventory(self):
        before = (overview.psutil, overview.time, system.psutil)
        selected = self.call('process.find', {'name': 'preview', 'limit': 1})
        self.assertTrue(selected.ok)
        self.assertEqual(selected.data['processes'][0]['name'], 'FixturePreview.exe')
        self.assertEqual(selected.data['processes'][0]['memory_gb'], 2)
        self.assertEqual(selected.data['processes'][0]['running_minutes'], 15)
        self.assertNotIn('cpu_percent', selected.data['processes'][0])
        missing = self.call('process.find', {'name': 'does-not-exist'})
        self.assertFalse(missing.ok)
        self.assertEqual(missing.data['count'], 0)
        with self.assertRaises(ValueError):
            self.call('process.find', {'name': 'x'})
        self.assertEqual((overview.psutil, overview.time, system.psutil), before)

    def test_original_pid_existence_never_supplies_other_fields(self):
        present = self.call('process.inspect', {'pid': 4242})
        absent = self.call('process.inspect', {'pid': 9090})
        self.assertEqual(present.data, {'pid': 4242, 'exists': True})
        self.assertEqual(absent.data, {'pid': 9090, 'exists': False})

    def test_original_account_resolution_matches_predeclared_v2_roster(self):
        access = self.reg.google_access
        self.assertEqual(access.vault.labels(), ('personal', 'work'))
        self.assertEqual(access.resolve_account('work'), 'work')
        for label in ('school', 'unknown-fixture-account'):
            with self.assertRaises(GoogleAccessError) as failure:
                access.resolve_account(label)
            self.assertEqual(failure.exception.code, 'not_connected')
        self.assertTrue(access.has_capability('work', 'gmail.read'))
        self.assertEqual(FixtureVault().labels(), ('personal', 'school'))

    def test_original_todo_string_id_lookup_and_status_filters(self):
        existing = self.call('todo.get', {'id': 'task_fixture_1'})
        self.assertEqual(existing.data['task']['id'], 'task_fixture_1')
        with self.assertRaises(ValueError):
            self.call('todo.get', {'id': 'task_fixture_unknown'})
        with self.assertRaises(Exception):
            self.call('todo.get', {'id': 1})
        self.assertEqual(self.call('todo.list', {'status': 'completed'}).data['count'], 0)
        self.assertEqual(self.call('todo.list', {'course': 'Different course'}).data['count'], 0)

    def test_original_owned_note_write_has_bounded_verification_read(self):
        case = {**self.case, 'scope': 'isolated final'}
        cfg = load_config(ROOT / 'config', data_dir=self.state, env={})
        reg = build_default_registry(cfg, data_dir=self.state)
        install_seams(reg, case, self.files, self.state, self.source, self.events.append)
        result = reg.execute(ToolRequest('note.append', {'text': 'Owned original note', 'tag': 'control'}))
        self.assertTrue(result.ok)
        self.assertEqual(result.verification['status'], 'VERIFIED')
        foreign = reg.execute(ToolRequest('file.read', {'path': str(self.base / 'foreign.txt')}, source='tool.verification'))
        self.assertFalse(foreign.ok)
        self.assertEqual(foreign.error['code'], 'OUTSIDE_OWNED_FIXTURE')
if __name__ == '__main__':
    unittest.main()
