"""Explicit, content-addressed attachment transfer, separate from task submission."""
import base64
import hashlib
import os
from pathlib import Path
import re


def prepare(path, roots):
    from hanni.tools.sensitive_paths import is_sensitive_path
    from hanni.logs.redaction import redact_text
    source = Path(path).expanduser()
    if any(part.is_symlink() for part in [source, *source.parents]):
        raise ValueError('Attachment symlinks are not permitted.')
    source = source.resolve()
    if not any(source.is_relative_to(Path(root).resolve()) for root in roots) or is_sensitive_path(source):
        raise ValueError('Attachment is outside explicitly authorized roots or is sensitive.')
    if not source.is_file() or source.stat().st_size > 4*1024*1024:
        raise ValueError('Attachment must be a file of at most 4 MiB.')
    raw = source.read_bytes()
    if len(raw) > 4*1024*1024:
        raise ValueError('Attachment changed beyond limit.')
    if source.suffix.lower() in {'.txt', '.json', '.yaml', '.yml', '.md', '.csv'}:
        text = raw.decode('utf-8', errors='replace')
        if redact_text(text) != text:
            raise ValueError('Credential-like content cannot be transferred.')
    if source.suffix.lower() not in {'.txt', '.md', '.pdf', '.png', '.jpg', '.jpeg', '.wav', '.csv'}:
        raise ValueError('Unsupported attachment type.')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'suffix': source.suffix.lower(),
            'content': base64.b64encode(raw).decode('ascii')}


def receive(payload, root, *, container_root='/data'):
    if set(payload) != {'sha256', 'suffix', 'content'} or not re.fullmatch('[0-9a-f]{64}', payload['sha256']):
        raise ValueError('Invalid attachment contract.')
    if payload['suffix'] not in {'.txt', '.md', '.pdf', '.png', '.jpg', '.jpeg', '.wav', '.csv'}:
        raise ValueError('Unsupported attachment type.')
    raw = base64.b64decode(payload['content'], validate=True)
    if len(raw) > 4*1024*1024 or hashlib.sha256(raw).hexdigest() != payload['sha256']:
        raise ValueError('Attachment size/digest mismatch.')
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or (os.name != 'nt' and root.stat().st_mode & 0o002):
        raise ValueError('Shared folder is missing, a symlink, or world writable.')
    path = root/(payload['sha256']+payload['suffix'])
    if path.is_symlink():
        raise ValueError('Existing attachment is a symlink.')
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != payload['sha256']:
            raise ValueError('Existing content-addressed file changed.')
    else:
        if len(list(root.glob('*'))) >= 128:
            raise ValueError('Shared-file quota reached; clean up explicitly.')
        with path.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        # UID 10001 owns the protected parent, so it can read this agent-created
        # file without making the parent directory world accessible/writable.
        os.chmod(path, 0o644)
    return {'ok': True, 'sha256': payload['sha256'], 'size_bytes': len(raw),
            'remote_path': str(path), 'container_path': container_root+'/'+path.name,
            'verification': {'verified': True, 'scope': 'saved_bytes_sha256'}}
