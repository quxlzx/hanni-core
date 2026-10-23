"""Voice-first assistant response cleanup.

The Supervisor is prompted to speak naturally, but this final lightweight layer
prevents common chat-format artifacts from leaking into future TTS output.
"""

from __future__ import annotations

import re

# Broad ranges cover common emoji/pictographs without touching ordinary ASCII
# punctuation or accented language text.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)


def sanitize_response_chunk(text: str) -> str:
    """Remove speech-hostile formatting from one streaming model chunk."""
    if not text:
        return ""
    value = text
    # Character-level cleanup is intentionally streaming-safe even when a pair
    # such as ** is split across model chunks.
    value = value.replace("*", "").replace("`", "").replace("#", "")
    value = value.replace("__", "")
    value = _EMOJI_RE.sub("", value)
    # Spoken output should not contain paragraph/bullet formatting pauses.
    value = re.sub(r"[\r\n]+", " ", value)
    return value


def sanitize_assistant_text(text: str) -> str:
    """Normalize a complete assistant response for history/TTS."""
    value = sanitize_response_chunk(text)
    # Markdown links -> visible label.
    value = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", value)
    # Remove common bullet / numbered-list prefixes left after chunk cleanup.
    value = re.sub(r"(?:(?<=^)|(?<=\s))(?:[-+>]\s+|\d+[.)]\s+)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def runaway_reason(text: str) -> str | None:
    """Detect only extreme model loops; normal emphasis/repetition is allowed."""
    if len(text) < 80:
        return None
    if re.search(r"\d{40,}", text):
        return "long_digit_run"
    if re.search(r"\b([A-Za-z]{4,})\b(?:[\s,._-]+\1\b){4,}", text, re.I):
        return "repeated_word"
    if re.search(r"(.{48,240}?)\1{2,}", text, re.S):
        return "repeated_passage"
    return None


def guard_assistant_text(text: str) -> str:
    """Replace a pathological completion without inventing an answer."""
    if runaway_reason(text):
        return "I couldn't finish a reliable answer from those results."
    return sanitize_assistant_text(text)
