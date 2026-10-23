"""Public two-pass planning must re-admit before every model call."""
from pathlib import Path
import json
import threading
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture
from tests.integration.test_workflow_service_verifier import artifact_plan

def test_foreground_arriving_after_outline_blocks_next_binding_inference(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('Original isolated planning evidence.', encoding='utf-8')
    client = QueuedStructuredClient()
    artifact_plan(client, source)
    outline = client._responses.popleft()
    returned, box = (threading.Event(), {})

    def first_response(_messages, _options):
        box['fixture'].interaction.responding(True)
        returned.set()
        return outline
    client._responses.appendleft(first_response)
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        box['fixture'] = fixture
        fixture.observe('file.read', 'file.write')
        try:
            key = fixture.submit('Read the explicitly supplied local text file and preserve its verified contents.')
            assert returned.wait(5)
            import time
            time.sleep(0.2)
            evidence = {'original_interaction_state': fixture.interaction.snapshot(), 'inference_calls_after_foreground': len(client.calls), 'workflow_state': fixture.detail(key)['status'], 'file_read_entries': fixture.ledger.entries('file.read'), 'file_write_entries': fixture.ledger.entries('file.write')}
            (tmp_path / 'm3-between-model-pass-admission-cycle-1.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            assert len(client.calls) == 1, evidence
            assert fixture.ledger.entries('file.read') == fixture.ledger.entries('file.write') == 0
        finally:
            fixture.interaction.responding(False)
