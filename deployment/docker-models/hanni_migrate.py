"""Run on HANNI as athena. Preserve original systemd authority and binaries.

No model downloads, driver installation, public ports or privileged containers.
Host-library bindings preserve the existing Pascal CUDA/Vulkan builds.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import re
import subprocess
import tarfile
import time
import urllib.request

SERVICES={'swift':'hanni-swift.service','nex':'hanni-nex.service','mellum':'hanni-mellum.service'}
PORTS={'swift':8101,'nex':8102,'mellum':8103}
ALIASES={'swift':'swift-1.5','nex':'nex-n2-mini','mellum':'mellum-2.1'}
ROOT=Path.home()/'hanni-control/docker-migration'
IMAGE='hanni-host-runtime:existing-libraries-v1'
DOCKER=['docker','--host','unix:///var/run/docker.sock']


def run(args, **kwargs):
    return subprocess.run(args,check=True,capture_output=True,**kwargs)


def record(model):
    unit=Path.home()/'.config/systemd/user'/SERVICES[model]
    raw=unit.read_text()
    starts=[line[10:] for line in raw.splitlines() if line.startswith('ExecStart=')]
    if len(starts)!=1:raise ValueError('Expected one original native ExecStart')
    argv=shlex.split(starts[0])
    if 'llama-server' not in Path(argv[0]).name:raise ValueError('Existing unit is not the expected native model')
    env={}
    for line in raw.splitlines():
        if line.startswith('Environment='):
            for item in shlex.split(line[12:]):
                key,value=item.split('=',1)
                if key not in {'CUDA_VISIBLE_DEVICES','LD_LIBRARY_PATH'}:
                    raise ValueError('Review unexpected model environment before migration')
                env[key]=value
    return {'unit':str(unit),'sha256':hashlib.sha256(raw.encode()).hexdigest(),
            'argv':argv,'env':env,'uid':os.getuid(),'gid':os.getgid(),'model':model}


def image():
    probe=subprocess.run(DOCKER+['image','inspect',IMAGE],capture_output=True)
    if probe.returncode==0:
        value=json.loads(probe.stdout)[0]
        if value.get('Config',{}).get('Labels',{}).get('org.hanni.runtime')!='existing-libraries-v1':
            raise ValueError('Image name belongs to an unrelated image')
        return
    content=io.BytesIO()
    with tarfile.open(fileobj=content,mode='w'):pass
    run(DOCKER+['import','--change','LABEL org.hanni.runtime=existing-libraries-v1','-',IMAGE],input=content.getvalue())


def docker_args(value, *, probe=False):
    model=value['model'];name='hanni-model-'+model
    argv=value['argv'];model_path=argv[argv.index('-m')+1]
    args=DOCKER+['run','--rm','--name',name+('-probe' if probe else ''),
          '--label','org.hanni.service='+SERVICES[model],
          '--label','org.hanni.owner=control-center', '--read-only','--cap-drop=ALL',
          '--security-opt=no-new-privileges','--user',str(value['uid'])+':'+str(value['gid']),
          '--network','none' if probe else 'host','--stop-timeout','30',
          '--tmpfs','/tmp:rw,nosuid,nodev,size=128m','--pids-limit','128']
    mounts=['/usr','/lib','/lib64','/etc/ld.so.cache',str(Path(argv[0]).parent),model_path]
    for path in ['/etc/alternatives','/etc/vulkan','/usr/share/vulkan']:
        if Path(path).exists() and not any(Path(path).is_relative_to(Path(parent)) for parent in mounts):mounts.append(path)
    for path in mounts:args+=['--mount','type=bind,src='+path+',dst='+path+',readonly']
    for key,val in value['env'].items():args+=['--env',key+'='+val]
    if model=='swift':
        for device in sorted(Path('/dev/dri').glob('*')):
            if device.name.startswith(('renderD','card')):args+=['--device',str(device)]
        groups={device.stat().st_gid for device in Path('/dev/dri').glob('*')}
        for gid in sorted(groups):args+=['--group-add',str(gid)]
    else:
        for device in sorted(Path('/dev').glob('nvidia*')):
            if not device.is_dir():args+=['--device',str(device)]
    effective=list(argv)
    if not probe and model=='swift':
        if not value.get('container_device'):raise ValueError('Vulkan container identity mapping is not verified')
        effective[effective.index('-dev')+1]=value['container_device']
    return args+[IMAGE]+([argv[0],'--list-devices'] if probe else effective)


def health(model, *, inference=False):
    base='http://127.0.0.1:'+str(PORTS[model])
    with urllib.request.urlopen(base+'/health',timeout=3) as response:
        if json.load(response).get('status')!='ok':raise ValueError('Model health is not ready')
    with urllib.request.urlopen(base+'/v1/models',timeout=3) as response:
        if ALIASES[model] not in [row.get('id') for row in json.load(response).get('data',[])]:
            raise ValueError('Loaded model identity differs from original')
    if inference:
        payload={'model':ALIASES[model],'messages':[{'role':'user','content':'What is 3 plus 4? Answer with only the number.'}],
                 'max_tokens':32,'temperature':0,'stream':False,'chat_template_kwargs':{'enable_thinking':False}}
        request=urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=45) as response:value=json.load(response)
        content=value['choices'][0]['message'].get('content','').strip()
        if content!='7':raise ValueError('Live inference check failed; do not promote container')
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['prepare','migrate','rollback','run'])
    parser.add_argument('model',choices=SERVICES)
    args=parser.parse_args();model=args.model
    ROOT.mkdir(parents=True,exist_ok=True)
    saved=ROOT/(model+'.json');backup=ROOT/(SERVICES[model]+'.original')
    dropin=Path.home()/'.config/systemd/user'/(SERVICES[model]+'.d')/'50-hanni-docker.conf'
    if args.operation=='prepare':
        value=record(model)
        if saved.exists() or backup.exists():
            if not saved.exists() or not backup.exists() or json.loads(saved.read_text())['sha256']!=value['sha256'] or backup.read_bytes()!=Path(value['unit']).read_bytes():
                raise ValueError('Existing preparation differs; never overwrite another scope')
        image()
        devices=run(docker_args(value,probe=True),timeout=20).stdout.decode(errors='replace')
        expected='RX 9060' if model=='swift' else 'P6000' if model=='nex' else 'P40'
        if expected not in devices:raise ValueError('Assigned physical GPU not visible in container')
        if model=='swift':
            native=run([value['argv'][0],'--list-devices'],timeout=20).stdout.decode()
            original_device=value['argv'][value['argv'].index('-dev')+1]
            line=next(line for line in native.splitlines() if line.strip().startswith(original_device+':'))
            original_name=line.split(':',1)[1].strip().split(' (')[0]
            matches=[line.strip().split(':',1)[0] for line in devices.splitlines() if original_name in line]
            if len(matches)!=1 or expected not in original_name:raise ValueError('Assigned Vulkan GPU identity is ambiguous')
            value['container_device']=matches[0]
            value['physical_gpu']=original_name
        if not backup.exists():backup.write_bytes(Path(value['unit']).read_bytes())
        saved.write_text(json.dumps(value,indent=2))
        print(json.dumps({'model':model,'prepared':True,'gpu_probe':devices,'backup':str(backup)}));return
    value=json.loads(saved.read_text())
    if hashlib.sha256(Path(value['unit']).read_bytes()).hexdigest()!=value['sha256']:
        raise ValueError('Original unit changed; re-review before changing service')
    if args.operation=='run':
        os.execvp('docker',docker_args(value));return
    if args.operation=='rollback':
        run(['systemctl','--user','stop',SERVICES[model]])
        if dropin.exists():dropin.unlink()
        run(['systemctl','--user','daemon-reload']);run(['systemctl','--user','reset-failed',SERVICES[model]]);run(['systemctl','--user','start',SERVICES[model]])
        print(json.dumps({'model':model,'rollback_requested':True}));return
    if dropin.exists():raise ValueError('Existing Docker override must not be overwritten')
    health(model)
    with urllib.request.urlopen('http://127.0.0.1:'+str(PORTS[model])+'/slots',timeout=3) as response:
        slots=json.load(response)
    if not isinstance(slots,list) or any(slot.get('is_processing') for slot in slots):
        raise ValueError('Model has an active inference request; cutover was not attempted')
    override='[Service]\nExecStart=\nExecStart=/usr/bin/python3 '+str(Path(__file__).resolve())+' run '+model+'\nExecStop=\nExecStop=/usr/bin/docker --host unix:///var/run/docker.sock stop --time 30 hanni-model-'+model+'\n'
    # Stop just this original service. Systemd remains the sole restart owner.
    run(['systemctl','--user','stop',SERVICES[model]])
    try:
        dropin.parent.mkdir(exist_ok=True);dropin.write_text(override)
        run(['systemctl','--user','daemon-reload']);run(['systemctl','--user','start',SERVICES[model]])
        deadline=time.monotonic()+180
        while True:
            try:health(model);break
            except Exception:
                state=run(['systemctl','--user','show',SERVICES[model],'--property=ActiveState','--value']).stdout.decode().strip()
                if state=='failed':raise ValueError('Docker unit failed before readiness')
                if time.monotonic()>deadline:raise ValueError('Docker model failed to become ready')
                time.sleep(2)
        health(model,inference=True)
        info=json.loads(run(DOCKER+['inspect','hanni-model-'+model]).stdout)[0]
        print(json.dumps({'model':model,'docker_running':info['State']['Running'],'pid':info['State']['Pid'],
                          'model_identity_verified':True,'inference':'7','port':PORTS[model]}))
    except BaseException:
        run(['systemctl','--user','stop',SERVICES[model]])
        if dropin.exists():dropin.unlink()
        run(['systemctl','--user','daemon-reload']);run(['systemctl','--user','reset-failed',SERVICES[model]]);run(['systemctl','--user','start',SERVICES[model]])
        raise


if __name__=='__main__':main()
