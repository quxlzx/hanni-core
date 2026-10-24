"""Versioned learned procedures, shadowing bundled skills only after approval."""
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from .skills import load_skills


class SkillStore:
    def __init__(self, root):
        self.root = Path(root)
        self.learned = self.root / 'skills'

    def catalog(self):
        bundled = load_skills(metadata_only=True)
        learned = load_skills(str(self.learned), metadata_only=True)
        return list({s['name']: s for s in [*bundled, *learned]}.values())

    def read(self, name, resource=None):
        skill = next((s for s in self.catalog() if s['name'] == name), None)
        if not skill:
            raise ValueError('Skill not found.')
        path = Path(skill['path'])
        if resource:
            target = (path.parent / resource).resolve()
            if not target.is_relative_to(path.parent.resolve()) or target.suffix.lower() != '.md':
                raise ValueError('Skill reference must be a Markdown file inside the skill.')
            path = target
        raw = path.read_text(encoding='utf-8')
        return {'name': name, 'content': raw[:24000], 'truncated': len(raw) > 24000,
                'revision': hashlib.sha256(raw.encode()).hexdigest()}

    def save(self, *, name, description, instructions, triggers, expected_revision, verification, correction):
        import yaml
        from ..logs.redaction import redact_text
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', name):
            raise ValueError('Use a skill name of lowercase letters, digits and hyphens.')
        if not all(isinstance(s, str) and s.strip() for s in (description, instructions, verification, correction)):
            raise ValueError('Description, procedure, verification evidence and correction are required.')
        raw = '---\n' + yaml.safe_dump({'name': name, 'description': description,
                  'metadata': {'hanni': {'triggers': triggers}}}, sort_keys=False) + '---\n\n' + instructions.strip() + '\n'
        if len(raw) > 24000 or redact_text(raw) != raw:
            raise ValueError('Skill exceeds 24KB or contains credential-like content.')
        self.learned.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.root / 'skill-revisions.sqlite3', timeout=10) as db:
            db.execute('CREATE TABLE IF NOT EXISTS revisions(name TEXT, revision TEXT, content TEXT, verification TEXT, correction TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)')
            db.execute('BEGIN IMMEDIATE')
            try:
                current = self.read(name)['revision']
            except ValueError:
                current = ''
            if current != expected_revision:
                raise ValueError('Skill changed. Read its current revision before saving.')
            folder = self.learned / name
            folder.mkdir(exist_ok=True)
            if not folder.resolve().is_relative_to(self.learned.resolve()):
                raise ValueError('Skill directory escapes learned procedures.')
            revision = hashlib.sha256(raw.encode()).hexdigest()
            db.execute('INSERT INTO revisions(name,revision,content,verification,correction) VALUES(?,?,?,?,?)',
                       (name, revision, raw, redact_text(verification), redact_text(correction)))
            fd, temp = tempfile.mkstemp(dir=folder, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
                    stream.write(raw)
                os.replace(temp, folder / 'SKILL.md')
            finally:
                if Path(temp).exists():
                    Path(temp).unlink()
        return {'ok': True, 'data': {'name': name, 'revision': revision, 'verified_by_runtime': False},
                'message': 'Procedure saved for future matching tasks. Model weights were not changed.'}
