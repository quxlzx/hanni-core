"""Existing disabled implementation and UI guard tests, not vision accuracy."""
import pytest
from scripts.campaign7_screen.audit import run_case

def run(tmp_path, operation, **values):
    row = run_case({'id': operation, 'operation': operation, **values}, tmp_path / 'isolated')
    assert row['source_before'] == row['source_after']
    assert not row['network_attempts']
    assert row['model_dispatches'] == row['physical_capture_calls'] == 0
    return row

@pytest.mark.parametrize('retention', [1, 30, 120])
def test_status_is_disabled_and_retention_is_metadata(tmp_path, retention):
    row = run(tmp_path, 'awareness_status', settings={'retention_seconds': retention})
    status = row['observation']['status']
    assert row['error'] is None
    assert not any((status[key] for key in ('available', 'capture_active', 'enabled', 'context_available')))
    assert status['expires_at'] is None and status['retention_seconds'] == retention
    assert not any(status['actions'].values())

@pytest.mark.parametrize('action', ['enable', 'disable', 'capture', 'analyze', 'stop'])
def test_screen_mutation_route_is_not_registered(tmp_path, action):
    row = run(tmp_path, 'denied_awareness_mutation', request={'action': action})
    assert row['error'] is None and row['observation']['http_status'] == 404
    assert not row['observation']['status']['capture_active']
    assert row['observation']['owned_server_closed']

@pytest.mark.parametrize('case_request', [{'authorized': False}, {'foreign_origin': True}, {'stop_active': True}])
def test_original_http_authority_and_shutdown_states_do_not_add_capture(tmp_path, case_request):
    row = run(tmp_path, 'denied_awareness_mutation', request=case_request)
    assert row['error'] is None and row['observation']['http_status'] == (404 if case_request.get('stop_active') else 403)
    assert not row['observation']['status']['context_available']

@pytest.mark.parametrize('name', ['screen.capture', 'screen.describe', 'vision.analyze', 'camera.capture'])
def test_registry_does_not_advertise_missing_perception(tmp_path, name):
    row = run(tmp_path, 'registry_capability_missing', request={'name': name})
    assert row['error']['type'] == 'UnknownToolError'
    # Explicit OCR is now implemented; unrestricted capture, camera, and
    # multimodal vision APIs remain unavailable.
    assert row['observation']['perception_definitions'] == ['screen.read_text']

@pytest.mark.parametrize('content', [[{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,aQ=='}}], [{'type': 'text', 'text': 'Synthetic'}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,Yg=='}}], {'type': 'image', 'value': 'synthetic'}])
def test_original_native_adapter_rejects_multimodal_before_network(tmp_path, content):
    row = run(tmp_path, 'native_multimodal_rejected', request={'messages': [{'role': 'user', 'content': content}]})
    assert row['error']['type'] == 'ModelSelectionError'
    assert 'multimodal' in row['error']['message']

@pytest.mark.parametrize('case_request,reason', [({}, 'required_capability_not_verified'), ({'legacy_default': True}, 'required_capability_not_verified'), ({'remote': True, 'row': {'capabilities': ['text', 'vision']}}, 'transport_unsupported_tool_or_vision'), ({'row': {'capabilities': ['text', 'vision'], 'allowed_categories': ['project']}}, 'privacy_not_authorized'), ({'row': {'capabilities': ['text', 'vision'], 'max_context_verified': 0}}, 'required_context_not_verified')])
def test_original_vision_eligibility_requires_correct_transport_privacy_and_proof(tmp_path, case_request, reason):
    row = run(tmp_path, 'vision_eligibility', request=case_request)
    assert row['error'] is None and reason in row['observation']['reasons']

def test_missing_configured_model_is_rejected_by_original_registry_without_dispatch(tmp_path):
    row = run(tmp_path, 'vision_eligibility', request={'model': 'campaign-only-missing-vision-model'})
    assert row['error']['type'] == 'KeyError'
    assert row['observation']['requested_model'] == 'campaign-only-missing-vision-model'
    assert 'configured_model_id' not in row['observation']

@pytest.mark.parametrize('case_request', [{}, {'token_present': False}, {'error': 'Synthetic disconnection'}])
def test_real_react_screen_component_renders_disabled_current_implementation(tmp_path, case_request):
    row = run(tmp_path, 'frontend_disabled_projection', request=case_request)
    assert row['error'] is None
    html = row['observation']['html']
    assert 'disabled=""' in html and 'No screen image is being collected' in html
    assert 'saved policy, not an active capture session' in html

@pytest.mark.parametrize('operation', ['capture', 'analyze', 'expiry', 'sensitivity'])
def test_missing_pipeline_semantics_are_not_scored_as_successful_execution(tmp_path, operation):
    row = run(tmp_path, operation)
    assert row['error'] is None and row['observation']['classification'] == 'NOT_IMPLEMENTED'
    assert row['observation']['operation_executed'] is False

def test_executor_rejects_oracles_before_storage(tmp_path):
    with pytest.raises(ValueError, match='expected answers'):
        run_case({'operation': 'capture', 'expected': 'answer'}, tmp_path / 'forbidden')
    assert not (tmp_path / 'forbidden').exists()
