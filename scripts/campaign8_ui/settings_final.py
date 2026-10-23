"""Separate prospectively sealed status/configuration checks, not device use."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all earlier prospective inputs and errors.')
    rows = [{'id': 'settings-final-screen-status', 'route': 'screen', 'steps': [{'action': 'click', 'role': 'button', 'name': 'Refresh status'}, {'action': 'click', 'selector': '.awareness-diagnostic summary'}], 'readback_paths': ['/api/awareness']}, {'id': 'settings-final-audio-default-save', 'route': 'settings', 'steps': [{'action': 'select', 'selector': '#microphone-device', 'value': 'default'}, {'action': 'select', 'selector': '#speaker-device', 'value': 'default'}, {'action': 'click', 'selector': '#audio-apply', 'settle_ms': 700}], 'readback_paths': ['/api/audio-devices']}, {'id': 'settings-final-gpu-absence', 'route': 'settings', 'steps': [{'action': 'click', 'role': 'button', 'name': 'Refresh GPUs'}], 'readback_paths': ['/api/gpu-routing']}]
    checks = [{'actual_status_refresh_and_reason_details': True, 'available': False, 'capture_pipeline_not_implemented': True}, {'input_id': 'default', 'output_id': 'default', 'persisted_under_exact_owned_data_root': True, 'no_mic_speaker_activation_or_runtime_restart': True}, {'original_device_projection_matches_disabled_or_enabled_controls': True, 'no_gpu_config_apply_or_restart': True}]
    for row in rows:
        row.update({'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-backend', 'window_size': [1280, 800]})
        validate_input(row)
    oracles = [{'id': row['id'], 'check': check, 'scope': 'Original native/local configuration only. No screen acquisition, physical audio, GPU placement or owner preference write.'} for row, check in zip(rows, checks)]
    output.mkdir(parents=True)
    hashes = {}
    for name, value in [('inputs.json', rows), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': 3, 'hashes': hashes, 'execution_attempted': False, 'physical_audio_or_capture_authorized': False, 'generation_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
