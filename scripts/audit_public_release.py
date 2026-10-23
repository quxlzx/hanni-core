"""Offline publication audit. Findings contain locations and categories, never values."""
from __future__ import annotations
import argparse
from collections import Counter
import ipaddress
import json
from pathlib import Path
import re
import subprocess


PATTERNS = {
    'personal_email': re.compile(rb'(?<![A-Za-z0-9_.+-])[A-Za-z0-9_.+-]+@(?!(?:example\.(?:com|org|net|edu))\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}',re.I),
    'credential': re.compile(rb'(?<![A-Za-z0-9_-])(?:AIza[A-Za-z0-9_-]{30,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{30,}|glpat-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-(?:ant-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'credential_assignment': re.compile(rb'''(?:api[_-]?key|client_secret|refresh_token|access_token|password)\s*["']?\s*[:=]\s*["']([^"'\r\n]{16,})["']''',re.I),
    'authenticated_url': re.compile(rb'https?://[^\s/@]+:[^\s/@]+@'),
    'private_user_path': re.compile(rb'(?:[A-Za-z]:[\\/]+Users[\\/]+|/home/|/Users/)(?!user(?:name)?\b|example\b|me\b|YourName\b)[A-Za-z0-9_.-]+',re.I),
}
IP = re.compile(rb'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
IP6 = re.compile(rb'(?<![\w:])(?:[a-fA-F0-9]{0,4}:){2,7}[a-fA-F0-9]{0,4}(?![\w:])')
DOCUMENTATION = [ipaddress.ip_network(s) for s in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24','2001:db8::/32')]
STANDARD_NETWORKS = {'10.0.0.0/8','100.64.0.0/10','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','224.0.0.0/4','240.0.0.0/4','fc00::/7','fe80::/10'}
TEXT = {'.py','.md','.txt','.yaml','.yml','.json','.jsonl','.toml','.ps1','.sh','.cmd','.js','.cjs','.mjs','.ts','.tsx','.css','.html','.example','.ini','.cfg','.service'}
PUBLIC_ROLE_MAILBOXES={'onboarding','jobs','alerts','notify','ci','news','editor','intel','capitalone','reddit','info'}
PUBLIC_MAIL_DOMAINS={'intel.com','tiktok.com','nvidia.com','reddit.com','linkedin.com','github.com','myworkday.com','intelligence.com'}
PUBLIC_PERSONAL_PROVIDERS={'gmail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','live.com','aol.com','proton.me','protonmail.com'}


def synthetic_email(value):
    local,_,domain=value.decode('ascii',errors='ignore').lower().partition('@')
    return (domain.endswith(('.example','.test','.invalid','.localhost'))
            or (local in PUBLIC_ROLE_MAILBOXES and domain in PUBLIC_MAIL_DOMAINS)
            or (re.fullmatch(r'example-[0-9a-f]{10}',local) and domain in PUBLIC_PERSONAL_PROVIDERS))


def synthetic_auth_url(data,match):
    from urllib.parse import urlsplit
    end=re.match(rb'[A-Za-z0-9.-]+',data[match.end():])
    if not end:return False
    try:url=urlsplit((match.group()+end.group()).decode())
    except ValueError:return False
    return (url.username in {'user','username','owner','me','alice'} and url.password in {'pass','password','secret','SECRET','token'}
            and (url.hostname.endswith(('.example','.test','.invalid')) or url.hostname in {'example.com','example.org','example.net'}))


def findings(data, location):
    result = []
    for category, pattern in PATTERNS.items():
        if category=='personal_email' and any(s in location.lower() for s in ('license','ofl.txt','third_party_notices')):continue
        for match in pattern.finditer(data):
            if category=='personal_email' and synthetic_email(match.group()):continue
            if category=='authenticated_url' and synthetic_auth_url(data,match):continue
            if category == 'credential_assignment':
                value = match.group(1).lower()
                if value.startswith((b'fixture-',b'test-',b'example-',b'your-',b'<',b'${',b'{env:')):
                    continue
            result.append({'location':location,'line':data.count(b'\n',0,match.start())+1,'category':category})
    for pattern in (IP,IP6):
        for match in pattern.finditer(data):
            try: address=ipaddress.ip_address(match.group().decode())
            except ValueError: continue
            suffix=re.match(rb'/\d{1,3}',data[match.end():])
            if suffix and (match.group()+suffix.group()).decode() in STANDARD_NETWORKS:continue
            if address.is_loopback or address.is_unspecified or any(address.version==n.version and address in n for n in DOCUMENTATION):
                continue
            result.append({'location':location,'line':data.count(b'\n',0,match.start())+1,'category':'nonpublic_endpoint' if address.is_private or address in ipaddress.ip_network('100.64.0.0/10') else 'network_address'})
    return result


def audit_tree(root):
    root=Path(root)
    if (root/'.git').exists():
        names=subprocess.check_output(['git','-C',str(root),'ls-files','-z','--cached','--others','--exclude-standard']).decode().split('\0')
    else:
        names=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and not any(part in {'.git','node_modules','__pycache__','.venv'} for part in p.relative_to(root).parts)]
    result=[];count=0
    for name in sorted(set(names)):
        p=root/name
        if not name or not p.is_file() or p.is_symlink():continue
        if p.suffix in {'.zip','.whl','.pem','.key','.p12','.pfx','.sqlite','.sqlite3','.db'} or name=='.env' or name.startswith('data/'):
            result.append({'location':name,'line':0,'category':'private_or_archive_file'})
            continue
        if p.suffix.lower() not in TEXT and p.name not in {'.env.example','Dockerfile','.gitignore','LICENSE','MANIFEST.in'}:continue
        count+=1
        result.extend(findings(p.read_bytes(),name))
    return {'files_scanned':count,'findings':result}


def audit_history(root):
    objects=subprocess.check_output(['git','-C',str(root),'rev-list','--objects','--all']).decode().splitlines()
    result=[];count=0
    process=subprocess.Popen(['git','-C',str(root),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for row in objects:
            oid,_,name=row.partition(' ')
            process.stdin.write((oid+'\n').encode());process.stdin.flush()
            header=process.stdout.readline().decode().split()
            if len(header)!=3:raise RuntimeError('Unable to read Git object.')
            size=int(header[2]);data=process.stdout.read(size);process.stdout.read(1)
            if header[1] not in {'blob','commit','tag'}:continue
            count+=1
            if b'\0' in data[:8192]:continue
            observed=findings(data,'git:'+oid+':'+name)
            if header[1]!='blob':observed=[f for f in observed if f['category']!='personal_email']
            result.extend(observed)
    finally:
        process.stdin.close();process.stdout.close();process.wait(timeout=10)
    return {'blobs_scanned':count,'findings':result}


def audit_known_local_secrets(root):
    """Compare existing private token material in memory; never serialize it."""
    root=Path(root);secrets=[]
    token=root/'data/hermes/bridge.token'
    if token.is_file():
        value=token.read_bytes().strip()
        if len(value)>=12:secrets.append(value)
    env=root/'.env'
    if env.is_file():
        for line in env.read_bytes().splitlines():
            key,sep,value=line.partition(b'=')
            if sep and re.search(rb'(?:TOKEN|KEY|SECRET|PASSWORD)$',key.strip(),re.I):
                value=value.strip().strip(b'"\'')
                if len(value)>=12:secrets.append(value)
    names=subprocess.check_output(['git','-C',str(root),'ls-files','-z','--cached','--others','--exclude-standard']).decode().split('\0')
    result=[]
    for name in names:
        path=root/name
        if not name or not path.is_file() or path.is_symlink():continue
        data=path.read_bytes()
        if any(secret in data for secret in secrets):
            result.append({'location':name,'line':0,'category':'known_local_secret'})
    objects=subprocess.check_output(['git','-C',str(root),'rev-list','--objects','--all']).decode().splitlines()
    proc=subprocess.Popen(['git','-C',str(root),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for row in objects:
            oid,_,name=row.partition(' ')
            proc.stdin.write((oid+'\n').encode());proc.stdin.flush()
            head=proc.stdout.readline().decode().split();size=int(head[2])
            data=proc.stdout.read(size);proc.stdout.read(1)
            if head[1]=='blob' and any(secret in data for secret in secrets):
                result.append({'location':'git:'+oid+':'+name,'line':0,'category':'known_local_secret'})
    finally:
        proc.stdin.close();proc.stdout.close();proc.wait(timeout=10)
    return {'private_values_compared':len(secrets),'findings':result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--history',action='store_true')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    report={'tree':audit_tree(args.root)}
    if args.history:
        report['history']=audit_history(args.root)
        report['known_local_secrets']=audit_known_local_secrets(args.root)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    for section,data in report.items():
        print(section,json.dumps(dict(Counter(f['category'] for f in data['findings']))))
    return 1 if any(data['findings'] for data in report.values()) else 0


if __name__=='__main__':raise SystemExit(main())
