"""Always-listening relevance, persistent engagement, and filler suppression.

The classifier is deliberately deterministic and cheap. Background speech is
never sent to the Supervisor merely because it was transcribed. An explicit
wake name activates H.A.N.N.I.; by default she remains active until a configured
disengage phrase is heard. Pure filler utterances such as ``um``/``hmm`` are
ignored even while active and do not create Supervisor turns.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Sequence


DEFAULT_WAKE_NAMES = ("hanni", "ani", "hani", "hanny", "hannie", "honey")
DEFAULT_DISENGAGE_PHRASES = (
    "that's all",
    "that is all",
    "that'll be all",
    "that will be all",
    "we're done",
    "we are done",
    "go quiet",
    "you can go quiet",
    "stop responding",
    "stand by",
    "standby",
    "never mind",
    "nevermind",
    "never mind hanni",
    "thanks hanni that's all",
    "thank you hanni that's all",
    "bye",
    "goodbye",
    "see you",
    "talk to you later",
)
DEFAULT_FILLER_WORDS = (
    "um",
    "umm",
    "ummm",
    "uh",
    "uhh",
    "uhhh",
    "hm",
    "hmm",
    "hmmm",
    "mm",
    "mmm",
    "erm",
    "er",
    "err",
    "ah",
)
DEFAULT_ACKNOWLEDGEMENT_WORDS = (
    "thanks",
    "thank you",
    "yeah",
    "yep",
    "okay",
    "ok",
    "alright",
    "got it",
    "cool",
)


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    """Result of classifying one ephemeral transcript."""

    relevant: bool
    wake_word_detected: bool = False
    follow_up: bool = False
    disengaged: bool = False
    engaged: bool = False
    filler_ignored: bool = False
    acknowledgement_ignored: bool = False
    command_text: str = ""
    reason: str = "irrelevant"


class SpeechRelevanceClassifier:
    """Stateful deterministic gate for always-listening speech.

    ``engagement_seconds=0`` means persistent engagement: after the wake name is
    heard, H.A.N.N.I. remains active until a disengage phrase is spoken. A
    positive value retains the older timed-window behavior for diagnostics or
    future configuration experiments.

    ``recent_turns`` remains accepted for compatibility with the early M2 stub,
    but the live path uses explicit engagement state.
    """

    _FOLLOW_UP_HINTS = (
        "what", "why", "how", "when", "where", "who", "which", "next",
        "again", "more", "this", "that", "it", "them", "they", "show",
        "tell", "open", "close", "start", "stop", "wait", "resume",
        "continue",
    )

    def __init__(
        self,
        *,
        wake_names: Sequence[str] = DEFAULT_WAKE_NAMES,
        engagement_seconds: float = 0.0,
        disengage_phrases: Sequence[str] = DEFAULT_DISENGAGE_PHRASES,
        filler_words: Sequence[str] = DEFAULT_FILLER_WORDS,
        acknowledgement_words: Sequence[str] = DEFAULT_ACKNOWLEDGEMENT_WORDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        names = tuple(dict.fromkeys(self._normalize(name) for name in wake_names if self._normalize(name)))
        if not names:
            raise ValueError("at least one wake name is required")
        if engagement_seconds < 0:
            raise ValueError("engagement_seconds must be >= 0")
        self.wake_names = names
        self.engagement_seconds = float(engagement_seconds)
        self.disengage_phrases = tuple(
            dict.fromkeys(self._normalize(phrase) for phrase in disengage_phrases if self._normalize(phrase))
        )
        self.filler_words = tuple(
            dict.fromkeys(self._normalize(word) for word in filler_words if self._normalize(word))
        )
        self._filler_set = frozenset(self.filler_words)
        self.acknowledgement_words = tuple(
            dict.fromkeys(self._normalize(word) for word in acknowledgement_words if self._normalize(word))
        )
        self._acknowledgement_set = frozenset(self.acknowledgement_words)
        self.clock = clock
        # M6 owner preference: every configured wake alias is token-bounded but
        # may appear anywhere in the utterance. This includes the practical
        # Whisper fallback "honey". Examples such as "can you open VS Code,
        # Hanni?" and "hey, Honey, are you there?" now activate H.A.N.N.I.
        alternatives = "|".join(re.escape(name) for name in sorted(self.wake_names, key=len, reverse=True))
        self._wake_re = (
            re.compile(rf"(?<![a-z])(?:{alternatives})(?![a-z])", re.IGNORECASE)
            if alternatives
            else None
        )
        self._engaged = False
        self._engaged_until = 0.0

    @property
    def engaged_until(self) -> float:
        return self._engaged_until

    @property
    def persistent_engagement(self) -> bool:
        return self.engagement_seconds == 0

    def is_engaged(self, *, now: float | None = None) -> bool:
        if not self._engaged:
            return False
        if self.persistent_engagement:
            return True
        current = self.clock() if now is None else now
        return current < self._engaged_until

    def clear_engagement(self) -> None:
        self._engaged = False
        self._engaged_until = 0.0

    def classify(
        self,
        text: str,
        *,
        recent_turns: Sequence[str] = (),
        now: float | None = None,
    ) -> RelevanceDecision:
        current = self.clock() if now is None else now
        raw = text.strip()
        normalized = self._normalize(raw)
        if not normalized:
            return RelevanceDecision(False, reason="empty")

        was_engaged = self.is_engaged(now=current)
        wake_match = self._find_wake_match(raw)
        wake_word_detected = wake_match is not None

        # Remove harmless leading hesitation words for semantic decisions, but
        # never let the filler filter hide a real wake name anywhere in the
        # utterance (e.g. "umm, Hanni, open VS Code").
        meaningful_raw = self._strip_leading_fillers(raw)
        meaningful_normalized = self._normalize(meaningful_raw)

        if not wake_word_detected and not meaningful_normalized:
            return RelevanceDecision(
                False,
                engaged=was_engaged,
                filler_ignored=True,
                reason="filler_only",
            )

        # A clear conversational close wins even if it contains the wake name.
        # When idle, a random "never mind" is background speech, not a state
        # transition that starts or stops microphone capture.
        disengage_text = meaningful_normalized or normalized
        if (was_engaged or wake_word_detected) and self._matches_disengage(disengage_text):
            self.clear_engagement()
            return RelevanceDecision(
                False,
                wake_word_detected=wake_word_detected,
                disengaged=True,
                engaged=False,
                command_text="",
                reason="disengage_phrase",
            )

        # Short passive acknowledgements should not generate a fresh LLM turn.
        # They leave H.A.N.N.I. engaged so the owner can continue naturally.
        if was_engaged and not wake_word_detected and meaningful_normalized in self._acknowledgement_set:
            self._engage(current)
            return RelevanceDecision(
                False,
                engaged=True,
                acknowledgement_ignored=True,
                reason="passive_acknowledgement",
            )

        if wake_word_detected:
            self._engage(current)
            command = self._strip_leading_fillers(self._strip_wake_name(raw, wake_match))
            # Wake-only utterances are still relevant so the Supervisor may
            # acknowledge the activation naturally.
            if not command:
                command = "Hanni"
            return RelevanceDecision(
                True,
                wake_word_detected=True,
                follow_up=False,
                engaged=True,
                command_text=command,
                reason="wake_name",
            )

        if was_engaged:
            self._engage(current)  # no-op timeout refresh in persistent mode
            return RelevanceDecision(
                True,
                wake_word_detected=False,
                follow_up=True,
                engaged=True,
                command_text=meaningful_raw or raw,
                reason="engaged_follow_up",
            )

        # Compatibility with the M2 prototype test. This is not used by the
        # live M3 path, which relies on explicit activation/deactivation.
        recent_text = " ".join(self._normalize(turn) for turn in recent_turns if turn and turn.strip())
        if recent_text and self._looks_like_follow_up(meaningful_normalized):
            return RelevanceDecision(
                True,
                wake_word_detected=False,
                follow_up=True,
                engaged=False,
                command_text=meaningful_raw or raw,
                reason="recent_turn_follow_up",
            )

        return RelevanceDecision(False, command_text="", reason="background")

    def _engage(self, now: float) -> None:
        self._engaged = True
        self._engaged_until = float("inf") if self.persistent_engagement else now + self.engagement_seconds

    @staticmethod
    def _normalize(text: str) -> str:
        value = text.lower().strip().replace('\u2019', "'").replace('\u2018', "'")
        value = re.sub(r"[^a-z0-9'\s]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _matches_disengage(self, normalized: str) -> bool:
        # STT may omit contraction apostrophes. These spelling differences
        # must still reach standby rather than being forwarded as a model turn.
        normalized = normalized.replace("'", "")
        return any(
            normalized == phrase
            or normalized.startswith(phrase + " ")
            or normalized.endswith(" " + phrase)
            or f" {phrase} " in f" {normalized} "
            for configured in self.disengage_phrases
            for phrase in (configured.replace("'", ""),)
        )

    def _find_wake_match(self, original: str):
        if self._wake_re is not None:
            return self._wake_re.search(original)
        return None

    def _strip_wake_name(self, original: str, match=None) -> str:
        if match is None:
            match = self._find_wake_match(original)
        if match is None:
            return original.strip()
        before = original[: match.start()].strip(" \t,.:;!?-—")
        after = original[match.end() :].strip(" \t,.:;!?-—")
        return " ".join(part for part in (before, after) if part).strip()

    def _strip_leading_fillers(self, original: str) -> str:
        value = original.strip()
        while value:
            match = re.match(r"^([A-Za-z']+)(?:[\s,.:;!?-]+|$)", value)
            if match is None:
                break
            if self._normalize(match.group(1)) not in self._filler_set:
                break
            value = value[match.end() :].lstrip()
        return value.strip()

    def _looks_like_follow_up(self, text: str) -> bool:
        if not text:
            return False
        words = text.split()
        if any(word in self._FOLLOW_UP_HINTS for word in words):
            return True
        return len(words) <= 12 and any(word in {"please", "okay", "alright", "thanks"} for word in words)
