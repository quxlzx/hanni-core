"""Install verified local voice assets and generate a synthetic preview.

Only this explicit setup command downloads models. Normal speech is offline.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import time
import urllib.request
import wave

from dotenv import load_dotenv
from hanni.config.loader import load_config
from hanni.speech.neural import KokoroTts
from hanni.speech.neural_worker import render_chunks

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
ASSETS = {
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}
PREVIEW = "Hi, I'm Hanni. I'm here and ready when you are. What would you like to do today?"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_assets(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in ASSETS.items():
        target = directory / name
        if target.is_file() and digest(target) == expected:
            print(f"Verified {name}", flush=True)
            continue
        # Never replace a working file with an incomplete download.
        partial = target.with_suffix(target.suffix + ".download")
        print(f"Downloading {name} ...", flush=True)
        try:
            with urllib.request.urlopen(RELEASE + name, timeout=60) as response, partial.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            if digest(partial) != expected:
                raise ValueError(f"SHA-256 mismatch for {name}; download rejected")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--play", action="store_true", help="also play the generated preview")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    config = load_config(root / "config")
    settings = config.hanni.speech.tts
    engine = KokoroTts(settings, data_dir=config.paths.data_dir)
    output = engine.directory / "hanni-preview.wav"
    if settings.backend == "windows_australian":
        from hanni.speech.australian import WindowsAustralianTts, australian_voice
        if australian_voice():
            output.parent.mkdir(parents=True, exist_ok=True)
            voice = WindowsAustralianTts(settings, data_dir=config.paths.data_dir)
            playback = voice.start(PREVIEW, output=output)
            try:
                playback.wait(settings.timeout_seconds)
            finally:
                playback.stop()
            print(f"Australian voice preview: {output}")
            if args.play:
                voice.speak(PREVIEW)
            return
        print("Australian pack is not installed. Preview uses the higher-pitched British fallback.")
    download_assets(engine.directory)
    payload = dict(chunks=[PREVIEW], model_dir=str(engine.directory), voice="hanni",
                   speed=settings.speed, language="en-gb" if settings.language == "en-au" else settings.language,
                   volume=settings.volume, cpu_threads=settings.cpu_threads,
                   pitch_semitones=settings.pitch_semitones)
    start = time.perf_counter()
    samples, rate = next(render_chunks(payload))
    elapsed = time.perf_counter() - start
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes((samples * 32767).astype("<i2").tobytes())
    print(f"Preview: {output}\nGenerated {len(samples) / rate:.1f}s of audio in {elapsed:.1f}s (including model load).")
    print("Voice: HANNI original blend, British English pronunciation. Restart HANNI to load configuration.")
    if args.play:
        import sounddevice as sd
        sd.play(samples, rate, blocking=True)


if __name__ == "__main__":
    main()
