"""Self-diagnostic capabilities: what H.A.N.N.I. can do and how it is running.

These let the Supervisor answer questions about the runtime itself from
measured state instead of from model recall. ``hanni.capabilities`` is
introspection only: listing a capability never grants or widens authority, and
every listed capability still passes the same validation, permission,
confirmation, emergency-stop, and audit gates at execution time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping

from hanni.config.schema import AppConfig
from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult


@dataclass(slots=True)
class RegistryHolder:
    """Late-bound reference to the registry these capabilities describe."""

    registry: Any = field(default=None)

    def require(self) -> Any:
        if self.registry is None:
            raise RuntimeError("capability introspection is not wired to a registry")
        return self.registry


def _capabilities_handler(holder: RegistryHolder):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        from hanni.tools.capabilities import LocalCapabilityDiscovery, capability_catalog

        registry = holder.require()
        goal = str(args.get("goal", "") or "").strip()
        category = str(args.get("category", "") or "").strip().casefold()
        limit = max(1, min(int(args.get("limit", 25)), 200))
        if goal:
            matches = LocalCapabilityDiscovery(registry).search(goal, limit=min(limit, 32))
            rows = [{"name": match.capability.name, "description": match.capability.description,
                     "category": match.capability.category, "risk_level": match.capability.risk_level,
                     "side_effect": match.capability.side_effect, "score": match.score,
                     "matched_terms": list(match.matched_terms)} for match in matches]
            message = (f"{len(rows)} capability/capabilities look relevant to '{goal}'"
                       + (f"; best match {rows[0]['name']}." if rows else "; nothing matched."))
        else:
            catalog = capability_catalog(registry)
            rows = [{"name": cap.name, "description": cap.description, "category": cap.category,
                     "risk_level": cap.risk_level, "side_effect": cap.side_effect}
                    for cap in catalog if not category or cap.category == category]
            categories = sorted({cap.category for cap in catalog})
            message = (f"{len(rows)} registered capability/capabilities"
                       + (f" in category '{category}'." if category else
                          f" across {len(categories)} categories: {', '.join(categories)}."))
        return ToolResult("hanni.capabilities", True, message,
                          {"capabilities": rows[:limit], "total": len(rows), "goal": goal, "category": category,
                           "note": "listing is advisory; execution still passes permission and confirmation checks"})
    return handler


def _audit_handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    limit = max(1, min(int(args.get("limit", 20)), 200))
    only_failures = bool(args.get("only_failures", False))
    tool_name = str(args.get("tool", "") or "").strip()
    rows = context.audit.tail(limit=min(limit * 5, 500))
    if tool_name:
        rows = [row for row in rows if row.get("tool") == tool_name]
    if only_failures:
        rows = [row for row in rows if not row.get("ok")]
    rows = rows[-limit:]
    failures = sum(1 for row in rows if not row.get("ok"))
    return ToolResult("hanni.audit_tail", True,
                      f"{len(rows)} recent audited action(s), {failures} failed."
                      + (f" Most recent: {rows[-1].get('tool')} at {rows[-1].get('timestamp')}." if rows else ""),
                      {"entries": rows, "count": len(rows), "failures": failures})


def _stop_state_handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    active = bool(context.emergency_stop.is_tripped)
    return ToolResult("hanni.stop_state", True,
                      "Emergency stop is ACTIVE; new tool execution is blocked until it is cleared."
                      if active else "Emergency stop is clear; capabilities can run normally.",
                      {"stopped": active})


def _permissions_handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    permissions = context.permissions
    profiles = getattr(permissions, "profiles", {}) or {}
    rows = []
    for name, profile in (profiles.items() if isinstance(profiles, dict) else []):
        rows.append({"profile": name,
                     "max_auto_approve_level": getattr(profile, "max_auto_approve_level", None),
                     "chat_only": bool(getattr(profile, "chat_only", False))})
    return ToolResult("hanni.permissions", True,
                      "Level 3 always requires explicit owner confirmation; "
                      f"{len(rows) or 'the configured'} profile(s) auto-approve up to their own limit.",
                      {"profiles": rows, "level_3_always_confirmed": True})


def _model_status_handler(config: AppConfig):
    def handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
        from hanni.models.registry import create_client, model_spec

        model_id = str(args.get("model_id", "") or "").strip() or None
        spec = model_spec(config, model_id)
        client = create_client(config, model_id)
        health = client.health()
        payload = health.to_dict() if hasattr(health, "to_dict") else {"health": str(health)}
        reachable = bool(payload.get("ok", payload.get("reachable", False)))
        placement = _owned_model_placement(config, spec) if reachable else _unverified_placement(spec)
        return ToolResult("model.status", reachable,
                          f"Model '{spec.id}' is "
                          f"{'reachable' if reachable else 'not reachable'} at {client.health_url}."
                          + (f" Verified on {placement['selected_device_name'] or placement['selected_device_id']}."
                             if placement['placement_verified'] else " GPU placement is unverified."),
                          {"model_id": spec.id,
                           "model_file": spec.model_file, "quantization": spec.quantization,
                           "context_length": spec.context_length,
                           "endpoint": client.health_url, "reachable": reachable, "health": payload,
                           **placement})
    return handler


def _unverified_placement(spec):
    return {"selected_device_id": None, "selected_device_name": None,
            "gpu_selection_mode": spec.gpu_selection, "placement_verified": False,
            "offloaded_layers": None}


def _owned_model_placement(config, spec):
    """Report GPU placement only from an owned, healthy launch and offload log."""
    from hanni.models.manager import current
    from hanni.models.runtime import gpu_inventory, load_gpu_routing

    unknown = _unverified_placement(spec)
    manager = current(spec)
    entry = manager.entries.get(spec.id) if manager else None
    if not entry or entry.process is None or entry.state not in {"READY", "BUSY"}:
        return unknown
    if entry.process.poll() is not None:
        return unknown
    command = list(entry.command)
    if "--device" not in command:
        return unknown
    device_index = command.index("--device") + 1
    if device_index >= len(command):
        return unknown
    device_id = command[device_index]
    if not device_id or device_id == "none":
        return unknown
    log_path = config.paths.data_dir / f"dashboard-{spec.id}.log"
    try:
        log_text = log_path.read_text(encoding="utf-8", errors="replace")[-50000:]
    except OSError:
        return unknown
    offload = re.search(r"offloaded\s+(\d+)/(\d+)\s+layers to GPU", log_text, re.I)
    if not offload or int(offload.group(1)) <= 0:
        return unknown
    try:
        names = {device.id: device.name for device in gpu_inventory()}
    except (OSError, RuntimeError, ValueError):
        names = {}
    try:
        routing = load_gpu_routing(config.paths.data_dir / "gpu-routing.json")
        mode = routing["mode"]
    except (OSError, ValueError, KeyError):
        mode = spec.gpu_selection
    return {"selected_device_id": device_id, "selected_device_name": names.get(device_id),
            "gpu_selection_mode": mode, "placement_verified": True,
            "offloaded_layers": int(offload.group(1))}


def _gpu_memory_handler(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    from hanni.tools.system import definitions as system_definitions

    stats = next((item for item in system_definitions() if item.name == "system.stats"), None)
    if stats is None:  # pragma: no cover - registry always provides system.stats
        raise RuntimeError("system.stats capability is unavailable")
    result = stats.handler({}, context, request)
    gpus = list(result.data.get("gpus", []) or [])
    rows = []
    for gpu in gpus:
        total = float(gpu.get("memory_total_mb") or 0) / 1024
        used = float(gpu.get("memory_used_mb") or 0) / 1024
        rows.append({"name": gpu.get("name", ""), "total_gb": round(total, 2), "used_gb": round(used, 2),
                     "free_gb": round(max(0.0, total - used), 2),
                     "percent_used": round(used / total * 100, 1) if total else 0.0})
    headroom = round(sum(row["free_gb"] for row in rows), 2)
    return ToolResult("gpu.memory", True,
                      f"{len(rows)} GPU(s); about {headroom} GB of VRAM free in total."
                      if rows else "No GPU telemetry is available on this machine.",
                      {"gpus": rows, "free_gb_total": headroom})


def definitions(config: AppConfig, holder: RegistryHolder) -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("hanni.capabilities", "List H.A.N.N.I.'s own registered capabilities, or rank the ones relevant to a stated goal. Answers 'what can you do' and 'which tool would you use'.",
                       0, 0, {"goal": str, "category": str, "limit": int},
                       {"capabilities": "array", "total": "integer"}, _capabilities_handler(holder),
                       side_effect="read",
                       tags=("capabilities", "tools", "abilities", "can", "help", "self", "what", "do", "which"),
                       aliases=("what can you do", "what tools do you have", "can you", "which tool would you use")),
        ToolDefinition("hanni.audit_tail", "Read recent entries from H.A.N.N.I.'s own tool audit log, optionally only failures or one capability.",
                       0, 0, {"limit": int, "only_failures": bool, "tool": str},
                       {"entries": "array", "count": "integer", "failures": "integer"}, _audit_handler,
                       side_effect="read",
                       tags=("audit", "log", "history", "did", "recent", "actions", "failed", "self"),
                       aliases=("what did you just do", "show your audit log", "what failed")),
        ToolDefinition("hanni.stop_state", "Report whether the deterministic emergency stop is currently active.",
                       0, 0, {}, {"stopped": "boolean"}, _stop_state_handler,
                       side_effect="read",
                       tags=("stop", "emergency", "halted", "blocked", "safe", "state", "self"),
                       aliases=("are you stopped", "is safe mode on")),
        ToolDefinition("hanni.permissions", "Report the permission profile boundaries H.A.N.N.I. enforces outside the model.",
                       0, 0, {}, {"profiles": "array", "level_3_always_confirmed": "boolean"}, _permissions_handler,
                       side_effect="read",
                       tags=("permission", "allowed", "confirm", "risk", "level", "authority", "self"),
                       aliases=("what are you allowed to do", "do you need permission")),
        ToolDefinition("model.status", "Read HANNI's active model and endpoint health with no arguments. Report GPU placement only when HANNI owns the launch and verified offload; an external server's adapter is unknown.",
                       0, 0, {}, {"model_id": "string", "endpoint": "string", "reachable": "boolean",
                                                "selected_device_name": "string|null", "placement_verified": "boolean"},
                       _model_status_handler(config), timeout_seconds=30, side_effect="read",
                       tags=("model", "llm", "supervisor", "server", "loaded", "reachable", "slow", "self"),
                       aliases=("is the model running", "why are you slow", "is llama up")),
        ToolDefinition("gpu.memory", "Report per-GPU VRAM used and free, for deciding whether another model can be loaded.",
                       0, 0, {}, {"gpus": "array", "free_gb_total": "number"}, _gpu_memory_handler,
                       side_effect="read",
                       tags=("gpu", "vram", "memory", "free", "headroom", "model", "load"),
                       aliases=("how much vram is free", "can i load another model")),
    )
