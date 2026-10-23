"""Prepared Docker launcher for Wonyoung; requires usable Docker first.

Reuse the exact installed Strata, ROCm SDK, model packs and protected config.
No download, privilege mode, new port, model change or alternative manager.
"""
import json
import os
from pathlib import Path
import subprocess
import io
import tarfile
import socket

BASE=Path('/home/user/Strata')
DATA=Path('/home/user/Strata-data')
DOCKER=['docker','--host','unix:///var/run/docker.sock']
IMAGE='hanni-strata-runtime:existing-libraries-v1'


def command():
    cfg=BASE/'strata-iq3_s.json'
    settings=json.loads(cfg.read_text())
    if settings.get('port')!=8080 or settings.get('host')!='0.0.0.0' or not settings.get('api_key'):
        raise ValueError('Original private Strata endpoint/auth binding differs; review it before launch')
    log=Path(settings['log'])
    if log!=BASE/'strata-iq3_s.log' or not log.is_file():
        raise ValueError('Expected existing Strata log is unavailable')
    args=DOCKER+['run','--rm','--name','hanni-strata','--label','org.hanni.owner=control-center',
        '--label','org.hanni.service=strata','--network','host','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges','--user',str(os.getuid())+':'+str(os.getgid()),
        '--group-add',str(Path('/dev/kfd').stat().st_gid),
        '--device','/dev/kfd','--device','/dev/dri/renderD128',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=256m','--pids-limit','256','--stop-timeout','45',
        '--workdir',str(BASE),'--env','PYTHONDONTWRITEBYTECODE=1']
    sdk=BASE/'.venv/lib/python3.14/site-packages'
    lib=sdk/'_rocm_sdk_libraries_gfx110X_dgpu/lib'
    args+=['--env','ROCBLAS_TENSILE_LIBPATH='+str(lib/'rocblas/library'),
           '--env','HIPBLASLT_TENSILE_LIBPATH='+str(lib/'hipblaslt/library')]
    for path in ['/usr','/lib','/lib64','/etc/ld.so.cache','/etc/alternatives',str(BASE),str(DATA)]:
        if Path(path).exists():args+=['--mount','type=bind,src='+path+',dst='+path+',readonly']
    args+=['--mount','type=bind,src='+str(log)+',dst='+str(log)]
    return args+[IMAGE,str(BASE/'.venv/bin/python'),str(BASE/'serve/server.py'),
                 '--engine','strata','--config',str(cfg),'--port','8080']


def main():
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',8080))==0:
            raise ValueError('Original Strata port is occupied; no duplicate model was launched')
    subprocess.run(DOCKER+['info'],check=True,stdout=subprocess.DEVNULL)
    existing=subprocess.run(DOCKER+['image','inspect',IMAGE],capture_output=True)
    if existing.returncode:
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w'):pass
        subprocess.run(DOCKER+['import','--change','LABEL org.hanni.runtime=existing-libraries-v1','-',IMAGE],
                       input=payload.getvalue(),check=True,stdout=subprocess.DEVNULL)
    else:
        value=json.loads(existing.stdout)[0]
        if value.get('Config',{}).get('Labels',{}).get('org.hanni.runtime')!='existing-libraries-v1':
            raise ValueError('Runtime image belongs to an unrelated deployment')
    os.execvp('docker',command())


if __name__=='__main__':main()
