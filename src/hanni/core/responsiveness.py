"""Ephemeral scalar phase timings; no prompts, transcripts or audio are stored."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_turn = ContextVar('hanni_responsiveness', default=None)


class TurnTimings:
    def __init__(self, *, speech_ended_at=None, clock=time.perf_counter):
        self.clock = clock
        self.started = clock()
        self.speech_ended_at = speech_ended_at
        self.phases = {}
        self.events = {}
        self.server_queue_ms = None
        self.vad_to_tts_dispatch_ms = None

    def mark(self, name):
        if name == 'first_tts_dispatch' and name not in self.events and self.speech_ended_at:
            self.vad_to_tts_dispatch_ms = (time.monotonic() - self.speech_ended_at) * 1000
        self.events.setdefault(name, (self.clock() - self.started) * 1000)

    def snapshot(self):
        return {'phases_ms': dict(self.phases), 'events_ms': dict(self.events),
                'server_queue_ms': self.server_queue_ms,
                'audible_onset_ms': None, 'audible_onset_status': 'NOT MEASURED',
                'vad_segment_end_to_tts_dispatch_ms': self.vad_to_tts_dispatch_ms,
                'total_ms': (self.clock() - self.started) * 1000}


@contextmanager
def turn_scope(timing=None):
    if timing is None and _turn.get() is not None:
        yield _turn.get()
        return
    timing = timing or TurnTimings()
    token = _turn.set(timing)
    try:
        yield timing
    finally:
        _turn.reset(token)


@contextmanager
def phase(name):
    turn = _turn.get()
    at = time.perf_counter()
    try:
        yield
    finally:
        if turn is not None:
            turn.phases[name] = turn.phases.get(name, 0) + (time.perf_counter() - at) * 1000


def mark(name):
    turn = _turn.get()
    if turn is not None:
        turn.mark(name)
