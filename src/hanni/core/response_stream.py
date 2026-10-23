"""Final-answer sentence boundaries and cooperative turn cancellation.

This layer never handles tool arguments or grants authority. Callers supply only
final answer content. Text inside thinking tags is withheld, including split tags.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import re

_cancel = ContextVar('hanni_response_cancel', default=None)


class TurnCancelled(RuntimeError):
    pass


class FinalSentence(str):
    """A final-answer sentence; never a model tool-selection fragment."""


def check_cancelled():
    event = _cancel.get()
    if event is not None and event.is_set():
        raise TurnCancelled('This response was cancelled.')


def cancellation_guard():
    return check_cancelled if _cancel.get() is not None else None


def current_cancellation_event():
    """Bind asynchronous task cancellation to this original response turn."""
    return _cancel.get()


@contextmanager
def cancellation_scope(event):
    token = _cancel.set(event)
    try:
        yield
    finally:
        _cancel.reset(token)


class SentenceBuffer:
    def __init__(self, max_chars=8192):
        self.buffer = ''
        self.hidden = False
        self.max_chars = max_chars

    def feed(self, chunk, *, final=False):
        self.buffer += str(chunk)
        if len(self.buffer) > self.max_chars:
            raise ValueError('Final-answer sentence exceeded the bounded speech buffer.')
        output = []
        while self.buffer:
            if self.hidden:
                close = self.buffer.find('</think>')
                if close < 0:
                    self.buffer = self.buffer[-8:]
                    break
                self.buffer = self.buffer[close + 8:]
                self.hidden = False
                continue
            opening = self.buffer.find('<think>')
            boundary = self._boundary(final)
            if opening >= 0 and (boundary is None or opening < boundary):
                before = self.buffer[:opening].strip()
                if before:
                    # A preceding fragment cannot become a speech success claim.
                    output.extend(SentenceBuffer().feed(before, final=True))
                self.buffer = self.buffer[opening + 7:]
                self.hidden = True
                continue
            if boundary is not None:
                value = self.buffer[:boundary].strip()
                self.buffer = self.buffer[boundary:].lstrip()
                if value:
                    output.append(value)
                continue
            if final:
                value = self.buffer.strip()
                self.buffer = ''
                # A partial tag or unmatched reasoning span never escapes.
                if value and '<' not in value:
                    output.append(value)
            break
        return output

    def _boundary(self, final):
        for match in re.finditer(r'[.!?](?:["\')\]]*)', self.buffer):
            i, end = match.start(), match.end()
            if self.buffer[i] == '.':
                if i and i + 1 < len(self.buffer) and self.buffer[i - 1].isdigit() and self.buffer[i + 1].isdigit():
                    continue
                word = self.buffer[:i].rsplit(None, 1)[-1].casefold() if self.buffer[:i].strip() else ''
                if word in {'mr', 'mrs', 'ms', 'dr', 'prof', 'vs', 'etc', 'e.g', 'i.e'} or len(word) == 1:
                    continue
                if re.search(r'\b[A-Za-z]:[\\/][^\s]*$', self.buffer[:i]):
                    continue
            # Require lookahead so decimal points, filenames and split endings
            # are not spoken prematurely. At EOF a complete sentence is usable.
            if end < len(self.buffer) and self.buffer[end].isspace() or final and end == len(self.buffer):
                return end
        return None


def final_sentences(chunks, *, validator=None):
    buffer = SentenceBuffer()
    source = iter(chunks)
    first = True
    try:
        for chunk in source:
            check_cancelled()
            for sentence in buffer.feed(chunk):
                check_cancelled()
                yield FinalSentence(('' if first else ' ') + (validator(sentence) if validator else sentence))
                first = False
        for sentence in buffer.feed('', final=True):
            check_cancelled()
            yield FinalSentence(('' if first else ' ') + (validator(sentence) if validator else sentence))
            first = False
    finally:
        close = getattr(source, 'close', None)
        if callable(close):
            close()


def guard_knowledge_sentence(sentence):
    # Conversational generation has no action receipts. This checks self-claims,
    # not factual descriptions of historical actions or quoted owner text.
    if re.search(r"\bI(?:'ve| have)?\s+(?:successfully\s+)?(?:opened|launched|deleted|installed|"
                 r'restarted|created|sent|changed|moved|killed|scheduled|saved)\b', sentence, re.I):
        return "I haven't verified an action for that request."
    return sentence
