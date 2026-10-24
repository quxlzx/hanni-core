"""Foreground priority and one speech/action owner across local execution lanes."""
from __future__ import annotations
from contextlib import contextmanager
from collections import deque
import logging
import threading
from uuid import uuid4


class InteractionState:
    def __init__(self):
        self.condition = threading.Condition(threading.RLock())
        self.actions = threading.RLock()
        self.foreground_requests = 0
        self.response_in_progress = False
        self.voice_engaged = False
        self.speech_muted = False
        self.speech_mute_revision = 0
        self.wake_enabled = True
        self.voice_mode_session = uuid4().hex
        self.voice_mode_revision = 0
        self.voice_mode_events = deque(maxlen=32)
        self.active_background_jobs = 0
        self.playback = None
        self.response_cancel_event = None
        self.completion_playback = None
        self.completion_text = ''
        self.synthesizing = False
        self.speaker = None
        self.closed = False

    def snapshot(self):
        with self.condition:
            speaking = self.synthesizing or bool(self.playback and self.playback.active)
            return dict(response_in_progress=self.response_in_progress, tts_speaking=speaking,
                        tts_preparing=bool(self.synthesizing),
                        tts_playback_active=bool(self.playback and self.playback.active),
                        voice_engaged=self.voice_engaged,
                        speech_muted=self.speech_muted, wake_enabled=self.wake_enabled,
                        foreground_request_active=self.foreground_requests > 0,
                        active_background_jobs=self.active_background_jobs)

    def engaged(self, value):
        with self.condition:
            value = bool(value)
            if value != self.voice_engaged:
                self.voice_engaged = value
                self.voice_mode_revision += 1
                self.voice_mode_events.append({'revision': self.voice_mode_revision, 'engaged': value})

    def mute_speech(self, muted):
        with self.condition:
            if self.speech_muted != bool(muted):
                self.speech_mute_revision += 1
            self.speech_muted = bool(muted)
            if muted:
                if self.playback is not None:
                    self.playback.stop()
                self._stop_completion()

    def cancel_response(self):
        with self.condition:
            if self.response_cancel_event is not None:
                self.response_cancel_event.set()
            if self.playback is not None:
                self.playback.stop()
            self._stop_completion()

    def voice_modes(self):
        with self.condition:
            return {'mode_session': self.voice_mode_session, 'mode_revision': self.voice_mode_revision,
                    'mode_events': [dict(event) for event in self.voice_mode_events]}

    @contextmanager
    def synthesis(self):
        with self.condition:
            self._stop_completion()
            self.synthesizing = True
        try:
            yield
        finally:
            with self.condition: self.synthesizing = False

    def responding(self, value):
        with self.condition:
            if value:
                self._stop_completion()
            self.response_in_progress = bool(value)
            self.condition.notify_all()

    def _stop_completion(self):
        if self.completion_playback is not None:
            self.completion_playback.stop()
            self.completion_playback = None

    @contextmanager
    def foreground(self):
        with self.condition:
            self._stop_completion()
            self.foreground_requests += 1
        try:
            yield
        finally:
            with self.condition:
                self.foreground_requests -= 1
                self.condition.notify_all()

    def yield_background(self, interrupted=lambda: False):
        with self.condition:
            while self.foreground_requests and not interrupted():
                self.condition.wait(.1)
            return not interrupted()

    def completion(self, summary, notify):
        # Starting speech and admitting a foreground response share this lock.
        # A new foreground turn cancels ONLY completion speech, never owner speech.
        with self.condition:
            state = self.snapshot()
            if (self.speaker and not self.speech_muted and state['voice_engaged'] and not self.closed and
                not any(state[k] for k in ('response_in_progress', 'tts_speaking', 'foreground_request_active'))):
                try:
                    self.completion_playback = self.speaker(summary[:240])
                    self.completion_text = summary[:240]
                    self.playback = self.completion_playback
                    return 'speech'
                except Exception:
                    logging.getLogger(__name__).warning('Completion speech unavailable')
        notify()
        return 'notification'

    def close(self):
        with self.condition:
            self.closed = True
            self.engaged(False)
            self.speaker = None
            self._stop_completion()
            self.condition.notify_all()


interaction = InteractionState()
