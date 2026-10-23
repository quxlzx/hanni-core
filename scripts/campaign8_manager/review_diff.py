"""Compare candidate bytes with archived original; distinguish authorized UI changes."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def main():
    baseline = json.loads((ROOT / 'data/campaign8-manager/PREFLIGHT.json').read_text(encoding='utf-8'))
    changed, missing = ([], [])
    for name, old in baseline['source_manifest'].items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
            continue
        now = hashlib.sha256(path.read_bytes()).hexdigest()
        if now != old:
            changed.append({'path': name, 'before': old, 'after': now, 'authorized_ui_scope': name.startswith('frontend/src/') or name.startswith('src/hanni/dashboard/static/')})
    protected_bad = []
    for name, old in baseline['protected'].items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != old:
            protected_bad.append(name)
    result = {'changed_originals': changed, 'missing_originals': missing, 'unauthorized_original_changes': [row['path'] for row in changed if not row['authorized_ui_scope'] and row['path'] != 'src/hanni/dashboard/server.py' and (not row['path'].startswith(('scripts/campaign8_', 'tests/integration/test_campaign8')))], 'protected_prior_campaign_or_owner_changed': protected_bad}
    out = ROOT / 'data/campaign8-manager/CANDIDATE_DIFF.json'
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'changed_original_paths': [row['path'] for row in changed], 'missing': missing, 'unauthorized': result['unauthorized_original_changes'], 'protected_changed': protected_bad}, indent=2))
if __name__ == '__main__':
    main()
