"""Conservative ingress classification; never supplies execution consent."""
import re


def workflow_request(prompt):
    from hanni.tools.routing_intents import action_requested, clauses, request_intent, no_tool_request
    clean = request_intent(prompt)
    if no_tool_request(clean):
        return False
    if prompt.casefold().startswith('/goal '):
        return True
    persistent = re.search(r'\b(?:automate|monitor|keep checking|keep watching|every \d+|until)\b', clean, re.I)
    dependent = re.search(r'\b(?:then|after that|once that|followed by)\b', clean, re.I)
    parts = clauses(clean)
    actions = sum(action_requested(part) for part in parts)
    return bool(persistent or dependent and len(parts) >= 2 and actions >= 2)


def needs_grounding(prompt):
    from hanni.tools.routing_intents import no_tool_request, request_intent, action_requested
    positive = request_intent(prompt)
    if no_tool_request(positive):
        return False
    return bool(action_requested(positive) or re.search(
        r'\b(?:my|mine|this computer|this machine|current|currently|right now|actual|measured)\b', positive, re.I))
