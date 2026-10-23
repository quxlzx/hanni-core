"""Runtime modes."""

from __future__ import annotations

from enum import Enum


class RuntimeMode(str, Enum):
    """Operating mode of the H.A.N.N.I. process."""

    NORMAL = "normal"
    # Entered by emergency stop. No automation, tool execution, or TTS until the
    # owner or the local machine explicitly clears the stop.
    SAFE_MODE = "safe-mode"
