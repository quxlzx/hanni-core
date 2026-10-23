"""One explicit Windows accelerator; never a keyboard hook or a command router."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import queue
import threading
import logging

SHORTCUTS = {
    'Ctrl+Shift+Space': (0x0002 | 0x0004 | 0x4000, 0x20),
    'Ctrl+Alt+Space': (0x0002 | 0x0001 | 0x4000, 0x20),
    'Alt+Shift+Space': (0x0001 | 0x0004 | 0x4000, 0x20),
    'Ctrl+Shift+H': (0x0002 | 0x0004 | 0x4000, 0x48),
}
DEFAULT_SHORTCUT = 'Ctrl+Shift+Space'


class HotkeyRegistration:
    """Atomic change: a conflict leaves the previous shortcut registered."""
    def __init__(self, api):
        self.api = api
        self.current = None
        self.identifier = None
        self.error = ''

    def configure(self, shortcut):
        if shortcut not in SHORTCUTS:
            raise ValueError('Choose one of the supported HANNI Mini shortcuts.')
        if self.current == shortcut:
            self.error = ''
            return self.status()
        new_id = 0x4A11 if self.identifier != 0x4A11 else 0x4A12
        modifiers, key = SHORTCUTS[shortcut]
        if not self.api.RegisterHotKey(None, new_id, modifiers, key):
            self.error = f'{shortcut} is in use by another application. Choose another shortcut or use the tray menu.'
            return self.status()
        old_id = self.identifier
        self.current, self.identifier, self.error = shortcut, new_id, ''
        if old_id is not None:
            self.api.UnregisterHotKey(None, old_id)
        return self.status()

    def status(self):
        return {'shortcut': self.current, 'error': self.error, 'choices': list(SHORTCUTS)}

    def close(self):
        if self.identifier is not None:
            self.api.UnregisterHotKey(None, self.identifier)
        self.identifier, self.current = None, None


class GlobalHotkey:
    WM_CONFIGURE = 0x8001

    def __init__(self, callback, shortcut=DEFAULT_SHORTCUT):
        self.callback, self.shortcut = callback, shortcut
        self.ready, self.stopping = threading.Event(), threading.Event()
        self.commands = queue.Queue()
        self.lock = threading.RLock()
        self.registration = None
        self.thread_id = None
        self.thread = None

    def start(self):
        if self.stopping.is_set():
            return self.status()
        self.thread = threading.Thread(target=self._run, name='hanni-mini-shortcut', daemon=True)
        self.thread.start()
        self.ready.wait(3)
        return self.status()

    def status(self):
        with self.lock:
            if self.registration:
                return self.registration.status()
        return {'shortcut': None, 'error': 'Global shortcut is not available yet.', 'choices': list(SHORTCUTS)}

    def configure(self, shortcut):
        if shortcut not in SHORTCUTS:
            raise ValueError('Choose one of the supported HANNI Mini shortcuts.')
        if self.stopping.is_set() or not self.thread_id:
            return self.status()
        complete, result = threading.Event(), {}
        self.commands.put((shortcut, complete, result))
        ctypes.windll.user32.PostThreadMessageW(self.thread_id, self.WM_CONFIGURE, 0, 0)
        if not complete.wait(3):
            return {**self.status(), 'error': 'Shortcut update timed out. Try again.'}
        return result

    def stop(self):
        self.stopping.set()
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(3)

    def _run(self):
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        # Explicit signatures keep thread IDs and message pointers correct on 64-bit Windows.
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        message = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        self.thread_id = kernel32.GetCurrentThreadId()
        with self.lock:
            self.registration = HotkeyRegistration(user32)
            self.registration.configure(self.shortcut)
        self.ready.set()
        try:
            while not self.stopping.is_set() and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == self.registration.identifier:
                    if not self.stopping.is_set():
                        try:
                            self.callback()
                        except Exception:
                            logging.getLogger('hanni.desktop').exception('Mini shortcut activation failed')
                elif message.message == self.WM_CONFIGURE:
                    while True:
                        try:
                            shortcut, complete, result = self.commands.get_nowait()
                        except queue.Empty:
                            break
                        with self.lock:
                            result.update(self.registration.configure(shortcut))
                        complete.set()
        finally:
            with self.lock:
                self.registration.close()
                self.thread_id = None
