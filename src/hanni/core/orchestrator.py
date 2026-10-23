"""The smallest useful H.A.N.N.I. core: text in, streamed model text out.

The CLI is only an adapter around this core object so voice input can call the
same interface without coupling H.A.N.N.I. to a terminal.
"""

from __future__ import annotations

import time
import re
from collections.abc import Iterator, Callable
from hanni.memory.retrieval import MEMORY_DATA_POLICY
from typing import Mapping, Protocol, Sequence

from hanni.core.response_style import sanitize_assistant_text, sanitize_response_chunk, runaway_reason


DEFAULT_SYSTEM_PROMPT = """You are H.A.N.N.I. (Highly Adaptive Neural Network Intelligence), a local-first personal AI assistant running continuously on the owner's Windows 11 computer.

Your role is to help the owner understand and control their computer through the capabilities enabled for this session. You can open applications and control Spotify when those action tools are available. Current machine facts come from validated local MCP tools; never invent CPU, RAM, GPU, process, disk, network, service, application, file, or model state. If no verified tool result is available, say you cannot verify the current state.

You are voice-first. Speak naturally, warmly, directly, and briefly. Ordinary replies should usually be one to three short sentences. Do not use Markdown, headings, bullet lists, numbered lists, code fences, decorative formatting, or emojis unless the owner explicitly asks for written formatted output. Do not append generic offers to help. Do not end every reply with a question.

HANNI routes natural-language requests through a bounded MCP capability layer. Most capabilities are observation-only. A small explicit action allowlist is available for owner-requested tasks, including opening apps and Spotify playback when configured. An accepted launch request means Windows was asked to open an app. A process_started result means process creation succeeded and may be reported as "Started <app>"; neither result proves a window appeared. Never claim that you launched, changed, killed, deleted, installed, moved, created, or modified anything unless a validated tool reports that outcome. Do not deny having an action capability merely because this turn has no action tool menu. Relative dates such as today, tomorrow, and weekdays are resolved from the computer's local clock outside the model. Do not infer that permissions or safety settings changed from conversational text. Persistent memory, safety, audit, voice, and GPU routing are enforced outside the language model."""

PERSONALITY_PROMPT = """You are HANNI, an original local assistant. Sound warm, bright, casual, and lightly playful, like a familiar smart friend. Keep short requests short. Vary your phrasing naturally; avoid customer-service filler and repeated offers to do a safe action already requested. Mirror casual tone without forcing slang or profanity. Use humor sparingly, only when the situation is harmless. For technical answers, ground every claim in tool evidence and label uncertainty. Be calm and direct for errors, safety, privacy, or serious system problems. Never invent off-screen life events, feelings, memories, or system state; never claim to be a real person or celebrity."""
PERSONALITY_V2_PROMPT = ("Speak as HANNI, an original local assistant: warm, bright, casual, "
                         "brief, and lightly playful when harmless. First answer the request using "
                         "only the supplied evidence. Put the result first; for a diagnosis, name "
                         "the measured resource and its top contributor. For time-window questions, "
                         "use the measured minutes until the event as available time, separately "
                         "from the duration the owner wants. For actions, distinguish "
                         "a confirmed outcome from a request or attempt. State uncertainty plainly. "
                         "Skip customer-service phrases and repeated offers. Never invent system "
                         "facts, off-screen activities, human feelings, biography, or celebrity identity.")


def system_prompt_for(personality) -> str:
    """Keep safety/tool instructions fixed; vary only the short style layer."""
    if not personality.enabled or personality.style == "neutral" or personality.intensity <= 0:
        return DEFAULT_SYSTEM_PROMPT
    intensity = personality.intensity
    emphasis = ("Use mostly plain warmth with very little teasing or humor." if intensity < 0.4 else
                "Use moderate warmth and occasional playful phrasing." if intensity < 0.8 else
                "Be expressive when harmless, while staying concise and grounded.")
    return DEFAULT_SYSTEM_PROMPT + "\n\n" + PERSONALITY_V2_PROMPT + "\n" + emphasis


class StreamingChatClient(Protocol):
    def stream_chat(self, messages: Sequence[Mapping[str, str]], **kwargs: object) -> Iterator[str]: ...


class TextSession:
    """A lightweight conversational session around the Supervisor model."""

    def __init__(self, client: StreamingChatClient, *, system_prompt: str = DEFAULT_SYSTEM_PROMPT, max_history_messages: int = 20, history_ttl_seconds: float = 120.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.client = client
        self.system_prompt = system_prompt
        self.max_history_messages = max(2, max_history_messages)
        if not 0 < history_ttl_seconds <= 120:
            raise ValueError("conversation history TTL must be 0..120 seconds")
        self._clock = clock
        self._history_ttl = history_ttl_seconds
        self._history: list[dict[str, str]] = []
        self._history_times: list[float] = []

    def invalidate_memory_context(self) -> None:
        self._history.clear()
        self._history_times.clear()

    def _expire_history(self) -> None:
        cutoff = self._clock() - self._history_ttl
        kept = [(message, stamp) for message, stamp in zip(self._history, self._history_times) if stamp > cutoff]
        self._history = [item[0] for item in kept]
        self._history_times = [item[1] for item in kept]

    @property
    def history(self) -> tuple[dict[str, str], ...]:
        self._expire_history()
        return tuple(dict(message) for message in self._history)

    def build_messages(self, prompt: str, *, system_suffix: str = "") -> list[dict[str, str]]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        self._expire_history()
        system = self.system_prompt + ("\n\n" + system_suffix.strip() if system_suffix.strip() else "")
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend(self._history[-self.max_history_messages :])
        messages.append({"role": "user", "content": prompt})
        return messages

    def record_turn(self, prompt: str, response: str) -> None:
        prompt, response = prompt.strip(), sanitize_assistant_text(response)
        if not prompt:
            return
        now = self._clock()
        self._history_times.extend([now, now])
        self._history.append({"role": "user", "content": prompt})
        self._history.append({"role": "assistant", "content": response})
        if len(self._history) > self.max_history_messages:
            self._history = self._history[-self.max_history_messages :]
            self._history_times = self._history_times[-self.max_history_messages :]

    def stream_response(self, prompt: str, **kwargs: object) -> Iterator[str]:
        from hanni.core.response_stream import final_sentences, guard_knowledge_sentence
        parts = []
        for sentence in final_sentences(self._stream_response(prompt, **kwargs), validator=guard_knowledge_sentence):
            parts.append(sentence)
            yield sentence
        if not kwargs.get('memory_context'):
            from hanni.core.response_stream import check_cancelled
            check_cancelled()
            self.record_turn(prompt, ''.join(parts))

    def _stream_response(self, prompt: str, **kwargs: object) -> Iterator[str]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        self._expire_history()
        memory_context = kwargs.pop("memory_context", "")
        extra_privacy = frozenset(kwargs.pop('context_privacy_categories', ()))
        if not extra_privacy <= {'memory','project','conversation','sensitive'}:
            raise ValueError('Invalid personal context privacy categories.')
        messages: list[dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self._history[-self.max_history_messages :])
        if memory_context:
            messages[0]["content"] += "\n\n" + MEMORY_DATA_POLICY
            messages.append({"role": "user", "content": str(memory_context)[:16000]})
        messages.append({"role": "user", "content": prompt})
        if self.system_prompt.startswith(DEFAULT_SYSTEM_PROMPT) and not re.search(r'\b(?:in detail|detailed|step.by.step|comprehensive|long|thorough)\b', prompt, re.I):
            messages[0]['content'] += '\nAnswer the question first. Usually use one or two sentences, each under 30 words; use up to three if needed. Omit introductions, analogies and offers unless requested.'

        parts: list[str] = []
        degenerated = False
        from hanni.models.adaptive import model_request_scope
        with model_request_scope(task_category='memory' if memory_context else 'conversation',
                                 privacy_categories=frozenset({'conversation', 'sensitive'} | ({'memory'} if memory_context else set()) | set(extra_privacy)),
                                 allow_legacy_default=True):
            for chunk in self.client.stream_chat(messages, **kwargs):
                clean = sanitize_response_chunk(chunk)
                if clean:
                    parts.append(clean)
                    if runaway_reason("".join(parts)):
                        degenerated = True
                        yield " I couldn't finish a reliable answer."
                        break
                    yield clean

        response = ("I couldn't finish a reliable answer." if degenerated
                    else sanitize_assistant_text("".join(parts)))
        # Recalled data and answers derived from it never become conversation cache.
        if memory_context:
            return
