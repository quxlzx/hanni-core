"""Safe wrapper around an existing Strata server; original files stay intact."""
from __future__ import annotations

import json

from .registry import ComputeError, integer


def launch_program(startup, *, port, nonce):
    allowed = {'authorized', 'kind', 'installation_dir', 'config_file', 'python_executable',
               'context', 'max_runtime_seconds', 'minimum_free_ram_bytes'}
    if set(startup) - allowed or startup.get('authorized') is not True or startup.get('kind') != 'strata':
        raise ComputeError('Strata startup requires the existing authorized installation.')
    for field in ('installation_dir', 'config_file', 'python_executable'):
        value = startup.get(field)
        if not isinstance(value, str) or not value.startswith('/') or any(char in value for char in '\x00\n\r'):
            raise ComputeError('Strata startup requires verified absolute installation paths.')
    context = integer(startup.get('context', 8192), 1024, 131072, 'Strata context')
    runtime = integer(startup.get('max_runtime_seconds', 600), 30, 3600, 'owned server runtime')
    ram = integer(startup.get('minimum_free_ram_bytes', 4 * 1024 ** 3), 1024 ** 3, 16 * 1024 ** 3, 'RAM reserve')
    parameters = json.dumps({'installation_dir': startup['installation_dir'], 'config_file': startup['config_file'],
        'python_executable': startup['python_executable'], 'context': context, 'port': port,
        'nonce': nonce, 'runtime': runtime, 'minimum_free_ram_bytes': ram})
    return '''import json,os,pathlib,signal,socket,subprocess,threading,time
p=json.loads(PARAMETERS)
root=pathlib.Path(p['installation_dir']).resolve()
original=pathlib.Path(p['config_file']).resolve()
cfg=json.loads(original.read_text())
# Preserve the virtual-environment invocation path: resolving a symlinked
# python executable changes sys.prefix and silently drops installed packages.
python=pathlib.Path(p['python_executable']).absolute()
server=root/'serve/server.py'
if not server.is_file() or not python.is_file():raise SystemExit('Existing Strata server is unavailable.')
s=socket.socket();s.settimeout(1);occupied=s.connect_ex(('127.0.0.1',p['port']))==0;s.close()
if occupied:raise SystemExit('An existing server owns this port.')
args=cfg.get('args')
if not isinstance(args,list) or not all(isinstance(v,str) for v in args):raise SystemExit('Invalid existing Strata engine arguments.')
if '--max-context' in args:
 i=args.index('--max-context');args[i+1]=str(p['context'])
else:args+=['--max-context',str(p['context'])]
managed=root/'.hanni-managed'/p['nonce'];managed.mkdir(parents=True,mode=0o700)
os.chmod(managed,0o700)
cfg.update(host='127.0.0.1',port=p['port'],args=args,log=str(managed/'engine.log'),
           open_browser=False,api_monitor=False,fit_max_tokens=False)
for field in ('before_load','mcp_servers','mcp_config','vision','slot_save_path'):
 cfg.pop(field,None)
owned_config=managed/'deployment.json';owned_config.write_text(json.dumps(cfg));os.chmod(owned_config,0o600)
env=os.environ.copy();env['HANNI_COMPUTE_OWNER']=p['nonce']
log=open(managed/'server.log','ab',buffering=0)
child=subprocess.Popen([str(python),str(server),'--engine','strata','--config',str(owned_config),
                       '--host','127.0.0.1','--port',str(p['port'])],cwd=root,env=env,
                       stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'pid':child.pid,'nonce':p['nonce'],'managed_directory':str(managed),'context':p['context']}),flush=True)
watchdog=os.fork()
if watchdog==0:
 os.setsid()
 null=os.open('/dev/null',os.O_RDWR)
 for fd in (0,1,2):os.dup2(null,fd)
 deadline=time.monotonic()+p['runtime']
 while time.monotonic()<deadline:
  try:
   os.kill(child.pid,0)
   mem={line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2}
   if mem.get('MemAvailable',0)<p['minimum_free_ram_bytes']:break
  except (ProcessLookupError,OSError,ValueError):os._exit(0)
  time.sleep(1)
 try:
  token=('HANNI_COMPUTE_OWNER='+p['nonce']).encode()
  if token in pathlib.Path(f'/proc/{child.pid}/environ').read_bytes().split(b'\\0'):
   os.kill(child.pid,signal.SIGTERM)
   time.sleep(5)
   try:
    if token in pathlib.Path(f'/proc/{child.pid}/environ').read_bytes().split(b'\\0'):os.killpg(child.pid,signal.SIGKILL)
   except (ProcessLookupError,OSError):pass
 except (ProcessLookupError,OSError):pass
 os._exit(0)
'''.replace('PARAMETERS', repr(parameters))
