"""Local SQLite durable memory with conservative keyed facts and verified cleanup."""

from __future__ import annotations

import re
import heapq
import hashlib
import sqlite3
import uuid
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from hanni.memory.privacy import normalize_memory_text, validate_memory_text

SCHEMA_VERSION = 3
SEMANTIC_STATUSES = frozenset({'statement', 'plan', 'decision', 'verified_outcome', 'question', 'hypothetical', 'inference',
                               'completed_claim', 'historical', 'failed_claim', 'temporary'})

_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "i", "in", "is", "it", "me", "my",
    "of", "on", "or", "that", "the", "this", "to", "was", "what", "with", "you", "your",
})
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.:+\\/-]*", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: str
    content: str
    memory_type: str
    source: str
    confidence: float
    created_at: datetime
    updated_at: datetime
    fact_key: str = ""
    fact_value: str = ""
    project_id: str = ""
    semantic_status: str = "statement"
    source_ref: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "fact_key": self.fact_key,
            "fact_value": self.fact_value,
            "project_id": self.project_id,
            "semantic_status": self.semantic_status,
            "source_ref": self.source_ref,
            "confidence_calibrated": False,
        }


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    record: MemoryRecord
    score: float


@dataclass(frozen=True, slots=True)
class MemorySuggestion:
    id: str
    kind: str
    content: str
    source: str
    source_ref: str
    target_id: str
    target_updated_at: str
    project_id: str
    semantic_status: str
    reason: str
    uncertainty: str
    related_ids: tuple[str, ...]
    status: str
    created_at: datetime
    updated_at: datetime

    def to_dict(self):
        from dataclasses import asdict
        value = asdict(self)
        value.update(created_at=self.created_at.isoformat(), updated_at=self.updated_at.isoformat())
        return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_for_match(text: str) -> str:
    return normalize_memory_text(text).casefold().strip(" .?!,;:\"'")


def classify_memory(text: str) -> str:
    value = text.casefold()
    if re.search(r"\b(?:prefer|preferred|preference|favorite|favourite|like|dislike)\b", value):
        return "preference"
    if "project" in value and ("\\" in text or "/" in text or "folder" in value or "directory" in value):
        return "project"
    if re.search(r"\b(?:workflow|routine|usually|every time)\b", value):
        return "workflow"
    if re.search(r"\b(?:decided|decision|we chose|i chose)\b", value):
        return "decision"
    if re.search(r"\b(?:correction|actually|instead of)\b", value):
        return "correction"
    if re.search(r"\b(?:device|laptop|desktop|phone|tablet)\b", value):
        return "device"
    return "fact"


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(text) if token.casefold() not in _STOPWORDS and len(token) > 1}


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _revision_matches(stored: str, expected: str) -> bool:
    """Compare legacy naive UTC timestamps with the canonical API representation.

    Reading a migrated record adds UTC to a naive timestamp without rewriting
    the user's original data. Compare the represented instant, not spelling.
    """
    try:
        return _parse_dt(stored) == _parse_dt(expected)
    except (TypeError, ValueError):
        return False


class MemoryConflictError(ValueError):
    pass


class MemoryStore:
    """Small owner-local durable memory database.

    Search stays deterministic and local. Indexed fact keys live in the same
    transactional database; there is no external vector index or durable cache.
    """

    def __init__(self, path: Path, *, max_item_chars: int = 1200) -> None:
        self.path = Path(path)
        self.max_item_chars = max_item_chars
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open one transactional SQLite connection and always close it.

        ``sqlite3.Connection.__exit__`` commits or rolls back a transaction,
        but it does *not* close the connection. On Windows that leaves the
        database file locked until the connection is garbage-collected, which
        breaks temporary-directory cleanup in tests and can hold stale handles
        in short-lived CLI commands.
        """
        connection = sqlite3.connect(self.path, timeout=10.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA secure_delete=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL UNIQUE,
                    memory_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                """
            )
            row = db.execute("SELECT value FROM memory_meta WHERE key='schema_version'").fetchone()
            version = int(row['value']) if row else 1
            if version not in {1, 2, SCHEMA_VERSION}:
                raise RuntimeError(f"unsupported memory database schema {version}; expected {SCHEMA_VERSION}")
            # Idempotent migration: existing IDs/content/timestamps are preserved.
            columns = {row['name'] for row in db.execute('PRAGMA table_info(memories)')}
            for column in ('fact_key', 'fact_value'):
                if column not in columns:
                    db.execute(f"ALTER TABLE memories ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            db.execute('CREATE INDEX IF NOT EXISTS idx_memories_fact_key ON memories(fact_key)')
            for column, default in (('project_id', ''), ('semantic_status', 'statement'), ('source_ref', '')):
                if column not in columns:
                    db.execute(f"ALTER TABLE memories ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
            db.executescript('''
                CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
                CREATE TABLE IF NOT EXISTS memory_history (
                    revision_id TEXT PRIMARY KEY, memory_id TEXT NOT NULL,
                    content TEXT NOT NULL, source TEXT NOT NULL, source_ref TEXT NOT NULL,
                    semantic_status TEXT NOT NULL, project_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, original_updated_at TEXT NOT NULL,
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS memory_suggestions (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL,
                    source TEXT NOT NULL, source_ref TEXT NOT NULL, target_id TEXT NOT NULL,
                    target_updated_at TEXT NOT NULL, project_id TEXT NOT NULL,
                    semantic_status TEXT NOT NULL, reason TEXT NOT NULL, uncertainty TEXT NOT NULL,
                    related_ids TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_suggestions_status ON memory_suggestions(status);
            ''')
            if version == 1:
                from hanni.memory.facts import extract_fact
                for old in db.execute('SELECT id, content FROM memories').fetchall():
                    try:
                        fact = extract_fact(old['content'], explicit=True, max_chars=self.max_item_chars)
                    except ValueError:
                        fact = None
                    if fact:
                        db.execute('UPDATE memories SET fact_key=?, fact_value=? WHERE id=?', (fact.key, fact.value, old['id']))
            if version < 3:
                from hanni.laya.intelligence import classify_semantic_status
                for old in db.execute('SELECT id,content FROM memories').fetchall():
                    db.execute('UPDATE memories SET semantic_status=? WHERE id=?',
                               (classify_semantic_status(old['content']), old['id']))
            db.execute("INSERT OR REPLACE INTO memory_meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=str(row["id"]),
            content=str(row["content"]),
            memory_type=str(row["memory_type"]),
            source=str(row["source"]),
            confidence=float(row["confidence"]),
            created_at=_parse_dt(str(row["created_at"])),
            updated_at=_parse_dt(str(row["updated_at"])),
            fact_key=str(row["fact_key"]),
            fact_value=str(row["fact_value"]),
            project_id=str(row['project_id']), semantic_status=str(row['semantic_status']), source_ref=str(row['source_ref']),
        )

    def fingerprint(self) -> str:
        """Detect cross-process corrections/deletions without caching memory text."""
        digest = hashlib.sha256()
        with self._connect() as db:
            for row in db.execute('SELECT * FROM memories ORDER BY id'):
                # Imported writers can change content or provenance while
                # preserving timestamps. Fingerprint actual record state.
                digest.update(json.dumps(dict(row), sort_keys=True, ensure_ascii=False,
                                         separators=(',', ':'), default=repr).encode('utf-8'))
                digest.update(b'\n')
        return digest.hexdigest()

    def remember(self, content: str, *, source: str = 'owner_explicit', confidence: float = 1.0,
                 memory_type: str | None = None, project_id: str = '', semantic_status: str | None = None,
                 source_ref: str = '') -> tuple[MemoryRecord, bool]:
        result = self._remember(content, source=source, confidence=confidence, memory_type=memory_type,
                                project_id=project_id, semantic_status=semantic_status, source_ref=source_ref)
        if not result[1]:
            self.cleanup()
        return result

    def _remember(
        self,
        content: str,
        *,
        source: str = "owner_explicit",
        confidence: float = 1.0,
        memory_type: str | None = None,
        project_id: str = '', semantic_status: str | None = None, source_ref: str = '',
    ) -> tuple[MemoryRecord, bool]:
        clean = validate_memory_text(content, max_chars=self.max_item_chars)
        from hanni.laya.intelligence import classify_semantic_status
        status = semantic_status or classify_semantic_status(clean)
        self._validate_metadata(project_id, status, source_ref)
        if status == 'verified_outcome' and not source.startswith('workflow_verified:'):
            raise ValueError('Verified outcome status requires a verified workflow source.')
        from hanni.memory.facts import extract_fact
        fact = extract_fact(clean, explicit=True, max_chars=self.max_item_chars)
        fact_key, fact_value = (fact.key, fact.value) if fact else ('', '')
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("memory confidence must be between 0 and 1")
        normalized = normalize_for_match(clean)
        now = utc_now().isoformat()
        kind = memory_type or classify_memory(clean)
        for value in (source, kind):
            if not isinstance(value, str):
                raise ValueError('invalid memory provenance metadata')
            if value:
                validate_memory_text(value, max_chars=self.max_item_chars)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute("SELECT * FROM memories WHERE normalized_content=?", (normalized,)).fetchone()
            if existing is not None and existing['project_id'] != project_id:
                raise MemoryConflictError('Identical text already belongs to another project; its scope cannot be changed implicitly.')
            conflicts = db.execute('SELECT * FROM memories WHERE fact_key=? AND project_id=? ORDER BY updated_at DESC', (fact_key, project_id)).fetchall() if fact_key else []
            if conflicts:
                # Extraction is lower authority than an explicit owner correction.
                if not source.startswith('owner_explicit') and any(row['fact_value'].casefold() != fact_value.casefold() for row in conflicts):
                    raise MemoryConflictError('A different value is already remembered; use an explicit remember command to replace it.')
                chosen = conflicts[0]
                if not source.startswith('owner_explicit') and chosen['source'].startswith('owner_explicit'):
                    return self._record(chosen), False
                self._save_history(db, chosen)
                self._purge_suggestions(db, chosen['id'])
                for duplicate in conflicts[1:]:
                    self._purge_suggestions(db, duplicate['id'])
                    db.execute('DELETE FROM memories WHERE id=?', (duplicate['id'],))
                db.execute('UPDATE memories SET content=?, normalized_content=?, memory_type=?, source=?, confidence=?, updated_at=?, fact_value=?, project_id=?, semantic_status=?, source_ref=? WHERE id=?',
                           (clean, normalized, kind, source, float(confidence), now, fact_value, project_id or chosen['project_id'], status, source_ref, chosen['id']))
                row = db.execute('SELECT * FROM memories WHERE id=?', (chosen['id'],)).fetchone()
                return self._record(row), False
            if existing is not None:
                db.execute(
                    "UPDATE memories SET source=?, confidence=?, updated_at=?, project_id=?, semantic_status=?, source_ref=? WHERE id=?",
                    (source, float(confidence), now, project_id or existing['project_id'], status, source_ref, existing["id"]),
                )
                row = db.execute("SELECT * FROM memories WHERE id=?", (existing["id"],)).fetchone()
                assert row is not None
                return self._record(row), False
            memory_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO memories(id, content, normalized_content, memory_type, source, confidence, created_at, updated_at, fact_key, fact_value, project_id, semantic_status, source_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (memory_id, clean, normalized, kind, source, float(confidence), now, now, fact_key, fact_value, project_id, status, source_ref),
            )
            row = db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            assert row is not None
            return self._record(row), True

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        return self._record(row) if row is not None else None

    @staticmethod
    def _filters(project_id=None, memory_type=None):
        clauses, values = [], []
        for name, value in (('project_id', project_id), ('memory_type', memory_type)):
            if value is not None:
                clauses.append(name + '=?')
                values.append(str(value))
        return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), values

    def list(self, *, limit: int = 50, offset: int = 0, project_id: str | None = None,
             memory_type: str | None = None, sort: str = 'updated') -> tuple[MemoryRecord, ...]:
        limit = max(1, min(int(limit), 500))
        order = {'updated': 'updated_at DESC, id', 'created': 'created_at DESC, id', 'type': 'memory_type, updated_at DESC, id'}.get(sort)
        if not order:
            raise ValueError('unsupported memory sort')
        where, values = self._filters(project_id, memory_type)
        with self._connect() as db:
            rows = db.execute('SELECT * FROM memories' + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?',
                              (*values, limit, max(0, int(offset)))).fetchall()
        return tuple(self._record(row) for row in rows)

    def count(self, *, project_id: str | None = None, memory_type: str | None = None) -> int:
        where, values = self._filters(project_id, memory_type)
        with self._connect() as db:
            row = db.execute('SELECT COUNT(*) AS n FROM memories' + where, values).fetchone()
        return int(row["n"] if row is not None else 0)

    def iter_records(self, *, project_id: str | None = None) -> Iterator[MemoryRecord]:
        """One fresh SQLite read snapshot, closed before context is returned."""
        where, values = self._filters(project_id, None)
        with self._connect() as db:
            for row in db.execute('SELECT * FROM memories' + where + ' ORDER BY updated_at DESC, id', values):
                yield self._record(row)

    @staticmethod
    def _score(query: str, record: MemoryRecord) -> float:
        candidate = normalize_for_match(record.content)
        query_tokens, candidate_tokens = _tokens(query), _tokens(candidate)
        score = 0.0
        if query == candidate:
            score = 100.0
        elif query in candidate:
            score = 80.0 + min(10.0, len(query) / max(1, len(candidate)) * 10.0)
        elif candidate in query:
            score = 70.0
        if query_tokens:
            overlap = len(query_tokens & candidate_tokens)
            score = max(score, 55.0 * overlap / len(query_tokens) + 15.0 * overlap / max(1, len(candidate_tokens)))
        return round(score, 3)

    def search(self, query: str, *, limit: int = 8, offset: int = 0, project_id: str | None = None,
               memory_type: str | None = None, exclude_ids=(), eligibility=None) -> tuple[MemorySearchResult, ...]:
        clean = normalize_for_match(query)
        if not clean or not _tokens(clean):
            return ()
        limit = max(1, min(int(limit), 100))
        offset = max(0, min(int(offset), 10000))
        where, values = self._filters(project_id, memory_type)
        excluded = frozenset(exclude_ids)
        with self._connect() as db:
            def candidates():
                for row in db.execute('SELECT * FROM memories' + where, values):
                    record = self._record(row)
                    if record.id in excluded or (eligibility is not None and not eligibility(record)):
                        continue
                    score = self._score(clean, record)
                    if score > 0:
                        yield MemorySearchResult(record, score)
            return tuple(heapq.nlargest(limit + offset, candidates(), key=lambda item: (item.score, item.record.updated_at.timestamp(), item.record.id))[offset:])

    def find_all(self, query: str) -> tuple[MemoryRecord, ...]:
        """All topic matches, never truncated by a UI/search limit.

        Require every meaningful query token (or the exact substring) so a
        generic shared word such as 'project' cannot erase unrelated projects.
        """
        clean = normalize_for_match(query)
        terms = _tokens(clean)
        if not terms:
            return ()
        with self._connect() as db:
            return tuple(self._record(row) for row in db.execute('SELECT * FROM memories')
                         if clean in row['normalized_content'] or terms <= _tokens(row['content']))

    def by_key(self, fact_key: str, *, project_id: str | None = None) -> tuple[MemoryRecord, ...]:
        with self._connect() as db:
            query = 'SELECT * FROM memories WHERE fact_key=?'
            arguments = (fact_key,)
            if project_id is not None:
                query += ' AND project_id=?'
                arguments += (project_id,)
            rows = db.execute(query+' ORDER BY updated_at DESC', arguments).fetchall()
        return tuple(self._record(row) for row in rows)

    def delete(self, memory_id: str, *, expected_updated_at: str | None = None) -> bool:
        with self._connect() as db:
            if expected_updated_at is not None:
                # Explicit desktop deletion must not erase a concurrently corrected
                # record. Compare and delete in one existing SQLite transaction.
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT updated_at FROM memories WHERE id=?', (memory_id,)).fetchone()
                if current is None or not _revision_matches(current['updated_at'], expected_updated_at):
                    raise MemoryConflictError('The memory changed; inspect it again before forgetting it.')
            self._purge_suggestions(db, memory_id)
            cursor = db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            deleted = cursor.rowcount > 0
            remaining = db.execute("SELECT 1 FROM memories WHERE id=?", (memory_id,)).fetchone()
        if remaining is not None:
            raise RuntimeError("memory deletion verification failed")
        self.cleanup()
        return deleted

    def delete_many(self, memory_ids: Iterable[str]) -> int:
        ids = tuple(dict.fromkeys(str(value) for value in memory_ids if str(value)))
        if not ids:
            return 0
        deleted = 0
        with self._connect() as db:
            for memory_id in ids:
                self._purge_suggestions(db, memory_id)
                cursor = db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
                deleted += max(0, cursor.rowcount)
            remaining = []
            for offset in range(0, len(ids), 400):
                chunk = ids[offset:offset + 400]
                placeholders = ','.join('?' for _ in chunk)
                remaining.extend(db.execute(f'SELECT id FROM memories WHERE id IN ({placeholders})', chunk).fetchall())
        if remaining:
            raise RuntimeError("memory deletion verification failed")
        self.cleanup()
        return deleted

    def forget(self, query: str, *, delete_all: bool = False, limit: int = 20) -> tuple[MemoryRecord, ...]:
        if delete_all:
            clean, terms = normalize_for_match(query), _tokens(query)
            if not terms:
                return ()
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                def matches(row):
                    return clean in row['normalized_content'] or terms <= _tokens(row['content'])
                records = tuple(self._record(row) for row in db.execute('SELECT * FROM memories') if matches(row))
                for record in records:
                    self._purge_suggestions(db, record.id)
                db.executemany('DELETE FROM memories WHERE id=?', ((record.id,) for record in records))
                if any(matches(row) for row in db.execute('SELECT * FROM memories')):
                    raise RuntimeError('topic deletion verification failed')
            self.cleanup()
            return records
        matches = self.search(query, limit=max(2, limit))
        if not matches:
            return ()
        # Exact/substring matches are safe enough for a unique explicit forget.
        best = matches[0]
        if len(matches) > 1 and best.score < 80.0:
            return ()
        if len(matches) > 1 and abs(best.score - matches[1].score) < 5.0:
            return ()
        self.delete(best.record.id)
        return (best.record,)

    @staticmethod
    def _validate_metadata(project_id, semantic_status, source_ref):
        if semantic_status not in SEMANTIC_STATUSES:
            raise ValueError('unknown memory semantic status')
        for value, maximum in ((project_id, 128), (source_ref, 500)):
            if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 for c in value):
                raise ValueError('invalid memory provenance metadata')
            if value:
                validate_memory_text(value, max_chars=maximum)

    @staticmethod
    def _save_history(db, row):
        db.execute('INSERT INTO memory_history VALUES(?,?,?,?,?,?,?,?,?)',
                   (uuid.uuid4().hex, row['id'], row['content'], row['source'], row['source_ref'],
                    row['semantic_status'], row['project_id'], utc_now().isoformat(), row['updated_at']))

    @staticmethod
    def _purge_suggestions(db, memory_id):
        # Inspect stable IDs, never text matching, so correction/deletion cannot
        # leave an old candidate containing the deleted source text in the queue.
        original = db.execute('SELECT normalized_content FROM memories WHERE id=?', (memory_id,)).fetchone()
        ids = [row['id'] for row in db.execute('SELECT id,target_id,related_ids,content FROM memory_suggestions')
               if row['target_id'] == memory_id or memory_id in json.loads(row['related_ids'])
               or (original and normalize_for_match(row['content']) == original['normalized_content'])]
        db.executemany('DELETE FROM memory_suggestions WHERE id=?', ((value,) for value in ids))

    def history(self, memory_id: str, *, limit: int = 50, offset: int = 0) -> tuple[dict[str, object], ...]:
        with self._connect() as db:
            return tuple(dict(row) for row in db.execute('SELECT * FROM memory_history WHERE memory_id=? ORDER BY recorded_at DESC LIMIT ? OFFSET ?',
                         (memory_id, max(1, min(int(limit), 500)), max(0, int(offset)))))

    def count_history(self, memory_id: str) -> int:
        with self._connect() as db:
            return int(db.execute('SELECT count(*) FROM memory_history WHERE memory_id=?', (memory_id,)).fetchone()[0])

    def _correct(self, db, memory_id, content, expected_updated_at, source, project_id, semantic_status, source_ref):
        clean = validate_memory_text(content, max_chars=self.max_item_chars)
        row = db.execute('SELECT * FROM memories WHERE id=?', (memory_id,)).fetchone()
        if row is None or not _revision_matches(row['updated_at'], expected_updated_at):
            raise MemoryConflictError('The memory changed; inspect it again before correcting it.')
        from hanni.laya.intelligence import classify_semantic_status
        status = semantic_status or classify_semantic_status(clean)
        if status == 'verified_outcome' and not source.startswith('workflow_verified:'):
            raise ValueError('Verified outcome status requires a verified workflow source.')
        project = row['project_id'] if project_id is None else project_id
        reference = row['source_ref'] if source_ref is None else source_ref
        self._validate_metadata(project, status, reference)
        if not isinstance(source, str):
            raise ValueError('invalid memory provenance metadata')
        if source:
            validate_memory_text(source, max_chars=self.max_item_chars)
        from hanni.memory.facts import extract_fact
        fact = extract_fact(clean, explicit=True, max_chars=self.max_item_chars)
        fact_key, fact_value = (fact.key, fact.value) if fact else ('', '')
        if db.execute('SELECT 1 FROM memories WHERE id<>? AND (normalized_content=? OR (fact_key<>? AND fact_key=? AND project_id=?))',
                      (memory_id, normalize_for_match(clean), '', fact_key, project)).fetchone():
            raise MemoryConflictError('The correction conflicts with another record; review both before merging.')
        self._save_history(db, row)
        self._purge_suggestions(db, memory_id)
        db.execute('UPDATE memories SET content=?, normalized_content=?, memory_type=?, source=?, confidence=1.0, updated_at=?, fact_key=?, fact_value=?, project_id=?, semantic_status=?, source_ref=? WHERE id=?',
                   (clean, normalize_for_match(clean), classify_memory(clean), source, utc_now().isoformat(), fact_key, fact_value, project, status, reference, memory_id))
        return self._record(db.execute('SELECT * FROM memories WHERE id=?', (memory_id,)).fetchone())

    def correct(self, memory_id: str, content: str, *, expected_updated_at: str,
                source: str = 'owner_explicit:correction', project_id: str | None = None,
                semantic_status: str | None = None, source_ref: str | None = None) -> MemoryRecord:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = self._correct(db, memory_id, content, expected_updated_at, source, project_id, semantic_status, source_ref)
        self.cleanup()
        return record

    @staticmethod
    def _suggestion(row):
        return MemorySuggestion(**{key: (tuple(json.loads(row[key])) if key == 'related_ids' else
                                         _parse_dt(row[key]) if key in {'created_at', 'updated_at'} else row[key])
                                  for key in MemorySuggestion.__dataclass_fields__})

    def propose(self, kind: str, content: str, *, source: str, source_ref: str = '', target_id: str = '',
                expected_updated_at: str = '', project_id: str = '', semantic_status: str = 'statement',
                reason: str = '', uncertainty: str = '', related_ids: Iterable[str] = ()) -> MemorySuggestion:
        if kind not in {'add', 'correct', 'duplicate', 'conflict', 'related', 'stale', 'archive'}:
            raise ValueError('unsupported memory proposal kind')
        clean = validate_memory_text(content, max_chars=self.max_item_chars)
        self._validate_metadata(project_id, semantic_status, source_ref)
        for value in (source, reason, uncertainty):
            if value:
                validate_memory_text(value, max_chars=1200)
        related = tuple(dict.fromkeys(str(value) for value in related_ids))
        if len(related) > 50:
            raise ValueError('too many related records')
        if kind != 'add' and not target_id and not related:
            raise ValueError('A derived record proposal requires stable source record identifiers.')
        now, suggestion_id = utc_now().isoformat(), uuid.uuid4().hex
        with self._connect() as db:
            for value in related:
                if db.execute('SELECT 1 FROM memories WHERE id=?', (value,)).fetchone() is None:
                    raise MemoryConflictError('A related memory is no longer available.')
            if target_id:
                target = db.execute('SELECT updated_at FROM memories WHERE id=?', (target_id,)).fetchone()
                if not target or not expected_updated_at or not _revision_matches(target['updated_at'], expected_updated_at):
                    raise MemoryConflictError('The proposed target changed; generate a new suggestion.')
            db.execute('INSERT INTO memory_suggestions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (suggestion_id, kind, clean, source, source_ref, target_id, expected_updated_at, project_id,
                        semantic_status, reason, uncertainty, json.dumps(related), 'pending', now, now))
            return self._suggestion(db.execute('SELECT * FROM memory_suggestions WHERE id=?', (suggestion_id,)).fetchone())

    def get_suggestion(self, suggestion_id: str) -> MemorySuggestion | None:
        with self._connect() as db:
            row = db.execute('SELECT * FROM memory_suggestions WHERE id=?', (suggestion_id,)).fetchone()
            return self._suggestion(row) if row else None

    def suggestions(self, *, status: str = 'pending', limit: int = 50, offset: int = 0) -> tuple[MemorySuggestion, ...]:
        with self._connect() as db:
            return tuple(self._suggestion(row) for row in db.execute('SELECT * FROM memory_suggestions WHERE status=? ORDER BY updated_at DESC,id LIMIT ? OFFSET ?',
                         (status, max(1, min(int(limit), 500)), max(0, int(offset)))))

    def count_suggestions(self, *, status: str = 'pending') -> int:
        with self._connect() as db:
            return int(db.execute('SELECT count(*) FROM memory_suggestions WHERE status=?', (status,)).fetchone()[0])

    def review_suggestion(self, suggestion_id: str, action: str, *, expected_updated_at: str,
                          edited_content: str | None = None) -> MemorySuggestion:
        """Owner controller calls this AFTER permission/Safe Mode checks.

        No model/client has a reference to this method. Suggestions are never
        evidence of verification, nor may they directly archive/delete records.
        """
        if action not in {'approve', 'reject', 'dismiss'}:
            raise ValueError('unknown suggestion review action')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM memory_suggestions WHERE id=?', (suggestion_id,)).fetchone()
            if not row or row['status'] != 'pending' or not _revision_matches(row['updated_at'], expected_updated_at):
                raise MemoryConflictError('The suggestion changed; inspect it again before reviewing it.')
            if action == 'approve':
                content = validate_memory_text(edited_content if edited_content is not None else row['content'], max_chars=self.max_item_chars)
                if row['semantic_status'] == 'verified_outcome':
                    raise ValueError('A memory suggestion cannot confer verified outcome status.')
                if row['kind'] == 'correct':
                    self._correct(db, row['target_id'], content, row['target_updated_at'], 'owner_explicit:review', row['project_id'], row['semantic_status'], row['source_ref'])
                    # Correction invalidates all target proposals, including this
                    # one. Return a text-free receipt; stale source text is gone.
                    return MemorySuggestion(suggestion_id, row['kind'], '', row['source'], '', '', '', '',
                                            row['semantic_status'], '', '', (), 'approved', _parse_dt(row['created_at']), utc_now())
                if row['kind'] != 'add':
                    raise ValueError('Consolidation requires explicit record correction/deletion; approval is only an acknowledgement.')
                # Keep this insert in the review transaction; do not re-enter a
                # second SQLite writer or overwrite keyed owner facts implicitly.
                from hanni.memory.facts import extract_fact
                fact = extract_fact(content, explicit=True, max_chars=self.max_item_chars)
                key, value = (fact.key, fact.value) if fact else ('', '')
                if db.execute('SELECT 1 FROM memories WHERE normalized_content=? OR (fact_key<>? AND fact_key=? AND project_id=?)',
                              (normalize_for_match(content), '', key, row['project_id'])).fetchone():
                    raise MemoryConflictError('A matching memory exists; inspect it before applying this suggestion.')
                now = utc_now().isoformat()
                new_memory_id = uuid.uuid4().hex
                db.execute('INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (new_memory_id, content, normalize_for_match(content), classify_memory(content), 'owner_explicit:review', 1.0,
                            now, now, key, value, row['project_id'], row['semantic_status'], row['source_ref']))
                db.execute('UPDATE memory_suggestions SET target_id=?,target_updated_at=? WHERE id=?',
                           (new_memory_id, now, suggestion_id))
            status = {'approve': 'approved', 'reject': 'rejected', 'dismiss': 'dismissed'}[action]
            db.execute('UPDATE memory_suggestions SET status=?,updated_at=? WHERE id=?', (status, utc_now().isoformat(), suggestion_id))
            return self._suggestion(db.execute('SELECT * FROM memory_suggestions WHERE id=?', (suggestion_id,)).fetchone())


    def cleanup(self) -> dict[str, object]:
        """Checkpoint deletion residue and inspect integrity; never remove live facts."""
        # Checkpoint must be outside an active transaction and all handles close.
        with self._connect() as db:
            integrity = str(db.execute('PRAGMA quick_check').fetchone()[0])
            checkpoint = tuple(db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
        if integrity != 'ok' or checkpoint[0] != 0:
            raise RuntimeError('Memory cleanup incomplete: database busy or integrity check failed. Retry after closing other memory readers.')
        return {'integrity': integrity, 'wal_checkpointed': True, 'schema_version': SCHEMA_VERSION, 'records': self.count()}
