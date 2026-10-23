"""Independently reproduce exact digital-silence STT using cached real weights.

No microphone, audible playback, raw personal audio, downloads or GPU workload.
Baseline is the saved original Git module; candidate is current production code.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]

class CountingActualModel:
    def __init__(self,model):self.model=model;self.calls=0
    def transcribe(self,*args,**kwargs):
        self.calls+=1
        return self.model.transcribe(*args,**kwargs)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline-only',action='store_true')
    parser.add_argument('--candidate-only',action='store_true')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    os.environ['HF_HUB_OFFLINE']='1'
    from faster_whisper import WhisperModel
    from hanni.config.loader import load_config
    from hanni.speech.vad import Utterance
    config=load_config(ROOT/'config',data_dir=output/'state',env={}).hanni.speech.stt
    result={'disclosure':__doc__,'model':asdict(config),'microphone_capture':False,'speaker_playback':False,
            'case':'2 seconds of explicitly generated all-zero mono PCM16 at 16000 Hz','arms':[]}
    load_start=time.perf_counter()
    actual=WhisperModel(config.model,device=config.device,compute_type=config.compute_type,
                       local_files_only=True,cpu_threads=2,num_workers=1)
    result['actual_cached_model_load_ms']=(time.perf_counter()-load_start)*1000
    baseline_source=subprocess.check_output(['git','show','45cde75:src/hanni/speech/stt.py'],cwd=ROOT)
    baseline=output/'original_stt_module.py';baseline.write_bytes(baseline_source)
    arms=[]
    if not args.candidate_only:
        spec=importlib.util.spec_from_file_location('independent_v36_original_stt',baseline)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        arms.append(('baseline_45cde75',module.FasterWhisperTranscriber,hashlib.sha256(baseline_source).hexdigest()))
    if not args.baseline_only:
        from hanni.speech.stt import FasterWhisperTranscriber
        arms.append(('current_candidate',FasterWhisperTranscriber,hashlib.sha256((ROOT/'src/hanni/speech/stt.py').read_bytes()).hexdigest()))
    for name,implementation,sourcehash in arms:
        counted=CountingActualModel(actual)
        adapter=implementation(model_name=config.model,device=config.device,compute_type=config.compute_type,
              language=config.language,beam_size=config.beam_size,model=counted)
        started=time.perf_counter()
        transcription=adapter.transcribe(Utterance(b'\0'*(16000*2*2),0,2,16000,1))
        result['arms'].append({'arm':name,'transcription':asdict(transcription),
              'latency_ms':(time.perf_counter()-started)*1000,'actual_decoder_calls':counted.calls,
              'source_sha256':sourcehash,'outcome':'ISOLATED_PASS' if not transcription.text.strip() else 'FAIL'})
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
