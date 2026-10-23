"""Private metadata-only audit log: no utterance, memory text or secrets."""
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path


def default_path():
    return Path.home() / '.local/state/hanni-laya-shadow/decisions.jsonl'


class PrivateAudit:
    def __init__(self, path=None):
        self.path = Path(path or default_path()).expanduser().resolve()
        # Never put runtime audit trails inside a Git repository.
        if any((part / '.git').exists() for part in (self.path.parent, *self.path.parents)):
            raise ValueError('Refusing to write an audit log inside a Git worktree')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)

    def write(self, request_id, decisions, latency_ms):
        record = {
            'utc': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'shadow_only': True,
            'memory_mutated': False,
            'decisions': decisions,
            'latency_ms': latency_ms,
        }
        # Private file even when caller umask is permissive. One atomic append.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            if hasattr(os, 'fchmod'):
                os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
            else:
                # Windows inherits directory ACLs; chmod sets its writable flag.
                os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
            os.write(fd, (json.dumps(record, separators=(',', ':')) + '\n').encode('utf-8'))
        finally:
            os.close(fd)
