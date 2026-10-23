"""Broad retrieval and safety invariants independent of exact phrasing."""
from datetime import datetime
from hanni.evals.routing import build_default_host
NOW = datetime.fromisoformat('2026-09-24T12:00:00-04:00')

def names(host, query):
    return {tool.capability_id for tool in host.route(query, now=NOW).tools}

def test_memory_only_never_pads_with_media_clock_or_archive():
    host = build_default_host()
    for phrase in ('whats eating my ram rn', 'show the app using most memory', 'which process is taking system memory'):
        selected = names(host, phrase)
        assert 'process.top_memory' in selected
        assert not any((name.startswith(('spotify.', 'archive.', 'time.', 'gpu.')) for name in selected))

def test_compound_request_preserves_both_domains():
    host = build_default_host()
    for phrase in ('open discord and check cpu', 'open steam and tell me what is using ram'):
        selected = names(host, phrase)
        assert 'app.open' in selected
        assert any((name in selected for name in ('system.stats', 'system.performance', 'process.top_cpu', 'process.top_memory')))

def test_permission_question_does_not_become_an_action():
    host = build_default_host()
    for phrase in ('is hanni allowed to kill processes', 'would you need approval to delete a file'):
        selected = names(host, phrase)
        assert not selected.intersection({'process.stop', 'file.delete', 'powershell.run'})

def test_plain_ram_and_explicit_vram_are_separate_resources():
    host = build_default_host()
    assert not any((name.startswith('gpu.') for name in names(host, 'what is using my ram')))
    assert any((name.startswith('gpu.') for name in names(host, 'how much vram is left on my gpu')))
