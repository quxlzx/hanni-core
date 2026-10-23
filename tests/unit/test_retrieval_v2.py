"""Generic metadata retrieval and original authority regressions; no model calls."""
from dataclasses import replace
from pathlib import Path
import pytest
from hanni.evals.routing import build_default_host
from hanni.tools.capabilities import capability_catalog
from hanni.tools.discovery import HybridCapabilityIndex, index_for, tokens, intent_text

@pytest.fixture
def host(tmp_path):
    return build_default_host(data_dir=tmp_path / 'isolated', timezone_name='America/New_York')

def test_typo_correction_is_vocabulary_derived_and_bounded(host):
    index = index_for(host.registry)
    assert index._correct('memroy') == 'memory'
    assert index._correct('clipbaord') == 'clipboard'
    assert index._correct('remain') == 'remain'
    rows = index.candidates('Inspect clipbaord text', eligible={'clipboard.read'})
    assert rows[0].name == 'clipboard.read'
    assert ('clipbaord', 'clipboard') in rows[0].corrections
    assert tokens('processes directories wireless') == ('process', 'directory', 'wireless')

@pytest.mark.parametrize('query', ['Tell me something encouraging', 'Why do people enjoy music?', 'Explain the idea of a hash table', 'I wish my schedule were less stressful'])
def test_single_incidental_word_does_not_fill_candidate_menu(host, query):
    assert host._retrieval_candidates(query) == ()

def test_candidate_count_tracks_evidence_not_fixed_padding(host):
    one = host._retrieval_candidates('Inspect command lookup path directories for duplicates')
    alternatives = host._retrieval_candidates('Compare git branch untracked changes checked out')
    assert [r.name for r in one] == ['env.path']
    assert 1 < len(alternatives) <= host.max_tools
    assert {'git.status', 'git.branches'} <= {r.name for r in alternatives}

def test_eligibility_filter_precedes_ranking_even_if_denied_definition_repeats_query(host):
    cap = capability_catalog(host.registry)[0]
    permitted = replace(cap, name='fixture.read', description='Inspect astronomical catalog coordinates', aliases=(), tags=())
    denied = replace(cap, name='fixture.destroy', description='Inspect astronomical catalog coordinates ' * 500, aliases=(), tags=())
    index = HybridCapabilityIndex((permitted, denied))
    selected = index.rank('Inspect astronomical catalog coordinates', eligible={'fixture.read'})
    assert [r.name for r in selected] == ['fixture.read']

def test_conversational_quantifiers_and_reporting_verbs_are_not_rare_evidence(host):
    cap = capability_catalog(host.registry)[0]
    ordinary = replace(cap, name='fixture.records', description='Inspect archival records', aliases=(), tags=(), display_name='', categories=(), argument_schema={})
    framed = replace(ordinary, name='fixture.alternative', aliases=('Ask what both records say',))
    index = HybridCapabilityIndex((ordinary, framed))
    plain = index.rank('Inspect archival records')
    conversational = index.rank('Ask to inspect what both archival records say')
    assert [(row.name, row.score, row.matched_terms) for row in plain] == [(row.name, row.score, row.matched_terms) for row in conversational]
    assert not {'both', 'ask', 'say'} & index.postings.keys()

@pytest.mark.parametrize('path', ['C:\\diagnostics\\hanni\\cpu-results.json', '"C:\\memory pressure\\model-status.json"', '/var/model/hanni-power-report.json', '\\\\server\\memory\\gpu-results.json', './diagnostics/performance.json', 'C:\\data\\gmail-message.txt', 'C:\\data\\spotify-status.txt'])
def test_path_words_are_argument_data_not_diagnostic_intent(host, path):
    query = 'read ' + path
    assert intent_text(query) == 'read file path'
    assert [tool.capability_id for tool in host.select_tools(query)] == ['file.read']
    assert query == 'read ' + path

@pytest.mark.parametrize('uri', ['https://example.org/report', 'http://127.0.0.1:8765/api/chat', 'file:///C:/data/report.txt'])
def test_uri_slashes_are_not_local_path_boundaries(uri):
    assert intent_text('inspect ' + uri) == 'inspect ' + uri

def test_index_rebuilds_on_exact_registry_revision_and_removal(host):
    original = index_for(host.registry)
    definition = host.registry.get('clipboard.read')
    host.registry.register(replace(definition, name='fixture.catalog', description='Inspect astronomical catalog coordinates', tags=(), aliases=()))
    updated = index_for(host.registry)
    assert updated is not original
    assert any((r.name == 'fixture.catalog' for r in updated.rank('astronomical catalog coordinates')))
    registered = host.registry.get('fixture.catalog')
    assert host.registry.unregister(registered.name, expected=registered)
    removed = index_for(host.registry)
    assert removed is not updated
    assert not any((r.name == 'fixture.catalog' for r in removed.rank('astronomical catalog coordinates')))

def test_read_retrieval_does_not_expose_actions_or_arbitrary_shell(host):
    for query in ['Kill the process using memory', 'Delete the largest directory', 'run powershell script']:
        assert host.select_tools(query) == ()
    candidates = host._retrieval_candidates('Inspect installed programs and versions')
    assert candidates
    assert all((host.registry.get(r.name).permission_level == 0 for r in candidates))
    assert all((host.registry.get(r.name).side_effect in {None, 'read'} for r in candidates))

def test_new_menu_preserves_exact_schema_and_resolved_date_contract(host):
    before = host.registry.get('clipboard.read').argument_schema()
    selected = host.select_tools('Inspect clipbaord text')
    assert selected[0].capability_id == 'clipboard.read'
    assert selected[0].input_schema == before
    agenda = host.route('what is on my calendar tomorrow')
    assert len(agenda.tools) == 1
    assert agenda.tools[0].capability_id == 'google_calendar.agenda'
    assert agenda.tools[0].fixed_arguments

def test_read_timeout_retry_contract_requires_authoritative_opt_in(host):

    def timeout(*args):
        raise TimeoutError('fixture timeout')
    registry = host.registry
    for name, retry_safe, external, expected in [('fixture.safe', True, '', True), ('fixture.once', False, '', False), ('mcp.fixture.safe', True, 'exacthash', False)]:
        source = registry.get('system.stats')
        registry.register(replace(source, name=name, handler=timeout, retry_safe=retry_safe, external_definition_hash=external))
        tool = host._as_tool(registry.get(name))
        from hanni.tools.base import ToolRegistry
        executable = ToolRegistry(registry.context)
        executable.register(replace(registry.get(name), handler=timeout))
        from hanni.mcp.host import McpHost
        result = McpHost(executable).call(tool, {})
        assert result['error']['code'] == 'TIMEOUT'
        assert result['error']['retryable'] is expected
