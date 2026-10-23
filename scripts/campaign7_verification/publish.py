"""Oracle-free final publication from immutable closed receipts/grades."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def publish(run, destination):
    run, destination = (Path(run), Path(destination))
    closed = json.loads((run / 'CLOSED.json').read_text(encoding='utf-8'))
    graded = json.loads((run / 'GRADES.json').read_text(encoding='utf-8'))
    receipt_ids = {r['id'] for r in closed['receipts']}
    if len(receipt_ids) != closed['case_count'] or receipt_ids != {r['id'] for r in graded['grades']}:
        raise ValueError('Final coverage mismatch')
    for row in closed['receipts']:
        if sha(run / row['path']) != row['sha256']:
            raise ValueError('Final raw receipt changed')
    failures = []
    for row in graded['grades']:
        if not row['passed']:
            failures.append({'id': row['id'], 'domain': row['domain'], 'category': row['category'], 'failed_fields': [key for key, check in row['checks'].items() if not check['passed']], 'harness_error_type': row['harness_error']['type'] if row.get('harness_error') else None, 'receipt_sha256': row['receipt_sha256']})
    payload = dict(scope=closed['scope'], final_once=True, case_count=closed['case_count'], aggregate=graded['aggregate'], strict_failures=failures, closed_sha256=sha(run / 'CLOSED.json'), grades_sha256=sha(run / 'GRADES.json'), raw_receipts=closed['receipts'], private_seal=closed['seal'], source_before=closed['source_before'], source_after=closed['source_after'], raw_elapsed_scope='Controlled adapter/case duration; not acoustic/model/vision latency', duration_seconds=closed['duration_seconds'], actual_asr_calls=closed['actual_asr_calls'], speaker_playbacks=closed['speaker_playbacks'], physical_audio_capture_calls=closed['physical_audio_capture_calls'], actual_vision_inference_calls=closed['actual_vision_inference_calls'], physical_screen_capture_calls=closed['physical_screen_capture_calls'], physical_or_model_metrics={key: None for key in ('wake_precision', 'wake_recall', 'word_error_rate', 'end_of_speech_latency_ms', 'first_audible_latency_ms', 'acoustic_interruption_latency_ms', 'vision_accuracy', 'capture_to_response_latency_ms')}, limitations=['Matched software predicates do not imply microphone, speaker, room-noise, VAD/STT or multimodal model success.', 'Screen implementation and retention enforcement are absent; original disabled projection is audited.', 'Capability and model labels in controlled eligibility rows are not real hardware/model evidence.', 'Frontend final projection uses ScreenAwarenessPage SSR; actual shipped pages have separate seven-case browser evidence.', 'Synthetic profile/surface/image labels can be metadata only; string model lookup is catalog-only, not live readiness.', 'Strict oracles are immutable. Manual explanations never promote failed cases.'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8', newline='\n')
    return payload
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = publish(args.run, args.out)
    print(json.dumps(result['aggregate']))
