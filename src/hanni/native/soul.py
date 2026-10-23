"""Persona loading: SOUL.md is the soul file that makes HANNI HANNI."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_SOUL = Path(__file__).resolve().parents[3] / "soul" / "SOUL.md"


def load_soul(path: str | None = None) -> str:
    """Persona text from HANNI_SOUL (env) or the repo's data/SOUL.md; '' if absent."""
    target = Path(path or os.environ.get("HANNI_SOUL") or DEFAULT_SOUL)
    try:
        return target.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def build_system_prompt(base: str, soul: str = "", skills_text: str = "") -> str:
    parts = []
    if soul:
        parts.append("## Persona (authoritative identity)\n" + soul)
    parts.append("## Operating contract\n" + base)
    if skills_text:
        parts.append("## Relevant learned procedures (follow when applicable)\n" + skills_text)
    return "\n\n".join(parts)
