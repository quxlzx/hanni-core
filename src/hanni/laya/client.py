"""Optional nonblocking HANNI-side publisher; discards all shadow predictions.

Copy this module to HANNI's Python package or make this package importable.
No imports from Laya or HANNI; Python standard library only.
"""
import json
import os
import queue
import threading
import urllib.request
from urllib.parse import urlsplit


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Shadow redirects are forbidden')


class ShadowClient:
    def __init__(self, enabled=False, url='http://127.0.0.1:8765/v1/shadow/evaluate',
                 token='', max_queue=64, timeout_s=2.0):
        self.enabled = bool(enabled)
        self._url = url
        self._token = token
        self._timeout_s = float(timeout_s)
        self._queue = queue.Queue(maxsize=max_queue)
        self._worker = None
        self._closed = False
        self._lock = threading.Lock()
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self.sent = 0
        self.dropped = 0
        self.errors = 0
        # Never ship user memories to remote/public HTTP addresses.
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != '/v1/shadow/evaluate':
            raise ValueError('Shadow URL must be local HTTP /v1/shadow/evaluate')
        if self.enabled and len(token) < 32:
            raise ValueError('Shadow enabled but bearer token missing')
        if self.enabled:
            self._worker = threading.Thread(target=self._run, daemon=True, name='hanni-laya-shadow')
            self._worker.start()

    @classmethod
    def from_env(cls):
        return cls(enabled=os.getenv('HANNI_LAYA_SHADOW_ENABLED', '').lower() in ('1', 'true', 'yes'),
                   url=os.getenv('HANNI_LAYA_SHADOW_URL', 'http://127.0.0.1:8765/v1/shadow/evaluate'),
                   token=os.getenv('HANNI_LAYA_SHADOW_TOKEN', ''))

    def observe(self, *, utterance=None, existing_memory=None, request=None, candidate_memory=None):
        """Fast, non-blocking, best-effort copy. Never returns a decision."""
        if not self.enabled or self._closed:
            return False
        p = {k:v for k,v in {
            'utterance':utterance, 'existing_memory':existing_memory,
            'request':request, 'candidate_memory':candidate_memory
        }.items() if v is not None}
        try:
            if not p or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in p.values()):
                self.dropped += 1
                return False
            with self._lock:
                if not self.enabled or self._closed:
                    return False
                self._queue.put_nowait(p)
                return True
        except queue.Full:
            self.dropped += 1
            return False

    def _run(self):
        while True:
            p = self._queue.get()
            try:
                if p is None:
                    return
                with self._lock:
                    if self._closed or not self.enabled:
                        self.dropped += 1
                        continue
                body = json.dumps(p).encode('utf-8')
                req = urllib.request.Request(self._url, data=body, method='POST', headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + self._token,
                })
                with self._lock:
                    if self._closed or not self.enabled:
                        self.dropped += 1
                        continue
                with self._opener.open(req, timeout=self._timeout_s) as response:
                    # Ignore all content; shadow can never make a decision in HANNI.
                    if response.status == 200:
                        self.sent += 1
                    else:
                        self.errors += 1
            except Exception:
                # Optional instrumentation only, never impact HANNI.
                self.errors += 1
            finally:
                self._queue.task_done()

    def close(self):
        """Stop admissions and discard queued text; an active HTTP call may finish."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            while True:
                try:
                    item = self._queue.get_nowait()
                    if item is not None:
                        self.dropped += 1
                    self._queue.task_done()
                except queue.Empty:
                    break
            if self._worker is not None:
                # Admissions share this lock, so the drained queue has room.
                self._queue.put_nowait(None)
