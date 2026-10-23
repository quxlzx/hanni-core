"""Independent prospective protocol safety controls, no hardware/model use."""
import pytest
from scripts.campaign7_verification.boundaries import capture_pre_stopped, stt_contract, failed_pump_snapshot
from scripts.campaign7_verification.boundaries import continuous_segment_boundary, completed_pump_restart, stopped_pump_start, managed_start_failure, managed_closed_inflight, synthesis_only_snapshot, failed_voice_action, pipeline_retention_end

@pytest.mark.parametrize('block_samples', [256, 1024])
def test_cancelled_before_capture_never_opens_device(block_samples):
    receipt = capture_pre_stopped(block_samples=block_samples)
    assert receipt['chunks'] == 0
    assert receipt['stream_constructed'] == 0
    assert receipt['stream_entered'] == 0

@pytest.mark.parametrize('rate', [11025, 44100])
def test_decoder_rejects_unsupported_rate_before_interpreting_samples(rate):
    receipt = stt_contract(sample_rate=rate)
    assert receipt['rejected']
    assert receipt['model_calls'] == 0

def test_decoder_silence_bypasses_model():
    receipt = stt_contract(samples=(0, 0, 0, 0))
    assert receipt['text'] == ''
    assert receipt['model_calls'] == 0

def test_decoder_mono_supported_positive():
    receipt = stt_contract()
    assert not receipt['rejected']
    assert receipt['model_calls'] == 1

def test_decoder_rejects_nonmono():
    receipt = stt_contract(channels=3)
    assert receipt['rejected']
    assert receipt['model_calls'] == 0

def test_failed_capture_pump_has_unavailable_controls():
    receipt = failed_pump_snapshot()
    assert not receipt['pump_running']
    assert not receipt['available']
    assert not receipt['microphone_active']

def test_continuous_speech_after_maximum_segment_is_not_lost():
    assert continuous_segment_boundary()['record_count'] == 4

def test_finished_pump_restart_has_a_fresh_consumer_queue():
    assert completed_pump_restart()['second'] == 'owned-cycle-2'

def test_stopped_pump_cannot_reenter_a_pipeline():
    assert stopped_pump_start()['pipeline_entries'] == 0

def test_failed_unmute_start_preserves_muted_state():
    receipt = managed_start_failure()
    assert receipt['paused']
    assert not receipt['running']

def test_shutdown_with_pending_record_discards_that_record():
    receipt = managed_closed_inflight()
    assert receipt['thread_closed']
    assert receipt['outcome'] == ['discarded']

def test_preparing_synthesis_is_not_observed_speech_playback():
    receipt = synthesis_only_snapshot()
    assert not receipt['actual_playback_created']
    assert not receipt['speaking']
    assert receipt['metrics']['first_audible_ms'] is None

@pytest.mark.parametrize('action', ['listen', 'unmute'])
def test_failed_voice_disallows_activity_increasing_commands(action):
    receipt = failed_voice_action(action)
    assert not receipt['before']['available']
    assert receipt['rejected']
    assert receipt['error_class'] == 'RuntimeError'
    assert receipt['fresh_pipeline_entries'] == 0
    assert not receipt['engaged_after']

@pytest.mark.parametrize('action', ['mute', 'interrupt'])
def test_failed_voice_preserves_activity_reducing_commands(action):
    receipt = failed_voice_action(action)
    assert not receipt['rejected']
    assert receipt['fresh_pipeline_entries'] == 0
    if action == 'interrupt':
        assert receipt['playback_stops'] == 1

@pytest.mark.parametrize('mode', ['complete', 'cancel', 'error'])
def test_ended_pipeline_does_not_retain_ephemeral_audio_or_transcripts(mode):
    receipt = pipeline_retention_end(mode)
    assert receipt['raw_audio_records'] == 0
    assert receipt['transcript_records'] == 0
    assert not receipt['segment_active']
    assert receipt['segment_recent_chunks'] == 0
    assert receipt['vad_resets'] >= 1

@pytest.mark.parametrize('field', ['expected', 'oracle'])
def test_final_executor_never_accepts_answer_material(field, tmp_path):
    from scripts.campaign7_verification.executor import run_case
    with pytest.raises(ValueError, match='Input-only'):
        run_case({'id': 'public-dev', 'operation': 'relevance', 'request': {'text': 'Hanni'}, field: {}}, tmp_path)

def test_missing_null_observation_is_not_scored_as_measured_null():
    from scripts.campaign7_verification.scoring import grade
    receipt = {'id': 'public-dev', 'domain': 'voice', 'category': 'timing', 'observed': {}, 'receipt_sha256': 'proof'}
    assert not grade(receipt, {'expected': {'first_audible_ms': None}})['passed']

def test_fixture_error_cannot_pass_matching_predicates():
    from scripts.campaign7_verification.scoring import grade
    receipt = {'id': 'public-dev', 'domain': 'voice', 'category': 'state', 'observed': {'active': False}, 'receipt_sha256': 'proof', 'harness_error': {'type': 'RuntimeError'}}
    assert not grade(receipt, {'expected': {'active': False}})['passed']

def test_private_wrapper_maps_original_wake_fields_without_audio(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'operation': 'relevance', 'request': {'text': 'Honey, inspect the green draft.', 'engaged': False}}, tmp_path)
    assert receipt['wake_detected'] and receipt['relevant']
    assert not receipt['follow_up']

def test_private_wrapper_empty_transcript_preserves_actual_engagement(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'operation': 'relevance', 'request': {'text': '', 'engaged': True}}, tmp_path)
    assert not receipt['relevant'] and receipt['engaged']

def test_private_wrapper_barge_receipt_retains_original_echo_decision(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'operation': 'barge', 'request': {'text': 'the green draft is ready', 'spoken_text': 'The green draft is ready for review.'}}, tmp_path)
    assert receipt['echo'] and (not receipt['interrupt'])

def test_private_wrapper_decoder_failure_is_a_typed_protocol_result(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'operation': 'stt_contract', 'request': {'samples': [13, -9], 'model_error': 'owned decoder fault'}}, tmp_path)
    assert receipt['rejected'] and receipt['typed_error'] == 'SttError'
    assert receipt['model_calls'] == 1

def test_private_wrapper_restart_uses_the_input_records(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'operation': 'pump_restart', 'request': {'first_record': 'old isolated message', 'second_record': 'new isolated message'}}, tmp_path)
    assert receipt['second'] == 'new isolated message'
    assert receipt['second_record_delivered'] and (not receipt['stale_record_delivered'])

def test_private_wrapper_closed_voice_has_no_held_thread(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'operation': 'voice_snapshot', 'request': {'pump_state': 'closed'}}, tmp_path)
    assert not receipt['available'] and receipt['first_audible_ms'] is None

def test_private_wrapper_missing_capability_uses_original_registry(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'domain': 'screen', 'operation': 'registry_capability_missing', 'request': {'name': 'screen.unregistered_owned_probe'}}, tmp_path / 'owned')
    assert not receipt['registered']
    assert receipt['original_error']['type'] == 'UnknownToolError'
    assert receipt['capture_calls'] == receipt['dispatch_calls'] == 0

def test_private_wrapper_awareness_keeps_absent_expiry_distinct(tmp_path):
    from scripts.campaign7_verification.executor import run_case
    receipt = run_case({'id': 'public-dev', 'domain': 'screen', 'operation': 'awareness_status', 'request': {'settings': {'retention_seconds': 19}}}, tmp_path / 'owned')
    assert receipt['retention_seconds'] == 19
    assert receipt['expires_at'] is None and receipt['expiry_enforcement'] == 'not_implemented'
    assert not receipt['capture_active'] and receipt['actions_all_false']
