"""Local SQLite durable memory with conservative keyed facts and verified cleanup."""

from __future__ import annotations

import re
import heapq
import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from hanni.memory.privacy import normalize_memory_text, validate_memory_text

SCHEMA_VERSION = 2

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
        }


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    record: MemoryRecord
    score: float


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
            if version not in {1, SCHEMA_VERSION}:
                raise RuntimeError(f"unsupported memory database schema {version}; expected {SCHEMA_VERSION}")
            # Idempotent migration: existing IDs/content/timestamps are preserved.
            columns = {row['name'] for row in db.execute('PRAGMA table_info(memories)')}
            for column in ('fact_key', 'fact_value'):
                if column not in columns:
                    db.execute(f"ALTER TABLE memories ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            db.execute('CREATE INDEX IF NOT EXISTS idx_memories_fact_key ON memories(fact_key)')
            if version == 1:
                from hanni.memory.facts import extract_fact
                for old in db.execute('SELECT id, content FROM memories').fetchall():
                    try:
                        fact = extract_fact(old['content'], explicit=True, max_chars=self.max_item_chars)
                    except ValueError:
                        fact = None
                    if fact:
                        db.execute('UPDATE memories SET fact_key=?, fact_value=? WHERE id=?', (fact.key, fact.value, old['id']))
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
        )

    def fingerprint(self) -> str:
        """Detect cross-process corrections/deletions without caching memory text."""
        digest = hashlib.sha256()
        with self._connect() as db:
            for row in db.execute('SELECT id, updated_at FROM memories ORDER BY id'):
                digest.update((row['id'] + row['updated_at']).encode('utf-8'))
        return digest.hexdigest()

    def remember(self, content: str, *, source: str = 'owner_explicit', confidence: float = 1.0,
                 memory_type: str | None = None) -> tuple[MemoryRecord, bool]:
        result = self._remember(content, source=source, confidence=confidence, memory_type=memory_type)
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
    ) -> tuple[MemoryRecord, bool]:
        clean = validate_memory_text(content, max_chars=self.max_item_chars)
        from hanni.memory.facts import extract_fact
        fact = extract_fact(clean, explicit=True, max_chars=self.max_item_chars)
        fact_key, fact_value = (fact.key, fact.value) if fact else ('', '')
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("memory confidence must be between 0 and 1")
        normalized = normalize_for_match(clean)
        now = utc_now().isoformat()
        kind = memory_type or classify_memory(clean)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            conflicts = db.execute('SELECT * FROM memories WHERE fact_key=? ORDER BY updated_at DESC', (fact_key,)).fetchall() if fact_key else []
            if conflicts:
                # Extraction is lower authority than an explicit owner correction.
                if not source.startswith('owner_explicit') and any(row['fact_value'].casefold() != fact_value.casefold() for row in conflicts):
                    raise MemoryConflictError('A different value is already remembered; use an explicit remember command to replace it.')
                chosen = conflicts[0]
                if not source.startswith('owner_explicit') and chosen['source'].startswith('owner_explicit'):
                    return self._record(chosen), False
                for duplicate in conflicts[1:]:
                    db.execute('DELETE FROM memories WHERE id=?', (duplicate['id'],))
                db.execute('UPDATE memories SET content=?, normalized_content=?, memory_type=?, source=?, confidence=?, updated_at=?, fact_value=? WHERE id=?',
                           (clean, normalized, kind, source, float(confidence), now, fact_value, chosen['id']))
                row = db.execute('SELECT * FROM memories WHERE id=?', (chosen['id'],)).fetchone()
                return self._record(row), False
            existing = db.execute("SELECT * FROM memories WHERE normalized_content=?", (normalized,)).fetchone()
            if existing is not None:
                db.execute(
                    "UPDATE memories SET source=?, confidence=?, updated_at=? WHERE id=?",
                    (source, float(confidence), now, existing["id"]),
                )
                row = db.execute("SELECT * FROM memories WHERE id=?", (existing["id"],)).fetchone()
                assert row is not None
                return self._record(row), False
            memory_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO memories(id, content, normalized_content, memory_type, source, confidence, created_at, updated_at, fact_key, fact_value) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (memory_id, clean, normalized, kind, source, float(confidence), now, now, fact_key, fact_value),
            )
            row = db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            assert row is not None
            return self._record(row), True

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        return self._record(row) if row is not None else None

    def list(self, *, limit: int = 50) -> tuple[MemoryRecord, ...]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            rows = db.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return tuple(self._record(row) for row in rows)

    def count(self) -> int:
        with self._connect() as db:
            row = db.execute("SELECT COUNT(*) AS n FROM memories").fetchone()
        return int(row["n"] if row is not None else 0)

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

    def search(self, query: str, *, limit: int = 8) -> tuple[MemorySearchResult, ...]:
        clean = normalize_for_match(query)
        if not clean or not _tokens(clean):
            return ()
        limit = max(1, min(int(limit), 100))
        with self._connect() as db:
            def candidates():
                for row in db.execute('SELECT * FROM memories'):
                    record = self._record(row)
                    score = self._score(clean, record)
                    if score > 0:
                        yield MemorySearchResult(record, score)
            return tuple(heapq.nlargest(limit, candidates(), key=lambda item: (item.score, item.record.updated_at.timestamp(), item.record.id)))

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

    def by_key(self, fact_key: str) -> tuple[MemoryRecord, ...]:
        with self._connect() as db:
            rows = db.execute('SELECT * FROM memories WHERE fact_key=? ORDER BY updated_at DESC', (fact_key,)).fetchall()
        return tuple(self._record(row) for row in rows)

    def delete(self, memory_id: str, *, expected_updated_at: str | None = None) -> bool:
        with self._connect() as db:
            if expected_updated_at is not None:
                # Explicit desktop deletion must not erase a concurrently corrected
                # record. Compare and delete in one existing SQLite transaction.
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT updated_at FROM memories WHERE id=?', (memory_id,)).fetchone()
                if current is None or current['updated_at'] != expected_updated_at:
                    raise MemoryConflictError('The memory changed; inspect it again before forgetting it.')
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


    def cleanup(self) -> dict[str, object]:
        """Checkpoint deletion residue and inspect integrity; never remove live facts."""
        # Checkpoint must be outside an active transaction and all handles close.
        with self._connect() as db:
            integrity = str(db.execute('PRAGMA quick_check').fetchone()[0])
            checkpoint = tuple(db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
        if integrity != 'ok' or checkpoint[0] != 0:
            raise RuntimeError('Memory cleanup incomplete: database busy or integrity check failed. Retry after closing other memory readers.')
        return {'integrity': integrity, 'wal_checkpointed': True, 'schema_version': SCHEMA_VERSION, 'records': self.count()}
