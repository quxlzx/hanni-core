"""Advisory planner metadata and replaceable, deterministic local retrieval.

Capability discovery answers one question: given a goal in the owner's own
words, which registered capabilities are worth putting in front of the
Supervisor? It is retrieval only. Neither a hint word, an intent route, nor a
high score authorizes execution - the ToolRegistry's validation, permission,
confirmation, emergency-stop, and audit gates remain authoritative (D-0022).

Ranking has three deterministic layers:

1. lexical overlap against capability name, tags/aliases, description, category;
2. phrase hits, where a multi-word alias such as "what is playing" appears
   verbatim in the goal;
3. curated intent routes, which pin a well-known owner phrasing to the one
   capability that answers it, so common questions resolve to the same
   capability every time instead of drifting with wording.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Protocol

from hanni.tools.base import ToolDefinition, ToolRegistry, UnknownToolError, SideEffect
from hanni.tools.capability_metadata import metadata_for


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    name: str
    description: str
    arguments: dict[str, list[str]]
    output_contract: dict[str, str]
    risk_level: int
    permission_level: int
    confirmation_policy: str
    side_effect: SideEffect
    category: str
    tags: tuple[str, ...]
    aliases: tuple[str, ...]
    prerequisites: tuple[str, ...]
    timeout_seconds: int
    execution_class: str
    background_allowed: bool
    schema_version: int
    display_name: str
    categories: tuple[str, ...]
    argument_schema: dict
    family: str
    subfamily: str
    risk: str
    state: str
    source: str
    requires: tuple[str, ...]
    permission: str
    read_write_class: str
    priority: int
    introduced_version: str

    def to_dict(self) -> dict:
        return asdict(self)


# Retrieval hints only. Neither these words nor search results authorize execution.
_HINTS = {
    # Milestone 6 core surface
    "file.list_dir": "organize sort downloads pdf images inventory inspect folder",
    "file.search": "organize sort downloads pdf images find locate",
    "file.mkdir": "organize sort downloads pdf images create folder directory",
    "file.move": "organize sort downloads pdf images rename relocate",
    "file.read": "read reread verify notes content configuration",
    "file.write": "write record save notes edit configuration code fix",
    "file.stat": "verify exists existence destination folder directory metadata",
    "system.stats": "ram memory usage statistics current cpu gpu utilization temperature load",
    "process.stop": "stop terminate kill process pid",
    "process.top_disk_io": "disk io hammering busy process program reads writes transfer throughput",
    "powershell.run": "run execute test tests pytest debug project build fix terminal",
    # M9.2 capability expansion
    "net.info": "internet online offline connection adapter ip address network working",
    "net.wifi": "wifi wireless signal ssid weak slow bars network",
    "net.ping": "ping latency lag reachable unreachable server responds",
    "net.dns_lookup": "dns resolve hostname domain website unreachable",
    "net.ports": "port listening localhost server bound socket occupied",
    "net.throughput": "bandwidth throughput mbps speed slow network transfer",
    "disk.usage": "disk drive space storage full free gigabytes remaining",
    "disk.free_space": "space free room enough before copying large",
    "disk.folder_size": "size folder directory big large measure how much",
    "disk.largest_files": "space eating hogging biggest largest files cleanup storage",
    "disk.largest_folders": "space breakdown biggest folders where went storage",
    "disk.recycle_bin_size": "recycle bin trash deleted space",
    "disk.cleanup_temp": "clean cleanup temp temporary free space reclaim junk",
    "app.list_installed": "installed program software version have uninstall list",
    "service.list": "service services background running windows state",
    "service.control": "restart start stop service fix hung",
    "startup.list": "startup boot login launch automatically slow start",
    "system.os_info": "windows version build specs machine hostname system",
    "system.uptime": "uptime reboot restart how long running since boot",
    "process.uptime": "process running since started how long open",
    "audio.status": "volume loud sound level mute audio",
    "audio.set_volume": "volume louder quieter turn up down sound",
    "audio.mute": "mute unmute silence quiet audio",
    "media.play_pause": "play pause resume music video media playback",
    "media.next_track": "next skip track song forward media",
    "media.previous_track": "previous back track song replay media",
    "media.stop": "stop playback media",
    "display.info": "monitor display resolution refresh screen hz",
    "display.brightness": "brightness dim bright screen backlight dark",
    "spotify.status": "spotify playing song track artist music now current",
    "spotify.launch": "spotify open launch start music app",
    "spotify.play_pause": "spotify play pause resume music song",
    "spotify.next": "spotify next skip song track",
    "spotify.previous": "spotify previous back song track",
    "spotify.search": "spotify search find song album artist playlist music",
    "spotify.open_uri": "spotify link uri playlist album open play",
    "spotify.volume": "spotify volume louder quieter music too loud",
    "spotify.focus": "spotify window show switch focus",
    "file.grep": "search inside contents mention where wrote find text phrase",
    "file.head": "head first beginning preview lines file",
    "file.tail": "tail last end recent log lines errors",
    "file.compare": "compare diff difference changed identical versions verify",
    "archive.zip": "zip compress archive package folder backup send",
    "archive.unzip": "unzip extract archive decompress open",
    "archive.list": "zip archive contents inside list peek",
    "clipboard.read": "clipboard copied paste buffer what did i copy",
    "clipboard.write": "clipboard copy put paste text",
    "time.now": "time date today day now clock",
    "time.convert": "timezone convert meeting utc time difference",
    "time.elapsed": "elapsed ago since how long duration",
    "schedule.list_tasks": "scheduled task automation runs job cron schedule",
    "notify.toast": "notify notification alert popup toast tell",
    "timer.set": "timer remind reminder alarm minutes countdown later",
    "git.status": "git repo changes uncommitted dirty clean status branch",
    "git.log": "git commits history recent log what did i commit",
    "git.diff": "git diff changes patch review modified",
    "git.branches": "git branch branches current checkout",
    "python.env_info": "python venv virtualenv packages pip installed interpreter dependency",
    "project.lint": "lint ruff flake8 style errors quality check",
    "project.format": "format black reformat style tidy",
    "project.test": "test tests pytest verify pass fail suite",
    "hanni.capabilities": "capabilities abilities tools can you do help which what",
    "hanni.audit_tail": "audit log history what did you do recent actions failed",
    "hanni.stop_state": "emergency stop stopped safe mode blocked halted",
    "hanni.permissions": "permission allowed confirm risk level authority",
    "model.status": "model llm supervisor server reachable loaded slow",
    "gpu.memory": "gpu vram free headroom memory model load",
    # M9.3 capability expansion
    "calc.evaluate": "calculate math percent total sum multiply divide work out",
    "unit.convert": "convert unit miles kilometer pound kilo celsius fahrenheit gigabyte",
    "text.stats": "word count characters reading length how long text",
    "text.hash": "hash checksum sha256 md5 fingerprint digest",
    "text.normalize": "slug uppercase lowercase title case filename normalize",
    "random.pick": "random pick choose decide coin flip between options",
    "random.number": "random number dice roll between pick",
    "id.generate": "uuid guid identifier token generate random id",
    "file.recent": "recent changed modified today yesterday latest worked files",
    "file.duplicates": "duplicate copies identical same wasted space files",
    "file.composition": "types extension breakdown how many pdf inventory folder",
    "file.empty_folders": "empty folders leftover tidy cleanup",
    "file.open": "open launch show view file folder explorer",
    "power.battery_detail": "battery charge charging remaining last unplugged power",
    "power.plans": "power plan balanced performance saver mode profile",
    "power.set_plan": "power plan performance saver switch change mode",
    "power.idle_settings": "sleep screen timeout idle turn off lock",
    "power.set_idle": "sleep screen timeout awake keep stop turning off",
    "power.battery_report": "battery health wear capacity degraded report",
    "security.defender": "antivirus defender virus protection secure safe scan",
    "security.firewall": "firewall blocked inbound security network",
    "security.bitlocker": "bitlocker encryption encrypted drive secure",
    "security.updates": "update updates patch hotfix windows installed recent",
    "security.pending_reboot": "reboot restart pending required waiting update",
    "system.event_errors": "error crash event log problem wrong bluescreen why failed",
    "device.audio": "audio speaker headphones microphone output device endpoint",
    "device.bluetooth": "bluetooth paired connected headphones wireless device",
    "device.usb": "usb plugged device drive peripheral",
    "device.printers": "printer print default device",
    "device.disk_health": "disk ssd hdd health smart failing hardware drive",
    "env.list": "environment variable env config setting",
    "env.get": "environment variable value set config",
    "env.which": "which where executable path installed command resolve",
    "env.path": "path environment broken duplicate entries command",
    "env.user_folders": "downloads desktop documents onedrive home where folder path",
    "ui.windows_detailed": "window open apps visible which running have",
    "ui.minimize_all": "minimize desktop hide clear windows show",
    "ui.window_state": "minimize maximize restore window resize full screen",
    "ui.close_window": "close window quit exit shut dismiss",
    "system.performance": "slow performance health overall doing lag struggling check snapshot",
    "process.find": "process running open find pid app is",
    "note.append": "note jot write down capture record todo",
    "note.list": "note today list recorded captured read",
    "note.search": "note search find mention did",
    "note.days": "note days history when calendar",
    # Google Calendar is the sole calendar provider.
    "google_calendar.agenda": "google calendar today tomorrow week agenda schedule events meetings busy search find appointment",
    "google_calendar.next": "google calendar next upcoming meeting event appointment soon when",
    "google_calendar.list": "google calendar calendars list sources connected primary school personal",
    "google_calendar.create": "google calendar add create schedule book appointment meeting event put new",
}

# Verification and observation companions. Bounded, and they never outrank a
# primary match; they exist so a plan can prove what it changed.
_RELATED = {
    "file.write": ("file.read", "file.stat"),
    "file.mkdir": ("file.stat",),
    "file.move": ("file.stat", "file.list_dir"),
    "file.copy": ("file.stat", "file.read"),
    "file.delete": ("file.stat",),
    "folder.open": ("file.stat", "ui.active_window"),
    "app.open": ("process.list", "ui.active_window"),
    "process.stop": ("process.inspect",),
    "ui.focus_window": ("ui.active_window",),
    "archive.zip": ("file.stat", "archive.list"),
    "archive.unzip": ("file.list_dir", "archive.list"),
    "disk.cleanup_temp": ("disk.usage",),
    "disk.largest_files": ("disk.usage",),
    "service.control": ("service.list",),
    "audio.set_volume": ("audio.status",),
    "audio.mute": ("audio.status",),
    "display.brightness": ("display.info",),
    "spotify.play_pause": ("spotify.status",),
    "spotify.next": ("spotify.status",),
    "spotify.previous": ("spotify.status",),
    "spotify.open_uri": ("spotify.status",),
    "spotify.search": ("spotify.status",),
    "spotify.volume": ("spotify.status",),
    "media.play_pause": ("ui.active_window",),
    "net.ping": ("net.info",),
    "net.throughput": ("net.info",),
    "project.lint": ("git.status",),
    "project.format": ("git.diff",),
    "project.test": ("git.status",),
    "clipboard.write": ("clipboard.read",),
    "timer.set": ("time.now",),
    "service.list": ("system.uptime",),
    "file.duplicates": ("disk.usage", "file.composition"),
    "file.recent": ("file.list_dir",),
    "power.set_plan": ("power.plans",),
    "power.set_idle": ("power.idle_settings",),
    "power.battery_report": ("file.stat",),
    "ui.close_window": ("ui.windows_detailed",),
    "ui.window_state": ("ui.windows_detailed",),
    "ui.minimize_all": ("ui.windows_detailed",),
    "note.append": ("note.list",),
    "system.performance": ("system.stats",),
    "security.pending_reboot": ("system.uptime",),
    "device.disk_health": ("disk.usage",),
    "env.which": ("env.path",),
    "todo.add": ("todo.get", "time.resolve"),
    "todo.complete": ("todo.get", "todo.list"),
    "gmail.search": ("gmail.read", "google.accounts"),
    "gmail.read": ("gmail.search",),
    "google_calendar.next": ("google.accounts", "google_calendar.agenda"),
}

# Curated owner phrasings that should always resolve to one capability. Each
# entry is (compiled phrase pattern, capability name). A route adds a bounded
# boost and protects that capability from the relevance floor; it does not skip
# validation, permissions, or confirmation.
_INTENT_ROUTE_SOURCES: tuple[tuple[str, str], ...] = (
    (r"(?=.*\bgoogle\b)(?=.*\bnext\b)(?=.*\b(?:calendar|event|meeting)\b)", "google_calendar.next"),
    (r"\b(?:mark|finish|complete)\b.*\b(?:task|assignment|homework)\b", "todo.complete"),
    (r"\b(?:homework|assignment|task)s?\b.*\bdue\b|\boverdue (?:homework|assignments?|tasks?)\b", "todo.due"),
    (r"\b(?:search|find|check)\b.*\b(?:email|emails|inbox|gmail)\b", "gmail.search"),
    (r"\bread\b.*\b(?:email|gmail)\b", "gmail.read"),
    (r"\b(?:am i|are we) (?:online|connected)\b|\bis (?:the )?(?:internet|wifi|network) (?:up|down|working)\b", "net.info"),
    (r"\bwhat(?:'s| is) my ip\b|\bmy ip address\b", "net.info"),
    (r"\bwi-?fi\b.*\b(?:signal|strength|weak|bars|ssid)\b|\b(?:signal|strength)\b.*\bwi-?fi\b", "net.wifi"),
    (r"\bwhat (?:wi-?fi|network) am i (?:on|connected to)\b", "net.wifi"),
    (r"\bping\b", "net.ping"),
    (r"\b(?:what(?:'s| is) )?(?:running|listening) on port\b|\bport \d{2,5}\b", "net.ports"),
    (r"\bhow (?:fast|slow) is my (?:internet|network|connection)\b|\bbandwidth\b", "net.throughput"),
    (r"\b(?:disk|drive|storage) (?:space|full|usage)\b|\bhow much (?:disk )?space\b|\bc drive\b", "disk.usage"),
    (r"\bwhat(?:'s| is) (?:taking up|eating|using) (?:my |up )?(?:disk|drive|storage|space)\b|\bbiggest files\b|\blargest files\b", "disk.largest_files"),
    (r"\bwhere did my (?:disk )?space go\b|\bbiggest folders?\b", "disk.largest_folders"),
    (r"\bhow big is\b.*\bfolder\b|\bsize of (?:the |my )?(?:folder|directory)\b", "disk.folder_size"),
    (r"\bclean(?: up)? (?:my )?temp\b|\bfree up (?:disk )?space\b|\btemporary files\b", "disk.cleanup_temp"),
    (r"\brecycle bin\b", "disk.recycle_bin_size"),
    (r"\b(?:do i have|is)\b.*\binstalled\b|\bwhat programs? (?:are|do i have) installed\b|\bwhat version of\b", "app.list_installed"),
    (r"\bstarts? (?:up )?with (?:my |the )?(?:pc|computer|windows)\b|\bstartup (?:programs?|items?|apps?)\b", "startup.list"),
    (r"\bis (?:the )?[\w.-]+ service running\b|\blist (?:my |the )?services\b", "service.list"),
    (r"\brestart the [\w.-]+ service\b|\b(?:start|stop) the [\w.-]+ service\b", "service.control"),
    (r"\bhow long has (?:my|this) (?:pc|computer|machine|laptop) been (?:on|up|running)\b|\buptime\b|\bwhen did i last (?:reboot|restart)\b", "system.uptime"),
    (r"\bwhat (?:version of )?windows\b|\bmy specs\b|\bsystem info\b", "system.os_info"),
    (r"\b(?:turn|set) (?:the |it |my )?(?:volume|sound)\b|\bturn it (?:up|down)\b|\b(?:louder|quieter)\b", "audio.set_volume"),
    (r"\b(?:mute|unmute|silence)\b", "audio.mute"),
    (r"\bhow loud\b|\bwhat(?:'s| is) my volume\b", "audio.status"),
    (r"\b(?:dim|brighten)\b|\bbrightness\b|\bscreen is too (?:dark|bright)\b", "display.brightness"),
    (r"\bwhat resolution\b|\brefresh rate\b|\bmy monitors?\b", "display.info"),
    (r"\bspotify\b.*\b(?:playing|song|track)\b|\bwhat song is (?:this|playing)\b|\bwhat(?:'s| is) playing\b", "spotify.status"),
    (r"\bopen spotify\b|\bstart spotify\b|\blaunch spotify\b", "spotify.launch"),
    (r"\b(?:pause|resume|play)\b.*\b(?:spotify|music|song)\b|\bspotify\b.*\b(?:pause|resume)\b", "spotify.play_pause"),
    (r"\b(?:skip|next)\b.*\b(?:song|track)\b|\bnext song\b", "spotify.next"),
    (r"\b(?:previous|last|go back a)\b.*\b(?:song|track)\b", "spotify.previous"),
    (r"\b(?:search|find|look ?up|put on)\b.*\bspotify\b|\bspotify\b.*\bsearch\b", "spotify.search"),
    (r"\bspotify\b.*\b(?:too loud|volume|quieter|louder)\b", "spotify.volume"),
    (r"\b(?:pause|play)\b(?!.*\bspotify\b)(?!.*\bsong\b)\s*(?:the )?(?:music|video|it)?\b", "media.play_pause"),
    (r"\b(?:search|find|grep|look) (?:in|inside|through)\b|\bwhere did i (?:write|mention|say)\b|\bwhich file (?:mentions|contains)\b", "file.grep"),
    (r"\b(?:tail|last lines|end of)\b.*\blog\b|\bwhat does the log say\b", "file.tail"),
    (r"\b(?:diff|compare)\b.*\bfiles?\b|\bare (?:these|those) (?:two )?files? the same\b|\bwhat changed between\b", "file.compare"),
    (r"\bzip\b|\bcompress\b|\barchive\b(?!.*\bextract\b)", "archive.zip"),
    (r"\bunzip\b|\bextract\b.*\b(?:zip|archive)\b", "archive.unzip"),
    (r"\bwhat(?:'s| is) (?:in|inside) (?:this|the) zip\b", "archive.list"),
    (r"\bwhat did i copy\b|\bmy clipboard\b|\bread the clipboard\b", "clipboard.read"),
    (r"\bcopy (?:that|this|it) to (?:my )?clipboard\b|\bput (?:that|this|it) on (?:my )?clipboard\b", "clipboard.write"),
    (r"\bwhat time is it\b|\bwhat(?:'s| is) (?:today|the date|the day)\b|\bcurrent date\b", "time.now"),
    (r"\bwhat time is that in\b|\btime ?zone\b|\bin utc\b", "time.convert"),
    (r"\bhow long ago\b|\btime since\b", "time.elapsed"),
    (r"\bscheduled tasks?\b|\bwhat runs automatically\b", "schedule.list_tasks"),
    (r"\b(?:set|start) a timer\b|\bremind me in\b|\bin \d+ minutes? remind\b", "timer.set"),
    (r"\bnotify me\b|\bsend me a notification\b|\bpop ?up\b", "notify.toast"),
    (r"\bis (?:my|the) repo (?:clean|dirty)\b|\buncommitted\b|\bgit status\b|\bwhat did i change\b", "git.status"),
    (r"\brecent commits?\b|\bcommit history\b|\bwhat did i commit\b|\bgit log\b", "git.log"),
    (r"\bgit diff\b|\bshow me my changes\b|\breview my diff\b", "git.diff"),
    (r"\bwhat branch am i on\b|\blist (?:the )?branches\b", "git.branches"),
    (r"\bwhich python\b|\bmy (?:venv|virtual ?env)\b|\bis [\w.-]+ (?:package )?installed in python\b|\bpip list\b", "python.env_info"),
    (r"\blint\b|\bstyle errors?\b|\bruff\b|\bflake8\b", "project.lint"),
    (r"\b(?:re)?format (?:my )?(?:code|project)\b|\bblack\b", "project.format"),
    (r"\brun (?:the )?tests?\b|\bpytest\b|\bdo the tests pass\b", "project.test"),
    (r"\bwhat can you do\b|\bwhat (?:tools|capabilities)\b|\bcan you\b.*\?|\bwhich tool\b", "hanni.capabilities"),
    (r"\bwhat did you (?:just )?do\b|\byour audit\b|\bwhat failed\b", "hanni.audit_tail"),
    (r"\bare you stopped\b|\bemergency stop\b|\bsafe mode\b", "hanni.stop_state"),
    (r"\bare you allowed\b|\bdo you need permission\b", "hanni.permissions"),
    (r"\bis the model (?:up|running|loaded)\b|\bwhy are you slow\b", "model.status"),
    (r"\bhow much vram\b|\bvram free\b|\bcan i load another model\b", "gpu.memory"),
    (r"\bhow much (?:ram|memory)\b|\bmemory usage\b|\bcpu usage\b", "system.stats"),
    (r"\bbattery\b", "system.battery"),
    # M9.3 routes
    (r"\bhow (?:much|many)\b.*\b(?:is|are)\b.*[\d]|\bwhat(?:'s| is) \d|\b\d+\s*%\s*of\b|\bcalculate\b|\bwork out\b", "calc.evaluate"),
    (r"\bconvert\b.*\bto\b|\bhow many (?:km|kilometers?|miles?|pounds?|kilos?|kg|gb|mb) \b|\bin (?:fahrenheit|celsius)\b", "unit.convert"),
    (r"\bhow many words\b|\bword count\b|\bhow long is (?:this|that) (?:text|document|note)\b", "text.stats"),
    (r"\bflip a coin\b|\bpick (?:one|for me|between)\b|\bchoose (?:for me|between)\b|\bdecide between\b", "random.pick"),
    (r"\broll (?:a )?(?:dice|die|d\d+)\b|\brandom number\b|\bpick a number\b", "random.number"),
    (r"\b(?:generate|give me) (?:a |an )?(?:uuid|guid|random id)\b", "id.generate"),
    (r"\bwhat did i work on\b|\bwhat (?:files? )?changed (?:recently|today|yesterday)\b|\brecent files\b", "file.recent"),
    (r"\bduplicate (?:files?|copies)\b|\bsame file twice\b|\bany duplicates\b", "file.duplicates"),
    (r"\bhow many (?:pdfs?|images?|photos?|videos?|files?) (?:are )?(?:in|under)\b|\bwhat (?:types|kinds) of files\b", "file.composition"),
    (r"\bempty folders?\b", "file.empty_folders"),
    (r"\bopen (?:that|this|the) (?:file|folder|document)\b", "file.open"),
    (r"\bhow long (?:will|does) (?:my )?battery\b|\bam i charging\b|\bbattery (?:time )?(?:left|remaining)\b", "power.battery_detail"),
    (r"\bpower plan\b|\bpower mode\b|\bbattery saver mode\b|\bhigh performance mode\b", "power.plans"),
    (r"\b(?:switch|change|set) (?:to )?(?:high performance|balanced|power saver|battery saver)\b", "power.set_plan"),
    (r"\bwhen does my screen turn off\b|\bsleep timeout\b|\bidle timeout\b", "power.idle_settings"),
    (r"\bkeep (?:my )?(?:pc|computer|screen|laptop) awake\b|\bstop my screen (?:from )?turning off\b|\b(?:change|set) (?:the )?sleep timeout\b", "power.set_idle"),
    (r"\bbattery health\b|\bis my battery (?:healthy|worn|degraded)\b", "power.battery_report"),
    (r"\bantivirus\b|\bdefender\b|\bam i protected\b|\bvirus protection\b", "security.defender"),
    (r"\bfirewall\b", "security.firewall"),
    (r"\bbitlocker\b|\bis my (?:drive|disk) encrypted\b", "security.bitlocker"),
    (r"\bwindows updates?\b|\brecent (?:updates|patches)\b|\bwhen did windows (?:last )?update\b", "security.updates"),
    (r"\bdo i need to (?:reboot|restart)\b|\breboot pending\b|\brestart pending\b", "security.pending_reboot"),
    (r"\bwhat went wrong\b|\bany errors? (?:recently|today)\b|\bwhy did (?:my )?(?:pc|computer|it) crash\b|\bevent log\b|\bblue ?screen\b", "system.event_errors"),
    (r"\bare my headphones connected\b|\bbluetooth\b", "device.bluetooth"),
    (r"\baudio devices?\b|\bmy speakers?\b|\bsound devices?\b", "device.audio"),
    (r"\bwhat(?:'s| is) plugged in\b|\busb devices?\b", "device.usb"),
    (r"\bprinters?\b", "device.printers"),
    (r"\bis my (?:ssd|hdd|disk|drive) (?:healthy|failing|dying)\b|\bdisk health\b|\bsmart status\b", "device.disk_health"),
    (r"\bwhere is (?:my )?(?:downloads?|desktop|documents)\b|\bmy (?:downloads?|documents) (?:folder|path)\b", "env.user_folders"),
    (r"\bis \w+ on (?:my )?path\b|\bwhere is (?:git|python|node|npm|pip)\b|\bdo i have the \w+ command\b", "env.which"),
    (r"\bwhat(?:'s| is) on my path\b|\bis my path broken\b", "env.path"),
    (r"\benvironment variables?\b|\benv var\b", "env.list"),
    (r"\bwhat do i have open\b|\bwhat (?:apps|windows) are open\b|\blist my windows\b", "ui.windows_detailed"),
    (r"\bshow (?:me )?(?:my )?desktop\b|\bminimize everything\b|\bclear my screen\b", "ui.minimize_all"),
    (r"\b(?:maximize|minimize|restore) (?:that|this|the) window\b", "ui.window_state"),
    (r"\bclose (?:that|this|the) window\b|\bquit that app\b", "ui.close_window"),
    (r"\bhow is my (?:pc|computer|machine|laptop) doing\b|\bwhy is my (?:pc|computer|laptop) slow\b|\bis everything (?:ok|okay|fine)\b|\bcheck my system\b", "system.performance"),
    (r"\bis \w+(?:\.exe)? (?:running|open)\b|\bfind (?:that|the) process\b", "process.find"),
    (r"\b(?:create|make|add)\s+(?:a\s+|an\s+|new\s+)*(?:folder|directory)\b", "file.mkdir"),
    (r"\bjot (?:this|that) down\b|\bmake a note\b|\bwrite (?:this|that) down\b|\bnote to self\b", "note.append"),
    (r"\bwhat did i note\b|\bread (?:me )?my notes\b|\bmy notes (?:for )?today\b", "note.list"),
    (r"\bwhat(?:'s| is)? (?:on|happening)(?: today| tomorrow)?\b(?!.*\b(?:tv|spotify|playing)\b)|\bwhat do i have (?:on )?(?:today|tomorrow)\b|\bmy schedule\b|\bon my calendar\b", "google_calendar.agenda"),
    (r"\bwhat(?:'s| is) on this week\b|\bmy week\b|\bagenda\b|\bhow busy am i\b|\bnext (?:few )?days\b", "google_calendar.agenda"),
    (r"\bnext meeting\b|\bwhat(?:'s| is) next\b|\bnext (?:event|appointment)\b|\bhow long until my next\b|\banything starting soon\b|\bcoming up (?:soon|shortly)\b", "google_calendar.next"),
    (r"\bwhen (?:is|am i seeing)\b.*\b(?:appointment|meeting|call)?\b.*|\bdo i have anything with\b", "google_calendar.agenda"),
    (r"\bwhere is my calendar (?:stored|kept)\b|\bwhat calendars do you read\b|\blist my calendars\b", "google_calendar.list"),
    (r"\bdid i note\b|\bsearch my notes\b|\bfind (?:that|the) note\b", "note.search"),
)
_INTENT_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), name) for pattern, name in _INTENT_ROUTE_SOURCES)

# Vocabulary bridges between how the owner speaks and how capabilities are
# tagged. Expansion is additive and never removes an original term.
_SYNONYMS = {
    "ram": ("memory",),
    "utilization": ("usage",),
    "temp": ("temperature",),
    "vram": ("gpu", "memory"),
    "wifi": ("wireless", "network"),
    "internet": ("network", "online"),
    "web": ("network",),
    "pc": ("computer", "system"),
    "laptop": ("computer", "system"),
    "machine": ("computer", "system"),
    "directory": ("folder",),
    "dir": ("folder",),
    "song": ("music", "track"),
    "tune": ("music", "track"),
    "album": ("music",),
    "playlist": ("music",),
    "volume": ("audio", "sound"),
    "loud": ("volume", "audio"),
    "quiet": ("volume", "audio"),
    "screen": ("display",),
    "monitor": ("display",),
    "app": ("program", "application"),
    "program": ("app", "application"),
    "repo": ("git", "repository"),
    "commit": ("git",),
    "branch": ("git",),
    "log": ("logs",),
    "trash": ("recycle",),
    "space": ("disk", "storage"),
    "gb": ("disk", "storage"),
    "boot": ("startup",),
    "reboot": ("uptime", "restart"),
    "zip": ("archive",),
    "clock": ("time",),
    "today": ("date", "time"),
    "reminder": ("timer", "notify"),
    "remind": ("timer", "notify"),
    "note": ("notes",),
    "jot": ("note",),
    "antivirus": ("defender", "security"),
    "virus": ("defender", "security"),
    "headphones": ("bluetooth", "audio"),
    "printer": ("print",),
    "sleep": ("idle", "timeout"),
    "awake": ("idle", "timeout"),
    "duplicate": ("duplicates", "copies"),
    "slow": ("performance",),
    "crash": ("error", "event"),
    "uuid": ("identifier", "id"),
    "maths": ("math", "calculate"),
    "calculate": ("math",),
    "meeting": ("calendar", "event"),
    "appointment": ("calendar", "event"),
    "schedule": ("calendar",),
    "agenda": ("calendar", "schedule"),
    "booked": ("calendar", "busy"),
}


def describe(definition: ToolDefinition) -> CapabilityDescriptor:
    side_effect = definition.side_effect
    if side_effect is None:
        side_effect = ("destructive" if definition.risk_level >= 3 else
                       "read" if definition.permission_level == definition.risk_level == 0 else
                       "reversible_write" if definition.name.startswith("file.") else "external_action")
    args = {key: [kind.__name__ for kind in (value if isinstance(value, tuple) else (value,))]
            for key, value in definition.input_schema.items()}
    policy = "runtime profile check"
    if definition.risk_level >= 3:
        policy += "; always explicit confirmation"
    if definition.requires_confirmation_if:
        policy += "; dynamic argument-dependent confirmation"
    return CapabilityDescriptor(
        definition.name, definition.description, args, dict(definition.output_schema),
        definition.risk_level, definition.permission_level, policy, side_effect,
        definition.name.split(".")[0], definition.tags,
        definition.aliases + tuple(_HINTS.get(definition.name, "").split()),
        definition.prerequisites, definition.timeout_seconds,
        definition.execution_class, definition.background_allowed, definition.schema_version,
        definition.display_name or definition.name.replace('.', ' ').replace('_', ' ').title(),
        definition.categories or (definition.name.split('.')[0],), definition.argument_schema(),
        **metadata_for(definition, side_effect),
    )


def capability_catalog(registry: ToolRegistry) -> tuple[CapabilityDescriptor, ...]:
    return tuple(describe(item) for item in registry.definitions())


@dataclass(frozen=True, slots=True)
class CapabilityMatch:
    capability: CapabilityDescriptor
    score: float
    matched_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"capability": self.capability.to_dict(), "score": self.score,
                "matched_terms": list(self.matched_terms)}


class CapabilityDiscovery(Protocol):
    def search(self, goal: str, *, limit: int = 8) -> tuple[CapabilityMatch, ...]: ...


_STOP = set("a an the my me you it in into of to and then that this for with please hanni current".split())
_PHRASE_BOOST = 8
_ROUTE_BOOST = 24
_PATH_BOOST = 6

# A goal that names a concrete filename or path is talking about the filesystem,
# even when a word in it (a "note", a "log") also names another capability
# family. Generic words like "folder" are deliberately not a path signal - they
# already score lexically, and treating them as context drowns out telemetry.
_PATH_SIGNAL = re.compile(r"[a-z0-9_-]+\.[a-z0-9]{1,5}\b|[a-z]:\\|(?:^|\s)[/~][\w./-]+")
_PATH_CATEGORIES = frozenset({"file", "archive"})


@dataclass(frozen=True, slots=True)
class CapabilityFamilyScope:
    """A coarse semantic slice of the capability registry.

    Family selection happens *before* individual capability ranking.  It is a
    retrieval boundary only: it never authorizes execution and never chooses a
    final tool for the model.
    """

    name: str
    prefixes: tuple[str, ...] = ()
    capability_ids: frozenset[str] = frozenset()

    def allows(self, capability_name: str) -> bool:
        return (
            capability_name in self.capability_ids
            or any(capability_name.startswith(prefix) for prefix in self.prefixes)
        )


_CAPABILITY_FAMILIES: dict[str, CapabilityFamilyScope] = {
    # Resource-specific computer families deliberately exclude unrelated local
    # domains (Calendar, Spotify, archives, UI, security, etc.) before ranking.
    "computer.memory": CapabilityFamilyScope(
        "computer.memory",
        capability_ids=frozenset({
            "process.top_memory", "process.find", "process.inspect", "process.list",
            "system.stats", "system.performance", "model.status",
        }),
    ),
    "computer.cpu": CapabilityFamilyScope(
        "computer.cpu",
        capability_ids=frozenset({
            "process.top_cpu", "process.find", "process.inspect", "process.list",
            "system.stats", "system.performance", "model.status",
        }),
    ),
    "computer.gpu": CapabilityFamilyScope(
        "computer.gpu",
        prefixes=("gpu.",),
        capability_ids=frozenset({
            "system.stats", "system.performance", "model.status",
            "process.find", "process.inspect",
        }),
    ),
    "computer.storage": CapabilityFamilyScope(
        "computer.storage",
        prefixes=("disk.",),
        capability_ids=frozenset({
            "device.disk_health", "process.top_disk_io", "system.performance",
        }),
    ),
    "computer.network": CapabilityFamilyScope(
        "computer.network",
        prefixes=("net.",),
        capability_ids=frozenset({"security.firewall", "system.performance"}),
    ),
    "computer.performance": CapabilityFamilyScope(
        "computer.performance",
        capability_ids=frozenset({
            "system.performance", "system.stats", "system.event_errors",
            "process.top_cpu", "process.top_memory", "process.top_disk_io",
            "gpu.memory", "gpu.top_processes", "model.status",
            "disk.usage", "device.disk_health", "net.throughput",
            "startup.list", "service.list",
        }),
    ),
    "calendar": CapabilityFamilyScope("calendar", prefixes=("google_calendar.",), capability_ids=frozenset({"google.accounts"})),
    "files": CapabilityFamilyScope("files", prefixes=("file.", "folder.", "archive."), capability_ids=frozenset({"env.user_folders", "disk.folder_size", "disk.free_space"})),
    "email": CapabilityFamilyScope("email", prefixes=("gmail.", "email."), capability_ids=frozenset({"google.accounts"})),
    "media": CapabilityFamilyScope("media", prefixes=("spotify.", "media.", "audio.")),
    "hanni": CapabilityFamilyScope("hanni", prefixes=("hanni.", "model.")),
    "time": CapabilityFamilyScope("time", prefixes=("time.", "timer.")),
}


_FAMILY_ROUTE_SOURCES: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(pattern), family) for pattern, family in (
    # Specific resource families precede broad performance language.
    (r"\b(?:vram|gpu|graphics\s+(?:card|memory)|video\s+memory)\b", "computer.gpu"),
    (r"\b(?:ram|memory)\b", "computer.memory"),
    (r"\b(?:cpu|processor)\b", "computer.cpu"),
    (r"\b(?:disk|ssd|hdd|storage|drive)\b|\b(?:free|low|out of)\s+space\b", "computer.storage"),
    (r"\b(?:network|internet|wi-?fi|latency|ping|dns|bandwidth|throughput)\b", "computer.network"),
    (r"(?=.*\b(?:pc|computer|machine|laptop|windows|system)\b)(?=.*\b(?:slow|sluggish|dragging|laggy|lagging|crawl|crawling|stutter|stuttering|performance|healthy|normal|normally|issues)\b)", "computer.performance"),
    (r"\b(?:calendar|agenda|appointment|meeting)\b", "calendar"),
    (r"\b(?:email|emails|gmail|inbox)\b", "email"),
    (r"\b(?:file|files|folder|folders|directory|directories|downloads|desktop|documents)\b", "files"),
    (r"\b(?:spotify|song|music|track|playlist|audio|volume)\b", "media"),
    (r"\b(?:hanni|model|llm)\b", "hanni"),
    (r"\b(?:time|date|clock|timezone|timer)\b", "time"),
))


def capability_family(goal: str) -> CapabilityFamilyScope | None:
    """Classify a natural-language goal into one high-confidence family.

    Returning ``None`` preserves the old full-catalog retrieval behavior.  The
    family is deliberately coarse and is applied before lexical ranking.
    """
    normalized = _normalized_goal(goal)
    for pattern, family_name in _FAMILY_ROUTE_SOURCES:
        if pattern.search(normalized):
            return _CAPABILITY_FAMILIES[family_name]
    return None


@dataclass(frozen=True, slots=True)
class DiagnosticSubintentScope:
    """A diagnostic retrieval scope inside a computer capability family.

    Sub-intents are intentionally *not* answers and do not choose or execute a
    tool.  They only remove unrelated diagnostic capabilities before lexical
    ranking so the model receives a cleaner MCP menu.
    """

    name: str
    family_name: str
    prefixes: tuple[str, ...] = ()
    capability_ids: frozenset[str] = frozenset()
    candidate_bundle: tuple[str, ...] = ()
    default_tool_budget: int = 4

    def allows(self, capability_name: str) -> bool:
        return (
            capability_name in self.capability_ids
            or any(capability_name.startswith(prefix) for prefix in self.prefixes)
        )


_DIAGNOSTIC_SUBINTENTS: dict[str, DiagnosticSubintentScope] = {
    "general_slowdown": DiagnosticSubintentScope(
        "general_slowdown",
        "computer.performance",
        capability_ids=frozenset({
            "system.performance", "system.stats", "system.event_errors",
            "process.top_cpu", "process.top_memory", "process.top_disk_io",
            "gpu.memory", "gpu.top_processes", "model.status",
            "disk.usage", "device.disk_health", "net.throughput",
            "startup.list", "service.list",
        }),
        candidate_bundle=(
            "system.performance", "system.stats", "process.top_cpu",
            "process.top_memory", "process.top_disk_io", "gpu.top_processes",
        ),
        default_tool_budget=6,
    ),
    "memory_pressure": DiagnosticSubintentScope(
        "memory_pressure",
        "computer.memory",
        capability_ids=frozenset({
            "process.top_memory", "process.find", "process.inspect",
            "system.stats", "system.performance", "model.status",
        }),
        candidate_bundle=(
            "process.top_memory", "system.stats", "system.performance", "model.status",
        ),
        default_tool_budget=3,
    ),
    "cpu_pressure": DiagnosticSubintentScope(
        "cpu_pressure",
        "computer.cpu",
        capability_ids=frozenset({
            "process.top_cpu", "process.find", "process.inspect",
            "system.stats", "system.performance", "model.status",
        }),
        candidate_bundle=(
            "process.top_cpu", "system.stats", "system.performance", "model.status",
        ),
        default_tool_budget=3,
    ),
    "gpu_vram": DiagnosticSubintentScope(
        "gpu_vram",
        "computer.gpu",
        prefixes=("gpu.",),
        capability_ids=frozenset({
            "system.stats", "system.performance", "model.status",
            "process.find", "process.inspect",
        }),
        candidate_bundle=(
            "gpu.top_processes", "gpu.memory", "system.stats", "model.status",
        ),
        default_tool_budget=4,
    ),
    "disk_io": DiagnosticSubintentScope(
        "disk_io",
        "computer.storage",
        capability_ids=frozenset({
            "process.top_disk_io", "disk.usage", "disk.free_space",
            "device.disk_health", "system.performance", "system.stats",
        }),
        candidate_bundle=(
            "process.top_disk_io", "disk.usage", "device.disk_health",
            "system.performance", "system.stats",
        ),
        default_tool_budget=5,
    ),
    "network": DiagnosticSubintentScope(
        "network",
        "computer.network",
        prefixes=("net.",),
        capability_ids=frozenset({"security.firewall", "system.performance"}),
        candidate_bundle=(
            "net.info", "net.throughput", "net.wifi", "net.ping", "net.dns_lookup",
        ),
        default_tool_budget=5,
    ),
    "thermal_power": DiagnosticSubintentScope(
        "thermal_power",
        "computer.performance",
        prefixes=("power.",),
        capability_ids=frozenset({
            "system.stats", "system.performance", "system.battery",
        }),
        candidate_bundle=(
            "system.stats", "system.performance", "system.battery",
            "power.battery_detail", "power.plans",
        ),
        default_tool_budget=5,
    ),
    "windows_errors": DiagnosticSubintentScope(
        "windows_errors",
        "computer.performance",
        capability_ids=frozenset({
            "system.event_errors", "security.pending_reboot",
            "security.updates", "security.defender", "service.list",
            "system.os_info", "system.uptime",
        }),
        candidate_bundle=(
            "system.event_errors", "security.pending_reboot", "security.updates", "service.list",
        ),
        default_tool_budget=4,
    ),
    "model_runtime": DiagnosticSubintentScope(
        "model_runtime",
        "computer.performance",
        capability_ids=frozenset({
            "model.status", "system.stats", "system.performance",
            "gpu.memory", "gpu.top_processes", "process.find",
            "process.inspect", "process.list", "net.ports",
        }),
        candidate_bundle=(
            "model.status", "system.stats", "gpu.memory", "gpu.top_processes",
            "process.find", "net.ports",
        ),
        default_tool_budget=6,
    ),
}


_DIAGNOSTIC_SUBINTENT_SOURCES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), name) for pattern, name in (
        # Specific resources precede broad slowdown language.  GPU/VRAM comes
        # before generic memory so "GPU memory" is never treated as system RAM.
        (r"\bvram\b|(?=.*\b(?:gpu|graphics(?:\s+card)?|video(?:\s+card)?)\b)(?=.*\b(?:usage|load|memory|ram|vram|process(?:es)?|programs?|apps?|busy|pressure|using|eating|hogging|hammering|maxing|hot|temperature|temp|acting\s+up)\b)", "gpu_vram"),
        (r"(?=.*\b(?:game|gaming|fps|frames?|textures?)\b)(?=.*\b(?:lag(?:ging)?|stutter(?:s|ing)?|slow|chok(?:e|ing)|drop(?:ping)?|dies?|tanks?|bad|cooked|worse)\b)", "gpu_vram"),
        (r"\b(?:ram|memory)\b", "memory_pressure"),
        (r"\b(?:cpu|processor)\b", "cpu_pressure"),
        (r"\b(?:disk|ssd|hdd|drive)\b.*\b(?:i/?o|busy|usage|active|activity|slow|latency|reads?|writes?|using|thrashing|100\s*%|bottleneck|pinned)\b|\b(?:disk\s+i/?o|disk\s+queue)\b", "disk_io"),
        (r"\b(?:network|internet|wi-?fi|latency|ping|dns|bandwidth|throughput|packet\s+loss)\b", "network"),
        (r"\b(?:thermal|temperature|temps?|overheat(?:ing)?|too\s+hot|running\s+hot|fans?\s+(?:are\s+)?(?:so\s+)?(?:loud|spinning|ramping)|power\s+draw|battery\s+drain)\b|(?=.*\b(?:battery|unplugged|charger)\b)(?=.*\b(?:slow|sluggish|crawling|performance|tanks)\b)", "thermal_power"),
        (r"\b(?:event\s+log|event\s+viewer|blue\s*screen|bsod|crash(?:ed|ing)?|system\s+errors?|windows\s+(?:event\s+)?errors?|reboot\s+pending|restart\s+pending)\b", "windows_errors"),
        (r"\b(?:llama(?:\.cpp)?|llama-server|qwen|inference|model\s+server|llm\s+server)\b|\b(?:model|llm)\b.*\b(?:running|loaded|reachable|server|slow|status|stuck|responding)\b", "model_runtime"),
        (r"(?=.*\b(?:pc|computer|machine|laptop|windows|system|everything|apps?|files?|folders?|desktop|blender|render(?:ing)?|this\s+thing|opening\s+stuff|background\s+thing|it\s+down\s+idle|something)\b)(?=.*\b(?:slow|sluggish|dragging|laggy|lagging|crawl|crawling|stutter|stuttering|performance|healthy|normal|normally|issues|cooked|chugging|freeze|freezing|hanging|locking|struggling|unusable|pauses?|tanks?|forever|ages|bogging|maxed|wrong)\b)|\b(?:everything|this\s+thing)\b.*\b(?:slow|sluggish|laggy|lagging|freezing|locking|chugging)\b|\bwhy does it feel sluggish\b", "general_slowdown"),
    )
)


def diagnostic_subintent(goal: str) -> DiagnosticSubintentScope | None:
    """Return the best high-confidence diagnostic search scope, if any.

    This classifier only narrows MCP retrieval.  It does not pick a final tool,
    execute a capability, or infer a diagnosis.
    """
    normalized = _normalized_goal(goal)
    for pattern, intent_name in _DIAGNOSTIC_SUBINTENT_SOURCES:
        if pattern.search(normalized):
            return _DIAGNOSTIC_SUBINTENTS[intent_name]
    return None


_DIRECT_RESOURCE_CULPRIT = re.compile(
    r"(?:\b(?:what|which|who)\b.*\b(?:process|app|program)\b.*\b(?:using|eating|hogging|hammering|taking|maxing)\b"
    r"|\b(?:what(?:'s| is)|who(?:'s| is))\b.*\b(?:using|eating|hogging|hammering|taking|maxing)\b)",
)
_MULTI_RESOURCE_USAGE = re.compile(
    r"(?=.*\b(?:cpu|processor)\b)(?=.*\b(?:ram|memory)\b)(?:.*\b(?:gpu|graphics|vram)\b)?"
)
_GPU_CULPRIT = re.compile(
    r"\b(?:what|which|who)\b.*\b(?:using|eating|hogging|hammering|taking|maxing)\b.*\b(?:vram|gpu|graphics(?:\s+card)?)\b"
    r"|\b(?:what(?:'s| is)|who(?:'s| is))\b.*\b(?:using|eating|hogging|hammering|taking)\b.*\b(?:vram|gpu)\b"
)
_GPU_MEMORY_STATUS = re.compile(
    r"\b(?:vram|gpu\s+memory)\b.*\b(?:free|left|usage|used|headroom|full|available|enough)\b"
    r"|\b(?:how much|show|check)\b.*\b(?:vram|gpu\s+memory)\b"
)
_WIFI_STATUS = re.compile(r"\bwi-?fi\b.*\b(?:signal|strength|weak|connected|ssid|network)\b|\bwhat\s+wi-?fi\b")
_NETWORK_THROUGHPUT = re.compile(r"\b(?:throughput|bandwidth|traffic|internet\s+slow|network\s+slow|connection\s+slow)\b")
_MODEL_STATUS = re.compile(
    r"\b(?:is|check|show|what)\b.*\b(?:model|llm|qwen|hanni)\b.*\b(?:running|loaded|up|status)\b"
    r"|\b(?:model|llm)\s+status\b"
)


def diagnostic_candidate_bundle(goal: str) -> tuple[str, ...]:
    """Return a curated MCP candidate menu for a diagnostic goal.

    Bundles only control retrieval.  They never call a capability or infer the
    answer.  Query-specific ordering keeps obvious status/culprit questions
    small and gives the resident model the most useful menu first.
    """
    scope = diagnostic_subintent(goal)
    if scope is None:
        return ()
    normalized = _normalized_goal(goal)

    if _MULTI_RESOURCE_USAGE.search(normalized) and re.search(r"\b(?:usage|utilization|using|stats?|percent|current)\b", normalized):
        return ("system.stats", "process.top_cpu", "process.top_memory", "gpu.memory")
    if scope.name == "gpu_vram":
        if _GPU_CULPRIT.search(normalized):
            return ("gpu.top_processes", "gpu.memory", "system.stats")
        if _GPU_MEMORY_STATUS.search(normalized):
            return ("gpu.memory", "system.stats", "model.status")
    if scope.name == "network":
        if _WIFI_STATUS.search(normalized):
            return ("net.wifi", "net.info", "net.throughput")
        if _NETWORK_THROUGHPUT.search(normalized):
            return ("net.throughput", "net.info", "net.wifi", "net.ping")
    return scope.candidate_bundle


def diagnostic_tool_budget(goal: str, *, ceiling: int = 8) -> int | None:
    """Return the diagnostic MCP menu size for ``goal``.

    The result is a retrieval budget, not an execution plan.  Specific culprit
    and status questions deliberately expose fewer tools; broad diagnoses expose
    enough cross-resource evidence for the resident model to choose from.
    """
    scope = diagnostic_subintent(goal)
    if scope is None:
        return None
    normalized = _normalized_goal(goal)
    budget = scope.default_tool_budget

    if _MULTI_RESOURCE_USAGE.search(normalized) and re.search(r"\b(?:usage|utilization|using|stats?|percent|current)\b", normalized):
        budget = 1
    elif scope.name in {"memory_pressure", "cpu_pressure"} and _DIRECT_RESOURCE_CULPRIT.search(normalized):
        budget = 2
    elif scope.name == "gpu_vram":
        if _GPU_CULPRIT.search(normalized):
            budget = 2
        elif _GPU_MEMORY_STATUS.search(normalized):
            budget = 1
    elif scope.name == "network":
        if _WIFI_STATUS.search(normalized):
            budget = 1
        elif _NETWORK_THROUGHPUT.search(normalized):
            budget = 3
    elif scope.name == "windows_errors" and re.search(r"\b(?:event\s+log|blue\s*screen|bsod|crash|errors?)\b", normalized):
        budget = 2
    elif scope.name == "model_runtime" and _MODEL_STATUS.search(normalized) and not re.search(r"\b(?:slow|stuck|problem|issue|down|unreachable)\b", normalized):
        budget = 1
    return max(1, min(int(ceiling), budget))


def _tokens(text: str) -> set[str]:
    return {word[:-1] if word.endswith("s") and len(word) > 3 else word
            for word in re.findall(r"[a-z0-9]+", text.casefold()) if word not in _STOP}


def _expanded_tokens(text: str) -> set[str]:
    terms = _tokens(text)
    extra: set[str] = set()
    for term in terms:
        extra.update(_tokens(" ".join(_SYNONYMS.get(term, ()))))
    return terms | extra


def _normalized_goal(goal: str) -> str:
    from hanni.tools.routing_intents import normalize
    return normalize(goal)


# Negative routing signals prevent incidental natural-language words from
# surfacing semantically unrelated tools.  These are retrieval-only guards;
# they neither choose nor execute a capability.
_SYSTEM_MEMORY_SIGNAL = re.compile(r"\b(?:ram|system\s+memory|memory\s+(?:usage|pressure|use))\b")
_GPU_MEMORY_SIGNAL = re.compile(
    r"\bvram\b|\b(?:gpu|graphics(?:\s+card)?|video(?:\s+card)?)\b.{0,28}\b(?:memory|ram)\b"
    r"|\b(?:memory|ram)\b.{0,28}\b(?:gpu|graphics(?:\s+card)?|video(?:\s+card)?)\b"
)
_INCIDENTAL_NOW_SIGNAL = re.compile(r"\b(?:right\s+now|rn|currently|at\s+the\s+moment)\b")
_EXPLICIT_TIME_SIGNAL = re.compile(
    r"\b(?:what\s+time|time\s+is\s+it|current\s+time|local\s+time|clock|timezone|time\s+zone|"
    r"what\s+date|date\s+is\s+it|what\s+day|today(?:'s)?\s+date|timer)\b"
)
_WINDOWS_PERFORMANCE_SIGNAL = re.compile(
    r"\bwindows\b.*\b(?:slow|sluggish|dragging|laggy|lagging|crawl|crawling|stutter|stuttering|performance|healthy|normal|normally|issues)\b"
    r"|\b(?:slow|sluggish|laggy|lagging|crawl|crawling|stutter|stuttering)\b.*\bwindows\b"
)
_EXPLICIT_WINDOW_UI_SIGNAL = re.compile(
    r"\b(?:active|current|focused|foreground|open)\s+windows?\b|\bwindow\s+(?:title|focus|list)\b"
)


def _routing_signal_adjustment(goal: str, capability_name: str) -> float | None:
    """Return a retrieval score adjustment, or ``None`` to suppress a tool.

    The adjustment is deliberately narrow.  It corrects known lexical traps
    without turning retrieval into a second decision-maker: the LLM still
    chooses from the resulting MCP menu.
    """
    normalized = _normalized_goal(goal)

    # System RAM and GPU memory are different resources.  Plain RAM/memory
    # language should make process memory the obvious candidate and should not
    # leak GPU-memory tools unless the owner explicitly mentions VRAM/GPU memory.
    if _SYSTEM_MEMORY_SIGNAL.search(normalized) and not _GPU_MEMORY_SIGNAL.search(normalized):
        if capability_name.startswith("gpu."):
            return None
        if capability_name == "process.top_memory":
            return 80.0
        if capability_name == "system.stats":
            return 30.0

    # "right now" is normally a recency modifier, not a request for the clock.
    if (_INCIDENTAL_NOW_SIGNAL.search(normalized) and not _EXPLICIT_TIME_SIGNAL.search(normalized)
            and capability_name.startswith(("time.", "timer."))):
        return None

    # "Windows feels slow" refers to the operating system, not the active UI
    # window.  UI tools remain eligible when the user explicitly asks about a
    # window/focus/title.
    if (_WINDOWS_PERFORMANCE_SIGNAL.search(normalized) and not _EXPLICIT_WINDOW_UI_SIGNAL.search(normalized)
            and capability_name.startswith("ui.")):
        return None

    return 0.0


def intent_routes(goal: str) -> tuple[str, ...]:
    """Return capability names pinned to this goal by a curated intent route."""
    normalized = _normalized_goal(goal)
    names: list[str] = []
    for pattern, name in _INTENT_ROUTES:
        if name not in names and pattern.search(normalized):
            names.append(name)
    return tuple(names)


class LocalCapabilityDiscovery:
    """Deterministic lexical + phrase + intent-route capability retrieval."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def _index(self):
        """Share a metadata/token index across all planners for this registry."""
        cached = getattr(self.registry, '_discovery_cache', None)
        if cached is not None and cached[0] == self.registry.revision:
            return cached[1:]
        entries, postings = {}, {}
        for cap in capability_catalog(self.registry):
            argument_text = ' '.join(str(rule.get('description', ''))
                                     for rule in cap.argument_schema.get('properties', {}).values()
                                     if isinstance(rule, dict))
            fields = [(_tokens(cap.name), 6), (_tokens(' '.join(cap.aliases + cap.tags)), 4),
                      (_tokens(cap.description), 1), (_tokens(' '.join(cap.categories)), 1),
                      (_tokens(cap.display_name + ' ' + argument_text), 1)]
            entries[cap.name] = (cap, fields)
            for terms, _ in fields:
                for term in terms: postings.setdefault(term, set()).add(cap.name)
        self.registry._discovery_cache = (self.registry.revision, entries, postings)
        return entries, postings

    def search(self, goal: str, *, limit: int = 8, extensions_only: bool = False) -> tuple[CapabilityMatch, ...]:
        if not 1 <= limit <= 32:
            raise ValueError("capability limit must be 1..32")
        terms = _expanded_tokens(goal)
        normalized = _normalized_goal(goal)
        routed = intent_routes(goal)
        family = capability_family(goal)
        diagnostic = diagnostic_subintent(goal)
        diagnostic_bundle = diagnostic_candidate_bundle(goal)
        # A high-confidence diagnostic sub-intent is narrower than the coarse
        # family classifier, so its family becomes the retrieval boundary.
        if diagnostic is not None:
            family = _CAPABILITY_FAMILIES.get(diagnostic.family_name, family)
        path_context = bool(_PATH_SIGNAL.search(normalized))
        scores: dict[str, CapabilityMatch] = {}
        entries, postings = self._index()
        if extensions_only:
            # The same cached lexical index retrieves imported tools. Built-in
            # family/intent reservations continue unchanged for ordinary search.
            entries = {name: entry for name, entry in entries.items() if name.startswith('mcp.')}
            family, diagnostic, diagnostic_bundle, routed = None, None, (), ()

        # Family-first retrieval: unrelated families never enter the ranking
        # pool.  If classification is not confident, preserve full-catalog
        # behavior rather than guessing a family.
        eligible = set(entries)
        if family is not None:
            eligible = {name for name in entries if family.allows(name)}
        if diagnostic is not None:
            eligible = {name for name in eligible if diagnostic.allows(name)}

        candidates = (set(routed) | set(diagnostic_bundle)) & eligible
        for term in terms:
            candidates.update(set(postings.get(term, ())) & eligible)

        # Positive negative-signal companions can enter the candidate set even
        # when their metadata has no literal token overlap (for example plain
        # "RAM" should still strongly surface process.top_memory).
        for name in eligible:
            adjustment = _routing_signal_adjustment(goal, name)
            if adjustment is not None and adjustment > 0:
                candidates.add(name)

        for name in candidates & eligible:
            adjustment = _routing_signal_adjustment(goal, name)
            if adjustment is None:
                continue
            cap, fields = entries[name]
            matched: set[str] = set()
            score = adjustment
            if adjustment:
                matched.add("routing signal")
            for tokens, weight in fields:
                overlap = terms & tokens
                score += len(overlap) * weight
                matched |= overlap
            for alias in cap.aliases:
                if " " in alias and alias.casefold() in normalized:
                    score += _PHRASE_BOOST
                    matched.add(alias)
            # A generic single-word hit ("folder") is not filename context; the
            # boost needs the capability to already match the goal on two terms.
            if path_context and cap.category in _PATH_CATEGORIES and len(matched) >= 2:
                score += _PATH_BOOST
                matched.add("filesystem context")
            if cap.name in routed:
                score += _ROUTE_BOOST - routed.index(cap.name)
                matched.add("intent route")
            if cap.name in diagnostic_bundle:
                # Curated diagnostic bundles shape the menu, not the answer.
                # The boost keeps bundle members ahead of weak lexical noise
                # while preserving lexical/intent-route ordering within it.
                score += 1000.0 - (diagnostic_bundle.index(cap.name) * 100.0)
                matched.add("diagnostic bundle")
            if score:
                scores[cap.name] = CapabilityMatch(cap, score, tuple(sorted(matched)))
        if scores:
            floor = max(match.score for match in scores.values()) * 0.2
            scores = {name: match for name, match in scores.items()
                      if match.score >= floor or name in routed}
        # Verification companions remain bounded and do not drown out primary matches.
        ranked = sorted(scores.values(), key=lambda m: (-m.score, m.capability.name))
        for match in ranked[:limit]:
            for name in _RELATED.get(match.capability.name, ()):
                if (name not in scores
                        and (family is None or family.allows(name))
                        and (diagnostic is None or diagnostic.allows(name))):
                    try:
                        scores[name] = CapabilityMatch(describe(self.registry.get(name)), 0.5, ("verification companion",))
                    except UnknownToolError:
                        pass
        return tuple(sorted(scores.values(), key=lambda m: (-m.score, m.capability.name))[:limit])

    def best_match(self, goal: str) -> CapabilityMatch | None:
        """Return the single most relevant capability, or None when nothing matches."""
        matches = self.search(goal, limit=1)
        return matches[0] if matches else None
