#!/bin/sh
set -eu
test "$(id -u)" -ne 0 || { echo 'Run as the configured Hermes owner account; no sudo needed.'; exit 1; }
bridge="$HOME/hanni-hermes-bridge"
source_root="$HOME/.hermes/hermes-agent"
launcher="$HOME/.local/bin/hermes"
test -d "$bridge/lib/hanni/hermes"
test -x "$launcher"
test -f "$HOME/.hermes/config.yaml"
test -f "$bridge/OWNER" && test "$(cat "$bridge/OWNER")" = 'hanni-hermes-v1'
if test -e "$source_root/hanni_hermes_adapter.py"; then
    cmp -s "$bridge/deployment/hanni_hermes_adapter.py" "$source_root/hanni_hermes_adapter.py" || { echo 'Adapter differs from owned staged source; review before updating.'; exit 1; }
fi
test ! -e "$HOME/.config/systemd/user/hanni-hermes-bridge.service" || { echo 'Unit already exists: review before applying changes.'; exit 1; }
cp "$bridge/deployment/hanni_hermes_adapter.py" "$source_root/hanni_hermes_adapter.py"
"$launcher" --run-module hanni_hermes_adapter check
python3 - "$bridge" <<'PY'
import pathlib,secrets,socket,os,sys
root=pathlib.Path(sys.argv[1])
with socket.socket() as probe:
    probe.bind(('127.0.0.1',8092))
token=root/'bridge.token'
if not token.exists():
    fd=os.open(token,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(48))
os.chmod(root,0o700)
PY
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/hanni-hermes-bridge.service" <<EOF
[Unit]
Description=HANNI scoped Hermes task bridge (not a messaging gateway)
After=network-online.target
[Service]
Type=simple
WorkingDirectory=$source_root
ExecStart=$launcher --run-module hanni_hermes_adapter service --root $bridge/state --hermes-config $HOME/.hermes/config.yaml --token-file $bridge/bridge.token --port 8092 --shared-root $HOME/hanni-capabilities/data --worker-launcher $launcher
Restart=on-failure
RestartSec=10
TimeoutStopSec=12
KillMode=control-group
NoNewPrivileges=yes
UMask=0077
MemoryMax=2G
TasksMax=128
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now hanni-hermes-bridge.service
python3 - "$bridge" <<'PY'
import pathlib,sys,json,http.client,time
root=pathlib.Path(sys.argv[1]);token=(root/'bridge.token').read_text().strip()
for _ in range(30):
    try:
        c=http.client.HTTPConnection('127.0.0.1',8092,timeout=2)
        c.request('GET','/health',headers={'Authorization':'Bearer '+token})
        r=c.getresponse();data=json.loads(r.read());c.close()
        if r.status==200 and data.get('protocol')==1:break
    except OSError:time.sleep(.2)
else:raise SystemExit('Bridge health gate failed; inspect the bridge unit without dumping credentials.')
print('Loopback bridge healthy. The existing Discord gateway was not restarted.')
sys.path.insert(0,str(root/'lib'))
from hanni.hermes.catalog import SEED
c=http.client.HTTPConnection('127.0.0.1',8092,timeout=5)
c.request('GET','/catalog',headers={'Authorization':'Bearer '+token})
r=c.getresponse();catalog=json.loads(r.read());c.close()
if catalog['revision']==0:
    c=http.client.HTTPConnection('127.0.0.1',8092,timeout=5)
    c.request('POST','/catalog',body=json.dumps({'revision':0,'entries':SEED,'id':'installation-seed-v1','adopt_seed':True}),
              headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    r=c.getresponse();result=json.loads(r.read());c.close()
    if r.status!=200 or result.get('sync_error'):raise SystemExit('Catalog requires conflict review; no gateway restart performed.')
print('Three existing MCP endpoints registered in the canonical catalog; tool approvals unchanged.')
c=http.client.HTTPConnection('127.0.0.1',8092,timeout=5)
c.request('GET','/catalog',headers={'Authorization':'Bearer '+token})
r=c.getresponse();catalog=json.loads(r.read());c.close()
from hanni.hermes.catalog import connection_hash
for entry in catalog['entries']:
    if entry['name'] not in {item['name'] for item in SEED}:continue
    c=http.client.HTTPConnection('127.0.0.1',8092,timeout=5)
    c.request('POST','/catalog/connection',body=json.dumps({'name':entry['name'],'expected_hash':connection_hash(entry),'approve':True}),
              headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    r=c.getresponse();r.read();c.close()
    if r.status!=200:raise SystemExit('Existing-server discovery approval could not be recorded.')
print('Recorded the requested discovery permission for the three existing verified servers only.')
PY
