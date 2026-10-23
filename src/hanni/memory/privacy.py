"""Durable-memory privacy gate for Milestone 9.

M9 stores concise explicit memories and conservative stable owner facts. Raw audio,
rolling transcript windows, and screenshots are never passed to the store. The gate
rejects credentials/secrets rather than attempting to redact and persist them.
"""

from __future__ import annotations

import math
import re

from hanni.logs.redaction import redact_text


class SensitiveMemoryError(ValueError):
    """Raised when text must not be written to durable memory."""


_SENSITIVE_TERMS = re.compile(
    r"(?ix)\b(?:"
    r"password|passwd|passcode|pin\s*(?:code|number)?|"
    r"2fa|two[-\s]?factor|otp|one[-\s]?time\s+(?:password|passcode|code)|"
    r"verification\s+code|auth(?:entication)?\s+code|"
    r"api[-\s_]?key|access[-\s_]?token|refresh[-\s_]?token|bearer\s+token|"
    r"private[-\s_]?key|secret[-\s_]?key|client[-\s_]?secret|"
    r"seed\s+phrase|recovery\s+phrase|mnemonic|"
    r"credit\s+card|card\s+number|cvv|cvc|bank\s+account|routing\s+number|"
    r"social\s+security|ssn"
    r")\b"
)

_AUTO_APPROVAL_INSTRUCTION = re.compile(
    r'(?i)(?:^|[.!?;]\s*)(?:[-*]\s*)?(?:(?:please|always|also)\s+)?'
    r'(?:auto[-\s]?approve|automatically\s+approve)\b'
)


def normalize_memory_text(text: str) -> str:
    """Normalize owner-explicit text without changing its meaning."""
    return " ".join(str(text or "").strip().split())


def validate_memory_text(text: str, *, max_chars: int) -> str:
    """Return normalized safe text or raise ``SensitiveMemoryError``/``ValueError``."""
    clean = normalize_memory_text(text)
    if not clean:
        raise ValueError("memory text must not be empty")
    if len(clean) > max_chars:
        raise ValueError(f"memory text is too long ({len(clean)} characters; maximum is {max_chars})")
    # If the process-wide log redactor recognizes a registered/token-shaped secret,
    # never persist either the original or a redacted placeholder.
    if redact_text(clean) != clean or _SENSITIVE_TERMS.search(clean):
        raise SensitiveMemoryError(
            "durable memory refuses passwords, authentication codes, financial credentials, API keys, tokens, and other secrets"
        )
    if re.search(r"(?i)\b(?:ignore|override|bypass|disable)\b.{0,50}\b(?:instructions?|safety|permissions?|confirmations?|safe mode|rules?)\b|\b(?:confirmed|auto.?approve)\s*[=:]|\b(?:never|without)\s+(?:ask|asking|confirmation)|\b(?:system|developer)\s*(?:message|prompt)\b", clean):
        raise SensitiveMemoryError("durable memory refuses instructions that attempt to change runtime authority")
    if _AUTO_APPROVAL_INSTRUCTION.search(clean):
        raise SensitiveMemoryError("durable memory refuses instructions that attempt to change runtime authority")
    return clean


def validate_memory_record(record, *, max_chars=1200):
    """Recheck imported record data and provenance under the current privacy policy.

    Validation neither repairs the record nor grants authority from its metadata.
    A secret registered after persistence must be withheld on subsequent reads.
    """
    if not isinstance(record.content, str):
        raise ValueError('Invalid stored memory content')
    validate_memory_text(record.content, max_chars=max_chars)
    for field in ('id', 'source', 'source_ref', 'fact_key', 'fact_value', 'project_id', 'memory_type', 'semantic_status'):
        value = getattr(record, field, '')
        if not isinstance(value, str):
            raise ValueError('Invalid stored memory metadata')
        if value:
            validate_memory_text(value, max_chars=max_chars)
    from hanni.memory.store import SEMANTIC_STATUSES
    if getattr(record, 'semantic_status', 'statement') not in SEMANTIC_STATUSES:
        raise ValueError('Invalid stored memory statement type')
    confidence = getattr(record, 'confidence', None)
    if (type(confidence) not in (int, float) or not 0 <= confidence <= 1
            or not math.isfinite(confidence)):
        raise ValueError('Invalid stored memory confidence')
    return record
