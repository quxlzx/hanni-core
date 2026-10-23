"""Independent development variations for resource/entity/context precedence."""
import argparse
import json
import re
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.mcp.host import McpHost
from hanni.evals.isolation import isolated_host
CASES = [('qwen-placement', 'Is Qwen actually on the GPU for this HANNI session?', ['model.status']), ('hanni-placement', 'Which GPU is running Hanni inference?', ['model.status']), ('model-observation', 'Report where the HANNI model is executing.', ['model.status']), ('first-person-memory', 'I am concerned about the RAM load. Could you check its current percentage?', ['system.stats']), ('first-person-cpu', 'I notice the CPU remains busy, which process accounts for most of it?', ['process.top_cpu']), ('permission-question', 'May you remove a file without my approval?', ['hanni.permissions']), ('comma-gpu', 'My graphics memory is full, find the biggest consumers.', ['gpu.top_processes']), ('comma-io', 'My file copies are taking ages, identify the process doing the most disk reads and writes.', ['process.top_disk_io']), ('comma-memory', 'RAM usage looks excessive, identify its largest process consumers.', ['process.top_memory']), ('local-hanni', 'Is Hanni running locally on this computer?', ['model.status']), ('quant-hanni', 'Which quantization is Hanni running today?', ['model.status']), ('mixed-qwen', 'Tell me my upcoming appointment and whether Qwen is running.', ['google_calendar.next', 'model.status']), ('permissions-explanation', 'Explain the limits of your permission to write my documents.', ['hanni.permissions']), ('memory-remaining', 'Why do I have less than a gigabyte of memory remaining?', ['process.top_memory']), ('comma-ram-culprit', 'My RAM use rose dramatically, identify the culprit.', ['process.top_memory']), ('comma-cpu-culprit', 'CPU load shot up, show its main culprit.', ['process.top_cpu']), ('named-memory', 'How much memory is mspaint.exe using right now?', ['process.find']), ('named-cpu', 'Inspect the CPU use of notepad.exe.', ['process.find']), ('hanni-gpu-public', 'what gpu is hanni running on', ['model.status']), ('llama-local-public', 'is llama running locally', ['model.status'])]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    assert out.is_relative_to((ROOT / 'data/campaign1-verifier').resolve()) and (not out.exists())
    out.mkdir(parents=True)
    cfg = load_config(ROOT / 'config', data_dir=out / 'state', env={})
    reg = build_default_registry(cfg, data_dir=out / 'state')
    host = isolated_host(McpHost(reg, read_only=cfg.hanni.mcp.read_only, allowed_actions=cfg.hanni.mcp.allowed_actions, max_tools=8))
    public = ROOT / 'data/campaign1-manager/cycle1-routing/regressions-vs-baseline.json'
    exposed = list(CASES)
    if public.exists():
        for row in json.loads(public.read_text(encoding='utf8')):
            required = list(dict.fromkeys((m.group(1) for reason in row['reasons'] for m in re.finditer('missing required capability ([\\w.]+)', reason))))
            exposed.append(('old-public-' + row['id'], row['query'], required))
    rows = []
    for ident, query, wanted in exposed:
        d = host.route(query)
        names = [t.capability_id for t in d.tools]
        rows.append({'id': 'independent-context-' + ident, 'query': query, 'expected_groups': [[n] for n in wanted], 'menu': names, 'status': d.status, 'required_groups': getattr(d, 'required_groups', ()), 'passed': all((n in names for n in wanted))})
    (out / 'results.json').write_text(json.dumps({'scope': 'independent exposed development metadata only; no model/handler', 'results': rows}, indent=2), encoding='utf8')
    from hanni.reliability.execution import close_service
    close_service(out / 'state')
    print(json.dumps(rows))
if __name__ == '__main__':
    main()
