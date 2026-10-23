"""Local Windows microphone capture using sounddevice/PortAudio.

The dependency is imported lazily so Milestone 0-1 commands continue to work
without the optional speech stack installed.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from hanni.speech.types import AudioChunk
from hanni.core.activity import activity


class SpeechDependencyError(RuntimeError):
    """Raised when an optional local speech dependency is unavailable."""


class MicrophoneError(RuntimeError):
    """Raised when the microphone cannot be opened or read."""


@dataclass(frozen=True, slots=True)
class MicrophoneDevice:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float
    hostapi: int | None = None

    def render(self) -> str:
        return f"{self.index}: {self.name} (inputs={self.max_input_channels}, default_rate={self.default_samplerate:g})"


def _sounddevice() -> Any:
    try:
        import sounddevice as sd
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise SpeechDependencyError(
            'sounddevice is not installed; run `.\\scripts\\setup_speech.ps1` or `pip install -e ".[speech]"`'
        ) from exc
    return sd


def list_input_devices() -> tuple[MicrophoneDevice, ...]:
    sd = _sounddevice()
    try:
        devices = sd.query_devices()
    except Exception as exc:  # pragma: no cover - hardware/backend dependent
        raise MicrophoneError(f"unable to enumerate audio devices: {exc}") from exc
    result: list[MicrophoneDevice] = []
    for index, item in enumerate(devices):
        channels = int(item.get("max_input_channels", 0))
        if channels <= 0:
            continue
        result.append(
            MicrophoneDevice(
                index=index,
                name=str(item.get("name", f"device-{index}")),
                max_input_channels=channels,
                default_samplerate=float(item.get("default_samplerate", 0.0)),
                hostapi=int(item["hostapi"]) if item.get("hostapi") is not None else None,
            )
        )
    return tuple(result)


def resolve_device(value: str | int | None) -> str | int | None:
    if value is None or value == "" or (isinstance(value, str) and value.strip().lower() == "default"):
        return None
    if isinstance(value, int):
        return value
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError:
        return stripped


class MicrophoneCapture:
    """Yield fixed-size PCM16 chunks from the local default/selected microphone."""

    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        channels: int = 1,
        block_samples: int = 512,
        device: str | int | None = None,
        queue_blocks: int = 64,
        clock=time.monotonic,
        backend: Any | None = None,
    ) -> None:
        if sample_rate <= 0 or channels <= 0 or block_samples <= 0:
            raise ValueError("sample_rate, channels, and block_samples must be positive")
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_samples = block_samples
        self.device = resolve_device(device)
        self.queue_blocks = max(4, int(queue_blocks))
        self.clock = clock
        self._backend = backend
        self.dropped_blocks = 0

    def chunks(self, *, stop_event: threading.Event | None = None, max_chunks: int | None = None) -> Iterator[AudioChunk]:
        if stop_event is not None and stop_event.is_set():
            return
        if self.device == 'desktop':
            yield from self._desktop_chunks(stop_event=stop_event, max_chunks=max_chunks)
            return
        sd = self._backend or _sounddevice()
        q: queue.Queue[tuple[bytes, float] | BaseException] = queue.Queue(maxsize=self.queue_blocks)

        def callback(indata, frames, time_info, status) -> None:  # sounddevice callback signature
            if status:
                # Status flags are not fatal; keep capture real-time and expose drop
                # count through the object rather than logging from PortAudio's thread.
                pass
            payload = bytes(indata)
            item = (payload, self.clock())
            try:
                q.put_nowait(item)
            except queue.Full:
                self.dropped_blocks += 1
                try:
                    q.get_nowait()  # drop oldest; recent audio matters most
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(item)
                except queue.Full:
                    self.dropped_blocks += 1

        try:
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_samples,
                device=self.device,
                channels=self.channels,
                dtype="int16",
                callback=callback,
            )
            with stream:
                emitted = 0
                while stop_event is None or not stop_event.is_set():
                    if max_chunks is not None and emitted >= max_chunks:
                        return
                    try:
                        item = q.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    if isinstance(item, BaseException):
                        raise MicrophoneError(str(item))
                    payload, captured_at = item
                    activity.microphone(payload)
                    emitted += 1
                    yield AudioChunk(payload, self.sample_rate, self.channels, captured_at)
        except SpeechDependencyError:
            raise
        except Exception as exc:  # pragma: no cover - depends on PortAudio/hardware
            raise MicrophoneError(f"unable to capture microphone audio: {exc}") from exc

    def _desktop_chunks(self, *, stop_event: threading.Event | None, max_chunks: int | None) -> Iterator[AudioChunk]:
        """Capture the current Windows default speaker through WASAPI loopback."""
        if self.channels != 1:
            raise MicrophoneError('desktop audio capture requires mono speech input')
        try:
            import numpy as np
            import soundcard as sc
        except ImportError as exc:
            raise SpeechDependencyError('desktop audio capture requires the soundcard speech dependency') from exc
        # The transcription worker can spend seconds decoding one utterance.
        # Keep reading WASAPI on its own thread and buffer recent audio, just
        # as sounddevice's callback does for a physical microphone.
        captured: queue.Queue[tuple[bytes, float] | BaseException] = queue.Queue(maxsize=max(256, self.queue_blocks))
        halt = threading.Event()

        def enqueue(item: tuple[bytes, float] | BaseException) -> None:
            try:
                captured.put_nowait(item)
            except queue.Full:
                self.dropped_blocks += 1
                try:
                    captured.get_nowait()
                except queue.Empty:
                    pass
                captured.put_nowait(item)

        def capture() -> None:
            # SoundCard's module initializer also calls CoInitializeEx. Import
            # it before the thread starts; initialize COM separately here.
            import os
            ole32 = None
            com_initialized = False
            try:
                if os.name == 'nt':
                    import ctypes
                    ole32 = ctypes.WinDLL('ole32')
                    ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_uint)
                    ole32.CoInitializeEx.restype = ctypes.c_long
                    result = ole32.CoInitializeEx(None, 0)
                    if result in (0, 1):
                        com_initialized = True
                    elif result != -2147417850:  # RPC_E_CHANGED_MODE
                        raise MicrophoneError(f'could not initialize Windows audio thread: 0x{result & 0xffffffff:08x}')
                speaker = sc.default_speaker()
                if speaker is None:
                    raise MicrophoneError('Windows has no default speaker to capture')
                loopback = sc.get_microphone(speaker.id, include_loopback=True)
                if loopback is None or not loopback.isloopback:
                    raise MicrophoneError('WASAPI loopback is unavailable for the default speaker')
                with loopback.recorder(samplerate=self.sample_rate, channels=[0, 1],
                                       blocksize=max(2048, self.block_samples * 4)) as recorder:
                    while not halt.is_set() and (stop_event is None or not stop_event.is_set()):
                        frames = recorder.record(numframes=self.block_samples)
                        mono = np.asarray(frames, dtype=np.float32).mean(axis=1)
                        payload = (np.clip(mono, -1.0, 1.0) * 32767).astype('<i2').tobytes()
                        enqueue((payload, self.clock()))
            except BaseException as exc:
                enqueue(exc)
            finally:
                if com_initialized:
                    ole32.CoUninitialize()

        worker = threading.Thread(target=capture, name='hanni-desktop-audio', daemon=True)
        worker.start()
        try:
            emitted = 0
            while stop_event is None or not stop_event.is_set():
                if max_chunks is not None and emitted >= max_chunks:
                    return
                try:
                    item = captured.get(timeout=0.25)
                except queue.Empty:
                    if not worker.is_alive():
                        raise MicrophoneError('desktop audio capture stopped unexpectedly')
                    continue
                if isinstance(item, BaseException):
                    if isinstance(item, MicrophoneError):
                        raise item
                    raise MicrophoneError(f'unable to capture desktop audio: {item}') from item
                payload, captured_at = item
                activity.microphone(payload)
                emitted += 1
                yield AudioChunk(payload, self.sample_rate, 1, captured_at)
        finally:
            halt.set()
            worker.join(timeout=2)
