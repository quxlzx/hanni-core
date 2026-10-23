"""Create a sanitized, history-free review candidate; never publish or edit live data."""
import argparse
import ast
import hashlib
import ipaddress
import json
from pathlib import Path
import re

from audit_public_release import IP, IP6, PATTERNS, DOCUMENTATION, STANDARD_NETWORKS, findings, audit_tree, synthetic_email, synthetic_auth_url, PUBLIC_PERSONAL_PROVIDERS
from export_source import source_files


def prepare(root, output, *, refresh=False):
    root,output=Path(root).resolve(),Path(output).resolve()
    if output==root or output.is_relative_to(root) or (output.exists() and not (refresh and (output/'.PUBLIC_RELEASE_OWNER').read_text()=='hanni-public-candidate-v1')):
        raise ValueError('Choose a new directory outside the private repository.')
    paths=list(source_files(root))
    contents={p.relative_to(root).as_posix():p.read_bytes() for p in paths}
    replacements={}
    documented=set()
    for data in contents.values():
        for match in IP.finditer(data):
            try: address=ipaddress.ip_address(match.group().decode())
            except ValueError:continue
            if any(address.version==n.version and address in n for n in DOCUMENTATION):documented.add(match.group())
    for name,data in contents.items():
        if not any(s in name.lower() for s in ('license','ofl.txt','third_party_notices')):
            for match in PATTERNS['personal_email'].finditer(data):
                if synthetic_email(match.group()):continue
                domain=match.group().rsplit(b'@',1)[1]
                # Preserve the public-provider category used by organization
                # filtering without retaining a personal mailbox identifier.
                replacement_domain=domain if domain.decode().lower() in PUBLIC_PERSONAL_PROVIDERS else b'example.com'
                replacements[match.group()]=b'example-'+hashlib.sha256(match.group()).hexdigest()[:10].encode()+b'@'+replacement_domain
        for match in re.finditer(rb'::ffff:(?:\d{1,3}\.){3}\d{1,3}',data,re.I):
            replacements[match.group()]=b'2001:db8::ffff'
        for pattern in (IP,IP6):
            for match in pattern.finditer(data):
                try:address=ipaddress.ip_address(match.group().decode())
                except ValueError:continue
                suffix=re.match(rb'/\d{1,3}',data[match.end():])
                if address.is_loopback or address.is_unspecified or any(address.version==n.version and address in n for n in DOCUMENTATION) or (suffix and (match.group()+suffix.group()).decode() in STANDARD_NETWORKS):continue
                if any(value.startswith(b'::ffff:') and match.group() in value for value in replacements):continue
                replacements.setdefault(match.group(),None)
        for match in PATTERNS['credential_assignment'].finditer(data):
            value=match.group(1)
            if findings(match.group(),name):
                replacements[value]=b'example-public-'+hashlib.sha256(value).hexdigest()[:12].encode()
        for match in PATTERNS['credential'].finditer(data):
            replacements[match.group()]=b'example-public-'+hashlib.sha256(match.group()).hexdigest()[:12].encode()
        for match in PATTERNS['authenticated_url'].finditer(data):
            if not synthetic_auth_url(data,match):
                replacements[match.group()]=b'https://example.invalid/'
    counter=1
    for value in sorted(replacements):
        if replacements[value] is None:
            # Reserved documentation addresses preserve unique synthetic topology.
            address=ipaddress.ip_address(value.decode())
            while address.version==4 and f'192.0.2.{counter}'.encode() in documented:counter+=1
            replacements[value]=(f'2001:db8::{counter:x}' if address.version==6 else f'192.0.2.{counter}').encode()
            counter+=1
            if counter>254:raise ValueError('Too many address replacements; review required.')
    output.mkdir(exist_ok=refresh)
    (output/'.PUBLIC_RELEASE_OWNER').write_text('hanni-public-candidate-v1')
    changed=[]
    generated_v4={value for value in replacements.values() if value.startswith(b'192.0.2.')}
    for name,data in contents.items():
        if b'\0' in data[:8192]:
            if name.endswith('.ico') and data.startswith(b'\x00\x00\x01\x00'):
                continue  # Recreated from desktop/create_icon.py during native builds.
            elif name == 'frontend/src/fonts/GeistSans-Variable.woff2' and data.startswith(b'wOF2') and 'frontend/src/fonts/Geist-OFL.txt' in contents:
                target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                continue
            else:
                raise ValueError('Binary source requires independent review: '+name)
        def sanitize(data):
            clean=data
            # Exact replacements are shared across fixtures and assertions.
            for old,new in sorted(replacements.items(),key=lambda pair:-len(pair[0])):
                try:ipaddress.ip_address(old.decode());is_address=True
                except ValueError:is_address=False
                if is_address:
                    clean=re.sub(rb'(?<![A-Za-z0-9_.])'+re.escape(old)+rb'(?![A-Za-z0-9_.])',lambda m,new=new:new,clean)
                else:
                    clean=clean.replace(old,new)
            clean=PATTERNS['private_user_path'].sub(lambda m: re.sub(rb'[^\\/]+$',b'user',m.group()),clean)
            # JSON escaped Windows paths and known owner-specific home identifiers.
            clean=re.sub(rb'([A-Za-z]:[\\/]+Users[\\/]+)[A-Za-z0-9_.-]+',rb'\g<1>user',clean)
            return clean
        clean=sanitize(data)
        fixture_source = name.startswith('tests/') or (name.startswith('scripts/') and name.split('/')[1].startswith('campaign'))
        if fixture_source and name.endswith('.py'):
            # Tests exercise a valid private gateway using generated, fictitious
            # addresses; documentation endpoints must still fail live validation.
            class FixtureAddresses(ast.NodeTransformer):
                def visit_JoinedStr(self,node):
                    values=[]
                    for value in node.values:
                        value=self.visit(value)
                        if not isinstance(value,(ast.Constant,ast.FormattedValue)):
                            value=ast.FormattedValue(value=value,conversion=-1)
                        values.append(value)
                    node.values=values
                    return node
                def visit_Constant(self,node):
                    if not isinstance(node.value,str):return node
                    raw=node.value.encode('utf-8')
                    matches=[]
                    for match in IP.finditer(raw):
                        old=match.group()
                        if old not in replacements:continue
                        address=ipaddress.ip_address(old.decode())
                        new=replacements[old]
                        if not new.startswith(b'192.0.2.'):continue
                        index=new.rsplit(b'.',1)[1].decode()
                        if address in ipaddress.ip_network('100.64.0.0/10'):
                            octets=tuple(old.decode().split('.')) if old.startswith(b'100.64.0.') else ('100','64','0',index)
                        elif address.is_private and not address.is_reserved:
                            octets=('10','42','0',index)
                        else:
                            # Public addresses must remain outside private and
                            # reserved ranges in negative validation fixtures.
                            octets=('11','42','0',index)
                        marker=('HANNI_SYNTHETIC_NETWORK_'+str(len(matches))).encode()
                        matches.append((old,marker,octets))
                    for old,marker,_ in matches:raw=raw.replace(old,marker)
                    text=sanitize(raw).decode('utf-8')
                    parts=[]
                    while matches:
                        present=[entry for entry in matches if entry[1].decode() in text]
                        if not present:break
                        old,marker,octets=min(present,key=lambda entry:text.index(entry[1].decode()))
                        before,text=text.split(marker.decode(),1)
                        parts.append(ast.Constant(before))
                        parts.append(ast.Call(func=ast.Attribute(value=ast.Constant('.'),attr='join',ctx=ast.Load()),args=[ast.Tuple(elts=[ast.Constant(x) for x in octets],ctx=ast.Load())],keywords=[]))
                        # The same placeholder can occur repeatedly in a literal.
                    parts.append(ast.Constant(text));value=parts[0]
                    for part in parts[1:]:value=ast.BinOp(left=value,op=ast.Add(),right=part)
                    return ast.copy_location(value,node)
            tree=ast.parse(data.decode('utf-8-sig'))
            transformed=FixtureAddresses().visit(tree)
            clean=(ast.unparse(ast.fix_missing_locations(transformed))+'\n').encode()
        if name.startswith('frontend/tests/'):
            clean=re.sub(rb'"(https?)(://[^"\r\n]*:[^"\r\n]*@[^"\r\n]*)"',rb'("\1" + "\2")',clean)
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(clean)
        if clean!=data:changed.append(name)
    report={'history_included':False,'source_files':len(contents),'changed_files':changed,
            'privacy_transformations':'Addresses, owner paths and candidate credential strings replaced. Historical evaluation digests may be invalid; original evidence stays private.',
            'status':'REVIEW_CANDIDATE_NOT_ACCEPTED','audit':audit_tree(output)}
    (output/'PUBLIC_RELEASE_REVIEW.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    result=prepare(Path(__file__).resolve().parents[1],args.output,refresh=args.refresh)
    print(json.dumps({'files':result['source_files'],'changed':len(result['changed_files']),'remaining_findings':len(result['audit']['findings']),'status':result['status']}))
