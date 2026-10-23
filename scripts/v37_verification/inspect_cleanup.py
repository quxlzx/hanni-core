"""Independent bounded read-only cleanup and original-file integrity check.

Hash whole original configuration bytes without parsing or printing credentials.
Only specifically assigned PIDs/loopback ports are checked. No process is stopped.
"""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.dashboard.cluster import load_nodes,_run,_ssh_prefix,_tailscale_executable,tailscale_snapshot

PROGRAM=r'''
import hashlib,json,pathlib,socket,subprocess,shutil
settings=SETTINGS
result={'readonly':True,'processes':[],'ports':[],'original_hashes':{},'credentials_printed':False}
for pid in settings['pids']:
 p=pathlib.Path('/proc')/str(pid)
 result['processes'].append({'pid':pid,'exists':p.exists(),'comm':(p/'comm').read_text().strip() if p.exists() else None})
for port in settings['ports']:
 with socket.socket() as s:
  s.settimeout(1);code=s.connect_ex(('127.0.0.1',port))
 result['ports'].append({'port':port,'accepts_loopback_connection':code==0,'connect_code':code})
if settings['strata_original']:
 for name in ('run-iq3_s.sh','strata-iq3_s.json','serve/server.py'):
  p=pathlib.Path.home()/'Strata'/name
  result['original_hashes'][name]=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
if shutil.which('nvidia-smi'):
 p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
 result['gpu_processes']={'exit_code':p.returncode,'stdout':p.stdout[:6000],'stderr':p.stderr[:500]}
print(json.dumps(result))
'''

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--node',choices=['hanni','wonyoung'],required=True)
 parser.add_argument('--pid',type=int,action='append',default=[])
 parser.add_argument('--port',type=int,action='append',default=[])
 parser.add_argument('--strata-original',action='store_true')
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 if any(p<1 for p in args.pid) or any(not 1<=p<=65535 for p in args.port) or len(args.pid)>6 or len(args.port)>6:
  raise SystemExit('Choose bounded specifically assigned PIDs and ports.')
 output=args.output.resolve()
 if ROOT/'data' not in output.parents or output.exists():raise SystemExit('Choose new protected evidence.')
 nodes=load_nodes(ROOT/'data');node=next(n for n in nodes if n.id==args.node)
 peer=tailscale_snapshot(nodes)['peers'].get(node.tailscale_ip,{})
 settings={'pids':args.pid,'ports':args.port,'strata_original':args.strata_original}
 encoded=base64.b64encode(PROGRAM.replace('settings=SETTINGS','settings='+repr(settings)).encode()).decode()
 command="python3 -c \"import base64;exec(base64.b64decode('"+encoded+"'))\""
 result=_run(_ssh_prefix(node,node.tailscale_ip,tailscale=_tailscale_executable() if peer.get('ssh_enabled') else None)+[command],timeout=20)
 if result.returncode:raise SystemExit('Strict read-only cleanup inspection is blocked.')
 record=json.loads(result.stdout);output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record,indent=2))

if __name__=='__main__':main()
