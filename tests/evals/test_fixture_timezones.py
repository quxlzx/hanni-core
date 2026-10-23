from pathlib import Path
from hanni.config.loader import load_config
from hanni.evals.fixtures import fixture_timezone
from hanni.evals.routing import build_default_host

def test_historical_fixture_zone_is_independent_of_live_owner_zone():
    corpus = Path('evals/llm_tools/cases.jsonl')
    assert load_config(Path('config')).hanni.user.timezone == 'America/New_York'
    assert fixture_timezone(corpus) == 'America/Chicago'
    host = build_default_host(timezone_name=fixture_timezone(corpus))
    assert host.timezone_name == 'America/Chicago'

def test_unlisted_corpus_uses_live_configuration(tmp_path):
    corpus = tmp_path / 'future.jsonl'
    corpus.write_text('', encoding='utf-8')
    assert fixture_timezone(corpus) is None
    assert build_default_host(timezone_name=fixture_timezone(corpus)).timezone_name == 'America/New_York'
