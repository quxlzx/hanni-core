"""Bounded public skill discovery and commit-pinned GitHub package downloads."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import re
import time
from urllib.parse import quote, urlencode, urlsplit

import yaml

from hanni.logs.redaction import redact_text
from .skills import FRONT, skill_terms

NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,62}')
REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}')
HOSTS = {'skills.sh', 'www.skills.sh', 'api.github.com', 'raw.githubusercontent.com'}


def fetch_public(url, cap):
    from .local_tools import _http_get
    def allowed(value):
        parts = urlsplit(value)
        return parts.scheme == 'https' and parts.hostname in HOSTS and not parts.username and not parts.password and parts.port in {None, 443}
    if not allowed(url): raise ValueError('Skill downloads require a supported public HTTPS source.')
    final, raw = _http_get(url, cap=cap + 1)
    if not allowed(final): raise ValueError('The skill source redirected outside supported hosts.')
    if len(raw) > cap: raise ValueError('The skill response exceeded its download limit.')
    return raw


def online_search(query, *, limit=6, fetch=fetch_public):
    if (not isinstance(query, str) or not 2 <= len(query.strip()) <= 120
            or redact_text(query) != query or re.search(r'\S+@\S+|https?://|[\r\n]', query)):
        raise ValueError('Search online with a short generic capability, such as calendar scheduling; omit private content and addresses.')
    limit = max(1, min(limit, 6))
    raw = fetch('https://skills.sh/api/search?' + urlencode({'q': query.strip(), 'limit': limit}), 128 * 1024)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('skills'), list):
        raise ValueError('The public skill directory returned an invalid response.')
    rows = []
    for item in data['skills'][:30]:
        if not isinstance(item, dict): continue
        name, source = item.get('name', ''), item.get('source', '')
        if not isinstance(name, str) or not isinstance(source, str) or not NAME.fullmatch(name) or not REPO.fullmatch(source): continue
        rows.append({'name': name, 'repository': source, 'origin': 'internet',
                     'source_url': 'https://github.com/' + source, 'installed': False})
        if len(rows) == limit: break
    return rows


def download_skill(repository, skill, *, fetch=fetch_public, cancelled=lambda: False):
    if not isinstance(repository, str) or not REPO.fullmatch(repository) or '..' in repository:
        raise ValueError('Use a public GitHub repository in owner/repository form.')
    if not isinstance(skill, str) or not NAME.fullmatch(skill): raise ValueError('Choose an exact skill name from discovery.')
    deadline = time.monotonic() + 60
    def read(url, cap):
        if cancelled(): raise InterruptedError('Skill download cancelled.')
        if time.monotonic() > deadline: raise TimeoutError('Skill download exceeded its time budget.')
        value = fetch(url, cap)
        if cancelled(): raise InterruptedError('Skill download cancelled.')
        if time.monotonic() > deadline: raise TimeoutError('Skill download exceeded its time budget.')
        return value
    base = 'https://api.github.com/repos/' + repository
    commit = json.loads(read(base + '/commits/HEAD', 128 * 1024)).get('sha', '')
    if not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('GitHub did not resolve an immutable skill revision.')
    tree = json.loads(read(base + '/git/trees/' + commit + '?recursive=1', 2 * 1024 * 1024))
    nodes = tree.get('tree')
    if tree.get('truncated') or not isinstance(nodes, list) or len(nodes) > 10000:
        raise ValueError('The repository is too large to inspect completely; use a smaller skill repository.')
    candidates = [n for n in nodes if isinstance(n, dict) and isinstance(n.get('path'), str)
                  and PurePosixPath(n['path']).name == 'SKILL.md'
                  and PurePosixPath(n['path']).parent.name == skill]
    if not candidates:
        candidates = [n for n in nodes if isinstance(n, dict) and n.get('path') == 'SKILL.md']
    if len(candidates) != 1: raise ValueError('The skill package was not uniquely identified in that repository.')
    source_path = PurePosixPath(candidates[0]['path'])
    folder = source_path.parent
    selected, seen = [], set()
    for item in nodes:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str): continue
        path = PurePosixPath(item['path'])
        if not path.is_relative_to(folder) or item.get('type') == 'tree': continue
        relative = path.relative_to(folder)
        if (path.is_absolute() or any(p in {'..', '.'} or ':' in p or '\\' in p for p in path.parts)
                or item.get('type') != 'blob' or item.get('mode') not in {'100644', '100755'}
                or not isinstance(item.get('size'), int) or not 0 <= item['size'] <= 256 * 1024):
            raise ValueError('The skill contains an unsafe path, link or oversized support file.')
        if (str(relative).casefold() in seen or any(p.rstrip(' .') != p or p.upper().split('.')[0] in
                {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))} for p in relative.parts)
                or relative.name.casefold() == 'skill.md' and str(relative) != 'SKILL.md'):
            raise ValueError('The skill contains a conflicting filename or a nested skill package.')
        seen.add(str(relative).casefold())
        selected.append((str(relative), item))
    if len(selected) > 32 or sum(item['size'] for _, item in selected) > 1024 * 1024:
        raise ValueError('The skill package exceeds 32 files or 1 MiB.')
    resources = {}
    for relative, item in selected:
        raw = read('https://raw.githubusercontent.com/' + repository + '/' + commit + '/' + quote(item['path'], safe='/'), 256 * 1024)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if len(raw) != item['size'] or blob != item.get('sha'):
            raise ValueError('A skill file did not match the pinned GitHub tree.')
        resources[relative] = raw
    original = resources.pop('SKILL.md', None)
    if original is None: raise ValueError('The downloaded package has no SKILL.md.')
    raw = original.decode('utf-8-sig')
    front = FRONT.match(raw)
    meta = yaml.safe_load(front.group(1)) if front else None
    if not isinstance(meta, dict) or meta.get('name') != skill:
        raise ValueError('The skill name did not match its downloaded frontmatter.')
    description = meta.get('description')
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 500:
        raise ValueError('The downloaded skill needs a description of 1 to 500 characters.')
    metadata = meta.get('metadata') or {}
    hanni = (metadata.get('hanni') or {}) if isinstance(metadata, dict) else {}
    triggers = hanni.get('triggers') if isinstance(hanni, dict) else None
    if not isinstance(triggers, list) or not triggers:
        triggers = [skill.replace('-', ' '), *sorted(skill_terms(description))][:12]
    if any(p.casefold() == 'upstream_skill.md' for p in resources): raise ValueError('The package uses HANNI\'s reserved provenance filename.')
    resources['UPSTREAM_SKILL.md'] = original
    payload = {'name': skill, 'description': description.strip(), 'instructions': raw[front.end():].strip(),
               'triggers': triggers[:12], 'expected_revision': '',
               'verification': 'Package bytes matched the immutable GitHub tree; workflow execution is not verified.',
               'correction': 'Imported on demand for the current task; dependencies and tools still require availability checks.'}
    provenance = {'repository': repository, 'commit_sha': commit, 'source_path': str(source_path),
                  'content_sha256': hashlib.sha256(original).hexdigest()}
    return payload, resources, provenance
