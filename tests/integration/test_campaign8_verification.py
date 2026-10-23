from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from scripts.campaign8_verification.validation import VISUAL_WEIGHTS, capture_receipt_errors, control_coverage, final_input_errors, visual_result

def original_receipt(image):
    return {'evidence_class': 'CONTROLLED', 'window': {'pid': 4321, 'create_time': 12345.125, 'hwnd': 98765, 'class': 'WindowsForms10.Window', 'dpi': 96, 'dpi_scope': 'current_windows_observed', 'rect': [20, 20, 1000, 740], 'client_rect': [0, 0, 980, 680]}, 'capture': {'method': 'owned_hwnd_printwindow', 'pid_verified': True, 'create_time_verified': True, 'hwnd_verified': True, 'scope': 'owned_hanni_hwnd_only', 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}}

def test_browser_rendering_cannot_pass_native_receipt_conformance(tmp_path):
    path = tmp_path / 'own.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-header-validator-only')
    row = original_receipt(path)
    row['capture']['method'] = 'cdp_page_screenshot'
    assert 'capture is not original owned HWND pixels' in capture_receipt_errors(row, path, tmp_path)

def test_emulated_dpi_is_not_physical_windows_level(tmp_path):
    path = tmp_path / 'own.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-header-validator-only')
    row = original_receipt(path)
    row['window']['dpi_scope'] = 'cdp_emulated'
    assert capture_receipt_errors(row, path, tmp_path)

def test_missing_process_identity_rejects_capture_conformance(tmp_path):
    path = tmp_path / 'own.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-header-validator-only')
    row = original_receipt(path)
    del row['window']['create_time']
    assert capture_receipt_errors(row, path, tmp_path)

def test_tampered_pixels_reject_existing_receipt(tmp_path):
    path = tmp_path / 'own.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-header-validator-only')
    row = original_receipt(path)
    path.write_bytes(b'\x89PNG\r\n\x1a\nchanged')
    assert 'capture bytes do not match the receipt' in capture_receipt_errors(row, path, tmp_path)

def test_foreign_artifact_not_adopted(tmp_path):
    outside = tmp_path / 'outside.png'
    outside.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-header-validator-only')
    assert capture_receipt_errors(original_receipt(outside), outside, tmp_path / 'owned')

def test_inventory_denominator_grows_from_observed_controls():
    result = control_coverage([{'id': f'control-{n}'} for n in range(17)], [])
    assert result['inventoried'] == result['counts']['not_run'] == 17

def test_primary_no_receipt_remains_unverified():
    result = control_coverage([{'id': 'missing', 'primary': True}], [])
    assert result['all_primary_controls_verified'] is False

def test_empty_inventory_cannot_claim_verified_primary_controls():
    result = control_coverage([], [])
    assert result['primary_count'] == 0
    assert result['all_primary_controls_verified'] is False

def test_mock_pass_without_original_native_evidence_remains_unknown():
    result = control_coverage([{'id': 'fake', 'primary': True}], [{'id': 'fake', 'status': 'pass', 'evidence_class': 'mock'}])
    assert result['counts']['unknown'] == 1
    assert result['all_primary_controls_verified'] is False

def test_duplicate_outcomes_are_not_more_coverage():
    result = control_coverage([{'id': 'one'}], [{'id': 'one'}, {'id': 'one'}])
    assert result['inventoried'] == result['counts']['unknown'] == 1

def test_duplicate_inventory_occurrences_are_rejected():
    with pytest.raises(ValueError):
        control_coverage([{'id': 'one'}, {'id': 'one'}], [])

def test_critical_backend_falsehood_prevents_good_layout_acceptance():
    result = visual_result(dict.fromkeys(VISUAL_WEIGHTS, 9), template_score=1, native_capture_verified=True, screenshot_sha256='a' * 64, critical_defects=['unavailable worker is claimed available'])
    assert result['score'] == 9 and result['accepted'] is False

def test_high_score_without_native_pixels_is_ineligible():
    result = visual_result(dict.fromkeys(VISUAL_WEIGHTS, 10), template_score=0, native_capture_verified=False, screenshot_sha256=None, critical_defects=[])
    assert result['eligible'] is False and result['accepted'] is False

def test_low_typography_is_not_compensated_by_other_dimensions():
    dimensions = dict.fromkeys(VISUAL_WEIGHTS, 10)
    dimensions['typography'] = 8
    result = visual_result(dimensions, template_score=1, native_capture_verified=True, screenshot_sha256='a' * 64, critical_defects=[])
    assert result['score'] > 8.6 and result['accepted'] is False

def test_unmeasured_visual_dimension_is_not_imputed():
    dimensions = dict.fromkeys(VISUAL_WEIGHTS, 9)
    dimensions['typography'] = None
    with pytest.raises(ValueError):
        visual_result(dimensions, template_score=1, native_capture_verified=True, screenshot_sha256='a' * 64, critical_defects=[])

def test_scores_are_not_rounded_up_to_cross_threshold():
    result = visual_result(dict.fromkeys(VISUAL_WEIGHTS, 8.59999), template_score=1, native_capture_verified=True, screenshot_sha256='a' * 64, critical_defects=[])
    assert result['accepted'] is False

def test_nonfinite_visual_score_rejected():
    with pytest.raises(ValueError):
        visual_result(dict.fromkeys(VISUAL_WEIGHTS, float('nan')), template_score=1, native_capture_verified=True, screenshot_sha256='a' * 64, critical_defects=[])

def test_case_input_does_not_contain_oracle_answers():
    assert final_input_errors({'operation': 'measure_layout', 'authority_mode': 'owner_read_only'}) == []
    assert final_input_errors({'operation': 'measure_layout', 'authority_mode': 'owner_read_only', 'expected': {}})

def test_generation_or_owner_effect_operations_not_admitted():
    for operation in ('send_message', 'reboot', 'start_assistant', 'save_owner_memory', 'shutdown'):
        assert final_input_errors({'operation': operation, 'authority_mode': 'owner_read_only'})

def test_missing_post_close_semantic_evidence_never_passes():
    from scripts.campaign8_verification.scoring import criterion_result
    assert criterion_result(True, None, evidence='original.png')['passed'] is False
    assert criterion_result(True, True, evidence=None)['passed'] is False

def test_zero_counts_and_boolean_facts_do_not_alias():
    from scripts.campaign8_verification.scoring import criterion_result
    assert criterion_result(False, 0, evidence='original receipt')['passed'] is False
    assert criterion_result(0, 0, evidence='original receipt')['passed'] is True

def test_review_classification_never_promotes_observed_failure():
    from scripts.campaign8_verification.scoring import grade_case
    row = {'id': 'development-only', 'family': 'truth', 'route': 'home', 'surface': 'desktop'}
    oracle = {'id': row['id'], 'expected': {'unauthorized_effects': 0}}
    review = {'id': row['id'], 'independently_reviewed': True, 'receipt_sha256': 'a' * 64, 'observed': {'unauthorized_effects': 1}, 'evidence': {'unauthorized_effects': 'original receipt'}, 'manual_classification': 'source defect, unchanged frozen oracle'}
    assert grade_case(row, oracle, review)['passed'] is False

def test_unclosed_raw_observations_cannot_open_grading_answers(tmp_path):
    import json
    from scripts.campaign8_verification.scoring import grade_closed
    (tmp_path / 'CLOSED.json').write_text(json.dumps({'complete': False}), encoding='utf8')
    with pytest.raises(ValueError, match='complete closed'):
        grade_closed(tmp_path, oracle_path=tmp_path / 'answers-not-present', oracle_sha256='a' * 64, reviews_path=tmp_path / 'review-not-present')

def test_original_projection_tokens_are_redacted_without_changing_facts():
    from scripts.campaign8_verification.final_runner import scrub
    actual = {'token': 'private', 'ready': False, 'nested': [{'refresh_token': 'private', 'available': None}]}
    clean = scrub(actual)
    assert clean == {'token': '[REDACTED]', 'ready': False, 'nested': [{'refresh_token': '[REDACTED]', 'available': None}]}
    assert actual['token'] == 'private'

def test_final_freeze_rejects_foreign_manifest_member(tmp_path):
    import json
    from scripts.campaign8_verification.final_runner import freeze_manifest
    (tmp_path / 'MANIFEST.json').write_text(json.dumps({'../foreign.py': 'a' * 64}), encoding='utf8')
    with pytest.raises(ValueError, match='manifest member'):
        freeze_manifest(tmp_path)

def test_control_adapter_rejects_unbounded_occurrence_index():
    from scripts.campaign8_verification.final_runner import named_control
    with pytest.raises(ValueError, match='control index'):
        named_control(None, {'role': 'button', 'name': 'Development-only', 'index': 1000})

def test_declared_maximum_is_a_bound_not_a_required_failure_value():
    from scripts.campaign8_verification.scoring import criterion_result
    assert criterion_result(1, 0, evidence='native layout', name='overflow_px_max')['passed']
    assert not criterion_result(1, 1.01, evidence='native layout', name='overflow_px_max')['passed']
    assert not criterion_result(1, False, evidence='native layout', name='overflow_px_max')['passed']

def test_backend_provenance_allows_only_bound_venv_interpreter_child(tmp_path):
    from scripts.campaign8_verification.development_smoke import backend_link_valid
    launcher = {'pid': 100}
    command = ['python.exe', '-m', 'scripts.campaign8_ui.backend', '--root', str(tmp_path)]
    assert backend_link_valid({'pid': 101, 'parent_pid': 100}, launcher, command, tmp_path)
    assert not backend_link_valid({'pid': 101, 'parent_pid': 999}, launcher, command, tmp_path)
    assert not backend_link_valid({'pid': 101, 'parent_pid': 100}, launcher, command, tmp_path / 'foreign')

def test_private_projection_token_is_ephemeral_and_original_authorized(monkeypatch):
    from scripts.campaign8_verification import final_runner
    calls = []
    monkeypatch.setattr(final_runner, 'process_identity', lambda pid: {'create_time': 123})

    def original(url, path, **kwargs):
        calls.append((path, kwargs))
        return {'token': 'controlled-private-token'} if path == '/api/chat?before=1' else {'available': False}
    monkeypatch.setattr(final_runner, 'request_json', original)
    row = final_runner.original_projection({'pid': 1, 'create_time': 123, 'url': 'http://127.0.0.1:1'}, '/api/voice')
    assert calls[1][1]['token'] == 'controlled-private-token'
    assert row == {'available': False}

def test_actual_flat_capture_receipt_rejects_reused_process_and_bad_client_region(tmp_path):
    from PIL import Image
    from scripts.campaign8_verification.validation import actual_capture_receipt_errors
    path = tmp_path / 'owned.png'
    Image.new('RGB', (100, 100)).save(path)
    row = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'method': 'Win32 PrintWindow PW_RENDERFULLCONTENT', 'capture_scope': 'Verified owned HWND client and native chrome only', 'desktop_pixel_capture': False, 'evidence_class': 'CONTROLLED', 'pid': 10, 'create_time': 123, 'hwnd': 20, 'dpi': 120, 'window_class': 'OwnedFixtureOnly', 'window_rect': [0, 0, 100, 100], 'image_size': [100, 100], 'client_region_verified': [1, 20, 99, 99]}
    identity = {'pid': 10, 'create_time': 123}
    assert not actual_capture_receipt_errors(row, session_identity=identity, owned_root=tmp_path)
    row['create_time'] = 124
    assert actual_capture_receipt_errors(row, session_identity=identity, owned_root=tmp_path)
    row['create_time'] = 123
    row['client_region_verified'] = [1, 20, 101, 99]
    assert actual_capture_receipt_errors(row, session_identity=identity, owned_root=tmp_path)

@pytest.mark.parametrize('key,value', [('pid', 999), ('create_time', 124), ('dpi', 96), ('method', 'cdp_page_screenshot'), ('sha256', '0' * 64), ('window_rect', [15, 63, 215, 175])])
def test_safe_menu_selection_rejects_foreign_or_unviewed_popup(key, value):
    from scripts.campaign8_verification.application_menu_repro import VIEWED_POPUP_SHA256, safe_row_point
    capture = {'pid': 10, 'create_time': 123, 'dpi': 120, 'image_size': [199, 112], 'method': 'Win32 PrintWindow PW_RENDERFULLCONTENT', 'desktop_pixel_capture': False, 'sha256': VIEWED_POPUP_SHA256, 'window_class': 'WindowsForms10.Window.OwnedTest', 'window_rect': [15, 63, 214, 175]}
    capture[key] = value
    with pytest.raises(ValueError, match='no click permitted'):
        safe_row_point(capture, {'pid': 10, 'create_time': 123})
