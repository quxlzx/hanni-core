"""Coordinator-GO-only final collection; inputs never reach an oracle or scorer."""
from contextlib import ExitStack
import argparse
from copy import deepcopy
import json
from pathlib import Path
import traceback
from .adapter import collect_once
from .contracts import receipt_observation
from .integrity import assert_freeze, verify_go
ROOT = Path(__file__).resolve().parents[2]

def collect(freeze_path, go_path):
    private = ROOT / 'data/campaign10-verifier'
    freeze = json.loads(Path(freeze_path).read_text(encoding='utf-8'))
    seal = json.loads((private / 'SEAL.json').read_text(encoding='utf-8'))
    go = json.loads(Path(go_path).read_text(encoding='utf-8'))
    verify_go(go, assert_freeze(ROOT, freeze), seal['input_sha256'])
    from scripts.campaign10_manager.model import ModelBudget
    from scripts.campaign10_manager.live import execute_case
    budget = ModelBudget(private / 'final-model')
    transport = ExitStack()
    admitted = False

    def executor(case, root):
        nonlocal admitted
        start = len(budget.wire)
        try:
            if not admitted:
                transport.enter_context(budget.transport())
                admitted = True
            row = execute_case(case, root, budget)
        except Exception as exc:
            row = {'id': case['id'], 'evidence_categories': ['BLOCKED'], 'error': {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}, 'request_path_original': False, 'actual_generated': len(budget.wire) > start, 'mock_model': False}
        wires = []
        for record in budget.wire[start:]:
            wire = deepcopy({key: value for key, value in record.items() if key != '_raw'})
            wire['raw_response'] = bytes(record.get('_raw', b'')).decode('utf-8', errors='replace')
            wires.append(wire)
        row['actual_generation_wire'] = wires
        row['actual_model_calls'] = len(wires)
        row['selection_eligible'] = any((bool(wire['request_body'].get('tools')) for wire in wires))
        usage = []
        for wire in wires:
            text = wire['raw_response']
            chunks = [line[6:] for line in text.splitlines() if line.startswith('data: ')] if text.startswith('data:') else [text]
            observed = []
            for chunk in chunks:
                try:
                    payload = json.loads(chunk)
                except (ValueError, TypeError):
                    continue
                item = payload.get('usage') if isinstance(payload, dict) else None
                if isinstance(item, dict) and type(item.get('total_tokens')) is int:
                    observed.append(item['total_tokens'])
            if observed:
                usage.append(max(observed))
        row['usage_measurement'] = 'COMPLETE_REPORTED_USAGE' if len(usage) == len(wires) and wires else 'NOT_MEASURED_OR_PARTIAL'
        if wires and len(usage) == len(wires):
            row['observed_tokens'] = sum(usage)
        budget.save()
        return receipt_observation(row)
    try:
        return collect_once(ROOT, private, freeze_path, go_path, executor)
    finally:
        transport.close()
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--go', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.freeze, args.go)))
