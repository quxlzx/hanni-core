"""Project mention identity and unresolved continuation controls, not answer fixtures."""
from uuid import uuid4
import pytest
from hanni.memory.projects import ProjectContext
from tests.integration.test_campaign3_boundaries import feature

@pytest.fixture
def projects(tmp_path):
    app = feature(tmp_path)
    rows = [app.store.mutate('project.create', {'name': name, 'description': ''}, str(uuid4()))['project'] for name in ('Sable', 'Sable Compiler')]
    return (ProjectContext(app.memory_store(), app.store), rows)

@pytest.mark.parametrize('query,expected', [('Continue Sable Compiler', 'long'), ('Recall the Sable Compiler decisions', 'long'), ('Continue Sable', 'short'), ('Compare Sable and Sable Compiler decisions', 'ambiguous'), ('Sable Compiler versus Sable', 'ambiguous'), ('Resume it', 'ambiguous'), ('Please continue that', 'ambiguous'), ('Continue our work', 'ambiguous'), ('Where did we leave off?', 'ambiguous'), ('Resume playback', 'none'), ('Continue reading the weather forecast', 'none'), ('What is the structure of a rain cloud?', 'none'), ('Continue an unknown Opal project', 'none')])
def test_project_identity_is_explicit_or_requires_owner_selection(projects, query, expected):
    context, rows = projects
    actual = context.resolve(query)
    if expected in {'short', 'long'}:
        assert actual['status'] == 'matched'
        assert actual['project_id'] == rows[expected == 'long']['id']
    else:
        assert actual['status'] == expected and actual['project_id'] is None

def test_equal_shared_alias_never_selects_a_more_recent_project(projects):
    context, rows = projects
    for row in rows:
        context.add_alias(row['id'], 'synthetic optics work', expected_fingerprint=row['fingerprint'])
    actual = context.resolve('Continue synthetic optics work')
    assert actual['status'] == 'ambiguous' and len(actual['candidates']) == 2

def test_explicit_long_name_does_not_hide_an_independently_mentioned_short_alias(projects):
    context, rows = projects
    context.add_alias(rows[0]['id'], 'old prototype', expected_fingerprint=rows[0]['fingerprint'])
    actual = context.resolve('Compare old prototype with Sable Compiler')
    assert actual['status'] == 'ambiguous' and len(actual['candidates']) == 2
