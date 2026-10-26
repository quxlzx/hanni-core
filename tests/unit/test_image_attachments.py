import base64
from io import BytesIO
import json
import threading
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from hanni.dashboard.chat import ChatHub
from hanni.dashboard.native_chat import NativeChat
from hanni.native.compact import compact, ContextOverflow, estimate_tokens
from hanni.native.images import image_info, resolve_image
from hanni.native.provider import NativeClient
from tests.unit.test_dashboard_chat import chat_server, send


def picture(format='PNG', size=(80, 40)):
    stream = BytesIO()
    Image.new('RGB', size, 'red').save(stream, format=format)
    return stream.getvalue()


@pytest.fixture
def images(tmp_path):
    hub = ChatHub(tmp_path / 'dashboard-chat.sqlite3'); hub.ready = True
    raw = picture(size=(2000, 1000))
    file = hub.files.add(str(uuid4()), 'default', 'capture.png', base64.b64encode(raw).decode())
    turn = str(uuid4())
    hub.submit(turn, 'Describe this picture', attachments=[file['id']])
    reference = hub.files.context(turn)[0]['image_reference']
    yield hub, file, turn, reference
    hub.close(); hub.db.close()


@pytest.mark.parametrize('name,format,media', [('a.png', 'PNG', 'image/png'), ('a.jpg', 'JPEG', 'image/jpeg'), ('a.webp', 'WEBP', 'image/webp'), ('a.gif', 'GIF', 'image/gif'), ('a.bmp', 'BMP', 'image/bmp')])
def test_supported_images_are_decoded_and_typed(name, format, media):
    description, actual, truncated = image_info(name, picture(format))
    assert '80 × 40' in description and actual == media and not truncated


@pytest.mark.parametrize('data', [b'not an image', b'<svg xmlns="http://www.w3.org/2000/svg"/>', picture()[:35]])
def test_invalid_images_are_rejected_without_storage(data):
    hub = ChatHub()
    try:
        with pytest.raises(ValueError):
            hub.files.add(str(uuid4()), 'default', 'capture.png', base64.b64encode(data).decode())
        assert hub.db.execute('SELECT count(*) FROM chat_files').fetchone()[0] == 0
    finally:
        hub.close(); hub.db.close()


def test_image_type_and_dimensions_are_validated():
    with pytest.raises(ValueError, match='format'):
        image_info('fake.jpg', picture())
    with pytest.raises(ValueError, match='large'):
        image_info('oversize.png', picture(size=(17000, 1)))


def test_originals_remain_downloadable_but_task_context_contains_only_bound_references(images, tmp_path):
    hub, file, turn, reference = images
    assert file['media_type'] == 'image/png'
    assert hub.files.read(file['id'], 'default')[1] == picture(size=(2000, 1000))
    context = hub.files.context(turn)
    assert len(json.dumps(context)) < 1000 and 'base64' not in json.dumps(context)
    part = resolve_image(tmp_path, reference, turn=turn, conversation='default')
    assert part['type'] == 'image_url'
    with Image.open(BytesIO(base64.b64decode(part['image_url']['url'].partition(',')[2]))) as decoded:
        assert decoded.size == (1536, 768) and decoded.getpixel((0, 0))[0] > 240
    for altered in [{**reference, 'turn': str(uuid4())}, {**reference, 'conversation': 'other'}, {**reference, 'id': '../outside'}, {**reference, 'path': 'secret'}]:
        with pytest.raises(ValueError):
            resolve_image(tmp_path, altered, turn=turn, conversation='default')


def test_provider_expands_images_without_mutating_checkpoint_messages(images, tmp_path):
    _, _, turn, reference = images
    model = {'id': 'vision', 'api_model': 'vision', 'source': 'api', 'endpoint': 'https://fixture.example/v1'}
    client = NativeClient(model)
    client.image_resolver = lambda ref: resolve_image(tmp_path, ref, turn=turn, conversation='default')
    messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'Describe it'}, reference]}]
    before = json.dumps(messages)
    payloads = []
    original = httpx.Client
    def respond(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': 'vision', 'architecture': {'input_modalities': ['text', 'image']}}]})
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Synthetic vision reply.'}}]})
    with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        assert client.chat(messages)['message']['content'] == 'Synthetic vision reply.'
    assert payloads[0]['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert json.dumps(messages) == before and 'base64' not in before
    client._image_support_checked = False
    with patch.object(client, 'status', return_value={'ready': True, 'image_input_supported': False}), pytest.raises(ValueError, match='does not accept'):
        client._payload(messages, None)


def test_images_remain_present_after_compression_and_overflow_is_explicit(images):
    _, _, _, reference = images
    class Summary:
        def chat(self, *args):return {'message': {'content': 'Goal: inspect image; prior progress recorded.'}}
    messages = [{'role': 'system', 'content': 'Instructions'}, {'role': 'user', 'content': [{'type': 'text', 'text': 'x' * 80000}, reference]},
                {'role': 'assistant', 'content': 'Prior observation'}, {'role': 'user', 'content': 'Continue'}]
    folded = compact(messages, Summary(), max_tokens=12000, keep_recent=2, task_anchor='Inspect image')
    assert any(reference in m['content'] for m in folded if isinstance(m.get('content'), list))
    assert estimate_tokens(folded) <= 12000
    with pytest.raises(ContextOverflow):
        compact(messages[:2], Summary(), max_tokens=1000, task_anchor='Inspect image')


def test_text_only_model_keeps_unsent_image_then_vision_model_accepts_it(chat_server):
    hub = chat_server.chat; hub.native_mode = True
    data = {'operation': 'add', 'id': str(uuid4()), 'conversation': 'default', 'name': 'capture.png', 'data': base64.b64encode(picture()).decode()}
    status, file = send(chat_server, path='/api/chat/files', body=data)
    assert status == 201 and file['media_type'] == 'image/png'
    request = {'id': str(uuid4()), 'message': 'Describe', 'conversation': 'default', 'attachments': [file['id']]}
    with patch.object(chat_server.model_settings, 'reasoning_model', return_value={'id': 'fixture', 'source': 'local', 'endpoint': 'http://localhost:8411/v1'}), patch.object(NativeClient, 'status', return_value={'ready': True, 'image_input_supported': False}):
        status, result = send(chat_server, body=request)
        assert status == 400 and 'does not accept images' in result['error']
        assert not hub.queue and hub.files.pending('default')[0]['id'] == file['id']
        with patch.object(NativeClient, 'status', return_value={'ready': True, 'image_input_supported': True}):
            assert send(chat_server, body=request)[0] == 202
        assert send(chat_server, body=request)[0] == 202  # Exact retry is still acknowledged after model availability changes.
        assert len(hub.queue) == 1


def test_native_bridge_package_keeps_refs_instead_of_image_bytes(images):
    hub, _, turn, reference = images
    prompt = hub.take(); submissions = []
    def proxy(method, path, body=None):
        if method == 'POST':submissions.append(body); return {'id': 'fixture'}
        return {'state': 'review_required', 'result': {'model_claims': 'Synthetic image response.'}}
    NativeChat(hub, threading.Event(), proxy=proxy).respond(prompt)
    package = submissions[0]
    assert package['task']['context']['attached_files_untrusted'][0]['image_reference'] == reference
    assert package['key'] == 'chat-' + turn
    assert 'base64' not in json.dumps(package) and len(json.dumps(package)) < 65536


def test_worker_delivers_image_pixels_and_checkpoints_only_references(images, tmp_path, monkeypatch):
    from hanni.native import worker
    from hanni.hermes.state import TaskStore
    hub, _, turn, reference = images
    model = {'id': 'vision', 'source': 'api', 'endpoint': 'https://fixture.example/v1', 'context_length': 65536, 'native_max_tokens': 1200}
    monkeypatch.setattr(worker, 'load_model', lambda: model)
    monkeypatch.setattr(worker, 'discover', lambda *a, **kw: [])
    monkeypatch.setattr('hanni.native.mcp_client.discover', lambda *a: [])
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'skills'))
    payloads = []
    original = httpx.Client
    def respond(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': 'vision', 'architecture': {'input_modalities': ['text', 'image']}}]})
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Synthetic image response.'}, 'finish_reason': 'stop'}]})
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        task = store.submit('chat-' + turn, {'origin': 'hanni', 'prompt': 'Describe image', 'windows_tools': [],
            'context': {'conversation_id': 'default', 'attached_files_untrusted': hub.files.context(turn)}})
        with patch('httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
            worker.run(store.path, task['id'], {'entries': []})
        completed = store.get(task['id'])
        assert completed['state'] == 'review_required', completed
        assert payloads[0]['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
        checkpoint = store.checkpoint(task['id'])
        assert checkpoint['messages'][1]['content'][1] == reference
        assert 'base64' not in json.dumps(checkpoint)
    finally:
        store.close()
