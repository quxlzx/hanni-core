"""Audit retains diagnostic metadata without duplicating personal content."""
from pathlib import Path
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign9_manager.audit_privacy import historical_projection, probe

def test_original_tool_audit_does_not_duplicate_private_note_shell_or_secret_metadata(tmp_path):
    with original_backend(tmp_path / 'runtime') as backend:
        try:
            rows = probe(backend)
            assert len(rows) == 5
            assert all((not row.get('private_body_in_arguments_or_message', row.get('registered_canary_in_audit', False)) for row in rows))
            audit = backend.registry.context.audit.tail(5)
            assert len(audit) == 5
            assert all((isinstance(row['tool'], str) and row['ok'] is True and (row['duration_ms'] >= 0) for row in audit))
            assert [r['tool'] for r in audit] == ['note.append', 'note.list', 'note.search', 'powershell.run', 'file.stat']
        finally:
            from hanni.reliability.execution import close_service
            close_service(backend.root)
    assert backend.closed and (not backend.thread.is_alive())

def test_activity_projection_masks_old_private_note_records(tmp_path):
    with original_backend(tmp_path / 'runtime') as backend:
        assert historical_projection(backend)['private_body_in_arguments_or_message'] is False
