"""Prospective development references and actual Windows speech-to-file corpus.

Reference text is authored before synthesis or recognition. These synthetic
files are not recordings of the owner or proof of acoustic microphone behavior.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import wave
from array import array
PHRASES = {'direct_wake': ['Hanni, what time is it?', 'Hanni, tell me the current processor load.', 'Hanni, read my next calendar appointment.', 'Hanni, describe the weather forecast.', 'Hanni, help me find my project folder.', 'Hanni, make a short shopping checklist.', 'Hanni, explain what virtual memory means.', 'Hanni, summarize this paragraph for me.', 'Hanni, which cluster nodes are available?', 'Hanni, please repeat your last answer.'], 'wake_position': ['Can you show available memory, Hanni?', 'Before lunch, Hanni, remind me to drink water.', 'Um, Hanni, could you open the settings page?', 'I need a little help, Hanni, with this calculation.', 'Please explain the error message to me, Hanni.', 'When you have a moment, Hanni, check the battery.', 'Are you still listening, Hanni?', 'Okay, Hanni, let us start a new conversation.', 'The question I have, Hanni, is about disk space.', 'Could you make that answer shorter, Hanni, please?'], 'idle_background': ['The library closes earlier on Saturdays.', 'I think the blue notebook is in the kitchen.', 'That train usually arrives at the second platform.', 'We watched a documentary about coastal birds.', 'There are fresh strawberries in the refrigerator.', 'The neighbor planted three trees last spring.', 'My jacket needs a new button on its sleeve.', 'The concert tickets arrived in the mail today.', 'A cloud passed over the mountains this morning.', 'We should leave the umbrella near the front door.'], 'near_wake': ['Hannah bought a new bicycle yesterday.', 'The history lesson mentioned Hannibal crossing the Alps.', 'This tool has a handy keyboard shortcut.', 'The Hanning window changes the spectral estimate.', 'There is an annual festival by the river.', 'The mechanic inspected the handbrake cable.', 'A handwritten receipt was inside the package.', 'The hallway light stayed on all evening.', 'A tiny animal crossed the garden path.', 'The new handbook explains the safety procedure.'], 'engaged_follow_up': ['Can you give me one concrete example?', 'What does the second number represent?', 'Please explain the difference more slowly.', 'Now sort those results by response time.', 'Which option would use less memory?', 'Can you repeat just the final sentence?', 'I meant the other project in that folder.', 'Tell me why that check failed.', 'Could you save the summary after I review it?', 'How would that change if the node were offline?'], 'filler': ['Um.', 'Uh.', 'Hmm.', 'Erm.', 'Ah.', 'Um, uh.', 'Hmm, mm.', 'Er, um.', 'Uh, ah.', 'Mm, hmm, um.'], 'disengage': ['That is all.', 'We are done.', 'Go quiet.', 'Stop responding.', 'Stand by.', 'Never mind.', 'That will be all.', 'You can go quiet.', 'Thanks Hanni, that is all.', 'Never mind Hanni.'], 'passive_acknowledgement': ['Thanks.', 'Thank you.', 'Yeah.', 'Yep.', 'Okay.', 'OK.', 'Alright.', 'Got it.', 'Cool.', 'Thank you!'], 'playback_interrupt': ['Stop.', 'Wait.', 'Hold on.', 'Quiet.', 'Cancel.', 'No.', 'No wait.', 'Hanni stop.', 'Honey stop.', 'Ani stop.'], 'playback_echo': ['The forecast includes light rain this afternoon.', 'Your processor usage is thirty six percent.', 'The next appointment begins at half past nine.', 'I found two matching folders in the workspace.', 'The report contains a summary and three observations.', 'Available memory is measured in bytes.', 'The offline node has no current telemetry.', 'Your local settings are stored on this computer.', 'A restart can interrupt currently running work.', 'The search returned one verified source file.']}

def references():
    """Return authored expected behavior, independent of any production output."""
    rows = []
    conditions = ['clean', 'noise_24db', 'noise_12db', 'low_amplitude', 'internal_pause']
    for category, phrases in PHRASES.items():
        for index, phrase in enumerate(phrases):
            sample_id = f'c7-dev-{category}-{index + 1:02d}'
            playing = category.startswith('playback_')
            engaged = category in {'engaged_follow_up', 'filler', 'disengage', 'passive_acknowledgement'}
            wake = category in {'direct_wake', 'wake_position'} or (category == 'disengage' and 'Hanni' in phrase)
            relevant = category in {'direct_wake', 'wake_position', 'engaged_follow_up'}
            rows.append({'id': sample_id, 'category': category, 'transcript': phrase, 'state_before': 'playing' if playing else 'engaged' if engaged else 'idle', 'wake_expected': None if playing else wake, 'relevance_expected': None if playing else relevant, 'disengaged_expected': category == 'disengage', 'barge_expected': category == 'playback_interrupt' if playing else None, 'barge_routes_after_interrupt': False if playing else None, 'spoken_text': phrase if category == 'playback_echo' else '', 'condition': conditions[index % len(conditions)], 'sapi_rate': [-1, 0, 1, 2][index % 4], 'seed': 71000 + len(rows)})
    return rows

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def author(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'references.json'
    if path.exists():
        raise FileExistsError('Prospective reference artifact already exists; preserve its bytes.')
    rows = references()
    assert len(rows) >= 100 and len({r['id'] for r in rows}) == len(rows)
    payload = {'schema_version': 1, 'scope': 'Synthetic development speech references; prospectively authored before audio decoding; not owner recordings.', 'classification_config': 'Original configured wake/relevance policy, with Hanni explicit in wake-positive development cases.', 'samples': rows}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'references': path.as_posix(), 'sha256': sha(path), 'sample_count': len(rows), 'categories': dict(Counter((r['category'] for r in rows)))}))
SYNTHESIZE_SCRIPT = '\n$ErrorActionPreference = \'Stop\'\n[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false\n[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\nAdd-Type -AssemblyName System.Speech\n$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json\n$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\ntry {\n    $voices = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like \'en-*\' } | ForEach-Object { $_.VoiceInfo.Name })\n    if ($voices.Count -eq 0) { throw \'No installed English synthesis voice is available.\' }\n    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo -ArgumentList 16000,([System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen),([System.Speech.AudioFormat.AudioChannel]::Mono)\n    $rows = @()\n    foreach ($sample in $payload.samples) {\n        $voiceName = $voices[$rows.Count % $voices.Count]\n        $synth.SelectVoice([string]$voiceName)\n        $synth.Rate = [int]$sample.sapi_rate\n        $synth.Volume = 100\n        $synth.SetOutputToWaveFile([string]$sample.path, $format)\n        if ($sample.condition -eq \'internal_pause\') {\n            $words = @(([string]$sample.transcript).Split(\' \'))\n            $midpoint = [Math]::Max(1, [int][Math]::Floor($words.Count / 2))\n            $left = [Security.SecurityElement]::Escape(($words[0..($midpoint - 1)] -join \' \'))\n            $right = if ($midpoint -lt $words.Count) { [Security.SecurityElement]::Escape(($words[$midpoint..($words.Count - 1)] -join \' \')) } else { \'\' }\n            $synth.SpeakSsml(\'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">\' + $left + \'<break time="650ms"/>\' + $right + \'</speak>\')\n        } else { $synth.Speak([string]$sample.transcript) }\n        $synth.SetOutputToNull()\n        $rows += [PSCustomObject]@{id=[string]$sample.id;voice=[string]$voiceName;path=[string]$sample.path}\n    }\n    ConvertTo-Json -InputObject $rows -Compress\n} finally { $synth.Dispose() }\n'

def synthesize(root):
    root = Path(root).resolve()
    refs_path = root / 'references.json'
    refs = json.loads(refs_path.read_text(encoding='utf8'))
    output = root / 'wav'
    output.mkdir(exist_ok=True)
    if any(output.glob('*.wav')):
        raise FileExistsError('Existing development WAVs must not be silently replaced.')
    executable = shutil.which('powershell.exe')
    if not executable:
        raise RuntimeError('Windows PowerShell is unavailable for local synthesis.')
    samples = [{**r, 'path': str(output / (r['id'] + '.wav'))} for r in refs['samples']]
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', SYNTHESIZE_SCRIPT], input=json.dumps({'samples': samples}), capture_output=True, text=True, encoding='utf8', timeout=180, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Local file synthesis failed: ' + result.stderr.strip()[:2000])
    observed = {r['id']: r for r in json.loads(result.stdout)}
    metadata = []
    for row in refs['samples']:
        path = output / (row['id'] + '.wav')
        original_hash = sha(path)
        with wave.open(str(path), 'rb') as handle:
            assert handle.getnchannels() == 1 and handle.getframerate() == 16000 and (handle.getsampwidth() == 2)
            values = array('h', handle.readframes(handle.getnframes()))
        rms = (sum((x * x for x in values)) / max(1, len(values))) ** 0.5
        rng = random.Random(row['seed'])
        if row['condition'].startswith('noise_'):
            snr = int(row['condition'].split('_')[1].removesuffix('db'))
            sigma = rms / 10 ** (snr / 20)
            values = array('h', (max(-32768, min(32767, round(x + rng.gauss(0, sigma)))) for x in values))
        elif row['condition'] == 'low_amplitude':
            values = array('h', (round(x * 0.08) for x in values))
        padding = array('h', [0]) * 8000
        values = padding + values + padding
        with wave.open(str(path), 'wb') as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(values.tobytes())
        metadata.append({'id': row['id'], 'category': row['category'], 'condition': row['condition'], 'wav_path': path.relative_to(root).as_posix(), 'sha256': sha(path), 'synthesis_sha256_before_condition': original_hash, 'sample_rate': 16000, 'channels': 1, 'sample_width': 2, 'frames': len(values), 'seconds': len(values) / 16000, 'voice': observed[row['id']]['voice'], 'sapi_rate': row['sapi_rate'], 'seed': row['seed'], 'pcm_peak': max((abs(x) for x in values)), 'pcm_rms': (sum((x * x for x in values)) / max(1, len(values))) ** 0.5})
    manifest = {'schema_version': 1, 'scope': 'Actual local Windows System.Speech synthesis to files with controlled postprocessing. No microphone, desktop capture, acoustic playback or STT calls.', 'references_sha256': sha(refs_path), 'sample_count': len(metadata), 'samples': metadata}
    path = root / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'manifest': path.as_posix(), 'sha256': sha(path), 'sample_count': len(metadata), 'seconds': sum((r['seconds'] for r in metadata)), 'voices': sorted({r['voice'] for r in metadata}), 'categories': dict(Counter((r['category'] for r in metadata))), 'conditions': dict(Counter((r['condition'] for r in metadata)))}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['author', 'synthesize'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    (author if args.mode == 'author' else synthesize)(args.output)
if __name__ == '__main__':
    main()
