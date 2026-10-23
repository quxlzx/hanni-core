"""Manager's bounded read-only census using the protected deployment roster."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import socket
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.dashboard.cluster import load_nodes, _run, _ssh_prefix, _tailscale_executable, tailscale_snapshot
REMOTE = runpy.run_path(str(ROOT / 'scripts/v37_verification/inspect_hardware.py'))['REMOTE']

EXTRA = r'''
import time
result['cpu_model']=None
try:
 for line in pathlib.Path('/proc/cpuinfo').read_text().splitlines():
  if line.startswith('model name'):
   result['cpu_model']=line.split(':',1)[1].strip();break
except OSError:pass
result['storage_backends']=[]
result['search_complete']=True
started=time.monotonic();visited=0
for search_root in (home,pathlib.Path('/mnt'),pathlib.Path('/media'),pathlib.Path('/opt'),pathlib.Path('/srv'),pathlib.Path('/data'),pathlib.Path('/usr/local')):
 if not search_root.is_dir():continue
 for current,folders,files in os.walk(search_root,followlinks=False):
  visited+=1
  folders[:]=[f for f in folders if f not in {'.git','node_modules','__pycache__','.venv','venv','.local','.config','.npm','.rustup','.cargo','.mozilla','snap','Trash','trash','site-packages'}]
  if len(pathlib.Path(current).relative_to(search_root).parts)>=4:folders[:]=[]
  for name in files:
   if not (name.lower().endswith('.gguf') or name in {'llama-server','llama-cli','nvcc','libggml-cuda.so'}):continue
   path=pathlib.Path(current)/name
   try:result['storage_backends'].append({'path':str(path),'size_bytes':path.stat().st_size,'is_symlink':path.is_symlink()})
   except OSError:pass
  if visited>=2500 or time.monotonic()-started>8:
   result['search_complete']=False;break
 if not result['search_complete']:break
result['search_directories']=visited
'''


def main():
    output = ROOT / 'data/v37-manager/discovery'
    output.mkdir(parents=True, exist_ok=True)
    nodes = load_nodes(ROOT / 'data')
    tail = tailscale_snapshot(nodes)
    encoded = base64.b64encode(REMOTE.replace('print(json.dumps(result))', EXTRA + '\nprint(json.dumps(result))').encode()).decode()
    command = "python3 -c \"import base64;exec(base64.b64decode('" + encoded + "'))\""

    def inspect(node):
        record = {'node_id': node.id, 'status': 'BLOCKED', 'readonly': True, 'attempts': []}
        peer = tail.get('peers', {}).get(node.tailscale_ip, {})
        for address, transport in ((node.lan_ip, 'lan'), (node.tailscale_ip, 'tailscale')):
            if not address:
                continue
            try:
                with socket.create_connection((address, 22), timeout=.8):
                    pass
            except OSError:
                record['attempts'].append({'transport': transport, 'status': 'tcp_unreachable'})
                continue
            began = time.monotonic()
            try:
                wrapper = _tailscale_executable() if transport == 'tailscale' and peer.get('ssh_enabled') else None
                result = _run(_ssh_prefix(node, address, tailscale=wrapper) + [command], timeout=30)
                record['attempts'].append({'transport': transport, 'returncode': result.returncode, 'elapsed_ms': round(1000*(time.monotonic()-began),1)})
                if result.returncode == 0:
                    record.update(status='PASS', transport=transport, hardware=json.loads(result.stdout))
                    break
                record['error_kind'] = 'authentication_or_remote_command_failed'
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                record['error_kind'] = type(exc).__name__
        (output / f'{node.id}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        return {'node_id': node.id, 'status': record['status'], 'transport': record.get('transport'),
                'cpu': record.get('hardware', {}).get('cpu_model'), 'ram_bytes': record.get('hardware', {}).get('ram_total_bytes'),
                'backend_files': len(record.get('hardware', {}).get('storage_backends', []))}

    summaries = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(inspect, node) for node in nodes if not node.maintenance]):
            value = future.result()
            summaries.append(value)
            print(json.dumps(value), flush=True)
    (output / 'summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
