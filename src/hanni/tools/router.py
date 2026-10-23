"""Deterministic one-step voice router for local Windows tools.

M7.3 deliberately routes machine-state questions to measured local tools instead
of letting the conversational model guess about CPU, RAM, GPU, battery, files,
or the active window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hanni.tools.base import ToolRequest


@dataclass(frozen=True, slots=True)
class VoiceToolMatch:
    request: ToolRequest
    intent: str


class VoiceToolRouter:
    _FOLDER_PATHS = {
        "download": "~/Downloads",
        "downloads": "~/Downloads",
        "desktop": "~/Desktop",
        "document": "~/Documents",
        "documents": "~/Documents",
    }

    def route(self, text: str) -> VoiceToolMatch | None:
        raw = text.strip()
        normalized = re.sub(r"\s+", " ", raw.lower()).strip(" .?!")
        if not normalized:
            return None

        # Preserve the requested object before broad application/telemetry rules.
        folder = re.fullmatch(r'(?:open|launch)\s+(?:the |my )?(downloads?|desktop|documents?)(?:\s+folder)?', normalized)
        if folder:
            return VoiceToolMatch(ToolRequest('folder.open', {'path':self._FOLDER_PATHS[folder.group(1)]}, source='voice'), 'open_folder')
        memory = re.search(r'\bhow much (?:ram|memory) (?:(?P<before>[\w.-]+) is|is (?P<after>[\w.-]+)) using\b', normalized)
        if memory:
            name=memory.group('before') or memory.group('after')
            if name not in {'i','we','you','it','computer','system'}:
                return VoiceToolMatch(ToolRequest('process.find', {'name':name}, source='voice'), 'process_memory')

        # Foreground-window metadata is authoritative Windows state and does not
        # require multimodal inference.
        if re.search(r"\b(?:active|current|foreground)\s+window\b", normalized):
            return VoiceToolMatch(ToolRequest("ui.active_window", {}, source="voice"), "active_window")

        # Battery questions must never be guessed by the LLM.  Keep explicit
        # screen/page wording out of this one-step system route so M7 can answer
        # from visible evidence instead.  Natural owner shorthand such as
        # "What's my battery?" and "How much battery do I have?" should still
        # resolve to measured local telemetry.
        battery_on_screen = bool(
            re.search(r"\bbattery\b", normalized)
            and re.search(r"\b(?:shown|visible|displayed|on|in)\b.*\b(?:page|screen)\b|\b(?:page|screen)\b.*\bbattery\b", normalized)
        )
        battery_question = bool(
            re.search(r"\bbattery\b", normalized)
            and (
                re.search(r"\b(?:percent|percentage|left|remaining|level|status|charge|charged)\b", normalized)
                or re.search(r"\bwhat(?:'s| is)\s+(?:my|the|this\s+computer(?:'s)?)\s+battery\b", normalized)
                or re.search(r"\bhow\s+much\s+battery\b", normalized)
                or re.search(r"\b(?:check|show|tell\s+me)\b.*\b(?:my\s+)?battery\b", normalized)
                or normalized in {"battery", "my battery", "battery status"}
            )
        )
        if battery_question and not battery_on_screen:
            return VoiceToolMatch(ToolRequest("system.battery", {}, source="voice"), "battery_status")

        # Per-process resource questions. Handle natural wording such as
        # "what's eating my RAM" or "what is being used most by my CPU".
        top_words = r"(?:most|highest|top|biggest|maximum|max|eating|hogging|taking|bottom|using\s+the\s+most|using\s+most|being\s+used\s+most)"
        if re.search(rf"\b{top_words}\b.*\b(?:ram|memory)\b|\b(?:ram|memory)\b.*\b{top_words}\b", normalized):
            return VoiceToolMatch(ToolRequest("process.top_memory", {"limit": 5}, source="voice"), "process_top_memory")
        if re.search(rf"\b{top_words}\b.*\bcpu\b|\bcpu\b.*\b{top_words}\b", normalized):
            return VoiceToolMatch(ToolRequest("process.top_cpu", {"limit": 5}, source="voice"), "process_top_cpu")
        if re.search(rf"\b{top_words}\b.*\b(?:gpu|vram)\b|\b(?:gpu|vram)\b.*\b{top_words}\b", normalized):
            return VoiceToolMatch(ToolRequest("gpu.top_processes", {"limit": 5}, source="voice"), "gpu_top_processes")

        if re.search(r"\bhow much\b.*\b(?:ram|memory|cpu|gpu)\b", normalized):
            return VoiceToolMatch(ToolRequest("system.stats", {}, source="voice"), "system_stats")

        # Broader forms that do not necessarily contain the word "most".
        if re.search(r"\bwhat(?:'s| is)?\s+(?:using|eating|hogging)\s+(?:up\s+)?(?:my\s+)?(?:ram|memory)\b", normalized):
            return VoiceToolMatch(ToolRequest("process.top_memory", {"limit": 5}, source="voice"), "process_top_memory")
        if re.search(r"\bwhat(?:'s| is)?\s+(?:using|eating|hogging)\s+(?:up\s+)?(?:my\s+)?cpu\b", normalized):
            return VoiceToolMatch(ToolRequest("process.top_cpu", {"limit": 5}, source="voice"), "process_top_cpu")
        if re.search(r"\bwhat(?:'s| is)?\s+(?:using|eating|hogging)\s+(?:up\s+)?(?:my\s+)?(?:gpu|vram)\b", normalized):
            return VoiceToolMatch(ToolRequest("gpu.top_processes", {"limit": 5}, source="voice"), "gpu_top_processes")

        # Whisper occasionally substitutes words such as "bottom" for "most".
        # If an utterance clearly asks what is using a named resource, prefer
        # measured process telemetry instead of letting the LLM guess.
        if re.search(r"\b(?:what|which|who|using|used|eating|hogging|taking|bottom|biggest)\b", normalized):
            if re.search(r"\b(?:ram|memory)\b", normalized) and re.search(r"\b(?:using|used|eating|hogging|taking|bottom|biggest|most|top|highest)\b", normalized):
                return VoiceToolMatch(ToolRequest("process.top_memory", {"limit": 5}, source="voice"), "process_top_memory")
            if re.search(r"\bcpu\b", normalized) and re.search(r"\b(?:using|used|eating|hogging|taking|bottom|biggest|most|top|highest)\b", normalized):
                return VoiceToolMatch(ToolRequest("process.top_cpu", {"limit": 5}, source="voice"), "process_top_cpu")
            if re.search(r"\b(?:gpu|vram)\b", normalized) and re.search(r"\b(?:using|used|eating|hogging|taking|bottom|biggest|most|top|highest)\b", normalized):
                return VoiceToolMatch(ToolRequest("gpu.top_processes", {"limit": 5}, source="voice"), "gpu_top_processes")

        if re.search(r"\b(?:cpu|memory|ram|gpu)\b.*\b(?:usage|use|using)\b", normalized) or normalized in {"system stats", "computer stats"}:
            return VoiceToolMatch(ToolRequest("system.stats", {}, source="voice"), "system_stats")

        if re.search(r"\b(?:list|show)\b.*\bprocesses\b", normalized) or re.search(r"\bwhat\b.*\b(?:programs|processes)\b.*\brunning\b", normalized):
            return VoiceToolMatch(ToolRequest("process.list", {"limit": 15}, source="voice"), "process_list")

        # Natural directory-listing forms such as "what's in my Downloads folder"
        # and "can you list what is in my download folders".  In these forms
        # "folder" describes the location, not a request to filter only folders.
        folder_match = re.search(
            r"\b(?:list|show)(?:\s+me)?\b.*\bwhat(?:'s|\s+is)?\s+(?:in|inside|under)\s+(?:my\s+)?(downloads?|desktop|documents?)(?:\s+folders?)?\b",
            normalized,
        )
        if folder_match:
            folder = folder_match.group(1)
            return VoiceToolMatch(ToolRequest("file.list_dir", {"path": self._FOLDER_PATHS[folder], "limit": 50, "kind": "all"}, source="voice"), "list_folder")
        folder_match = re.search(
            r"\bwhat(?:'s|\s+is)\s+(?:in|inside)\s+(?:my\s+)?(downloads?|desktop|documents?)(?:\s+folders?)?\b",
            normalized,
        )
        if folder_match:
            folder = folder_match.group(1)
            return VoiceToolMatch(ToolRequest("file.list_dir", {"path": self._FOLDER_PATHS[folder], "limit": 50, "kind": "all"}, source="voice"), "list_folder")

        folder_match = re.search(
            r"\b(?:list|show|what(?:'s| is)?)\b.*\b(files?|folders?)\b.*\b(?:in|inside|under)\s+(?:my\s+)?(downloads?|desktop|documents?)\b",
            normalized,
        )
        if folder_match:
            item_word, folder = folder_match.groups()
            kind = "folder" if item_word.startswith("folder") else "all"
            return VoiceToolMatch(ToolRequest("file.list_dir", {"path": self._FOLDER_PATHS[folder], "limit": 50, "kind": kind}, source="voice"), "list_folder")
        folder_match = re.search(r"\blist\s+(?:my\s+)?(downloads?|desktop|documents?)(?:\s+folder)?\b", normalized)
        if folder_match:
            folder = folder_match.group(1)
            return VoiceToolMatch(ToolRequest("file.list_dir", {"path": self._FOLDER_PATHS[folder], "limit": 50, "kind": "all"}, source="voice"), "list_folder")

        # Folder creation is a real validated tool action. Support both
        # "create a folder called X in Downloads" and location-first wording.
        mkdir_match = re.search(
            r"\b(?:create|make)\s+(?:a\s+)?folder\s+(?:called|named)\s+([^\\/:*?\"<>|]+?)\s+(?:in|inside|under)\s+(?:my\s+)?(downloads?|desktop|documents?)(?:\s+folders?)?\s*[.!?]*$",
            raw,
            re.IGNORECASE,
        )
        if mkdir_match:
            name = mkdir_match.group(1).strip(" ,.!?")
            folder = mkdir_match.group(2).lower()
            return VoiceToolMatch(
                ToolRequest("file.mkdir", {"path": f"{self._FOLDER_PATHS[folder]}/{name}"}, source="voice"),
                "create_folder",
            )
        mkdir_match = re.search(
            r"\b(?:create|make)\s+(?:a\s+)?folder\s+(?:in|inside|under)\s+(?:my\s+)?(downloads?|desktop|documents?)(?:\s+folders?)?\s+(?:called|named)\s+([^\\/:*?\"<>|]+?)\s*[.!?]*$",
            raw,
            re.IGNORECASE,
        )
        if mkdir_match:
            folder = mkdir_match.group(1).lower()
            name = mkdir_match.group(2).strip(" ,.!?")
            return VoiceToolMatch(
                ToolRequest("file.mkdir", {"path": f"{self._FOLDER_PATHS[folder]}/{name}"}, source="voice"),
                "create_folder",
            )

        create_match = re.search(
            r"\bcreate\s+(?:a\s+)?(?:text\s+)?file\s+(?:on|in)\s+(?:my\s+)?(desktop|downloads?|documents?)\s+(?:called|named)\s+([^\\/:*?\"<>|]+)$",
            raw,
            re.IGNORECASE,
        )
        if create_match:
            folder = create_match.group(1).lower()
            filename = create_match.group(2).strip(" ,.!?")
            return VoiceToolMatch(
                ToolRequest("file.write", {"path": f"{self._FOLDER_PATHS[folder]}/{filename}", "text": ""}, source="voice"),
                "create_file",
            )

        if "powershell" in normalized and re.search(r"\b(?:current|today'?s?)\s+date\b", normalized):
            return VoiceToolMatch(
                ToolRequest("powershell.run", {"command": "Get-Date -Format 'dddd, MMMM d, yyyy h:mm tt'"}, source="voice"),
                "powershell_current_date",
            )
        if "powershell" in normalized and re.search(r"\bcurrent\s+time\b", normalized):
            return VoiceToolMatch(
                ToolRequest("powershell.run", {"command": "Get-Date -Format 'h:mm:ss tt'"}, source="voice"),
                "powershell_current_time",
            )

        if re.match(r"^(?:how|why|when|where|what)\b", normalized) and re.search(r"\b(?:open|launch)\b", normalized):
            return None

        match = re.search(r"\b(?:open|launch)\s+(.+?)(?:\s+for me)?$", raw, re.IGNORECASE)
        if match:
            target = match.group(1).strip(" ,.!?")
            if re.match(r"^(?:https?://|www\.)", target, re.IGNORECASE) or re.search(r"\.[a-z]{2,}(?:/|$)", target, re.IGNORECASE):
                return VoiceToolMatch(ToolRequest("browser.open_url", {"url": target}, source="voice"), "open_url")
            return VoiceToolMatch(ToolRequest("app.open", {"app": target}, source="voice"), "open_app")

        match = re.search(r"\bfocus\s+(?:the\s+)?(.+?)(?:\s+window)?$", raw, re.IGNORECASE)
        if match:
            return VoiceToolMatch(ToolRequest("ui.focus_window", {"title": match.group(1).strip(" ,.!?")}, source="voice"), "focus_window")

        match = re.search(r"\brun\s+(?:this\s+)?powershell(?:\s+command)?\s*[:,-]\s*(.+)$", raw, re.IGNORECASE)
        if match:
            return VoiceToolMatch(ToolRequest("powershell.run", {"command": match.group(1).strip()}, source="voice"), "powershell")

        return None
