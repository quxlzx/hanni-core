"""Owner-selected local microphone and speech output routing."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .microphone import MicrophoneError, SpeechDependencyError, _sounddevice
from .tts import TtsError, _powershell_executable


FILENAME = 'audio-routing.json'


class AudioDeviceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class InputDevice:
    index: int
    name: str
    hostapi: str

    def to_dict(self):
        return {'id': str(self.index), 'name': self.name, 'hostapi': self.hostapi}


DESKTOP_INPUT = InputDevice(-1, 'Desktop audio (Windows default output)', 'Windows WASAPI loopback')


@dataclass(frozen=True, slots=True)
class OutputDevice:
    id: str
    name: str

    def to_dict(self):
        return {'id': self.id, 'name': self.name}


_OUTPUTS_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$voice = New-Object -ComObject SAPI.SpVoice
try {
    $tokens = $voice.GetAudioOutputs()
    $rows = @(
        for ($i = 0; $i -lt $tokens.Count; $i++) {
            $token = $tokens.Item($i)
            [PSCustomObject]@{ id = [string]$token.Id; name = [string]$token.GetDescription() }
        }
    )
    ConvertTo-Json -InputObject $rows -Compress
}
finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($voice) }
'''


def list_inputs() -> tuple[InputDevice, ...]:
    sd = _sounddevice()
    try:
        hosts = sd.query_hostapis()
        inputs = tuple(InputDevice(index, str(row['name']), str(hosts[row['hostapi']]['name']))
                     for index, row in enumerate(sd.query_devices())
                     if int(row.get('max_input_channels', 0)) > 0)
        try:
            import soundcard as sc
            speaker = sc.default_speaker()
            if speaker and sc.get_microphone(speaker.id, include_loopback=True):
                inputs += (DESKTOP_INPUT,)
        except (ImportError, RuntimeError, OSError):
            pass
        return inputs
    except Exception as exc:
        raise MicrophoneError(f'unable to enumerate microphone devices: {exc}') from exc


def list_outputs() -> tuple[OutputDevice, ...]:
    if os.name != 'nt':
        raise TtsError('Windows speech output selection is available on Windows only')
    executable = _powershell_executable()
    if not executable:
        raise TtsError('Windows PowerShell was not found')
    try:
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', _OUTPUTS_SCRIPT],
                                capture_output=True, text=True, encoding='utf-8', errors='replace',
                                timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TtsError(f'could not enumerate speech outputs: {type(exc).__name__}') from exc
    if result.returncode != 0:
        raise TtsError('could not enumerate Windows speech outputs')
    try:
        payload = json.loads(result.stdout.strip() or '[]')
    except json.JSONDecodeError as exc:
        raise TtsError('Windows returned an invalid speech output list') from exc
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise TtsError('Windows returned an invalid speech output list')
    return tuple(OutputDevice(row['id'], row['name']) for row in payload
                 if isinstance(row, dict) and isinstance(row.get('id'), str)
                 and isinstance(row.get('name'), str) and row['id'] and row['name'])


def routing_path(data_dir: Path) -> Path:
    return Path(data_dir) / FILENAME


def load_selection(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'input': None, 'output': None}
    except (OSError, ValueError) as exc:
        raise AudioDeviceError('Saved audio device selection is invalid; choose devices again') from exc
    if not isinstance(data, dict) or set(data) != {'input', 'output'}:
        raise AudioDeviceError('Saved audio device selection is invalid; choose devices again')
    for key, fields in (('input', {'index', 'name', 'hostapi'}), ('output', {'id', 'name'})):
        value = data[key]
        if value is not None and (not isinstance(value, dict) or set(value) != fields
                                  or any(not isinstance(part, str) or not part for name, part in value.items()
                                         if name != 'index')
                                  or key == 'input' and (type(value['index']) is not int or
                                      value['index'] < 0 and value != asdict(DESKTOP_INPUT))):
            raise AudioDeviceError('Saved audio device selection is invalid; choose devices again')
    return data


def save_selection(path: Path, *, input_id: str, output_id: str) -> dict:
    if not isinstance(input_id, str) or not isinstance(output_id, str):
        raise AudioDeviceError('Choose a detected microphone and speaker')
    inputs = list_inputs() if input_id != 'default' else ()
    outputs = list_outputs() if output_id != 'default' else ()
    selected_input = next((item for item in inputs if str(item.index) == input_id), None)
    selected_output = next((item for item in outputs if item.id == output_id), None)
    if input_id != 'default' and selected_input is None:
        raise AudioDeviceError('Selected microphone is no longer available')
    if output_id != 'default' and selected_output is None:
        raise AudioDeviceError('Selected speaker is no longer available')
    data = {'input': asdict(selected_input) if selected_input else None,
            'output': asdict(selected_output) if selected_output else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     prefix='.audio-routing-', suffix='.tmp', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def selected_input(data_dir: Path) -> int | str | None:
    saved = load_selection(routing_path(data_dir))['input']
    if saved is None:
        return None
    if saved == asdict(DESKTOP_INPUT):
        return 'desktop'
    matches = [item for item in list_inputs()
               if item.name == saved['name'] and item.hostapi == saved['hostapi']]
    exact = next((item for item in matches if item.index == saved['index']), None)
    selected = exact or (matches[0] if len(matches) == 1 else None)
    if selected is None:
        raise MicrophoneError('Selected microphone is unavailable; choose another in the dashboard')
    return selected.index


def selected_output(data_dir: Path) -> OutputDevice | None:
    saved = load_selection(routing_path(data_dir))['output']
    if saved is None:
        return None
    selected = next((item for item in list_outputs() if item.id == saved['id']), None)
    if selected is None:
        raise TtsError('Selected speaker is unavailable; choose another in the dashboard')
    return selected


def routing_state(data_dir: Path) -> dict:
    saved = load_selection(routing_path(data_dir))
    input_error = output_error = None
    try:
        inputs = list_inputs()
    except (MicrophoneError, SpeechDependencyError) as exc:
        inputs, input_error = (), str(exc)
    try:
        outputs = list_outputs()
    except TtsError as exc:
        outputs, output_error = (), str(exc)
    input_id = 'default'
    if saved['input']:
        matches = [item for item in inputs if item.name == saved['input']['name']
                   and item.hostapi == saved['input']['hostapi']]
        current = next((item for item in matches if item.index == saved['input']['index']), None)
        current = current or (matches[0] if len(matches) == 1 else None)
        input_id = str(current.index if current else saved['input']['index'])
        if current is None:
            input_error = input_error or 'Saved microphone is not currently detected'
    output_id = saved['output']['id'] if saved['output'] else 'default'
    if saved['output'] and not any(item.id == output_id for item in outputs):
        output_error = output_error or 'Saved speaker is not currently detected'
    return {'inputs': [item.to_dict() for item in inputs],
            'outputs': [item.to_dict() for item in outputs],
            'input_id': input_id, 'output_id': output_id,
            'input_error': input_error, 'output_error': output_error}
