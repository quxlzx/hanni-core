"""Two prospectively sealed actual enabled draft controls; no execution."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, select

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all earlier inputs and evidence.')
    inputs = [{'id': 'draft-final-preferred-endpoint', 'route': 'model-routing', 'steps': [select('Selection policy', 'manual'), select('Preferred endpoint', 'local:supervisor'), select('Selection policy', 'balanced')], 'readback_paths': ['/api/model-routing']}, {'id': 'draft-final-add-through-hanni', 'route': 'memory', 'steps': [button('Add through HANNI')], 'readback_paths': ['/api/memory/explorer?limit=30']}]
    oracles = [{'id': inputs[0]['id'], 'check': {'actual_draft_endpoint': 'local:supervisor', 'final_draft_policy': 'balanced', 'persisted_original_policy_unchanged': True, 'no_policy_save_or_inference_or_eligibility_override': True}}, {'id': inputs[1]['id'], 'check': {'actual_route': 'chat', 'actual_draft': 'Remember that ', 'authoritative_memories_and_pending_unchanged': True, 'no_chat_submission_or_tool_execution_or_model_inference': True}}]
    for row in inputs:
        row.update({'surface': 'desktop', 'operation': 'local_sequence', 'window_size': [1280, 800], 'fixture_id': 'original-populated-dense'})
        validate_input(row)
    for oracle in oracles:
        oracle['scope'] = 'Actual original native draft-only controls on disposable original services. A configured endpoint option is not a healthy/eligible inference endpoint; a prepared draft is not persistent memory.'
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': 2, 'hashes': hashes, 'execution_attempted': False, 'model_or_tool_or_provider_execution_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
