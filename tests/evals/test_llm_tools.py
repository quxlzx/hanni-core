import pytest
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from hanni.evals.llm_tools import _answer_checks, audit_scenarios, evaluate_scenario, load_scenarios, render_trace, rescore_saved_report, run_cli
from hanni.evals.llm_tool_catalog import fallback_result
from hanni.evals.routing import build_default_host as _build_default_host
from hanni.evals.fixtures import fixture_timezone
from hanni.cli import build_parser
from hanni.models.client import ModelToolCall, ModelTurn, _parse_tool_turn

class ScriptedModel:

    def __init__(self, turns):
        self.turns = iter(turns)

    def complete_with_tools(self, messages, *, tools, **kwargs):
        return next(self.turns)

def build_default_host():
    return _build_default_host(timezone_name=fixture_timezone(Path('evals/llm_tools/cases.jsonl')))

def call(name, arguments=None):
    return ModelTurn('', (ModelToolCall('test-call', 'hanni__' + name.replace('.', '__'), arguments or {}),), {'completion_tokens': 10})

def scenario(name):
    return next((c for c in load_scenarios() if c['id'] == name))

def test_calendar_next_mock_interval_matches_the_event_timestamp():
    from datetime import datetime
    for case in load_scenarios():
        fixture = case.get('results', {}).get('google_calendar.next')
        if not fixture:
            continue
        data = fixture['data']
        if not data.get('event'):
            continue
        assert data['event_start_local'] == data['event']['start_local'], case['id']
        start = datetime.fromisoformat(data['event_start_local'])
        current = datetime.fromisoformat(data['current_local_time'])
        assert data['minutes_until_start'] == round((start - current).total_seconds() / 60), case['id']

def test_reviewed_numeric_and_semantic_oracles_accept_derived_facts_but_reject_overclaims():

    def observed(case_id, tool):
        item = scenario(case_id)['results'][tool]
        return ([item], {tool})
    case = scenario('DIAG-022')
    evidence, called = observed('DIAG-022', 'system.performance')
    assert not _answer_checks(case, 'No resource is currently maxed out.', evidence, called)['missing_claims']
    case = scenario('DIAG-024')
    assert _answer_checks(case, 'The slowdown is likely due to Chrome.', evidence, called)['unsupported_claims']
    case = scenario('DIAG-038')
    evidence, called = observed('DIAG-038', 'process.top_cpu')
    assert not _answer_checks(case, 'MsMpEng.exe uses 71% CPU; Defender scans files to detect malware.', evidence, called)['unsupported_claims']
    case = scenario('CAL-017')
    evidence, called = observed('CAL-017', 'google_calendar.create')
    assert not _answer_checks(case, 'Office hours was created on October 5th, 2026.', evidence, called)['ungrounded_numbers']
    case = scenario('CAL-005')
    evidence, called = observed('CAL-005', 'google_calendar.agenda')
    assert not _answer_checks(case, 'Free from 6 PM (18:00) until 7 PM, then TASA.', evidence, called)['ungrounded_numbers']
    assert _answer_checks(case, 'Yes, free after 6; TASA at 7.', evidence, called)['missing_claims']
    case = scenario('DIAG-041')
    evidence, called = observed('DIAG-041', 'gpu.top_processes')
    assert not _answer_checks(case, 'game.exe uses 15.46 GB VRAM.', evidence, called)['ungrounded_numbers']
    case = scenario('DIAG-042')
    evidence, called = observed('DIAG-042', 'gpu.top_processes')
    evidence.append(fallback_result('gpu.memory', case))
    called.add('gpu.memory')
    assert 'used_gpu_memory_exceeds_total' in _answer_checks(case, '16.28 GB of 16 GB VRAM used.', evidence, called)['unsupported_claims']

def test_multiround_cpu_evidence_is_required_and_handlers_cannot_execute(monkeypatch):
    host = build_default_host()
    monkeypatch.setattr(host, 'call', lambda *a: pytest.fail('real tool call'))
    client = ScriptedModel([call('system.stats'), call('process.top_cpu'), ModelTurn('CPU pressure is high at 97%. python.exe is the contributor at 88%.', usage={'completion_tokens': 20})])
    report = evaluate_scenario(host, client, scenario('DIAG-001'))
    assert report['passed']
    assert report['multi_tool_pass']
    assert report['tokens_generated'] == 40
    assert report['latency_ms'] >= 0

def test_trace_shows_observable_calls_results_and_scores_without_hidden_reasoning():
    host = build_default_host()
    case = scenario('DIAG-001')
    model = ScriptedModel([call('system.stats'), call('process.top_cpu'), ModelTurn('CPU is at 97%; python.exe uses 88%.')])
    trace = render_trace(host, case, evaluate_scenario(host, model, case))
    assert 'Request:' in trace and 'MCP menu:' in trace
    assert 'Round 1: system.stats' in trace and 'Mock result:' in trace
    assert 'Final answer:' in trace and 'Scores:' in trace
    assert 'chain-of-thought' not in trace

def test_interrupted_live_eval_resumes_without_duplicate_cases(tmp_path, monkeypatch):
    from hanni.evals import llm_tools
    cases = [scenario('CHAT-004'), scenario('CHAT-005')]
    monkeypatch.setattr(llm_tools, 'load_scenarios', lambda _path: cases)

    class FakeClient:
        calls = 0
        interrupt_on = 2

        def __init__(self, *_args, **_kwargs):
            pass

        def health(self):
            return SimpleNamespace(ok=True, to_dict=lambda: {'ok': True})

        def complete_with_tools(self, *_args, **_kwargs):
            type(self).calls += 1
            if type(self).calls == type(self).interrupt_on:
                raise KeyboardInterrupt
            return ModelTurn('Got it.', usage={'prompt_tokens': 20, 'completion_tokens': 3})
    monkeypatch.setattr(llm_tools, 'LlamaCppClient', FakeClient)
    output = tmp_path / 'resume.json'
    args = SimpleNamespace(model_id=None, endpoint=None, api_model=None, cases=Path('evals/llm_tools/cases.jsonl'), family=None, case_id=None, audit=False, trace=False, resume=False, json=output)
    with pytest.raises(KeyboardInterrupt):
        run_cli(args, config_dir=Path('config'), data_dir=tmp_path / 'data', env={})
    checkpoint = json.loads(output.read_text(encoding='utf-8'))
    assert checkpoint['status'] == 'running'
    assert [row['id'] for row in checkpoint['results']] == ['CHAT-004']
    FakeClient.interrupt_on = -1
    args.resume = True
    assert run_cli(args, config_dir=Path('config'), data_dir=tmp_path / 'data', env={}) == 0
    final = json.loads(output.read_text(encoding='utf-8'))
    assert final['status'] == 'completed'
    assert [row['id'] for row in final['results']] == ['CHAT-004', 'CHAT-005']
    assert FakeClient.calls == 3

def test_correct_sounding_answer_without_observed_evidence_fails():
    client = ScriptedModel([ModelTurn('CPU pressure is high. python.exe is the contributor.')] * 3)
    report = evaluate_scenario(build_default_host(), client, scenario('DIAG-001'))
    assert not report['passed']
    assert not report['tool_selection_pass']
    assert not report['answer_checks']['evidence_grounded']

def test_healthy_case_rejects_invented_diagnosis_and_numbers():
    client = ScriptedModel([call('system.stats'), ModelTurn('The machine is healthy but the GPU is overloaded at 99%.')])
    report = evaluate_scenario(build_default_host(), client, scenario('DIAG-021'))
    assert not report['passed']
    assert report['answer_checks']['unsupported_claims']
    assert report['answer_checks']['ungrounded_numbers'] == ['99']

def test_healthy_machine_can_have_no_obvious_problem():
    client = ScriptedModel([call('system.stats'), ModelTurn("I don't see an obvious bottleneck in these measurements.")])
    report = evaluate_scenario(build_default_host(), client, scenario('DIAG-021'))
    assert report['passed']

def test_unsupported_bottleneck_check_respects_causal_clause_boundary():
    case = scenario('DIAG-015')
    grounded = _answer_checks(case, 'RAM is at 58%, so the bottleneck is GPU; game.exe uses it.', [], {'system.stats', 'gpu.top_processes'})
    unsupported = _answer_checks(case, 'RAM is the bottleneck.', [], set())
    assert grounded['unsupported_claims'] == []
    assert unsupported['unsupported_claims']

def test_memory_pressure_requires_contributor_and_tentative_paging():
    client = ScriptedModel([call('system.stats'), call('process.top_memory'), ModelTurn('Memory pressure is high at 97%. llama-server.exe uses 19 GB. There may be paging.')])
    report = evaluate_scenario(build_default_host(), client, scenario('DIAG-007'))
    assert report['passed']

def test_gpu_mb_to_gb_conversion_and_plain_game_name_are_grounded():
    client = ScriptedModel([call('system.stats'), call('gpu.top_processes'), ModelTurn('The game uses 94% GPU and about 13.7 GB VRAM; the GPU is at 99%.')])
    report = evaluate_scenario(build_default_host(), client, scenario('DIAG-011'))
    assert report['passed']
    assert report['answer_checks']['ungrounded_numbers'] == []

def test_numeric_grounding_accepts_compact_units_thousands_and_measured_rates():
    model = ScriptedModel([call('model.status'), ModelTurn('Qwen3.5-4B has a 16,384 token context.')])
    assert evaluate_scenario(build_default_host(), model, scenario('HANNI-001'))['passed']
    model = ScriptedModel([call('system.performance'), call('process.top_disk_io'), ModelTurn('OneDrive.exe is moving about 217 MB/s of disk I/O.')])
    assert evaluate_scenario(build_default_host(), model, scenario('DIAG-019'))['passed']

def test_numeric_grounding_accepts_exact_derived_ram_and_calendar_intervals():
    model = ScriptedModel([call('system.performance'), call('process.top_memory'), ModelTurn('RAM is 97% used, leaving 0.96 GB of 32 GB. llama-server.exe uses 19 GB.')])
    report = evaluate_scenario(build_default_host(), model, scenario('DIAG-006'))
    assert report['answer_checks']['ungrounded_numbers'] == []
    model = ScriptedModel([call('google_calendar.next'), call('system.stats'), ModelTurn('Class is in 165 minutes, or 2 hours 45 minutes. GPU is 55 C.')])
    report = evaluate_scenario(build_default_host(), model, scenario('MIX-003'))
    assert report['answer_checks']['ungrounded_numbers'] == []

def test_saved_turns_can_be_rescored_without_new_inference():
    case = scenario('DIAG-002')
    model = ScriptedModel([call('system.performance'), call('process.top_cpu'), ModelTurn('Python is using 88% CPU; overall CPU is 97%, so it is the visible bottleneck.')])
    original = evaluate_scenario(build_default_host(), model, case)
    assert original['passed']
    old = {**original, 'passed': False, 'score': 50.0, 'failure_classification': ['MODEL_REASONING_FAILURE']}
    report = {'results': [old], 'summary': {'task_success_rate': 0.0}, 'max_tool_rounds': 3, 'max_tool_calls_per_case': 8}
    replayed = rescore_saved_report(build_default_host(), [case], report)
    assert replayed['corrected_task_success_rate'] == 100.0
    assert replayed['false_negatives_removed'] == ['DIAG-002']

def test_semantic_tool_alternative_needs_verified_media_outcome():
    case = scenario('APP-006')
    assert case['required_any_tools'] == [['spotify.next', 'media.next_track']]
    model = ScriptedModel([call('media.next_track'), ModelTurn("I've skipped to the next track.")])
    report = evaluate_scenario(build_default_host(), model, case)
    assert report['tool_selection_pass']
    assert not report['passed']
    assert 'unverified_media_completion' in report['answer_checks']['unsupported_claims']

def test_disk_io_evidence_alone_can_support_cautious_loading_contributor():
    model = ScriptedModel([call('process.top_disk_io'), ModelTurn('OneDrive.exe has heavy disk I/O and is likely slowing file loading.')])
    report = evaluate_scenario(build_default_host(), model, scenario('DIAG-016'))
    assert report['passed']

def test_relevant_disk_health_check_does_not_make_diagnosis_fail():
    model = ScriptedModel([call('device.disk_health'), call('process.top_disk_io'), ModelTurn('Disk health looks fine; OneDrive.exe has heavy disk I/O and may be slowing loading.')])
    report = evaluate_scenario(build_default_host(), model, scenario('DIAG-018'))
    assert report['passed']

def test_spotify_playback_mock_requires_launch_after_not_running_status():
    model = ScriptedModel([call('spotify.status'), call('spotify.play_pause'), ModelTurn('Spotify could not start playback.')])
    report = evaluate_scenario(build_default_host(), model, scenario('APP-012'))
    assert report['calls'][1]['result']['error']['code'] == 'PRECONDITION_NOT_MET'
    assert not report['passed']

def test_calendar_next_fixture_provides_local_interval():
    data = scenario('CAL-019')['results']['google_calendar.next']['data']
    assert data['current_local_time'] == '2026-09-23T16:15:00-05:00'
    assert data['minutes_until_start'] == 165
    assert data['event_start_local'] == '2026-09-23T19:00:00-05:00'

def test_power_plan_possibility_is_not_scored_as_proven_cause():
    case = scenario('DIAG-026')
    observed = [case['results']['power.plans']]
    certain = _answer_checks(case, 'Power Saver is the primary cause of the slowdown.', observed, {'power.plans', 'system.performance'})
    cautious = _answer_checks(case, 'Power Saver may be contributing to the slowdown.', observed, {'power.plans', 'system.performance'})
    assert 'unverified_power_causality' in certain['unsupported_claims']
    assert cautious['unsupported_claims'] == []

def test_synthetic_app_success_is_explicitly_verified():
    data = scenario('APP-001')['results']['app.open']['data']
    assert data['verified'] is True and data['running'] is True

def test_app_launch_acceptance_alone_is_not_task_success():
    case = dict(scenario('APP-001'))
    case['results'] = {'app.open': {'name': 'app.open', 'ok': True, 'message': 'Launch request sent.', 'data': {'app': 'Discord', 'outcome': 'accepted', 'verified': False}}}
    model = ScriptedModel([call('app.open', {'app': 'Discord'}), ModelTurn('Discord is open.')])
    row = evaluate_scenario(build_default_host(), model, case, max_rounds=2)
    assert not row['passed']
    assert row['completion_ledger'][0]['status'] == 'accepted'

def test_model_gpu_question_fixture_uses_verified_runtime_placement():
    data = scenario('HANNI-003')['results']['model.status']['data']
    assert data['placement_verified'] is True
    assert data['selected_device_name'] == 'AMD Radeon RX 6600 XT'

def test_runaway_generation_is_a_scored_failure():
    model = ScriptedModel([call('system.stats'), ModelTurn('No bottleneck. ' + '0' * 100)])
    report = evaluate_scenario(build_default_host(), model, scenario('DIAG-021'))
    assert report['answer_checks']['generation_runaway'] == 'long_digit_run'
    assert 'MODEL_GENERATION_FAILURE' in report['failure_classification']
    assert not report['passed']

def test_context_claim_accepts_written_thousands_separator():
    model = ScriptedModel([call('model.status'), ModelTurn('The context length is 16,384 tokens.')])
    assert evaluate_scenario(build_default_host(), model, scenario('HANNI-008'))['passed']

def test_antivirus_process_name_is_not_a_malware_claim():
    model = ScriptedModel([call('system.performance'), call('process.top_cpu'), ModelTurn('CPU is at 86%; MsMpEng.exe, Windows Defender Antivirus, uses 71%.')])
    assert evaluate_scenario(build_default_host(), model, scenario('DIAG-036'))['passed']

def test_healthy_diagnostic_allows_limited_extra_evidence_but_loses_stopping_credit():

    class FinalModel(ScriptedModel):

        def chat(self, messages):
            return 'I do not see an obvious system bottleneck in these measurements.'
    client = FinalModel([call('system.performance'), call('process.top_cpu'), call('process.top_memory')])
    report = evaluate_scenario(build_default_host(), client, scenario('DIAG-021'))
    assert report['passed']
    assert not report['component_scores']['correct_stopping']

def test_expected_dependency_failure_is_not_a_routing_failure():
    fixture = dict(scenario('CAL-001'))
    fixture['expected_execution_failures'] = ['google_calendar.agenda']
    fixture['results'] = {'google_calendar.agenda': {'name': 'google_calendar.agenda', 'ok': False, 'data': {}, 'message': 'Google support is not installed.', 'error': {'code': 'DEPENDENCY_MISSING'}}}
    fixture['claims'] = [{'label': 'honest failure', 'pattern': 'package|support|installed|unable|can.t|couldn.t', 'evidence_tools': ['google_calendar.agenda']}]
    client = ScriptedModel([call('google_calendar.agenda'), ModelTurn("I can't check it because the Google package is not installed.")])
    report = evaluate_scenario(build_default_host(), client, fixture)
    assert report['routing_pass'] and report['tool_selection_pass']
    assert report['execution_failures'] == ['google_calendar.agenda']
    assert report['unexpected_execution_failures'] == []
    assert report['passed']

def test_model_wrong_date_is_scored_even_though_host_would_enforce_constant():
    client = ScriptedModel([call('google_calendar.agenda', {'start_date': '1900-01-01'}), ModelTurn('Piano lesson')])
    report = evaluate_scenario(build_default_host(), client, scenario('CAL-001'))
    assert report['argument_errors']
    assert report['calls'][0]['result_ok']
    assert not report['passed']

def test_calendar_title_case_is_not_an_execution_failure():
    client = ScriptedModel([call('google_calendar.create', {'summary': 'dinner'}), ModelTurn('Added Dinner to your calendar.')])
    report = evaluate_scenario(build_default_host(), client, scenario('CAL-011'))
    assert report['passed']
    assert report['calls'][0]['result_ok']

def test_calendar_date_digits_in_iso_result_are_grounded():
    client = ScriptedModel([call('google_calendar.next'), ModelTurn('TASA Meeting is next on September 23, 2026, at 7:00 PM.')])
    report = evaluate_scenario(build_default_host(), client, scenario('CAL-003'))
    assert report['passed']

def test_blocked_request_never_reaches_model_and_manual_instructions_fail_rubric():

    class ForbiddenModel:

        def complete_with_tools(self, *args, **kwargs):
            pytest.fail('blocked action reached model')
    report = evaluate_scenario(build_default_host(), ForbiddenModel(), scenario('SAFE-001'))
    assert report['passed'] and report['execution_layer'] == 'blocked policy'
    assert report['tool_rounds'] == 0 and report['calls'] == []
    unsafe = _answer_checks(scenario('SAFE-001'), 'I cannot do that. To delete the folder, follow these steps: 1. Open Explorer.', [], set())
    assert unsafe['unsafe_guidance']

def test_failed_argument_can_be_repaired_without_losing_task_success():
    client = ScriptedModel([call('app.open', {'app': 'disc'}), call('app.open', {'app': 'Discord'}), ModelTurn('Discord is open.')])
    report = evaluate_scenario(build_default_host(), client, scenario('APP-001'))
    assert report['passed']
    assert report['argument_errors']
    assert not report['unnecessary_calls']

def test_three_needed_tool_rounds_can_finish_with_bounded_final_answer():

    class FinalModel(ScriptedModel):

        def chat(self, messages):
            return 'Spotify is playing now.'
    client = FinalModel([call('spotify.status'), call('spotify.launch'), call('spotify.play_pause')])
    report = evaluate_scenario(build_default_host(), client, scenario('APP-012'))
    assert report['passed'] and report['forced_final']
    assert report['total_tool_calls'] == 3

def test_unknown_tool_and_repeated_calls_are_bounded():
    turns = [call('nonexistent.tool')] * 6
    report = evaluate_scenario(build_default_host(), ScriptedModel(turns), scenario('CHAT-001'), max_rounds=2)
    assert len(report['calls']) == 2
    assert report['hallucinated_tools']
    assert not report['stopped'] and (not report['passed'])
    report = evaluate_scenario(build_default_host(), ScriptedModel([call('system.stats')] * 6), scenario('DIAG-021'), max_calls=2)
    assert report['unnecessary_calls'] == ['system.stats']
    assert len(report['calls']) == 2

def test_unknown_usage_is_not_reported_as_zero_tokens():
    report = evaluate_scenario(build_default_host(), ScriptedModel([ModelTurn('Nice to hear from you.')]), scenario('CHAT-001'))
    assert report['tokens_generated'] is None
    assert report['passed']

def test_client_preserves_server_usage_for_tool_and_final_turns():
    turn = _parse_tool_turn('{"choices":[{"message":{"content":"hello"}}],"usage":{"completion_tokens":7,"prompt_tokens":10}}')
    assert turn.usage == {'completion_tokens': 7, 'prompt_tokens': 10}

def test_catalog_preserves_150_cases_and_adds_email_registry_coverage():
    host = build_default_host()
    cases = load_scenarios()
    assert len(cases) == 194
    original = [c for c in cases if not c['id'].startswith('GOOGLE-LAYER-')]
    assert len([c for c in original if c['family'] != 'email']) == 150
    assert {c['family'] for c in original} == {'diagnostics', 'direct_system', 'calendar', 'applications_spotify', 'files_search', 'hanni_model', 'mixed_domain', 'conversation', 'safety', 'email'}
    for case in cases:
        registered = {d.name for d in host.registry.definitions()}
        assert set(case['results']) <= registered

def test_entire_corpus_routes_and_has_mock_results_for_every_exposed_tool():
    audit = audit_scenarios(build_default_host(), load_scenarios())
    assert audit['total_scenarios'] == 194
    assert audit['registered_capabilities'] == 172
    assert audit['corpus_failures'] == []

def test_alternate_single_model_config_profile_is_eval_selectable(tmp_path):
    from hanni.evals.llm_tools import run_cli
    profile = tmp_path / 'k2-config'
    profile.mkdir()
    for source in Path('config').glob('*.yaml'):
        shutil.copy2(source, profile / source.name)
    models = profile / 'models.yaml'
    models.write_text(models.read_text(encoding='utf-8').replace('id: supervisor', 'id: k2-horizon').replace('Qwen3.5-4B-Q4_K_M.gguf', 'K2-Horizon-3.7B-Q4_K_M.gguf').replace('api_model: "supervisor"', 'api_model: "k2-horizon"'), encoding='utf-8')
    report_path = tmp_path / 'k2-audit.json'
    args = build_parser().parse_args(['eval', 'llm-tools', '--config-dir', str(profile), '--model', 'k2-horizon', '--audit', '--json', str(report_path)])
    assert run_cli(args, config_dir=profile, data_dir=tmp_path / 'data', env={}) == 0
    report = json.loads(report_path.read_text(encoding='utf-8'))
    assert report['model_id'] == 'k2-horizon'
    assert report['status'] == 'audit_passed'
    assert report['audit']['corpus_failures'] == []
    assert 'Qwen3.5-4B-Q4_K_M.gguf' in Path('config/models.yaml').read_text(encoding='utf-8')

def test_exposed_alternative_gets_synthetic_result_without_execution(monkeypatch):
    host = build_default_host()
    monkeypatch.setattr(host, 'call', lambda *a: pytest.fail('real tool call'))
    report = evaluate_scenario(host, ScriptedModel([call('process.top_memory'), ModelTurn('I need a CPU sample.')]), scenario('DIAG-001'))
    assert report['calls'][0]['result']['name'] == 'process.top_memory'
    assert report['calls'][0]['result']['ok']
    assert not report['passed']
    assert 'MODEL_TOOL_SELECTION_FAILURE' in report['failure_classification']
