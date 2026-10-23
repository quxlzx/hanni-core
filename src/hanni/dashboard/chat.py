"""Local chat history and a bounded inbox consumed by the existing CLI loop."""
from __future__ import annotations

from collections import deque
import secrets
import sqlite3
import threading
import time
import uuid
import queue
import sys


class ChatHub:
    def __init__(self, path=None):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path) if path else ':memory:', check_same_thread=False)
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, turn TEXT, role TEXT, content TEXT, channel TEXT, status TEXT, created REAL)')
        self.db.commit()
        self.owned_turns = set()
        self.queue = deque()
        self.seen = set()
        self.current = None
        self.ready = False
        self.closed = False
        self.stopping = False
        self.token = secrets.token_urlsafe(32)
        self.epoch = uuid.uuid4().hex
        self.saved = path is not None

    def _add(self, turn, role, content, channel, status):
        self.owned_turns.add(turn)
        cursor = self.db.execute('INSERT INTO messages(turn,role,content,channel,status,created) VALUES (?,?,?,?,?,?)',
                                 (turn, role, content, channel, status, time.time()))
        self.db.commit()
        return cursor.lastrowid

    def submit(self, request_id, message):
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ValueError('Enter a message of 1 to 4000 characters.')
        if not isinstance(request_id, str) or len(request_id) > 40:
            raise ValueError('Invalid request ID.')
        try:
            request_id = str(uuid.UUID(request_id))
        except ValueError:
            raise ValueError('Invalid request ID.') from None
        with self.lock:
            if not self.ready or self.closed or self.stopping:
                raise RuntimeError('HANNI is not ready. Check the launcher terminal.')
            if request_id in self.seen or self.db.execute('SELECT 1 FROM messages WHERE turn=? LIMIT 1', (request_id,)).fetchone():
                return request_id
            if len(self.queue) >= 8:
                raise RuntimeError('The message queue is full. Wait for HANNI to finish.')
            self.seen.add(request_id)
            self._add(request_id, 'user', message.strip(), 'browser', 'queued')
            self.queue.append((request_id, message.strip()))
            return request_id

    def take(self):
        with self.lock:
            if self.closed or not self.queue:
                return None
            self.current = self.queue.popleft()
            self.db.execute("UPDATE messages SET status='complete' WHERE turn=?", (self.current[0],))
            self.db.commit()
            return self.current[1]

    def begin(self, prompt, channel):
        with self.lock:
            if self.current:
                turn, _ = self.current
                channel = 'browser'
            else:
                turn = str(uuid.uuid4())
                self._add(turn, 'user', prompt[:4000], channel, 'complete')
            return self._add(turn, 'assistant', '', channel, 'working')

    def update(self, row, content, status='working'):
        with self.lock:
            self.db.execute('UPDATE messages SET content=?,status=? WHERE id=?', (content[:64000], status, row))
            self.db.commit()
            if status != 'working':
                self.current = None

    def turn_context(self, row):
        """Return only the stored request identity and channel for an assistant row."""
        with self.lock:
            result = self.db.execute("SELECT turn,channel FROM messages WHERE id=? AND role='assistant'",
                                     (row,)).fetchone()
            if result is None:
                raise ValueError('Unknown assistant turn.')
            return result

    def note(self, prompt, message, channel='browser'):
        row = self.begin(prompt, channel)
        self.update(row, message, 'complete')

    def snapshot(self, before=None):
        with self.lock:
            rows = self.db.execute('SELECT id,turn,role,content,channel,status,created FROM messages '
                                   'WHERE id < ? ORDER BY id DESC LIMIT 100', (before or 2**63-1,)).fetchall()
            keys = ('id','turn','role','content','channel','status','created')
            more = bool(rows and self.db.execute('SELECT 1 FROM messages WHERE id < ? LIMIT 1',(rows[-1][0],)).fetchone())
            return dict(messages=[dict(zip(keys,row)) for row in reversed(rows)], has_more=more,
                        ready=self.ready and not self.closed and not self.stopping, queued=len(self.queue),
                        busy=self.current is not None or bool(self.db.execute("SELECT 1 FROM messages WHERE status='working' LIMIT 1").fetchone()),
                        token=self.token, epoch=self.epoch, saved=self.saved)

    def clear(self):
        with self.lock:
            if not self.ready or self.closed:
                raise RuntimeError('Start the assistant before clearing history.')
            if self.current or self.queue or self.db.execute("SELECT 1 FROM messages WHERE status='working' LIMIT 1").fetchone():
                raise RuntimeError('Wait for the current conversation to finish before clearing history.')
            self.db.execute('DELETE FROM messages')
            self.db.commit()
            self.epoch = uuid.uuid4().hex
            self.token = secrets.token_urlsafe(32)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.stopping = True
            self.ready = False
            self.queue.clear()
            self.db.executemany("UPDATE messages SET status='interrupted' WHERE turn=? AND status IN ('working','queued')",
                                [(turn,) for turn in self.owned_turns])
            self.db.commit()

    def request_shutdown(self):
        """Stop accepting work while the current assistant response finishes."""
        with self.lock:
            self.stopping = True
            self.ready = False
            queued = [turn for turn, _ in self.queue]
            self.queue.clear()
            self.db.executemany("UPDATE messages SET status='interrupted' WHERE turn=? AND status='queued'",
                                [(turn,) for turn in queued])
            self.db.commit()

    def activate(self):
        # Called only after the CLI has acquired its existing session/job owner
        # lock. A monitor-only or failed second launch must not modify live chat.
        with self.lock:
            if self.stopping or self.closed:
                return
            self.db.execute("UPDATE messages SET status='interrupted' WHERE status IN ('queued','working')")
            self.db.commit()
            self.ready = True


_hub = None


def install(hub):
    global _hub
    _hub = hub


def current_hub():
    return _hub


_terminal_lock = threading.Lock()
_terminal_source = None


def _terminal_inputs():
    """Reuse one stdin reader across controller restarts.

    A Windows console read cannot be cancelled by setting a Python event.
    Starting another reader would leave the previous session stealing input.
    """
    global _terminal_source
    with _terminal_lock:
        if _terminal_source is None or _terminal_source[0] is not sys.stdin:
            inbox, ended = queue.Queue(), threading.Event()
            _terminal_source = (sys.stdin, inbox, ended)
            def read():
                while True:
                    try:
                        value = input('You> ')
                    except (EOFError, OSError):
                        ended.set()
                        return
                    inbox.put(value)
            threading.Thread(target=read, name='hanni-terminal-input', daemon=True).start()
        return _terminal_source[1:]


def keyboard_inputs(hub, *, stop_event=None):
    """Keep terminal input available while the main thread consumes browser chat."""
    inbox, ended = _terminal_inputs()
    while stop_event is None or not stop_event.is_set():
        browser = hub.take()
        if browser is not None:
            yield browser, True
            continue
        try:
            value = inbox.get(timeout=.1)
        except queue.Empty:
            if ended.is_set():
                return
            continue
        yield value.strip(), False


def attach(session, channel):
    if _hub is None:
        return session
    _hub.activate()
    return ChatSession(session, _hub, channel)


class ChatSession:
    def __init__(self, session, hub, channel):
        self.fallback_session = session
        self.hub, self.channel = hub, channel

    def stream_response(self, prompt, **kwargs):
        from hanni.reliability.context import request_scope
        row = self.hub.begin(prompt, self.channel)
        request_id, channel = self.hub.turn_context(row)
        content, updated = '', 0.0
        try:
            with request_scope(request_id, channel):
                for chunk in self.fallback_session.stream_response(prompt, **kwargs):
                    content += chunk
                    if time.monotonic() - updated > .1:
                        self.hub.update(row, content)
                        updated = time.monotonic()
                    yield chunk
            from hanni.core.response_stream import check_cancelled
            check_cancelled()
            self.hub.update(row, content or 'No response was returned.', 'complete')
        except BaseException:
            self.hub.update(row, content or 'The response was interrupted. Check the launcher terminal.', 'interrupted')
            raise

    def invalidate_memory_context(self):
        return self.fallback_session.invalidate_memory_context()

    def close(self):
        self.hub.close()
