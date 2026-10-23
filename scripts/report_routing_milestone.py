"""Summarize captured results without rerunning the old router or changing scores.

Only the documented GPU-domain annotation correction is applied to captured
baseline selections. All original target, precision and date checks are retained.
"""
import json
from collections import defaultdict
from pathlib import Path

from hanni.evals.routing import _domain, build_default_host
from hanni.tools.capabilities import describe
from hanni.tools.capability_api import risk_of


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['family']].append(row)
    return dict(total=len(rows), pass_rate=round(100 * sum(r['passed'] for r in rows) / len(rows), 2),
                families={family: dict(cases=len(items), pass_rate=round(100*sum(r['passed'] for r in items)/len(items), 2))
                          for family, items in sorted(groups.items())})


def main():
    root = Path('evals/routing')
    before = json.loads((root/'before.json').read_text())
    after = json.loads((root/'after.json').read_text())
    cases = {r['id']: r for r in map(json.loads, (root/'cases.jsonl').read_text().splitlines())}
    corrected = []
    adjusted = []
    for original in before['results']:
        row = dict(original)
        case = cases[row['id']]
        if case.get('primary') == 'gpu.top_processes' and any('expected domain process' in reason for reason in row['reasons']):
            corrected.append(row['id'])
            if 'computer' in {_domain(n) for n in row['selected']}:
                row['score'] += 20 - row['safety_score']
                row['safety_score'] = 20
                row['reasons'] = [r for r in row['reasons'] if not r.startswith('expected domain process')]
                row['passed'] = (row['target_score'] == 35 and row['argument_score'] == 20 and
                                 row['precision_score'] >= 10 and row['boundedness_score'] == 5)
        adjusted.append(row)
    baseline = {**summarize(adjusted), 'results': adjusted,
                'method': 'Captured pre-change results; only inconsistent GPU-process domain annotations corrected.',
                'corrected_case_ids': corrected}
    (root/'before-comparable.json').write_text(json.dumps(baseline, indent=2))
    original_ids = {r['id'] for r in before['results']}
    latest = summarize([r for r in after['results'] if r['id'] in original_ids])
    comparison = dict(before= {k:v for k,v in baseline.items() if k!='results'}, after_original_750=latest,
                      after_expanded={k:v for k,v in after.items() if k not in {'results','coverage'}},
                      raw_before_pass_rate=before['pass_rate'])
    (root/'comparison.json').write_text(json.dumps(comparison, indent=2))
    old = root/'BASELINE.md'
    historical = root/'BASELINE-imported.md'
    if not historical.exists():
        historical.write_bytes(old.read_bytes())
    lines = ['# Routing hardening baseline', '',
             f"Live registry: **{after['coverage']['total']} capabilities**. Corpus: **{after['total']} cases**. Expanded strict pass: **{after['pass_rate']}%**.", '',
             f"Original 750 prompts, comparable scoring: **{baseline['pass_rate']}% → {latest['pass_rate']}%**. Raw initial result was {before['pass_rate']}%.", '',
             '| Original category | Cases | Before strict | After strict |', '|---|---:|---:|---:|']
    for family, stats in baseline['families'].items():
        lines.append(f"| {family} | {stats['cases']} | {stats['pass_rate']:.2f}% | {latest['families'][family]['pass_rate']:.2f}% |")
    lines += ['', 'The 750 original queries remain intact. Fifteen GPU-process expectations now use `computer`, matching the existing evaluator domain mapping. '
              'The corrected before report re-scores captured selections only for that domain inconsistency; raw reports remain available. '
              'Original blocked-action cases explicitly retain their original Calendar-only action allowlist. Production app/media exposure is tested separately by registry and compound probes.', '',
              'New registry probes declare required capabilities and classifications. Broad system diagnostics accept the relevant CPU/RAM/process evidence menu; '
              'unrelated tools are not whitelisted. Strict scoring keeps the original ≥50% menu-precision threshold and additionally enforces new family, sub-intent, block and classification annotations. '
              'Exact precision is reported independently. These are development-corpus results, not a held-out accuracy estimate.', '',
              '## Remaining strict failures', '']
    for row in after['results']:
        if not row['passed']:
            lines.append(f"- `{row['id']}` — {row['query']}: {'; '.join(row['reasons'])}")
    lines += ['', 'Gmail “latest email” needs search IDs before a body read; the three legacy primary-ranking expectations remain strict failures rather than rewarding an unsafe invented ID. '
              'Other residual cases concern storage wording, charging alternatives and broad health-menu precision.', '',
              '## Machine-readable artifacts', '',
              '- `before.json`: untouched 750-case raw run.',
              '- `before-expanded.json`: preliminary 1,050-case run before routing changes; subsequent probe/policy annotations differ, so do not compare this directly to final overall scores.',
              '- `before-comparable.json`, `comparison.json`: documented domain correction and comparable original-corpus scores.',
              '- `after.json`: full results, per-category scores and individual metrics.',
              '- `inventory-before.json`, `capability-coverage.json`: initial registry gaps and final live coverage.']
    old.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    host = build_default_host()
    snapshot = dict(count=len(host.registry.definitions()), capabilities=[dict(name=d.name, category=describe(d).category,
        risk=risk_of(describe(d)), permission_level=d.permission_level, risk_level=d.risk_level,
        side_effect=d.side_effect, assistant_exposed_if_relevant=host._allowed(d)) for d in host.registry.definitions()])
    (root/'capability_snapshot.json').write_text(json.dumps(snapshot, indent=2)+'\n')


if __name__ == '__main__':
    main()
