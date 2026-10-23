"""Publish hash-only prospective metadata, without opening production services."""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

def main() -> None:
    workspace = Path(__file__).resolve().parents[2]
    private = workspace / 'data/campaign9-verifier/holdout'
    destination = workspace / 'docs/campaign9/FINAL_SEAL.json'
    if destination.exists() or (private / 'SEAL.json').exists():
        raise SystemExit('Refusing to replace an independent prospective seal')
    inputs = json.loads((private / 'inputs.json').read_text(encoding='utf8'))
    oracles = json.loads((private / 'oracles.json').read_text(encoding='utf8'))
    protocol = json.loads((private / 'protocol.json').read_text(encoding='utf8'))
    assert [row['id'] for row in inputs] == [row['id'] for row in oracles]
    areas = collections.Counter((row['area'] for row in inputs))
    faults = collections.Counter((fault for row in inputs for fault in row['fault_categories']))
    assert len(inputs) == 60 and len(areas) == 20 and (min(areas.values()) == 3)
    assert set(faults) == set(protocol['fault_categories'])
    pins = {name: hashlib.sha256((private / name).read_bytes()).hexdigest() for name in ('author.py', 'inputs.json', 'oracles.json', 'protocol.json')}
    payload = {'campaign': 9, 'sealed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'case_count': len(inputs), 'security_area_count': len(areas), 'security_area_counts': dict(sorted(areas.items())), 'fault_category_count': len(faults), 'fault_category_counts': dict(sorted(faults.items())), 'private_file_sha256': pins, 'seal_kind': 'prospective independent controlled security cases and separate oracles', 'production_case_executions_before_seal': 0, 'final_execution_authorized': False, 'final_execution_rule': 'complete once only after explicit root source freeze and GO', 'root_and_engineer_access_to_private_cases': False, 'unsupported_or_unmeasured_scopes_cannot_pass': True, 'synthetic_credentials_only': True, 'real_provider_or_hardware_success_claims': False, 'inputs_and_oracles_must_remain_unchanged': True}
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + '\n').encode('utf8')
    (private / 'SEAL.json').write_bytes(encoded)
    destination.write_bytes(encoded)
    print(json.dumps({'public_seal': str(destination), 'sha256': hashlib.sha256(encoded).hexdigest(), 'cases': len(inputs), 'areas': len(areas), 'fault_categories': len(faults)}))
if __name__ == '__main__':
    main()
