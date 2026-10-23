"""Conservative owner-statement extraction. Never accepts tool/model/screen input."""
from __future__ import annotations

import ntpath
import re
from dataclasses import dataclass

from hanni.memory.privacy import validate_memory_text


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    content: str
    key: str
    value: str
    memory_type: str
    confidence: float = 0.9


def key_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.casefold().strip(' .?!'))


def absolute_path(text: str) -> bool:
    # Windows paths must work during off-Windows source tests as well.
    return text.startswith(('~/', '~\\', '/')) or ntpath.isabs(text)


_PROJECT = re.compile(r'^(?:my\s+)?(?P<name>[\w .-]{1,60}?)\s+(?:project|workspace)(?:\s+(?:folder|path|directory))?\s+(?:is(?:\s+(?:at|in))?|lives\s+(?:at|in))\s+(?P<path>.+)$', re.I)
_PREFERENCE = re.compile(r'^my\s+(?:preferred|favorite|favourite)\s+(?P<subject>[\w -]{1,40}?)\s+is\s+(?P<value>.+)$', re.I)
_USE = re.compile(r'^I\s+(?:prefer|use)\s+(?P<value>.+?)\s+(?:as|for)\s+my\s+(?P<subject>[\w -]{1,40})$', re.I)
_WORKFLOW = re.compile(r'^when\s+I\s+(?P<trigger>[\w ,.-]{1,80}),\s+I\s+(?:usually|always)\s+(?P<value>.+)$', re.I)
_DEVICE = re.compile(r'^my\s+(?P<subject>(?:work |home |main )?(?:laptop|desktop|phone|tablet|printer))\s+is\s+(?P<value>.+)$', re.I)
_DECISION = re.compile(r'^(?:I|we)\s+(?:decided|chose)\s+to\s+(?P<value>.+)$', re.I)
_MODEL = re.compile(r'^my\s+(?:primary|main)\s+model\s+is\s+(?P<value>.+)$', re.I)
_MODEL_SWITCH = re.compile(r'^I\s+switched\s+my\s+(?:primary|main)\s+model\s+to\s+(?P<value>.+)$', re.I)
# Do not extract quoted/conditional/example speech or transient chat as a stable fact.
_UNCERTAIN = re.compile(r'\b(?:maybe|might|perhaps|hypothetically|for example|if |used to|not sure|don.t remember|do not remember|don.t save|do not save|private|off the record|today|tonight|currently|right now|for now|yesterday|tomorrow|no longer|not)\b', re.I)


def extract_fact(text: str, *, explicit: bool = False, max_chars: int = 1200) -> ExtractedFact | None:
    clean = validate_memory_text(text, max_chars=max_chars).strip().rstrip('.!?')
    if not explicit and (len(clean) > 350 or '\n' in text or '?' in text or _UNCERTAIN.search(clean) or clean.startswith(('"', "'", '`')) or re.search(r'[.!;]\s+[A-Za-z]', clean)):
        return None
    match = _PROJECT.fullmatch(clean)
    if match:
        name = match['name'].strip()
        path = match['path'].strip().strip('"\'')
        if absolute_path(path) and not any(c in path for c in ('\n', '\r', '\x00', '"')):
            return ExtractedFact(clean, 'project:' + key_text(name), path, 'project', 1.0 if explicit else 0.9)
        return None
    style = re.fullmatch(r'I prefer (short|brief|concise|detailed|long)(?: spoken)? (?:answers|responses|replies)', clean, re.I)
    if style:
        return ExtractedFact(clean, 'preference:response length', style[1].casefold(), 'preference')
    match = _PREFERENCE.fullmatch(clean) or _USE.fullmatch(clean)
    if match:
        subject = key_text(match['subject'])
        subject = {'editor': 'code editor', 'ide': 'code editor', 'programming language': 'coding language',
                   'main model': 'primary model'}.get(subject, subject)
        return ExtractedFact(clean, 'preference:' + subject, match['value'].strip(), 'preference')
    match = _MODEL.fullmatch(clean) or _MODEL_SWITCH.fullmatch(clean)
    if match:
        return ExtractedFact(clean, 'preference:primary model', match['value'].strip(), 'preference')
    match = _WORKFLOW.fullmatch(clean)
    if match:
        return ExtractedFact(clean, 'workflow:' + key_text(match['trigger']), match['value'].strip(), 'workflow')
    match = _DEVICE.fullmatch(clean)
    if match and (explicit or re.search(r'\b(?:ThinkPad|Lenovo|Dell|HP|Asus|Acer|Framework|Apple|MacBook|Samsung|Google|iPhone|Pixel|Surface|Brother|Epson|Canon)\b', match['value'], re.I)):
        return ExtractedFact(clean, 'device:' + key_text(match['subject']), match['value'].strip(), 'device')
    match = _DECISION.fullmatch(clean)
    if match:
        # Decisions have no universal conflict key. Only concise stable declarations.
        return ExtractedFact(clean, '', match['value'].strip(), 'decision', 0.85)
    return None


def project_reference(text: str) -> str | None:
    match = re.fullmatch(r'(?:(?:please|hanni|honey)[, ]+)?(?:(?:can|could|would) you )?(?:open|show|locate|find)\s+(?:my|the)\s+([\w .-]{1,60}?)\s+(?:project|workspace)(?:\s+folder)?[.!?]*', text.strip(), re.I)
    return key_text(match[1]) if match else None
