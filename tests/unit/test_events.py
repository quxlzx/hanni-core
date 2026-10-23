from __future__ import annotations
import unittest
from datetime import datetime, timezone
from hanni.core.events import SCHEMA_VERSION, Event, EventType, EventValidationError

class EventTests(unittest.TestCase):

    def test_roundtrip_json(self) -> None:
        event = Event(EventType.TOOL_REQUESTED, source='tools.registry', payload={'tool': 'open_application', 'args': {'name': 'code'}}, correlation_id='abc')
        restored = Event.from_json(event.to_json())
        self.assertEqual(restored, event)
        self.assertEqual(restored.schema_version, SCHEMA_VERSION)
        self.assertIsNotNone(restored.timestamp.tzinfo)

    def test_payload_is_copied(self) -> None:
        payload = {'a': 1}
        event = Event(EventType.SYSTEM_ALERT, source='vision.capture', payload=payload)
        payload['a'] = 2
        self.assertEqual(event.payload['a'], 1)

    def test_unknown_type_rejected(self) -> None:
        with self.assertRaisesRegex(EventValidationError, 'unknown event type'):
            Event.from_dict({'event_id': 'x', 'type': 'NOT_A_TYPE', 'timestamp': '2026-08-29T00:00:00+00:00', 'source': 's'})
        with self.assertRaises(EventValidationError):
            Event('TOOL_REQUESTED', source='s')

    def test_naive_timestamp_rejected(self) -> None:
        with self.assertRaisesRegex(EventValidationError, 'timezone-aware'):
            Event(EventType.SYSTEM_ALERT, source='s', timestamp=datetime(2026, 1, 1))
        with self.assertRaises(EventValidationError):
            Event.from_dict({'event_id': 'x', 'type': 'SYSTEM_ALERT', 'timestamp': '2026-01-01T00:00:00', 'source': 's'})

    def test_missing_fields_and_bad_json(self) -> None:
        with self.assertRaisesRegex(EventValidationError, 'missing required field'):
            Event.from_dict({'type': 'SYSTEM_ALERT'})
        with self.assertRaisesRegex(EventValidationError, 'invalid event JSON'):
            Event.from_json('{nope')
        with self.assertRaisesRegex(EventValidationError, 'source'):
            Event(EventType.SYSTEM_ALERT, source='  ')

    def test_non_serializable_payload_rejected(self) -> None:
        with self.assertRaisesRegex(EventValidationError, 'JSON-serializable'):
            Event(EventType.SYSTEM_ALERT, source='s', payload={'when': datetime.now(timezone.utc)})
        with self.assertRaisesRegex(EventValidationError, 'payload must be a mapping'):
            Event(EventType.SYSTEM_ALERT, source='s', payload=['not', 'a', 'mapping'])

    def test_all_v1_event_types_present(self) -> None:
        expected = {'VOICE_ACTIVITY_STARTED', 'VOICE_ACTIVITY_ENDED', 'TRANSCRIPT_READY', 'OWNER_COMMAND', 'SCREEN_CHANGED', 'ACTIVE_WINDOW_CHANGED', 'MODEL_STARTED', 'MODEL_FAILED', 'TASK_CREATED', 'TASK_UPDATED', 'TASK_COMPLETED', 'TOOL_REQUESTED', 'TOOL_COMPLETED', 'TOOL_FAILED', 'MEMORY_CREATED', 'EMERGENCY_STOP', 'HANNI_STARTED', 'HANNI_STOPPED', 'SYSTEM_ALERT', 'EMERGENCY_STOP_CLEARED'}
        self.assertEqual(expected, {t.value for t in EventType})

    def test_two_pc_event_types_are_gone(self) -> None:
        """D-0009: no Discord or node lifecycle events in V1."""
        self.assertFalse({'DISCORD_MESSAGE', 'NODE_CONNECTED', 'NODE_DISCONNECTED'} & {t.value for t in EventType})
