"""Local, proposal-only memory intelligence; scores are uncalibrated heuristics.

This module has no database writer, model loader, network client or tool access.
An owner statement is evidence that the owner said it, not a verified tool outcome.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from hanni.memory.facts import extract_fact
from hanni.memory.privacy import validate_memory_text, validate_memory_record


def classify_semantic_status(text: str) -> str:
    value = text.strip()
    if re.match(r'(?i)^when\s+I\b.+,\s*I\s+(?:always|usually)\b', value) and '?' not in value:
        return 'statement'
    if '?' in value or re.match(r'(?i)^(?:can|could|would|should|what|why|how|when|where|do|does|is|are)\b', value):
        return 'question'
    if re.search(r'(?i)\b(?:might|maybe|perhaps|hypothetical(?:ly)?|suppose|for example|if)\b', value):
        return 'hypothetical'
    if re.search(r'(?i)\b(?:i think|i guess|probably|apparently|seems|assume)\b', value):
        return 'inference'
    if re.search(r'(?i)\b(?:used to|previously|formerly|no longer|in the past)\b', value):
        return 'historical'
    if re.search(r'(?i)\b(?:for now|right now|temporarily|today|tonight|this week)\b', value):
        return 'temporary'
    if re.search(r'(?i)\b(?:decided|decision|chose|chosen|switched)\b', value):
        return 'decision'
    if re.search(r'(?i)\b(?:plan(?:ning)?|intend|will|going to|want to|need to|next benchmark)\b', value):
        return 'plan'
    if re.search(r'(?i)\b(?:failed|crashed|broke|unsuccessful|cancelled|canceled|aborted)\b', value) or re.search(
            r"(?i)\b(?:not(?!\s+(?:only|just)\b)|never|without|(?:did|does|has|have|had|is|was|were|can|could)n['’]t)\b"
            r'.{0,40}\b(?:complet(?:e|ed|ing|ion)|finish(?:ed|ing)?|run|ran|pass(?:ed|ing)?|publish(?:ed|ing)?|creat(?:e|ed|ing)|sav(?:e|ed|ing)|upload(?:ed|ing)?|install(?:ed|ing)?)\b', value):
        return 'failed_claim'
    if re.search(r'(?i)\b(?:completed|finished|ran|passed|published|created|saved|uploaded|installed)\b', value):
        return 'completed_claim'
    return 'statement'


@dataclass(frozen=True, slots=True)
class CandidateMemory:
    content: str
    memory_type: str
    semantic_status: str
    fact_key: str = ''
    fact_value: str = ''
    importance: float = 0.0
    importance_calibrated: bool = False
    source_ref: str = ''
    reason: str = ''
    uncertainty: str = 'Owner statement; not independently verified. Approval required.'
    project_id: str = ''

    def to_dict(self):
        from dataclasses import asdict
        return asdict(self)


def analyze_statement(text: str, *, source_ref: str = '', max_chars: int = 1200) -> CandidateMemory | None:
    """Identify review candidates without converting plans to completed actions."""
    clean = validate_memory_text(text, max_chars=max_chars)
    status = classify_semantic_status(clean)
    if status in {'question', 'hypothetical', 'inference', 'temporary'} or clean.startswith(('"', "'", '`')):
        return None
    if re.search(r'(?i)\b(?:do not save|don.t save|off the record|private|today|tonight|for now)\b', clean):
        return None
    normalized = re.sub(r'(?i)^(?:actually|correction)[,:]?\s+', '', clean)
    fact = extract_fact(normalized, explicit=False, max_chars=max_chars)
    if fact:
        score = 0.85 if fact.memory_type in {'preference', 'project', 'workflow'} else 0.7
        return CandidateMemory(clean, fact.memory_type, status, fact.key, fact.value, score,
                               source_ref=source_ref, reason='Explicit reusable owner statement matching a conservative local rule.')
    if status in {'plan', 'decision', 'completed_claim', 'failed_claim', 'historical'} and re.search(r'(?i)\b(?:project|model|benchmark|workflow|goal|test)\b', clean) and len(clean) <= 350:
        kind = 'decision' if status == 'decision' else 'goal' if status == 'plan' else 'fact'
        return CandidateMemory(clean, kind, status, importance=0.65,
                               source_ref=source_ref, reason='Explicit project statement; preserve intent/history/outcome claim without conferring verification.')
    return None


def analyze_candidate(candidate: CandidateMemory, records: Iterable) -> tuple[RelationProposal, ...]:
    """Compare an unpersisted proposal with identified authorized source records."""
    output = []
    for record in tuple(records)[:500]:
        try:
            validate_memory_record(record)
        except ValueError:
            continue
        if candidate.project_id != getattr(record, 'project_id', ''):
            continue
        if candidate.content.casefold().strip(' .') == record.content.casefold().strip(' .'):
            output.append(RelationProposal('duplicate', (record.id,), 'The candidate repeats an existing statement.'))
        elif candidate.fact_key and record.fact_key == candidate.fact_key and record.fact_value.casefold() != candidate.fact_value.casefold():
            output.append(RelationProposal('conflict', (record.id,), 'The proposed value differs for the same explicit fact key. Current truth requires owner review.'))
    return tuple(output)


@dataclass(frozen=True, slots=True)
class RelationProposal:
    kind: str
    memory_ids: tuple[str, ...]
    reason: str
    requires_review: bool = True
    uncertainty: str = 'Relationship suggestion; no record has been changed.'

    def to_dict(self):
        from dataclasses import asdict
        return asdict(self)


def analyze_relationships(records: Iterable, *, now: datetime | None = None, stale_days: int = 180,
                          limit: int = 100) -> tuple[RelationProposal, ...]:
    """Suggest keyed conflicts, exact duplicates, explicit project links and age flags.

    Shared words alone never establish relationships. Age flags do not establish
    that a fact is false, and recency never chooses a winner in a contradiction.
    """
    now = now or datetime.now(timezone.utc)
    rows = tuple(records)[:500]
    output: list[RelationProposal] = []
    for index, left in enumerate(rows):
        try:
            validate_memory_record(left, max_chars=1200)
        except ValueError:
            continue
        if (now - left.updated_at).days >= stale_days:
            output.append(RelationProposal('stale', (left.id,), 'Record age exceeds the review interval; truth is unknown.'))
        for right in rows[index + 1:]:
            try:
                validate_memory_record(right, max_chars=1200)
            except ValueError:
                continue
            same_scope = left.project_id == right.project_id
            if same_scope and left.content.casefold().strip(' .') == right.content.casefold().strip(' .'):
                output.append(RelationProposal('duplicate', (left.id, right.id), 'The normalized statements are identical.'))
            elif same_scope and left.fact_key and left.fact_key == right.fact_key and left.fact_value.casefold() != right.fact_value.casefold():
                output.append(RelationProposal('conflict', (left.id, right.id), 'The same explicit fact key has different values; owner review must resolve it.'))
            elif left.project_id and left.project_id == right.project_id:
                output.append(RelationProposal('related', (left.id, right.id), 'Both records are explicitly associated with the same persisted project.'))
            if len(output) >= limit:
                return tuple(output[:limit])
    return tuple(output[:limit])
