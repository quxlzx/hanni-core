"""Local signature voice with cancellable synthesis and memory-only playback."""
from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
import subprocess
import sys
import threading

from .tts import CompletedPlayback, SubprocessTtsPlayback, TtsError, WindowsSapiTts, split_for_speech


class NeuralPlayback(SubprocessTtsPlayback):
    """Enforce a deadline even when a caller only polls active (voice mode)."""

    def __init__(self, process, timeout_seconds):
        self._timed_out = False
        self._cancelled = False
        self._timer = threading.Timer(timeout_seconds, self._expire)
        self._timer.daemon = True
        super().__init__(process)
        self._timer.start()

    def _expire(self):
        with self._stop_lock:
            if not self._cancelled and super().active:
                self._timed_out = True
                super().stop()

    @property
    def active(self):
        running = super().active
        if not running:
            self._timer.cancel()
        return running

    def stop(self):
        self._timer.cancel()
        with self._stop_lock:
            if not self._timed_out:
                self._cancelled = True
            super().stop()

    @property
    def cancelled(self):
        return self._cancelled

    def wait(self, timeout=None):
        try:
            super().wait(timeout)
            if self._timed_out:
                raise TtsError("local neural TTS timed out")
        finally:
            self._timer.cancel()


class KokoroTts:
    """One hidden worker per reply: stopping it cancels synthesis AND audio.

    No server, open port, persistent audio file, or model download at runtime.
    Releasing the worker also returns its model memory between conversations.
    """

    def __init__(self, config, *, data_dir=None, output_device=None):
        self.config = config
        self.output_device = output_device
        directory = Path(config.model_dir).expanduser()
        self.directory = (directory if directory.is_absolute() else Path(data_dir or "data") / directory).resolve()
        self._warned = False
        self.fallback = WindowsSapiTts(rate=config.rate, volume=config.volume,
                                       chunk_chars=config.chunk_chars, timeout_seconds=config.timeout_seconds,
                                       output_device=output_device)

    def unavailable_reason(self):
        for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            if not (self.directory / name).is_file():
                return "voice model files are missing"
        for module in ("kokoro_onnx", "sounddevice"):
            if importlib.util.find_spec(module) is None:
                return "optional voice packages are missing"
        return None

    def start(self, text):
        from hanni.core.interaction import interaction
        if interaction.speech_muted:
            return CompletedPlayback()
        chunks = split_for_speech(text, max_chars=min(180, self.config.chunk_chars))
        if not chunks:
            return CompletedPlayback()
        reason = self.unavailable_reason()
        if reason:
            if not self.config.sapi_fallback:
                raise TtsError(f"{reason}; run python scripts/setup_hanni_voice.py")
            if not self._warned:
                logging.getLogger(__name__).warning("%s; using Windows SAPI. Run python scripts/setup_hanni_voice.py", reason)
                self._warned = True
            return self.fallback.start(text)
        payload = dict(chunks=chunks, model_dir=str(self.directory), voice=self.config.voice,
                       speed=self.config.speed, language=self.config.language,
                       volume=self.config.volume, cpu_threads=self.config.cpu_threads,
                       pitch_semitones=self.config.pitch_semitones,
                       output_name=self.output_device.name if self.output_device else None)
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "hanni.speech.neural_worker"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert proc.stdin is not None
            proc.stdin.write(json.dumps(payload))
            proc.stdin.close()
        except OSError as exc:
            if proc is not None:
                proc.kill()
                proc.wait()
            raise TtsError("Could not start the local voice worker") from exc
        return NeuralPlayback(proc, self.config.timeout_seconds)

    def prepare(self):
        """Check the chosen voice before capture starts, without changing it."""
        reason = self.unavailable_reason()
        if reason and not self.config.sapi_fallback:
            raise TtsError(f'{reason}; run python scripts/setup_hanni_voice.py')

    def speak(self, text):
        from hanni.core.interaction import interaction
        with interaction.synthesis():
            playback = self.start(text)
            try:
                playback.wait(self.config.timeout_seconds)
            finally:
                playback.stop()
