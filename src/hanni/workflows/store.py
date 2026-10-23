"""Private durable workflow state with owner fencing and invocation checkpoints.

Every dispatch is recorded before its handler can run. Recovery never infers a
write failed from an absent result. Expiry uses persisted wall time; an observed
clock rollback blocks admission rather than extending approvals or leases.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from uuid import uuid4

from .types import (
    LeaseLost, StaleWorkflow, WorkflowError, WorkflowLimits, STATUSES,
    STEP_STATUSES, TERMINAL, TRANSITIONS, canonical_json, fingerprint, identifier, iso_time,
    request_uuid, wall_time, within_root,
)


SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE workflows(
 id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL,
 created REAL NOT NULL, updated REAL NOT NULL, payload TEXT NOT NULL);
CREATE TABLE steps(
 workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
 id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(workflow_id,id));
CREATE TABLE invocations(
 id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
 step_id TEXT NOT NULL, fence INTEGER NOT NULL, state TEXT NOT NULL,
 created REAL NOT NULL, payload TEXT NOT NULL);
CREATE TABLE approvals(
 id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
 step_id TEXT, state TEXT NOT NULL, expires REAL NOT NULL, payload TEXT NOT NULL);
CREATE TABLE checkpoints(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
 created REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE operations(
 id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, created REAL NOT NULL,
 response TEXT NOT NULL);
CREATE TABLE owner(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), token TEXT NOT NULL,
 fence INTEGER NOT NULL, expires REAL NOT NULL);
CREATE INDEX workflow_updated ON workflows(updated DESC);
CREATE INDEX invocation_workflow ON invocations(workflow_id,created);
"""
TABLES = {'metadata', 'workflows', 'steps', 'invocations', 'approvals',
          'checkpoints', 'operations', 'owner'}


def _schema_identity(db):
    """Compare the complete user schema before any persistent PRAGMA changes."""
    return tuple((row[0], row[1], row[2],
                  ' '.join(row[3].split()).casefold() if row[3] else None)
                 for row in db.execute(
                     'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))


def _expected_schema():
    db = sqlite3.connect(':memory:')
    try:
        db.executescript(SCHEMA)
        return _schema_identity(db)
    finally:
        db.close()


EXPECTED_SCHEMA = _expected_schema()


class WorkflowStore:
    def __init__(self, data_dir, limits=None, *, clock=time.time, observer=None):
        self.root = Path(data_dir).resolve()
        self.path = self.root / 'workflows' / 'workflows.sqlite3'
        self.limits = WorkflowLimits.from_config(limits)
        self.clock = clock
        self.observer = observer
        self.lock = threading.RLock()
        self.db = None

    def _connect(self):
        if self.db is not None:
            return self.db
        if self.path.is_symlink() or not within_root(self.path, self.root):
            raise WorkflowError('Workflow storage path is unavailable.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None,
                             timeout=5)
        db.row_factory = sqlite3.Row
        try:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise WorkflowError('Unsupported workflow storage version.')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise WorkflowError('Workflow storage integrity check failed.')
            present = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if version == 1 and not TABLES <= present:
                raise WorkflowError('Workflow storage schema is incomplete.')
            if version == 1 and _schema_identity(db) != EXPECTED_SCHEMA:
                raise WorkflowError('Unrecognized workflow storage schema is preserved.')
            if version == 0 and present:
                raise WorkflowError('Unrecognized workflow storage is preserved.')
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            if version == 0:
                db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA +
                                 '\nPRAGMA user_version=1;\nCOMMIT;')
            if os.name != 'nt':
                self.path.chmod(0o600)
        except Exception:
            db.close()
            raise
        self.db = db
        return db

    @contextmanager
    def transaction(self):
        with self.lock:
            db = self._connect()
            outer = not db.in_transaction
            if outer:
                db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                if outer:
                    db.commit()
            except BaseException:
                if outer:
                    db.rollback()
                raise

    def _now(self, db):
        now = wall_time(self.clock())
        row = db.execute("SELECT value FROM metadata WHERE key='last_wall'").fetchone()
        if row and now < wall_time(float(row[0])):
            raise WorkflowError('System clock moved backwards; workflow admission is blocked.')
        db.execute("INSERT INTO metadata VALUES('last_wall',?) ON CONFLICT(key) "
                   'DO UPDATE SET value=excluded.value', (str(now),))
        return now

    def _encode(self, value, *, result=False):
        return canonical_json(value, maximum=(self.limits.max_result_bytes if result
                                             else self.limits.max_payload_bytes))

    def execute_request(self, request_id, body, authority, action):
        """Commit an operation and its replay response in the same transaction."""
        key = request_uuid(request_id)
        digest = fingerprint({'body': body, 'authority': authority})
        with self.transaction() as db:
            now = self._now(db)
            old = db.execute('SELECT fingerprint,response FROM operations WHERE id=?',
                             (key,)).fetchone()
            if old:
                if old['fingerprint'] != digest:
                    raise WorkflowError('Request ID was already used for a different operation.')
                return json.loads(old['response'])
            response = action()
            db.execute('INSERT INTO operations VALUES(?,?,?,?)',
                       (key, digest, now, self._encode(response)))
            # The request ledger stays bounded without forgetting IDs for retained workflows.
            # At the hard cap new operations fail; no old write consent can be replayed.
            if db.execute('SELECT COUNT(*) FROM operations').fetchone()[0] > self.limits.max_workflows * 256:
                raise WorkflowError('Workflow operation retention limit reached.')
            return response

    def create(self, goal, mode, *, scope=None, collaboration='auto'):
        from .types import MODES
        if not isinstance(goal, str) or not goal.strip() or len(goal) > self.limits.max_goal_chars:
            raise WorkflowError('Goal is empty or exceeds its size limit.')
        if mode not in MODES:
            raise WorkflowError('Unsupported workflow mode.')
        from hanni.models.collaboration import PATTERNS
        if not isinstance(collaboration, str) or collaboration not in PATTERNS:
            raise WorkflowError('Unsupported trusted collaboration preference.')
        with self.transaction() as db:
            now = self._now(db)
            if db.execute('SELECT COUNT(*) FROM workflows').fetchone()[0] >= self.limits.max_workflows:
                raise WorkflowError('Workflow retention limit reached.')
            key = 'wf_' + uuid4().hex
            record = {
                'workflow_id': key, 'goal': goal.strip(), 'mode': mode, 'collaboration': collaboration,
                'status': 'submitted', 'revision': 1, 'plan_hash': None,
                'plan_version': 0, 'created_at': iso_time(now), 'updated_at': iso_time(now),
                'pause_requested': False, 'cancel_requested': False,
                'active_uninterruptible': False, 'scope': scope,
                'invocation_count': 0, 'planning_attempts': 0, 'error': None,
            }
            db.execute('INSERT INTO workflows VALUES(?,?,?,?,?,?)',
                       (key, 1, 'submitted', now, now, self._encode(record)))
            self._checkpoint(db, key, now, 'submitted', {'revision': 1})
            return record

    def _get(self, db, key):
        identifier(key, workflow=True)
        row = db.execute('SELECT * FROM workflows WHERE id=?', (key,)).fetchone()
        if row is None:
            raise WorkflowError('Workflow was not found.')
        return json.loads(row['payload'])

    def get(self, key):
        with self.lock:
            return self._get(self._connect(), key)

    def list(self, limit=50):
        with self.lock:
            if self.db is None and not self.path.exists():
                return []
            rows = self._connect().execute('SELECT payload FROM workflows ORDER BY updated DESC LIMIT ?',
                                          (max(1, min(100, int(limit))),))
            return [json.loads(row[0]) for row in rows]

    def nonterminal(self):
        """Runner admission is independent of the newest history page."""
        with self.lock:
            db = self._connect()
            marks = ','.join('?' for _ in TERMINAL)
            return [json.loads(row[0]) for row in db.execute(
                f'SELECT payload FROM workflows WHERE status NOT IN ({marks}) '
                'ORDER BY created,id LIMIT ?', (*sorted(TERMINAL), self.limits.max_workflows))]

    def _save(self, db, record, expected_revision, now):
        if record['status'] not in STATUSES:
            raise WorkflowError('Invalid workflow state.')
        if type(expected_revision) is not int or expected_revision < 1:
            raise StaleWorkflow('Workflow revision is required.')
        prior = self._get(db, record['workflow_id'])
        if prior['status'] in TERMINAL:
            raise WorkflowError('A terminal workflow is immutable.')
        if record['status'] != prior['status'] and record['status'] not in TRANSITIONS[prior['status']]:
            raise WorkflowError('Workflow state transition is not permitted.')
        record = dict(record, revision=expected_revision + 1, updated_at=iso_time(now))
        updated = db.execute('UPDATE workflows SET revision=?,status=?,updated=?,payload=? '
                             'WHERE id=? AND revision=?',
                             (record['revision'], record['status'], now, self._encode(record),
                              record['workflow_id'], expected_revision)).rowcount
        if updated != 1:
            raise StaleWorkflow('Workflow changed; review the current state.')
        return record

    def update(self, key, expected_revision, changes, *, kind='updated', lease=None):
        forbidden = {'workflow_id', 'goal', 'mode', 'collaboration', 'revision', 'created_at', 'updated_at'}
        if forbidden.intersection(changes):
            raise WorkflowError('Immutable workflow fields cannot be changed.')
        with self.transaction() as db:
            now = self._now(db)
            if lease:
                self._fence(db, lease, now)
            record = self._get(db, key)
            record.update(changes)
            record = self._save(db, record, expected_revision, now)
            self._checkpoint(db, key, now, kind, {'revision': record['revision']})
            return record

    def save_plan(self, key, expected_revision, plan, steps, *, lease, preserve_verified=False):
        if not isinstance(steps, list) or not 1 <= len(steps) <= self.limits.max_steps:
            raise WorkflowError('Plan step count is outside its limit.')
        ids = [identifier(step.get('step_id')) for step in steps]
        if len(set(ids)) != len(ids):
            raise WorkflowError('Plan step IDs must be unique.')
        if not isinstance(plan, dict) or plan.get('steps') != steps:
            raise WorkflowError('Plan hash must bind the exact executable steps.')
        self._encode(plan)
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            record = self._get(db, key)
            if record['status'] in TERMINAL or record['status'] not in {
                'submitted', 'planning', 'awaiting_plan_approval', 'blocked',
            }:
                raise WorkflowError('A plan cannot be replaced in the current workflow state.')
            invoked = [json.loads(row[0]) for row in db.execute('SELECT payload FROM invocations WHERE workflow_id=?', (key,))]
            retained = {}
            if invoked:
                if not preserve_verified or any(i['write'] or i['state'] in {'dispatched', 'uncertain'} for i in invoked):
                    raise WorkflowError('An invoked plan cannot be replaced.')
                retained = {s['step_id']: s for s in self.steps(key) if s['status'] == 'verified'}
                original = {s['step_id']: s for s in record['plan']['steps']}
                proposed = {s['step_id']: s for s in steps}
                if any(proposed.get(sid) != original[sid] for sid in retained):
                    raise WorkflowError('Replanning must preserve every verified step and its exact contract.')
                if any(i['step_id'] in proposed and i['step_id'] not in retained for i in invoked):
                    raise WorkflowError('Replanning cannot reuse an unsuccessful invocation identity.')
            for step in steps:
                deps = step.get('dependencies', [])
                if not isinstance(deps, list) or any(dep not in ids or dep == step['step_id'] for dep in deps):
                    raise WorkflowError('Invalid plan dependencies.')
            visiting, done = set(), set()
            by_id = {step['step_id']: step for step in steps}
            def visit(step_id):
                if step_id in visiting:
                    raise WorkflowError('Plan dependency graph contains a cycle.')
                if step_id in done:
                    return
                visiting.add(step_id)
                for dep in by_id[step_id].get('dependencies', []):
                    visit(dep)
                visiting.remove(step_id)
                done.add(step_id)
            for step_id in ids:
                visit(step_id)
            db.execute('DELETE FROM steps WHERE workflow_id=?', (key,))
            for step in steps:
                payload = retained.get(step['step_id']) or dict(step, status='pending', attempts=0,
                               verification=None, error=None, started_at=None, finished_at=None)
                db.execute('INSERT INTO steps VALUES(?,?,?)', (key, step['step_id'], self._encode(payload)))
            record.update(plan=plan, plan_hash=fingerprint(plan),
                          plan_version=record['plan_version'] + 1,
                          status='awaiting_plan_approval', error=None)
            record = self._save(db, record, expected_revision, now)
            self._checkpoint(db, key, now, 'plan_saved', {'plan_hash': record['plan_hash'],
                                                       'revision': record['revision']})
            return record

    def steps(self, key):
        with self.lock:
            self._get(self._connect(), key)
            return [json.loads(row[0]) for row in self.db.execute(
                'SELECT payload FROM steps WHERE workflow_id=? ORDER BY rowid', (key,))]

    def _step(self, db, key, step_id):
        row = db.execute('SELECT payload FROM steps WHERE workflow_id=? AND id=?',
                         (key, step_id)).fetchone()
        if not row:
            raise WorkflowError('Workflow step was not found.')
        return json.loads(row[0])

    def _save_step(self, db, key, step):
        if step['status'] not in STEP_STATUSES:
            raise WorkflowError('Invalid workflow step state.')
        db.execute('UPDATE steps SET payload=? WHERE workflow_id=? AND id=?',
                   (self._encode(step), key, step['step_id']))

    def claim(self, token, *, seconds=None):
        token = request_uuid(token)
        duration = self.limits.lease_seconds if seconds is None else seconds
        if type(duration) is not int or not 1 <= duration <= self.limits.lease_seconds:
            raise WorkflowError('Invalid owner lease duration.')
        with self.transaction() as db:
            now = self._now(db)
            old = db.execute('SELECT * FROM owner WHERE singleton=1').fetchone()
            if old and wall_time(old['expires']) > now and old['token'] != token:
                raise LeaseLost('Another workflow runner owns the durable lease.')
            fence = old['fence'] if old and old['token'] == token and old['expires'] > now else (old['fence'] + 1 if old else 1)
            db.execute('INSERT INTO owner VALUES(1,?,?,?) ON CONFLICT(singleton) '
                       'DO UPDATE SET token=excluded.token,fence=excluded.fence,expires=excluded.expires',
                       (token, fence, now + duration))
            return {'token': token, 'fence': fence}

    def _fence(self, db, lease, now):
        row = db.execute('SELECT * FROM owner WHERE singleton=1').fetchone()
        if (not row or row['token'] != lease.get('token') or row['fence'] != lease.get('fence')
                or wall_time(row['expires']) <= now):
            raise LeaseLost('Workflow runner lease was lost.')

    def heartbeat(self, lease):
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            db.execute('UPDATE owner SET expires=? WHERE singleton=1',
                       (now + self.limits.lease_seconds,))

    def release(self, lease):
        with self.transaction() as db:
            now = self._now(db)
            row = db.execute('SELECT * FROM owner WHERE singleton=1').fetchone()
            if row and row['token'] == lease.get('token') and row['fence'] == lease.get('fence'):
                db.execute('UPDATE owner SET expires=? WHERE singleton=1', (now,))

    def add_approval(self, key, expected_revision, binding, *, lease=None):
        with self.transaction() as db:
            now = self._now(db)
            if lease:
                self._fence(db, lease, now)
            record = self._get(db, key)
            if binding.get('plan_hash') != record['plan_hash']:
                raise StaleWorkflow('Approval plan is stale.')
            approval_id = 'approval_' + uuid4().hex
            expires = now + self.limits.approval_ttl_seconds
            payload = dict(binding, approval_id=approval_id, workflow_id=key,
                           state='pending', created_at=iso_time(now), expires_at=iso_time(expires))
            db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?)',
                       (approval_id, key, binding.get('step_id'), 'pending', expires, self._encode(payload)))
            record = self._save(db, record, expected_revision, now)
            self._checkpoint(db, key, now, 'approval_requested', {'approval_id': approval_id})
            return payload, record

    def decide_approval(self, key, expected_revision, approval_id, decision, binding):
        if decision not in {'approved', 'rejected', 'revoked'}:
            raise WorkflowError('Invalid approval decision.')
        with self.transaction() as db:
            now = self._now(db)
            record = self._get(db, key)
            row = db.execute('SELECT * FROM approvals WHERE id=? AND workflow_id=?',
                             (approval_id, key)).fetchone()
            if not row:
                raise WorkflowError('Approval was not found for this workflow.')
            payload = json.loads(row['payload'])
            if decision != 'revoked':
                if row['state'] != 'pending' or wall_time(row['expires']) <= now:
                    raise WorkflowError('Approval is expired or no longer pending.')
                for field in ('plan_hash', 'step_id', 'argument_hash', 'definition_hash'):
                    if payload.get(field) != binding.get(field):
                        raise StaleWorkflow('Approval binding changed; review the current request.')
                if payload['plan_hash'] != record['plan_hash']:
                    raise StaleWorkflow('Approval plan changed.')
            payload['state'] = decision
            db.execute('UPDATE approvals SET state=?,payload=? WHERE id=?',
                       (decision, self._encode(payload), approval_id))
            record = self._save(db, record, expected_revision, now)
            self._checkpoint(db, key, now, 'approval_' + decision, {'approval_id': approval_id})
            return payload, record

    def begin_invocation(self, key, expected_revision, step_id, *, lease, arguments,
                         definition_hash, write, retry_safe=False, approval_id=None,
                         resource_keys=()):
        """Consume exact action consent and commit the invocation before dispatch."""
        if type(write) is not bool or type(retry_safe) is not bool:
            raise WorkflowError('Invocation policy is invalid.')
        arg_hash = fingerprint(arguments)
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            record = self._get(db, key)
            if record['status'] not in {'ready', 'running'} or record['pause_requested'] or record['cancel_requested']:
                raise WorkflowError('Workflow is not admitting new invocations.')
            if record['invocation_count'] >= self.limits.max_invocations:
                raise WorkflowError('Workflow invocation budget exhausted.')
            step = self._step(db, key, step_id)
            # Renaming a step during replanning cannot reset an operation's budget.
            matching = [json.loads(row[0]) for row in db.execute('SELECT payload FROM invocations WHERE workflow_id=?', (key,))]
            matching = [i for i in matching if i.get('capability_id') == step.get('capability_id')
                        and i['argument_hash'] == arg_hash and i['step_id'] != step_id
                        and (record.get('plan') or {}).get('contract') == 'bounded_intent_v1'
                        and (write or i.get('plan_hash') != record['plan_hash'])]
            if matching and (write or not retry_safe or len(matching) + step['attempts'] >= self.limits.max_retries + 1):
                raise WorkflowError('Previously invoked operation cannot bypass its replay budget.')
            if step['status'] not in {'pending', 'ready'}:
                raise WorkflowError('Step cannot be invoked in its current state.')
            attempt = step['attempts'] + 1
            if attempt > 1 and (write or not retry_safe or attempt > self.limits.max_retries + 1):
                raise WorkflowError('Step retry budget exhausted or replay is prohibited.')
            if attempt > 1:
                retry_at = step.get('next_attempt_at')
                if retry_at is None or wall_time(retry_at) > now:
                    raise WorkflowError('Durable retry backoff has not elapsed.')
            if step['definition_hash'] != definition_hash:
                raise StaleWorkflow('Tool definition changed before dispatch.')
            for dep in step.get('dependencies', []):
                if self._step(db, key, dep)['status'] != 'verified':
                    raise WorkflowError('Prerequisite has not been verified.')
            if write:
                for old in db.execute("SELECT payload FROM invocations WHERE state IN ('dispatched','uncertain')"):
                    prior = json.loads(old[0])
                    if prior['write'] and (not resource_keys or not prior['resource_keys']
                                          or set(resource_keys).intersection(prior['resource_keys'])):
                        raise WorkflowError('A conflicting write is active or requires reconciliation.')
            if approval_id:
                row = db.execute('SELECT * FROM approvals WHERE id=? AND workflow_id=? AND step_id=?',
                                 (approval_id, key, step_id)).fetchone()
                if not row or row['state'] != 'approved' or wall_time(row['expires']) <= now:
                    raise WorkflowError('Exact action approval is unavailable or expired.')
                approval = json.loads(row['payload'])
                if any(approval.get(field) != expected for field, expected in (
                    ('plan_hash', record['plan_hash']), ('argument_hash', arg_hash),
                    ('definition_hash', definition_hash))):
                    raise StaleWorkflow('Exact action approval no longer matches the invocation.')
                approval['state'] = 'consumed'
                db.execute("UPDATE approvals SET state='consumed',payload=? WHERE id=?",
                           (self._encode(approval), approval_id))
            invocation_id = 'invocation_' + uuid4().hex
            payload = {
                'invocation_id': invocation_id, 'workflow_id': key, 'step_id': step_id,
                'fence': lease['fence'], 'state': 'dispatched', 'write': write,
                'retry_safe': retry_safe, 'attempt': attempt, 'argument_hash': arg_hash,
                'plan_hash': record['plan_hash'],
                'definition_hash': definition_hash, 'resource_keys': list(resource_keys),
                'approval_id': approval_id, 'capability_id': step.get('capability_id'),
                'correlation_id': str(uuid4()),
                'started_at': iso_time(now), 'finished_at': None, 'result': None,
            }
            self._encode(arguments)  # Arguments are retained in the private step, not audit metadata.
            step.update(status='running', attempts=attempt, arguments=arguments,
                        started_at=iso_time(now), finished_at=None)
            self._save_step(db, key, step)
            db.execute('INSERT INTO invocations VALUES(?,?,?,?,?,?,?)',
                       (invocation_id, key, step_id, lease['fence'], 'dispatched', now, self._encode(payload)))
            record.update(status='running', invocation_count=record['invocation_count'] + 1,
                          active_uninterruptible=True)
            record = self._save(db, record, expected_revision, now)
            self._checkpoint(db, key, now, 'invocation_committed',
                             {'invocation_id': invocation_id, 'step_id': step_id, 'fence': lease['fence']})
        if self.observer:
            self.observer('before_dispatch', dict(payload))
        return payload, record

    def finish_invocation(self, invocation_id, *, lease, result, step_status, verification=None):
        if step_status not in {'verified', 'unverified', 'failed', 'blocked'}:
            raise WorkflowError('Invalid invocation completion state.')
        self._encode(result, result=True)
        if self.observer:
            self.observer('after_result', {'invocation_id': invocation_id})
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            row = db.execute('SELECT * FROM invocations WHERE id=?', (invocation_id,)).fetchone()
            if not row or row['fence'] != lease['fence'] or row['state'] != 'dispatched':
                raise LeaseLost('Invocation result belongs to an obsolete runner.')
            payload = json.loads(row['payload'])
            key = payload['workflow_id']
            record = self._get(db, key)
            step = self._step(db, key, payload['step_id'])
            payload.update(state='finished', finished_at=iso_time(now), result=result)
            db.execute("UPDATE invocations SET state='finished',payload=? WHERE id=? AND state='dispatched'",
                       (self._encode(payload, result=True), invocation_id))
            step.update(status=step_status, verification=verification,
                        finished_at=iso_time(now), result=result)
            self._save_step(db, key, step)
            remaining = db.execute("SELECT 1 FROM invocations WHERE workflow_id=? AND state='dispatched' LIMIT 1",
                                   (key,)).fetchone()
            record['active_uninterruptible'] = bool(remaining)
            record = self._save(db, record, record['revision'], now)
            self._checkpoint(db, key, now, 'result_committed',
                             {'invocation_id': invocation_id, 'step_id': step['step_id'], 'status': step_status})
            return record

    def record_collaboration(self, invocation_id, collaboration, *, lease):
        """Real inference telemetry inside an existing fenced V3 receipt.

        Telemetry has no authority to finish a step, approve tools, or alter its
        dependency graph. Partial progress survives restart without replay.
        """
        encoded = self._encode(collaboration, result=True)
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            row = db.execute('SELECT * FROM invocations WHERE id=?', (invocation_id,)).fetchone()
            if not row or row['fence'] != lease['fence'] or row['state'] != 'dispatched':
                raise LeaseLost('Collaboration telemetry belongs to an obsolete invocation.')
            payload = json.loads(row['payload'])
            key = payload['workflow_id']
            step = self._step(db, key, payload['step_id'])
            if step['kind'] != 'analysis' or step['status'] != 'running':
                raise WorkflowError('Collaboration progress requires an active original analysis step.')
            payload['collaboration'] = json.loads(encoded)
            step['collaboration'] = json.loads(encoded)
            db.execute('UPDATE invocations SET payload=? WHERE id=?', (self._encode(payload, result=True), invocation_id))
            self._save_step(db, key, step)
            record = self._get(db, key)
            self._save(db, record, record['revision'], now)
            self._checkpoint(db, key, now, 'collaboration_progress', {'invocation_id': invocation_id,
                'step_id': step['step_id'], 'collaboration_state': collaboration.get('state'),
                'participants': [{'participant_id': item['participant_id'], 'state': item['state']}
                                 for item in collaboration.get('participants', [])]})

    def recover(self, lease):
        """Abandoned writes remain uncertain; safe reads require explicit resumption."""
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            changed = set()
            rows = list(db.execute("SELECT * FROM invocations WHERE state='dispatched' AND fence<>?",
                                   (lease['fence'],)))
            for row in rows:
                payload = json.loads(row['payload'])
                key = payload['workflow_id']
                step = self._step(db, key, payload['step_id'])
                uncertain = payload['write']
                payload['state'] = 'uncertain' if uncertain else 'abandoned'
                db.execute('UPDATE invocations SET state=?,payload=? WHERE id=?',
                           (payload['state'], self._encode(payload), row['id']))
                eligible_retry = (payload['retry_safe'] and step['attempts'] < self.limits.max_retries + 1)
                step['status'] = 'blocked' if uncertain or not eligible_retry else 'pending'
                if step['status'] == 'pending':
                    step['next_attempt_at'] = now + min(2 ** step['attempts'], 5)
                step['error'] = 'Action outcome is uncertain; automatic replay is disabled.' if uncertain else 'Runner stopped before recording a result.'
                if step.get('collaboration'):
                    step['collaboration']['state'] = 'interrupted'
                    for participant in step['collaboration'].get('participants', []):
                        if participant['state'] in {'queued', 'running'}:
                            participant.update(state='interrupted', error='Runner restarted; this model request was not replayed.')
                    payload['collaboration'] = step['collaboration']
                    db.execute('UPDATE invocations SET payload=? WHERE id=?',
                               (self._encode(payload, result=True), row['id']))
                self._save_step(db, key, step)
                self._checkpoint(db, key, now, 'recovered',
                                 {'invocation_id': row['id'], 'uncertain_write': uncertain})
                changed.add(key)
            for key in sorted(changed):
                # Recovery is a workflow decision, not "last invocation wins".
                # Existing uncertainty also survives later independent read recovery.
                uncertain = db.execute("SELECT 1 FROM invocations WHERE workflow_id=? AND state='uncertain' LIMIT 1",
                                       (key,)).fetchone()
                blocked = any(json.loads(row[0])['status'] == 'blocked' for row in db.execute(
                    'SELECT payload FROM steps WHERE workflow_id=?', (key,)))
                record = self._get(db, key)
                record.update(status='blocked' if uncertain or blocked else 'paused',
                              active_uninterruptible=False, pause_requested=False,
                              error=('Action outcome is uncertain; automatic replay is disabled.'
                                     if uncertain else 'Runner stopped before recording a result.'))
                self._save(db, record, record['revision'], now)
            return sorted(changed)

    def _checkpoint(self, db, key, now, kind, payload):
        payload = dict(payload, status=self._get(db, key)['status'])
        db.execute('INSERT INTO checkpoints(workflow_id,created,kind,payload) VALUES(?,?,?,?)',
                   (key, now, kind, self._encode(payload)))

    def edit_step(self, key, expected_revision, step_id, changes, *, lease, kind='step_updated'):
        """Runner-only step changes with the same lease and workflow CAS."""
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            record = self._get(db, key)
            if record['revision'] != expected_revision:
                raise StaleWorkflow('Workflow changed before step preparation.')
            step = self._step(db, key, step_id)
            if step['status'] == 'verified' or 'step_id' in changes:
                raise WorkflowError('Verified steps and identities are immutable.')
            step.update(changes)
            self._save_step(db, key, step)
            record = self._save(db, record, expected_revision, now)
            self._checkpoint(db, key, now, kind, {'step_id': step_id})
            return record

    def assert_lease(self, lease):
        with self.transaction() as db:
            self._fence(db, lease, self._now(db))

    def dispatch_guard(self, invocation_id, lease):
        """Recheck fencing and revocation after the pre-dispatch observer."""
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            row = db.execute('SELECT * FROM invocations WHERE id=?', (invocation_id,)).fetchone()
            if not row or row['state'] != 'dispatched' or row['fence'] != lease['fence']:
                raise LeaseLost('Invocation no longer belongs to this runner.')
            invocation = json.loads(row['payload'])
            record = self._get(db, invocation['workflow_id'])
            if record['pause_requested'] or record['cancel_requested']:
                raise WorkflowError('Workflow admission was withdrawn before dispatch.')
            scope = record.get('scope') or {}
            if scope.get('plan_hash') != record['plan_hash'] or wall_time(scope.get('expires')) <= now:
                raise WorkflowError('Reviewed workflow scope is unavailable or expired.')
            approval = db.execute('SELECT state,expires FROM approvals WHERE id=?',
                                  (scope.get('approval_id'),)).fetchone()
            if not approval or approval['state'] != 'approved' or approval['expires'] <= now:
                raise WorkflowError('Reviewed plan authority has been revoked or expired.')
            if invocation.get('approval_id'):
                approval = db.execute('SELECT state,expires FROM approvals WHERE id=?',
                                      (invocation['approval_id'],)).fetchone()
                if not approval or approval['state'] != 'consumed' or approval['expires'] <= now:
                    raise WorkflowError('Exact action authority has been revoked or expired.')

    def abandon_invocation(self, invocation_id, lease, reason):
        """A returned call without a retainable receipt never licenses replay."""
        with self.transaction() as db:
            now = self._now(db)
            self._fence(db, lease, now)
            row = db.execute('SELECT * FROM invocations WHERE id=?', (invocation_id,)).fetchone()
            if not row or row['fence'] != lease['fence'] or row['state'] != 'dispatched':
                return
            receipt = json.loads(row['payload'])
            receipt.update(state='uncertain' if receipt['write'] else 'abandoned', finished_at=iso_time(now))
            db.execute('UPDATE invocations SET state=?,payload=? WHERE id=?',
                       (receipt['state'], self._encode(receipt), invocation_id))
            key = receipt['workflow_id']
            step = self._step(db, key, receipt['step_id'])
            step.update(status='blocked', error=reason, finished_at=iso_time(now))
            self._save_step(db, key, step)
            record = self._get(db, key)
            active = db.execute("SELECT 1 FROM invocations WHERE workflow_id=? AND state='dispatched' LIMIT 1", (key,)).fetchone()
            record.update(status='blocked', active_uninterruptible=bool(active), error=reason)
            self._save(db, record, record['revision'], now)
            self._checkpoint(db, key, now, 'receipt_unavailable', {'invocation_id': invocation_id,
                'step_id': receipt['step_id'], 'uncertain_write': receipt['write']})

    def history(self, key):
        with self.lock:
            db = self._connect()
            self._get(db, key)
            checkpoints = [dict(sequence=row['sequence'], created_at=iso_time(row['created']),
                                kind=row['kind'], **json.loads(row['payload']))
                           for row in db.execute('SELECT * FROM checkpoints WHERE workflow_id=? ORDER BY sequence', (key,))]
            return {
                'checkpoints': checkpoints,
                'invocations': [json.loads(row[0]) for row in db.execute(
                    'SELECT payload FROM invocations WHERE workflow_id=? ORDER BY created', (key,))],
                'approvals': [json.loads(row[0]) for row in db.execute(
                    'SELECT payload FROM approvals WHERE workflow_id=? ORDER BY rowid', (key,))],
            }

    def close(self):
        with self.lock:
            if self.db:
                self.db.close()
                self.db = None
