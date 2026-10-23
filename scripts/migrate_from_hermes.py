#!/usr/bin/env python3
"""One-time migration: Hermes memories + skills into HANNI-Core native form.

- ~/.hermes/memories/{MEMORY,USER}.md  -> MemoryStore at <bridge-root>/memory.sqlite3
- ~/.hermes/skills/**/SKILL.md (+ support dirs) -> HANNI-core/skills/<name>/

Idempotent: memories dedupe via the store's fingerprint; skills overwrite.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hanni.memory.store import MemoryStore  # noqa: E402

HERMES = Path.home() / ".hermes"
REPO = Path(__file__).resolve().parents[1]
SUPPORT_DIRS = ("references", "templates", "scripts", "assets")


def migrate_memories(store_path: Path) -> tuple[int, int]:
    from hanni.memory.store import MemoryConflictError
    store = MemoryStore(store_path)
    added = skipped = 0
    for name, source in (("MEMORY.md", "owner_explicit"), ("USER.md", "owner_explicit")):
        path = HERMES / "memories" / name
        if not path.is_file():
            continue
        for entry in re.split(r"\n?\u00a7\n?", path.read_text(encoding="utf-8")):
            entry = entry.strip()
            if len(entry) < 8:
                continue
            try:
                store.remember(entry, source=source)
                added += 1
            except MemoryConflictError:
                skipped += 1
    return added, skipped


def migrate_skills(dest: Path) -> int:
    count = 0
    src_root = HERMES / "skills"
    if not src_root.is_dir():
        return 0
    for skill_md in sorted(src_root.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        name = re.sub(r"[^a-z0-9_-]+", "-", skill_dir.name.lower()).strip("-")
        if not name:
            continue
        target = dest / name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_md, target / "SKILL.md")
        for sub in SUPPORT_DIRS:
            src = skill_dir / sub
            if src.is_dir():
                shutil.copytree(src, target / sub, dirs_exist_ok=True)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-root", default=str(Path.home() / "hanni-hermes-bridge" / "state"))
    parser.add_argument("--skills-dest", default=str(REPO / "skills"))
    args = parser.parse_args()
    root = Path(args.bridge_root)
    root.mkdir(parents=True, exist_ok=True)
    added, skipped = migrate_memories(root / "memory.sqlite3")
    skills = migrate_skills(Path(args.skills_dest))
    print(f"memories: {added} added, {skipped} already present -> {root/'memory.sqlite3'}")
    print(f"skills:   {skills} migrated -> {args.skills_dest}")


if __name__ == "__main__":
    main()
