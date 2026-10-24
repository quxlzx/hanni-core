import http.client
import json
import uuid
from unittest.mock import patch

import httpx
import pytest

from hanni.native.model_settings import atomic_json
from hanni.native.output_settings import OutputSettings
from hanni.native.provider import NativeClient, load_model
from hanni.native.reasoning_settings import ReasoningSettings, reasoning_identity
from tests.unit.test_dashboard_chat import chat_server, send
from tests.unit.test_output_settings import output

LOCAL = {'ready': True, 'reasoning_levels': [], 'reasoning_budget_supported': True, 'reasoning_disable_supported': True}


def body(control, *, effort=None, budget=None):
    return {'id': str(uuid.uuid4()), 'model_id': control.output_snapshot()['model_id'], 'effort': effort, 'budget': budget}


def test_local_support_separates_effort_from_reasoning_budget(output):
    _, model = output
    original = httpx.Client
    def respond(request):
        return httpx.Response(200, json={'data': [{'id': 'actual-model'}]} if request.url.path == '/v1/models' else
                              {'default_generation_settings': {'n_ctx': 65536}, 'chat_template_caps': {'supports_reasoning_effort': False}})
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        status = NativeClient(model).status()
    assert status['ready'] and not status['reasoning_levels']
    assert status['reasoning_budget_supported'] and status['reasoning_disable_supported']


def test_budget_reaches_requests_while_existing_clients_and_internal_review_are_unchanged(output):
    control, model = output
    old = NativeClient(load_model())
    settings = ReasoningSettings(control.root)
    settings.save(model, body(control, budget=700), LOCAL)
    new = NativeClient(load_model())
    assert old.reasoning_budget is None and new.reasoning_budget == 700
    payloads = []
    original = httpx.Client
    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Synthetic response'}}]})
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        new.chat([{'role': 'user', 'content': 'Hello'}])
    assert payloads[0]['reasoning_budget_tokens'] == 700 and payloads[0]['max_tokens'] == 1200
    internal = NativeClient({**load_model(), 'native_reasoning_budget': 0, 'use_reasoning_preferences': False})
    assert internal.reasoning_budget == 0


def test_off_uncapped_defaults_and_model_scoping(output):
    control, model = output
    model['native_reasoning_budget'] = 512
    settings = ReasoningSettings(control.root)
    settings.save(model, body(control, effort='none'), LOCAL)
    payload = NativeClient(model)._payload([], None)
    assert payload['reasoning_effort'] == 'none'
    assert payload['reasoning_budget_tokens'] == 0
    assert payload['chat_template_kwargs'] == {'enable_thinking': False}
    assert settings.values({**model, 'model_file': 'another.gguf'}) == {'effort': None, 'budget': 512}
    settings.save(model, body(control, budget=-1), LOCAL)
    assert NativeClient(model)._payload([], None)['reasoning_budget_tokens'] == -1
    settings.save(model, body(control), {'ready': False})  # Defaults can restore an offline model.
    assert NativeClient(model).reasoning_budget == 512
    assert not settings.snapshot(model, LOCAL)['customized']


@pytest.mark.parametrize('budget', [-2, 1200, True, False, 1.2, '512', [], {}])
def test_invalid_budgets_are_rejected_without_writes(output, budget):
    control, model = output
    with pytest.raises(ValueError):
        ReasoningSettings(control.root).save(model, body(control, budget=budget), LOCAL)
    assert not (control.root / 'reasoning-settings.json').exists()


def test_rejects_unsupported_effort_budget_stale_model_and_offline_save(output):
    control, model = output
    settings = ReasoningSettings(control.root)
    with pytest.raises(ValueError, match='advertise'):
        settings.save(model, body(control, effort='high'), LOCAL)
    with pytest.raises(ValueError, match='does not expose'):
        settings.save(model, body(control, budget=500), {'ready': True})
    with pytest.raises(ValueError, match='active model changed'):
        settings.save(model, {**body(control, budget=500), 'model_id': 'stale'}, LOCAL)
    with pytest.raises(RuntimeError, match='Connect'):
        settings.save(model, body(control, budget=500), {'ready': False})
    with pytest.raises(ValueError, match='rather than both'):
        settings.save(model, body(control, effort='none', budget=500), LOCAL)
    assert not (control.root / 'reasoning-settings.json').exists()


def test_api_only_sends_advertised_effort_never_llama_budget(output):
    control, model = output
    model = {**model, 'source': 'api'}
    status = {'ready': True, 'reasoning_levels': ['low', 'medium', 'high']}
    settings = ReasoningSettings(control.root)
    settings.save(model, body(control, effort='high'), status)
    payload = NativeClient(model)._payload([], None)
    assert payload['reasoning_effort'] == 'high'
    assert 'reasoning_budget_tokens' not in payload and 'chat_template_kwargs' not in payload
    with pytest.raises(ValueError, match='does not expose'):
        settings.save(model, body(control, effort='high', budget=500), status)


def test_legacy_slash_command_preferences_remain_visible_and_budget_tracks_output(output):
    control, model = output
    atomic_json(control.root / 'reasoning-settings.json', {reasoning_identity(model): {'effort': 'high', 'budget': 1024}})
    settings = ReasoningSettings(control.root)
    assert settings.snapshot(model, LOCAL)['budget'] == 1024
    output_settings = OutputSettings(control.root)
    output_settings.save(model, {'id': str(uuid.uuid4()), 'model_id': control.output_snapshot()['model_id'], 'max_tokens': 512})
    effective = load_model()
    assert settings.snapshot(effective, LOCAL)['budget'] == 511
    assert NativeClient(effective).reasoning_budget == 511
    assert settings.snapshot(model, LOCAL)['budget'] == 1024


def test_endpoint_protects_reads_writes_and_never_interrupts_work(chat_server, output):
    control, model = output
    chat_server.model_settings = control
    values = body(control, budget=500)
    assert send(chat_server, path='/api/model-reasoning', body=values, headers={'X-Hanni-Token': 'wrong'})[0] == 403
    conn = http.client.HTTPConnection('127.0.0.1', chat_server.server_port)
    try:
        conn.request('GET', '/api/model-reasoning')
        assert conn.getresponse().status == 403
    finally:
        conn.close()
    chat_server.chat.submit(str(uuid.uuid4()), 'Current work')
    before = chat_server.chat.snapshot()
    with patch.object(NativeClient, 'status', return_value=LOCAL):
        assert send(chat_server, path='/api/model-reasoning', body=values)[0] == 200
        assert control.change() is None and chat_server.chat.snapshot() == before
        assert send(chat_server, path='/api/model-reasoning', body=body(control, budget=600))[0] == 200
        assert send(chat_server, path='/api/model-reasoning', body=values)[0] == 200
        assert ReasoningSettings(control.root).values(model)['budget'] == 600
        atomic_json(control.root / 'model-change.json', {'status': 'pending'})
        assert send(chat_server, path='/api/model-reasoning', body=body(control, budget=800))[0] == 409
