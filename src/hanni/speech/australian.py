"""Offline Australian Windows voice, using installed tokens without registry edits."""
from __future__ import annotations

from dataclasses import replace
import json
import logging
import os
import subprocess

from .neural import KokoroTts, NeuralPlayback
from .tts import CompletedPlayback, TtsError, _powershell_executable, split_for_speech


def australian_voice():
    """Find a female en-AU voice (LCID 0x0c09); never select a foreign accent."""
    if os.name != "nt":
        return None
    import winreg
    candidates = []
    for root in (r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens",
                 r"SOFTWARE\Microsoft\Speech\Voices\Tokens"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as voices:
                for index in range(winreg.QueryInfoKey(voices)[0]):
                    name = winreg.EnumKey(voices, index)
                    try:
                        with winreg.OpenKey(voices, name + r"\Attributes") as attributes:
                            languages = winreg.QueryValueEx(attributes, "Language")[0]
                            gender = winreg.QueryValueEx(attributes, "Gender")[0]
                            if gender.lower() == "female" and any(int(code, 16) == 0xC09 for code in languages.split(";")):
                                candidates.append("HKEY_LOCAL_MACHINE\\" + root + "\\" + name)
                    except (OSError, ValueError):
                        continue
        except OSError:
            continue
    return next((p for p in candidates if "catherine" in p.lower()), candidates[0] if candidates else None)


# XML is constructed from escaped plain text, never interpreted from the model.
# Use SAPI's native pitch tag and its XML parser (SPF_IS_XML | SPF_PARSE_SAPI).
_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$voice = New-Object -ComObject SAPI.SpVoice
$token = New-Object -ComObject SAPI.SpObjectToken
$stream = $null
try {
    $token.SetId([string]$payload.token)
    $voice.Voice = $token
    $voice.Volume = [int]$payload.volume
    $voice.Rate = [int]$payload.rate
    if ($payload.output_token -and -not $payload.output) {
        $selected = $null
        $outputs = $voice.GetAudioOutputs()
        for ($i = 0; $i -lt $outputs.Count; $i++) {
            $candidate = $outputs.Item($i)
            if ($candidate.Id -eq [string]$payload.output_token) { $selected = $candidate; break }
        }
        if (-not $selected) { throw 'Selected speaker is unavailable' }
        $voice.AudioOutput = $selected
    }
    if ($payload.output) {
        $stream = New-Object -ComObject SAPI.SpFileStream
        $stream.Open([string]$payload.output, 3, $false)
        $voice.AudioOutputStream = $stream
    }
    foreach ($chunk in $payload.chunks) {
        $escaped = [System.Security.SecurityElement]::Escape([string]$chunk)
        $xml = '<pitch absmiddle="' + [string]$payload.pitch + '">' + $escaped + '</pitch>'
        [void]$voice.Speak($xml, 136)
    }
}
finally {
    if ($stream) { $stream.Close(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($stream) }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($voice)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($token)
}
'''


class WindowsAustralianTts:
    def __init__(self, config, *, data_dir=None, output_device=None):
        self.config = config
        self.output_device = output_device
        self.fallback = KokoroTts(replace(config, backend="kokoro", voice="hanni", language="en-gb"),
                                  data_dir=data_dir, output_device=output_device)
        self._warned = False

    def start(self, text, *, output=None):
        chunks = split_for_speech(text, max_chars=self.config.chunk_chars)
        if not chunks:
            return CompletedPlayback()
        token = australian_voice()
        if token is None:
            if output is not None or not self.config.sapi_fallback:
                raise TtsError("Install English (Australia) under Windows Settings > Time & language > Speech > Add voices")
            if not self._warned:
                logging.getLogger(__name__).warning(
                    "Australian voice pack is missing; using higher-pitched British HANNI for now. "
                    "Install English (Australia) in Windows Speech settings.")
                self._warned = True
            return self.fallback.start(text)
        executable = _powershell_executable()
        if not executable:
            raise TtsError("Windows PowerShell is unavailable")
        payload = dict(token=token, chunks=chunks, volume=self.config.volume,
                       rate=self.config.rate, pitch=round(self.config.pitch_semitones),
                       output=str(output) if output else None,
                       output_token=self.output_device.id if self.output_device else None)
        process = None
        try:
            process = subprocess.Popen([executable, "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
                                       stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            process.stdin.write(json.dumps(payload))
            process.stdin.close()
        except OSError as exc:
            if process is not None:
                process.kill()
                process.wait()
            raise TtsError("Could not start Australian voice playback") from exc
        return NeuralPlayback(process, self.config.timeout_seconds)

    def speak(self, text):
        from hanni.core.interaction import interaction
        with interaction.synthesis():
            playback = self.start(text)
            try:
                playback.wait(self.config.timeout_seconds)
            finally:
                playback.stop()
