"""Opt-in controls for the existing attentive voice session, never a new recorder.

No pipeline is started by importing this module or by a dashboard request. The
attend loop binds its own pump/classifier/playback and unbinds them on exit.
"""
from __future__ import annotations

import queue
import threading
import time

from hanni.core.activity import activity
from hanni.core.interaction import interaction
from hanni.dashboard.features import RequestLedger


class ManagedTranscriptPump:
    """Close capture on mute; resume only after the old pump has actually exited."""
    def __init__(self, factory, initial):
        self.factory = factory
        self.pump = initial
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.paused = False
        self.closed = False

    def start(self):
        self.pump.start()

    def running(self):
        thread = getattr(self.pump, 'thread', None)
        return bool(thread and thread.is_alive())

    @property
    def failed(self):
        return bool(getattr(self.pump, 'failed', False))

    def pause(self):
        with self.lock:
            if self.closed:
                raise RuntimeError('The voice session has stopped.')
            self.paused = True
            self.pump.stop()
            self.changed.notify_all()

    def resume(self):
        with self.lock:
            if self.closed:
                raise RuntimeError('The voice session has stopped.')
            if not self.paused:
                return
            if self.running():
                raise RuntimeError('Capture is still stopping; wait before unmuting.')
            # A new pipeline has empty ephemeral audio/transcript/segment buffers.
            fresh = self.factory()
            try:
                fresh.start()
            except BaseException:
                fresh.stop()
                raise
            self.pump = fresh
            self.paused = False
            self.changed.notify_all()

    def get(self, timeout=None):
        with self.lock:
            if self.closed:
                raise queue.Empty()
            if self.paused:
                # Preserve the attend loop's bounded queue wait while muted.
                # Returning immediately here would spin its consumer at 100% CPU.
                self.changed.wait(timeout=.1 if timeout is None else max(0, timeout))
                raise queue.Empty()
            pump = self.pump
        result = pump.get(timeout=timeout)
        with self.lock:
            if self.closed or self.paused or pump is not self.pump:
                raise queue.Empty()
        return result

    def stop(self):
        with self.lock:
            self.closed = True
            self.pump.stop()
            self.changed.notify_all()


class VoiceControl:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.pump = self.classifier = self.registry = None
        self.wake_name = None
        self.ledger = RequestLedger()
        self.metrics = self._empty_metrics()
        self.utterance_ended_at = None
        self.responsiveness = None

    @staticmethod
    def _empty_metrics():
        return {'wake_to_listening_ms': None, 'end_to_response_ms': None,
                'first_audible_ms': None, 'interrupt_ms': None, 'audio_failures': 0}

    def bind(self, pump, classifier, registry, wake_name):
        with self.lock:
            if self.pump is not None:
                raise RuntimeError('A voice controller is already attached.')
            self.pump, self.classifier, self.registry, self.wake_name = pump, classifier, registry, wake_name
            self.metrics = self._empty_metrics()
            self.ledger = RequestLedger()
            self.utterance_ended_at = None
            self.responsiveness = None

    def unbind(self, pump):
        with self.lock:
            if self.pump is pump:
                self.pump = self.classifier = self.registry = self.wake_name = None

    def snapshot(self):
        with self.lock:
            measured = activity.snapshot()
            with interaction.condition:
                state, mode_snapshot = interaction.snapshot(), interaction.voice_modes()
            failed = self.pump is not None and bool(getattr(self.pump, 'failed', False))
            available = self.pump is not None and not self.pump.closed and not failed
            paused = bool(available and self.pump.paused)
            muting = bool(paused and self.pump.running())
            muted = paused and not muting
            speaking = bool(available and (measured['speaking'] or state['tts_playback_active']))
            processing = bool(available and (state['response_in_progress'] or state['tts_preparing']))
            phase = ('disabled' if not available else 'muting' if muting else 'muted' if muted
                     else 'speaking' if speaking else 'processing' if processing
                     else 'listening' if state['voice_engaged'] else 'standby')
            return {'available': available, 'state': phase, 'active': available,
                    'listening_mode': bool(available and not paused and state['voice_engaged']),
                    **mode_snapshot,
                    'muted': muted, 'microphone_active': bool(available and not paused and measured['microphone_active']),
                    'input_level': measured['input_level'] if available and not paused else 0,
                    'speaking': speaking, 'processing': processing,
                    'actions': {'listen': available and not paused, 'mute': available and not paused,
                                'unmute': muted, 'interrupt': speaking or processing},
                    'metrics': dict(self.metrics),
                    'responsiveness': self.responsiveness,
                    'reason': None if available else 'Voice capture failed; restart the existing voice assistant.' if failed
                    else 'Start the existing voice assistant to enable voice controls.'}

    def execute(self, body):
        if (set(body) != {'id', 'action'} or not isinstance(body['action'], str)
                or body['action'] not in {'listen', 'mute', 'unmute', 'interrupt'}):
            raise ValueError('Choose a supported voice action and request ID.')
        return self.ledger.execute(body['id'], body, lambda: self._apply(body['action']))

    def transcript_observed(self, record, wake):
        with self.lock:
            # Source timestamps are from the existing ephemeral audio pipeline.
            # This measures end-of-utterance to the wake decision, not phoneme timing.
            ended = getattr(record, 'ended_at', 0)
            self.utterance_ended_at = ended if ended > 0 else None
            if wake and self.utterance_ended_at is not None:
                self.metrics['wake_to_listening_ms'] = round(max(0, self.clock() - ended) * 1000, 2)

    def response_observed(self):
        with self.lock:
            if self.utterance_ended_at is not None:
                self.metrics['end_to_response_ms'] = round(max(0, self.clock() - self.utterance_ended_at) * 1000, 2)
                self.utterance_ended_at = None

    def response_timings_observed(self, timing):
        with self.lock:
            self.responsiveness = timing

    def interruption_observed(self, started):
        with self.lock:
            self.metrics['interrupt_ms'] = round(max(0, self.clock() - started) * 1000, 2)

    def audio_failure(self):
        with self.lock:
            self.metrics['audio_failures'] += 1

    def _apply(self, action):
        with self.lock:
            if self.pump is None or self.pump.closed:
                raise RuntimeError('The attentive voice session is not running.')
            if action in {'listen', 'unmute'} and bool(getattr(self.pump, 'failed', False)):
                raise RuntimeError('Voice capture failed; restart the existing voice assistant.')
            # Mute/interrupt reduce activity and remain usable in Safe Mode.
            if action in {'listen', 'unmute'}:
                self.registry.context.emergency_stop.guard('resume local voice capture')
            if action == 'mute':
                self.pump.pause()
                self.classifier.clear_engagement()
                interaction.engaged(False)
            elif action == 'unmute':
                self.pump.resume()
            elif action == 'listen':
                if self.pump.paused:
                    raise RuntimeError('Unmute before starting a voice interaction.')
                # Use the original wake classifier; this is explicit manual arming,
                # not a claimed spoken wake recognition or synthetic audio event.
                self.classifier.classify(self.wake_name)
                interaction.engaged(True)
            else:
                beginning = self.clock()
                with interaction.condition:
                    playback = interaction.playback
                    cancellation = interaction.response_cancel_event
                    if (playback is None or not playback.active) and cancellation is None:
                        raise RuntimeError('There is no active speech playback to interrupt.')
                    if cancellation is not None:
                        cancellation.set()
                    if playback is not None and playback.active:
                        playback.stop()
                    interaction._stop_completion()
                self.metrics['interrupt_ms'] = round((self.clock() - beginning) * 1000, 2)
            return self.snapshot()


voice_control = VoiceControl()
