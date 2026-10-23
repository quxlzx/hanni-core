"""Native Mini completion requires actual full text and the idle original state."""
import sqlite3
import pytest
from scripts.campaign8_native import mini_streaming

def test_actual_completed_mini_text_is_eligible():
    message = {'role': 'assistant', 'status': 'complete', 'content': 'Actual complete response.'}
    native = {'message_exists': True, 'rendered_content': message['content'], 'message_status': '', 'mini_state': 'Ready'}
    assert mini_streaming.mini_completion_matches(native, message)

@pytest.mark.parametrize('field,value', [('rendered_content', 'Actual complete'), ('rendered_content', 'Another answer.'), ('mini_state', 'Working'), ('mini_state', 'Assistant offline'), ('message_exists', False), ('message_status', 'working')])
def test_partial_busy_or_missing_mini_render_is_not_certified(field, value):
    message = {'role': 'assistant', 'status': 'complete', 'content': 'Actual complete response.'}
    native = {'message_exists': True, 'rendered_content': message['content'], 'message_status': '', 'mini_state': 'Ready', field: value}
    assert not mini_streaming.mini_completion_matches(native, message)

def test_incomplete_original_message_is_never_certified():
    assert not mini_streaming.mini_completion_matches({'message_exists': True, 'rendered_content': 'partial', 'message_status': '', 'mini_state': 'Ready'}, {'role': 'assistant', 'status': 'working', 'content': 'partial'})

def test_sqlite_evidence_reads_only_existing_owned_database(tmp_path, monkeypatch):
    monkeypatch.setattr(mini_streaming, 'ROOT', tmp_path)
    root = tmp_path / 'data/campaign8-ui/owned'
    root.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        mini_streaming.owned_chat_rows(root)
    assert not (root / 'campaign-chat.sqlite3').exists()
    with sqlite3.connect(root / 'campaign-chat.sqlite3') as db:
        db.execute('CREATE TABLE messages(id,turn,role,content,channel,status,created)')
        db.execute("INSERT INTO messages VALUES(1,'owned','assistant','actual','browser','complete',1)")
    assert mini_streaming.owned_chat_rows(root)[0]['content'] == 'actual'
    with pytest.raises(ValueError, match='disposable campaign backend'):
        mini_streaming.owned_chat_rows(tmp_path / 'owner')
