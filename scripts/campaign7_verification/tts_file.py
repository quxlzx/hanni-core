"""Independent configured TTS file-only observation; never speaker fallback."""
from pathlib import Path
import hashlib
import json
import time
import wave

def run(destination):
    from hanni.config.loader import load_config
    from hanni.speech.australian import WindowsAustralianTts, australian_voice
    from hanni.speech.tts import TtsError
    root = Path(__file__).resolve().parents[2]
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    configs = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'config').glob('*.yaml')}
    config = load_config(root / 'config', data_dir=destination / 'isolated-state', env={})
    tts = config.hanni.speech.tts
    result = dict(scope='original configured WindowsAustralianTts with explicit owned output path', backend=tts.backend, configured_voice=tts.voice, native_au_token_available=bool(australian_voice()), physical_playbacks=0, actual_asr_calls=0, neural_model_loads=0, config_before=configs)
    engine = WindowsAustralianTts(tts, data_dir=destination / 'isolated-state')
    playback = None
    start = time.monotonic()
    try:
        playback = engine.start('A lilac receipt is ready for this isolated file test.', output=destination / 'native-au.wav')
        playback.wait(timeout=min(20, tts.timeout_seconds))
        with wave.open(str(destination / 'native-au.wav'), 'rb') as handle:
            result.update(frames=handle.getnframes(), sample_rate=handle.getframerate(), channels=handle.getnchannels(), sample_width=handle.getsampwidth())
        result.update(outcome='actual_native_file_synthesis', wav_sha256=hashlib.sha256((destination / 'native-au.wav').read_bytes()).hexdigest())
    except TtsError as exc:
        result.update(outcome='native_au_unavailable', error_type=type(exc).__name__, reason=str(exc))
    finally:
        if playback is not None:
            playback.stop()
    result['elapsed_seconds'] = time.monotonic() - start
    result['config_after'] = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'config').glob('*.yaml')}
    result['config_unchanged'] = result['config_after'] == configs
    (destination / 'RESULTS.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.out)))
