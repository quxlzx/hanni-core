"""Verifier-owned bounded model runtime; no full HANNI startup/download."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.config.loader import load_config
from hanni.models.manager import ModelManager


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--weights',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=3600)
    args=parser.parse_args()
    output,weights=args.output.resolve(),args.weights.resolve()
    assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    assert 60<=args.seconds<=7200
    config=load_config(ROOT/'config',data_dir=output/'state',env={})
    assert weights.is_file() and weights.name==config.models.supervisor.model_file
    output.mkdir(parents=True)
    with weights.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    manager=ModelManager(config,model_files={config.models.supervisor.id:str(weights)},startup_timeout=180)
    entry=None;process=None
    evidence={'weights_sha256':digest,'weight_bytes':weights.stat().st_size,'no_download':True,
              'maximum_runtime_seconds':args.seconds,'started_at':time.time()}
    try:
        began=time.perf_counter()
        entry=manager.ensure_loaded(config.models.supervisor.id)
        assert entry.process is not None,'External process preserved; owned helper required.'
        process=entry.process
        evidence.update(owned_pid=entry.process.pid,state='ready',load_time_ms=(time.perf_counter()-began)*1000,
                        snapshot=manager.snapshot())
        (output/'ownership.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
        print(json.dumps({'state':'ready','owned_pid':entry.process.pid,'load_time_ms':evidence['load_time_ms']}),flush=True)
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline and not (output/'stop').exists() and process.poll() is None: time.sleep(1)
    finally:
        manager.close()
        evidence.update(closed_at=time.time(),owned_process_closed=process is None or process.poll() is not None)
        (output/'closed.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
        print(json.dumps({'state':'closed','owned_process_closed':evidence['owned_process_closed']}),flush=True)


if __name__=='__main__':main()
