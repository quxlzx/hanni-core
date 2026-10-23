"""Non-blocking, deduplicated local job notifications using the existing adapter."""
import logging
import threading
from queue import Queue, Empty, Full
from hanni.tools.base import ToolRequest


class JobNotifier:
    def __init__(self, registry):
        self.registry = registry
        self.queue = Queue(maxsize=32)
        self.seen = set()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name='hanni-notifications', daemon=True)
        self.thread.start()

    def notify(self, *, job_id, category, message):
        key = (job_id, category)
        with self.lock:
            if key in self.seen:
                return
            self.seen.add(key)
            if len(self.seen) > 2048:
                self.seen = {key}
        try:
            self.queue.put_nowait(message[:200])
        except Full:
            logging.getLogger(__name__).warning('Local notification queue is full')

    def _run(self):
        while not self.stop.is_set():
            try:
                message = self.queue.get(timeout=.2)
            except Empty:
                continue
            try:
                self.registry.execute(ToolRequest('notify.toast', {'title':'H.A.N.N.I.', 'message':message}, source='job-notification'))
            except Exception as exc:
                logging.getLogger(__name__).warning('Local job notification failed (%s)', type(exc).__name__)

    def close(self):
        self.stop.set()
