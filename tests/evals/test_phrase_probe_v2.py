"""Keep the new-phrase routing probe separate from prior benchmark requests."""
import hashlib
import json
from pathlib import Path

def test_phrase_probe_lock_and_request_separation():
    root = Path(__file__).resolve().parents[2]
    path = root / 'evals' / 'routing' / 'phrase_probe_v2.jsonl'
    lock = json.loads(path.with_name('phrase_probe_v2.lock.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    routing_development = [json.loads(line) for line in (root / 'evals' / 'routing' / 'cases.jsonl').read_text(encoding='utf-8').splitlines()]
    llm_holdout = [json.loads(line) for line in (root / 'evals' / 'llm_tools' / 'holdout_v1.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == lock['scenario_count'] == 30
    assert hashlib.sha256(path.read_bytes()).hexdigest() == lock['sha256_file']
    assert len({row['id'] for row in rows}) == len({row['query'].casefold() for row in rows}) == 30
    assert not {row['query'].casefold() for row in rows} & {row['query'].casefold() for row in routing_development + llm_holdout}
    assert all((row.get('mode') == 'blocked' or row.get('required') for row in rows))
