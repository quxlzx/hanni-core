"""Explicit owner-requested delegation; ordinary requests remain in HANNI."""
import time
import re
from uuid import uuid4


OWNER_PREFIX = r'(?:(?:hanni[, :]*)?)(?:(?:please|can you|could you|would you|will you|i want you to)\s+)?(?:please\s+)?'


def explicit_delegation(prompt):
    """Require a direct owner instruction naming Hermes; no semantic auto-router."""
    text = prompt.strip()
    prefix = OWNER_PREFIX
    transfer = r'(?:delegate|deligate|send|give|assign|pass|hand(?:\s+off)?)\b[^\n]{0,2000}?\bto\s+hermes\b'
    addressed = r'(?:ask|have|tell)\s+hermes\s+to\s+\S'
    match = re.match(prefix+'(?:'+transfer+'|'+addressed+')', text, re.I)
    if not match:
        return False
    # A negated transfer is a local instruction, never execution consent.
    return not re.search(r"\b(?:not|never|don't|dont|do not)\b|\bgive\s+(?:me|us)\b", match.group(0), re.I)


class HermesSession:
    def __init__(self, fallback_session, control, registry, client):
        self.fallback_session, self.control, self.registry, self.client = fallback_session, control, registry, client
        self.last_task = None
        self.last_task_time = 0
        self.last_prompt = ''
        self.last_turn_delegated = False
        self.previous_prompt = ""
        self.previous_prompt_time = 0

    @property
    def last_metrics(self):
        return None if self.last_turn_delegated else getattr(self.fallback_session,'last_metrics',None)

    @property
    def last_trace(self):
        return None if self.last_turn_delegated else getattr(self.fallback_session,'last_trace',None)

    def stream_response(self, prompt, **kwargs):
        from hanni.core.response_stream import check_cancelled, TurnCancelled
        self.last_turn_delegated = False
        check_cancelled()
        if self.last_task and re.fullmatch(r'(?:please\s+)?(?:cancel|stop|abort)(?:\s+(?:that|the|this|my|last))?\s+(?:task|job|request|work)[.!]?', prompt.strip(), re.I):
            self.control.request_cancel(self.last_task)
            yield 'Cancellation requested. Completed actions have not been undone.'
            return
        if time.monotonic()-self.last_task_time > 120:
            self.last_task = None
        explicit = explicit_delegation(prompt)
        if not explicit:
            self.previous_prompt = prompt
            self.previous_prompt_time = time.monotonic()
            yield from self.fallback_session.stream_response(prompt, **kwargs)
            return
        if not self.control.enabled:
            yield 'Hermes delegation is disabled. Enable explicit delegation in the Hermes tab first.'
            return
        followup = self.last_task is not None and bool(re.search(r'\b(?:that task|that job|continue|update|follow up)\b', prompt, re.I))
        submission = prompt
        if re.fullmatch(r'(?:please\s+)?(?:give|send|delegate|deligate|pass|hand off|assign)\s+(?:it|this|that|the task|that task)\s+to\s+hermes[.!]?', re.sub(OWNER_PREFIX, '', prompt.strip(), count=1, flags=re.I), re.I):
            if not self.previous_prompt or time.monotonic()-self.previous_prompt_time > 120:
                yield 'Tell me which task you want to give Hermes.'
                return
            submission = 'Owner explicitly requests Hermes delegation of this previous request: '+self.previous_prompt+'\nDelegation instruction: '+prompt+'\nPrevious local execution is not established. Check actual receipts before repeating any consequential action.'
        self.previous_prompt = prompt
        self.previous_prompt_time = time.monotonic()
        task = None
        self.last_turn_delegated = True
        try:
            check_cancelled()
            from hanni.reliability.context import current_request_id
            task = self.control.submit(submission, self.registry, key=current_request_id() or uuid4().hex,
                                       prior_task=self.last_task if followup else None)
            from hanni.core.response_stream import current_cancellation_event
            event = current_cancellation_event()
            if event is not None:
                self.control.turn_cancellations[task['id']] = event
            self.last_task, self.last_task_time = task['id'], time.monotonic()
            self.last_prompt = prompt
            check_cancelled()
            yield f"Hermes received task {task['id'][:8]}. I'll report the result here; any required approvals will appear in the Hermes tab."
        except TurnCancelled:
            if task is not None:
                try:
                    self.control.client.request('POST', '/tasks/'+task['id']+'/cancel', {})
                except RuntimeError:
                    pass
            raise
        except (RuntimeError, OSError, ValueError):
            yield 'Hermes is unavailable or the request was blocked. Review the saved submission in the Hermes tab; no paid service was used.'

    def invalidate_memory_context(self):
        method = getattr(self.fallback_session, 'invalidate_memory_context', None)
        if method:
            method()

    def close(self):
        pass  # Dashboard owns bridge lifecycle; the existing session traversal closes its inner session.
