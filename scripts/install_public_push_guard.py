"""Install a local privacy gate without replacing an existing Git hook."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
configured=subprocess.run(['git','-C',str(root),'config','--get','core.hooksPath'],capture_output=True,text=True)
if configured.returncode==0:
    raise SystemExit('Existing custom hooks retained. Integrate the privacy audit manually.')
relative=subprocess.check_output(['git','-C',str(root),'rev-parse','--git-path','hooks/pre-push'],text=True).strip()
path=(root/relative).resolve()
if not path.is_relative_to(root) or path.exists():
    raise SystemExit('Existing or external hook retained; no overwrite performed.')
path.parent.mkdir(parents=True,exist_ok=True)
path.write_bytes(b'#!/bin/sh\nset -eu\ncd "$(git rev-parse --show-toplevel)"\npython scripts/audit_public_release.py --history --report data/public-release/pre-push-audit.json\n')
path.chmod(0o755)
print('Local pre-push privacy gate installed. Nothing pushed.')
