"""Populated fixtures retain real store and isolated tool evidence, not model output."""
import hashlib
from pathlib import Path
import pytest
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.seed import populate

def test_populated_original_backend_projects_memory_review_and_notifications(tmp_path):
    with original_backend(tmp_path / 'populated') as backend:
        seed = populate(backend)
        status, productivity = backend.request('/api/productivity')
        assert status == 200
        assert {r['id'] for r in productivity['projects']} == {seed['project_id']}
        assert any((r['id'] == seed['task_id'] for r in productivity['tasks']))
        assert any((r['id'] == seed['note_id'] for r in productivity['notes']))
        assert any((r['id'] == seed['link_id'] for r in productivity['links']))
        status, memories = backend.request('/api/memory/explorer?limit=30')
        assert status == 200 and any((r['id'] == seed['memory_id'] for r in memories['records']))
        status, suggestions = backend.request('/api/memory/suggestions?limit=20')
        assert status == 200 and any((r['id'] == seed['suggestion_id'] for r in suggestions['items']))
        assert any((r['key'] == 'campaign8-controlled-fixture' for r in backend.features.store.notifications()['items']))
        assert not backend.chat.snapshot()['ready']
        assert seed['model_requests'] == 0 and (not seed['controller_attached'])

def test_seeded_workflow_history_has_original_fenced_receipt_artifact_and_disabled_authority(tmp_path):
    with original_backend(tmp_path / 'populated') as backend:
        seed = populate(backend)['workflow']
        status, detail = backend.request('/api/workflows/' + seed['completed_id'])
        assert status == 200
        detail = detail['workflow']
        assert detail['status'] == 'completed' and detail['counts']['verified'] == 1
        assert len(detail['invocations']) == 1 and detail['invocations'][0]['state'] == 'finished'
        assert detail['steps'][0]['verification']['status'] == 'VERIFIED'
        assert detail['steps'][0]['result']['verification']['status'] == 'VERIFIED'
        artifact = Path(seed['artifact_path'])
        assert artifact.resolve().is_relative_to(backend.root)
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == seed['artifact_sha256']
        assert detail['artifacts'][0]['sha256'] == seed['artifact_sha256']
        status, pending = backend.request('/api/workflows/' + seed['pending_id'])
        assert status == 200
        pending = pending['workflow']
        assert pending['status'] == 'awaiting_plan_approval'
        assert any((a['approval_id'] == seed['approval_id'] and a['state'] == 'pending' for a in pending['approvals']))
        assert all((not c['enabled'] for c in pending['controls'].values()))
        assert seed['origin'] == 'MANUALLY_SEEDED_ORIGINAL_STORE_AND_REGISTERED_TOOL_RECEIPT'
