"""Optional, in-memory dashboard observations. Never stores audio or text."""
from __future__ import annotations

import math
import struct
import threading
import time
from contextlib import contextmanager


class Activity:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.enabled = False
        self._lock = threading.Lock()
        self._level = 0.0
        self._heard_at = float('-inf')
        self._playback = None
        self._speaking = False

    def microphone(self, pcm16: bytes) -> None:
        if not self.enabled:
            return
        # Runs in the capture consumer, never PortAudio's real-time callback.
        try:
            samples = [sample[0] for sample in struct.iter_unpack('<h', pcm16)]
            rms = math.sqrt(sum(x*x for x in samples) / max(1, len(samples))) / 32768
            with self._lock:
                self._level = min(1.0, rms * 8)
                self._heard_at = self.clock()
        except (ValueError, struct.error):
            pass  # An observer cannot break capture.

    def playback(self, process) -> None:
        if self.enabled:
            with self._lock:
                self._playback = process

    @contextmanager
    def speaking(self):
        if self.enabled:
            with self._lock:
                self._speaking = True
        try:
            yield
        finally:
            with self._lock:
                self._speaking = False

    def snapshot(self) -> dict:
        with self._lock:
            live = self.enabled and self.clock() - self._heard_at < 0.8
            speaking = self._speaking
            if self._playback is not None:
                try:
                    speaking = speaking or self._playback.poll() is None
                except OSError:
                    pass
                if not speaking:
                    self._playback = None
            return {'microphone_active': live, 'input_level': self._level if live else 0.0,
                    'speaking': bool(self.enabled and speaking)}


activity = Activity()
