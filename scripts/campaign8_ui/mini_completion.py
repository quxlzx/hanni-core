"""Separate manager-authorized one-request Mini/owned-history extension.

Reuses the unchanged original streaming admission/backend and per-process
one-request guard. Earlier two-request cohorts and their limits stay immutable.
"""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .streaming import PROMPT
from .supplement import button, field

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Keep every earlier model-request seal and result.')
    inputs = [{'id': 'mini-extension-one-genuine-send', 'route': 'chat', 'surface': 'mini', 'operation': 'local_sequence', 'fixture_id': 'original-genuine-streaming', 'window_size': [880, 560], 'steps': [field('textarea[aria-label="Message HANNI"]', PROMPT), button('Send', settle_ms=0)], 'readback_paths': []}, {'id': 'mini-extension-main-clear-cancel', 'route': 'chat', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-genuine-streaming', 'window_size': [1280, 800], 'steps': [{'action': 'click', 'selector': '#chat-clear'}, button('Cancel')], 'readback_paths': []}, {'id': 'mini-extension-main-clear-confirm', 'route': 'chat', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-genuine-streaming', 'window_size': [1280, 800], 'steps': [{'action': 'click', 'selector': '#chat-clear'}, {'action': 'click', 'selector': 'dialog button.danger-button', 'settle_ms': 1500}], 'readback_paths': []}]
    oracles = [{'id': inputs[0]['id'], 'check': {'actual_generation_POSTs': 1, 'surface': 'actual_original_Mini', 'raw_SSE_original_API_SQLite_equal': True, 'Mini_rendered_actual_completed_reply': True, 'semantic_answer_quality': 'NOT_GRADED', 'no_audio_or_tool_dispatch': True}}, {'id': inputs[1]['id'], 'check': {'actual_original_confirmation_closed': True, 'owned_messages_and_token_unchanged': True}}, {'id': inputs[2]['id'], 'check': {'actual_original_confirmation_closed': True, 'owned_messages_after': 0, 'owned_token_rotated': True, 'old_token_status': 403, 'new_token_status': 200, 'owner_history_and_model_untouched': True}}]
    for item in inputs:
        validate_input(item)
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': 3, 'hashes': hashes, 'execution_attempted': False, 'scope': 'Exactly one additional genuine existing-endpoint request, then original native Clear cancel/confirm on owned history only.', 'max_additional_generation_requests': 1, 'previous_genuine_generation_requests': 2, 'unchanged_original_request_time_identity_RAM_admission_guards': True, 'minimum_available_RAM_MiB': 3072, 'critical_used_percent_exclusive': 90, 'max_tokens': 64, 'temperature': 0, 'HTTP_timeout_seconds': 30, 'audio_tools_provider_or_new_model_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
