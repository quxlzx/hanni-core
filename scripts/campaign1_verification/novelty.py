"""Query hashes only: never print or retain historical/final answer content."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata
QUERY_KEYS = ('query', 'request', 'prompt', 'owner_text', 'goal')
CONTAINERS = ('cases', 'turns', 'workflows', 'results', 'records', 'messages', 'rows')

def normalized_hash(query):
    text = unicodedata.normalize('NFKC', query).casefold()
    text = re.sub('\\s+', ' ', text).strip().rstrip('.?!')
    return hashlib.sha256(text.encode('utf8')).hexdigest()

def query_hashes(payload):
    if isinstance(payload, list):
        for row in payload:
            yield from query_hashes(row)
    elif isinstance(payload, dict):
        for key in QUERY_KEYS:
            value = payload.get(key)
            if isinstance(value, str):
                yield normalized_hash(value)
        if payload.get('role') == 'user' and isinstance(payload.get('content'), str):
            yield normalized_hash(payload['content'])
        for key in CONTAINERS:
            value = payload.get(key)
            if isinstance(value, (list, dict)):
                if key == 'turns' and isinstance(value, list):
                    for row in value:
                        if isinstance(row, str):
                            yield normalized_hash(row)
                        else:
                            yield from query_hashes(row)
                else:
                    yield from query_hashes(value)

def file_hashes(path):
    if path.suffix == '.jsonl':
        with path.open(encoding='utf-8-sig') as stream:
            for line in stream:
                if line.strip():
                    try:
                        yield from query_hashes(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    else:
        try:
            yield from query_hashes(json.loads(path.read_text(encoding='utf-8-sig')))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--old-root', type=Path, action='append', required=True)
    args = parser.parse_args()
    before = hashlib.sha256(args.corpus.read_bytes()).hexdigest()
    corpus = json.loads(args.corpus.read_text(encoding='utf8'))
    old = set()
    scanned = []
    for root in args.old_root:
        for path in root.rglob('*'):
            if path.suffix not in {'.json', '.jsonl'}:
                continue
            text = path.as_posix().lower()
            if any((x in text for x in ('campaign1', '/state/', '/credentials/', '/oauth/', '/vault/', '.venv'))):
                continue
            if root.name == 'data' and (not any((x in text for x in ('verif', 'campaign', 'benchmark', 'eval', 'protocol', 'cohort')))):
                continue
            hashes = set(file_hashes(path))
            if hashes:
                old.update(hashes)
                scanned.append({'file': str(path), 'query_hash_count': len(hashes)})
    development = set(file_hashes(args.development)) if args.development else set()
    collisions = []
    internal = {}
    turn_count = 0
    for case in corpus['cases']:
        for index, query in enumerate(case.get('turns') or [case['query']]):
            value = normalized_hash(query)
            turn_count += 1
            internal.setdefault(value, []).append({'case_id': case['id'], 'turn': index})
            if value in old or value in development:
                collisions.append({'case_id': case['id'], 'turn': index, 'query_sha256': value, 'historical': value in old, 'development': value in development})
    assert before == hashlib.sha256(args.corpus.read_bytes()).hexdigest()
    result = {'corpus_sha256': before, 'case_count': len(corpus['cases']), 'all_owner_turns_checked': turn_count, 'historical_query_hashes': len(old), 'development_query_hashes': len(development), 'historical_files_with_queries': len(scanned), 'scanned': scanned, 'collisions': collisions, 'internal_repeated_turn_hashes': [{'query_sha256': h, 'locations': v} for h, v in internal.items() if len(v) > 1], 'query_or_answer_content_emitted': False, 'normalization': 'NFKC,casefold,space-collapse,terminal-punctuation trim', 'no_corpus_change': True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'scanned', 'internal_repeated_turn_hashes'}}, indent=2))
if __name__ == '__main__':
    main()
