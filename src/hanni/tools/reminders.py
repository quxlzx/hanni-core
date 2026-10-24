"""Durable one-time reminders, delivered to the existing notification center."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
import sqlite3
import threading
from uuid import uuid4
from zoneinfo import ZoneInfo

from .base import ToolDefinition, ToolResult, ToolRequest
from .whenparse import parse_when
from hanni.memory.privacy import validate_memory_text


def resolve_time(phrase, zone, *, now=None, require_time=True):
    tz = ZoneInfo(zone)
    reference = now or datetime.now(tz)
    relative = re.fullmatch(r'in\s+(\d+)\s*(seconds?|minutes?|mins?|hours?|hrs?|days?)', phrase.strip(), re.I)
    if relative:
        amount, unit = int(relative[1]), relative[2].lower()
        seconds = amount * (1 if unit.startswith('second') else 60 if unit.startswith(('min',)) else 3600 if unit.startswith(('hour', 'hr')) else 86400)
        if not 5 <= seconds <= 366 * 86400:
            raise ValueError('Choose a reminder from 5 seconds to 366 days ahead.')
        return (reference.astimezone(timezone.utc) + timedelta(seconds=seconds)).astimezone(tz)
    parsed = parse_when(phrase, now=reference.replace(tzinfo=None))
    if require_time and parsed.all_day:
        raise ValueError('Include a time, for example tomorrow at 9am or 2026-12-01T09:00-06:00.')
    result = parsed.start
    if result.tzinfo is None:
        early, late = result.replace(tzinfo=tz, fold=0), result.replace(tzinfo=tz, fold=1)
        if early.utcoffset() != late.utcoffset():
            raise ValueError('That local time is ambiguous or missing during a clock change. Include an explicit UTC offset.')
        result = early
    return result.astimezone(tz)


def split_reminder(argument):
    if ' | ' in argument:
        when, message = argument.split(' | ', 1)
    elif argument.startswith('"'):
        match = re.fullmatch(r'"([^"\n]+)"\s+(.+)', argument, re.S)
        if not match:
            raise ValueError('Use /remind "tomorrow at 9am" Check the report.')
        when, message = match.groups()
    else:
        clock = r'(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})'
        pattern = (r'^(in\s+\d+\s*(?:seconds?|minutes?|mins?|hours?|hrs?|days?)|'
                   r'\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}(?::\d{2})?(?:[Zz]|[+-]\d{2}:\d{2})?|'
                   r'(?:(?:today|tomorrow|(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\s+(?:at\s+)?|at\s+)' + clock + r')\s+(.+)$')
        match = re.fullmatch(pattern, argument.strip(), re.I | re.S)
        if not match:
            raise ValueError('Use /remind in 10 minutes Check the report, or /remind tomorrow at 9am | Check the report.')
        when, message = match.groups()
    if not when.strip() or not message.strip():
        raise ValueError('Include both a scheduled time and a reminder message.')
    return when.strip(), message.strip()


class ReminderStore:
    def __init__(self, root):
        self.path = Path(root).resolve() / 'reminders.sqlite3'
        if self.path.is_symlink():
            raise ValueError('Reminder storage cannot be a symbolic link.')

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, payload TEXT, message TEXT, scheduled_at TEXT, zone TEXT, status TEXT, error TEXT)')
            yield db

    def create(self, when, message, zone, request_id):
        message = validate_memory_text(message, max_chars=1000)
        due = datetime.fromisoformat(when)
        if due.tzinfo is None:
            raise ValueError('Reminder time must include a UTC offset.')
        due = due.astimezone(timezone.utc)
        payload = json.dumps([due.isoformat(), message, zone])
        with self.connect() as db:
            prior = db.execute('SELECT * FROM reminders WHERE request_id=?', (request_id,)).fetchone()
            if prior:
                if prior['payload'] != payload:
                    raise ValueError('Reminder request ID was reused with different fields.')
                return dict(prior)
            if due <= datetime.now(timezone.utc):
                raise ValueError('Choose a reminder time in the future.')
            if (due - datetime.now(timezone.utc)).days > 366:
                raise ValueError('Reminders are limited to 366 days ahead.')
            if db.execute("SELECT count(*) FROM reminders WHERE status='scheduled'").fetchone()[0] >= 1000:
                raise ValueError('Review your existing reminders before adding more.')
            record_id = uuid4().hex
            db.execute('INSERT INTO reminders VALUES (?,?,?,?,?,?,?,NULL)', (record_id, request_id, payload, message, due.isoformat(), zone, 'scheduled'))
            return dict(db.execute('SELECT * FROM reminders WHERE id=?', (record_id,)).fetchone())

    def list(self, *, due_before=None):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM reminders WHERE status='scheduled'" +
                (' AND scheduled_at<=?' if due_before else '') + ' ORDER BY scheduled_at LIMIT 1000', (due_before,) if due_before else ())]

    def delivered(self, record_id):
        with self.connect() as db:
            return bool(db.execute("UPDATE reminders SET status='delivered',error=NULL WHERE id=? AND status='scheduled'", (record_id,)).rowcount)


class ReminderDelivery:
    def __init__(self, features):
        self.features = features
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='hanni-reminders', daemon=True)

    def start(self):
        self.thread.start()

    def tick(self, *, now=None):
        if not isinstance(getattr(self.features, 'root', None), Path) or not (self.features.root / 'reminders.sqlite3').exists():
            return
        self.features.registry.context.emergency_stop.guard('deliver reminders')
        store = ReminderStore(self.features.root)
        timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        due = store.list(due_before=timestamp)
        if due and not self.features.store.notifications()['preferences']['categories']['reminders']:
            return
        for row in due:
            if self.stop.is_set():
                return
            self.features.store.ingest([{'key': 'reminder:' + row['id'], 'category': 'reminders', 'priority': 'action_required',
                'title': 'Reminder', 'message': row['message'], 'target': {'screen': 'notifications', 'id': row['id']}, 'created_at': row['scheduled_at']}])
            if not store.delivered(row['id']):
                continue
            # The durable in-app event is authoritative. Desktop toast is best
            # effort and is never replayed after a crash or acknowledgment loss.
            try:
                self.features.registry.execute(ToolRequest('notify.toast', {'title': 'HANNI reminder', 'message': row['message']}, source='reminder-delivery'))
            except (RuntimeError, OSError, ValueError):
                pass

    def run(self):
        while not self.stop.wait(.5):
            try:
                self.tick()
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                # Retain scheduled rows. Retry delivery, never discard a reminder.
                pass

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=12)


def definitions(root):
    store = ReminderStore(root)
    def create(args, context, request):
        record = store.create(args['when'], args['message'], context.timezone_name or 'UTC', request.correlation_id or uuid4().hex)
        return ToolResult('reminder.create', True, 'Reminder saved.', {'reminder': record})
    return (ToolDefinition('reminder.create', 'Save one explicit one-time reminder for the local notification center.',
        2, 2, {'when': str, 'message': str}, {'reminder': 'object'}, create, side_effect='reversible_write', background_allowed=False),)
