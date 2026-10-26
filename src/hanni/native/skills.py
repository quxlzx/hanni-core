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
Standard skill frontmatter can put HANNI trigger lists in metadata.hanni.triggers.
"""
from __future__ import annotations

import os
import math
import re
from pathlib import Path

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def load_skills(directory: str | None = None, *, metadata_only=False) -> list[dict]:
    default = Path(__file__).resolve().parents[3] / "soul" / "skills"
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
            if metadata_only:
                # Read only the YAML header for discovery, not every procedure.
                with path.open(encoding='utf-8') as stream:
                    lines = [stream.readline(4096)]
                    if lines[0].strip() == '---':
                        for _ in range(80):
                            line = stream.readline(4096)
                            lines.append(line)
                            if not line or line.strip() == '---':
                                break
                raw = ''.join(lines) + '\n'
            else:
                raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = {}, raw
        match = FRONT.match(raw)
        if match:
            body = raw[match.end():]
            import yaml
            try:
                parsed = yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                continue
            if isinstance(parsed, dict):
                meta = parsed
        name = meta.get("name") or path.stem
        description = str(meta.get('description') or '')
        metadata = meta.get('metadata')
        hanni = metadata.get('hanni') if isinstance(metadata, dict) else None
        raw_triggers = meta.get('triggers') or (hanni.get('triggers') if isinstance(hanni, dict) else None) or []
        if isinstance(raw_triggers, str):
            raw_triggers = re.split(r'[,;]', raw_triggers)
        if not isinstance(raw_triggers, list):
            raw_triggers = []
        triggers = [str(t).strip().lower() for t in raw_triggers if str(t).strip()]
        if not triggers:
            triggers = re.findall(r"[a-z0-9/]{4,}", (description + " " + str(name)).lower())
        skills.append({"name": str(name), "description": description,
                       "triggers": triggers, "path": str(path.resolve()),
                       **({} if metadata_only else {'body': body.strip()})})
    return skills


STOP_WORDS = frozenset('a an and are as at be can check could do for from get give have help i in inspect is it me my of on or please read review see show some tell that the there this to use want what whats when will with would you your'.split())


def skill_terms(text):
    return {word[:-1] if word.endswith('s') and len(word) > 4 else word
            for word in re.findall(r'[a-z][a-z0-9]{2,}', text.casefold()) if word not in STOP_WORDS}


def search_skills(skills, query, *, limit=6):
    """Rank metadata without loading procedure bodies or contacting a provider."""
    words = skill_terms(query)
    if not words: return []
    documents = [skill_terms(' '.join([s['name'], s.get('description', ''), *s['triggers']])) for s in skills]
    weights = {w: math.log(1 + len(skills) / (1 + sum(w in doc for doc in documents))) for w in words}
    ranked = []
    for skill, document in zip(skills, documents):
        overlap = words & document
        exact = [t for t in skill['triggers'] if re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', query, re.I)]
        if not overlap and not exact: continue
        name_words = skill_terms(skill['name'])
        score = sum(weights[w] * (4 if w in name_words else 1) for w in overlap)
        score += sum(6 + min(len(t), 80) / 20 for t in exact)
        extension = any(re.fullmatch(r'\.[a-z0-9]+', t) for t in exact)
        ranked.append({**skill, 'score': round(score, 3), 'extension_match': extension})
    ranked.sort(key=lambda s: (-s['extension_match'], -s['score'], s['name']))
    return ranked[:max(0, min(limit, 12))]


def render_skills(skills, *, char_budget=6000):
    out, used = [], 0
    for skill in skills:
        separator = 2 if out else 0
        remaining = max(0, char_budget - used - separator)
        body = skill.get('body')
        if body is None:
            raw = Path(skill['path']).read_text(encoding='utf-8')
            front = FRONT.match(raw)
            body = raw[front.end():].strip() if front else raw
        block = f"### skill: {skill['name']}\n{body}"
        if len(block) > remaining: block = block[:remaining]
        if not block: break
        out.append(block)
        used += separator + len(block)
    return '\n\n'.join(out)


def match_skills(skills: list[dict], text: str, *, max_skills: int = 3, char_budget: int = 6000) -> str:
    lowered = text.lower()
    def matches(trigger):
        # File extensions identify a concrete reader; do not match .html inside
        # .htmlx or let a generic "review" skill crowd out the document reader.
        if re.fullmatch(r'\.[a-z0-9]+', trigger):
            return re.search(re.escape(trigger) + r'(?![a-z0-9])', lowered) is not None
        return trigger in lowered
    hits = [s for s in skills if any(matches(t) for t in s["triggers"])]
    hits.sort(key=lambda s: (any(t.startswith('.') and matches(t) for t in s['triggers']),
                             sum(len(t) for t in s['triggers'] if matches(t))), reverse=True)
    return render_skills(hits[:max_skills], char_budget=char_budget)
