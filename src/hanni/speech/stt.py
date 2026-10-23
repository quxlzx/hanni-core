"""Local faster-whisper speech-to-text adapter."""

from __future__ import annotations

from typing import Any

from hanni.speech.microphone import SpeechDependencyError
from hanni.speech.types import Transcription
from hanni.speech.vad import Utterance


class SttError(RuntimeError):
    """Raised when local transcription fails."""


class FasterWhisperTranscriber:
    """Lazily load and run a local faster-whisper model.

    Milestone 2 defaults to CPU int8 so the 8 GB RTX 5060 can remain available
    for the Qwen Supervisor.  The device and compute type are configuration,
    not assumptions in the rest of the speech pipeline.
    """

    def __init__(
        self,
        *,
        model_name: str = "small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = "en",
        beam_size: int = 1,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._model = model

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SpeechDependencyError(
                'faster-whisper is not installed; run `.\\scripts\\setup_speech.ps1`'
            ) from exc
        try:
            self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        except Exception as exc:  # pragma: no cover - model/runtime dependent
            raise SttError(f"unable to load faster-whisper model {self.model_name!r}: {exc}") from exc
        return self._model

    def prepare(self):
        """Load configured STT before the voice session announces readiness."""
        self._load()

    def transcribe(self, utterance: Utterance) -> Transcription:
        if utterance.channels != 1:
            raise ValueError("STT expects mono audio")
        if utterance.sample_rate != 16_000:
            raise ValueError("STT expects 16000 Hz audio")
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SpeechDependencyError("numpy is required for faster-whisper") from exc
        audio = np.frombuffer(utterance.pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        # Whisper may hallucinate text for digital silence (for example "You").
        # Empty/all-zero input contains no speech evidence. Do not apply an RMS
        # threshold: even one nonzero low-amplitude sample retains normal STT.
        if audio.size == 0 or not np.any(audio):
            return Transcription(text="", language=self.language)
        try:
            segments, info = self._load().transcribe(
                audio,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            text = " ".join(str(segment.text).strip() for segment in segments if str(segment.text).strip()).strip()
        except Exception as exc:
            raise SttError(f"local transcription failed: {exc}") from exc
        language = getattr(info, "language", self.language)
        probability = getattr(info, "language_probability", None)
        return Transcription(text=text, language=language, language_probability=probability)
