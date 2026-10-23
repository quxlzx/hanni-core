"""Markdown skills with keyword loading — the portable procedural memory.

A skill is a markdown file with YAML-ish frontmatter:

    ---
    name: strata-server-ops
    description: benchmarking or tuning the Strata server
    triggers: strata, benchmark, tok/s, gpu
    ---
    body...

Skills are matched against the task prompt by trigger keywords (falling back
to description words) and injected into the system prompt under a char budget.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def load_skills(directory: str | None = None) -> list[dict]:
    default = Path(__file__).resolve().parents[3] / "skills"
    root = Path(directory or os.environ.get("HANNI_SKILLS_DIR") or default)
    skills = []
    if not root.is_dir():
        return skills
    for path in sorted(root.rglob("*.md")):
        if path.name.upper() == "README.md":
            continue
        # nested skills use the SKILL.md convention; support-file markdown
        # (references/, templates/, ...) must not become standalone skills
        if path.parent != root and path.name != "SKILL.md":
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = {}, raw
        match = FRONT.match(raw)
        if match:
            body = raw[match.end():]
            for line in match.group(1).splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip().lower()] = value.strip()
        name = meta.get("name") or path.stem
        triggers = [t.strip().lower() for t in re.split(r"[,;]", meta.get("triggers", "")) if t.strip()]
        if not triggers:
            triggers = [w for w in re.findall(r"[a-z0-9/]{4,}", (meta.get("description", "") + " " + name).lower())]
        skills.append({"name": name, "description": meta.get("description", ""),
                       "triggers": triggers, "body": body.strip()})
    return skills


def match_skills(skills: list[dict], text: str, *, max_skills: int = 3, char_budget: int = 6000) -> str:
    lowered = text.lower()
    hits = [s for s in skills if any(t in lowered for t in s["triggers"])]
    hits.sort(key=lambda s: -sum(len(t) for t in s["triggers"] if t in lowered))
    out, used = [], 0
    for skill in hits[:max_skills]:
        block = f"### skill: {skill['name']}\n{skill['body']}"
        if used + len(block) > char_budget:
            block = block[:max(0, char_budget - used)]
        if not block:
            break
        out.append(block)
        used += len(block)
    return "\n\n".join(out)
