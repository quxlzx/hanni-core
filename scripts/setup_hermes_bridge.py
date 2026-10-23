"""Deploy only the scoped bridge; reuse authorized SSH and Hermes' installed bootstrap.

Run inspect first. --deploy changes only new owned adapter/service paths; never
restarts the messaging gateway. --configure-windows stores private references,
keeps explicit delegation disabled, and refuses existing local config.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT/'data'


def configured_node():
    from hanni.dashboard.cluster import load_nodes
    node = next(n for n in load_nodes(DATA_DIR) if n.id == 'karina')
    if node.maintenance or not node.username or not node.tailscale_ip:
        raise RuntimeError('Configure the owner-approved Hermes node in the private roster first.')
    return node


def remote(program, *, input=None, timeout=20):
    from hanni.dashboard.cluster import load_nodes, _ssh_prefix, _run, _tailscale_executable
    node = configured_node()
    result = _run(_ssh_prefix(node, node.tailscale_ip, tailscale=_tailscale_executable())+
                  ['python3 -c '+shlex.quote(program)], input=input, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError('Authorized remote operation failed; no credentials were printed. Inspect the relevant service or paths.')
    return result.stdout


def inspect_remote():
    return json.loads(remote("""import pathlib,json,socket,subprocess,yaml
home=pathlib.Path.home();root=home/'.hermes/hermes-agent';p=home/'hanni-capabilities/data';s=p.stat()
cfg=yaml.safe_load((home/'.hermes/config.yaml').read_text())
with socket.socket() as probe:
 try:probe.bind(('127.0.0.1',8092));free=True
 except OSError:free=False
print(json.dumps({'host':'karina','port_8092_free':free,'bridge_exists':(home/'hanni-hermes-bridge').exists(),
 'gateway':subprocess.check_output(['systemctl','--user','is-active','hermes-gateway.service'],text=True).strip(),
 'launcher':str(home/'.local/bin/hermes'),'shared_mode':oct(s.st_mode&4095),'shared_owner_uid':s.st_uid,
 'model':{k:v for k,v in cfg['model'].items() if k in ['default','provider','base_url','context_length']},
 'mcp':{k:{'url':v.get('url'),'stdio':bool(v.get('command'))} for k,v in cfg.get('mcp_servers',{}).items()}}))
"""))


def deploy():
    evidence = inspect_remote()
    if not evidence['port_8092_free'] or evidence['bridge_exists']:
        raise RuntimeError('Bridge path or port is already occupied; inspect ownership before updating.')
    if evidence['shared_mode'] != '0o2770' or evidence['shared_owner_uid'] != 10001:
        raise RuntimeError('Shared storage gate failed; do not change its permissions automatically.')
    files = {'lib/hanni/__init__.py': (ROOT/'src/hanni/__init__.py').read_text()}
    for path in (ROOT/'src/hanni/hermes').glob('*.py'):
        files['lib/hanni/hermes/'+path.name] = path.read_text(encoding='utf-8')
    for path in (ROOT/'src/hanni/logs').glob('*.py'):
        files['lib/hanni/logs/'+path.name] = path.read_text(encoding='utf-8')
    for path in (ROOT/'deployment/hermes').iterdir():
        if path.is_file():
            files['deployment/'+path.name] = path.read_text(encoding='utf-8')
    remote("""import pathlib,json,sys,os
root=pathlib.Path.home()/'hanni-hermes-bridge'
root.mkdir(mode=0o700)
files=json.load(sys.stdin)
for name,content in files.items():
 parts=pathlib.PurePosixPath(name).parts
 if '..' in parts or name.startswith('/') or parts[0] not in {'lib','deployment'}:raise ValueError('Invalid staged path')
 target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('x') as f:f.write(content)
(root/'OWNER').write_text('hanni-hermes-v1')
print('Source staged; no existing services changed.')
""", input=json.dumps(files))
    # Installer is fixed and already staged; no dynamic shell command or secret argument.
    remote("""import subprocess
from pathlib import Path
r=subprocess.run(['sh',str(Path.home()/'hanni-hermes-bridge/deployment/install-karina.sh')],capture_output=True,text=True,timeout=90)
print(r.stdout[-2000:])
if r.returncode:raise RuntimeError('Adapter installation failed; gateway unchanged.')
""", timeout=100)
    print('Scoped bridge installed. Existing messaging gateway and model defaults preserved.')


def configure_windows(data_dir, windows_roots):
    from hanni.hermes.tunnel import ManagedTunnel
    root = data_dir.resolve()/'hermes'
    if (root/'config.json').exists() or (root/'bridge.token').exists():
        raise RuntimeError('Local private configuration exists; review instead of overwriting.')
    # Verify the actual key-only forwarding identity before writing startup settings.
    node = configured_node()
    destination = f'{node.username}@{node.tailscale_ip}'
    tunnel = {'destination':destination, 'forwards':[[18092,8092],[8090,8090],[8091,8091],[8931,8931]]}
    identity = os.environ.get('HANNI_CLUSTER_SSH_IDENTITY')
    if identity:
        tunnel['identity_file'] = identity
    candidate = ManagedTunnel(tunnel)
    command = candidate.command()
    # Check host/key trust without opening a forward or asking for a password.
    probe = ['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
             '-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=5']
    if identity:
        probe += ['-i',identity,'-o','IdentitiesOnly=yes']
    subprocess.run(probe+[destination,'true'], check=True, timeout=10)
    encoded = remote("""import base64,pathlib
p=pathlib.Path.home()/'hanni-hermes-bridge/bridge.token'
print(base64.b64encode(p.read_bytes()).decode())
""").strip()
    credential = base64.b64decode(encoded, validate=True)
    if not 32 <= len(credential) <= 256:
        raise RuntimeError('Invalid existing bridge credential reference.')
    root.mkdir(parents=True, exist_ok=True)
    token = root/'bridge.token'
    with token.open('xb') as handle:
        handle.write(credential)
    if os.name == 'nt':
        account = subprocess.check_output(['whoami'],text=True).strip()
        result = subprocess.run(['icacls',str(token),'/inheritance:r','/grant:r',account+':F'],
                                capture_output=True, timeout=10)
        if result.returncode:
            token.unlink()
            raise RuntimeError('Private credential ACL gate failed; configuration not enabled.')
    else:
        token.chmod(0o600)
    config = {'version':1, 'enabled':False, 'connection_only':True, 'delegation_policy':'explicit', 'endpoint':'http://127.0.0.1:18092',
              'token_file':str(token), 'tunnel':tunnel,
              'windows_capabilities':['file.read','file.stat','file.locate','file.write','app.open',
                                      'system.stats','system.performance','process.top_cpu','process.top_memory'],
              'windows_apps':['calculator','notepad'],
              'windows_roots':[str(path.resolve()) for path in windows_roots],
              'attachment_roots':[str(path.resolve()) for path in windows_roots], 'remote_read_hashes':[]}
    if windows_roots:
        config['windows_capabilities'].insert(0,'hermes.attachment.transfer')
    with (root/'config.json').open('x',encoding='utf-8') as handle:
        json.dump(config,handle,indent=2)
    print('Private Windows bridge references saved. Reopen HANNI, review the Hermes tab, then explicitly enable delegation.')


def update_owned():
    files = {'lib/hanni/__init__.py': (ROOT/'src/hanni/__init__.py').read_text()}
    files.update({'lib/hanni/hermes/'+p.name:p.read_text(encoding='utf-8') for p in (ROOT/'src/hanni/hermes').glob('*.py')})
    files.update({'lib/hanni/logs/'+p.name:p.read_text(encoding='utf-8') for p in (ROOT/'src/hanni/logs').glob('*.py')})
    files.update({'deployment/'+p.name:p.read_text(encoding='utf-8') for p in (ROOT/'deployment/hermes').iterdir() if p.is_file()})
    remote("""import pathlib,json,sys,sqlite3,subprocess,hashlib,os
root=pathlib.Path.home()/'hanni-hermes-bridge';assert (root/'OWNER').read_text()=='hanni-hermes-v1'
loader=pathlib.Path.home()/'.hermes/hermes-agent/hanni_hermes_adapter.py'
assert loader.read_bytes()==(root/'deployment/hanni_hermes_adapter.py').read_bytes(), 'Unmanaged loader edit'
c=sqlite3.connect(root/'state/tasks.sqlite3')
terminal={'completed','review_required','failed','cancelled','interrupted','uncertain'}
assert all(json.loads(row[0])['state'] in terminal for row in c.execute('SELECT payload FROM tasks')), 'Bridge has active tasks'
c.close()
files=json.load(sys.stdin)
for name in files:
 p=root/name
 assert p.resolve().is_relative_to(root.resolve()) and not p.is_symlink() and not pathlib.PurePosixPath(name).is_absolute()
 assert pathlib.PurePosixPath(name).parts[0] in {'lib','deployment'}
subprocess.run(['systemctl','--user','stop','hanni-hermes-bridge.service'],check=True)
for name,content in files.items():
 p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  old=p.read_bytes();b=root/'setup-backups'/hashlib.sha256(old).hexdigest();b.parent.mkdir(exist_ok=True)
  if not b.exists():b.write_bytes(old)
 tmp=p.with_name(p.name+'.new');tmp.write_text(content);os.replace(tmp,p)
loader.write_text((root/'deployment/hanni_hermes_adapter.py').read_text())
subprocess.run([str(pathlib.Path.home()/'.local/bin/hermes'),'--run-module','hanni_hermes_adapter','check'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['systemctl','--user','start','hanni-hermes-bridge.service'],check=True)
print('Owned idle bridge updated; messaging gateway and inference services unchanged.')
""", input=json.dumps(files), timeout=60)
    print('Owned bridge source updated after idle check. Prior source backups and receipts retained.')


def main():
    global DATA_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['inspect','deploy','configure-windows','update'])
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    parser.add_argument('--windows-root',type=Path,action='append',default=[])
    args=parser.parse_args()
    DATA_DIR = args.data_dir.resolve()
    if args.operation=='inspect':
        print(json.dumps(inspect_remote(),indent=2))
    elif args.operation=='deploy':
        deploy()
    elif args.operation=='update':
        update_owned()
    else:
        configure_windows(args.data_dir,args.windows_root)


if __name__=='__main__':
    main()
