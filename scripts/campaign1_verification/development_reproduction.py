"""Independent exposed-development routing reproduction, never final cases."""
import json
import sys
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.mcp.host import McpHost
from hanni.evals.isolation import isolated_host
IDS = ['telemetry_snapshot-08', 'process_cpu-10', 'file_analysis-07', 'educational_no_tool-01', 'quoted_data_and_mixed_intent-03', 'security_observation-03', 'compound_evidence_requests-07', 'compound_evidence_requests-03']
VARIATIONS = [('memory-with-no-mutation', 'Read the current memory percentage; please do not end any running task.', ['system.stats']), ('process-read-only', 'Inspect PID 4180 and explain its details. This grants no permission to terminate it.', ['process.inspect']), ('archive-list-only', 'Show the entries in C:\\EvalFixture\\bundle.zip, leaving its contents compressed.', ['archive.list']), ('definition', 'What does RAM utilization mean, conceptually? I am asking for a definition. ', []), ('quotation', 'In the sentence "open Spotify and play music", identify the verbs. Do not control an app.', []), ('physical-encryption', 'Is the C: local volume encrypted with BitLocker?', ['security.bitlocker']), ('two-security-observations', 'Report the current firewall settings and the Defender protection status.', ['security.firewall', 'security.defender']), ('two-git-observations', 'For C:\\EvalFixture\\repo, list recent git commits and identify dirty working-tree files.', ['git.log', 'git.status'])]

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    assert out.is_relative_to((ROOT / 'data/campaign1-verifier').resolve()) and (not out.exists())
    out.mkdir(parents=True)
    cfg = load_config(ROOT / 'config', data_dir=out / 'state', env={})
    reg = build_default_registry(cfg, data_dir=out / 'state')
    base = McpHost(reg, read_only=cfg.hanni.mcp.read_only, allowed_actions=cfg.hanni.mcp.allowed_actions, max_tools=8, timezone_name=cfg.hanni.user.timezone)
    cases = [json.loads(x) for x in (ROOT / 'evals/campaign1/development.jsonl').read_text(encoding='utf8').splitlines()]
    rows = []
    for c in cases:
        if not any((c['id'].endswith(x) for x in IDS)):
            continue
        actions = cfg.hanni.mcp.allowed_actions if c['fixture']['routing_profile'] == 'owner' else c['fixture']['allowed_actions']
        h = isolated_host(base, allowed_actions=actions)
        d = h.route(c['query'], history=c.get('history', []), now=datetime.fromisoformat(c['fixture']['now']))
        rows.append({'id': c['id'], 'query': c['query'], 'status': d.status, 'menu': [t.capability_id for t in d.tools], 'expected': c['expected']['menu']['essential_groups']})
    for ident, q, names in VARIATIONS:
        h = isolated_host(base)
        d = h.route(q, now=datetime.fromisoformat('2026-10-12T10:15:00-04:00'))
        rows.append({'id': 'independent-dev-' + ident, 'query': q, 'status': d.status, 'menu': [t.capability_id for t in d.tools], 'expected': [[n] for n in names]})
    (out / 'results.json').write_text(json.dumps({'scope': 'original metadata only, no handlers/model; exposed development and independent development variations', 'results': rows}, indent=2), encoding='utf8')
    print(json.dumps({'output': str(out), 'cases': len(rows), 'results': [{k: v for k, v in r.items() if k != 'query'} for r in rows]}))
    from hanni.reliability.execution import close_service
    close_service(out / 'state')
if __name__ == '__main__':
    main()
