"""Versioned untrusted advisory contract, isolated from authoritative memory.

Existing /v1/shadow/evaluate stays acknowledgement-only. This contract must be
explicitly enabled at the server and independently gated at the HANNI client.
"""
from __future__ import annotations

import hashlib
import json
import queue
import threading
import time
import re
import urllib.request
from urllib.parse import urlsplit

from hanni.laya.engine import ShadowEngine
from hanni.memory.privacy import validate_memory_text

VERSION = 1
MAX_CANDIDATES = 8
MAX_BYTES = 16384


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Advisory redirects are forbidden')


def validate_request(payload):
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload.get('version') != VERSION:
        raise ValueError('Unsupported advisory contract')
    operation = payload.get('operation')
    keys = {'version', 'request_id', 'operation', 'utterance'} if operation == 'analyze' else {'version', 'request_id', 'operation', 'request', 'candidates'}
    if operation not in {'analyze', 'rank'} or set(payload) != keys:
        raise ValueError('Invalid advisory operation or fields')
    if not isinstance(payload['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', payload['request_id']):
        raise ValueError('Invalid request identifier')
    if len(json.dumps(payload).encode('utf-8')) > MAX_BYTES:
        raise ValueError('Advisory request exceeds payload bound')
    field = 'utterance' if operation == 'analyze' else 'request'
    validate_memory_text(payload[field], max_chars=1200)
    if operation == 'rank':
        candidates = payload['candidates']
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES:
            raise ValueError('Invalid candidate count')
        ids = set()
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {'id', 'content', 'updated_at'}:
                raise ValueError('Unknown candidate fields')
            if not isinstance(candidate['id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', candidate['id']) or candidate['id'] in ids:
                raise ValueError('Invalid or duplicate candidate identifier')
            ids.add(candidate['id'])
            if not isinstance(candidate['updated_at'], str) or not 1 <= len(candidate['updated_at']) <= 80:
                raise ValueError('Candidate revision required')
            validate_memory_text(candidate['content'], max_chars=1200)
    return payload


class AdvisoryEngine:
    """Uses the checkpoint's unchanged training-time question contract."""
    def __init__(self, predictor):
        self.shadow = ShadowEngine(predictor)

    def evaluate(self, payload):
        payload = validate_request(payload)
        started = time.perf_counter()
        result = {'version': VERSION, 'request_id': payload['request_id'], 'operation': payload['operation'],
                  'uncalibrated': True, 'memory_mutated': False}
        if payload['operation'] == 'analyze':
            predictions, _ = self.shadow.evaluate({'utterance': payload['utterance']})
            if not 0 <= predictions['importance'] <= 3:
                raise ValueError('Importance outside model score range')
            result['suggestions'] = predictions
        else:
            rankings = []
            for candidate in payload['candidates']:
                prediction, _ = self.shadow.evaluate({'request': payload['request'], 'candidate_memory': candidate['content']})
                rankings.append({'id': candidate['id'], 'updated_at': candidate['updated_at'], 'relevant': prediction['relevance']})
            result['rankings'] = rankings
        result['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
        return result


def validate_response(response, request):
    """Reject invented IDs, authority fields, nonboolean labels and stale revisions."""
    if not isinstance(response, dict):
        raise ValueError('Expected advisory response object')
    common = {'version', 'request_id', 'operation', 'uncalibrated', 'memory_mutated', 'latency_ms'}
    fields = common | ({'rankings'} if request['operation'] == 'rank' else {'suggestions'})
    if set(response) != fields or type(response.get('version')) is not int or response.get('version') != VERSION or response.get('request_id') != request['request_id'] or response.get('operation') != request['operation'] or response.get('memory_mutated') is not False or response.get('uncalibrated') is not True:
        raise ValueError('Invalid or unauthorized advisory response')
    import math
    if isinstance(response['latency_ms'], bool) or not isinstance(response['latency_ms'], (int, float)) or not math.isfinite(response['latency_ms']) or response['latency_ms'] < 0:
        raise ValueError('Invalid latency metadata')
    if request['operation'] == 'rank':
        expected = {candidate['id']: candidate['updated_at'] for candidate in request['candidates']}
        rankings = response['rankings']
        if not isinstance(rankings, list) or len(rankings) != len(expected):
            raise ValueError('Missing candidate results')
        seen = set()
        for ranking in rankings:
            if not isinstance(ranking, dict) or set(ranking) != {'id', 'updated_at', 'relevant'} or not isinstance(ranking['id'], str) or ranking['id'] in seen or expected.get(ranking['id']) != ranking['updated_at'] or not isinstance(ranking['relevant'], bool):
                raise ValueError('Invalid candidate result')
            seen.add(ranking['id'])
    else:
        suggestions = response['suggestions']
        if not isinstance(suggestions, dict) or set(suggestions) != {'capture', 'importance', 'sensitive'}:
            raise ValueError('Invalid suggestions')
        if any(not isinstance(suggestions[field], bool) for field in ('capture', 'sensitive')) or isinstance(suggestions['importance'], bool) or not isinstance(suggestions['importance'], (int, float)) or not math.isfinite(suggestions['importance']) or not 0 <= suggestions['importance'] <= 3:
            raise ValueError('Invalid suggestion scores')
    return response


class AdvisoryClient:
    """Bounded async inference with separate stored/remote consent; no DB handle.

    Cache keys include current content/revisions, so deletion/correction cannot
    reintroduce old results. Cache stores only IDs and booleans, never raw text.
    """
    def __init__(self, *, enabled=False, retrieval_enabled=False, quality_gate_passed=False,
                 url='http://127.0.0.1:8766/v1/advisory/evaluate', token='', transport='local',
                 allow_stored_memories=False, allow_remote_text=False, allow_remote_memories=False,
                 timeout_seconds=1.5, max_queue=8, cache_seconds=30, opener=None, clock=time.monotonic,
                 admission_guard=None):
        endpoint = urlsplit(url)
        if endpoint.scheme != 'http' or endpoint.hostname not in {'127.0.0.1', 'localhost'} or endpoint.path != '/v1/advisory/evaluate' or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError('Advisory URL must be loopback HTTP')
        if transport not in {'local', 'remote-ssh'} or not .05 <= timeout_seconds <= 3 or not 1 <= max_queue <= 32 or not 1 <= cache_seconds <= 60:
            raise ValueError('Invalid advisory limits')
        self.enabled = bool(enabled and quality_gate_passed)
        self._quality_gate_passed = bool(quality_gate_passed)
        self.admission_guard = admission_guard
        self.retrieval_enabled = bool(self.enabled and retrieval_enabled)
        self.status = ('disabled' if not enabled else 'unavailable: independent model gate not verified' if not quality_gate_passed else 'connecting')
        self.url, self._token, self.transport = url, token, transport
        self.allow_stored_memories, self.allow_remote_text, self.allow_remote_memories = allow_stored_memories, allow_remote_text, allow_remote_memories
        self.timeout_seconds, self.cache_seconds, self._clock = timeout_seconds, cache_seconds, clock
        self._queue = queue.Queue(maxsize=max_queue)
        self._cache, self._pending = {}, set()
        self._lock = threading.Lock()
        self._closed = False
        self._epoch = 0
        self._opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self.sent = self.dropped = self.errors = 0
        self._worker = None
        if self.enabled:
            if len(token) < 32:
                raise ValueError('Advisory enabled without authenticated token')
            self._worker = threading.Thread(target=self._run, name='hanni-laya-advisory', daemon=True)
            self._worker.start()

    @staticmethod
    def _rank_request(goal, records):
        candidates = [{'id': record.id, 'content': record.content, 'updated_at': record.updated_at.isoformat()} for record in records]
        key = hashlib.sha256(json.dumps([goal, candidates], sort_keys=True).encode('utf-8')).hexdigest()
        return key, {'version': VERSION, 'request_id': key, 'operation': 'rank', 'request': goal, 'candidates': candidates}

    def submit_rank(self, goal, records, *, validation=None):
        if not self._rank_allowed():
            return False
        try:
            key, request = self._rank_request(goal, records)
            validate_request(request)
        except (TypeError, ValueError):
            self.dropped += 1
            return False
        with self._lock:
            self._expire()
            if key in self._pending or key in self._cache:
                return False
            try:
                self._queue.put_nowait((self._epoch, key, request, validation))
                self._pending.add(key)
                return True
            except queue.Full:
                self.dropped += 1
                return False

    def cached_rank(self, goal, records):
        if not self._rank_allowed():
            return None
        key, _ = self._rank_request(goal, records)
        with self._lock:
            self._expire()
            cached = self._cache.get(key)
            if not cached:
                return None
            if cached[2] is not None:
                try:
                    current = bool(cached[2]())
                except Exception:
                    current = False
                if not current:
                    self._cache.pop(key, None)
                    return None
            ranks = cached[1]['rankings']
            # Stable deterministic order among candidates with the same binary
            # label; no invented calibrated scores or extra memory identifiers.
            return tuple(row['id'] for row in sorted(ranks, key=lambda row: row['relevant'], reverse=True))

    def submit_analysis(self, utterance):
        if not self._analysis_allowed():
            return False
        key = hashlib.sha256(('analysis:' + utterance).encode('utf-8')).hexdigest()
        request = {'version': VERSION, 'request_id': key, 'operation': 'analyze', 'utterance': utterance}
        try:
            validate_request(request)
        except (TypeError, ValueError):
            self.dropped += 1
            return False
        with self._lock:
            self._expire()
            if key in self._pending or key in self._cache:
                return False
            try:
                self._queue.put_nowait((self._epoch, key, request, None))
                self._pending.add(key)
                return True
            except queue.Full:
                self.dropped += 1
                return False

    def cached_analysis(self, utterance):
        if not self._analysis_allowed():
            return None
        key = hashlib.sha256(('analysis:' + utterance).encode('utf-8')).hexdigest()
        with self._lock:
            self._expire()
            cached = self._cache.get(key)
            return dict(cached[1]['suggestions']) if cached and not self._closed else None

    def _analysis_allowed(self):
        try:
            admitted = self.admission_guard is None or bool(self.admission_guard())
        except Exception:
            admitted = False
        return admitted and self.enabled and self._quality_gate_passed and not self._closed and (self.transport != 'remote-ssh' or self.allow_remote_text)

    def _rank_allowed(self):
        return self._analysis_allowed() and self.retrieval_enabled and self.allow_stored_memories and (self.transport != 'remote-ssh' or self.allow_remote_memories)

    def _expire(self):
        now = self._clock()
        self._cache = {key: value for key, value in self._cache.items() if now - value[0] < self.cache_seconds}
        while len(self._cache) >= 64:
            self._cache.pop(next(iter(self._cache)))

    def _run(self):
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                epoch, key, request, validation = item
                with self._lock:
                    allowed = self._rank_allowed() if request['operation'] == 'rank' else self._analysis_allowed()
                    if not allowed or epoch != self._epoch:
                        continue
                if validation is not None and not validation():
                    continue
                http = urllib.request.Request(self.url, data=json.dumps(request).encode('utf-8'), method='POST',
                                              headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self._token})
                # Recheck after source validation/payload construction, directly
                # before opening the socket. Runtime Safe Mode can change while
                # a queued request is waiting behind another inference.
                with self._lock:
                    allowed = self._rank_allowed() if request['operation'] == 'rank' else self._analysis_allowed()
                    if not allowed or epoch != self._epoch:
                        continue
                with self._opener.open(http, timeout=self.timeout_seconds) as response:
                    raw = response.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES or response.status != 200:
                        raise ValueError('Invalid advisory HTTP response')
                    result = validate_response(json.loads(raw.decode('utf-8')), request)
                with self._lock:
                    allowed = self._rank_allowed() if request['operation'] == 'rank' else self._analysis_allowed()
                    published = False
                    if not self._closed and epoch == self._epoch and allowed:
                        self._cache[key] = (self._clock(), result, validation)
                        published = True
                if published:
                    self.sent += 1
                    self.status = 'production retrieval enabled' if self.retrieval_enabled else 'advisory'
            except Exception:
                self.errors += 1
                if not self._closed:
                    self.status = 'unavailable'
            finally:
                if item is not None:
                    with self._lock:
                        self._pending.discard(item[1])
                self._queue.task_done()

    def invalidate(self):
        with self._lock:
            self._epoch += 1
            self._cache.clear()
            while True:
                try:
                    item = self._queue.get_nowait()
                    if item is not None:
                        self._pending.discard(item[1])
                    self._queue.task_done()
                except queue.Empty:
                    break

    def close(self):
        self._closed = True
        self.invalidate()
        # Do not retain queued raw memories after shutdown.
        while True:
            try:
                item = self._queue.get_nowait()
                if item is not None:
                    with self._lock:
                        self._pending.discard(item[1])
                self._queue.task_done()
            except queue.Empty:
                break
        if self._worker is not None:
            self._queue.put_nowait(None)
        self.status = 'disabled'


def from_config(config, *, token='', quality_gate_passed=False, opener=None, admission_guard=None):
    """Create an isolated client without loading models, SSH, or reading secrets.

    The default quality gate is closed. Configuration enablement alone cannot
    assert independent validation. Caller supplies a private token only after
    reviewing installed model/contract identity and independent rollout gates.
    """
    cfg = getattr(getattr(config, 'hanni', config), 'laya', config)
    return AdvisoryClient(enabled=cfg.advisory_enabled, retrieval_enabled=cfg.retrieval_enabled,
                          quality_gate_passed=quality_gate_passed, url=cfg.url, token=token,
                          transport=cfg.transport, allow_stored_memories=cfg.allow_stored_memories,
                          allow_remote_text=cfg.allow_remote_text, allow_remote_memories=cfg.allow_remote_memories,
                          timeout_seconds=cfg.timeout_seconds, max_queue=cfg.max_queue,
                          cache_seconds=cfg.cache_seconds, opener=opener, admission_guard=admission_guard)
