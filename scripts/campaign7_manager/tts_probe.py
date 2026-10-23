"""Configured native TTS file probe: never selects speakers or loads neural TTS."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import time
import wave
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

def run():
    from hanni.config.loader import load_config
    from hanni.speech.australian import WindowsAustralianTts, australian_voice
    from hanni.speech.tts import TtsError
    out = ROOT / 'data/campaign7-manager/configured-tts-file'
    out.mkdir(parents=True, exist_ok=False)
    config = load_config(ROOT / 'config', data_dir=out / 'isolated-state', env={})
    speech = config.hanni.speech.tts
    result = {'backend': speech.backend, 'configured_voice': speech.voice, 'installed_australian_token': bool(australian_voice()), 'scope': 'configured WindowsAustralianTts native file mode only', 'speaker_playbacks': 0, 'neural_model_loads': 0, 'physical_speaker_verified': False, 'neural_or_SAPI_fallback_playback_tested': False}
    if speech.backend != 'windows_australian':
        result['outcome'] = 'NOT_APPLICABLE'
    else:
        engine = WindowsAustralianTts(speech, data_dir=out / 'isolated-state')
        playback = None
        started = time.monotonic()
        try:
            playback = engine.start('Hanni validation. This speech is saved to a disposable file.', output=out / 'configured-voice.wav')
            playback.wait(timeout=min(20, speech.timeout_seconds))
            with wave.open(str(out / 'configured-voice.wav'), 'rb') as audio:
                result.update(channels=audio.getnchannels(), sample_rate=audio.getframerate(), frames=audio.getnframes(), sample_width=audio.getsampwidth())
            result['sha256'] = hashlib.sha256((out / 'configured-voice.wav').read_bytes()).hexdigest()
            result['outcome'] = 'ACTUAL_NATIVE_FILE_SYNTHESIS'
        except TtsError as exc:
            result.update(outcome='NATIVE_AU_VOICE_UNAVAILABLE', error_class=type(exc).__name__, reason=str(exc))
        finally:
            if playback is not None:
                playback.stop()
        result['elapsed_seconds'] = time.monotonic() - started
    (out / 'RESULTS.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(result))
if __name__ == '__main__':
    run()
