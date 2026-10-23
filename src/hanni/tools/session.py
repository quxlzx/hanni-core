"""One-step tool-aware session used by the M6 voice path."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import replace

from hanni.core.shutdown import EmergencyStopActive
from hanni.tools.base import ConfirmationRequired, ToolError, ToolRegistry, ToolRequest
from hanni.tools.router import VoiceToolRouter


_CONFIRM_RE = re.compile(
    r"(?:yes|yeah|yep|confirm|confirmed|do it|go ahead|proceed|you can do that|yes do it|please do|do that)[.!?]*",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(r"^(?:no|nope|cancel|never mind|nevermind|don't|do not)\b", re.IGNORECASE)
_PERMISSION_TALK_RE = re.compile(r"\b(?:permission|permissions|privilege|privileges)\b", re.IGNORECASE)

_LOCAL_EXECUTION_RE = re.compile(
    r"^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?(?:create|make|write|delete|remove|move|copy|rename|run|execute|close|kill|install|uninstall|change|modify)\b.*(?:\b(?:file|folder|directory|app|application|program|process|powershell|downloads?|desktop|documents?|wallpaper|background|setting|settings)\b|\b[\w.-]+\.(?:py|txt|json|yaml|yml|md|csv|log|ps1|bat|cmd|js|ts)\b|[\\/])",
    re.IGNORECASE,
)

_INFO_OPEN_RE = re.compile(r"^(?:how\s+(?:would|do|can)\s+you\s+(?:open|launch))\s+(.+?)[?.!]*$", re.IGNORECASE)
_GROUNDED_EXPLAIN_RE = re.compile(r"\b(?:and|then)\s+(?:explain|tell\s+me|say)\b", re.IGNORECASE)
_EXPLAINABLE_READ_TOOLS = {"process.top_memory", "process.top_cpu", "gpu.top_processes", "system.battery", "system.stats"}


class ToolAwareSession:
    def __init__(self, fallback_session, registry: ToolRegistry, router: VoiceToolRouter | None = None) -> None:
        self.fallback_session = fallback_session
        self.registry = registry
        self.router = router or VoiceToolRouter()
        self._pending_confirmation: ToolRequest | None = None
        self._pending_trace_id = None

    def _execute(self, request: ToolRequest) -> Iterator[str]:
        service = self.registry.context.reliability
        if service is None:
            yield from self._execute_inner(request)
            return
        scope = service.resume_task(self._pending_trace_id) if request.confirmed and self._pending_trace_id else service.task('tool')
        with scope as trace:
            from hanni.reliability.context import current_correlation_id
            request = replace(request, correlation_id=current_correlation_id())
            yield from self._execute_inner(request)
            if self._pending_confirmation is not None:
                trace.record['waiting_for_approval'] = True
                self._pending_trace_id = trace.record['task_id']
                service.pending_owners[self._pending_trace_id] = self
            else:
                self._pending_trace_id = None

    def close(self):
        if self._pending_trace_id and self.registry.context.reliability:
            self.registry.context.reliability.cancel_pending(self._pending_trace_id)
        self._pending_confirmation = None
        self._pending_trace_id = None

    def _execute_inner(self, request: ToolRequest) -> Iterator[str]:
        try:
            result = self.registry.execute(request)
            self._pending_confirmation = None
            yield result.message
        except ConfirmationRequired as exc:
            self._pending_confirmation = request
            yield f"I need your explicit confirmation before I do that. {exc} Say yes or go ahead to confirm."
        except EmergencyStopActive:
            self._pending_confirmation = None
            yield "Safe Mode is active, so I won't run computer actions until you explicitly resume H.A.N.N.I."
        except (ToolError, OSError, ValueError, LookupError, PermissionError) as exc:
            self._pending_confirmation = None
            yield f"I couldn't do that safely: {exc}"

    def _execute_with_grounded_explanation(self, request: ToolRequest, owner_prompt: str, **kwargs: object) -> Iterator[str]:
        try:
            result = self.registry.execute(request)
        except EmergencyStopActive:
            yield "Safe Mode is active, so I won't run computer actions until you explicitly resume H.A.N.N.I."
            return
        except (ConfirmationRequired, ToolError, OSError, ValueError, LookupError, PermissionError) as exc:
            yield f"I couldn't do that safely: {exc}"
            return
        yield result.message
        evidence_prompt = (
            "AUTHORITATIVE LOCAL TOOL RESULT: " + result.message + "\n"
            "Owner request: " + owner_prompt + "\n"
            "Answer only the requested explanatory part in one concise sentence. "
            "Treat the tool result as authoritative, do not invent different live values, and do not claim any new action happened."
        )
        explanation = "".join(self.fallback_session.stream_response(evidence_prompt, **kwargs)).strip()
        if explanation:
            yield " " + explanation

    def stream_response(self, prompt: str, **kwargs: object) -> Iterator[str]:
        clean = prompt.strip()

        # Confirmation is intentionally narrow and only applies to the immediately
        # pending validated tool request. An unrelated next turn clears it.
        if self._pending_confirmation is not None:
            pending = self._pending_confirmation
            if _CONFIRM_RE.fullmatch(clean):
                yield from self._execute(replace(pending, confirmed=True))
                return
            if _CANCEL_RE.match(clean):
                self._pending_confirmation = None
                if self._pending_trace_id and self.registry.context.reliability:
                    self.registry.context.reliability.cancel_pending(self._pending_trace_id)
                self._pending_trace_id = None
                yield "Okay, I won't do that."
                return
            self._pending_confirmation = None
            if self._pending_trace_id and self.registry.context.reliability:
                self.registry.context.reliability.cancel_pending(self._pending_trace_id)
            self._pending_trace_id = None

        info_open = _INFO_OPEN_RE.match(clean)
        if info_open:
            target = info_open.group(1).strip(" ,.!?")
            yield f"I would use my validated local app-launch tool for {target}; it only opens the app if Windows can resolve it. I won't launch it unless you explicitly ask me to open it."
            return

        # Tool permissions are configuration state, not something the conversational
        # model is allowed to grant or revoke. This also prevents a mis-transcribed
        # sentence about "deletion privileges" from sounding like a permission change.
        if _PERMISSION_TALK_RE.search(clean):
            yield "My tool permissions haven't changed. Destructive actions are still enforced by the configured safety and confirmation rules."
            return

        match = self.router.route(clean)
        if match is None:
            # Never let the conversational model claim that a local computer
            # action happened when no validated tool/agent route actually ran.
            if _LOCAL_EXECUTION_RE.search(clean):
                yield "I didn't run that action because I don't have a validated tool route for that exact request yet."
                return
            yield from self.fallback_session.stream_response(clean, **kwargs)
            return
        if match.request.name in _EXPLAINABLE_READ_TOOLS and _GROUNDED_EXPLAIN_RE.search(clean):
            yield from self._execute_with_grounded_explanation(match.request, clean, **kwargs)
            return
        yield from self._execute(match.request)
