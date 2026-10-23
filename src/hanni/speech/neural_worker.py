"""Private stdin-only voice worker. Assistant text/audio are never logged."""
from __future__ import annotations

import json
from pathlib import Path
import sys

# A reproducible blend of stock synthetic voices, with no recording/reference
# speaker. This is a HANNI profile, not a trained or cloned human identity.
HANNI_BLEND = {"af_heart": 0.65, "bf_emma": 0.20, "af_bella": 0.15}


def synthesizer(payload):
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    directory = Path(payload["model_dir"])
    options = ort.SessionOptions()
    options.intra_op_num_threads = payload["cpu_threads"]
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    session = ort.InferenceSession(str(directory / "kokoro-v1.0.onnx"),
                                   sess_options=options, providers=["CPUExecutionProvider"])
    engine = Kokoro.from_session(session, str(directory / "voices-v1.0.bin"))
    voice = payload["voice"]
    if voice in ("default", "hanni"):
        voice = sum(engine.get_voice_style(name) * weight for name, weight in HANNI_BLEND.items())
    return engine, voice


def render_chunks(payload):
    import numpy as np

    engine, voice = synthesizer(payload)
    factor = 2 ** (payload.get("pitch_semitones", 0.0) / 12)
    # Generate slower before raising pitch by resampling, keeping the requested
    # speaking pace approximately unchanged. The modest shift also brightens
    # formants; it does not change pronunciation or impersonate a speaker.
    speed = max(0.5, min(2.0, payload["speed"] / factor))
    for chunk in payload["chunks"]:
        samples, rate = engine.create(chunk, voice=voice, speed=speed,
                                      lang=payload["language"], trim=False)
        if not samples.size or not np.isfinite(samples).all():
            raise ValueError("invalid synthesis output")
        if factor != 1:
            samples = np.interp(np.arange(0, len(samples), factor), np.arange(len(samples)), samples)
        samples = np.clip(samples * payload["volume"] / 100, -1, 1).astype(np.float32)
        yield samples, rate


def play(payload):
    import sounddevice as sd

    output_name = payload.get('output_name')
    candidates = []
    if output_name:
        hosts = sd.query_hostapis()
        candidates = [(index, hosts[row['hostapi']]['name'])
                      for index, row in enumerate(sd.query_devices())
                      if row.get('max_output_channels', 0) > 0
                      and row['name'].casefold() == output_name.casefold()]
        if not candidates:
            raise RuntimeError('Selected speaker is unavailable to neural playback')
        candidates.sort(key=lambda item: ({'Windows WASAPI': 0, 'Windows DirectSound': 1,
                                           'MME': 2}.get(item[1], 3), item[0]))
    devices_by_rate = {}
    try:
        for samples, rate in render_chunks(payload):
            device = None
            if candidates:
                if rate not in devices_by_rate:
                    for index, _ in candidates:
                        try:
                            sd.check_output_settings(device=index, samplerate=rate,
                                                     channels=1, dtype='float32')
                        except Exception:
                            continue
                        devices_by_rate[rate] = index
                        break
                    else:
                        raise RuntimeError('Selected speaker does not support neural voice playback')
                device = devices_by_rate[rate]
            sd.play(samples, rate, device=device, blocking=True)
    finally:
        sd.stop()


def main():
    try:
        payload = json.load(sys.stdin)
        play(payload)
        return 0
    except Exception as exc:
        # Exception messages from G2P/audio libraries may contain private text.
        print(f"Neural voice failed ({type(exc).__name__}). Check audio output and voice files; "
              "set speech.tts.backend to windows_sapi to restore Windows speech.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
