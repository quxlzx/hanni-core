"""Convert reviewed HANNI exports to offline Atropos ScoredDataGroup JSONL.

Run in a separate training environment with transformers installed. This only
writes local data; it never starts training or sends trajectories to a server.
"""
import argparse
import json
from pathlib import Path
from hanni.native.training import atropos_group


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--labels', required=True, type=Path, help='JSON object mapping trajectory IDs to reviewed numeric rewards')
    p.add_argument('--tokenizer', required=True, type=Path, help='Existing local tokenizer directory')
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.input.stat().st_size > 8 * 1024 * 1024 or args.labels.stat().st_size > 100000: p.error('Input is too large.')
    if not args.tokenizer.is_dir(): p.error('Provide a local tokenizer directory.')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True, trust_remote_code=False)
    records = [json.loads(line) for line in args.input.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    labels = json.loads(args.labels.read_text(encoding='utf-8-sig'))
    # Keep rewards grouped by the same initial task prompt. Never mix unrelated prompts.
    groups = {}
    for record in records:
        if record.get('schema') != 'hanni.trajectory.v1': p.error('Use HANNI trajectory format.')
        first = next((m.get('content') for m in record['messages'] if m['role'] == 'user'), None)
        if first is None: p.error('Trajectory has no user prompt.')
        groups.setdefault(first, []).append(record)
    converted = [atropos_group(group, labels, tokenizer) for group in groups.values()]
    with args.output.open('x', encoding='utf-8') as out:
        for group in converted: out.write(json.dumps(group, allow_nan=False) + '\n')
    print(json.dumps({'groups': len(converted), 'trajectories': len(records), 'training_started': False}))


if __name__ == '__main__': main()
