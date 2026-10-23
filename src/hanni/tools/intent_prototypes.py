"""Small deterministic intent prototypes used only for weak MCP retrieval.

The prototypes are operation descriptions, not benchmark phrases. They do not
execute tools or grant permissions; the MCP host still applies its registry,
action allowlist, date resolver, and menu ceiling.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Prototype:
    name: str
    family: str
    examples: tuple[str, ...]
    anchors: tuple[frozenset[str], ...]
    menu: tuple[str, ...]
    minimum: float = .48


@dataclass(frozen=True)
class PrototypeMatch:
    name: str
    menu: tuple[str, ...]
    confidence: float
    margin: float
    family: str


@dataclass(frozen=True)
class PrototypeCandidate:
    name: str
    family: str
    score: float
    similarity: float
    anchor_boost: float
    matched_anchors: int
    total_anchors: int
    eligible: bool


_ALIASES = {
    'processor':'cpu', 'cycles':'cpu',
    'ram':'memory', 'mem':'memory',
    'ssd':'disk', 'hdd':'disk', 'drive':'disk', 'storage':'disk',
    'files':'file', 'folders':'file', 'folder':'file',
    'document':'file', 'documents':'file',
    'charger':'battery', 'unplugged':'battery', 'unplugging':'battery', 'wall':'battery',
    'graphics':'gpu', 'frames':'gpu', 'fps':'gpu', 'textures':'gpu',
    'temperature':'temp', 'temperatures':'temp', 'temps':'temp', 'hot':'temp',
    'slowly':'slow', 'sluggish':'slow', 'crawls':'slow', 'crawling':'slow',
    'laggy':'slow', 'lagging':'slow', 'choppy':'slow', 'hesitates':'slow',
    'heavy':'slow', 'stuttering':'slow', 'struggling':'slow', 'capped':'slow', 'hangs':'slow',
    'anything':'everything',
    'hammering':'hog', 'thrashing':'hog', 'chewing':'hog', 'eating':'hog',
    'hitting':'hog', 'hogging':'hog', 'maxed':'hog', 'pinned':'hog',
    'usage':'usage', 'utilization':'usage', 'load':'usage', 'percentage':'percent',
    'copying':'copy', 'stutter':'slow',
    'apps':'app', 'application':'app', 'applications':'app', 'program':'app',
    'launch':'open', 'start':'open', 'boot':'open', 'bring':'open', 'run':'open',
    'song':'music', 'track':'music', 'playlist':'music', 'playback':'music',
    'playing':'music', 'spotify':'music',
    'advance':'next', 'skip':'next', 'rewind':'previous', 'back':'previous', 'before':'previous',
    'scheduled':'calendar', 'appointment':'calendar', 'appointments':'calendar',
    'booked':'calendar', 'plans':'calendar', 'event':'calendar', 'events':'calendar',
    'class':'calendar', 'classes':'calendar',
    'soonest':'next', 'first':'next', 'upcoming':'next',
    'permitted':'permission', 'allowed':'permission', 'authority':'permission',
    'permissions':'permission', 'rules':'permission',
    'clock':'time',
}
_STOP = {'a','an','the','is','are','i','my','me','you','your','can','could','would',
         'please','do','does','of','for','to','in','on','at','with','and','it',
         'this','that','now','rn','right','current','tell','show','check','give',
         'hey','what','whats','how','why','who','which','something'}
_APPS = {
    'visual studio code':'Visual Studio Code', 'vs code':'Visual Studio Code',
    'vscode':'Visual Studio Code', 'code':'Visual Studio Code',
    'discord':'Discord', 'disc':'Discord', 'spotify':'Spotify',
    'chrome':'Chrome', 'steam':'Steam', 'powershell':'PowerShell', 'pwsh':'PowerShell',
}


def concepts(text: str) -> frozenset[str]:
    words = re.findall(r"[a-z]+", text.casefold().replace("'", ''))
    terms = {_ALIASES.get(word, word) for word in words if word not in _STOP}
    if 'music' in terms and 'on' in words and 'playback' in words:
        terms.add('play')
    if 'music' in terms and 'stop' in words and any(word in words for word in ('song','track')):
        terms.add('pause')
    if 'music' in terms and any(word in words for word in ('what','whats','which','tell','show')) and not {'open','next','previous','pause','play'} & terms:
        terms.add('status')
    return frozenset(terms)


PROTOTYPES = (
    Prototype('app_open','applications',('open an application','launch a program','bring an app up',
              'run a program','put an app on screen','get an application running',
              'have a program ready','make an app available','fire an app up'),
              (frozenset({'open'}),frozenset({'app'})),('app.open',)),
    Prototype('cpu_contributor','diagnostics',('cpu hog process','which app uses cpu','process chewing cpu cycles'),
              (frozenset({'cpu'}),frozenset({'hog','process','app','who'})),('process.top_cpu','system.stats')),
    Prototype('cpu_usage','diagnostics',('current cpu usage','processor load','cpu percent'),
              (frozenset({'cpu'}),frozenset({'usage','percent','status'})),('system.stats',)),
    Prototype('memory_contributor','diagnostics',('which app uses memory','memory hog process','who is eating ram'),
              (frozenset({'memory'}),frozenset({'hog','process','app','who'})),('process.top_memory','system.stats')),
    Prototype('memory_usage','diagnostics',('current memory usage','ram percent','how full is memory'),
              (frozenset({'memory'}),frozenset({'usage','percent','full','status'})),('system.stats',)),
    Prototype('system_usage','diagnostics',('system resource usage','overall computer load','current machine stats'),
              (frozenset({'system','computer','machine'}),frozenset({'usage','stats','load'})),('system.stats',)),
    Prototype('disk_io','diagnostics',('disk activity high','files loading slowly','disk process hog',
              'reads and writes activity','file access is stalling','directory browsing is delayed',
              'file loads slowly'),
              (frozenset({'disk','file','reads','writes'}),frozenset({'hog','slow','activity','reads','writes','copy','loading'})),
              ('process.top_disk_io','system.performance')),
    Prototype('power_slowdown','diagnostics',('computer slow on battery','performance worse unplugged',
              'off charger sluggish','portable power reduces performance'),
              (frozenset({'battery'}),frozenset({'slow','performance','power'})),
              ('power.plans','power.battery_detail','system.performance')),
    Prototype('gpu_pressure','diagnostics',('game frames dropping','gpu load high','graphics slow after loading textures'),
              (frozenset({'gpu','vram','game'}),frozenset({'slow','hog','usage','load','full'})),
              ('gpu.memory','gpu.top_processes','system.stats')),
    Prototype('temperatures','diagnostics',('read cpu gpu temperatures','is computer hot','system temperature status'),
              (frozenset({'temp'}),),('system.stats',)),
    Prototype('general_slowdown','diagnostics',('computer feels slow','everything feels slow',
              'desktop stutters','check overall machine performance','computer responsiveness is poor'),
              (frozenset({'slow','performance','usage','hog'}),frozenset({'computer','pc','machine','desktop','everything','overall','system'})),
              ('system.performance','system.stats','process.top_cpu','process.top_memory','process.top_disk_io','gpu.top_processes')),
    Prototype('spotify_status','media',('what music is playing','music status','current song'),
              (frozenset({'music'}),frozenset({'status','what','current','playing'})),('spotify.status',)),
    Prototype('spotify_next','media',('next music track','advance music playlist','skip spotify song'),
              (frozenset({'music'}),frozenset({'next'})),('spotify.next',)),
    Prototype('spotify_previous','media',('previous music track','rewind spotify playlist','song before this'),
              (frozenset({'music'}),frozenset({'previous'})),('spotify.previous',)),
    Prototype('spotify_play','media',('play spotify music','resume music playback','music playing again'),
              (frozenset({'music'}),frozenset({'play','resume','again'})),
              ('spotify.play_pause','spotify.status','spotify.launch')),
    Prototype('spotify_pause','media',('pause spotify music','stop the current song','pause music for a minute'),
              (frozenset({'music'}),frozenset({'pause','stop'})),
              ('spotify.play_pause','spotify.status')),
    Prototype('calendar_next','calendar',('next calendar event','upcoming appointment','soonest scheduled meeting'),
              (frozenset({'calendar'}),frozenset({'next','soon'})),('google_calendar.next',)),
    Prototype('calendar_agenda','calendar',('calendar plans tomorrow','appointments on friday','what is booked tonight'),
              (frozenset({'calendar'}),frozenset({'today','tomorrow','tmr','tonight','friday','saturday','sunday','monday','tuesday','wednesday','thursday'})),
              ('google_calendar.agenda',)),
    Prototype('calendar_availability','calendar',('am i free this evening','is there an opening tonight',
              'do i have time tomorrow','is my schedule clear on friday',
              'is there a gap in my day','can another activity fit on my calendar'),
              (frozenset({'free','opening','time','clear','gap','available','fit','room','squeeze','packed'}),frozenset({'today','tomorrow','tonight','evening',
              'monday','tuesday','wednesday','thursday','friday','saturday','sunday'})),
              ('google_calendar.agenda',), .48),
    Prototype('file_search','files',('find a file by name','search downloads for pdf','look for project document','where is project file'),
              (frozenset({'find','search','look','where','locate'}),frozenset({'file','pdf','document','download','desktop','spreadsheet','report'})),
              ('file.search',)),
    Prototype('permission_question','permissions',('am i allowed to stop a process','what permissions do you have','safety rules for actions'),
              (frozenset({'permission'}),),('hanni.permissions',)),
    Prototype('time_now','time',('local time here','clock check','current time'),
              (frozenset({'time'}),),('time.now',)),
    Prototype('model_placement','model',('where is hanni running','which gpu runs the model','model runtime placement'),
              (frozenset({'hanni','model'}),frozenset({'where','running','gpu','placement'})),('model.status',)),
    Prototype('model_context','model',('how much conversation can hanni remember at once',
              'what context capacity does the model have','how large is your context window'),
              (frozenset({'context','conversation'}),frozenset({'hanni','model','your','capacity','window'})),
              ('model.status',), .56),
)


def app_entity(text: str) -> str | None:
    lower = text.casefold()
    for alias, name in sorted(_APPS.items(), key=lambda pair: -len(pair[0])):
        if re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', lower):
            return name
    return None


def _feature(text: str) -> tuple[frozenset[str], frozenset[str]]:
    terms = concepts(text)
    clean = ' '.join(sorted(terms))
    return terms, frozenset(clean[i:i+3] for i in range(max(0, len(clean)-2)))


_EXAMPLE_FEATURES = {example: _feature(example) for intent in PROTOTYPES for example in intent.examples}


def _similarity_features(query: tuple[frozenset[str], frozenset[str]],
                         example: tuple[frozenset[str], frozenset[str]]) -> float:
    left,tri_left = query
    right,tri_right = example
    common = len(left & right)
    token = 2 * common / (len(left)+len(right)) if left and right else 0
    trigram = 2 * len(tri_left & tri_right) / (len(tri_left)+len(tri_right)) if tri_left and tri_right else 0
    return .72*token + .28*trigram


def rank_intents(text: str) -> tuple[PrototypeCandidate, ...]:
    """Score every safe intent candidate, including ones with missing anchors.

    Anchors supply evidence; they are no longer a prerequisite for lexical
    comparison. An action still needs an exact known app entity, and permission
    questions retain their explicit safety boundary.
    """
    query_features = _feature(text)
    terms = query_features[0]
    entity = app_entity(text)
    if entity:
        terms = terms | {'app'}
    rows = []
    for intent in PROTOTYPES:
        matched = sum(bool(terms & group) for group in intent.anchors)
        eligible = bool(terms)
        if intent.name == 'app_open':
            eligible = bool(entity) and not bool({'command', 'script', 'shell'} & terms)
            eligible &= not bool(re.match(r'^\s*(?:how|why|when|what)\b', text, re.I))
        elif intent.name == 'permission_question':
            eligible = 'permission' in terms
        elif intent.name == 'calendar_next':
            eligible = 'calendar' in terms or bool(re.search(
                r'\bnext\s+(?:event|meeting|appointment|class)\b', text, re.I))
        elif intent.name == 'temperatures':
            eligible = bool(re.search(r'\b(?:temperatures?|temps|hot|heat)\b', text, re.I)
                            or ('temp' in terms and terms & {'cpu', 'gpu', 'pc', 'computer', 'system'}))
        elif intent.name == 'time_now':
            eligible = not bool(re.search(r'\b(?:that|convert|from|since|ago)\b', text, re.I))
        elif intent.name == 'spotify_play':
            eligible = not bool(terms & {'next', 'previous'})
        if intent.family == 'media':
            # "go back" or "play" alone has no unique media target.
            eligible = eligible and 'music' in terms

        # Compare operation meaning, then add the evidence from anchors. The
        # application entity stands in for the generic noun in app prototypes.
        best = max(_similarity_features(query_features, _EXAMPLE_FEATURES[example])
                   for example in intent.examples)
        if intent.name == 'app_open' and entity:
            canonical_app = text
            for alias in sorted(_APPS, key=len, reverse=True):
                canonical_app = re.sub(r'(?<!\w)' + re.escape(alias) + r'(?!\w)',
                                       'app', canonical_app, flags=re.I)
            canonical_features = _feature(canonical_app)
            best = max(best, max(_similarity_features(canonical_features, _EXAMPLE_FEATURES[example])
                                 for example in intent.examples))
        boost = .08 if matched == len(intent.anchors) else .035 * matched
        if intent.name == 'app_open' and entity:
            boost += .07
        score = min(1.0, best + boost)
        if (intent.name == 'model_context' and 'context' in terms
                and terms & {'size', 'window', 'length', 'capacity', 'tokens'}
                and re.search(r'\b(?:you|your|hanni|model|assistant|qwen)\b', text, re.I)):
            score = max(score, .72)
        if (intent.name == 'calendar_availability' and matched == len(intent.anchors)
                and (re.search(r'\b(?:i|my|me)\b', text, re.I)
                     or re.search(r'\b(?:free\s+(?:hour|time)|(?:today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+free)\b', text, re.I))):
            score = max(score, .64)
        if matched == len(intent.anchors):
            if intent.name == 'app_open' and 'open' in terms and entity:
                score = max(score, .72)
            if intent.name in {'disk_io', 'power_slowdown', 'temperatures', 'file_search'}:
                score = max(score, .70)
            if intent.name == 'general_slowdown':
                score = max(score, .60)
            if intent.name == 'system_usage':
                score = max(score, .68)
            if intent.name in {'memory_usage', 'cpu_usage'}:
                score = max(score, .68)
        rows.append(PrototypeCandidate(intent.name, intent.family, round(score, 4),
                                       round(best, 4), round(boost, 4), matched,
                                       len(intent.anchors), eligible))
    return tuple(sorted(rows, key=lambda row: row.score, reverse=True))


def match_intent(text: str, *, minimum_margin: float = .08) -> PrototypeMatch | None:
    by_name = {intent.name: intent for intent in PROTOTYPES}
    candidates = [(row.score, by_name[row.name]) for row in rank_intents(text)
                  if row.eligible and row.score >= max(by_name[row.name].minimum,
                    .58 if row.matched_anchors < row.total_anchors else 0)]
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0], reverse=True)
    score, winner = candidates[0]
    runner = candidates[1][0] if len(candidates)>1 else 0.0
    margin = score-runner
    if margin < minimum_margin:
        if len(candidates)>1 and winner.family == candidates[1][1].family == 'diagnostics':
            return PrototypeMatch('diagnostic_ambiguous',('system.performance','system.stats','process.top_cpu',
                'process.top_memory','process.top_disk_io','gpu.top_processes'),score,margin,'diagnostics')
        return None
    if winner.name == 'app_open' and app_entity(text) == 'Spotify':
        return PrototypeMatch('app_open',('spotify.launch','app.open'),score,margin,winner.family)
    return PrototypeMatch(winner.name,winner.menu,score,margin,winner.family)
