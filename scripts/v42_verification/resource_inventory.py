"""Fresh protected resource/endpoint inspection, redacted safe selected metadata."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from hanni.models.resource_manager import snapshot_resources


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    output.parent.mkdir(parents=True,exist_ok=True)
    registry=ComputeRegistry(ROOT/'data');transport=InferenceTransport(registry);rows=[]
    try:
        for worker in registry.workers():
            began=time.perf_counter();health=transport.health(worker)
            startup=worker.get('startup',{})
            row={'worker_id':worker['worker_id'],'configured_model':worker.get('model_id'),
                'actual_health_status':health.get('status'),'model_reported':health.get('model_id'),
                'reported_context':health.get('context_reported'),'configured_context':startup.get('context'),
                'configured_backend':startup.get('kind'),'configured_gpu_device':startup.get('gpu_device'),
                'configured_cache_k':startup.get('cache_type_k'),'configured_cache_v':startup.get('cache_type_v'),
                'configured_concurrency':worker.get('concurrency',1),'interactive_reserve':worker.get('interactive_reserve',0),
                'allowed_categories':worker.get('allowed_categories'),'check_duration_ms':(time.perf_counter()-began)*1000,
                'current_verified_context':None,'resources':None,'ssh_setup_or_access_needed':health.get('status')!='healthy'}
            if health.get('status')=='healthy':
                sampled=transport.resources(worker)
                row['resources']={key:sampled.get(key) for key in ('ram_total_bytes','ram_available_bytes','vram_total_bytes','vram_free_bytes','gpus','resource_sampled_at')}
            rows.append(row)
            print(json.dumps({key:row[key] for key in ('worker_id','actual_health_status','model_reported','check_duration_ms')}),flush=True)
        report={'sampled_at':time.time(),'local_host':asdict(snapshot_resources()),'workers':rows,
                'remote_start_attempts':0,'original_strata_not_stopped':True,
                'context_scope':'Fresh inference validation required; historical proofs do not become new measurements',
                'resource_scope':'Unknown resources remain null and cannot be overridden by tunnels/history',
                'owned_gpu_cleanup_receipt':'data/v41-verification/cleanup-owned-v42-m0.json'}
        output.write_text(json.dumps(report,indent=2),encoding='utf8')
    finally:transport.close();registry.close()


if __name__=='__main__':main()
