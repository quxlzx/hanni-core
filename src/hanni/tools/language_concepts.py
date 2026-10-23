"""Small, context-bound concept bridges for casual and transcribed requests.

These transformations do not grant capabilities. The MCP host still checks the
registry, action allowlist, and permission policy after retrieval.
"""
from __future__ import annotations

import re
from typing import Mapping, Sequence

from hanni.tools.time_routing import normalize_question


_APP_OPEN = re.compile(r"^(?:open|launch|start|fire up|bring up|pop open|boot up|get)\b", re.I)
_MEDIA_OBJECT = re.compile(r"\b(?:music|song|track|tune|playback|media)\b", re.I)
_MEDIA_ACTION = re.compile(r"\b(?:pause|resume|continue|unpause|play|stop|skip|next|previous|back)\b", re.I)
_BARE_MEDIA = re.compile(r"^(?:pause|resume|continue|unpause|play|skip|next|back|previous)(?:\s+(?:it|that|this))?$", re.I)
_PERMISSION = re.compile(r"^(?:can|could|may|is|are|do|does|would)\b.*\b(?:hanni|you)\b.*\b(?:allowed|permitted|able|permission|can)\b", re.I)


def recent_subject(history: Sequence[Mapping[str, object]]) -> str | None:
    """Inherit through short media follow-ups; an unrelated turn clears context."""
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        text = str(item.get("content", "")).casefold()
        if _BARE_MEDIA.fullmatch(normalize_question(text)) or re.fullmatch(r"what(?:'s| is) playing\??", text):
            continue
        if "spotify" in text:
            return "spotify"
        if _MEDIA_OBJECT.search(text):
            return "media"
        if re.search(r"\b(?:calendar|agenda|meeting|appointment|tomorrow|tmr)\b", text):
            return "calendar"
        if re.match(r"^(?:open|launch|start|fire up|bring up|pop open)\b", text):
            return "app"
        if re.search(r"\b(?:cpu|ram|memory|gpu|vram|disk|storage|wifi)\b", text):
            return "diagnostics"
        if re.search(r"\b(?:pc|computer|system|desktop|everything|game)\b", text) and re.search(r"\b(?:slow|lagging|freezing|cooked|stuttering|hanging)\b", text):
            return "diagnostics"
        return None
    return None


def conceptual_query(query: str, history: Sequence[Mapping[str, object]] = ()) -> str:
    """Canonicalize *meaningful context*, without broad fuzzy tool matching."""
    text = re.sub(r"\s+", " ", query.casefold().strip())
    bare_follow_up = normalize_question(text)
    if re.match(r'^(?:hey|hi|hello)[, ]+hanni\b', text):
        text = bare_follow_up
    text = re.sub(r"\b(?:uh|um)\s+(?=\w)", "", text)
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text)
    text = re.sub(r'\bgraphics\s+processor\b', 'gpu', text)
    if _PERMISSION.search(text):
        return text

    if _APP_OPEN.search(text) and not re.search(r"\b(?:window|foreground)\b", text):
        text = re.sub(r"^(?:pop open|boot up|bring up|fire up)\b", "open", text)
        text = re.sub(r"^(?:get)\s+(.+?)\s+up$", r"open \1", text)
        text = re.sub(r"\b(?:disc|disco)\b", "discord", text)
        text = re.sub(r"\b(?:vs code|vscode)\b", "code", text)

    if re.search(r"\b(?:hanni|you|your|u|assistant|qwen[\w.]*)\b", text) and not re.search(r"\b(?:think|opinion|explain|generally)\b", text):
        if re.search(r"\b(?:quant|qwen[\w.]*|locally|hardware|status)\b", text):
            text += " model status"
        if re.search(r"\b(?:hardware|gpu)\b", text):
            text += " what gpu is hanni on"

    if _MEDIA_ACTION.search(text) and (_MEDIA_OBJECT.search(text) or "spotify" in text):
        text = re.sub(r"\b(?:continue|unpause|keep playing|carry on)\b", "resume", text)
        text = re.sub(r"\b(?:song|track|tune)\b", "music", text)
        text = re.sub(r"\b(?:skip|next)\s+(?:this|the)\s+music\b", "next media", text)
    elif _BARE_MEDIA.fullmatch(bare_follow_up):
        subject = recent_subject(history)
        if subject in {"spotify", "media"}:
            action = re.sub(r"\b(?:continue|unpause)\b", "resume", bare_follow_up)
            return f"{action} {subject}"
        # No unique target: allow the host to ask rather than call it forbidden.
        return bare_follow_up
    if re.fullmatch(r"what(?:'s| is) playing\??", text) and recent_subject(history) == 'spotify':
        return 'spotify status now playing'

    if re.search(r"\b(?:pc|computer|desktop|system|everything|apps?|folders?|files?)\b", text):
        text = re.sub(r"\b(?:crawls?|crawling|dragging|chugging|cooked|hanging|stalling)\b", "slow", text)
        text = re.sub(r"\btakes? (?:forever|ages) to (?:load|open)\b", "slow to open", text)
        text = re.sub(r"\btaking (?:forever|ages) to (?:load|open)\b", "slow to open", text)
        if re.search(r"\bsystem load\b", text):
            text += " system performance"
    if re.search(r"\b(?:cpu|ram|memory|gpu|vram|disk|drive)\b", text):
        if re.search(r"\b(?:write|writing|reading)\b.*\bdisk\b", text):
            text += " disk io"
        if re.search(r"\b(?:gpu|graphics card)\b.*\b(?:at|use|pinned|maxing)\b", text):
            text += " gpu usage"
    if re.search(r"\b(?:today|tomorrow|tmr|tonight|friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b", text):
        text = re.sub(r"\b(?:what(?:'s|s)?|any)\s+(?:my\s+)?plans\b", "what do i have", text)
        text = re.sub(r"\b(?:my\s+)?plans\b", "what do i have", text) if text.startswith(("tmr ", "tomorrow ")) else text
        text = re.sub(r"^my plans\b", "what do i have", text)
        text = re.sub(r"^what(?: does|s|'s) (\w+) look like\b", r"what do i have \1", text)
        text = re.sub(r"^got something\b", "do i have anything", text)
        text = re.sub(r"^what classes do i have\b", "what do i have", text)
        text = re.sub(r"^what(?:'s|s) tomorrow(?=$|\s+(?:and|plus|then)\b)", "what do i have tomorrow", text)
        text = re.sub(r"^tomorrow schedule\b", "what do i have tomorrow", text)
        text = re.sub(r"^calendar (\w+)\b", r"what do i have \1 on my calendar", text)
        text = re.sub(r"^what(?:'s|s) on (today|tomorrow|tonight|\w+day)\b", r"what do i have \1", text)
    if re.search(r"\b(?:next|after this)\b", text):
        text = re.sub(r"^what comes after this$", "what's next", text)
        text = re.sub(r"^what do i got next$", "what's next", text)
    if text.startswith("do i have stuff this weekend"):
        text = "do i have anything this weekend"
    if recent_subject(history) == "calendar":
        text = re.sub(r"^(?:how about|and)\s+(today|tomorrow|\w+day)\b", r"what do i have \1", text)
    if recent_subject(history) == "diagnostics":
        text = re.sub(r"^(?:what about|and)\s+(gpu|disk|storage|vram)\b", r"check \1 usage", text)
    if re.search(r"\b(?:find|where)\b", text) and re.search(r"\bcv\b", text):
        text = re.sub(r"\bcv\b", "resume file", text)
    return text


def media_menu(query: str, history: Sequence[Mapping[str, object]] = ()) -> tuple[str, ...] | None:
    """Resolve a media action to an existing safe control, never a new tool."""
    explicit_track = bool(re.search(r"\b(?:music|song|track|tune)\b", query, re.I))
    text = conceptual_query(query, history)
    if _PERMISSION.search(text):
        return None
    if "spotify" in text:
        # Existing Spotify-specific resolver retains URI, launch, and status
        # precedence. This bridge is for a player-agnostic request.
        return None
    subject = "spotify" if "spotify" in text else ("media" if _MEDIA_OBJECT.search(text) else None)
    if subject is None and _BARE_MEDIA.fullmatch(normalize_question(text)):
        subject = recent_subject(history)
    if subject not in {"spotify", "media"}:
        return None
    if re.search(r"\b(?:pause|resume|continue|unpause|play)\b", text):
        if subject == "spotify":
            return ("spotify.play_pause", "spotify.status", "spotify.launch")
        return ("media.play_pause", "spotify.status", "spotify.play_pause") if explicit_track else ("media.play_pause",)
    if re.search(r"\b(?:skip|next)\b", text):
        if subject == "spotify":
            return ("spotify.next",)
        return ("media.next_track", "spotify.next") if explicit_track else ("media.next_track",)
    if re.search(r"\b(?:previous|back)\b", text):
        if subject == "spotify":
            return ("spotify.previous",)
        return ("media.previous_track", "spotify.previous") if explicit_track else ("media.previous_track",)
    if re.search(r"\bstop\b", text) and subject == "media":
        return ("media.stop",)
    return None
