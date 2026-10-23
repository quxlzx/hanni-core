"""Read-only identity admission and bounded recording for the configured model."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import time
from unittest.mock import patch
import urllib.request
from urllib.parse import urlsplit
from scripts.campaign10_manager.admission import original_model_admission
from scripts.campaign9_tools.live import WireResponse

class AdmissionError(RuntimeError):
    pass

class ModelBudget:

    def __init__(self, output, maximum=450):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.maximum = maximum
        self.wire = []
        self.admissions = []
        self.task_id = None
        self.prompts = []
        self.task_posts = 0
        self.deadline = 0
        self.initial = None
        self.ledger = Path(__file__).resolve().parents[2] / 'data/campaign10-manager/MODEL_BUDGET_LEDGER.json'

    def reserve(self):
        import msvcrt
        lock_path = self.ledger.with_suffix('.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a+b') as lock:
            lock.seek(0)
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                data = json.loads(self.ledger.read_text(encoding='utf8')) if self.ledger.exists() else {'admitted': 0, 'maximum': 450}
                if data['maximum'] != 450 or data['admitted'] >= 450:
                    raise AdmissionError('The entire campaign generation budget is exhausted.')
                data['admitted'] += 1
                self.ledger.write_text(json.dumps(data) + '\n', encoding='utf8')
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def begin(self, task_id, prompts):
        self.task_id = task_id
        self.prompts = list(prompts)
        self.task_posts = 0
        self.deadline = time.monotonic() + 140

    def save(self):
        rows = []
        for record in self.wire:
            item = {k: v for k, v in record.items() if k != '_raw'}
            item['raw_response'] = bytes(record.get('_raw', b'')).decode('utf8', errors='replace')
            rows.append(item)
        for name, value in [('WIRE.json', rows), ('ADMISSIONS.json', self.admissions)]:
            (self.output / name).write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf8')

    @contextmanager
    def transport(self, *, starting_owned_model=False):
        raw = urllib.request.OpenerDirector.open
        if starting_owned_model and self.maximum != 0:
            raise AdmissionError('Deferred startup identity is permitted only with zero generation budget.')
        self.initial = None if starting_owned_model else original_model_admission()

        def guarded(opener, request, *args, **kwargs):
            url = getattr(request, 'full_url', str(request))
            parts = urlsplit(url)
            method = request.get_method() if hasattr(request, 'get_method') else 'GET'
            if (parts.scheme, parts.hostname, parts.port) != ('http', '127.0.0.1', 8080):
                raise AdmissionError('Only the existing configured loopback inference server is admitted.')
            record = None
            if method == 'POST':
                body = json.loads(request.data)
                if parts.path != '/v1/chat/completions' or self.task_id is None:
                    raise AdmissionError('No unassigned generation is admitted.')
                if len(self.wire) >= self.maximum or self.task_posts >= 3 or time.monotonic() > self.deadline:
                    raise AdmissionError('The fixed inference budget is exhausted.')
                if type(body.get('max_tokens')) is not int or not 0 < body['max_tokens'] <= 256 or body.get('temperature') != 0:
                    raise AdmissionError('The fixed generation bounds were exceeded.')
                if not any((m.get('role') == 'user' and m.get('content') in self.prompts for m in body.get('messages', []))):
                    raise AdmissionError('Generation lacks an assigned synthetic task prompt.')
                if len(request.data) > 262144:
                    raise AdmissionError('Payload exceeds the fixed bound.')
                admission = original_model_admission(self.initial['process'] if self.initial else None)
                self.reserve()
                self.admissions.append({'task_id': self.task_id, **admission})
                self.task_posts += 1
                record = {'task_id': self.task_id, 'request_body': deepcopy(body), 'started_at': time.time(), 'finished_at': None, 'status': None, 'response_bytes': 0, 'truncated': False, '_raw': bytearray()}
                self.wire.append(record)
            elif method != 'GET' or parts.path not in {'/health', '/v1/health', '/props', '/slots', '/v1/models'}:
                raise AdmissionError('Only completion and bounded metadata routes are admitted.')
            if len(args) >= 2:
                args = (args[0], min(float(args[1]), 45), *args[2:])
            else:
                kwargs['timeout'] = min(float(kwargs.get('timeout', 45)), 45)
            try:
                response = raw(opener, request, *args, **kwargs)
                if record is not None:
                    record['status'] = getattr(response, 'status', None)
                    return WireResponse(response, record)
                return response
            except Exception as exc:
                if record is not None:
                    record['error'] = {'type': type(exc).__name__, 'message': str(exc)}
                raise
        try:
            with patch.object(urllib.request.OpenerDirector, 'open', guarded):
                yield self
        finally:
            self.save()
