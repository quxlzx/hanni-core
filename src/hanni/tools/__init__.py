"""Validated local computer tools (Milestone 6)."""

from hanni.tools.audit import ToolAuditLog
from hanni.tools.base import (
    ConfirmationRequired,
    ToolContext,
    ToolDefinition,
    ToolError,
    ToolPermissionError,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    ToolValidationError,
    UnknownToolError,
)
from hanni.tools.registry import build_default_registry
from hanni.tools.router import VoiceToolMatch, VoiceToolRouter
from hanni.tools.session import ToolAwareSession

__all__ = [
    "ConfirmationRequired", "ToolAuditLog", "ToolContext", "ToolDefinition", "ToolError",
    "ToolPermissionError", "ToolRegistry", "ToolRequest", "ToolResult", "ToolValidationError",
    "UnknownToolError", "VoiceToolMatch", "VoiceToolRouter", "ToolAwareSession", "build_default_registry",
]
