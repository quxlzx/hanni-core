"""Imported numeric contracts and current project-record publication, no owner data."""
from dataclasses import replace
from uuid import uuid4
import pytest
from hanni.memory.integration import PersonalContextProvider
from hanni.memory.privacy import validate_memory_record
from hanni.memory.projects import ProjectContext
from hanni.memory.store import MemoryStore
from tests.integration.test_campaign3_boundaries import feature

@pytest.mark.parametrize('confidence', [float('nan'), float('inf'), -float('inf'), -0.01, 1.01, True, False, '0.5', None])
def test_record_confidence_must_be_finite_numeric_probability(tmp_path, confidence):
    row, _ = MemoryStore(tmp_path / 'memory.sqlite3').remember('The fixture telescope uses a narrow aperture')
    with pytest.raises(ValueError):
        validate_memory_record(replace(row, confidence=confidence))

@pytest.mark.parametrize('confidence', [0, 0.001, 0.5, 1])
def test_valid_uncalibrated_confidence_is_preserved_without_coercion(tmp_path, confidence):
    row, _ = MemoryStore(tmp_path / 'memory.sqlite3').remember('The fixture telescope uses a narrow aperture')
    modified = replace(row, confidence=confidence)
    assert validate_memory_record(modified) is modified
    assert modified.to_dict()['confidence_calibrated'] is False

def project_fixture(tmp_path):
    app = feature(tmp_path)
    project = app.store.mutate('project.create', {'name': 'Telescope calibration', 'description': ''}, str(uuid4()))['project']
    store = app.memory_store()
    row, _ = store.remember('Telescope calibration decision selects a narrow aperture', project_id=project['id'])
    return (app, store, project, row)

@pytest.mark.parametrize('field,value', [('source', 'password is project-fixture-unsafe'), ('source_ref', 'password is project-fixture-unsafe'), ('fact_key', 'password is project-fixture-unsafe'), ('fact_value', 'password is project-fixture-unsafe'), ('memory_type', 'password is project-fixture-unsafe'), ('id', 'password is project-fixture-unsafe'), ('semantic_status', 'unapproved_execution'), ('confidence', 'nan'), ('confidence', 'inf'), ('confidence', -1), ('confidence', 2)])
def test_project_package_quarantines_whole_unsafe_record_not_only_metadata(tmp_path, field, value):
    app, store, project, row = project_fixture(tmp_path)
    sibling, _ = store.remember('Telescope calibration decision retains the old tripod', project_id=project['id'])
    with store._connect() as db:
        db.execute('PRAGMA ignore_check_constraints=ON')
        db.execute(f'UPDATE memories SET {field}=? WHERE id=?', (value, row.id))
    before = store.fingerprint()
    package = ProjectContext(store, app.store).package(project['id'])
    assert row.content not in package['context_text'], 'Unsafe metadata still legitimizes the record content'
    assert [item['id'] for item in package['memories']] == [sibling.id]
    assert any(('withheld' in item.casefold() for item in package['uncertainties']))
    assert store.fingerprint() == before, 'Read quarantine must not silently delete or correct imported rows'

def test_project_package_preserves_safe_record_provenance_and_excludes_other_project(tmp_path):
    app, store, project, row = project_fixture(tmp_path)
    unrelated, _ = store.remember('Other telescope calibration decision uses a broad aperture', project_id='different-project')
    package = ProjectContext(store, app.store).package(project['id'])
    assert len(package['memories']) == 1
    assert all((package['memories'][0][key] == value for key, value in row.to_dict().items() if value != ''))
    assert row.content in package['context_text'] and row.source in package['context_text']
    assert unrelated.content not in package['context_text']

def test_project_package_rechecks_current_registered_secret_metadata(tmp_path):
    from hanni.logs.redaction import clear_registry, register_secret
    app, store, project, row = project_fixture(tmp_path)
    with store._connect() as db:
        db.execute('UPDATE memories SET source_ref=? WHERE id=?', ('fixture-telescope-provenance', row.id))
    register_secret('CAMPAIGN3_PROJECT_SYNTHETIC', 'fixture-telescope-provenance')
    try:
        package = ProjectContext(store, app.store).package(project['id'])
        assert not package['memories'] and row.content not in package['context_text']
        assert store.get(row.id) is not None
    finally:
        clear_registry()

@pytest.mark.parametrize('operation', ['content', 'source', 'confidence', 'delete'])
def test_project_provider_rechecks_complete_record_after_package_same_timestamp_change(tmp_path, operation):
    app, store, project, row = project_fixture(tmp_path)
    original_package = ProjectContext(store, app.store).package(project['id'])

    class ConcurrentProjectView:

        def resolve(self, _):
            return dict(status='matched', project_id=project['id'])

        def package(self, *_args, **_kwargs):
            with store._connect() as db:
                if operation == 'delete':
                    db.execute('DELETE FROM memories WHERE id=?', (row.id,))
                else:
                    db.execute('PRAGMA ignore_check_constraints=ON')
                    value = dict(content='Telescope calibration decision now selects a wider aperture', source='password is changed-project-provenance', confidence='nan')[operation]
                    db.execute(f'UPDATE memories SET {operation}=? WHERE id=?', (value, row.id))
            return original_package
    result = PersonalContextProvider(store, project_context=ConcurrentProjectView()).retrieve('Continue Telescope calibration')
    assert row.content not in result.text, 'Project context published a stale observation after its same-timestamp source changed'
    assert all((match.record.id != row.id or match.record.content != row.content for match in result.matches))
    assert 'changed-project-provenance' not in result.text

def test_project_provider_rechecks_secret_registry_after_package(tmp_path):
    from hanni.logs.redaction import clear_registry, register_secret
    app, store, project, row = project_fixture(tmp_path)
    original_package = ProjectContext(store, app.store).package(project['id'])

    class ConcurrentProjectView:

        def resolve(self, _):
            return dict(status='matched', project_id=project['id'])

        def package(self, *_args, **_kwargs):
            register_secret('CAMPAIGN3_PROJECT_SYNTHETIC', 'narrow aperture')
            return original_package
    try:
        result = PersonalContextProvider(store, project_context=ConcurrentProjectView()).retrieve('Continue Telescope calibration')
        assert 'narrow aperture' not in result.text and (not result.matches)
    finally:
        clear_registry()
