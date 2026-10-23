"""Backend completion must not certify a partial or busy native render."""
import pytest
from scripts.campaign8_native.streaming import native_completion_matches

def original_readbacks():
    message = {'id': 2, 'content': 'The complete measured backend answer.'}
    native = {'message_exists': True, 'rendered_content': message['content'], 'aria_busy': 'false', 'chat_state': 'Ready when you are', 'voice_state': 'Standby'}
    return (native, message)

def test_exact_completed_native_reply_and_idle_state_are_required():
    native, message = original_readbacks()
    assert native_completion_matches(native, message)

@pytest.mark.parametrize('field,value', [('rendered_content', 'The complete measured'), ('rendered_content', 'An unrelated answer.'), ('aria_busy', 'true'), ('chat_state', 'HANNI is responding'), ('voice_state', 'Processing'), ('message_exists', False), ('voice_state', None)])
def test_api_complete_with_lagged_or_unavailable_native_state_is_not_certified(field, value):
    native, message = original_readbacks()
    native[field] = value
    assert not native_completion_matches(native, message)
