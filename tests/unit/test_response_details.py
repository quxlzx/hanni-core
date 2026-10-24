"""Returned model reasoning and measured stats survive the native task flow."""
import json
import itertools
from unittest.mock import patch

from hanni.hermes.state import TaskStore
from hanni.native import worker
from hanni.native.loop import returned_reasoning, run_loop
from tests.test_native_loop import FakeClient, spec


def run(replies, **kwargs):
    return run_loop(FakeClient(replies), system_prompt='s', user_message='u',
                    tool_specs=[spec('lookup')], execute=lambda *args: {'ok': True},
                    context_budget_tokens=None, **kwargs)


def test_reasoning_is_separate_and_statistics_use_server_measurements():
    progress = []
    result = run([{'message': {'content': 'Visible answer', 'reasoning_content': 'Model notes'},
                   'usage': {'prompt_tokens': 40, 'completion_tokens': 20},
                   'timings': {'predicted_n': 20, 'predicted_ms': 500}}], on_progress=progress.append)
    assert result['claims'] == 'Visible answer'
    assert result['reasoning'] == [{'step': 1, 'text': 'Model notes', 'truncated': False}]
    assert result['stats']['tokens_per_second'] == 40
    assert result['stats']['rate_source'] == 'generation'
    assert result['stats']['completion_tokens'] == 20
    assert result['stats']['prompt_tokens'] == 40
    assert progress[0]['activity']['phase'] == 'thinking'
    assert progress[-1]['reasoning'] == result['reasoning']


def test_no_reasoning_or_usage_is_not_invented():
    result = run([{'message': {'content': 'Ordinary answer'}}])
    assert result['reasoning'] == []
    assert result['stats']['completion_tokens'] is None
    assert result['stats']['prompt_tokens'] is None
    assert result['stats']['tokens_per_second'] is None
    assert result['stats']['elapsed_seconds'] >= 0


def test_tagged_reasoning_is_collected_once_and_never_in_final_answer():
    assert returned_reasoning({'reasoning_content': 'Notes', 'reasoning': 'Notes',
                               'content': '<think>Notes</think>Answer'}) == 'Notes'
    assert returned_reasoning({'content': 'Answer<think>Incomplete notes'}) == 'Incomplete notes'
    result = run([{'message': {'content': '<think>Notes</think>Answer'}}])
    assert result['claims'] == 'Answer'
    assert result['reasoning'][0]['text'] == 'Notes'


@patch('hanni.native.loop.time.monotonic', side_effect=itertools.count(1, .01))
def test_tool_rounds_aggregate_usage_and_keep_progress_snapshots_independent(_clock):
    progress = []
    result = run([
        {'message': {'reasoning_content': 'First notes', 'tool_calls': [
            {'id': 'c1', 'function': {'name': 'lookup', 'arguments': '{}'}}]},
         'usage': {'prompt_tokens': 40, 'completion_tokens': 10}},
        {'message': {'content': 'Done', 'reasoning_content': 'Second notes'},
         'usage': {'prompt_tokens': 60, 'completion_tokens': 20}},
    ], on_progress=progress.append)
    records = [item for item in progress if item['reasoning']]
    assert len(records[0]['reasoning']) == 1
    assert len(records[-1]['reasoning']) == 2
    assert result['stats']['completion_tokens'] == 30
    assert result['stats']['prompt_tokens'] == 100
    assert result['stats']['model_requests'] == 2
    assert result['stats']['rate_source'] == 'request'
    assert result['stats']['last_prompt_tokens'] == 60
    assert result['stats']['last_completion_tokens'] == 20


def test_saved_reasoning_is_redacted_and_bounded_in_serialized_size():
    result = run([{'message': {'content': 'Answer', 'reasoning_content': 'api_key=secret-value ' + '\u4e2d' * 30000}}])
    assert 'secret-value' not in json.dumps(result['reasoning'])
    assert result['reasoning'][0]['truncated']
    assert len(json.dumps(result['reasoning'])) < 14500


def test_forced_final_reply_records_its_reasoning_and_usage():
    result = run([{'message': {'content': 'Final', 'reasoning': 'Final notes'},
                   'usage': {'completion_tokens': 2}}], max_iterations=0)
    assert result['interrupted']
    assert result['reasoning'][0]['text'] == 'Final notes'
    assert result['stats']['completion_tokens'] == 2


def test_malformed_optional_metrics_do_not_break_the_answer():
    result = run([{'message': {'content': 'Answer'}, 'usage': ['invalid'],
                   'timings': {'predicted_ms': float('nan'), 'predicted_n': 10}}])
    assert result['claims'] == 'Answer'
    assert result['stats']['tokens_per_second'] is None


def test_worker_persists_details_in_final_task_result(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('details-test', {'prompt': 'Answer', 'windows_tools': [], 'origin': 'hanni', 'context': {}})
    fake = FakeClient([{'message': {'content': 'Answer', 'reasoning_content': 'Returned notes'},
                        'usage': {'completion_tokens': 9}}])
    fake.max_tokens = 1200
    try:
        with patch.object(worker, 'NativeClient', return_value=fake), \
                patch.object(worker, 'load_model', return_value={'context_length': 65536}), \
                patch('hanni.native.mcp_client.discover', return_value=[]):
            worker.run(store.path, task['id'], {'entries': []})
        result = store.get(task['id'])
        assert result['state'] == 'review_required', result
        assert result['result']['model_claims'] == 'Answer'
        assert result['result']['reasoning'][0]['text'] == 'Returned notes'
        assert result['result']['stats']['completion_tokens'] == 9
    finally:
        store.close()
