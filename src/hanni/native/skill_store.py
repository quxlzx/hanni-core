"""Versioned procedures, staged diffs, usage and recoverable lifecycle state."""
from contextlib import contextmanager
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from uuid import uuid4
from .skills import load_skills


class SkillStore:
    def __init__(self, root):
        self.root = Path(root)
        self.learned = self.root / 'skills'
        self.root.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS revisions(name TEXT, revision TEXT, content TEXT, verification TEXT, correction TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS skill_meta(name TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'active', pinned INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL, last_view REAL, last_use REAL, last_patch REAL, views INTEGER DEFAULT 0, uses INTEGER DEFAULT 0, patches INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS skill_usage(name TEXT, kind TEXT, source TEXT, PRIMARY KEY(name,kind,source));
                CREATE TABLE IF NOT EXISTS skill_events(id TEXT PRIMARY KEY, name TEXT, action TEXT, revision TEXT, source TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS skill_proposals(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE, payload TEXT, before_text TEXT,
                    after_text TEXT, source TEXT, status TEXT, created REAL, updated REAL);
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.root / 'skill-revisions.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def inventory(self):
        bundled = [{**s, 'origin': 'bundled'} for s in load_skills(metadata_only=True)]
        learned = [{**s, 'origin': 'learned'} for s in load_skills(str(self.learned), metadata_only=True)]
        with self._db() as db:
            metadata = {r['name']: dict(r) for r in db.execute('SELECT * FROM skill_meta')}
        bundled_names = {s['name'] for s in bundled}
        return [{**s, 'overrides_bundled': s['origin'] == 'learned' and s['name'] in bundled_names,
                 **metadata.get(s['name'], {'state': 'active', 'pinned': False, 'views': 0, 'uses': 0, 'patches': 0})}
                for s in {s['name']: s for s in [*bundled, *learned]}.values()]

    def catalog(self):
        return [s for s in self.inventory() if s['state'] != 'archived']

    def _read(self, name, resource=None, *, archived=False):
        skill = next((s for s in (self.inventory() if archived else self.catalog()) if s['name'] == name), None)
        if not skill: raise ValueError('Skill not found.')
        path = Path(skill['path'])
        if resource:
            target = (path.parent / resource).resolve()
            if not target.is_relative_to(path.parent.resolve()) or target.suffix.lower() != '.md':
                raise ValueError('Skill reference must be a Markdown file inside the skill.')
            path = target
        raw = path.read_text(encoding='utf-8-sig')
        return {'name': name, 'content': raw[:24000], 'truncated': len(raw) > 24000,
                'revision': hashlib.sha256(raw.encode()).hexdigest()}

    def read(self, name, resource=None, *, source=None):
        result = self._read(name, resource)
        self.track(name, 'view', source=source)
        return result

    def track(self, name, kind, *, source=None):
        if kind not in {'view', 'use'}: raise ValueError('Unknown skill usage.')
        if not any(s['name'] == name for s in self.inventory()): raise ValueError('Skill not found.')
        with self._db() as db:
            if source and not db.execute('INSERT OR IGNORE INTO skill_usage VALUES(?,?,?)', (name, kind, source)).rowcount: return
            db.execute('INSERT OR IGNORE INTO skill_meta(name,created) VALUES(?,?)', (name, time.time()))
            field, count = ('last_use', 'uses') if kind == 'use' else ('last_view', 'views')
            db.execute(f"UPDATE skill_meta SET {field}=?, {count}={count}+1, state=CASE WHEN state='stale' THEN 'active' ELSE state END WHERE name=?", (time.time(), name))

    @staticmethod
    def render(*, name, description, instructions, triggers, verification, correction, expected_revision):
        import yaml
        from ..logs.redaction import redact_text
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', name):
            raise ValueError('Use a skill name of lowercase letters, digits and hyphens.')
        if not all(isinstance(s, str) and s.strip() for s in (description, instructions, verification, correction)):
            raise ValueError('Description, procedure, verification evidence and correction are required.')
        if (len(description) > 500 or len(instructions) > 20000 or len(verification) > 3000 or len(correction) > 3000
                or not isinstance(expected_revision, str) or len(expected_revision) not in {0, 64}
                or not isinstance(triggers, list) or not 1 <= len(triggers) <= 12
                or any(not isinstance(t, str) or not t.strip() or len(t) > 100 for t in triggers)):
            raise ValueError('Use bounded skill text, trigger keywords and a current revision.')
        raw = '---\n' + yaml.safe_dump({'name': name, 'description': description,
                  'metadata': {'hanni': {'triggers': triggers}}}, sort_keys=False) + '---\n\n' + instructions.strip() + '\n'
        if len(raw) > 24000 or any(redact_text(s) != s for s in (raw, verification, correction)):
            raise ValueError('Skill exceeds 24KB or contains credential-like content.')
        return raw

    def _event(self, db, name, action, revision='', source='owner'):
        db.execute('INSERT INTO skill_events VALUES(?,?,?,?,?,?)', (uuid4().hex, name, action, revision, source[:200], time.time()))

    def _save(self, db, payload, *, source):
        raw = self.render(**payload)
        name = payload['name']
        try: previous = self._read(name, archived=True)
        except ValueError: previous = {'revision': '', 'content': ''}
        if previous['revision'] != payload['expected_revision']:
            raise ValueError('Skill changed. Read its current revision before saving.')
        self.learned.mkdir(parents=True, exist_ok=True)
        folder = self.learned / name
        folder.mkdir(exist_ok=True)
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.learned.resolve()):
            raise ValueError('Skill directory escapes learned procedures.')
        original = next((s for s in load_skills(metadata_only=True) if s['name'] == name), None)
        if original and Path(original['path']).name == 'SKILL.md':
            # A learned override must retain bundled references and support files.
            # Never flatten a package or copy through linked source/target paths.
            import shutil
            base = Path(original['path']).parent
            files = [p for p in base.rglob('*') if p.is_file() and p.name != 'SKILL.md']
            if len(files) > 250 or sum(p.stat().st_size for p in files) > 8 * 1024 * 1024:
                raise ValueError('Skill support package exceeds the copy limit.')
            for path in files:
                target = folder / path.relative_to(base)
                if not path.resolve().is_relative_to(base.resolve()) or not target.resolve().is_relative_to(folder.resolve()):
                    raise ValueError('Skill support path escapes its package.')
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        revision = hashlib.sha256(raw.encode()).hexdigest()
        if previous['revision'] and not db.execute('SELECT 1 FROM revisions WHERE name=? AND revision=?', (name, previous['revision'])).fetchone():
            db.execute('INSERT INTO revisions(name,revision,content,verification,correction) VALUES(?,?,?,?,?)',
                       (name, previous['revision'], previous['content'], 'Previous instruction revision', 'Before update'))
        db.execute('INSERT INTO revisions(name,revision,content,verification,correction) VALUES(?,?,?,?,?)',
                   (name, revision, raw, payload['verification'], payload['correction']))
        fd, temp = tempfile.mkstemp(dir=folder, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream: stream.write(raw)
            os.replace(temp, folder / 'SKILL.md')
        finally:
            if Path(temp).exists(): Path(temp).unlink()
        now = time.time()
        db.execute('INSERT OR IGNORE INTO skill_meta(name,created) VALUES(?,?)', (name, now))
        db.execute("UPDATE skill_meta SET state='active',last_patch=?,patches=patches+1 WHERE name=?", (now, name))
        self._event(db, name, 'updated' if previous['revision'] else 'created', revision, source)
        return {'ok': True, 'data': {'name': name, 'revision': revision, 'verified_by_runtime': False},
                'message': 'Procedure saved for future matching tasks. Model weights were not changed.'}

    def save(self, *, source='agent_tool', **payload):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            return self._save(db, payload, source=source)

    def stage(self, payload, *, source='agent_tool', absorbs=None, replaces=None):
        raw = self.render(**payload)
        try: before = self._read(payload['name'], archived=True)
        except ValueError: before = {'revision': '', 'content': ''}
        if before['revision'] != payload['expected_revision']:
            raise ValueError('Skill changed. Read its current revision before staging.')
        absorbs = absorbs or []
        if not isinstance(absorbs, list) or len(absorbs) > 8: raise ValueError('Choose at most eight overlapping learned skills.')
        for target in absorbs:
            if not isinstance(target, dict) or set(target) != {'name', 'revision'} or target['name'] == payload['name']:
                raise ValueError('Choose exact distinct source skills for consolidation.')
            skill = self._managed(target['name'], target['revision'])
            if skill.get('pinned') or skill['overrides_bundled'] or skill['state'] == 'archived' or any(p.name != 'SKILL.md' for p in Path(skill['path']).parent.iterdir()):
                raise ValueError('Pinned, archived and support-file skills must remain standalone.')
        document = {**payload, 'absorbs': absorbs}
        fingerprint = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = None
            if replaces:
                previous = db.execute('SELECT * FROM skill_proposals WHERE id=?', (replaces[0],)).fetchone()
                if not previous or previous['fingerprint'] != replaces[1] or previous['status'] != 'pending':
                    raise ValueError('The proposal changed. Inspect it before revising.')
                old = json.loads(previous['payload'])
                if old['name'] != payload['name'] or old['expected_revision'] != payload['expected_revision']:
                    raise ValueError('A revision must address the same skill and baseline.')
            if db.execute("SELECT count(*) FROM skill_proposals WHERE status='pending'").fetchone()[0] >= 500:
                raise ValueError('Review pending skill proposals before creating more.')
            key, now = uuid4().hex, time.time()
            db.execute('INSERT OR IGNORE INTO skill_proposals VALUES(?,?,?,?,?,?,?,?,?)',
                       (key, fingerprint, json.dumps(document), before['content'], raw, source[:200], 'pending', now, now))
            row = db.execute('SELECT * FROM skill_proposals WHERE fingerprint=?', (fingerprint,)).fetchone()
            if previous and previous['id'] != row['id']:
                db.execute("UPDATE skill_proposals SET status='superseded',updated=? WHERE id=?", (now, previous['id']))
                self._event(db, payload['name'], 'superseded', previous['fingerprint'], source)
            if row['id'] == key: self._event(db, payload['name'], 'proposed', fingerprint, source)
            return self._proposal(row)

    @staticmethod
    def _proposal(row):
        return {'id': row['id'], 'revision': row['fingerprint'], 'data': json.loads(row['payload']), 'source': row['source'],
                'status': row['status'], 'created': row['created'],
                'diff': ''.join(difflib.unified_diff(row['before_text'].splitlines(True), row['after_text'].splitlines(True),
                                                  fromfile='current/SKILL.md', tofile='proposed/SKILL.md'))}

    def proposals(self, *, status='pending'):
        with self._db() as db:
            return [self._proposal(r) for r in db.execute('SELECT * FROM skill_proposals WHERE status=? ORDER BY created DESC LIMIT 100', (status,))]

    def review(self, key, revision, action, *, protected=()):
        if action not in {'accept', 'reject'}: raise ValueError('Accept or reject the displayed proposal.')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM skill_proposals WHERE id=?', (key,)).fetchone()
            if not row or row['fingerprint'] != revision: raise ValueError('Proposal changed. Inspect it again.')
            status = 'accepted' if action == 'accept' else 'rejected'
            if row['status'] == status: return self._proposal(row)
            if row['status'] != 'pending': raise ValueError('This proposal has already been reviewed.')
            payload = json.loads(row['payload'])
            if action == 'accept':
                absorbs = payload.pop('absorbs')
                for target in absorbs:
                    skill = self._managed(target['name'], target['revision'])
                    if skill.get('pinned') or skill['overrides_bundled'] or target['name'] in protected or skill['state'] == 'archived' or any(p.name != 'SKILL.md' for p in Path(skill['path']).parent.iterdir()):
                        raise ValueError('A consolidation source became protected. Stage a new proposal.')
                self._save(db, payload, source=row['source'])
                for target in absorbs:
                    db.execute('INSERT OR IGNORE INTO skill_meta(name,created) VALUES(?,?)', (target['name'], time.time()))
                    db.execute("UPDATE skill_meta SET state='archived' WHERE name=?", (target['name'],))
                    self._event(db, target['name'], 'archived', target['revision'], 'consolidated:' + payload['name'])
            db.execute('UPDATE skill_proposals SET status=?,updated=? WHERE id=?', (status, time.time(), key))
            self._event(db, payload['name'], status, revision, row['source'])
            return self._proposal(db.execute('SELECT * FROM skill_proposals WHERE id=?', (key,)).fetchone())

    def _managed(self, name, revision):
        skill = next((s for s in self.inventory() if s['name'] == name), None)
        if not skill or skill['origin'] != 'learned': raise ValueError('Lifecycle changes apply only to learned skills.')
        if self._read(name, archived=True)['revision'] != revision: raise ValueError('Skill changed. Inspect it again.')
        return skill

    def lifecycle(self, name, revision, action):
        if action not in {'archive', 'restore', 'pin', 'unpin'}: raise ValueError('Choose a supported skill action.')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._managed(name, revision)
            db.execute('INSERT OR IGNORE INTO skill_meta(name,created) VALUES(?,?)', (name, time.time()))
            if action in {'archive', 'restore'}:
                db.execute('UPDATE skill_meta SET state=?,last_use=? WHERE name=?', ('archived' if action == 'archive' else 'active', time.time(), name))
            else: db.execute('UPDATE skill_meta SET pinned=? WHERE name=?', (action == 'pin', name))
            self._event(db, name, action, revision)
        return {'name': name, 'action': action}

    def curate(self, *, now=None, stale_days=14, archive_days=30, protected=(), dry_run=False):
        now = time.time() if now is None else now
        changes = []
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            for skill in self.inventory():
                if skill['origin'] != 'learned' or skill['overrides_bundled'] or skill['state'] == 'archived' or skill.get('pinned') or skill['name'] in protected: continue
                created = skill.get('created') or Path(skill['path']).stat().st_mtime
                last = max(skill.get('last_use') or created, skill.get('last_view') or created, skill.get('last_patch') or created)
                days = (now - last) / 86400
                state = 'archived' if days >= archive_days else 'stale' if days >= stale_days else 'active'
                if state == skill['state']: continue
                changes.append({'name': skill['name'], 'from': skill['state'], 'to': state})
                if not dry_run:
                    db.execute('INSERT OR IGNORE INTO skill_meta(name,created) VALUES(?,?)', (skill['name'], created))
                    db.execute('UPDATE skill_meta SET state=? WHERE name=?', (state, skill['name']))
                    self._event(db, skill['name'], state, source='curator')
        return {'changes': changes, 'dry_run': dry_run, 'deletes': 0}

    def detail(self, name, *, track=False):
        row = self._read(name, archived=True)
        if track: self.track(name, 'view')
        import yaml
        from .skills import FRONT
        front = FRONT.match(row['content'])
        meta = yaml.safe_load(front.group(1)) if front else {}
        with self._db() as db:
            history = [dict(r) for r in db.execute('SELECT revision,verification,correction,created FROM revisions WHERE name=? ORDER BY rowid DESC LIMIT 30', (name,))]
        skill = next(s for s in self.inventory() if s['name'] == name)
        return {**row, 'description': meta.get('description', ''), 'triggers': skill['triggers'],
                'instructions': row['content'][front.end():].strip() if front else row['content'], 'history': history}

    def journey(self, limit=100):
        with self._db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM skill_events ORDER BY created DESC LIMIT ?', (min(200, limit),))]
