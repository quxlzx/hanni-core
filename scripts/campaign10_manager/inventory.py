"""Fresh original registry metadata compared with the audited public inventory."""
from collections import Counter
import json
from pathlib import Path
from scripts.campaign9_tools.harness import environment, inventory
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign10-manager'

def main():
    root = OUT / 'inventory-state'
    if root.exists():
        raise FileExistsError('Preserve inventory evidence.')
    with environment(root) as state:
        rows = inventory(state)
    prior = json.loads((ROOT / 'docs/campaign2/INVENTORY.json').read_text(encoding='utf8'))
    (OUT / 'INVENTORY.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf8')
    summary = {'registered_capabilities': len(rows), 'source_modules': dict(Counter((r['module'] for r in rows))), 'evidence_scope': 'Original registry enumeration; prior C2 scorecard retained separately from C10 task execution', 'prior_inventory_type': type(prior).__name__, 'current_ids': [r['id'] for r in rows]}
    (OUT / 'INVENTORY_SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'registered': len(rows), 'modules': len(summary['source_modules'])}))
if __name__ == '__main__':
    main()
