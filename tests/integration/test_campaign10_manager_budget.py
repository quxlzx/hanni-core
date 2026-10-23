"""Campaign admission controls only; controlled transport is never model evidence."""
from io import BytesIO
import json
from urllib.request import Request, build_opener
from unittest.mock import patch
import pytest
from scripts.campaign10_manager.model import ModelBudget, AdmissionError

def payload(**changes):
    value = {'messages': [{'role': 'user', 'content': 'Owned synthetic task'}], 'max_tokens': 256, 'temperature': 0}
    value.update(changes)
    return value

def request(body=None, url='http://127.0.0.1:8080/v1/chat/completions'):
    return Request(url, data=json.dumps(body or payload()).encode(), method='POST')

@pytest.mark.parametrize('fault', ['none', 'foreign', 'unassigned', 'wrong_prompt', 'oversized', 'boolean_tokens', 'fourth_call', 'global_exhausted'])
def test_guard_before_original_transport(tmp_path, fault):
    budget = ModelBudget(tmp_path / 'receipts')
    budget.ledger = tmp_path / 'ledger.json'
    budget.begin('synthetic-development', ['Owned synthetic task'])
    if fault == 'unassigned':
        budget.task_id = None
    if fault == 'fourth_call':
        budget.task_posts = 3
    if fault == 'global_exhausted':
        budget.ledger.write_text('{"admitted":450,"maximum":450}', encoding='utf8')
    body = payload()
    if fault == 'wrong_prompt':
        body['messages'][0]['content'] = 'An unassigned request'
    if fault == 'oversized':
        body['max_tokens'] = 257
    if fault == 'boolean_tokens':
        body['max_tokens'] = True
    url = 'http://127.0.0.1:9999/v1/chat/completions' if fault == 'foreign' else 'http://127.0.0.1:8080/v1/chat/completions'
    entered = []

    def original_open(*args, **kwargs):
        entered.append(True)
        response = BytesIO(b'{"choices":[]}')
        response.status = 200
        return response
    with patch('scripts.campaign10_manager.model.original_model_admission', return_value={'process': {'pid': 123}}), patch('urllib.request.OpenerDirector.open', original_open):
        with budget.transport():
            if fault == 'none':
                with build_opener().open(request(body, url)) as response:
                    assert response.read() == b'{"choices":[]}'
            else:
                with pytest.raises(AdmissionError):
                    build_opener().open(request(body, url))
    assert len(entered) == (1 if fault == 'none' else 0)
    assert len(budget.wire) == (1 if fault == 'none' else 0)
    if fault == 'none':
        assert json.loads(budget.ledger.read_text(encoding='utf8'))['admitted'] == 1
