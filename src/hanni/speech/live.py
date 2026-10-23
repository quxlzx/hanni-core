"""Background transcript pump for full-duplex-ish local voice interaction."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class PumpFailure:
    error: BaseException

class PumpFinished:
    pass

PUMP_FINISHED = PumpFinished()

class TranscriptPump:
    """Run an STT pipeline continuously in a worker thread.

    Keeping capture/transcription off the main interaction loop lets H.A.N.N.I.
    continue hearing the owner while local TTS is speaking.
    """
    def __init__(self, pipeline: Any, *, queue_size: int = 32) -> None:
        self.pipeline = pipeline
        self.stop_event = threading.Event()
        self.queue: queue.Queue[Any] = queue.Queue(maxsize=max(4, queue_size))
        self.thread: threading.Thread | None = None
        self.failed = False
        self._start_lock = threading.Lock()

    def start(self) -> None:
        with self._start_lock:
            if self.thread and self.thread.is_alive():
                return
            # A completed cycle must not replay transcripts or its terminal.
            while True:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            self.failed = False
            self.thread = threading.Thread(target=self._run, name="hanni-stt-pump", daemon=True)
            self.thread.start()

    def _run(self) -> None:
        try:
            if self.stop_event.is_set():
                return
            try:
                iterator = self.pipeline.run(stop_event=self.stop_event)
            except TypeError:
                # Test doubles / older diagnostic pipelines may not expose the
                # stop_event argument. Production SpeechToTextPipeline does.
                iterator = self.pipeline.run()
            for record in iterator:
                if self.stop_event.is_set():
                    break
                self._put(record)
        except BaseException as exc:  # forwarded to the main thread
            self.failed = True
            self._put(PumpFailure(exc))
        finally:
            self._put(PUMP_FINISHED)

    def _put(self, item: Any) -> None:
        try:
            self.queue.put(item, timeout=0.25)
        except queue.Full:
            try:
                self.queue.get_nowait()  # favor newest conversational speech
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(item)
            except queue.Full:
                pass

    def get(self, timeout: float | None = None) -> Any:
        return self.queue.get(timeout=timeout)

    def get_nowait(self) -> Any:
        return self.queue.get_nowait()

    def stop(self, *, join_timeout: float = 1.0) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=join_timeout)
