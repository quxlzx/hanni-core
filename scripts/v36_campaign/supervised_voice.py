"""Explicit, bounded microphone test; raw PCM/transcripts never written to disk.

Run only after the owner agrees to a brief capture and confirms readiness. This
uses the original microphone, Silero VAD, cached configured faster-whisper and
relevance classifier. No continuous listener, webcam, speaker playback, download,
or production memory write is started.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from hanni.config.loader import load_config
from hanni.speech.microphone import MicrophoneCapture
from hanni.speech.stt import FasterWhisperTranscriber
from hanni.speech.relevance import SpeechRelevanceClassifier
from hanni.speech.vad import SileroVad, UtteranceSegmenter


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--owner-ready',action='store_true',required=True)
    p.add_argument('--wait-for-start',action='store_true')
    p.add_argument('--seconds',type=int,default=10,choices=range(5,13))
    p.add_argument('--output',type=Path,default=ROOT/'data/v36-campaign/supervised-voice.json')
    args=p.parse_args()
    assert args.owner_ready
    destination=args.output.resolve()
    assert destination.is_relative_to((ROOT/'data').resolve())
    config=load_config(ROOT/'config',data_dir=ROOT/'data/v36-campaign/voice-state',env={})
    cfg=config.hanni.speech
    os.environ['HF_HUB_OFFLINE']='1'
    transcriber=FasterWhisperTranscriber(model_name=cfg.stt.model,device=cfg.stt.device,
        compute_type=cfg.stt.compute_type,language=cfg.stt.language,beam_size=cfg.stt.beam_size)
    vad=SileroVad(sample_rate=cfg.sample_rate,threshold=cfg.vad.threshold,
        min_silence_ms=cfg.vad.min_silence_ms,speech_pad_ms=cfg.vad.speech_pad_ms)
    segmenter=UtteranceSegmenter(sample_rate=cfg.sample_rate,block_samples=cfg.block_samples,
        pre_roll_ms=cfg.vad.pre_roll_ms,max_utterance_seconds=cfg.vad.max_utterance_seconds)
    relevant=SpeechRelevanceClassifier(wake_names=cfg.relevance.wake_names,
        engagement_seconds=cfg.relevance.engagement_seconds,disengage_phrases=cfg.relevance.disengage_phrases,
        filler_words=cfg.relevance.filler_words,acknowledgement_words=cfg.relevance.acknowledgement_words)
    # Warm cached CPU models before the capture; readiness remains explicit.
    transcriber._load()
    vad._load()
    if args.wait_for_start:
        print('MODELS READY. Awaiting the manager START marker; microphone is closed.',flush=True)
        if sys.stdin.readline().strip() != 'START':
            raise SystemExit('Capture cancelled; no microphone opened')
    microphone=MicrophoneCapture(sample_rate=cfg.sample_rate,channels=cfg.channels,
        block_samples=cfg.block_samples,device=cfg.input_device)
    stop=threading.Event()
    timer=threading.Timer(args.seconds,stop.set)
    timer.daemon=True
    utterances=[];chunks=0
    result={'category':'M5_supervised','expected_phrase':'Hanni, what time is it?',
        'owner_consent':True,'requested_capture_seconds':args.seconds,'raw_audio_written':False,
        'raw_transcript_written':False,'capture_stopped':False,'model_configuration':asdict(cfg.stt),
        'scope':'owned bounded microphone/VAD/STT/wake test; controller and audible TTS evaluated separately'}
    began=time.monotonic()
    stream=None
    try:
        print('MICROPHONE ACTIVE: say Hanni, what time is it? Capture ends automatically.',flush=True)
        timer.start()
        stream=microphone.chunks(stop_event=stop,max_chunks=round(args.seconds*cfg.sample_rate/cfg.block_samples))
        for chunk in stream:
            chunks+=1
            utterance=segmenter.feed(chunk,vad.process(chunk))
            if utterance is not None: utterances.append(utterance)
        trailing=segmenter.flush()
        if trailing is not None: utterances.append(trailing)
    finally:
        stop.set();timer.cancel()
        if stream is not None:stream.close()
        result.update(capture_stopped=True,captured_chunks=chunks,
            capture_elapsed_seconds=round(time.monotonic()-began,3),dropped_blocks=microphone.dropped_blocks)
        print('MICROPHONE CLOSED. Transcribing ephemeral test utterances locally.',flush=True)
    try:
        decisions=[]
        for utterance in utterances:
            started=time.monotonic()
            text=transcriber.transcribe(utterance).text
            decision=relevant.classify(text)
            normalized=re.sub(r'[^a-z ]',' ',text.lower())
            matched=bool(re.search(r'what\s+time\s+is\s+it',normalized))
            decisions.append({'duration_seconds':round(utterance.duration_seconds,3),
                'latency_seconds':round(time.monotonic()-started,3),
                'expected_command_recognized':matched,'wake_detected':decision.wake_word_detected,
                'relevant':decision.relevant,'reason':decision.reason,
                'recognized_character_count':len(text)})
            del text,utterance
        result['decisions']=decisions
        result['outcome']='MANUAL_PASS' if any(x['expected_command_recognized'] and x['wake_detected'] and x['relevant'] for x in decisions) else 'FAIL'
        result['failure_category']=None if result['outcome']=='MANUAL_PASS' else 'acoustic_recognition_or_wake'
    finally:
        utterances.clear()
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
