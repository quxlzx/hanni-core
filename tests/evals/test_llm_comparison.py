import json
from hanni.cli import run
from hanni.evals.comparison import compare_reports, render_comparison

def report(model, success):
    return {'status': 'completed', 'model_id': model, 'quantization': 'Q4_K_M', 'corpus_sha256': 'corpus', 'routed_menus_sha256': 'menus', 'prompt_sha256': 'prompt', 'evaluator_sha256': 'rubric', 'owner_timezone': 'America/Chicago', 'max_tool_rounds': 3, 'max_tool_calls_per_case': 8, 'context_length': 16384, 'max_tokens': 768, 'tool_temperature': 0, 'final_temperature': 0.35, 'top_p': 0.9, 'total_scenarios': 150, 'results': [{'id': f'CASE-{i:03d}'} for i in range(150)], 'summary': {'task_success_rate': success, 'families': {'diagnostics': {'task_success_rate': success}}}}

def test_same_protocol_reports_can_be_compared():
    comparison = compare_reports(report('Qwen', 82.0), report('K2', 86.0))
    output = render_comparison(comparison)
    assert 'Qwen' in output and 'K2' in output
    assert '82.00%' in output and '86.00%' in output
    assert 'Physical hardware and VRAM usage are not verified' in output

def test_mismatched_or_incomplete_runs_are_rejected():
    from pytest import raises
    first, second = (report('Qwen', 82.0), report('K2', 86.0))
    second['owner_timezone'] = 'UTC'
    with raises(ValueError, match='owner_timezone'):
        compare_reports(first, second)
    second['owner_timezone'] = 'America/Chicago'
    second['total_scenarios'] = 149
    with raises(ValueError, match='same positive scenario count'):
        compare_reports(first, second)
    second['total_scenarios'] = 150
    second['results'] = second['results'][:-1]
    with raises(ValueError, match='same unique'):
        compare_reports(first, second)
    second['results'] = first['results']
    second['status'] = 'model_unavailable'
    with raises(ValueError, match='completed live-model'):
        compare_reports(first, second)

def test_locked_holdout_reports_can_be_compared():
    first, second = (report('Qwen', 80.0), report('K2', 84.0))
    for item in (first, second):
        item['total_scenarios'] = 50
        item['results'] = item['results'][:50]
        item['corpus_sha256'] = 'locked-holdout'
    assert '50 cases' in render_comparison(compare_reports(first, second))

def test_compare_command_runs_without_loading_runtime_configuration(tmp_path, capsys):
    first, second = (tmp_path / 'qwen.json', tmp_path / 'k2.json')
    first.write_text(json.dumps(report('Qwen', 82.0)), encoding='utf-8')
    second.write_text(json.dumps(report('K2', 86.0)), encoding='utf-8')
    assert run(['eval', 'compare', str(first), str(second)]) == 0
    assert '82.00%' in capsys.readouterr().out
