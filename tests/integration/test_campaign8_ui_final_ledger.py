"""Accounting guard contracts; these synthetic inputs are not live UI proof."""
import hashlib
import json
import pytest
from scripts.campaign8_ui.final_ledger import stream_assessments

def proof(tmp_path):
    source = {'routes': [{'route': 'chat'}], 'modules': [{'controls': [{'id': 'workspace.tsx:10:1', 'line': 10, 'component': 'App', 'tag': 'textarea', 'attributes': {'id': '"chat-input"'}}, {'id': 'workspace.tsx:20:1', 'line': 20, 'component': 'App', 'tag': 'button', 'attributes': {'aria-label': '"Send message"'}}]}]}
    raw_path = tmp_path / 'native.json'
    raw = {'assets': {}, 'actions': [{'id': 'fill', 'input': {'action': 'fill', 'selector': '#chat-input'}}, {'id': 'send', 'input': {'action': 'click', 'role': 'button', 'name': 'Send message'}}, {'id': 'unrelated', 'input': {'action': 'click', 'role': 'button', 'name': 'Clear history'}}]}
    raw_path.write_text(json.dumps(raw), encoding='utf8')
    value = {'evidence': [{'path': str(raw_path), 'sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest()}], 'assertions': {'raw_SSE_equals_original_API': True, 'raw_SSE_equals_persisted_SQLite_assistant': True, 'full_native_render_equals_API_in_two_samples': True}, 'scope': 'Synthetic accounting contract only.', 'verdict': 'contract'}
    review = tmp_path / 'review.json'
    review.write_text(json.dumps(value), encoding='utf8')
    return (source, raw_path, review, value)

def test_stream_credit_requires_independent_native_storage_correspondence(tmp_path):
    source, _, review, value = proof(tmp_path)
    value['assertions']['full_native_render_equals_API_in_two_samples'] = False
    review.write_text(json.dumps(value), encoding='utf8')
    with pytest.raises(ValueError, match='correspondence'):
        stream_assessments(source, review)

def test_changed_stream_receipt_cannot_keep_frozen_review_credit(tmp_path):
    source, raw, review, _ = proof(tmp_path)
    raw.write_text('{}', encoding='utf8')
    with pytest.raises(ValueError, match='changed'):
        stream_assessments(source, review)

def test_stream_credit_does_not_infer_native_clear_or_other_surface_actions(tmp_path):
    source, _, review, _ = proof(tmp_path)
    rows = stream_assessments(source, review)
    assert {r['source_slot_ids'][0] for r in rows} == {'workspace.tsx:10:1', 'workspace.tsx:20:1'}
    assert {r['action_evidence'][0]['action_id'] for r in rows} == {'fill', 'send'}
    assert all((r['readback_evidence'] and 'not tool selection' in r['coverage_scope'] for r in rows))
