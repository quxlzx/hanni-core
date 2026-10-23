"""Input-only Campaign 7 executor. No oracle import or device/model startup."""
from __future__ import annotations
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
import re
import threading
from types import SimpleNamespace
from unittest.mock import patch
from hanni.core.activity import Activity
from hanni.core.interaction import InteractionState
from hanni.core.shutdown import EmergencyStop
from hanni.dashboard.voice import ManagedTranscriptPump, VoiceControl
from hanni.speech.barge_in import BargeInClassifier
from hanni.speech.live import TranscriptPump
from hanni.speech.relevance import SpeechRelevanceClassifier, DEFAULT_FILLER_WORDS
from scripts.campaign7_verification.boundaries import FailingPipeline, capture_pre_stopped, completed_pump_restart, stt_contract

def voice_snapshot(request):
    entered = threading.Event()

    class IdlePipeline:

        def run(self, stop_event):
            entered.set()
            stop_event.wait(2)
            return iter(())
    mode = request.get('pump_state', 'running')
    pump = TranscriptPump(FailingPipeline() if mode == 'failed' else IdlePipeline())
    managed = ManagedTranscriptPump(lambda: TranscriptPump(IdlePipeline()), pump)
    if mode in {'failed', 'running'}:
        managed.start()
        if mode == 'failed':
            pump.thread.join(1)
            if pump.thread.is_alive():
                raise RuntimeError('Owned failure did not terminate')
        elif not entered.wait(1):
            managed.stop()
            raise RuntimeError('Owned pipeline did not enter')
    elif mode == 'paused':
        managed.pause()
    elif mode == 'closed':
        managed.stop()
    else:
        raise ValueError('Unsupported pump state')
    activity, state = (Activity(), InteractionState())
    if request.get('playback_active'):
        leaf = SimpleNamespace(active=True)
        leaf.stop = lambda: setattr(leaf, 'active', False)
        state.playback = leaf
    controller = VoiceControl()
    controller.bind(managed, SpeechRelevanceClassifier(), SimpleNamespace(context=SimpleNamespace(emergency_stop=EmergencyStop())), 'hanni')
    try:
        with patch('hanni.dashboard.voice.activity', activity), patch('hanni.dashboard.voice.interaction', state), state.synthesis() if request.get('synthesizing') else nullcontext():
            observed = controller.snapshot()
            observed['first_audible_ms'] = observed['metrics']['first_audible_ms']
            observed['playback_exists'] = state.playback is not None
            observed['scope'] = 'Original voice/interaction/pump; controlled pipeline/playback; no audible observation'
            return observed
    finally:
        controller.unbind(managed)
        managed.stop()
        if pump.thread and pump.thread.is_alive():
            raise RuntimeError('Owned voice thread leaked')

def screen_case(case, root):
    from scripts.campaign7_screen.audit import run_case
    receipt = run_case(case, root)
    operation = case['operation']
    request = case.get('request', {})
    observation = receipt.get('observation', {})
    result = dict(observation.get('status', {}))
    error = receipt.get('error')
    result.update(capture_calls=receipt['physical_capture_calls'], dispatch_calls=receipt['model_dispatches'], model_calls=receipt['model_dispatches'], original_error=error, raw_receipt=receipt)
    if operation == 'awareness_status':
        result['actions_all_false'] = not any(result.get('actions', {}).values())
        result['expiry_enforcement'] = 'not_implemented'
    elif operation == 'denied_awareness_mutation':
        result['denied'] = 400 <= observation.get('http_status', 0) < 500
    elif operation == 'registry_capability_missing':
        name = observation.get('requested_name', request.get('name'))
        result['registered'] = name in observation.get('registered_names', [])
        result['implementation'] = 'not_implemented' if not result['registered'] else 'registered'
        result['sensitivity_enforcement'] = 'not_implemented'
        result['privacy_capture_violations'] = receipt['physical_capture_calls']
    elif operation == 'native_multimodal_rejected':
        result['rejected'] = bool(error and error['type'] == 'ModelSelectionError')
        result['vision_accuracy'] = None
    elif operation == 'vision_eligibility':
        result['eligible'] = not observation.get('reasons', []) and error is None
        result['scope'] = 'Original pure eligibility guard with controlled row; request capabilities are task requirements'
        result['model_field_scope'] = 'Original model_spec catalog lookup only; not live endpoint/model proof' if isinstance(request.get('model'), str) else 'No string model supplied; no configured-model existence probe'
    elif operation == 'frontend_disabled_projection':
        html = observation.get('html', '')
        buttons = re.findall('<button\\b[^>]*>', html, flags=re.I)
        result['controls_disabled'] = bool(buttons) and all((re.search('\\bdisabled(?:=|\\s|>)', b) for b in buttons))
        result['controls_disabled'] = bool(result['controls_disabled'])
        result['capture_enabled'] = result.get('enabled')
        result['rendered_component'] = 'Original ScreenAwarenessPage SSR'
        result['requested_surface_scope'] = 'surface metadata is not a separate page execution; shipped UI evidence is reported independently'
    return result

def run_case(case, root):
    if set(case) & {'expected', 'oracle', 'checker_inputs', 'answers'}:
        raise ValueError('Input-only execution cannot receive expected answers')
    request = case.get('request', {})
    operation = case['operation']
    if case.get('domain') == 'screen':
        return screen_case(case, Path(root))
    if operation == 'relevance':
        classifier = SpeechRelevanceClassifier()
        if request.get('engaged'):
            classifier.classify('hanni')
        decision = classifier.classify(request['text'])
        observed = asdict(decision)
        observed.update(wake_detected=decision.wake_word_detected, disengage=decision.disengaged, filler_only=decision.filler_ignored, engaged=classifier.is_engaged(), scope='Original deterministic transcript classifier; no STT/audio')
        return observed
    if operation == 'barge':
        decision = BargeInClassifier(filler_words=DEFAULT_FILLER_WORDS).classify(request['text'], spoken_text=request.get('spoken_text', ''))
        observed = asdict(decision)
        observed.update(route_as_request=decision.route_after_interrupt, echo=decision.echo_ignored, scope='Original transcript heuristic; no acoustic echo or owner attribution')
        return observed
    if operation == 'stt_contract':
        return stt_contract(**request)
    if operation == 'capture_pre_stopped':
        return capture_pre_stopped(sample_rate=request.get('sample_rate', 16000), block_samples=request.get('block_samples', 512))
    if operation == 'pump_restart':
        observed = completed_pump_restart(**request)
        observed.update(second_record_delivered=observed['second'] == request['second_record'], stale_record_delivered=observed['second'] == request['first_record'])
        return observed
    if operation == 'voice_snapshot':
        return voice_snapshot(request)
    raise ValueError('Unsupported controlled operation')
