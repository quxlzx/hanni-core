"""Real extraction, storage, HTTP authorization and native context delivery."""
import base64
from io import BytesIO
import http.client
import json
import sqlite3
import threading
from uuid import uuid4
from zipfile import ZipFile

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from hanni.dashboard.attachments import MAX_FILE_BYTES, extract_text
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.native_chat import NativeChat
from tests.unit.test_dashboard_chat import chat_server, send


def upload(hub, text='Quarterly revenue: 42', *, conversation='default', name='report.txt', key=None):
    return hub.files.add(key or str(uuid4()), conversation, name, base64.b64encode(text.encode()).decode())


def pdf_bytes(text='Fixture revenue 42'):
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(f'BT /F1 12 Tf 20 200 Td ({text}) Tj ET'.encode())
    page[NameObject('/Contents')] = writer._add_object(stream)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def test_pdf_and_word_use_actual_extractors():
    text, media, truncated = extract_text('report.PDF', pdf_bytes())
    assert 'Fixture revenue 42' in text and '[Page 1]' in text and media == 'application/pdf' and not truncated
    result = BytesIO()
    with ZipFile(result, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Report Ω</w:t><w:tab/><w:t>42</w:t></w:r></w:p><w:p><w:r><w:t>Next paragraph</w:t></w:r></w:p></w:body></w:document>')
    assert extract_text('report.docx', result.getvalue())[0] == 'Report Ω\t42\nNext paragraph'


@pytest.mark.parametrize('name,data,error', [
    ('program.exe', b'code', 'Unsupported'), ('image.png', b'fake image', 'Unsupported'),
    ('file.txt', b'\x00binary', 'binary'), ('empty.csv', b' \n', 'no readable'),
    ('report.pdf', b'not pdf', 'PDF'), ('report.docx', b'not zip', 'Word'),
    ('report.txt', b'\xffinvalid', 'UTF-8'),
])
def test_unsupported_or_malformed_files_are_honest_errors(name, data, error):
    with pytest.raises(ValueError, match=error):
        extract_text(name, data)


def test_scanned_and_encrypted_pdfs_do_not_pretend_to_have_text():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match='OCR'):
        extract_text('scan.pdf', output.getvalue())
    writer.encrypt('fixture-password')
    output = BytesIO(); writer.write(output)
    with pytest.raises(ValueError, match='Unlock'):
        extract_text('locked.pdf', output.getvalue())


@pytest.mark.parametrize('name', ['../report.txt', 'folder\\report.txt', 'bad\x00.txt', 'x' * 201 + '.txt'])
def test_filenames_cannot_create_paths_or_response_headers(name):
    hub = ChatHub()
    try:
        with pytest.raises(ValueError, match='filename'):
            upload(hub, name=name)
        assert hub.db.execute('SELECT count(*) FROM chat_files').fetchone()[0] == 0
    finally:
        hub.close(); hub.db.close()


def test_storage_is_owned_persistent_and_exactly_idempotent(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    hub = ChatHub(path)
    hub.ready = True
    conversation = hub.create_conversation(str(uuid4()))
    file = upload(hub, conversation=conversation, name='Revenue Ω.txt')
    assert hub.snapshot(conversation=conversation)['pending_attachments'][0]['id'] == file['id']
    assert hub.snapshot(conversation='default')['pending_attachments'] == []
    assert upload(hub, conversation=conversation, name=file['name'], key=file['id']) == file
    with pytest.raises(ValueError, match='different content'):
        upload(hub, 'changed', conversation=conversation, name=file['name'], key=file['id'])
    turn = str(uuid4())
    hub.submit(turn, '', conversation, [file['id']])
    assert hub.snapshot(conversation=conversation)['pending_attachments'] == []
    hub.submit(turn, '', conversation, [file['id']])
    assert len(hub.queue) == 1
    assert hub.snapshot(conversation=conversation)['messages'][0]['attachments'][0]['id'] == file['id']
    with pytest.raises(ValueError):
        hub.files.read(file['id'], 'default')
    with pytest.raises(ValueError):
        hub.submit(str(uuid4()), 'Use another conversation file', 'default', [file['id']])
    with pytest.raises(ValueError, match='different message'):
        hub.submit(turn, 'changed question', conversation, [file['id']])
    hub.close(); hub.db.close()
    hub = ChatHub(path)
    try:
        assert hub.files.read(file['id'], conversation)[1] == b'Quarterly revenue: 42'
        assert not hub.queue
        assert hub.snapshot(conversation=conversation)['messages'][0]['attachments'][0]['name'] == 'Revenue Ω.txt'
        assert hub.snapshot(conversation='default')['messages'] == []
    finally:
        hub.close(); hub.db.close()


def test_retry_retains_files_and_undo_and_clear_remove_their_bytes():
    hub = ChatHub(); hub.ready = True
    try:
        file = upload(hub)
        hub.submit(str(uuid4()), 'Summarize', attachments=[file['id']])
        prompt = hub.take(); row = hub.begin(prompt, 'browser'); hub.update(row, '42', 'complete')
        second = str(uuid4()); hub.retry('default', second)
        assert hub.files.for_turn(second)[0]['id'] == file['id']
        assert hub.native_context('default', exclude_turn=second)['regenerate_only']
        prompt = hub.take(); row = hub.begin(prompt, 'browser'); hub.update(row, '42 again', 'complete')
        hub.undo('default')
        assert hub.db.execute('SELECT count(*) FROM chat_files').fetchone()[0] == 0
        file = upload(hub)
        hub.clear()
        with pytest.raises(ValueError, match='not found'):
            hub.files.read(file['id'], 'default')
    finally:
        hub.close(); hub.db.close()


def test_limits_fail_before_chat_changes_and_removed_uploads_can_be_retried():
    hub = ChatHub(); hub.ready = True
    try:
        files = [upload(hub) for _ in range(5)]
        with pytest.raises(ValueError, match='five'):
            upload(hub)
        with pytest.raises(ValueError, match='once'):
            hub.submit(str(uuid4()), 'duplicate', attachments=[files[0]['id']] * 2)
        for invalid in ['not a list', [None], {'id': files[0]['id']}]:
            with pytest.raises(ValueError):
                hub.submit(str(uuid4()), 'invalid', attachments=invalid)
        assert not hub.queue and not hub.snapshot()['messages']
        hub.files.remove(files[0]['id'], 'default'); hub.files.remove(files[0]['id'], 'default')
        upload(hub)
        with pytest.raises(ValueError, match='8 MiB'):
            hub.files.add(str(uuid4()), 'default', 'big.txt', 'A' * (((MAX_FILE_BYTES + 2) // 3) * 4 + 4))
    finally:
        hub.close(); hub.db.close()


def test_native_submission_carries_only_own_files_and_stays_inside_bridge_limit():
    hub = ChatHub(); hub.ready = True
    try:
        other = hub.create_conversation(str(uuid4()))
        other_file = upload(hub, 'PRIVATE_OTHER_CONVERSATION', conversation=other)
        hub.submit(str(uuid4()), 'Other tab', other, [other_file['id']]); hub.take()
        row = hub.begin('Other tab', 'browser'); hub.update(row, 'Other answer', 'complete')
        files = [upload(hub, '日' * 60000, name=f'report-{i}.txt') for i in range(5)]
        hub.submit(str(uuid4()), '日' * 4000, attachments=[f['id'] for f in files])
        prompt = hub.take(); submitted = []
        def proxy(method, path, body=None):
            if method == 'POST':
                submitted.append(body); return {'id': 'fixture-task'}
            return {'state': 'review_required', 'result': {'model_claims': 'Read the provided file text.'}}
        NativeChat(hub, threading.Event(), proxy=proxy).respond(prompt)
        package = submitted[0]['task']
        assert len(json.dumps(package)) <= 65536
        assert len(package['context']['attached_files_untrusted']) == 5
        assert all(f['excerpted'] and f['text'] for f in package['context']['attached_files_untrusted'])
        assert 'PRIVATE_OTHER_CONVERSATION' not in json.dumps(package)
        assert package['prompt'] == prompt and len(hub.files.read(files[0]['id'], 'default')[1]) == 180000
    finally:
        hub.close(); hub.db.close()


def test_file_api_requires_original_auth_and_download_is_attachment(chat_server):
    chat_server.chat.native_mode = True
    body = dict(operation='add', id=str(uuid4()), conversation='default', name='report Ω.txt', data=base64.b64encode(b'fixture report').decode())
    for headers in [{'X-Hanni-Token': 'wrong'}, {'Origin': 'https://evil.example'}]:
        assert send(chat_server, path='/api/chat/files', body=body, headers=headers)[0] == 403
    status, file = send(chat_server, path='/api/chat/files', body=body)
    assert status == 201
    assert send(chat_server, path='/api/chat/files', body=body) == (201, file)
    conn = http.client.HTTPConnection('127.0.0.1', chat_server.server_port, timeout=3)
    try:
        path = '/api/chat/file?id=' + file['id'] + '&conversation=default'
        conn.request('GET', path); response = conn.getresponse(); response.read()
        assert response.status == 403
        conn.request('GET', path, headers={'X-Hanni-Token': chat_server.chat.token})
        response = conn.getresponse()
        assert response.status == 200 and response.read() == b'fixture report'
        assert response.getheader('Content-Type') == 'application/octet-stream'
        assert response.getheader('Content-Disposition').startswith("attachment; filename*=UTF-8''")
    finally:
        conn.close()
    request = dict(id=str(uuid4()), message='Summarize this', attachments=[file['id']])
    assert send(chat_server, body=request)[0] == 202
    assert chat_server.chat.snapshot()['messages'][0]['attachments'][0]['id'] == file['id']


def test_legacy_chat_does_not_route_document_text_as_commands(chat_server):
    body = dict(operation='add', id=str(uuid4()), conversation='default', name='report.txt', data='eA==')
    assert send(chat_server, path='/api/chat/files', body=body)[0] == 409
    assert not chat_server.chat.db.execute('SELECT 1 FROM chat_files').fetchone()


def test_unsent_files_survive_restart_and_can_be_sent_or_removed(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    hub = ChatHub(path)
    file = upload(hub)
    hub.close(); hub.db.close()
    hub = ChatHub(path)
    try:
        pending = hub.snapshot(conversation='default')['pending_attachments']
        assert pending[0]['id'] == file['id'] and 'text' not in pending[0] and 'data' not in pending[0]
        hub.files.remove(file['id'], 'default')
        assert hub.snapshot(conversation='default')['pending_attachments'] == []
    finally:
        hub.close(); hub.db.close()


def test_failed_file_binding_rolls_back_the_message_and_can_retry():
    hub = ChatHub(); hub.ready = True
    try:
        file = upload(hub)
        turn = str(uuid4())
        hub.db.set_authorizer(lambda action, table, *rest: sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_UPDATE and table == 'chat_files' else sqlite3.SQLITE_OK)
        with pytest.raises(sqlite3.DatabaseError):
            hub.submit(turn, 'Review the document', attachments=[file['id']])
        hub.db.set_authorizer(None)
        assert not hub.queue and not hub.snapshot()['messages']
        assert hub.files.pending('default')[0]['id'] == file['id']
        hub.submit(turn, 'Review the document', attachments=[file['id']])
        assert len(hub.queue) == 1 and hub.files.for_turn(turn)[0]['id'] == file['id']
    finally:
        hub.db.set_authorizer(None)
        hub.close(); hub.db.close()
