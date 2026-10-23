"""MCP host boundary for HANNI's local computer capabilities.

The host deliberately exposes only a small, relevant subset of tools to the
resident language model. Authority remains in :class:`ToolRegistry`; MCP is a
standard discovery/call boundary, not a bypass around permissions or audit.
"""
from __future__ import annotations

import re
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

from hanni.tools.base import ToolRequest, ToolRegistry
from hanni.tools.capabilities import (LocalCapabilityDiscovery, describe, diagnostic_subintent, diagnostic_tool_budget)
from hanni.tools.capability_api import error_contract, risk_of
from hanni.tools.sensitive_paths import is_sensitive_path
from hanni.logs.redaction import redact_value
from hanni.tools.calendar_routing import calendar_create_request, calendar_read_request
from hanni.tools.time_routing import time_read_request


_WIRE_SAFE = re.compile(r"[^A-Za-z0-9_-]+")



@dataclass(frozen=True, slots=True)
class McpTool:
    server: str
    capability_id: str
    wire_name: str
    description: str
    input_schema: Mapping[str, Any]
    risk: str
    fixed_arguments: Mapping[str, Any] = field(default_factory=dict)
    definition_hash: str = ''

    def openai_schema(self) -> dict[str, Any]:
        """OpenAI/llama.cpp function schema for this MCP tool.

        Context that HANNI resolved deterministically is shown for reference,
        omitted from model-supplied parameters, and enforced at execution.
        """
        schema = dict(self.input_schema)
        description = self.description
        if self.capability_id == 'email.search':
            schema = {**schema, 'properties': dict(schema.get('properties', {}))}
            schema['properties'].pop('plan', None)
        if self.capability_id in {'google_calendar.agenda', 'google.calendar.events', 'google.calendar.availability'}:
            schema = {**schema, 'properties': dict(schema.get('properties', {}))}
            for key in ('availability_at', 'availability_start', 'availability_end',
                        'time_min', 'time_max', 'academic_concept', 'course', 'first_only',
                        'temporal_source', 'followup_context_used'):
                schema['properties'].pop(key, None)
        if self.fixed_arguments:
            schema = {**schema, "properties": dict(schema.get("properties", {})),
                      "required": list(schema.get("required", []))}
            for key, value in self.fixed_arguments.items():
                schema["properties"].pop(key, None)
            schema["required"] = [key for key in schema["required"] if key not in self.fixed_arguments]
            fixed = ", ".join(f"{key}={value}" for key, value in self.fixed_arguments.items())
            description += f" HANNI already resolved {fixed}; do not supply those arguments."
        return {
            "type": "function",
            "function": {
                "name": self.wire_name,
                "description": description,
                "parameters": schema,
            },
        }


def classification(definition) -> str:
    if definition.permission_level == 0 and definition.risk_level == 0 and definition.side_effect in {None, 'read'}:
        return 'read_only'
    return 'safe_action' if definition.risk_level <= 1 and definition.permission_level <= 1 else 'sensitive_action'


def family_of(name: str) -> str:
    return {'google_calendar': 'calendar', 'gmail': 'email', 'folder': 'files', 'file': 'files',
            'archive': 'files', 'spotify': 'media', 'audio': 'media', 'process': 'process',
            'gpu': 'computer', 'system': 'computer', 'disk': 'computer', 'net': 'network',
            'device': 'devices'}.get(name.split('.')[0], name.split('.')[0])


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    tools: tuple[McpTool, ...]
    status: str
    confidence: str
    families: tuple[str, ...]
    subintents: tuple[str, ...]
    blocked_capabilities: tuple[str, ...]
    required_groups: tuple[tuple[str, ...], ...] = ()


class McpHost:
    """Discover and call bounded local MCP tools for the resident assistant."""

    def __init__(self, registry: ToolRegistry, *, read_only: bool = True, max_tools: int = 8,
                 allowed_actions: tuple[str, ...] = (), timezone_name: str | None = None) -> None:
        if not 1 <= max_tools <= 8:
            raise ValueError("max_tools must be 1..8")
        self.registry = registry
        self.read_only = read_only
        self.max_tools = max_tools
        self.allowed_actions = frozenset(allowed_actions)
        self.timezone_name = timezone_name or registry.context.timezone_name
        self.discovery = LocalCapabilityDiscovery(registry)

    def _retrieval_candidates(self, query):
        from hanni.tools.discovery import index_for
        cached = getattr(self, '_eligible_retrieval_cache', None)
        if cached is None or cached[0] != self.registry.revision:
            revision = self.registry.revision
            eligible = tuple(
                definition.name for definition in self.registry.definitions()
                if self._allowed(definition) and definition.permission_level == 0
                and definition.side_effect in {None, 'read'}
                and definition.requires_confirmation_if is None
            )
            if revision == self.registry.revision:
                self._eligible_retrieval_cache = (revision, eligible)
        else:
            eligible = cached[1]
        return index_for(self.registry).candidates(query, eligible=eligible, ceiling=self.max_tools)

    def _retrieval_actions(self, query):
        """Metadata fallback for explicitly configured local reversible writes.

        This is a discovery menu, never execution consent. Provider/external
        actions retain their original resolvers and cannot enter this fallback.
        """
        from hanni.tools.discovery import index_for
        eligible = tuple(definition.name for definition in self.registry.definitions()
                         if definition.name in self.allowed_actions and self._allowed(definition)
                         and not definition.external_definition_hash
                         and describe(definition).side_effect == 'reversible_write')
        return tuple(row for row in index_for(self.registry).candidates(
            query, eligible=eligible, ceiling=self.max_tools)
            if row.coverage >= 0.5 and len(row.matched_terms) >= 3)

    @staticmethod
    def _wire_name(capability_id: str) -> str:
        # OpenAI-compatible servers are strict about function-name characters.
        compact = _WIRE_SAFE.sub("_", capability_id.replace(".", "__")).strip("_")
        return ("hanni__" + compact)[:64]

    def _allowed(self, definition) -> bool:
        cap = describe(definition)
        # A model-facing arbitrary command would make tool-name policy
        # meaningless. Keep the manual CLI path, but never offer it over MCP.
        if definition.name == 'powershell.run':
            return False
        if definition.name in self.allowed_actions or definition.name == 'google.calendar.create' and 'google_calendar.create' in self.allowed_actions:
            return definition.risk_level < 3 and definition.permission_level <= 2
        if not self.read_only:
            return definition.risk_level < 3
        return (
            risk_of(cap) == "read_only"
            and definition.permission_level == 0
            and definition.risk_level < 3
            and definition.side_effect in {None, "read"}
            and definition.requires_confirmation_if is None
        )

    def _as_tool(self, definition, *, fixed_arguments: Mapping[str, Any] | None = None) -> McpTool:
        cap = describe(definition)
        return McpTool(
            server=cap.name.split('.')[1] if definition.external_definition_hash else "local-computer",
            capability_id=cap.name,
            wire_name=self._wire_name(cap.name),
            description=cap.description,
            input_schema=cap.argument_schema,
            risk=risk_of(cap),
            fixed_arguments=dict(fixed_arguments or {}),
            definition_hash=definition.external_definition_hash,
        )

    def _google_write_enabled(self, definition, arguments):
        from hanni.tools.google_routing import google_service
        service = google_service(definition.name)
        if not service or definition.side_effect in {None, 'read'}:
            return True
        access = getattr(self.registry, 'google_access', None)
        if access is None:
            return False
        try:
            account = access.resolve_account(arguments.get('account'), service)
            return access.has_capability(account, service + '.write')
        except Exception:
            return False

    def route(self, query: str, *, history=(), now: datetime | None = None) -> RoutingDecision:
        from hanni.core.responsiveness import phase
        from hanni.core.response_stream import check_cancelled
        check_cancelled()
        with phase('routing'):
            decision = self._route(query, history=history, now=now)
            from hanni.tools.routing_intents import action_requested, request_intent, no_tool_request, mask_arguments
            positive = request_intent(query)
            from hanni.tools.discovery import intent_text
            if not decision.tools and decision.status != 'blocked' and not action_requested(positive) and not no_tool_request(positive):
                from hanni.tools.discovery import index_for, tokens
                index = index_for(self.registry)
                def correction(match):
                    word = match[0].casefold()
                    normalized = tokens(word)
                    if normalized and normalized[0] in index.postings:
                        return match[0]
                    return index._correct(word)
                masked = mask_arguments(positive)
                corrected = re.sub(r'\b[A-Za-z]{5,}\b', correction, masked)
                if corrected != masked:
                    decision = self._route(query, history=history, now=now, retrieval_text=corrected)
            if (decision.status != 'blocked' and not action_requested(positive)
                    and not no_tool_request(positive) and not re.search(r'[\"\']', query)
                    and mask_arguments(positive) == positive and intent_text(positive) == positive):
                # Operation clauses share no literal paths/titles. Allocate one
                # candidate per independent observation before alternatives.
                parts = re.split(r'\s+(?:and|plus|also|as well as)\s+', mask_arguments(positive), maxsplit=7, flags=re.I)
                if len(parts) > 1:
                    observations = [self._route(part, history=history, now=now) for part in parts]
                    groups = [tuple(tool.capability_id for tool in row.tools if tool.risk == 'read_only')
                              for row in observations]
                    if all(groups):
                        primary = [row.tools[0] for row in observations]
                        tools = list(dict((tool.capability_id, tool) for tool in
                                          [*primary, *(tool for row in observations for tool in row.tools)]
                                          if tool.risk == 'read_only').values())[:self.max_tools]
                        from dataclasses import replace
                        decision = replace(decision, tools=tuple(tools), status='tools',
                                           required_groups=tuple(groups))
            return decision

    def rediscover(self, query: str, *, owner_query: str, history=(), limit=None):
        """A bounded metadata page, not an action permission or argument resolver.

        A semantic reformulation can retrieve eligible observations. Writes can
        only be retained from the original owner's resolved, allowlisted menu.
        Never route reformulated action text to manufacture fixed arguments.
        """
        from hanni.core.response_stream import check_cancelled
        from hanni.tools.discovery import index_for, intent_text
        from hanni.tools.routing_intents import request_intent, no_tool_request
        check_cancelled()
        if not isinstance(query, str) or not 1 <= len(query) <= 512:
            raise ValueError('Discovery queries must be 1..512 characters.')
        original = self.route(owner_query, history=history)
        if original.status == 'blocked' or no_tool_request(request_intent(owner_query)):
            return ()
        cap = min(self.max_tools, max(1, limit or self.max_tools))
        pinned = [tool for tool in original.tools if tool.risk != 'read_only']
        rows = self._retrieval_candidates(intent_text(query))
        tools = [*pinned, *(self._as_tool(self.registry.get(row.name)) for row in rows)]
        unique = {tool.capability_id: tool for tool in tools}
        # Retain fixed observation arguments (dates, files, accounts) whenever
        # that capability was already resolved from the original owner request.
        for tool in original.tools:
            if tool.capability_id in unique:
                unique[tool.capability_id] = tool
        return tuple(unique.values())[:cap]

    def _route(self, query: str, *, history=(), now: datetime | None = None, retrieval_text=None) -> RoutingDecision:
        """Return an inspectable retrieval decision; never choose or call a tool."""
        from hanni.tools.routing_intents import (normalize, clauses, specific_menu, action_requested,
                                                mask_arguments, request_intent, no_tool_request,
                                                independent_observations, resource_followup)
        from hanni.tools.intent_prototypes import match_intent
        from hanni.tools.language_concepts import conceptual_query, media_menu, recent_subject
        from hanni.tools.capabilities import diagnostic_candidate_bundle
        from hanni.tools.discovery import intent_text
        original = query
        positive = request_intent(original)
        positive = resource_followup(positive, history)
        if positive is None:
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        planning_text = mask_arguments(intent_text(positive))
        if no_tool_request(planning_text):
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        # Explicit server mentions retrieve only approved live imports through
        # the original lexical index; definitions never supply routing policy.
        if any(item.external_definition_hash for item in self.registry.definitions()):
            imported = self.discovery.search(planning_text, limit=self.max_tools, extensions_only=True)
            explicit = []
            for match in imported:
                definition = self.registry.get(match.capability.name)
                server_name = definition.tags[0] if definition.tags else ''
                tool_name = definition.aliases[0] if definition.aliases else ''
                # An external name that shadows a built-in needs its server
                # label; bare built-in names retain the original meaning.
                try:
                    shadowed = not bool(self.registry.get(tool_name).external_definition_hash)
                except Exception: shadowed = False
                named_server = server_name and re.search(r'(?<!\w)' + re.escape(server_name.casefold()) + r'(?!\w)', planning_text.casefold())
                named_tool = not shadowed and tool_name and re.search(r'(?<!\w)' + re.escape(tool_name.casefold()) + r'(?!\w)', planning_text.casefold())
                leaf = tool_name.rsplit('.', 1)[-1].replace('_', ' ')
                named_leaf = leaf and re.search(r'(?<!\w)' + re.escape(leaf.casefold()) + r'(?!\w)', planning_text.casefold())
                # An exact unique external operation name plus metadata evidence
                # can be explicit without requiring the server's label. A leaf
                # that collides with a built-in or another import stays ambiguous.
                leaf_matches = [item for item in self.registry.definitions()
                                if item.name.rsplit('.', 1)[-1].replace('_', ' ') == leaf
                                or item.external_definition_hash and item.aliases
                                and item.aliases[0].rsplit('.', 1)[-1].replace('_', ' ') == leaf]
                unique_leaf = not shadowed and len(leaf_matches) == 1
                if match.score >= 8 and len(match.matched_terms) >= 2 and (
                        named_tool or named_leaf and (named_server or unique_leaf)):
                    explicit.append(definition)
            exact = self.registry.capabilities.resolve_id(original)
            if exact and exact.startswith('mcp.'):
                explicit = [self.registry.get(exact)]
            if explicit:
                allowed = tuple(self._as_tool(item) for item in explicit if self._allowed(item))
                return RoutingDecision(allowed, 'tools' if allowed else 'blocked', 'high',
                                       ('mcp',), (), tuple(item.name for item in explicit if not self._allowed(item)))
        location_followup = re.fullmatch(r'(?:what about|how about|and|try|check|search)\s+(?:in\s+)?(?:my\s+)?(downloads|documents|desktop)\??', query.strip(), re.I)
        if location_followup:
            prior = next((str(item.get('content', '')) for item in reversed(history)
                          if item.get('role') == 'user'), '')
            if re.search(r'\b(?:find|search|look for|locate)\b', prior, re.I):
                prior = re.sub(r'\b(?:in|under|inside)\s+(?:my\s+)?(?:downloads|documents|desktop)\b', '', prior, flags=re.I)
                original = prior.rstrip(' ?.') + ' in ' + location_followup.group(1)
                positive = request_intent(original)
                planning_text = mask_arguments(intent_text(positive))
        query = normalize(conceptual_query(retrieval_text or planning_text, history))
        if self.timezone_name:
            zone = ZoneInfo(self.timezone_name)
            now = datetime.now(zone) if now is None else (now.astimezone(zone) if now.tzinfo else now.replace(tzinfo=zone))
        from hanni.tools.google_routing import google_request, requested_account
        from hanni.tools.email_routing import email_write_requested
        if email_write_requested(positive):
            return RoutingDecision((), 'blocked', 'high', ('email',), (), ())
        planning_text = mask_arguments(intent_text(positive))
        local_menu = specific_menu(query)
        local_observation = bool(local_menu and not action_requested(query)
            and not re.search(r'\b(?:google|gmail|calendar|agenda)\b',query)
            and any(name.startswith(('system.','process.','disk.','gpu.','security.','device.','display.','net.','ui.','spotify.','power.'))
                    for name in local_menu)
            and re.search(r'\b(?:cpu|processor|ram|memory|gpu|vram|disk|storage|drive|bitlocker|encryption|firewall|defender|'
                          r'windows|process|pid|laptop|computer|pc|spotify|battery|power|charge)\b',query))
        local_source = bool(local_menu and not re.search(r'\b(?:email|gmail|inbox|google)\b',query)
            and (local_observation or 'file path' in query and any(name.startswith(('file.','archive.','disk.')) for name in local_menu)
                 or local_menu == ('app.open',)))
        google_plan = (google_request(planning_text, history=history, now=now, timezone_name=self.timezone_name)
                       if len(clauses(positive)) == 1 and not local_source else None)
        if google_plan is not None and planning_text != original:
            # Choose the operation from intent-only text, then retain the
            # original argument parser when it resolves that same operation.
            bound = google_request(positive, history=history, now=now, timezone_name=self.timezone_name)
            if bound is not None and bound.name == google_plan.name:
                google_plan = bound
        if google_plan is not None:
            try:
                definition = self.registry.get(google_plan.name)
            except Exception:
                return RoutingDecision((), 'blocked', 'high', ('google',), (), (google_plan.name,))
            if not self._allowed(definition) or not self._google_write_enabled(definition, google_plan.arguments):
                return RoutingDecision((), 'blocked', 'high', ('google',), (), (google_plan.name,))
            return RoutingDecision((self._as_tool(definition, fixed_arguments=google_plan.arguments),),
                                   'tools', 'high', ('google',), ('google_service',), ())
        from hanni.tools.email_routing import email_request, email_write_requested
        if email_write_requested(positive):
            return RoutingDecision((), 'blocked', 'high', ('email',), (), ())
        mail_request = (email_request(planning_text, history, now=now, timezone_name=self.timezone_name)
                        if not local_source else None)
        if mail_request is not None and planning_text != original:
            bound = email_request(positive, history, now=now, timezone_name=self.timezone_name)
            if bound is not None and bound.name == mail_request.name:
                mail_request = bound
        if mail_request is not None and len(clauses(positive)) == 1:
            account = requested_account(original)
            if account:
                from dataclasses import replace
                mail_request = replace(mail_request, arguments={**mail_request.arguments, 'account': account})
            definition = self.registry.get(mail_request.name)
            if not self._allowed(definition):
                return RoutingDecision((), 'blocked', 'high', ('email',), (), (mail_request.name,))
            return RoutingDecision((self._as_tool(definition, fixed_arguments=mail_request.arguments),),
                                   'tools', 'high', ('email',), ('email_read' if mail_request.name == 'email.read' else 'email_search',), ())
        educational = bool(re.match(r"^(?:what (?:is|does)\s+(?:(?:a|an|the)\s+)?(?:vram|cpu|ram|gpu|mcp|video memory)\b|"
                                    r"(?:explain|define|why do|how do)\b.*\b(?:vram|cpu|ram|gpu|mcp|video memory)\b)", query))
        if educational and not re.search(r"\b(?:my|i|mine|hanni|right now|currently|using|usage)\b", query):
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        general_question = bool(
            re.match(r'^(?:what (?:is|are) (?:a|an|the)\b|what does (?:a|an|the)\b|'
                     r'how does (?:a|an|the)\b.*\bwork\b|what does .+\bmean\b|'
                     r'tell me about the history of\b|do (?:apps?|programs?|computers?)\b.*\bneed\b)', query)
            or re.search(r'\b(?:in general|conceptually)\b', query))
        if (general_question and len(clauses(original)) == 1 and time_read_request(query) is None
                and not re.search(r'\b(?:log|email|file|document)\b.*\b(?:say|contain|show|read)\b', query)
                and not re.search(r'\b(?:i|my|mine|this|these|latest|value|hanni|right now|current|currently|live|usage|status|percent|level|load|remaining|free|active|loaded|running|on my|am i|do i)\b', query)):
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        if re.match(r"^(?:what do you think|your opinion|what's your take)\b", query) and not re.search(r"\b(?:my|hanni|right now|currently)\b", query):
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        if re.search(r"\b(?:don't|do not|never)\s+(?:open|play|launch|delete|kill|pause|run|send)\b", query):
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        if (re.match(r"^(?:i am|i'm|im)\b", query) and not action_requested(query)
                and not re.search(r"\b(?:pc|computer|laptop|calendar|model|system|cpu|ram|gpu|disk|spotify)\b", query)):
            return RoutingDecision((), 'clarification', 'low', (), (), ())
        if re.fullmatch(r'(?:open|launch|focus)\s+it(?:\s+again)?', query) and recent_subject(history) != 'app':
            return RoutingDecision((), 'clarification', 'low', ('app',), (), ())
        parts = clauses(positive)
        if len(parts) > 1:
            decisions = [self.route(part, history=history, now=now) for part in parts]
            # Block a compound mutation as a whole; never silently perform half.
            blocked = tuple(dict.fromkeys(n for d in decisions for n in d.blocked_capabilities))
            if any(d.status == 'blocked' for d in decisions):
                return RoutingDecision((), 'blocked', 'high', tuple(dict.fromkeys(f for d in decisions for f in d.families)), (), blocked)
            menus = [list(d.tools) for d in decisions if d.tools]
            selected, seen = [], set()
            # Round-robin reservation prevents a broad diagnostic from starving
            # the Calendar, files or model-status clause.
            while any(menus) and len(selected) < self.max_tools:
                for menu in menus:
                    if menu:
                        tool = menu.pop(0)
                        if tool.capability_id not in seen:
                            selected.append(tool)
                            seen.add(tool.capability_id)
                            if len(selected) == self.max_tools: break
            return RoutingDecision(tuple(selected), 'tools' if selected else 'clarification',
                'high' if selected else 'low', tuple(dict.fromkeys(f for d in decisions for f in d.families)),
                tuple(dict.fromkeys(f for d in decisions for f in d.subintents)), (),
                tuple(group for d in decisions for group in (d.required_groups or
                    (tuple(tool.capability_id for tool in d.tools),) if d.tools else ())))

        # Date and time facts are fixed before the model sees its menu.
        request = calendar_create_request(positive, now=now, timezone_name=self.timezone_name)
        if request is None and not action_requested(query):
            calendar_query = query
            if recent_subject(history) == 'calendar' and re.match(r'^(?:anything|what about|and)\s+after\s+\d', query):
                prior = next((str(item.get('content', '')) for item in reversed(history) if item.get('role') == 'user'), '')
                day = re.search(r'\b(today|tomorrow|tmr|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', prior, re.I)
                calendar_query = query + ' on my calendar' + (' ' + day[0] if day else '')
            request = (calendar_read_request(calendar_query, history, today=now.date() if now else None,
                                            now=now, timezone_name=self.timezone_name) if not local_source else None)
            if request is None:
                request = time_read_request(query)
        if request is None and re.search(r'\b(?:calendar|agenda)\b', query) and re.search(r'\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2})\b', query):
            return RoutingDecision((), 'clarification', 'low', ('calendar',), (), ())
        observations = independent_observations(query) if not action_requested(query) else ()
        menu = observations or media_menu(planning_text, history) or local_menu
        diagnostic = diagnostic_subintent(query)
        prototype = match_intent(query)
        if (prototype and prototype.name == 'calendar_next'
                and not re.search(r'\bnext\s+(?:week|month|weekend|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', query)
                and (request is None or request.name == 'google_calendar.agenda'
                     and not request.arguments.get('academic_concept'))):
            request = calendar_read_request("what's next", history, today=now.date() if now else None)
        elif prototype and prototype.name in {'calendar_agenda', 'calendar_availability'} and request is None:
            day = re.search(r'\b(?:(?:this|next|coming)\s+)?(?:today|tomorrow|tmr|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', query)
            if day:
                request = calendar_read_request('what do i have ' + day[0], history,
                                                today=now.date() if now else None)
        elif (prototype and prototype.name == 'time_now' and request is None and not menu
              and not re.search(r'\b(?:that|convert|from|since|ago)\b', query)):
            request = time_read_request('local time')
        status_only = bool(not re.search(r'\b(?:why|high|full|shot|jump|cooked|spike|almost|culprit|hog|eating|using)\b', query))
        resource_status_override = bool(prototype and prototype.name in {'memory_usage','cpu_usage'}
                                        and status_only and not query.startswith('check ')
                                        and not re.search(r'\b(?:process|task|program|executable|top\w*|biggest|which|who)\b', query)
                                        and not re.search(r'\b(?:gpu|vram|video memory)\b', query))
        prototype_override = bool(prototype and request is None and (
            (not menu and diagnostic is None)
            or resource_status_override
            or prototype.name == 'temperatures' and bool(re.search(r'\b(?:temps?|temperatures?|hot)\b', query))
            or prototype.name == 'file_search' and (not menu or menu == ('note.search',))
            or prototype.name == 'permission_question'
            or (prototype.name == 'disk_io' and menu in {('startup.list',), ('folder.open',)})
            or (prototype.name == 'disk_io' and not menu and diagnostic is not None
                and diagnostic.name == 'general_slowdown')
            or (prototype.name in {'spotify_play','spotify_pause','spotify_next','spotify_previous'}
                and (not menu or menu in {('spotify.status',), ('spotify.play_pause','spotify.status','spotify.launch')}))
            or (prototype.name == 'app_open' and (not menu or menu == ('spotify.status',)))))
        retrieved_action = False
        if request is not None:
            names = (request.name,)
        elif observations:
            names = observations
        elif prototype_override:
            names = prototype.menu
        elif diagnostic is not None and diagnostic.name in {'thermal_power', 'general_slowdown'} and re.search(r'\b(?:slow|sluggish|crawling|performance|tanks|lagging)\b', query) and not action_requested(query) and (not menu or menu in {('ui.windows_detailed',), ('ui.list_windows',)}):
            names = diagnostic_candidate_bundle(query)[:diagnostic_tool_budget(query, ceiling=self.max_tools)]
        elif diagnostic is not None and diagnostic.name == 'memory_pressure' and menu == ('model.status',) and re.search(r'\b(?:hogging|eating|using|chewing)\b', query):
            names = diagnostic_candidate_bundle(query)[:diagnostic_tool_budget(query, ceiling=self.max_tools)]
        elif menu:
            names = menu
        elif diagnostic is not None:
            names = diagnostic_candidate_bundle(query)[:diagnostic_tool_budget(query, ceiling=self.max_tools)]
        elif (not action_requested(query)
              and re.search(r'\b(?:computer|pc|laptop|machine|desktop|system|box|apps?|clicks?|screen|resources?)\b', query)
              and re.search(r'\b(?:unresponsive|responsiveness|delayed?|slow\w*|lag\w*|stall\w*|hang\w*|freez\w*|hesitat\w*|bogg\w*|drag\w*|chugg\w*|stutter\w*|hitch\w*|sluggish|longer)\b', query)):
            names = ('system.performance', 'system.stats', 'process.top_cpu',
                     'process.top_memory', 'process.top_disk_io', 'gpu.top_processes')[:self.max_tools]
        else:
            matches = self.discovery.search(query, limit=8)
            # Lexical fallback needs meaningful evidence, not question words.
            strong = [m for m in matches if m.score >= 20 and len(set(m.matched_terms) - {'intent route', 'verification companion'}) >= 2]
            if not strong:
                strong = [m for m in self.discovery.search(query, limit=8, extensions_only=True)
                          if m.score >= 8 and len(m.matched_terms) >= 2]
            names = tuple(m.capability.name for m in strong[:2])
            if not names:
                names = tuple(row.name for row in self._retrieval_candidates(intent_text(original)))
            if action_requested(query):
                actions = self._retrieval_actions(planning_text)
                eligible_actions = {row.name for row in actions}
                if names and set(names) <= eligible_actions:
                    # Preserve the original strong action discovery order.
                    retrieved_action = True
                elif actions and (not names or all(classification(self.registry.get(name)) == 'read_only' for name in names)):
                    # A read cannot satisfy an explicit action. Fall back only
                    # when original discovery produced no eligible action.
                    names = tuple(row.name for row in actions)
                    retrieved_action = True
        # Resolvers bind exact arguments and actions; generic retrieval cannot
        # widen them. Weak read-only menus may retain bounded alternatives when
        # stronger metadata evidence supports a different capability.
        if (names and request is None and not action_requested(query) and diagnostic is None
                and all(self._allowed(self.registry.get(name))
                        and classification(self.registry.get(name)) == 'read_only' for name in names)):
            from hanni.tools.discovery import index_for
            candidates = self._retrieval_candidates(intent_text(original))
            ranked = index_for(self.registry).rank(intent_text(original), eligible=names)
            current_score = ranked[0].score if ranked else 0
            index = index_for(self.registry)
            current_matched = set().union(*(row.matched_terms for row in ranked))
            alternatives = []
            for row in candidates:
                if row.name in names:
                    continue
                novel = set(row.matched_terms) - current_matched
                shared = set(row.matched_terms) & current_matched
                novel_weight = sum(index.idf.get(term, 0) for term in novel)
                # A weak literal match alone is not a reason to widen a menu.
                # Distinct, uncommon evidence may justify an alternative;
                # common words like 'running' or 'status' cannot fill slots.
                supported = (row.coverage >= 0.5 and len(row.matched_terms) >= 3
                             and row.score >= current_score * 1.35)
                complementary = (novel_weight >= 3.5 and row.score >= current_score * 0.8
                                 and len(row.matched_terms) >= 2)
                # A collection menu may match only the object word, while its
                # precise entity read has strong identifier/field evidence.
                # Registered namespace relationship permits that alternative;
                # unrelated families still require the original shared evidence.
                same_namespace = any(name.rsplit('.', 1)[0] == row.name.rsplit('.', 1)[0]
                                     for name in names)
                related = len(shared) >= 2 or (same_namespace and len(shared) >= 1 and supported)
                duplicate = any(
                    tuple(name.split('.')[-2:]) == tuple(row.name.split('.')[-2:]) for name in names
                )
                if related and not duplicate and (supported or complementary):
                    alternatives.append(row.name)
            if alternatives:
                names = tuple(dict.fromkeys((*names,*alternatives)))[:self.max_tools]
        # Only a clear creation resolver can expose calendar writes.
        names = tuple(n for n in names if n != 'google_calendar.create' or request is not None)
        if action_requested(query) and not menu and request is None and not prototype_override and not retrieved_action:
            if re.fullmatch(r'(?:pause|resume|continue|unpause|play|skip|next|back|previous)(?:\s+it)?', query):
                return RoutingDecision((), 'clarification', 'low', ('media',), (), ())
            return RoutingDecision((), 'blocked', 'high', (), (), ())
        if (action_requested(query) and names == ('hanni.permissions',)
                and not re.match(r'^(?:can|could|may|is|are|do|does|would|what|which|how)\b', original, re.I)):
            return RoutingDecision((), 'blocked', 'high', ('hanni',), (), ('hanni.permissions',))
        blocked = tuple(n for n in names if not self._allowed(self.registry.get(n)))
        if blocked and (menu or request):
            return RoutingDecision((), 'blocked', 'high', tuple(dict.fromkeys(family_of(n) for n in names)), (), blocked)
        names = tuple(n for n in names if n not in blocked)
        for name in names:
            definition = self.registry.get(name)
            args = request.arguments if request and request.name == name else {}
            if not self._google_write_enabled(definition, args):
                return RoutingDecision((), 'blocked', 'high', ('google',), (), (name,))
        # An action verb without a matching action must not substitute a read.
        if (action_requested(query) and names and all(classification(self.registry.get(n)) == 'read_only' for n in names)
                and not all(n.startswith(('text.', 'calc.', 'unit.', 'random.', 'id.', 'gmail.', 'hanni.permissions')) for n in names)):
            # Pure computations (convert, generate) are safe; open/run/etc are not.
            return RoutingDecision((), 'blocked', 'high', (), (), ())
        drive_mention = re.search(r'\b([a-z])(?::|\s+drive)\b', query, re.I)
        file_location = re.search(r'\b(?:in|under|inside)\s+(?:my\s+)?(downloads|documents|desktop)\b', original, re.I)
        file_root = str(Path.home() / file_location.group(1).title()) if file_location else ''
        selected = tuple(self._as_tool(self.registry.get(n), fixed_arguments=(
                             request.arguments if request and request.name == n else
                             {'root': file_root} if n == 'file.search' else
                             {'drive': drive_mention.group(1).upper()} if n == 'disk.usage' and drive_mention else None))
                         for n in names[:self.max_tools])
        account = requested_account(original)
        if account:
            from dataclasses import replace
            selected = tuple(replace(tool, fixed_arguments={**tool.fixed_arguments, 'account': account})
                             if tool.capability_id.startswith(('google_calendar.', 'gmail.', 'email.')) else tool
                             for tool in selected)
        families = tuple(dict.fromkeys(family_of(n) for n in names))
        subintents = ((prototype.name,) if prototype_override else
                      (diagnostic.name,) if diagnostic is not None and any(diagnostic.allows(n) for n in names) else ())
        return RoutingDecision(selected, 'tools' if selected else 'clarification', 'high' if request or menu or diagnostic else 'low',
                               families, subintents, (), tuple((name,) for name in observations))

    def select_tools(self, query: str, *, history=(), now: datetime | None = None) -> tuple[McpTool, ...]:
        return self.route(query, history=history, now=now).tools

    @staticmethod
    def _guard_credential_paths(capability_id, arguments):
        """Model-facing reads and mutations cannot expose credential sources.

        Manual registry/CLI operations retain their original owner authority.
        A configured write capability is not permission to launder a credential
        into a differently named file or archive for a subsequent model read.
        """
        from hanni.tools.base import ToolPermissionError
        if not capability_id.startswith(('file.', 'folder.', 'archive.')):
            return
        keys = ('path', 'source', 'destination', 'left', 'right', 'root', 'archive')
        if capability_id == 'file.locate': keys += ('name',)
        if any(is_sensitive_path(arguments.get(key)) for key in keys):
            raise ToolPermissionError('Credential file content is unavailable to the assistant.')
        if capability_id not in {'file.move', 'archive.zip'}:
            return
        source = arguments.get('source')
        if not isinstance(source, str) or not source.strip():
            return
        root = Path(source).expanduser().resolve()
        if not root.is_dir():
            return
        deadline, count = time.monotonic() + 30, 0
        def unreadable(error):
            raise ToolPermissionError('The source folder could not be checked for credential paths.')
        for current, dirs, names in os.walk(root, onerror=unreadable, followlinks=False):
            for name in (*dirs, *names):
                count += 1
                if count > 20000 or time.monotonic() >= deadline:
                    raise ToolPermissionError('The source folder exceeds the credential-path inspection limit.')
                if is_sensitive_path(Path(current) / name):
                    raise ToolPermissionError('Credential file content is unavailable to the assistant.')

    def prepare_call(self, tool: McpTool, arguments: Mapping[str, Any], *, artifact_root=None,
                     validate_arguments=True):
        """Prepare exact workflow arguments through the original host boundaries.

        Preparation grants no execution authority. The sole additional preview
        is file.write inside the caller-owned artifact root; dispatch still needs
        a trusted workflow scope and the original registry permission checks.
        """
        from hanni.tools.base import ToolPermissionError, ToolValidationError
        from hanni.workflows.policy import artifact_write
        definition = self.registry.get(tool.capability_id)
        if tool.definition_hash != definition.external_definition_hash:
            raise ToolPermissionError('Tool definition changed; discover and approve it again.')
        merged = dict(arguments)
        if tool.capability_id == 'email.search' and 'plan' in arguments and 'plan' not in tool.fixed_arguments:
            raise ToolValidationError('Email plans must be resolved by HANNI.')
        if tool.capability_id in {'google_calendar.agenda', 'google.calendar.events', 'google.calendar.availability'}:
            for key in ('availability_at', 'availability_start', 'availability_end',
                        'time_min', 'time_max', 'academic_concept', 'course', 'first_only',
                        'temporal_source', 'followup_context_used'):
                if key in arguments and key not in tool.fixed_arguments:
                    raise ToolValidationError(f'{key} must be resolved by HANNI before the Calendar call.')
        merged.update(tool.fixed_arguments)
        if tool.capability_id == 'app.open':
            from hanni.workflows.policy import pin_application
            merged['app'] = pin_application(merged.get('app'))
        if tool.capability_id.startswith(('file.', 'folder.', 'archive.')):
            for key in ('path', 'source', 'destination', 'left', 'right', 'root'):
                if isinstance(merged.get(key), str) and merged[key].strip():
                    merged[key] = str(Path(merged[key]).expanduser().resolve())
        from hanni.tools.google_routing import google_service
        if google_service(tool.capability_id) and 'account' not in tool.fixed_arguments:
            merged.pop('account', None)
        if not self._allowed(definition) and not artifact_write(definition, merged, artifact_root):
            raise ToolPermissionError('This HANNI assistant session exposes read-only MCP tools only.')
        if google_service(tool.capability_id) and definition.side_effect not in {None, 'read'}:
            if not tool.fixed_arguments or not self._google_write_enabled(definition, merged):
                raise ToolPermissionError('This Google write requires an explicit owner request, the service write scope, and session policy approval.')
        self._guard_credential_paths(tool.capability_id, merged)
        if validate_arguments:
            merged = definition.validate_arguments(merged)
        from hanni.reliability.context import current_correlation_id
        return ToolRequest(tool.capability_id, merged, actor_profile='owner', confirmed=False,
                           source='tool.workflow.preview', correlation_id=current_correlation_id())

    def call(self, tool: McpTool, arguments: Mapping[str, Any], *, workflow_authority=None) -> dict[str, Any]:
        """Execute one already-selected MCP tool through the validated registry."""
        if workflow_authority is not None:
            # This keyword is never sourced from model tool-call JSON. Default
            # interactive/session calls below retain their original behavior.
            from dataclasses import replace
            from hanni.workflows.policy import WorkflowAuthority
            try:
                if not isinstance(workflow_authority, WorkflowAuthority):
                    raise PermissionError('Workflow execution requires trusted authority.')
                request = self.prepare_call(tool, arguments,
                                            artifact_root=workflow_authority.artifact_root)
                definition = self.registry.get(tool.capability_id)
                workflow_authority.validate(definition, request.arguments)
                request = replace(request, actor_profile=workflow_authority.actor_profile,
                                  confirmed=workflow_authority.confirmed, source='tool.workflow',
                                  expected_definition_hash=workflow_authority.definition_hash,
                                  expected_definition=definition,
                                  execution_guard=workflow_authority.execution_guard)
                result = self.registry.capabilities.call(
                    request, background=workflow_authority.mode == 'background')
                return redact_value(result.to_dict())
            except Exception as exc:
                return redact_value({'name': tool.capability_id, 'ok': False, 'message': str(exc),
                                     'data': {}, 'error': error_contract(exc)})
        try:
            definition = self.registry.get(tool.capability_id)
        except Exception as exc:
            return {'name': tool.capability_id, 'ok': False, 'message': str(exc), 'data': {}, 'error': error_contract(exc)}
        if tool.definition_hash and tool.definition_hash != definition.external_definition_hash:
            return {'name': tool.capability_id, 'ok': False, 'message': 'The selected tool definition changed. Retrieve its current definition.',
                    'data': {}, 'error': {'code': 'DEFINITION_CHANGED', 'retryable': False}}
        if not self._allowed(definition):
            return {
                "name": tool.capability_id,
                "ok": False,
                "message": "This HANNI assistant session exposes read-only MCP tools only.",
                "data": {},
                "error": {"code": "PERMISSION_DENIED", "message": "read-only MCP session", "retryable": False},
            }
        try:
            merged = dict(arguments)
            if tool.capability_id == 'email.search' and 'plan' in arguments and 'plan' not in tool.fixed_arguments:
                return {'name': tool.capability_id, 'ok': False, 'message': 'Email plans must be resolved by HANNI.',
                        'data': {}, 'error': {'code': 'INVALID_ARGUMENTS', 'retryable': False}}
            if tool.capability_id in {'google_calendar.agenda', 'google.calendar.events', 'google.calendar.availability'}:
                for key in ('availability_at', 'availability_start', 'availability_end',
                            'time_min', 'time_max', 'academic_concept', 'course', 'first_only',
                            'temporal_source', 'followup_context_used'):
                    if key in arguments and key not in tool.fixed_arguments:
                        return {'name': tool.capability_id, 'ok': False,
                                'message': f'{key} must be resolved by HANNI before the Calendar call.',
                                'data': {}, 'error': {'code': 'INVALID_ARGUMENTS', 'retryable': False}}
            # Deterministically resolved context wins over model-supplied values.
            merged.update(tool.fixed_arguments)
            from hanni.tools.google_routing import google_service
            if google_service(tool.capability_id) and 'account' not in tool.fixed_arguments:
                # An unqualified request uses the configured account. The model
                # cannot widen it to all accounts or choose a different label.
                merged.pop('account', None)
            if google_service(tool.capability_id) and definition.side_effect not in {None, 'read'}:
                if not tool.fixed_arguments or not self._google_write_enabled(definition, merged):
                    return {'name': tool.capability_id, 'ok': False,
                            'message': 'This Google write requires an explicit owner request, the service write scope, and session policy approval.',
                            'data': {'state': 'permission_denied'}, 'error': {'code': 'PERMISSION_DENIED', 'retryable': False}}
            # File content is useful, but credential files must never be passed
            # through to the resident model. The check follows resolved links.
            self._guard_credential_paths(tool.capability_id, merged)
            from hanni.reliability.context import current_correlation_id
            from hanni.core.response_stream import cancellation_guard
            result = self.registry.execute(ToolRequest(
                tool.capability_id,
                merged,
                actor_profile="owner",
                confirmed=False,
                source="mcp.natural_language" if tool.fixed_arguments else "mcp.model",
                correlation_id=current_correlation_id(),
                execution_guard=cancellation_guard(),
            ))
            return redact_value(result.to_dict())
        except Exception as exc:  # exact safe contract is returned to the model
            error = error_contract(exc)
            # Only explicitly opted-in built-in observations can be repeated.
            # External server metadata never grants replay authority.
            effective_read = (definition.side_effect == 'read' or
                              definition.side_effect is None and definition.permission_level == definition.risk_level == 0)
            if (isinstance(exc,TimeoutError) and definition.retry_safe
                    and effective_read and definition.permission_level == 0
                    and definition.risk_level <= 1 and not definition.external_definition_hash
                    and not definition.name.startswith('mcp.')):
                error['retryable'] = True
            return redact_value({
                "name": tool.capability_id,
                "ok": False,
                "message": str(exc),
                "data": {},
                "error": error,
            })
