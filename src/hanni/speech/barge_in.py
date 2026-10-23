"""Milestone 5 barge-in classification and simple acoustic-echo suppression.

This layer is intentionally deterministic.  It never sends microphone speech to
an LLM merely to decide whether TTS should stop.  During playback, short filler
sounds are ignored, transcripts that closely match H.A.N.N.I.'s own current
spoken response are treated as speaker echo, and genuine owner speech cancels
playback immediately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

DEFAULT_INTERRUPT_PHRASES = (
    "stop", "wait", "hold on", "quiet", "cancel", "no", "no wait",
    "hanni stop", "honey stop", "ani stop",
)

@dataclass(frozen=True, slots=True)
class BargeInDecision:
    interrupt: bool
    route_after_interrupt: bool = False
    command_text: str = ""
    echo_ignored: bool = False
    filler_ignored: bool = False
    reason: str = "none"

class BargeInClassifier:
    def __init__(self, *, interrupt_phrases: Sequence[str] = DEFAULT_INTERRUPT_PHRASES,
                 filler_words: Sequence[str] = (), echo_min_words: int = 3,
                 echo_overlap_ratio: float = 0.72) -> None:
        self.interrupt_phrases = tuple(dict.fromkeys(self._normalize(p) for p in interrupt_phrases if self._normalize(p)))
        self.filler_words = frozenset(self._normalize(w) for w in filler_words if self._normalize(w))
        self.echo_min_words = max(2, int(echo_min_words))
        if not 0.5 <= echo_overlap_ratio <= 1.0:
            raise ValueError("echo_overlap_ratio must be between 0.5 and 1.0")
        self.echo_overlap_ratio = float(echo_overlap_ratio)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9']+", text.lower()))

    def classify(self, text: str, *, spoken_text: str = "") -> BargeInDecision:
        normalized = self._normalize(text)
        if not normalized:
            return BargeInDecision(False, reason="empty")
        tokens = normalized.split()
        if tokens and self.filler_words and all(t in self.filler_words for t in tokens):
            return BargeInDecision(False, filler_ignored=True, reason="filler_only")

        # Deterministic interruption phrases win over echo suppression. This
        # ensures "stop" works even if H.A.N.N.I. happened to just say "stop".
        for phrase in sorted(self.interrupt_phrases, key=len, reverse=True):
            phrase_match = re.search(
                rf"(?<![a-z0-9']){re.escape(phrase)}(?![a-z0-9'])",
                normalized,
            )
            if phrase_match is None:
                continue
            if normalized == phrase:
                return BargeInDecision(True, False, "", reason="interrupt_phrase")
            remainder = normalized[phrase_match.end():].strip()
            return BargeInDecision(True, bool(remainder), remainder, reason="interrupt_then_command")

        if spoken_text and self._looks_like_echo(normalized, spoken_text):
            return BargeInDecision(False, echo_ignored=True, reason="speaker_echo")

        # Any substantive non-echo speech while H.A.N.N.I. is talking is a
        # barge-in. The existing relevance classifier decides what to do with it.
        return BargeInDecision(True, True, text.strip(), reason="owner_speech")

    def _looks_like_echo(self, normalized_heard: str, spoken_text: str) -> bool:
        heard_tokens = normalized_heard.split()
        spoken = self._normalize(spoken_text)
        if not spoken:
            return False
        # Short multi-word phrases can still be speaker echo (e.g. "that's
        # all"). Single words are intentionally not suppressed because they
        # are common deliberate interruptions such as "stop" and "wait".
        if len(heard_tokens) >= 2 and normalized_heard in spoken:
            return True
        spoken_tokens = set(spoken.split())
        # A single substantial word emitted by the speakers can arrive as its
        # own VAD/STT segment. Suppress it when it is present in the current
        # spoken response; configured interrupt words were already handled
        # before this echo check and therefore still win deterministically.
        if len(heard_tokens) == 1 and len(heard_tokens[0]) >= 4 and heard_tokens[0] in spoken_tokens:
            return True
        if len(heard_tokens) < self.echo_min_words:
            return False
        overlap = sum(1 for token in heard_tokens if token in spoken_tokens) / len(heard_tokens)
        if overlap >= self.echo_overlap_ratio:
            return True
        return SequenceMatcher(None, normalized_heard, spoken).ratio() >= 0.62
