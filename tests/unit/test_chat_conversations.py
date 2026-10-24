"""Tabs must preserve separate histories and send only their own model context."""
import http.client
import json
import sqlite3
import threading
import uuid

from hanni.dashboard.chat import ChatHub
from hanni.dashboard.native_chat import NativeChat
from tests.unit.test_dashboard_chat import chat_server, send


def get(server, path):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_conversations_api_keeps_tabs_separate_and_creation_idempotent(chat_server):
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    for key in (first, first, second):
        assert send(chat_server, path='/api/chat/conversations', body={'id': key}) == (201, {'id': key})
    turn = str(uuid.uuid4())
    body = {'id': turn, 'message': 'Only in the first tab', 'conversation': first}
    assert send(chat_server, body=body)[0] == 202
    assert send(chat_server, body=body)[0] == 202
    assert send(chat_server, body={**body, 'conversation': second})[0] == 400
    assert len(chat_server.chat.queue) == 1
    assert get(chat_server, '/api/chat?conversation=' + second)[1]['messages'] == []
    snapshot = get(chat_server, '/api/chat?conversation=' + first)[1]
    assert snapshot['conversation_id'] == first
    assert snapshot['messages'][0]['content'] == body['message']
    conversations = get(chat_server, '/api/chat/conversations')[1]['conversations']
    assert len(conversations) == 3
    assert next(c for c in conversations if c['id'] == first)['title'] == body['message']
    assert get(chat_server, '/api/chat?conversation=missing')[0] == 400
    assert send(chat_server, body={**body, 'conversation': []})[0] == 400
    assert send(chat_server, path='/api/chat/conversations', body={'id': 'invalid'})[0] == 400


def test_new_conversation_creation_uses_existing_write_protection(chat_server):
    key = str(uuid.uuid4())
    assert send(chat_server, path='/api/chat/conversations', body={'id': key}, headers={'X-Hanni-Token': 'wrong'})[0] == 403
    assert all(c['id'] != key for c in chat_server.chat.conversations())


def test_old_history_migrates_without_erasing_messages_and_survives_reopen(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, turn TEXT, role TEXT, content TEXT, channel TEXT, status TEXT, created REAL)')
        db.execute("INSERT INTO messages VALUES (1,'old','user','Existing conversation','browser','complete',1)")
    hub = ChatHub(path)
    try:
        assert hub.snapshot(conversation='default')['messages'][0]['content'] == 'Existing conversation'
        assert hub.conversations()[0]['title'] == 'Existing conversation'
        conversation = hub.create_conversation(str(uuid.uuid4()))
        hub.ready = True
        hub.submit(str(uuid.uuid4()), 'A different conversation', conversation)
        assert hub.take() == 'A different conversation'
        row = hub.begin('A different conversation', 'browser')
        hub.update(row, 'A separate answer', 'complete')
        hub.close()
        hub.db.close()
        hub = ChatHub(path)
        assert [m['content'] for m in hub.snapshot(conversation=conversation)['messages']] == ['A different conversation', 'A separate answer']
        assert len(hub.snapshot(conversation='default')['messages']) == 1
    finally:
        hub.close()
        hub.db.close()


def test_native_chat_never_injects_another_tabs_history():
    hub = ChatHub()
    hub.ready = True
    first, second = (hub.create_conversation(str(uuid.uuid4())) for _ in range(2))
    def complete(conversation, prompt, reply):
        hub.submit(str(uuid.uuid4()), prompt, conversation)
        assert hub.take() == prompt
        hub.note(prompt, reply)
    try:
        complete(first, 'My private code is FIRST', 'FIRST saved')
        complete(second, 'My code is SECOND', 'SECOND saved')
        hub.submit(str(uuid.uuid4()), 'What code did I give you?', second)
        prompt = hub.take()
        submitted = []
        def proxy(method, path, body=None):
            if method == 'POST':
                submitted.append(body)
                return {'id': 'task-2'}
            return {'id': 'task-2', 'state': 'review_required', 'result': {'model_claims': 'SECOND'}}
        NativeChat(hub, threading.Event(), proxy=proxy).respond(prompt)
        history = submitted[0]['task']['context']['conversation']
        assert history == [{'role': 'user', 'text': 'My code is SECOND'}, {'role': 'assistant', 'text': 'SECOND saved'}]
        assert hub.snapshot(conversation=second)['messages'][-1]['task_id'] == 'task-2'
        assert 'FIRST' not in json.dumps(submitted)
    finally:
        hub.close()
        hub.db.close()


def test_history_pagination_and_clear_do_not_mix_conversations():
    hub = ChatHub()
    try:
        hub.ready = True
        conversation = hub.create_conversation(str(uuid.uuid4()))
        for index in range(55):
            hub.submit(str(uuid.uuid4()), str(index), conversation)
            hub.take()
            hub.note(str(index), 'reply')
        hub.note('Another tab', 'Another reply')
        recent = hub.snapshot(conversation=conversation)
        assert len(recent['messages']) == 100 and recent['has_more']
        older = hub.snapshot(recent['messages'][0]['id'], conversation=conversation)
        assert len(older['messages']) == 10 and not older['has_more']
        assert all(m['conversation'] == conversation for m in older['messages'])
        hub.clear()
        assert not hub.snapshot(conversation=conversation)['messages']
        assert all(c['title'] == 'New chat' for c in hub.conversations())
    finally:
        hub.close()
        hub.db.close()
