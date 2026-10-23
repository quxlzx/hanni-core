"""Offline frozen-oracle diagnostics of the manager's actual controller run."""
from collections import Counter
import argparse
import json
from pathlib import Path
from .grading import live_readback_score
from .harness import digest

def assess(inputs, oracles, receipts, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cases = {c['id']: c for c in json.loads(Path(inputs).read_text(encoding='utf-8'))}
    expected = json.loads(Path(oracles).read_text(encoding='utf-8'))
    rows, source = ([], {})
    for path in sorted(Path(receipts).glob('receipt-*.json')):
        raw = json.loads(path.read_text(encoding='utf-8'))
        if raw['id'] not in cases:
            continue
        case = cases[raw['id']]
        graded = live_readback_score(case, expected[case['id']], raw)
        scoped = {'id': case['id'], 'category': case['category'], 'strict_contract_matched': graded['passed'], 'model_calls': raw.get('actual_model_calls', 0), 'observed_actual_call_names': [a.get('name') for a in raw.get('actual_registry_calls', [])], 'required_contract_call_names': [a['name'] for a in case['actions'] if a['target'] == 'registry'], 'prescribed_nonregistry_actions_not_dispatched': [a['id'] for a in case['actions'] if a['target'] != 'registry'], 'fixture_paths_not_in_user_request': [p for p in case.get('setup', {}).get('files', {}) if p not in case['query']], 'returned_provider_tools_not_preconfigured': case['category'] == 'mcp' and (not raw.get('inert_mcp_provider_calls')), 'semantic_accuracy': None, 'scope': 'Post-run unchanged contract comparison; semantic verdict requires separate actual-output review', 'actual_reply': raw.get('actual_model_reply')}
        graded['scope_cautions'] = scoped
        name = 'grade-' + path.stem.removeprefix('receipt-') + '.json'
        (output / name).write_text(json.dumps(graded, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8', newline='\n')
        rows.append(scoped)
        source[path.name] = digest(path)
    counts = Counter((row['category'] for row in rows))
    summary = {'tasks': len(rows), 'strict_unchanged_contract_matches': sum((r['strict_contract_matched'] for r in rows)), 'actual_model_posts': sum((r['model_calls'] for r in rows)), 'tasks_with_actual_posts': sum((r['model_calls'] > 0 for r in rows)), 'categories': dict(counts), 'semantic_model_accuracy': None, 'rows': rows, 'original_receipt_hashes': source, 'original_receipts_unchanged': all((digest(Path(receipts) / name) == value for name, value in source.items())), 'inputs_sha256': digest(inputs), 'oracles_sha256': digest(oracles), 'scope': 'Mechanical contract comparison only. Missing task prerequisites and unavailable interface authority must not be presented as semantic model failures or invented completions.'}
    (output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8', newline='\n')
    return summary

def main():
    parser = argparse.ArgumentParser()
    for name in ('inputs', 'oracles', 'receipts', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.inputs, args.oracles, args.receipts, args.output)
    print(json.dumps({key: result[key] for key in ('tasks', 'strict_unchanged_contract_matches', 'actual_model_posts', 'tasks_with_actual_posts', 'original_receipts_unchanged')}))
if __name__ == '__main__':
    main()
