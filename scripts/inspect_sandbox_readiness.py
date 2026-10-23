"""Read-only inventory over HANNI's existing verified SSH boundary; no secrets."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil

from hanni.dashboard.cluster import load_nodes, tailscale_snapshot, _ssh_prefix, _run, _tailscale_executable

PROBE = r'''import json,os,pathlib,shutil,subprocess,platform
paths=['/etc/rancher/k3s/k3s.yaml',str(pathlib.Path.home()/'.kube/config'),'/srv/hanni/shared/sandbox']
out={'commands':{n:shutil.which(n) for n in ['k3s','kubectl','docker','podman','runsc','kata-runtime']},
 'paths':{p:{'exists':pathlib.Path(p).exists(),'readable':os.access(p,os.R_OK),'symlink':pathlib.Path(p).is_symlink()} for p in paths},
 'alternatives':{n:shutil.which(n) for n in ['microk8s','k0s','rke2','minikube']},
 'host':{'os':platform.system(),'architecture':platform.machine(),'logical_cpus':os.cpu_count(),
         'root_storage_free_bytes':shutil.disk_usage('/').free}}
try:
 memory={line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2}
 out['host'].update(ram_total_bytes=memory.get('MemTotal'),ram_available_bytes=memory.get('MemAvailable'))
except Exception:pass
try:
 if shutil.which('docker'):
  r=subprocess.run(['docker','info','--format','{{json .SecurityOptions}}'],capture_output=True,text=True,timeout=3)
  out['docker_security_options']=json.loads(r.stdout) if r.returncode==0 else None
  r=subprocess.run(['docker','ps','--format','{{.Image}}'],capture_output=True,text=True,timeout=3)
  out['running_kubernetes_container_candidates']=sum(any(k in image.lower() for k in ['k3s','k0s','kube-apiserver','microk8s']) for image in r.stdout.splitlines()) if r.returncode==0 else None
except Exception:out['docker_security_options']=None
try:
 r=subprocess.run(['systemctl','is-active','k3s','k3s-agent'],capture_output=True,text=True,timeout=3)
 out['k3s_service_states']=r.stdout.splitlines()[:2]
except Exception:out['k3s_service_states']=None
print(json.dumps(out))
'''
WINDOWS_PROBE = r'''$result=@{commands=@{};paths=@{};host=@{os='Windows'}}
foreach ($commandName in @('kubectl','k3s','wsl')) {
 $commandValue=Get-Command $commandName -ErrorAction SilentlyContinue
 $result.commands[$commandName]=if($commandValue){$commandValue.Source}else{$null}
}
$configPath=Join-Path $env:USERPROFILE '.kube\config'
$result.paths['owner-kubeconfig']=@{exists=(Test-Path -LiteralPath $configPath)}
$result | ConvertTo-Json -Depth 5 -Compress
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    nodes=load_nodes(Path('data'));tailnet=tailscale_snapshot(nodes)
    def inspect(node):
        row={'node_id':node.id,'maintenance':node.maintenance}
        if node.maintenance or not node.username or not (node.tailscale_ip or node.lan_ip):
            return {**row,'status':'NOT TESTED','reason':'Maintenance or missing authorized SSH binding'}
        address=node.tailscale_ip or node.lan_ip
        try:
            native=_tailscale_executable() if tailnet.get('peers',{}).get(address,{}).get('ssh_enabled') else None
            command=('powershell -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(WINDOWS_PROBE.encode('utf-16le')).decode()
                     if tailnet.get('peers',{}).get(address,{}).get('os')=='windows'
                     else 'python3 -c '+shlex.quote(PROBE))
            result=_run(_ssh_prefix(node,address,tailscale=native)+[command],timeout=10)
            if result.returncode:raise ValueError('Read-only SSH probe did not return valid inventory')
            return {**row,'status':'LIVE_READ_ONLY','inventory':json.loads(result.stdout)}
        except Exception as exc:
            return {**row,'status':'NOT VERIFIED','error_type':type(exc).__name__}
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(inspect,nodes))
    out={'sampled_at':datetime.now(timezone.utc).isoformat(),'scope':'READ_ONLY_NO_KUBECONFIG_CONTENTS',
         'local_commands':{n:shutil.which(n) for n in ('kubectl','docker')},'nodes':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(out,stream,indent=2)
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
