"""Catalog vocabulary for retrieval, independent of evaluation prompts.

Rules describe operations and their objects, not complete utterances. Returned
IDs are a candidate menu; only the model may call them. More specific operations
precede broader status questions. Unrecognized language has no forced default.
"""
import re

from hanni.tools.time_routing import normalize_question


def normalize(text: str) -> str:
    text = normalize_question(text)
    replacements = {'whats': "what's", 'whos': "who's", 'wats': "what's", 'wat': 'what',
                    'tmrw': 'tomorrow', 'tmr': 'tomorrow', 'rn': 'right now',
                    'mem': 'memory', 'proccess': 'process', 'proccesses': 'processes',
                    'proccessor': 'processor', 'calender': 'calendar', 'calandar': 'calendar',
                    'comp': 'computer', 'y': 'why', 'laggin': 'lagging',
                    'eatin': 'eating', 'hoggin': 'hogging', 'slammin': 'hammering',
                    'runnin': 'running', 'ur': 'your', 'cal': 'calendar', 'pls': 'please',
                    'memroy':'memory','proceses':'processes','usng':'using'}
    return re.sub(r'\b[a-z]+\b', lambda m: replacements.get(m[0], m[0]), text)


_QUOTED_ARGUMENT = re.compile(r'"[^"\n]*"|(?<!\w)\x27[^\x27\n]*\x27(?!\w)')
_ACTION_VERBS = ('open|launch|visit|start|stop|end|restart|terminate|kill|close|quit|create|make|write|type|save|replace|edit|modify|rename|move|copy|duplicate|delete|erase|wipe|remove|install|uninstall|send|post|push|commit|checkout|focus|play|pause|resume|skip|replay|set|change|switch|flip|enable|disable|turn|shut|reboot|mute|unmute|silence|dim|brighten|minimize|maximize|restore|keep|run|execute|format|reformat|lint|extract|unpack|compress|bundle|append|jot|notify|remind|pop|mark|finish|complete|add|put|book|schedule|bypass')
_NEGATIVE_VERBS = _ACTION_VERBS.split('|') + ['read','generate','inspect','check','measure','touch','perform',
    'claim','fabricate','invent','download','share','stage','clear','pair','unplug',
    'infer','assume','attribute']
_NEGATIVE_OPERATION = '(?:' + '|'.join(sorted({word[:-1] if word.endswith('e') else word for word in _NEGATIVE_VERBS})) + r')\w*\b'


def mask_arguments(text: str) -> str:
    """Quoted literals may supply arguments, never operation-selection words."""
    def mask(match):
        literal=match[0][1:-1]
        object_position=re.search(r'\b(?:open|launch|start|focus)\s+$',text[:match.start()],re.I)
        # A single named application remains an object. Multiword instructions
        # remain opaque data even when they occur at an object position.
        if object_position and re.fullmatch(r'[A-Za-z][\w.+-]{0,63}',literal): return literal
        return 'quoted text'
    return _QUOTED_ARGUMENT.sub(mask, text)


def request_intent(text: str) -> str:
    """Retain positive requests while excluding explicit negative constraints.

    Return the literal owner arguments unchanged. A separate masked copy is used
    for operation selection, and every invocation still uses the original gates.
    """
    quoted=[]
    def protect(match):
        quoted.append(match[0]); return f'QUOTEDARGUMENT{len(quoted)-1}TOKEN'
    protected=_QUOTED_ARGUMENT.sub(protect,text)
    parts=_CLAUSE.split(protected)
    expanded=[]
    for part in parts:
        # A comma can attach an imperative to its problem statement rather
        # than introduce a separate operation ("CPU spiked, find the cause").
        # Split it only after an already explicit request or negative clause.
        pieces=[]
        start=0
        for boundary in _REQUEST_BOUNDARY.finditer(part):
            left=part[start:boundary.start()]
            if boundary[0].lstrip().startswith(',') and not _REQUEST_START.match(left):
                continue
            pieces.append(left)
            start=boundary.end()
        pieces.append(part[start:])
        if len(pieces)>1 and re.match(r'^\s*(?:for|in|within|under|from|using)\b',pieces[0],re.I):
            # A leading source scope modifies the next request. It cannot
            # independently authorize or complete an observation.
            pieces[1]=pieces[0]+', '+pieces[1]
            pieces=pieces[1:]
        expanded.extend(pieces)
    parts=expanded
    positive=[]
    for part in parts:
        part=re.sub(r'(?:[,;.]\s*|\s+(?:but|and)\s+|\s+|^)(?:don[\x27\u2019]t|do not|never|without)\s+'
            + _NEGATIVE_OPERATION + r'.*$', '',part,flags=re.I)
        part=re.sub(r'[,;]\s*(?:not|rather than|instead of)\b.*$','',part,flags=re.I)
        part=re.sub(r'\.\s*(?:this|that|it)\s+(?:grants?|gives?|is)\s+no\s+(?:permission|authorization)\b.*$','',part,flags=re.I)
        part=part.strip(' ,;.')
        if part: positive.append(part)
    # A response refinement with a same-target referent is part of the read,
    # not an independent source request. Retain its wording and antecedent so
    # the original selector and ledger see the same bounded operation.
    combined=[]
    for part in positive:
        if combined and _dependent_read(part, combined[-1]):
            combined[-1] += ' '+part
        else:
            combined.append(part)
    result='; '.join(combined)
    result=re.sub(r'^(?:(?:please|actually|now|just)\s+|(?:can|could|would)\s+you\s+)+','',result,flags=re.I)
    for index,value in enumerate(quoted): result=result.replace(f'QUOTEDARGUMENT{index}TOKEN',value)
    return result


_RESOURCE_PATTERNS = {
    'cpu': r'\b(?:cpu|processor)\b',
    'gpu': r'\b(?:gpu|vram|video memory|graphics memory|graphics card)\b',
    'memory': r'\b(?:ram|memory)\b',
    'disk': r'\b(?:disk|storage|drive)\b',
    'battery': r'\b(?:battery|charge)\b',
}


def _resources(text: str) -> set[str]:
    text = re.sub(_RESOURCE_PATTERNS['gpu'], ' gpu ', text.casefold())
    return {name for name, pattern in _RESOURCE_PATTERNS.items() if re.search(pattern, text)}


def _dependent_read(text: str, antecedent: str) -> bool:
    """Join only bounded read refinements, never a new action or source."""
    value = text.casefold()
    if _ACTION.search(normalize(mask_arguments(antecedent))):
        return False
    if not re.match(r'^(?:i\s+(?:only\s+)?(?:need|want)|(?:please\s+)?(?:give|report|tell|show|provide|return|limit|restrict|keep))\b', value):
        return False
    # A referent does not turn a new operation into formatting. Do not join
    # mutation verbs, new read operations or different source identities.
    operation_words = _ACTION_VERBS.replace('|keep|', '|') + '|read|inspect|check|measure|find|search|compare|calculate|convert|count|hash|checksum|digest|uptime'
    if re.search(r'\b(?:'+operation_words+r')\b', value):
        return False
    if (re.search(r'\bfile\b', antecedent, re.I)
            and re.search(r'\b(?:size|metadata)\b', value)):
        return False
    if (re.search(r'\b(?:pid|process(?: id)?)\s*\d+\b', antecedent, re.I)
            and re.search(r'\bname\b', value)):
        return False
    if _resources(value) - _resources(antecedent):
        return False
    if re.search(r'\b(?:pid|process id)\s*\d+\b|\b(?:file|folder|directory|path|repo|repository|calendar|spotify|defender|firewall|archive|network|wifi|clipboard|email|account|audio|service|pc|computer|machine|laptop|system)\b|[a-z]:[\\/]', value):
        return False
    ranking = bool(re.search(r'\b(?:top|biggest|largest|highest|leaders?|consumers?|ranking)\b', value))
    if (ranking and re.match(r'^\s*(?:read|check|inspect|show|measure|report|give)\b', antecedent, re.I)
            and not re.search(r'\b(?:top|biggest|largest|highest|leaders?|consumers?|ranking)\b', antecedent, re.I)):
        return False
    if re.search(r'\b(?:it|its|that|those|this|same)\b', value):
        return True
    # A per-process detail/ranking refinement can inherit a unique resource
    # explicitly supplied earlier in this owner turn.
    return (len(_resources(antecedent)) == 1 and
            bool(re.search(r'\b(?:per.process|process (?:leaders|consumers|details))\b', value)))


def resource_followup(text: str, history=()) -> str | None:
    """Resolve a read ranking's unique recent owner subject, not its answer."""
    value = text.casefold()
    ranking = bool(re.search(r'\b(?:most|biggest|largest|highest|top)\b', value))
    process = bool(re.search(r'\b(?:process(?:es)?|tasks?|programs?|apps?|consumer)\b|'
                             r'\bwho\b.*\b(?:using|uses|consum\w*)\b', value))
    referent = bool(re.search(r'\b(?:it|that(?: resource| memory)?|this resource)\b', value))
    explicit = _resources(value)
    # "that memory" may refer to video memory. All other explicitly named
    # resources are already complete requests and need no history bridge.
    if not (ranking and process and referent) or explicit - {'memory'} or action_requested(value):
        return text
    prior = next((str(item.get('content', '')) for item in reversed(history)
                  if item.get('role') == 'user'), '')
    prior = request_intent(prior)
    if no_tool_request(prior):
        return None
    subjects = _resources(mask_arguments(prior))
    if len(subjects) != 1:
        return None
    subject = next(iter(subjects))
    if subject not in {'cpu', 'memory', 'gpu'}:
        return None
    return text+' '+{'cpu': 'CPU', 'memory': 'RAM', 'gpu': 'GPU'}[subject]


def no_tool_request(text: str) -> bool:
    """Conceptual and text-only requests do not request state observations."""
    text=normalize(mask_arguments(text))
    if not text: return True
    if re.match(r'^keep\s+(?:it|your answer|the response)\s+(?:to|brief|short|concise)\b',text): return True
    if re.search(r'\b(?:fictional|hypothetical)\s+(?:scene|story|example)\b|\b(?:proofread|mnemonic)\b',text):
        return not re.search(r'\b(?:read|inspect|check)\b.*\bfile path\b',text)
    if re.match(r'^(?:quote|paraphrase|translate|rewrite)\s+quoted text\b',text): return True
    if re.search(r'\b(?:example in my writing|explain its grammar)\b',text): return True
    if 'quoted text' in text and re.search(r'\b(?:grammar|verbs?|adjectives?|punctuation|wording|syntax)\b',text): return True
    if re.search(r'\b(?:definition|conceptually|in general)\b',text) and not re.search(r'\b(?:file path|read|inspect|check|measure)\b',text): return True
    educational=bool(re.match(r'^(?:explain|define|describe|teach|how does|how do|why can|why do)\b',text))
    live=bool(re.search(r'\b(?:i|my|mine|you|your|hanni|this|current|currently|right now|actual|measured)\b',text))
    source=bool(re.search(r'\bfile path\b|\b(?:read|inspect|check|measure|look up)\b',text))
    if educational and not live and not source:
        # Preserve the original symptom diagnostic contract. Explicitly
        # conceptual requests have already returned above.
        from hanni.tools.capabilities import diagnostic_subintent
        diagnostic=diagnostic_subintent(text)
        return not diagnostic or diagnostic.name != 'general_slowdown'
    return False


# Conjunctions split only when followed by a new request clause. Resource lists
# (CPU and RAM), filenames, event titles and search terms remain intact.
_CLAUSE = re.compile(r'\s+(?:and\s+(?:also\s+)?|plus\s+|also\s+|then\s+)(?=(?:what|whats|whos|who|where|which|when|how|why|is|are|am|do|does|show|tell|give|check|inspect|measure|report|find|list|open|start|play|pause|skip|read|write|type|search|kill|delete|remove|set|current|got|biggest|the\s+(?:biggest|top))\b)|\s+plus\s+(?=(?:my\s+)?(?:ram|memory|cpu|gpu|vram|disk|storage|drive)\s+(?:usage|use|status|hog|space|left)\b|(?:tomorrow|tmr|today)\s+plans\b|top\s+(?:cpu|ram|memory|disk|gpu)\b)|\s*;\s*', re.I)
_REQUEST_BOUNDARY = re.compile(r'(?:[.!?]\s+|,\s*(?:but\s+)?|\s+but\s+)'
    r'(?=(?:(?:please|now|actually|just)\s+)*(?:(?:can|could|would)\s+you\s+)?'
    r'(?:what|who|where|which|when|how|why|show|tell|give|check|find|list|read|inspect|measure|report|'
    + _ACTION_VERBS + r')\b)',re.I)
_REQUEST_START = re.compile(r'^\s*(?:(?:please|now|actually|just)\s+)*(?:(?:can|could|would)\s+you\s+)?'
    r'(?:what|who|where|which|when|how|why|show|tell|give|check|find|list|read|inspect|measure|report|'
    r'for|in|within|under|from|using|don[\x27\u2019]t|do not|never|without|'
    + _ACTION_VERBS + r')\b',re.I)


_TOPIC_MARKERS = {
    'calendar': r'\b(?:calendar|agenda|schedule|timetable|diary|meeting|appointment|class|today|tomorrow|tmr|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
    'diagnostics': r'\b(?:cpu|processor|ram|memory|gpu|vram|disk|drive|storage|battery|power|temperature|performance|system|network|connection|wifi)\b',
    'media': r'\b(?:spotify|song|track|tune|music|playback|media)\b',
    'model': r'\b(?:model|llm|qwen|hanni|context|quant|quantization)\b',
    'files': r'\b(?:files?|folders?|documents?|pdf|resume|spreadsheet|invoice|receipt|report|budget)\b',
    'applications': r'\b(?:discord|steam|chrome|vscode|vs code|powershell)\b',
}


def _topics(text: str) -> set[str]:
    return {name for name, pattern in _TOPIC_MARKERS.items() if re.search(pattern, text, re.I)}


def clauses(text: str) -> tuple[str, ...]:
    # Quoted content belongs to an argument, not a second request.
    if re.search(r'"[^"\n]*"', text):
        return (text,)
    parts = tuple(part.strip(' ,') for part in _CLAUSE.split(text) if part.strip(' ,'))
    if len(parts) == 1 and re.search(r'\b(?:disk|storage)\s+space\s+and\s+(?:cpu|ram|gpu|vram)\s+(?:usage|memory|space)\b', text, re.I):
        parts = tuple(part.strip(' ,') for part in re.split(r'\s+and\s+(?=(?:cpu|ram|gpu|vram|disk|storage)\s+(?:usage|memory|space)\b)', text, maxsplit=1, flags=re.I))
    if len(parts) == 1:
        expanded = re.split(r'\s+(?:while|as well as|along with)\s+|,\s*(?=(?:check|tell|show|open|launch|start|find|search|what|how|is|are)\b)',
                            text, maxsplit=1, flags=re.I)
        if (len(expanded) == 2 and all(part.strip(' ,') for part in expanded)
                and (not re.search(r'\bwhile\b|,', text, re.I)
                     or re.search(r'\b(?:pc|computer|machine|calendar|spotify|music|cpu|ram|memory|gpu|disk|storage|file)\b', expanded[1], re.I))):
            parts = tuple(part.strip(' ,') for part in expanded)
    if len(parts) == 1 and re.search(r'\b(?:spotify|song|track|music|calendar|agenda|appointment)\b', text, re.I):
        expanded = re.split(r'\s+(?:and|with)\s+(?=(?:current\s+)?(?:cpu|ram|memory|gpu|vram|disk|storage)\b)',
                            text, maxsplit=1, flags=re.I)
        if len(expanded) == 2 and all(part.strip(' ,') for part in expanded):
            parts = tuple(part.strip(' ,') for part in expanded)
    if len(parts) == 1:
        expanded = re.split(r'\s+plus\s+(?=free\s+(?:disk|drive|storage)\s+space\b)', text, maxsplit=1, flags=re.I)
        if len(expanded) == 2:
            parts = tuple(part.strip(' ,') for part in expanded)
    if len(parts) == 1 and re.search(r'\b(?:calendar|tomorrow|tmr|today|friday|monday|tuesday|wednesday|thursday|saturday|sunday|open|launch|spotify)\b', text, re.I):
        expanded = re.split(r'\s+(?:and|plus|then)\s+(?=(?:cpu\s+load|(?:disk|storage)\s+(?:space|left)|(?:tomorrow|tmr)\s+plans|see\s+if|show\s+hanni|what\s+time|what(?:s|\'s)\s+(?:tomorrow|my\s+gpu)|how\s+much\s+ram)\b)', text, maxsplit=1, flags=re.I)
        if len(expanded) == 2:
            return tuple(part.strip(' ,') for part in expanded)
    if len(parts) == 1:
        # A terse compound often has two topic-bearing fragments instead of
        # two complete sentences. Require a real topic change; ordinary noun
        # lists such as "CPU and RAM usage" stay in one clause.
        for split in re.finditer(r'\s*,\s*|\s+(?:and|plus|also|then|with|as well as|along with|while you(?:\x27| a)re at it),?\s+', text, re.I):
            left, right = text[:split.start()].strip(' ,'), text[split.end():].strip(' ,')
            left_topics, right_topics = _topics(left), _topics(right)
            if (left and right and left_topics and right_topics
                    and left_topics - right_topics and right_topics - left_topics):
                return (left, right)
    return parts


_ACTION = re.compile(r'^(?:(?:please|now|just)\s+)*(?:get\s+[\w.-]+\s+up$|fire\s+up|bring\s+up|' + _ACTION_VERBS + r')\b')


def action_requested(text: str) -> bool:
    text=normalize(request_intent(text))
    if re.match(r'^start\s+with\b',text): return False
    return bool(_ACTION.search(text))


# Each tuple is (object/operation regex, candidate IDs). Multiple tools are
# supplied only when their semantics are useful alternatives or complements.
_SOURCES = (
    (r"\bwhich files? are huge\b", ('disk.largest_files',)),
    (r"\bwhat is taking up storage\b", ('disk.largest_folders',)),
    (r"\bwhat went wrong with my computer\b", ('system.event_errors',)),
    (r"\bam i charging\b", ('power.battery_detail',)),
    (r"\b(?:healthy|normal|normally|obvious issues|looks unhealthy|look wrong)\b.*\b(?:pc|computer|system)\b|\b(?:pc|computer|system)\b.*\b(?:healthy|normal|normally|obvious issues|looks unhealthy|look wrong)\b|\btell me if anything looks unhealthy\b", ('system.performance','system.stats')),
    (r"\b(?:locate the exact file|where did i put)\b", ('file.locate',)),
    (r"\b(?:disk almost cooked how much free|ssd space right now)\b", ('disk.free_space',)),
    (r'\b(?:without|need|needs?|require|requires?)\s+(?:my\s+)?consent\b', ('hanni.permissions',)),
    (r"\b(?:can|could|may|is)\s+(?:hanni|you)\b.*\b(?:allowed|permitted|able|kill|stop|end|delete|run)\b", ('hanni.permissions',)),
    (r"\b(?:what|which)\b.*\b(?:gpu|graphics\s+card)\b.*\bhanni\b|\bhanni\b.*\b(?:gpu|graphics\s+card)\b", ('model.status', 'gpu.top_processes')),
    (r"\b(?:is|has)\s+hanni\b.*\b(?:stopped|halted|safe\s+mode)\b", ('hanni.stop_state',)),
    (r"\b(?:what can hanni do|hanni capabilities|hanni tools)\b", ('hanni.capabilities',)),
    (r"\bhanni\b.*\b(?:recent|tool)\b.*\b(?:activity|actions|calls)\b", ('hanni.audit_tail',)),
    (r"\b(?:quant|quantization|context\s+(?:size|length))\b.*\b(?:model|loaded|running)\b|\bmodel\b.*\b(?:quant|context)\b", ('model.status',)),
    (r"\b(?:bad|important|critical)\b.*\b(?:errors?|events?)\b", ('system.event_errors',)),
    (r"\bhow hot is my (?:pc|computer|gpu)\b", ('system.stats',)),
    (r"\bwhere\b.*\b(?:resume|cv|file)\b.*\b(?:go|went|put)\b", ('file.locate',)),
    (r"\b(?:find|where)\b.*\b(?:resume|spreadsheet|document|pdf|file)\b", ('file.search',)),
    (r"\bhow big\b.*\b(?:downloads|documents|desktop|folder|directory)\b", ('disk.folder_size',)),
    (r'\baudit\b', ('hanni.audit_tail',)),
    (r'^open\b.*\b(?:email|message)\b', ('gmail.read',)),
    (r'\b(?:this|that|the) text file says\b', ('file.read',)),
    (r'^(?:permanently )?(?:delete|clean)\b.*\btemp(?:orary)?\b', ('disk.cleanup_temp',)),
    (r'^permanently delete\b', ('file.delete',)),
    (r'\b(?:ports?|sockets?)\b', ('net.ports',)),
    (r'\b(?:without asking|require confirmation)\b', ('hanni.permissions',)),
    (r'\b(?:hotfixes|patches)\b|\bpc\b.*\bupdated\b', ('security.updates',)),
    (r'\b(?:reading and writing)\b', ('process.top_disk_io', 'system.stats')),
    (r'\b(?:audio status)\b', ('audio.status',)),
    (r'\b(?:tasks are running)\b', ('process.list',)),
    (r'\b(?:used and free|all drives|every drive)\b', ('disk.usage',)),
    (r'\b(?:how many|count)\b.*\b(?:pdfs|images|photos|files)\b.*\b(?:folder|directory|in|under)\b', ('file.composition',)),
    (r'\b(?:nvme|storage device|hard drive)\b.*\b(?:health|healthy|failing|wrong)\b|\b(?:health|wrong)\b.*\b(?:nvme|hard drive)\b', ('device.disk_health',)),
    (r'\bpackages\b.*\bpython\b|\b(?:python|pip|venv|virtual)\b.*\b(?:env|environment|interpreter|packages|installed)\b|\bpackages\b.*\b(?:virtual|environment)\b', ('python.env_info',)),
    (r'\b(?:encryption|bitlocker)\b', ('security.bitlocker',)),
    (r'\b(?:dns|resolve.*hostname|resolve.*ip)\b', ('net.dns_lookup',)),
    (r'\b(?:event log|event viewer|critical errors|event errors|windows errors|blue.?screen|bsod)\b', ('system.event_errors',)),
    (r'\b(?:terminate|kill)\b|^(?:stop|end)\b.*\b(?:process(?:es)?|ram|cpu|running\s+tasks?)\b', ('process.stop',)),
    (r'^(?:delete|erase|remove)\b', ('file.delete',)),
    (r'^(?:restart|start|stop|turn off)\b.*\bservice\b', ('service.control',)),
    (r'\b(?:powershell|terminal command)\b', ('powershell.run',)),
    (r'\b(?:pytest|automated tests|test suite)\b|^run\b.*\btests?\b', ('project.test',)),
    (r'\b(?:lint|ruff|flake8|style errors)\b', ('project.lint',)),
    (r'\b(?:reformat|formatting|black)\b|^format\b', ('project.format',)),
    (r'^(?:clean|delete)\b.*\btemp(?:orary)?\b', ('disk.cleanup_temp',)),
    (r'\b(?:keep|set|change)\b.*\b(?:awake|sleep|screen.off|timeout)\b', ('power.set_idle',)),
    (r'^(?:switch|set|change|enable|flip)\b.*\b(?:power|balanced|performance|saver)\b', ('power.set_plan',)),
    (r'\bbattery\b.*\b(?:health|wear|report)\b', ('power.battery_report',)),
    (r'\b(?:brightness|dim|brighten|brighter)\b', ('display.brightness',)),
    (r'\bspotify\b.*\b(?:uri|spotify:)\b|spotify:', ('spotify.open_uri',)),
    (r'\bfire up spotify\b', ('spotify.launch',)),
    (r'\bstop spotify\b', ('media.stop',)),
    (r'\bspotify\b', ('@spotify',)),
    (r'\b(?:media|video)\b.*\b(?:previous|back)\b|\b(?:previous|back)\b.*\b(?:media|video)\b', ('media.previous_track',)),
    (r'\b(?:skip|next.track)\b.*\b(?:media|video)\b|\bmedia\b.*\bnext\b', ('media.next_track',)),
    (r'\b(?:stop)\b.*\b(?:media|playback)\b|\bmedia stop\b', ('media.stop',)),
    (r'\b(?:play|pause|resume)\b.*\b(?:media|video|playback)\b', ('media.play_pause',)),
    (r'\b(?:skip|next)\b.*\b(?:song|track)\b', ('spotify.next', 'media.next_track')),
    (r'\b(?:mute|unmute|silence)\b', ('audio.mute',)),
    (r'^(?:turn|set|lower|raise)\b.*\b(?:volume|sound)\b', ('audio.set_volume',)),
    (r'\b(?:how loud|volume|muted|mute state)\b', ('audio.status',)),
    (r'^(?:open|visit)\b.*\b(?:https?|website|browser)\b', ('browser.open_url',)),
    (r'\b(?:minimize every|minimize all|show my desktop|hiding the windows)\b', ('ui.minimize_all',)),
    (r'^(?:maximize|minimize|restore)\b.*\bwindow\b', ('ui.window_state',)),
    (r'^(?:close|quit)\b.*\bwindow\b', ('ui.close_window',)),
    (r'^focus\b|^bring\b.*\b(?:window|foreground)\b|^switch\b.*\bwindow\b', ('ui.focus_window',)),
    (r'\b(?:extract|unzip|unpack)\b', ('archive.unzip',)),
    (r'\b(?:compress|bundle)\b|^zip\b', ('archive.zip',)),
    (r'\b(?:zip|archive)\b', ('archive.list',)),
    (r'^(?:copy|put)\b.*\b(?:clipboard|paste buffer)\b', ('clipboard.write',)),
    (r'\b(?:clipboard|paste buffer)\b|\bwhat.*did i copy\b', ('clipboard.read',)),
    (r'\b(?:create|make)\b.*\b(?:folder|directory)\b', ('file.mkdir',)),
    (r'^(?:move|rename)\b', ('file.move',)),
    (r'^(?:copy|duplicate)\b', ('file.copy',)),
    (r'^(?:write|save|replace)\b.*\b(?:file|contents|txt)\b', ('file.write',)),
    (r'^(?:open|launch|start)\s+(?:file\s+)?explorer$', ('app.open',)),
    (r'\b(?:open|show)\b.*\b(?:folder|directory)\b.*\bin explorer\b', ('folder.open',)),
    (r'^open\b.*\b(?:file|pdf|document|txt|folder)\b|\bassociated app\b', ('file.open',)),
    (r'^(?:open|launch|fire up|bring up)\b(?!.*\bwindow\b)|^get\s+[\w.-]+\s+up$', ('app.open',)),
    (r'^start\s+(?:discord|code|obs|steam|chrome|firefox|blender|notepad)\b', ('app.open',)),
    (r'\b(?:notify|notification|pop up|alert)\b', ('notify.toast',)),
    (r'\b(?:timer|countdown|remind me in)\b', ('timer.set',)),
    (r'^(?:mark|finish|complete)\b.*\b(?:task|assignment|homework)\b', ('todo.complete',)),
    (r'^(?:save|add)\b.*\b(?:task|assignment|homework)\b', ('todo.add',)),
    (r'\b(?:tasks?|assignments?|homework)\b.*\b(?:due|overdue)\b|\boverdue\b', ('todo.due',)),
    (r'\b(?:task|assignment)\b.*\b(?:id|number)\s*\d+\b', ('todo.get',)),
    (r'\b(?:tasks?|assignments?|homework)\b(?!.*\b(?:windows|scheduled|automatically|cpu|processor|ram|memory|gpu|vram|disk|process)\b)', ('todo.list',)),
    (r'\b(?:scheduled|windows)\b.*\b(?:tasks|jobs)\b|\bwhat runs automatically\b', ('schedule.list_tasks',)),
    (r'\b(?:jot|append|note to self)\b', ('note.append',)),
    (r'\b(?:days|dates)\b.*\bnotes?\b', ('note.days',)),
    (r'\b(?:search|find)\b.*\bnotes?\b', ('note.search',)),
    (r'\bnotes\b', ('note.list',)),
    (r'\bgoogle\b.*\b(?:accounts?|login|connections?)\b(?!.*\bcalendar\b)', ('google.accounts',)),
    (r'\b(?:email|gmail|inbox|messages?)\b', ('@email',)),
    (r'\b(?:emails|inbox)\b', ('gmail.search',)),
    (r'\b(?:model|llm|qwen|llama)\b(?!.*\b(?:process|vram|gpu|memory)\b)|\bwhy are you.*slow', ('model.status',)),
    (r'\b(?:service)\b.*\b(?:running|stopped|status)\b', ('service.list',)),
    (r'\b(?:defender|antivirus)\b', ('security.defender',)),
    (r'\b(?:updates?|patches|hotfixes|updated)\b.*\b(?:windows|installed|pc)\b|\bwindows\b.*\b(?:updates?|patch)\b', ('security.updates',)),
    (r'\bprinters?\b', ('device.printers',)),
    (r'\b(?:version|edition|build)\b.*\bwindows\b', ('system.os_info',)),
    (r'\b(?:windows|computer|pc|laptop|machine)\b.*\b(?:boot|restarted|rebooted|been up)\b', ('system.uptime',)),
    (r'\bwhen did\b.*\bstart\b', ('process.uptime',)),
    (r'\b(?:process|pid)\b.*\b\d+\b', ('process.inspect',)),
    (r'\bwindows\b.*\b(?:processes|pids|owning|minimized)\b', ('ui.windows_detailed',)),
    (r'\b(?:low on|running out of)\b.*\b(?:vram|gpu memory|video memory)\b', ('gpu.memory',)),
    (r'\b(?:top|most|highest|rank|biggest|hogging|consumes?|hammering)\b.*\b(?:gpu|vram|graphics)\b|\b(?:gpu|vram)\b.*\b(?:processes|consumption)\b', ('gpu.top_processes', 'gpu.memory')),
    (r'\b(?:how much|free|enough|headroom|available|left|load another)\b.*\b(?:vram|gpu|video memory|graphics memory)\b|\b(?:vram|gpu memory)\b.*\b(?:free|enough|headroom|left|available)\b', ('gpu.memory',)),
    (r'\b(?:most|top|highest|rank|biggest|consumes?)\b.*\b(?:cpu|processor)\b', ('process.top_cpu', 'system.stats')),
    (r'\b(?:most|top|highest|rank|biggest|consumes?)\b.*\b(?:ram|memory)\b', ('process.top_memory', 'system.stats')),
    (r'\b(?:disk|drive)\b.*\b(?:activity|thrashing|writes|reads|io|i/o)\b|\b(?:thrashing|reading and writing|using)\b.*\b(?:disk|drive)\b', ('process.top_disk_io', 'system.stats')),
    (r'\b(?:system stats|resource usage|hardware utilization|system resources|how loaded)\b', ('system.stats',)),
    (r'\b(?:cpu|processor)\b.*\b(?:ram|memory)\b|\bhow much\b.*\b(?:ram|memory)\b', ('system.stats',)),
    (r'\b(?:pid|process (?:number )?\d+)\b', ('process.uptime', 'process.inspect')),
    (r'\bhow long\b.*\b(?:running|open)\b|\bwhen did\b.*\bstart\b', ('@uptime',)),
    (r'\b(?:what is running|process list|tasks are running)\b', ('process.list',)),
    (r'^(?:(?:is|check whether)\s+(?:the\s+)?[\w.-]+\s+(?:currently\s+)?(?:running|open)|find\b.*\bprocess)\b', ('process.find',)),
    (r'\b(?:processes|running programs|programs.*running|process inventory)\b', ('process.list',)),
    (r'\b(?:installed|software version)\b', ('app.list_installed',)),
    (r'\b(?:launch(?:es)?|starts?)\b.*\b(?:log in|automatically|turns on)\b', ('startup.list',)),
    (r'\b(?:startup|login|starts? with|boot programs)\b', ('startup.list',)),
    (r'\bservices\b|\bservice\b.*\b(?:running|stopped|state)\b', ('service.list',)),
    (r'\b(?:pending|require|waiting|need)\b.*\b(?:reboot|restart)\b|\b(?:reboot|restart) pending\b', ('security.pending_reboot',)),
    (r'\b(?:updates|patches|hotfixes)\b', ('security.updates',)),
    (r'\b(?:defender|antivirus|virus protection|protected)\b', ('security.defender',)),
    (r'\bfirewall\b', ('security.firewall',)),
    (r'\b(?:bitlocker|encrypted|encryption)\b', ('security.bitlocker',)),
    (r'\b(?:windows|os)\b.*\b(?:version|edition|build)\b|\b(?:hostname|system info|specs)\b', ('system.os_info',)),
    (r'\b(?:uptime|since.*boot|last.*restart|last.*reboot)\b', ('system.uptime',)),
    (r'\b(?:power plan|power mode|power profiles)\b', ('power.plans',)),
    (r'\b(?:sleep|sleeps|idle|timeout|turn off)\b.*\b(?:screen|power|settings|timeouts?)\b|\bscreen\b.*\b(?:sleeps|turn off)\b', ('power.idle_settings',)),
    (r'\bbattery\b.*\b(?:last|time|remaining)\b(?!.*\bpercent)', ('power.battery_detail',)),
    (r'\b(?:battery|charging)\b(?!.*\b(?:drain|hot)\b)', ('system.battery',)),
    (r'\b(?:bluetooth|headphones)\b', ('device.bluetooth',)),
    (r'\b(?:audio endpoints|audio devices|sound devices|microphones|speakers)\b', ('device.audio',)),
    (r'\bprinters?\b', ('device.printers',)),
    (r'\busb\b|\bplugged in\b', ('device.usb',)),
    (r'\b(?:ssd|hdd|disk|drive)\b.*\b(?:healthy|health|failing|dying)\b|\bsmart\b', ('device.disk_health',)),
    (r'\b(?:refresh|resolution|monitors|display adapters)\b', ('display.info',)),
    (r'\b(?:window is active|current window|app.*focused)\b', ('ui.active_window',)),
    (r'\b(?:open apps|desktop windows)\b', ('ui.windows_detailed',)),
    (r'\b(?:active|foreground|focused)\s+window\b|\bwindow\b.*\b(?:focus|title)\b', ('ui.active_window',)),
    (r'\bwindows\b.*\b(?:process|pid|minimized|owning)\b', ('ui.windows_detailed',)),
    (r'\b(?:top.level|visible)\b.*\bwindows?\b|\bwindows\b.*\bvisible\b', ('ui.list_windows',)),
    (r'\b(?:windows|apps)\b.*\bopen\b|\bwhat do i have open\b', ('ui.windows_detailed',)),
    (r'\b(?:variable)\b|\b(?:value of|read just)\b.*\b(?:temp|userprofile)\b', ('env.get',)),
    (r'\b(?:is \w+ on my path|npm command|node command|git command)\b|^which python am i', ('env.which',)),
    (r'\b(?:my path|environment path)\b', ('env.path',)),
    (r'\benvironment\b(?!.*\b(?:python|virtual)\b)', ('env.list',)),
    (r'\b(?:executable|command)\b.*\b(?:path|find|live)\b|\bwhere is\b.*\b(?:python|node|git|npm|pip)\b', ('env.which',)),
    (r'\bpath\b.*\b(?:entries|duplicate|nonexistent|broken|directories)\b|\bwhat.*on my path\b', ('env.path',)),
    (r'\b(?:where|location|resolve)\b.*\b(?:downloads|desktop|documents|user folder)\b', ('env.user_folders',)),
    (r'\b(?:python|venv|virtual environment|virtualenv)\b', ('python.env_info',)),
    (r'\b(?:git|repo|repository|commits?|branches|uncommitted|staged|unstaged)\b', ('@git',)),
    (r'\b(?:recycle bin|trash)\b', ('disk.recycle_bin_size',)),
    (r'\b(?:duplicates?|duplicated|byte.identical|same file twice|copies.*same file)\b|\bfind identical files\b', ('file.duplicates',)),
    (r'\b(?:biggest|largest|rank|most)\b.*\b(?:subfolders|folders)\b|\b(?:folders|subfolders)\b.*\b(?:most|size|huge|biggest|largest)\b|\bwhere did.*space go\b', ('disk.largest_folders',)),
    (r'\b(?:biggest|largest) files\b|\bfiles\b.*\bmost.*space\b', ('disk.largest_files',)),
    (r'\b(?:how big|size|measure)\b.*\b(?:folder|directory)\b', ('disk.folder_size',)),
    (r'\b(?:enough|before copying|required|remaining|free)\b.*\b(?:space|capacity|copy|storage)\b|\b(?:space|storage)\b.*\b(?:enough|copy|left)\b|\b(?:room|free)\b.*\bdrive\b', ('disk.free_space',)),
    (r'\b(?:space|capacity)\b|\b(?:disks?|drives?|ssd)\b.*\bfull\b|\bfull\b.*\b(?:ssd|disk|drive)\b', ('disk.usage',)),
    (r'\bstorage\b', ('disk.usage',)),
    (r'\b(?:duplicate|byte.identical)\b', ('file.duplicates',)),
    (r'\bempty\b.*\b(?:folders|directories)\b|\bfolders\b.*\bnothing\b', ('file.empty_folders',)),
    (r'\b(?:file type|extension|how many.*(?:pdf|image)|break.*down)\b', ('file.composition',)),
    (r'\btwo files match\b|\b(?:compare|diff)\b.*\b(?:versions|configs?|old|two)\b|\bwhat changed between\b', ('file.compare',)),
    (r'\b(?:compare|diff|identical|same)\b.*\b(?:files?|txt)\b|\btxt\b.*\bidentical\b', ('file.compare',)),
    (r'\b(?:first|beginning|head|preview)\b.*\b(?:lines|file|log)\b', ('file.head',)),
    (r'\b(?:last|final|end|tail|latest|recent|bottom)\b.*\b(?:lines|file|log)\b', ('file.tail',)),
    (r'\b(?:grep|mentioned|mention|text inside|look through files|search in.*documents)\b|\b(?:search inside|search through|mentions?|contains|wrote|mentioning)\b.*\b(?:files?|documents?|text|deadline)\b|\b(?:file|document)\b.*\b(?:mentions?|contains|says)\b', ('file.grep',)),
    (r'\b(?:files?|documents?|disk)\b.*\b(?:modified|touched|worked on|recently)\b', ('file.recent',)),
    (r'\b(?:recent|recently|changed|worked on)\b.*\b(?:files?|documents?)\b|\bfiles\b.*\b(?:changed|recently)\b', ('file.recent',)),
    (r'\b(?:exists?|metadata|hash file)\b', ('file.stat',)),
    (r'\b(?:locate|where did i put|exact file|exact folder)\b', ('file.locate',)),
    (r'\b(?:find|search|look for)\b.*\b(?:files?|filenames?|pdfs?|downloads|documents)\b', ('file.search',)),
    (r'\b(?:read|says|contents)\b.*\b(?:txt|text file)\b|\btext file says\b', ('file.read',)),
    (r'\b(?:contents|inside|in|list|show)\b.*\b(?:folder|directory|downloads|documents|desktop)\b', ('file.list_dir',)),
    (r'\b(?:ports?|sockets?|listening|bound)\b', ('net.ports',)),
    (r'\b(?:dns|resolve.*hostname|resolve.*ip)\b', ('net.dns_lookup',)),
    (r'\b(?:ping|packet loss)\b', ('net.ping',)),
    (r'\b(?:ssid|wi.?fi)\b.*\b(?:signal|strength|connected|network)\b|\bwireless ssid\b', ('net.wifi',)),
    (r'\b(?:ip address|private ip|adapters|online|connected)\b', ('net.info',)),
    (r'\b(?:throughput|bytes per second|upload|download speed)\b', ('net.throughput',)),
    (r'\b(?:audit|actions.*perform|what did you.*do|tool calls|hanni actions|what have you done)\b', ('hanni.audit_tail',)),
    (r'\b(?:permissions?|approval|allowed|boundaries|confirmation|without asking)\b', ('hanni.permissions',)),
    (r'\b(?:emergency stop|halted|are you stopped|safe mode)\b', ('hanni.stop_state',)),
    (r'\b(?:capabilities|what can you do|what.*tools|what kinds.*help|able to access)\b', ('hanni.capabilities',)),
    (r'\b(?:uuid|guid|identifier|random id)\b', ('id.generate',)),
    (r'\b(?:coin|choose randomly|pick between|choose between)\b', ('random.pick',)),
    (r'\b(?:dice|die|random.*(?:number|integer)|roll)\b', ('random.number',)),
    (r'\b(?:sha256|sha512|md5|checksum|digest)\b', ('text.hash',)),
    (r'\b(?:slug|uppercase|lowercase|title case|strip accents|normalize)\b', ('text.normalize',)),
    (r'\b(?:word count|count.*words|how many words|reading time|characters)\b', ('text.stats',)),
    (r'\b(?:convert|how many)\b.*\b(?:miles|kilometers|celsius|fahrenheit|kg|pounds|gb|mb|units)\b', ('unit.convert',)),
    (r'\b(?:calculate|work out|divided|multiplied|percent of|math)\b|\d+\s*[%+*/]\s*\d+', ('calc.evaluate',)),
    (r'\b(?:elapsed|how long ago|time since|since.*timestamp|how long has it been since)\b', ('time.elapsed',)),
    (r'\b(?:convert|timezone|time zone)\b.*\b(?:time|utc|london|york)\b|\btime\b.*\b(?:london|york|eastern.*pacific)\b', ('time.convert',)),
)
_RULES = tuple((re.compile(pattern), menu) for pattern, menu in _SOURCES)


def independent_observations(text: str) -> tuple[str, ...]:
    """Reserve separate named read operations without expanding authority."""
    text=normalize(text)
    if not re.search(r'\b(?:and|plus|also|then)\b|[;&]',text): return ()
    operations=[]
    def add(pattern,name,context=True):
        match=re.search(pattern,text) if context else None
        if match: operations.append((match.start(),name))
    add(r'\bfirewall\b','security.firewall')
    add(r'\b(?:defender|antivirus)\b','security.defender')
    repository=bool(re.search(r'\b(?:git|repo|repository|commits?|working.tree)\b',text))
    add(r'\b(?:status|uncommitted|clean|dirty)\b','git.status',repository)
    add(r'\b(?:commits?|commit history|git log)\b','git.log',repository)
    add(r'\b(?:diff|patch)\b','git.diff',repository)
    file=bool(re.search(r'\b(?:file|file path)\b',text))
    add(r'\bread\b','file.read',file)
    add(r'\b(?:metadata|size)\b','file.stat',file)
    add(r'\bcompare\b','file.compare',file)
    add(r'\b(?:foreground|active)\s+window\b','ui.active_window')
    add(r'\b(?:monitor|display)\s+configuration\b','display.info')
    ranking=bool(re.search(r'\b(?:top|largest|biggest|highest|consumers?|processes)\b',text))
    add(r'\b(?:cpu|processor)\s+consumers?\b|\btop\s+(?:cpu|processor)\b','process.top_cpu',ranking)
    add(r'\b(?:ram|memory)\s+consumers?\b|\btop\s+(?:ram|memory)\b','process.top_memory',ranking)
    add(r'\b(?:free|available|remaining)\s+(?:vram|video memory|gpu memory)\b','gpu.memory')
    add(r'\b(?:free|available|remaining)\s+(?:disk|storage|drive)\s+space\b','disk.free_space')
    names=tuple(dict.fromkeys(name for _,name in sorted(operations)))
    return names if len(names)>1 else ()


def specific_menu(text: str) -> tuple[str, ...]:
    text = normalize(text)
    # Narrow operation/object pairs take precedence over broad nouns such as
    # "task", "capacity", and "storage". They do not authorize execution.
    if re.search(r'\b(?:process|pid|program|app)\b',text) and re.search(r'\b(?:uptime|how long|since|started)\b',text):
        return ('process.uptime',)
    if (not re.search(r'\bspotify\b',text) and (
            re.search(r'\b(?:process|program|app)\s+(?:named|called)\b',text)
            or re.search(r'\b[\w-]+\.exe\b',text) and re.search(r'\b(?:cpu|processor|memory|ram|running)\b',text))):
        return ('process.find',)
    if re.search(r'\b(?:bitlocker|encryption|encrypted)\b',text): return ('security.bitlocker',)
    if re.search(r'\b(?:foreground|active)\s+window\b',text): return ('ui.active_window',)
    if re.search(r'\b(?:monitors?|displays?)\b',text) and re.search(r'\b(?:attached|configuration|resolution|metadata)\b',text):
        return ('display.info',)
    if (re.search(r'\bfile\b', text) and re.search(r'\b(?:size|metadata)\b', text)
            and not re.search(r'\b(?:compare|difference|diff|identical)\b', text)):
        return ('file.stat',)
    if re.search(r'\bfile path\b',text) and not re.search(r'\b(?:email|gmail|inbox|google|git|commits?|repository|repo|branches|staged|unstaged)\b',text):
        if re.search(r'\b(?:checksum|hash|digest)\b',text): return ('file.stat',)
        if re.search(r'\b(?:largest|biggest)\s+files\b',text): return ('disk.largest_files',)
        if re.search(r'\b(?:folders|subfolders)\b',text) and re.search(r'\b(?:largest|biggest|most)\b',text):
            return ('disk.largest_folders',)
        if re.search(r'\bempty\s+(?:folders|directories)\b',text): return ('file.empty_folders',)
        if re.search(r'\b(?:case.sensitive|literal words|occurrences)\b',text): return ('file.grep',)
        if re.search(r'\b(?:first|beginning|opening|head)\b',text): return ('file.head',)
        if re.search(r'\b(?:last|bottom|tail|end)\b',text): return ('file.tail',)
        if re.search(r'\b(?:directory listing|direct children|subfolders)\b',text): return ('file.list_dir',)
        if re.search(r'\binspect\b',text) and re.search(r'\b(?:data|contents|text)\b',text): return ('file.read',)
        if re.search(r'\bread\b|\bquote\b.*\bfile data\b',text): return ('file.read',)
    if re.search(r'\b(?:find|locate|search)\b',text) and re.search(r'\b(?:file|directory|folder)\s+(?:named|called)\b',text):
        return ('file.locate',)
    if (re.search(r'\b(?:llama|hanni|model)\b', text)
            and re.search(r'\b(?:gpu|graphics\s+card|offload(?:ed|ing)?)\b', text)
            and not re.search(r'\b(?:memory|vram|usage|utilization|top\s+processes)\b', text)):
        return ('model.status',)
    if (re.search(r'\b(?:have|got|exists?|present|mounted|which|list|show|all|every)\b|\bis there\b|\bdoes this\b', text)
            and re.search(r'\b(?:[a-z]:?\s+drive|drives|volumes)\b', text)
            and not re.search(r'\b(?:free|space|capacity|usage|full)\b', text)):
        return ('disk.usage',)
    if re.search(r'\b(?:tasks?|process(?:es)?|executable|programs?)\b', text):
        if re.search(r'\b(?:cpu|processor)\b', text) and re.search(r'\b(?:most|top|biggest|hog|using|owns|taking|burning|consum|crowd)\w*\b', text):
            return ('process.top_cpu', 'system.stats')
        if re.search(r'\b(?:gpu|vram|graphics)\b', text) and re.search(r'\b(?:most|top|biggest|hog|using|owns|taking|consum|crowd)\w*\b', text):
            return ('gpu.top_processes', 'gpu.memory')
        if re.search(r'\b(?:ram|memory)\b', text) and re.search(r'\b(?:most|top|biggest|hog|using|owns|taking|swallow|consum|crowd)\w*\b', text):
            return ('process.top_memory', 'system.stats')
        if re.search(r'\b(?:disk|drive|storage)\b', text) and re.search(r'\b(?:read|write|traffic|activity|i/o|io|hammer)\w*\b', text):
            return ('process.top_disk_io', 'system.performance')
    if (re.search(r'\b(?:disk|drive|storage|ssd|volume)\b', text)
            and re.search(r'\b(?:free|remaining|left|available|unused|headroom|room)\b', text)
            and not re.search(r'\b(?:read|write|activity|traffic|io)\w*\b', text)):
        return ('disk.free_space',)
    if re.search(r'\bc\s+(?:drive|volume)\b', text) and re.search(r'\b(?:full|filled|capacity|space)\b', text):
        return ('disk.usage',)
    if (not action_requested(text)
            and re.search(r'\b(?:power|battery|charging|charger|outlet|mains|energy)\b', text)
            and re.search(r'\b(?:performance|slow\w*|speed|sluggish|capped|constrained|bog\w*|drop\w*)\b', text)):
        return ('power.plans', 'power.battery_detail', 'system.performance')
    if (not action_requested(text) and re.search(r'\b(?:plugged in|plugged into|unplugged)\b', text)
            and re.search(r'\b(?:slow\w*|sluggish|performance|speed)\b', text)):
        return ('power.plans', 'power.battery_detail', 'system.performance')
    if (re.search(r'\b(?:network|connection|internet|wifi|wi-fi)\b', text)
            and re.search(r'\b(?:throughput|bandwidth|traffic|transfer|rate|saturat\w*|pegged|maxed|busy)\b', text)):
        return ('net.throughput', 'net.info', 'net.wifi')
    if (not action_requested(text) and re.search(r'\b(?:song|track|music)\b', text)
            and re.search(r'\b(?:my|current|playing|listening|hearing|status|which|what|name)\b', text)):
        return ('spotify.status',)
    if (re.search(r'\b(?:you|your|hanni|model|assistant|qwen)\b', text)
            and (re.search(r'\bcontext\b.*\b(?:size|window|length|capacity)\b', text)
                 or re.search(r'\b(?:quant|quantization)\b', text))):
        return ('model.status',)
    if (not action_requested(text) and re.search(r'\b(?:model|qwen|llm)\b', text)
            and re.search(r'\b(?:active|loaded|running|resident)\b', text)
            and not re.search(r'\b(?:which file contains|search inside|grep)\b', text)):
        return ('model.status',)
    for pattern, menu in _RULES:
        if not pattern.search(text):
            continue
        if menu == ('disk.usage',) and re.search(r'\b(?:cpu|processor|network|context|conversation)\b', text):
            continue
        if menu == ('disk.usage',) and re.search(r'\b(?:reads?|writes?|activity|traffic|io)\b', text):
            continue
        if menu == ('process.list',) and re.search(r'\b(?:disk|cpu|ram|memory|gpu|vram)\b', text):
            continue
        if menu == ('todo.list',) and re.search(r'\b(?:cpu|processor|ram|memory|gpu|vram|disk|process)\b', text):
            continue
        if menu == ('model.status',) and re.search(r'\b(?:files?|text|grep|vram|gpu|memory|how long|when did)\b', text):
            continue
        if menu == ('python.env_info',) and re.search(r'\b(?:as an app|version of python)\b', text):
            continue
        if menu == ('@spotify',):
            if re.search(r'\b(?:how long|when did)\b', text):
                return ('process.uptime',)
            if re.search(r'^is\b.*\b(?:running|open)\b', text):
                return ('process.find',)
            if re.search(r'^start\b.*\b(?:music|song|track|playback)\b', text):
                return ('spotify.play_pause', 'spotify.status', 'spotify.launch')
            if re.search(r'\bget\b.*\bspotify\b.*\bgoing\b', text):
                return ('spotify.play_pause', 'spotify.status', 'spotify.launch')
            for words, name in ((r'uri|spotify:', 'open_uri'), (r'volume|louder|quieter', 'volume'),
                                (r'foreground|focus|switch', 'focus'), (r'previous|back|replay|earlier|prior|return.*last', 'previous'),
                                (r'next|skip', 'next'), (r'search|find|look up', 'search'),
                (r'open|launch|start|fire up|bring up|^get\s+spotify\s+up$', 'launch'), (r'play|pause|resume', 'play_pause')):
                if re.search(r'\b(?:' + words + r')\b', text):
                    return ('spotify.play_pause', 'spotify.status', 'spotify.launch') if name == 'play_pause' else ('spotify.' + name,)
            if re.search(r'\b(?:running|open)\b', text):
                return ('process.find',)
            return ('spotify.status',)
        if menu == ('@email',):
            return ('gmail.read', 'gmail.search') if re.search(r'\b(?:latest|recent)\b', text) else (('gmail.read',) if re.search(r'\b(?:read|body|full|open|say)\b', text) else ('gmail.search',))
        if menu == ('@git',):
            for words, name in ((r'diff|patch', 'diff'), (r'branches|branch', 'branches'), (r'commits?|history|log', 'log')):
                if re.search(r'\b(?:' + words + r')\b', text):
                    return ('git.' + name,)
            return ('git.status',)
        if menu == ('@uptime',):
            return ('system.uptime',) if re.search(r'\b(?:pc|computer|laptop|machine|system)\b', text) else ('process.uptime',)
        if menu == ('process.uptime', 'process.inspect'):
            return ('process.uptime',) if re.search(r'\b(?:long|start|since)\b', text) else ('process.inspect',)
        return menu
    return ()
