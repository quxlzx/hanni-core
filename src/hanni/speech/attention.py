"""Bridge ephemeral STT records into M3 owner-command decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from hanni.core.events import Event, EventType
from hanni.speech.relevance import RelevanceDecision, SpeechRelevanceClassifier
from hanni.speech.types import TranscriptRecord


class StreamingTextSession(Protocol):
    def stream_response(self, prompt: str, **kwargs: object) -> Iterator[str]: ...


@dataclass(frozen=True, slots=True)
class RoutedSpeech:
    """One transcript after the relevance boundary."""

    transcript: TranscriptRecord
    decision: RelevanceDecision
    event: Event | None


class SpeechAttentionRouter:
    """Apply relevance without persisting transcript contents in events/logs."""

    def __init__(self, classifier: SpeechRelevanceClassifier) -> None:
        self.classifier = classifier

    def route(self, transcript: TranscriptRecord) -> RoutedSpeech:
        decision = self.classifier.classify(transcript.text)
        from hanni.core.interaction import interaction
        interaction.engaged(decision.engaged)
        event = None
        if decision.relevant:
            event = Event(
                type=EventType.OWNER_COMMAND,
                source="speech.relevance",
                payload={
                    "transcript_id": transcript.transcript_id,
                    "wake_word_detected": decision.wake_word_detected,
                    "follow_up": decision.follow_up,
                },
            )
        return RoutedSpeech(transcript=transcript, decision=decision, event=event)


class AttentiveTextBridge:
    """Only forward relevant utterances to the Supervisor text session."""

    def __init__(self, router: SpeechAttentionRouter, session: StreamingTextSession) -> None:
        self.router = router
        self.session = session

    def handle(self, transcript: TranscriptRecord, **generation_kwargs: object) -> tuple[RoutedSpeech, Iterator[str]]:
        routed = self.router.route(transcript)
        if not routed.decision.relevant:
            return routed, iter(())
        return routed, self.session.stream_response(routed.decision.command_text, **generation_kwargs)
