"""Original isolated pagination seeds and prospectively safe input contract."""
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.seed import populate_dense
from scripts.campaign8_ui.sweep import cases
from scripts.campaign8_ui.plan import validate_input

def test_remaining_controls_are_inputs_only_and_never_start_external_work():
    inputs, oracles = cases()
    assert len(inputs) >= 29
    assert {row['id'] for row in inputs} == {row['id'] for row in oracles}
    for row in inputs:
        validate_input(row)
        assert not set(row) & {'oracle', 'expected', 'checker_inputs'}
        assert not any((step.get('name') in {'Start benchmark', 'Test & Discover', 'Reconnect', 'Confirm server startup'} for step in row['steps']))

def test_dense_records_reach_original_pagination_without_owner_or_model(tmp_path):
    with original_backend(tmp_path / 'owned-original-dense') as backend:
        seeded = populate_dense(backend)
        code, data = backend.request('/api/memory/explorer?limit=30')
        assert code == 200 and data['total_stored'] == 36
        assert len(data['records']) == 30 and data['has_more'] is True
        code, proposals = backend.request('/api/memory/suggestions?limit=20')
        assert code == 200 and proposals['total'] == 26
        assert len(proposals['items']) == 20 and proposals['has_more'] is True
        assert len(seeded['dense_fixture']['original_record_ids']) == 35
        assert seeded['model_requests'] == 0
        assert backend.chat.ready is False
        assert all((call['outcome'] == 'CONTROLLED_UNAVAILABLE' for call in backend.calls))
