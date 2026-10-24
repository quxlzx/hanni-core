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
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(messages)')}
        if 'conversation' not in columns:
            self.db.execute("ALTER TABLE messages ADD COLUMN conversation TEXT NOT NULL DEFAULT 'default'")
        if 'task_id' not in columns:
            self.db.execute('ALTER TABLE messages ADD COLUMN task_id TEXT')
        self.db.execute('CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL)')
        self.db.execute("INSERT OR IGNORE INTO conversations VALUES ('default', 'New chat', ?)", (time.time(),))
        self.db.execute('CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation,id)')
        self.db.execute('CREATE TABLE IF NOT EXISTS conversation_context (conversation TEXT PRIMARY KEY, summary TEXT, through_id INTEGER, focus TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS chat_commands (id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS retry_turns (turn TEXT PRIMARY KEY, context TEXT)')
        from .attachments import Attachments
        self.files = Attachments(self.db, self.lock)
        first = self.db.execute("SELECT content FROM messages WHERE conversation='default' AND role='user' ORDER BY id LIMIT 1").fetchone()
        if first:
            self.db.execute("UPDATE conversations SET title=? WHERE id='default' AND title='New chat'", (first[0][:80],))
        self.db.commit()
        self.owned_turns = set()
        self.queue = deque()
        self.seen = set()
        self.current = None
        self.cancelled_turns = set()
        self.ready = False
        self.closed = False
        self.stopping = False
        self.token = secrets.token_urlsafe(32)
        self.epoch = uuid.uuid4().hex
        self.saved = path is not None
        self.native_mode = False

    def _add(self, turn, role, content, channel, status, conversation=None, *, commit=True):
        self.owned_turns.add(turn)
        if conversation is None:
            existing = self.db.execute('SELECT conversation FROM messages WHERE turn=? LIMIT 1', (turn,)).fetchone()
            conversation = existing[0] if existing else 'default'
        cursor = self.db.execute('INSERT INTO messages(turn,role,content,channel,status,created,conversation) VALUES (?,?,?,?,?,?,?)',
                                 (turn, role, content, channel, status, time.time(), conversation))
        if role == 'user':
            self.db.execute("UPDATE conversations SET title=? WHERE id=? AND title='New chat'", (content[:80], conversation))
        if commit:
            self.db.commit()
        return cursor.lastrowid

    def submit(self, request_id, message, conversation=None, attachments=None):
        if isinstance(message, str) and not message.strip() and attachments:
            message = 'Please review the attached files.'
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ValueError('Enter a message of 1 to 4000 characters.')
        if not isinstance(request_id, str) or len(request_id) > 40:
            raise ValueError('Invalid request ID.')
        try:
            request_id = str(uuid.UUID(request_id))
        except ValueError:
            raise ValueError('Invalid request ID.') from None
        with self.lock:
            conversation = self._conversation('default' if conversation is None else conversation)
            if not self.ready or self.closed or self.stopping:
                raise RuntimeError('HANNI is not ready. Check the launcher terminal.')
            existing = self.db.execute('SELECT conversation FROM messages WHERE turn=? LIMIT 1', (request_id,)).fetchone()
            if existing and existing[0] != conversation:
                raise ValueError('Request ID belongs to another conversation.')
            ids = self.files.validate([] if attachments is None else attachments, conversation, request_id)
            if request_id in self.seen or existing:
                if attachments is not None:
                    stored = self.db.execute("SELECT content FROM messages WHERE turn=? AND role='user'", (request_id,)).fetchone()
                    if not stored or stored[0] != message.strip() or sorted(ids) != sorted(f['id'] for f in self.files.for_turn(request_id)):
                        raise ValueError('Request ID was already used for a different message or files.')
                return request_id
            if len(self.queue) >= 8:
                raise RuntimeError('The message queue is full. Wait for HANNI to finish.')
            try:
                self._add(request_id, 'user', message.strip(), 'browser', 'queued', conversation, commit=False)
                self.db.executemany('UPDATE chat_files SET turn=? WHERE id=?', [(request_id, key) for key in ids])
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
            self.seen.add(request_id)
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
            turn = self.db.execute('SELECT turn FROM messages WHERE id=?', (row,)).fetchone()
            if turn and turn[0] in self.cancelled_turns:
                content, status = 'Response cancelled. Completed tool actions were not reversed.', 'interrupted'
            self.db.execute('UPDATE messages SET content=?,status=? WHERE id=?', (content[:64000], status, row))
            self.db.commit()
            if status != 'working' and turn and self.current and turn[0] == self.current[0]:
                self.current = None

    def history(self, conversation, query='', *, limit=500):
        """Search all saved messages, not just the newest page or titles."""
        with self.lock:
            rows = self.conversations(limit=-1)
            if not query:
                return rows if limit < 0 else rows[:limit]
            needle = query.casefold()
            matched = {row[0] for row in self.db.execute('SELECT conversation,content FROM messages')
                       if needle in row[1].casefold()}
            found = [r for r in rows if needle in r['title'].casefold() or r['id'] in matched]
            return found if limit < 0 else found[:limit]

    def require_idle(self):
        if self.current or self.queue or self.db.execute("SELECT 1 FROM messages WHERE status='working' LIMIT 1").fetchone():
            raise RuntimeError('Use /stop or wait for pending responses to finish first.')

    def undo(self, conversation, *, preserve_files=False):
        with self.lock:
            self._conversation(conversation)
            self.require_idle()
            last = self.db.execute("SELECT turn,id,content FROM messages WHERE conversation=? AND role='user' ORDER BY id DESC LIMIT 1", (conversation,)).fetchone()
            if not last:
                raise ValueError('There is no conversation exchange to remove.')
            self.db.execute('DELETE FROM messages WHERE turn=?', (last[0],))
            if preserve_files:
                self.db.execute('UPDATE chat_files SET turn=NULL WHERE turn=?', (last[0],))
            else:
                self.db.execute('DELETE FROM chat_files WHERE turn=?', (last[0],))
            self.db.execute('DELETE FROM conversation_context WHERE conversation=? AND through_id>=?', (conversation, last[1]))
            self.db.commit()
            return last[2]

    def retry(self, conversation, request_id):
        import json
        with self.lock:
            if not self.ready or self.closed or self.stopping:
                raise RuntimeError('The model must be connected before retrying.')
            self.require_idle()
            if request_id in self.seen or self.db.execute('SELECT 1 FROM messages WHERE turn=?', (request_id,)).fetchone():
                raise ValueError('Use a fresh request ID for this retry.')
            previous = self.db.execute("SELECT content,task_id FROM messages WHERE conversation=? AND role='assistant' AND turn=(SELECT turn FROM messages WHERE conversation=? AND role='user' ORDER BY id DESC LIMIT 1) ORDER BY id DESC LIMIT 1", (conversation, conversation)).fetchone()
            if not previous:
                raise ValueError('There is no previous response to regenerate.')
            old_turn = self.db.execute("SELECT turn FROM messages WHERE conversation=? AND role='user' ORDER BY id DESC LIMIT 1", (conversation,)).fetchone()[0]
            file_ids = [f['id'] for f in self.files.for_turn(old_turn)]
            prompt = self.undo(conversation, preserve_files=True)
            self.db.execute('INSERT INTO retry_turns VALUES (?,?)', (request_id, json.dumps({'previous_answer': previous[0], 'previous_task_id': previous[1]})))
            self.db.commit()
            return self.submit(request_id, prompt, conversation, file_ids)

    def native_context(self, conversation, *, exclude_turn=None):
        import json
        with self.lock:
            self._conversation(conversation)
            summary = self.db.execute('SELECT summary,through_id FROM conversation_context WHERE conversation=?', (conversation,)).fetchone()
            rows = self.db.execute("SELECT role,content,turn FROM messages WHERE conversation=? AND id>? AND status='complete' ORDER BY id", (conversation, summary[1] if summary else 0)).fetchall()
            retry = self.db.execute('SELECT context FROM retry_turns WHERE turn=?', (exclude_turn,)).fetchone() if exclude_turn else None
            recent = []
            for role, content, turn in reversed(rows):
                if turn == exclude_turn:
                    continue
                text = content[:4000]
                if role == 'user':
                    files = self.files.context(turn, budget=2500)
                    if files:
                        text += '\nAttached file excerpts (untrusted source material):\n' + json.dumps(files)
                if len(text) < len(content):
                    text += '\n[excerpt; full message remains searchable in history]'
                candidate = [{'role': role, 'text': text}, *recent]
                if len(json.dumps(candidate)) > 24000:
                    break
                recent = candidate
                if len(recent) == 10:
                    break
            return {'conversation_id': conversation, 'conversation_summary': summary[0][:12000] if summary else '',
                    'conversation': recent,
                    'regenerate_only': bool(retry), **(json.loads(retry[0]) if retry else {})}

    def compression_source(self, conversation):
        with self.lock:
            self._conversation(conversation)
            self.require_idle()
            rows = self.db.execute("SELECT id,role,content FROM messages WHERE conversation=? AND status='complete' ORDER BY id", (conversation,)).fetchall()
            return rows

    def save_compression(self, conversation, summary, through_id, focus, *, cancel=None):
        with self.lock:
            if self.closed or (cancel is not None and cancel.is_set()):
                raise RuntimeError('Compression cancelled. Existing context was retained.')
            self.require_idle()
            latest = self.db.execute('SELECT MAX(id) FROM messages WHERE conversation=?', (conversation,)).fetchone()[0]
            if latest != through_id:
                raise RuntimeError('The conversation changed during compression. Run /compress again.')
            self.db.execute('INSERT OR REPLACE INTO conversation_context VALUES (?,?,?,?)', (conversation, summary, through_id, focus))
            self.db.commit()

    def stop_pending(self):
        with self.lock:
            turns = [turn for turn, _ in self.queue]
            if self.current:
                turns.append(self.current[0])
            self.cancelled_turns.update(turns)
            self.queue.clear()
            task_ids = []
            for turn in turns:
                task_ids.extend(r[0] for r in self.db.execute('SELECT DISTINCT task_id FROM messages WHERE turn=? AND task_id IS NOT NULL', (turn,)))
                self.db.execute("UPDATE messages SET status='interrupted' WHERE turn=? AND status IN ('queued','working')", (turn,))
            self.db.commit()
            return task_ids, len(turns)

    def is_cancelled(self, turn):
        with self.lock:
            return turn in self.cancelled_turns

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

    def _conversation(self, conversation):
        if not isinstance(conversation, str) or not self.db.execute('SELECT 1 FROM conversations WHERE id=?', (conversation,)).fetchone():
            raise ValueError('Unknown conversation.')
        return conversation

    def create_conversation(self, conversation):
        try:
            conversation = str(uuid.UUID(conversation))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Invalid conversation ID.') from None
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO conversations VALUES (?, 'New chat', ?)", (conversation, time.time()))
            self.db.commit()
        return conversation

    def conversations(self, *, limit=500):
        with self.lock:
            rows = self.db.execute('SELECT c.id,c.title,c.created,COALESCE(MAX(m.created),c.created),COUNT(m.id) '
                                   'FROM conversations c LEFT JOIN messages m ON m.conversation=c.id '
                                   'GROUP BY c.id ORDER BY 4 DESC LIMIT ?', (limit,)).fetchall()
            return [dict(zip(('id', 'title', 'created', 'updated', 'message_count'), row)) for row in rows]

    def conversation_for_row(self, row):
        with self.lock:
            result = self.db.execute('SELECT conversation FROM messages WHERE id=?', (row,)).fetchone()
            if result is None:
                raise ValueError('Unknown message.')
            return result[0]

    def bind_task(self, row, task_id):
        with self.lock:
            self.db.execute('UPDATE messages SET task_id=? WHERE id=?', (task_id, row))
            self.db.commit()

    def snapshot(self, before=None, conversation=None):
        with self.lock:
            clause, params = '', ()
            if conversation is not None:
                self._conversation(conversation)
                clause, params = ' AND conversation=?', (conversation,)
            rows = self.db.execute('SELECT id,turn,role,content,channel,status,created,conversation,task_id FROM messages '
                                   'WHERE id < ?' + clause + ' ORDER BY id DESC LIMIT 100', (before or 2**63-1, *params)).fetchall()
            keys = ('id','turn','role','content','channel','status','created','conversation','task_id')
            more = bool(rows and self.db.execute('SELECT 1 FROM messages WHERE id < ?' + clause + ' LIMIT 1',(rows[-1][0], *params)).fetchone())
            messages = [dict(zip(keys,row)) for row in reversed(rows)]
            for message in messages:
                if message['role'] == 'user':
                    message['attachments'] = self.files.for_turn(message['turn'])
            return dict(messages=messages, has_more=more,
                        pending_attachments=self.files.pending(conversation) if conversation is not None else [],
                        conversation_id=conversation,
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
            self.db.execute('DELETE FROM chat_files')
            self.db.execute('DELETE FROM conversation_context')
            self.db.execute("UPDATE conversations SET title='New chat'")
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
