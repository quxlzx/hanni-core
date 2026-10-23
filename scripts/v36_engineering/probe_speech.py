"""Actual installed voice dependencies; no microphone capture/speaker playback.

Only device/voice discovery and digitally generated zero-valued audio are used.
Speech weights must already be cached; downloads are disabled explicitly.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import time

from hanni.config.loader import load_config

ROOT = Path(__file__).resolve().parents[2]


def probe():
    config = load_config(ROOT/'config', data_dir=ROOT/'data/v36-engineering/speech-state', env={})
    result = {'version': 1, 'configured_speech': asdict(config.hanni.speech),
              'microphone_capture': False, 'speaker_playback': False,
              'inputs': 'Device discovery and generated digital PCM silence only; no owner recording.',
              'dependencies': {name: importlib.util.find_spec(name) is not None for name in
                  ('sounddevice', 'numpy', 'torch', 'silero_vad', 'faster_whisper', 'onnxruntime', 'pycaw')}}
    try:
        from hanni.speech.microphone import list_input_devices
        started = time.perf_counter()
        devices = list_input_devices()
        result['microphone_discovery'] = {'outcome':'LIVE_PASS', 'devices':[asdict(device) for device in devices],
                                          'latency_ms':(time.perf_counter()-started)*1000}
    except Exception as error:
        result['microphone_discovery'] = {'outcome':'BLOCKED', 'error':str(error)}
    try:
        from hanni.speech.tts import list_windows_voices
        started = time.perf_counter()
        voices = list_windows_voices()
        result['installed_windows_voices'] = {'outcome':'LIVE_PASS', 'voices':[asdict(voice) for voice in voices],
                                              'latency_ms':(time.perf_counter()-started)*1000}
    except Exception as error:
        result['installed_windows_voices'] = {'outcome':'BLOCKED', 'error':str(error)}
    try:
        from hanni.speech.types import AudioChunk
        from hanni.speech.vad import SileroVad
        vad = SileroVad()
        started = time.perf_counter()
        decisions = [vad.process(AudioChunk(b'\0'*(512*2), 16000, 1, index*512/16000)) for index in range(32)]
        vad.reset()
        valid = all(not item.started and not item.ended for item in decisions)
        result['generated_silence_vad'] = {'outcome':'ISOLATED_PASS' if valid else 'FAIL',
            'samples':32, 'seconds':32*512/16000, 'latency_ms':(time.perf_counter()-started)*1000,
            'decisions':[asdict(item) for item in decisions]}
    except Exception as error:
        result['generated_silence_vad'] = {'outcome':'BLOCKED', 'error':str(error)}
    try:
        # Original transcriber with the actual cached CPU/int8 model object.
        # local_files_only prevents the library's usual uncached download.
        os.environ['HF_HUB_OFFLINE'] = '1'
        from faster_whisper import WhisperModel
        from hanni.speech.stt import FasterWhisperTranscriber
        from hanni.speech.vad import Utterance
        stt_cfg = config.hanni.speech.stt
        started = time.perf_counter()
        model = WhisperModel(stt_cfg.model, device=stt_cfg.device,
                             compute_type=stt_cfg.compute_type, local_files_only=True,
                             cpu_threads=2, num_workers=1)
        load_ms = (time.perf_counter()-started)*1000
        transcriber = FasterWhisperTranscriber(model_name=stt_cfg.model, device=stt_cfg.device,
              compute_type=stt_cfg.compute_type, language=stt_cfg.language,
              beam_size=stt_cfg.beam_size, model=model)
        started = time.perf_counter()
        transcript = transcriber.transcribe(Utterance(b'\0'*(16000*2*2),0,2,16000,1))
        result['generated_silence_stt'] = {'outcome':'ISOLATED_PASS' if not transcript.text.strip() else 'FAIL',
            'transcript':asdict(transcript), 'duration_seconds':2,
            'model_load_ms':load_ms, 'transcription_ms':(time.perf_counter()-started)*1000,
            'quality_scope':'Digital silence only; does not establish real speech recognition accuracy.'}
    except Exception as error:
        result['generated_silence_stt'] = {'outcome':'BLOCKED', 'error':str(error),
            'reason':'Actual STT dependency/model unavailable or failed; no download attempted.'}
    result['supervised_acoustic_scenarios'] = {'outcome':'BLOCKED',
        'cases':['microphone selection/capture','wake-word acoustic activation','speech recognition accuracy',
                 'audible TTS quality','acoustic speech interruption/barge-in','real voice stop command'],
        'reason':'Requires a supervised person speaking/listening. Owner preference is continue without requiring additional action; no acoustic input/output was started.'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = probe()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding='utf-8')
    print(json.dumps({key:value.get('outcome') for key,value in result.items() if isinstance(value,dict) and 'outcome' in value},ensure_ascii=True))
