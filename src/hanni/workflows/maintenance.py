"""Bounded private context retention without forgetting prior operation IDs."""
import json
import os
from pathlib import Path
import stat

from .types import TERMINAL, WorkflowError, canonical_json, identifier, within_root, resource_identity


GC_PREFIX = 'artifact_gc:'


def prune_terminal(store, *, limit=32):
    """Expire old settled workflows atomically, retaining replay tombstones.

    Called by trusted runner admission/mutation, never by private history GET.
    Uncertain effects, in-flight work and live authority are retained for review.
    """
    if type(limit) is not int or not 1 <= limit <= 32:
        raise WorkflowError('Invalid workflow maintenance limit.')
    with store.transaction() as db:
        now = store._now(db)
        cutoff = now - store.limits.retention_days * 86400
        placeholders = ','.join('?' for _ in TERMINAL)
        rows = list(db.execute(
            f'SELECT id FROM workflows WHERE status IN ({placeholders}) AND updated<=? '
            "AND NOT EXISTS(SELECT 1 FROM invocations WHERE workflow_id=workflows.id "
            "AND state IN ('dispatched','uncertain')) "
            "AND NOT EXISTS(SELECT 1 FROM approvals WHERE workflow_id=workflows.id "
            "AND state IN ('pending','approved') AND expires>?) ORDER BY updated LIMIT ?",
            (*sorted(TERMINAL), cutoff, now, limit)))
        keys = [row['id'] for row in rows]
        for key in keys:
            identifier(key, workflow=True)
            # Queue physical cleanup in the same commit as context expiry.
            # A crash or locked file leaves the queue and storage budget intact.
            if db.execute('SELECT count(*) FROM metadata WHERE key GLOB ?',
                          (GC_PREFIX + '*',)).fetchone()[0] >= store.limits.max_workflows:
                raise WorkflowError('Workflow artifact cleanup is blocked at its retention limit.')
            db.execute('INSERT INTO metadata(key,value) VALUES(?,?)',
                       (GC_PREFIX + key, canonical_json({'workflow_id': key})))
            # SQLite JSON extraction targets the exact durable API response ID,
            # never a substring of unrelated output. Retain identity/fingerprint.
            tombstone = canonical_json({'workflow_id': key, 'expired': True})
            db.execute("UPDATE operations SET response=? WHERE json_extract(response,'$.workflow_id')=?",
                       (tombstone, key))
            for table in ('approvals', 'invocations', 'steps', 'checkpoints'):
                db.execute(f'DELETE FROM {table} WHERE workflow_id=?', (key,))
            db.execute('DELETE FROM workflows WHERE id=?', (key,))
        return keys


def _plain_path(path, boundary):
    """Validate absolute targets before any removal; never follow reparse paths."""
    # The validated absolute boundary remains fixed if a parent is replaced
    # during cleanup; resolving both sides again would follow that replacement.
    parent = os.path.normcase(str(boundary))
    try:
        valid = os.path.commonpath([resource_identity(path), parent]) == parent
    except ValueError:
        valid = False
    if not valid:
        raise WorkflowError('Artifact cleanup path is outside managed storage.')
    attributes = os.lstat(path)
    reparse = getattr(attributes, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
    if stat.S_ISLNK(attributes.st_mode) or reparse:
        raise WorkflowError('Artifact cleanup does not follow links or junctions.')
    return attributes


def _remove_owned_tree(target, boundary, maximum):
    """Bounded postorder unlink/rmdir; no recursive shell/delete operation."""
    pending = [(target, False)]
    visited = removed = 0
    complete = True
    while pending:
        path, after_children = pending.pop()
        if not after_children:
            visited += 1
            if visited > maximum:
                complete = False
                continue
        try:
            attributes = _plain_path(path, boundary)
            if stat.S_ISDIR(attributes.st_mode):
                if after_children:
                    try:
                        path.rmdir()
                    except OSError:
                        complete = False
                else:
                    pending.append((path, True))
                    with os.scandir(path) as children:
                        for index, child in enumerate(children):
                            if index >= maximum:
                                complete = False
                                break
                            pending.append((Path(child.path), False))
            elif stat.S_ISREG(attributes.st_mode):
                path.unlink()
                removed += 1
            else:
                raise WorkflowError('Artifact cleanup encountered an unsupported filesystem object.')
        except FileNotFoundError:
            continue
    return complete, removed


def cleanup_artifacts(store, *, limit=4, max_entries=128):
    """Drain a durable cleanup queue only inside canonical managed ID folders."""
    if type(limit) is not int or not 1 <= limit <= 4 or type(max_entries) is not int or not 1 <= max_entries <= 256:
        raise WorkflowError('Invalid artifact cleanup limit.')
    completed, retained = [], []
    removed_files = 0
    with store.transaction() as db:
        store._now(db)
        rows = list(db.execute('SELECT key,value FROM metadata WHERE key GLOB ? ORDER BY key LIMIT ?',
                               (GC_PREFIX + '*', limit)))
        artifacts = store.root / 'workflows' / 'artifacts'
        for row in rows:
            key = row['key'][len(GC_PREFIX):]
            try:
                identifier(key, workflow=True)
                if json.loads(row['value']) != {'workflow_id': key}:
                    raise WorkflowError('Artifact cleanup identity is unavailable.')
                target = artifacts / key
                # Refuse any replaced parent junction, even when the target is
                # currently absent. Never compute a deletion from persisted paths.
                for parent in (store.root / 'workflows', artifacts):
                    if parent.exists() or parent.is_symlink():
                        if not stat.S_ISDIR(_plain_path(parent, store.root).st_mode):
                            raise WorkflowError('Artifact cleanup parent is unavailable.')
                if not within_root(target, artifacts) or not within_root(target, store.root):
                    raise WorkflowError('Artifact cleanup target is outside managed storage.')
                if target.exists() or target.is_symlink():
                    done, count = _remove_owned_tree(target, target, max_entries)
                    removed_files += count
                    if not done:
                        retained.append(key)
                        continue
                db.execute('DELETE FROM metadata WHERE key=?', (row['key'],))
                completed.append(key)
            except (ValueError, OSError, WorkflowError):
                retained.append(key)
    return {'completed': completed, 'retained': retained, 'removed_files': removed_files}
