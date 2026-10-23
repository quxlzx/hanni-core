"""Bounded final-sentence speech with generation-time and playback interruption.

No voice identity, wake/relevance policy or synthesis backend is selected here.
All speech comes from the existing final-answer stream. A cancelled generation
can finish a pending HTTP read, but it cannot dispatch another tool or speak.
"""
from collections import deque
from contextvars import copy_context
from dataclasses import dataclass
import queue
import threading
import time

from hanni.core.response_stream import FinalSentence, SentenceBuffer, TurnCancelled, cancellation_scope, check_cancelled
from hanni.core.response_style import sanitize_assistant_text
from hanni.core.interaction import interaction
from hanni.core.responsiveness import mark
from hanni.speech.live import PUMP_FINISHED, PumpFailure
from hanni.speech.tts import TtsError


class ResponsePump:
    def __init__(self, response, *, gate=None, queue_size=32):
        self.response = response
        self.gate = gate or threading.Lock()
        self.queue = queue.Queue(maxsize=queue_size)
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.error = None
        context = copy_context()
        self.thread = threading.Thread(target=lambda: context.run(self._run), name='hanni-final-answer', daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        source = iter(self.response)
        try:
            with self.gate, cancellation_scope(self.cancelled):
                check_cancelled()
                for chunk in source:
                    check_cancelled()
                    while not self.cancelled.is_set():
                        try:
                            self.queue.put(chunk, timeout=.05)
                            break
                        except queue.Full:
                            pass
        except TurnCancelled:
            pass
        except Exception as exc:
            if not self.cancelled.is_set():
                self.error = exc
        finally:
            close = getattr(source, 'close', None)
            if callable(close):
                close()
            self.done.set()

    def cancel(self):
        self.cancelled.set()
        while True:
            try: self.queue.get_nowait()
            except queue.Empty: break


@dataclass
class VoiceResponseResult:
    pending: object = None
    stream_finished: bool = False
    interrupted: bool = False


def deliver_response(response, *, tts=None, pump=None, barge=None, barge_enabled=True,
                     echo_suppression=True, poll_seconds=.08, shutdown_event=None,
                     on_text=lambda chunk: None, on_interrupt=lambda started: None,
                     emergency=lambda text: False, gate=None, playback_timeout=30,
                     stop_active=lambda: False):
    producer = ResponsePump(response, gate=gate)
    pending_speech = deque()
    text_buffer = SentenceBuffer()
    playback = None
    spoken = ''
    recent_speech = deque(maxlen=3)
    flushed = False
    result = VoiceResponseResult()
    stop_initial = stop_active()
    with interaction.condition:
        interaction.response_cancel_event = producer.cancelled
    producer.start()

    def accept(text):
        value = sanitize_assistant_text(text)
        if value and tts is not None:
            pending_speech.append(value)

    def cancel():
        producer.cancel()
        pending_speech.clear()
        text_buffer.buffer = ''
        if playback is not None and playback.active:
            playback.stop()

    try:
        while True:
            if producer.cancelled.is_set():
                cancel()
                result.interrupted = True
                return result
            if shutdown_event is not None and shutdown_event.is_set():
                cancel()
                result.stream_finished = True
                return result
            if not stop_initial and stop_active():
                cancel()
                result.interrupted = True
                return result
            # Bounded producer and speech queues provide backpressure for detail.
            if len(pending_speech) < 16:
                try:
                    chunk = producer.queue.get(timeout=poll_seconds)
                    on_text(chunk)
                    if isinstance(chunk, FinalSentence):
                        for prior in text_buffer.feed('', final=True): accept(prior)
                        accept(chunk)
                    else:
                        for sentence in text_buffer.feed(chunk): accept(sentence)
                except queue.Empty:
                    pass
            if producer.done.is_set() and producer.queue.empty() and not flushed:
                for sentence in text_buffer.feed('', final=True): accept(sentence)
                flushed = True
                if producer.error is not None:
                    # Never speak a buffered partial answer after a generation error.
                    pending_speech.clear()
                    raise producer.error
            if playback is not None:
                if getattr(playback, 'cancelled', False) is True:
                    cancel()
                    result.interrupted = True
                    return result
                if not playback.active:
                    playback.wait(timeout=playback_timeout)
                    playback = None
            if playback is None and pending_speech:
                sentence = pending_speech.popleft()
                if producer.cancelled.is_set():
                    continue
                mark('first_tts_dispatch')  # Dispatch is not acoustic onset.
                recent_speech.append(sentence)
                spoken = ' '.join(recent_speech)
                if hasattr(tts, 'start'):
                    playback = tts.start(sentence)
                    with interaction.condition:
                        interaction.playback = playback
                else:
                    tts.speak(sentence)
            if flushed and not pending_speech and playback is None:
                return result
            during = None
            if pump is not None:
                try:
                    during = pump.get(timeout=poll_seconds)
                except queue.Empty:
                    pass
            else:
                producer.done.wait(poll_seconds)
            if during is PUMP_FINISHED:
                cancel()
                result.stream_finished = True
                return result
            if isinstance(during, PumpFailure):
                cancel()
                raise during.error
            if during is not None and (emergency(during.text) or barge_enabled and barge is not None):
                is_emergency = emergency(during.text)
                decision = None if is_emergency else barge.classify(
                    during.text, spoken_text=spoken if echo_suppression else '')
                if is_emergency or decision.interrupt:
                    at = time.monotonic()
                    cancel()
                    on_interrupt(at)
                    result.interrupted = True
                    if is_emergency:
                        result.pending = during
                    elif decision.route_after_interrupt and decision.command_text:
                        from dataclasses import replace
                        result.pending = replace(during, text=decision.command_text)
                    return result
    finally:
        cancel()
        producer.thread.join(timeout=.2)
        with interaction.condition:
            if interaction.playback is playback:
                interaction.playback = None
            if interaction.response_cancel_event is producer.cancelled:
                interaction.response_cancel_event = None
