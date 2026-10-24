"""Shared local speech interfaces, Windows SAPI fallback and backend selection.

Optional neural synthesis lives in a cancellable worker; the assistant's voice
attention, interruption and foreground/background arbitration use this interface.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import psutil
from dataclasses import dataclass
from typing import Protocol, Sequence
from hanni.core.activity import activity
from hanni.core.interaction import interaction


class TtsError(RuntimeError):
    """Raised when local speech synthesis cannot be completed."""


@dataclass(frozen=True, slots=True)
class TtsVoice:
    name: str
    culture: str = ""
    gender: str = ""
    age: str = ""

    def render(self) -> str:
        details = ", ".join(value for value in (self.culture, self.gender, self.age) if value)
        return f"{self.name}{f' ({details})' if details else ''}"


class TtsPlayback(Protocol):
    @property
    def active(self) -> bool: ...
    def stop(self) -> None: ...
    def wait(self, timeout: float | None = None) -> None: ...


class TtsEngine(Protocol):
    def speak(self, text: str) -> None: ...
    def start(self, text: str) -> TtsPlayback: ...


class CompletedPlayback:
    """No-op playback used for empty text."""
    @property
    def active(self) -> bool:
        return False
    def stop(self) -> None:
        return None
    def wait(self, timeout: float | None = None) -> None:
        return None


class SubprocessTtsPlayback:
    """Cancellable local TTS process used by Milestone 5 barge-in."""
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.process = process
        self._stopped = False
        self._stop_lock = threading.RLock()
        self._identity = None
        if type(getattr(process, 'pid', None)) is int:
            try:
                self._identity = psutil.Process(process.pid).create_time()
            except psutil.Error:
                pass
        activity.playback(process)
        with interaction.condition:
            interaction.playback = self

    @property
    def active(self) -> bool:
        return self.process.poll() is None

    @property
    def cancelled(self) -> bool:
        return self._stopped

    def _owned_children(self):
        # Windows venv python.exe redirects to another Python process. Killing
        # only the redirector leaves synthesis/playback and its device running.
        # Bind cleanup to the Popen identity; never find workers by process name.
        if self._identity is None:
            return []
        try:
            parent = psutil.Process(self.process.pid)
            if parent.create_time() != self._identity:
                return []
            return parent.children(recursive=True)
        except psutil.Error:
            return []

    def stop(self) -> None:
        with self._stop_lock:
            self._stopped = True
            children = self._owned_children()
            for child in reversed(children):
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
                except psutil.Error as exc:
                    raise TtsError('Could not stop an owned speech worker') from exc
            try:
                if self.active:
                    self.process.terminate()
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    self.process.wait(timeout=1.0)
                except (subprocess.TimeoutExpired, OSError) as exc:
                    raise TtsError('Could not stop the local speech process') from exc
            except OSError as exc:
                if self.active:
                    raise TtsError('Could not stop the local speech process') from exc
            if children:
                _, remaining = psutil.wait_procs(children, timeout=1.0)
                for child in remaining:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.Error as exc:
                        raise TtsError('Could not stop an owned speech worker') from exc
                _, remaining = psutil.wait_procs(remaining, timeout=1.0)
                if remaining:
                    raise TtsError('An owned speech worker is still stopping')

    def wait(self, timeout: float | None = None) -> None:
        try:
            code = self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self.stop()
            raise TtsError("local TTS timed out") from exc
        if code != 0 and not self._stopped:
            detail = ""
            if self.process.stderr is not None:
                try:
                    detail = self.process.stderr.read().strip()
                except Exception:
                    detail = ""
            raise TtsError(f"local TTS failed: {detail or f'exit code {code}'}")


# PowerShell receives JSON over stdin rather than interpolating user/model text
# into a command line. This avoids quoting/injection problems and preserves
# arbitrary punctuation safely (json.dumps defaults to ASCII escapes).
_SPEAK_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$raw = [Console]::In.ReadToEnd()
$payload = $raw | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.Rate = [int]$payload.rate
    $synth.Volume = [int]$payload.volume
    if ($payload.voice -and $payload.voice -ne 'default') {
        $synth.SelectVoice([string]$payload.voice)
    }
    foreach ($chunk in $payload.chunks) {
        if (-not [string]::IsNullOrWhiteSpace([string]$chunk)) {
            $synth.Speak([string]$chunk)
        }
    }
}
finally {
    $synth.Dispose()
}
"""

_SPEAK_SELECTED_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$voice = New-Object -ComObject SAPI.SpVoice
try {
    $selected = $null
    $outputs = $voice.GetAudioOutputs()
    for ($i = 0; $i -lt $outputs.Count; $i++) {
        $candidate = $outputs.Item($i)
        if ($candidate.Id -eq [string]$payload.output_token) { $selected = $candidate; break }
    }
    if (-not $selected) { throw 'Selected speaker is unavailable' }
    $voice.AudioOutput = $selected
    if ($payload.voice -and $payload.voice -ne 'default') {
        $found = $null
        $voices = $voice.GetVoices()
        for ($i = 0; $i -lt $voices.Count; $i++) {
            $candidate = $voices.Item($i)
            if ($candidate.GetDescription() -eq [string]$payload.voice) { $found = $candidate; break }
        }
        if (-not $found) { throw 'Selected voice is unavailable' }
        $voice.Voice = $found
    }
    $voice.Rate = [int]$payload.rate
    $voice.Volume = [int]$payload.volume
    foreach ($chunk in $payload.chunks) {
        if (-not [string]::IsNullOrWhiteSpace([string]$chunk)) {
            [void]$voice.Speak([string]$chunk, 16)
        }
    }
}
finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($voice) }
"""

_LIST_VOICES_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $items = @($synth.GetInstalledVoices() | ForEach-Object {
        $v = $_.VoiceInfo
        [PSCustomObject]@{
            name = [string]$v.Name
            culture = [string]$v.Culture.Name
            gender = [string]$v.Gender
            age = [string]$v.Age
        }
    })
    @($items) | ConvertTo-Json -Compress
}
finally {
    $synth.Dispose()
}
"""


def _powershell_executable() -> str | None:
    """Return Windows PowerShell, preferring the built-in 5.1 host.

    System.Speech is reliably available in Windows PowerShell. ``pwsh`` is used
    only as a fallback for unusual installations.
    """
    for candidate in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def split_for_speech(text: str, *, max_chars: int = 260) -> tuple[str, ...]:
    """Split assistant prose into natural bounded chunks for synthesis."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return ()
    if max_chars < 40:
        raise ValueError("max_chars must be >= 40")

    # Prefer sentence boundaries, then punctuation, then whitespace. The chunks
    # are processed in one synthesizer process, so this is not a process-per-
    # sentence design and does not add large startup pauses between sentences.
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    result: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            candidate = sentence if not current else f"{current} {sentence}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                result.append(current)
            current = sentence
            continue

        if current:
            result.append(current)
            current = ""
        remaining = sentence
        while len(remaining) > max_chars:
            cut = max(
                remaining.rfind(", ", 0, max_chars + 1),
                remaining.rfind("; ", 0, max_chars + 1),
                remaining.rfind(" ", 0, max_chars + 1),
            )
            if cut < max_chars // 2:
                cut = max_chars
            piece = remaining[:cut].strip(" ,;")
            if piece:
                result.append(piece)
            remaining = remaining[cut:].lstrip(" ,;")
        if remaining:
            current = remaining
    if current:
        result.append(current)
    return tuple(result)


class WindowsSapiTts:
    """Local Windows System.Speech TTS backend."""

    def __init__(
        self,
        *,
        voice: str = "default",
        rate: int = 0,
        volume: int = 100,
        chunk_chars: int = 260,
        timeout_seconds: int = 120,
        powershell: str | None = None,
        output_device=None,
    ) -> None:
        if not -10 <= rate <= 10:
            raise ValueError("rate must be between -10 and 10")
        if not 0 <= volume <= 100:
            raise ValueError("volume must be between 0 and 100")
        if chunk_chars < 40:
            raise ValueError("chunk_chars must be >= 40")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1")
        self.voice = voice.strip() or "default"
        self.rate = int(rate)
        self.volume = int(volume)
        self.chunk_chars = int(chunk_chars)
        self.timeout_seconds = int(timeout_seconds)
        self.powershell = powershell or _powershell_executable()
        self.output_device = output_device

    @property
    def available(self) -> bool:
        return bool(self.powershell and os.name == "nt")

    def start(self, text: str) -> TtsPlayback:
        from hanni.core.interaction import interaction
        if interaction.speech_muted:
            return CompletedPlayback()
        chunks = split_for_speech(text, max_chars=self.chunk_chars)
        if not chunks:
            return CompletedPlayback()
        if not self.powershell:
            raise TtsError("Windows PowerShell was not found; local Windows SAPI TTS is unavailable")
        if os.name != "nt":
            raise TtsError("windows_sapi TTS is only available on Windows")

        payload = json.dumps({
            "voice": self.voice, "rate": self.rate, "volume": self.volume,
            "output_token": self.output_device.id if self.output_device else None,
            "chunks": list(chunks),
        })
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.Popen(
                [self.powershell, "-NoProfile", "-NonInteractive", "-Command",
                 _SPEAK_SELECTED_SCRIPT if self.output_device else _SPEAK_SCRIPT],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, creationflags=creationflags,
            )
            assert proc.stdin is not None
            proc.stdin.write(payload)
            proc.stdin.close()
        except OSError as exc:
            raise TtsError(f"local TTS process failed: {exc}") from exc
        return SubprocessTtsPlayback(proc)

    def speak(self, text: str) -> None:
        from hanni.core.interaction import interaction
        if interaction.speech_muted:
            return
        chunks = split_for_speech(text, max_chars=self.chunk_chars)
        if not chunks:
            return
        if not self.powershell:
            raise TtsError("Windows PowerShell was not found; local Windows SAPI TTS is unavailable")
        if os.name != "nt":
            raise TtsError("windows_sapi TTS is only available on Windows")
        payload = json.dumps({
            "voice": self.voice, "rate": self.rate, "volume": self.volume,
            "output_token": self.output_device.id if self.output_device else None,
            "chunks": list(chunks),
        })
        try:
            with activity.speaking(), interaction.synthesis():
                result = subprocess.run(
                    [self.powershell, "-NoProfile", "-NonInteractive", "-Command",
                     _SPEAK_SELECTED_SCRIPT if self.output_device else _SPEAK_SCRIPT],
                    input=payload, text=True, capture_output=True,
                    timeout=self.timeout_seconds, check=False,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TtsError(f"local TTS process failed: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown PowerShell/System.Speech error").strip()
            raise TtsError(f"local TTS failed: {detail}")


def list_windows_voices(*, powershell: str | None = None, timeout_seconds: int = 15) -> tuple[TtsVoice, ...]:
    executable = powershell or _powershell_executable()
    if not executable:
        raise TtsError("Windows PowerShell was not found")
    if os.name != "nt":
        raise TtsError("Windows SAPI voice enumeration is only available on Windows")
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", _LIST_VOICES_SCRIPT],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TtsError(f"could not enumerate local voices: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown PowerShell/System.Speech error").strip()
        raise TtsError(f"could not enumerate local voices: {detail}")
    raw = result.stdout.strip()
    if not raw:
        return ()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TtsError(f"could not parse Windows voice list: {exc}") from exc
    if isinstance(data, dict):
        data = [data]
    return tuple(
        TtsVoice(
            name=str(item.get("name", "")),
            culture=str(item.get("culture", "")),
            gender=str(item.get("gender", "")),
            age=str(item.get("age", "")),
        )
        for item in data
        if isinstance(item, dict) and item.get("name")
    )


def create_tts(config, *, data_dir=None) -> TtsEngine:
    """Create a local backend; optional neural dependencies are loaded lazily."""
    output_device = None
    if data_dir is not None:
        from .audio_devices import selected_output
        output_device = selected_output(data_dir)
    if config.backend == "windows_australian":
        from .australian import WindowsAustralianTts
        return WindowsAustralianTts(config, data_dir=data_dir, output_device=output_device)
    if config.backend == "kokoro":
        from .neural import KokoroTts
        return KokoroTts(config, data_dir=data_dir, output_device=output_device)
    if config.backend != "windows_sapi":
        raise TtsError(f"unsupported TTS backend: {config.backend}")
    return WindowsSapiTts(
        voice=config.voice,
        rate=config.rate,
        volume=config.volume,
        chunk_chars=config.chunk_chars,
        timeout_seconds=config.timeout_seconds,
        output_device=output_device,
    )
