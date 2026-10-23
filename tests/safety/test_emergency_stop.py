"""Emergency stop must be deterministic, idempotent, persisted, and owner/local-clear only."""
from __future__ import annotations
import json
import threading
from datetime import datetime, timezone
from hanni.core.events import EventType
from hanni.core.identity import Actor
from hanni.core.shutdown import EmergencyStop, EmergencyStopActive, FileStopStateStore, LocalStopControls, MemoryStopStateStore, NotAuthorizedToClear, StopRecord, StopSource
from hanni.core.state import RuntimeMode
from tests.helpers import TempDirTestCase
OWNER = Actor.owner('voice')
UNPRIVILEGED = Actor.internal('supervisor-llm')
LOCAL = Actor.local('LAPTOP')

class EmergencyStopTests(TempDirTestCase):

    def test_starts_armed(self) -> None:
        stop = EmergencyStop()
        self.assertFalse(stop.is_tripped)
        self.assertIs(stop.mode, RuntimeMode.NORMAL)
        stop.guard('open application')

    def test_trip_is_idempotent_and_keeps_first_record(self) -> None:
        stop = EmergencyStop()
        first = stop.trip(source=StopSource.OWNER_VOICE, requested_by=OWNER, reason='stop everything')
        second = stop.trip(source=StopSource.LOCAL_HOTKEY, requested_by=LOCAL, reason='hotkey')
        self.assertIs(first, second)
        self.assertEqual(stop.record.source, StopSource.OWNER_VOICE)
        self.assertIs(stop.mode, RuntimeMode.SAFE_MODE)

    def test_guard_refuses_actions_while_tripped(self) -> None:
        stop = EmergencyStop()
        stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('watchdog'))
        with self.assertRaises(EmergencyStopActive) as ctx:
            stop.guard('run_command')
        self.assertIn('run_command', str(ctx.exception))

    def test_anyone_may_trip(self) -> None:
        stop = EmergencyStop()
        record = stop.trip(source=StopSource.INTERNAL, requested_by=UNPRIVILEGED)
        self.assertTrue(stop.is_tripped)
        self.assertEqual(record.requested_by, UNPRIVILEGED.label)

    def test_non_owner_cannot_clear(self) -> None:
        stop = EmergencyStop()
        stop.trip(source=StopSource.OWNER_TEXT, requested_by=OWNER)
        with self.assertRaises(NotAuthorizedToClear):
            stop.clear(UNPRIVILEGED)
        with self.assertRaises(NotAuthorizedToClear):
            stop.clear(Actor.internal('watchdog'))
        self.assertTrue(stop.is_tripped)

    def test_unauthorized_clear_is_refused_even_when_not_tripped(self) -> None:
        stop = EmergencyStop()
        with self.assertRaises(NotAuthorizedToClear):
            stop.clear(UNPRIVILEGED)

    def test_owner_and_local_machine_can_clear(self) -> None:
        for actor in (OWNER, LOCAL):
            with self.subTest(actor=actor.label):
                stop = EmergencyStop()
                stop.trip(source=StopSource.OWNER_VOICE, requested_by=OWNER)
                stop.clear(actor)
                self.assertFalse(stop.is_tripped)
                stop.guard('resume')

    def test_listeners_notified_and_failing_listener_does_not_block(self) -> None:
        stop = EmergencyStop()
        seen: list[tuple[str, StopRecord | None]] = []

        def broken(change, record):
            raise RuntimeError('listener crashed')
        stop.add_listener(broken)
        stop.add_listener(lambda change, record: seen.append((change, record)))
        record = stop.trip(source=StopSource.OWNER_VOICE, requested_by=OWNER)
        stop.clear(OWNER)
        self.assertEqual(seen, [('tripped', record), ('cleared', None)])
        self.assertFalse(stop.is_tripped)

    def test_concurrent_trips_produce_exactly_one_record(self) -> None:
        stop = EmergencyStop()
        records: list[StopRecord] = []
        barrier = threading.Barrier(8)

        def worker(i: int) -> None:
            barrier.wait()
            records.append(stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal(f't{i}')))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len({id(r) for r in records}), 1)

    def test_state_persists_across_instances(self) -> None:
        store = FileStopStateStore.for_data_dir(self.data_dir)
        EmergencyStop(store).trip(source=StopSource.LOCAL_TERMINAL, requested_by=LOCAL, reason='persist me')
        restored = EmergencyStop(FileStopStateStore.for_data_dir(self.data_dir))
        self.assertTrue(restored.is_tripped)
        self.assertEqual(restored.record.reason, 'persist me')
        self.assertEqual(restored.record.source, StopSource.LOCAL_TERMINAL)
        restored.clear(LOCAL)
        self.assertFalse(store.path.exists())
        self.assertFalse(EmergencyStop(FileStopStateStore.for_data_dir(self.data_dir)).is_tripped)

    def test_corrupt_state_file_fails_safe(self) -> None:
        store = FileStopStateStore.for_data_dir(self.data_dir)
        store.path.parent.mkdir(parents=True)
        store.path.write_text('{not json', encoding='utf-8')
        stop = EmergencyStop(store)
        self.assertTrue(stop.is_tripped)
        self.assertEqual(stop.record.source, StopSource.PERSISTED)
        with self.assertRaises(EmergencyStopActive):
            stop.guard('anything')

    def test_record_roundtrip_and_event(self) -> None:
        record = StopRecord(datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc), StopSource.OWNER_VOICE, OWNER.label, 'test')
        self.assertEqual(StopRecord.from_dict(json.loads(json.dumps(record.to_dict()))), record)
        event = record.to_event()
        self.assertIs(event.type, EventType.EMERGENCY_STOP)
        self.assertEqual(event.source, 'core.shutdown')
        self.assertEqual(event.payload['source'], 'owner-voice')

    def test_memory_store_used_by_default(self) -> None:
        stop = EmergencyStop(MemoryStopStateStore())
        stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('x'))
        self.assertTrue(stop.is_tripped)

    def test_local_controls_trip_and_clear(self) -> None:
        controls = LocalStopControls(self.data_dir, machine_name='LAPTOP')
        controls.trip('terminal')
        self.assertIs(controls.mode, RuntimeMode.SAFE_MODE)
        self.assertEqual(controls.record.requested_by, 'local-machine:LAPTOP')
        LocalStopControls(self.data_dir, machine_name='LAPTOP').clear()
        self.assertIs(LocalStopControls(self.data_dir, machine_name='LAPTOP').mode, RuntimeMode.NORMAL)

    def test_long_running_instance_refreshes_persisted_cross_process_state(self) -> None:
        first = EmergencyStop(FileStopStateStore.for_data_dir(self.data_dir))
        second = EmergencyStop(FileStopStateStore.for_data_dir(self.data_dir))
        self.assertIsNone(second.record)
        first.trip(source=StopSource.OWNER_TEXT, requested_by=OWNER, reason='cross-process')
        self.assertIsNotNone(second.record)
        second.clear(OWNER)
        self.assertIsNone(first.record)
