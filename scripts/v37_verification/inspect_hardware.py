"""Independent bounded read-only hardware audit; no inference or remote writes."""
from pathlib import Path
import base64
import json
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.dashboard.cluster import load_nodes, _run, _ssh_prefix, _tailscale_executable, tailscale_snapshot

REMOTE = r'''
import hashlib,json,os,pathlib,platform,shutil,subprocess,sys
def run(args):
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=4)
  return {'exit_code':p.returncode,'stdout':p.stdout[:18000],'stderr':p.stderr[:1800]}
 except (OSError,subprocess.TimeoutExpired) as e:return {'error':type(e).__name__}
home=pathlib.Path.home()
memory={}
try:memory={l.split(':')[0]:int(l.split()[1])*1024 for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if len(l.split())>=2}
except OSError:pass
os_release={}
try:os_release=dict(l.split('=',1) for l in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in l)
except OSError:pass
result={'platform':platform.platform(),'os_release':os_release,'cpu':platform.processor(),'cpu_count':os.cpu_count(),'python':sys.version,'ram_total_bytes':memory.get('MemTotal'),'ram_available_bytes':memory.get('MemAvailable'),'software':{n:shutil.which(n) for n in ('nvidia-smi','nvcc','llama-server','llama-cli','ollama','k3s','tailscale')},'gpu':None,'gpu_processes':None}
if shutil.which('nvidia-smi'):
 result['gpu']=run(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,driver_version,compute_cap,utilization.gpu','--format=csv,noheader,nounits'])
 result['gpu_processes']=run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader,nounits'])
if shutil.which('nvcc'):result['cuda']=run(['nvcc','--version'])
result['disks']=[]
for path in (home,pathlib.Path('/')):
 try:
  disk=shutil.disk_usage(path);result['disks'].append({'path':str(path),'total_bytes':disk.total,'free_bytes':disk.free})
 except OSError:pass
result['interfaces']=run(['ip','-j','address','show']) if shutil.which('ip') else None
result['listeners']=run(['ss','-ltnp']) if shutil.which('ss') else None
result['model_files']=[]
roots=(home/'models',home/'Models',home/'.cache/llama.cpp',home/'Strata/models',home/'HANNI/models',pathlib.Path('/opt/models'),pathlib.Path('/mnt/models'))
for root in roots:
 if not root.is_dir():continue
 count=0
 for current,folders,files in os.walk(root):
  depth=len(pathlib.Path(current).relative_to(root).parts)
  if depth>=3:folders[:]=[]
  for name in files:
   if not name.lower().endswith('.gguf'):continue
   path=pathlib.Path(current)/name
   try:result['model_files'].append({'path':str(path),'size_bytes':path.stat().st_size})
   except OSError:pass
   count+=1
   if count>=100:break
  if count>=100:break
launcher=home/'Strata/run-iq3_s.sh'
result['strata']={'directory_exists':(home/'Strata').is_dir(),'launcher_exists':launcher.is_file()}
if launcher.is_file():
 content=launcher.read_bytes()
 result['strata'].update(launcher_sha256=hashlib.sha256(content).hexdigest(),launcher_text=content[:24000].decode('utf8','replace'))
result['server_processes']=[]
for directory in pathlib.Path('/proc').iterdir():
 if not directory.name.isdigit():continue
 try:
  name=(directory/'comm').read_text().strip()
  if any(word in name.lower() for word in ('llama','strata','ollama','vllm')):
   result['server_processes'].append({'pid':int(directory.name),'name':name,'executable':os.readlink(directory/'exe')})
 except OSError:pass
print(json.dumps(result))
'''

def main():
    output = ROOT / 'data/v37-verification/hardware'
    output.mkdir(parents=True, exist_ok=True)
    nodes = load_nodes(ROOT / 'data')
    tail = tailscale_snapshot(nodes)
    (output / 'tailscale-projection.json').write_text(json.dumps(tail, indent=2), encoding='utf8')
    encoded = base64.b64encode(REMOTE.encode()).decode()
    remote_command = "python3 -c \"import base64;exec(base64.b64decode('" + encoded + "'))\""
    for node in [n for n in nodes if n.id in {'hanni', 'wonyoung'}]:
        record = {'node_id': node.id, 'attempts': [], 'status': 'BLOCKED', 'readonly': True, 'inference_started': False}
        addresses = []
        try:
            with socket.create_connection((node.lan_ip,22), timeout=1.5):
                addresses.append((node.lan_ip,None))
        except OSError:
            record['attempts'].append({'transport':'lan','status':'tcp_unreachable'})
        peer = tail.get('peers',{}).get(node.tailscale_ip,{})
        if peer.get('online') is not False:
            addresses.append((node.tailscale_ip,_tailscale_executable() if peer.get('ssh_enabled') else None))
        else:
            record['attempts'].append({'transport':'tailscale','status':'peer_offline','ssh_attempted':False})
        for address, wrapper in addresses:
            started = time.monotonic()
            try:
                result = _run(_ssh_prefix(node,address,tailscale=wrapper)+[remote_command],timeout=25)
                item={'transport':'tailscale' if address == node.tailscale_ip else 'lan','exit_code':result.returncode,'elapsed_ms':(time.monotonic()-started)*1000,'stderr':result.stderr[:1600]}
                record['attempts'].append(item)
                if result.returncode==0:
                    record.update(status='LIVE_PASS',hardware=json.loads(result.stdout))
                    break
            except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
                record['attempts'].append({'status':type(exc).__name__,'elapsed_ms':(time.monotonic()-started)*1000})
        (output / (node.id + '.json')).write_text(json.dumps(record, indent=2), encoding='utf8')
        print(json.dumps({'node_id':node.id,'status':record['status'],'attempts':len(record['attempts']),'gpus_measured':record.get('hardware',{}).get('gpu') is not None}))

if __name__ == '__main__':
    main()
