"""Read measured GPU memory and context of specifically assigned owned processes."""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.dashboard.cluster import load_nodes, _run, _ssh_prefix, _tailscale_executable, tailscale_snapshot

REMOTE = r'''
import datetime,json,pathlib,subprocess
pids = ASSIGNED_PIDS
result={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'processes':[]}
for pid in pids:
 p=pathlib.Path('/proc')/str(pid)
 try:
  argv=(p/'cmdline').read_bytes().decode().split('\0')
  flags={}
  for i,arg in enumerate(argv[:-1]):
   if arg in {'--ctx-size','-c','--host','--port','--main-gpu','--parallel','--cache-type-k','--cache-type-v'}:flags[arg]=argv[i+1]
  env=(p/'environ').read_bytes().decode(errors='replace').split('\0')
  selected=next((item.split('=',1)[1] for item in env if item.startswith('CUDA_VISIBLE_DEVICES=')),None)
  result['processes'].append({'pid':pid,'comm':(p/'comm').read_text().strip(),'runtime_flags':flags,'cuda_visible_devices':selected})
 except OSError as e:result['processes'].append({'pid':pid,'error':type(e).__name__})
for name,args in [('gpus',['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits']),('compute_processes',['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader,nounits'])]:
 p=subprocess.run(args,capture_output=True,text=True,timeout=5)
 result[name]={'exit_code':p.returncode,'stdout':p.stdout[:6000],'stderr':p.stderr[:500]}
print(json.dumps(result))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if any(pid<1 for pid in args.pid) or len(args.pid)>4:
        raise SystemExit('Choose at most four specifically assigned positive owned PIDs.')
    output=args.output.resolve()
    if ROOT/'data' not in output.parents or output.exists():
        raise SystemExit('Choose a new private observation artifact.')
    nodes=load_nodes(ROOT/'data')
    node=next(n for n in nodes if n.id=='hanni')
    peer=tailscale_snapshot(nodes)['peers'].get(node.tailscale_ip,{})
    encoded=base64.b64encode(REMOTE.replace('ASSIGNED_PIDS',json.dumps(args.pid)).encode()).decode()
    command="python3 -c \"import base64;exec(base64.b64decode('"+encoded+"'))\""
    p=_run(_ssh_prefix(node,node.tailscale_ip,tailscale=_tailscale_executable() if peer.get('ssh_enabled') else None)+[command],timeout=20)
    if p.returncode:
        raise SystemExit('Assigned strict SSH measurement is blocked.')
    record=json.loads(p.stdout)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(record,indent=2),encoding='utf8')
    print(json.dumps(record,indent=2))

if __name__=='__main__':
    main()
