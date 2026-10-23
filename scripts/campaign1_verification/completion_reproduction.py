"""Independent exposed compound-observation ledger boundary reproduction."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.mcp.host import McpHost
from hanni.evals.isolation import isolated_host
from hanni.mcp.completion import CompletionLedger
QUERIES = [('Inspect firewall and Defender status', 'security.firewall', 'security.defender'), ('For C:\\EvalFixture\\repo, report git status and recent commits.', 'git.status', 'git.log'), ('Inspect firewall and Defender status; provide current CPU and RAM percentages.', 'security.firewall', 'security.defender')]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    assert out.is_relative_to((ROOT / 'data/campaign1-verifier').resolve()) and (not out.exists())
    out.mkdir(parents=True)
    cfg = load_config(ROOT / 'config', data_dir=out / 'state', env={})
    reg = build_default_registry(cfg, data_dir=out / 'state')
    host = isolated_host(McpHost(reg, read_only=cfg.hanni.mcp.read_only, allowed_actions=cfg.hanni.mcp.allowed_actions, max_tools=8))
    rows = []
    for query, first, second in QUERIES:
        decision = host.route(query)
        ledger = CompletionLedger.from_request(host, query, decision=decision)
        before = ledger.to_dict()
        ledger.observe(first, {'name': first, 'ok': True, 'message': 'Controlled exposed receipt for this single observation only.', 'data': {}})
        rows.append({'query': query, 'menu': [t.capability_id for t in decision.tools], 'before': before, 'observed_single_receipt': first, 'missing_receipt': second, 'after': ledger.to_dict(), 'missing_receipt_still_pending': any((second in t.candidates for t in ledger.pending))})
    (out / 'results.json').write_text(json.dumps({'scope': 'original metadata and ledger only; no model/handler; receipts are controlled exposed test data', 'results': rows}, indent=2), encoding='utf8')
    from hanni.reliability.execution import close_service
    close_service(out / 'state')
    print(json.dumps(rows))
if __name__ == '__main__':
    main()
