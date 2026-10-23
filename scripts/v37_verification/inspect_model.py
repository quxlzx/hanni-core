"""Read existing registered-node GGUF metadata and backend build/device facts.

All deployment paths are explicit local CLI inputs. No model is loaded here.
"""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.dashboard.cluster import load_nodes, _run, _ssh_prefix, _tailscale_executable

PROGRAM = r'''
import hashlib,json,pathlib,struct,subprocess
settings=INPUT
result={}
def run(command):
 try:
  r=subprocess.run(command,capture_output=True,text=True,timeout=8)
  return {'exit_code':r.returncode,'stdout':r.stdout[:40000],'stderr':r.stderr[:40000]}
 except (OSError,subprocess.TimeoutExpired) as e:return {'error':type(e).__name__}
server=settings.get('server')
if server:
 result['backend_version']=run([server,'--version'])
 result['backend_devices']=run([server,'--list-devices'])
 result['backend_help']=run([server,'--help'])
if settings.get('nvcc'):result['cuda_compiler']=run([settings['nvcc'],'--version'])
if settings.get('cuobjdump') and settings.get('cuda_library'):
 result['cuda_binary_architectures']=run([settings['cuobjdump'],'--list-elf',settings['cuda_library']])
path=pathlib.Path(settings['model_file']);entry={'path':str(path),'exists':path.is_file()};result['model']=entry
formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
if path.is_file():
 entry['size_bytes']=path.stat().st_size
 with path.open('rb') as f:
  entry['prefix_64k_sha256']=hashlib.sha256(f.read(65536)).hexdigest();f.seek(0)
  def unpack(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
  def string(capture):
   length=unpack('Q')
   if not capture or length>262144:f.seek(length,1);return None
   return f.read(length).decode('utf8','replace')
  def value(kind,capture):
   if kind in formats:
    v=unpack(formats[kind]);return v if capture else None
   if kind==8:return string(capture)
   if kind==9:
    sub=unpack('I');count=unpack('Q')
    if sub in formats:f.seek(struct.calcsize('<'+formats[sub])*count,1)
    else:
     if count>1000000:raise ValueError('Unsafe array metadata count')
     for _ in range(count):value(sub,False)
    return {'element_type':sub,'length':count} if capture else None
   raise ValueError('Unknown GGUF value type')
  entry['magic']=f.read(4).decode('ascii','replace');entry['gguf_version']=unpack('I');entry['tensor_count']=unpack('Q');count=unpack('Q');entry['metadata_count']=count;entry['metadata']={}
  if entry['magic']!='GGUF' or count>10000:raise ValueError('Invalid bounded GGUF metadata')
  for _ in range(count):
   key=string(True);kind=unpack('I');capture=key.startswith('general.') or key.endswith(('.context_length','.block_count','.embedding_length','.head_count','.head_count_kv','.rope.dimension_count','.key_length','.value_length')) or key in ('tokenizer.ggml.model','tokenizer.chat_template')
   v=value(kind,capture)
   if capture:
    if key=='tokenizer.chat_template' and isinstance(v,str):v={'sha256':hashlib.sha256(v.encode()).hexdigest(),'bytes':len(v.encode())}
    entry['metadata'][key]=v
print(json.dumps(result))
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--model-file', required=True)
    parser.add_argument('--server')
    parser.add_argument('--nvcc')
    parser.add_argument('--cuobjdump')
    parser.add_argument('--cuda-library')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    nodes = load_nodes(ROOT / 'data')
    node = next((row for row in nodes if row.id == args.node), None)
    if node is None:
        raise SystemExit('Choose an existing protected registered node.')
    output = args.output.resolve()
    if ROOT / 'data' not in output.parents:
        raise SystemExit('Private audit output must stay in ignored repository data.')
    values = {key: value for key, value in vars(args).items() if key not in {'node', 'output'}}
    for value in values.values():
        if value is not None and (not value.startswith('/') or '\x00' in value or '\n' in value):
            raise SystemExit('Use existing absolute remote paths.')
    source = PROGRAM.replace('settings=INPUT', 'settings=' + repr(values))
    encoded = base64.b64encode(source.encode()).decode()
    command = "python3 -c \"import base64;exec(base64.b64decode('" + encoded + "'))\""
    result = _run(_ssh_prefix(node, node.tailscale_ip, tailscale=_tailscale_executable()) + [command], timeout=45)
    record = {'readonly': True, 'model_loaded_by_this_probe': False,
              'exit_code': result.returncode, 'stderr': result.stderr[:2000]}
    if result.returncode == 0:
        record['inspection'] = json.loads(result.stdout)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2), encoding='utf8')
    print(json.dumps({'exit_code': result.returncode,
                      'model_exists': record.get('inspection', {}).get('model', {}).get('exists')}))

if __name__ == '__main__':
    main()
