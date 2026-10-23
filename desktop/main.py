"""Native Windows WebView2 client. The existing loopback controller stays authoritative.

No HANNI imports here: the portable client never bundles models or the voice stack.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import html
import http.client
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

DEFAULT_URL = 'http://127.0.0.1:8765'
LOG = logging.getLogger('hanni.desktop')
SHORTCUT_CHOICES = ('Ctrl+Shift+Space', 'Ctrl+Alt+Space', 'Alt+Shift+Space', 'Ctrl+Shift+H')


def validate_url(value: str) -> str:
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError('The local dashboard port is invalid.') from error
    if (parts.scheme != 'http' or parts.hostname not in {'127.0.0.1', 'localhost'}
            or port is None or not 1 <= port <= 65535 or parts.username is not None
            or parts.password is not None or parts.path not in {'', '/'}
            or parts.query or parts.fragment):
        raise ValueError('Use http://127.0.0.1:PORT or http://localhost:PORT only.')
    return f'http://{parts.hostname}:{port}'


def request_json(url, path, *, body=None, token=None, timeout=2):
    """No proxies, redirects, cookies, or arbitrary destinations."""
    parts = urlsplit(validate_url(url))
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    headers = {'Accept': 'application/json'}
    if token is not None:
        headers['X-Hanni-Token'] = token
    payload = None
    if body is not None:
        headers.update({'Content-Type': 'application/json', 'Origin': url,
                        'X-Hanni-Token': token or ''})
        payload = json.dumps(body)
    try:
        connection.request('POST' if payload is not None else 'GET', path, payload, headers)
        response = connection.getresponse()
        if response.status != 200 and not (payload is not None and response.status == 202):
            raise RuntimeError(f'Local service returned {response.status}.')
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise RuntimeError('Local service response is too large.')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise RuntimeError('Local service response is invalid.')
        return result
    finally:
        connection.close()


def is_hanni(url, *, request=request_json):
    try:
        contract = request(url, '/api/workspace')
        return (contract.get('version') == 1 and contract.get('transport') == 'http-snapshots'
                and isinstance(contract.get('screens'), list)
                and 5 <= len(contract['screens']) <= 32
                and all(isinstance(screen, str) and 0 < len(screen) <= 32 for screen in contract['screens'])
                and {'home', 'chat', 'mission', 'cluster', 'settings'} <= set(contract['screens'])
                and isinstance(contract.get('features'), dict))
    except (OSError, ValueError, RuntimeError, http.client.HTTPException):
        return False


def load_preferences(path):
    defaults = {'width': 1366, 'height': 860, 'x': None, 'y': None,
                'maximized': False, 'close_to_tray': False,
                'minimize_to_tray': False, 'notifications': False,
                'voice_notifications': True,
                'mini_pinned': False, 'mini_shortcut': SHORTCUT_CHOICES[0]}
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(values, dict):
            return defaults
        for key in ('close_to_tray', 'minimize_to_tray', 'notifications', 'voice_notifications', 'maximized', 'mini_pinned'):
            if isinstance(values.get(key), bool):
                defaults[key] = values[key]
        if values.get('mini_shortcut') in SHORTCUT_CHOICES:
            defaults['mini_shortcut'] = values['mini_shortcut']
        for key, low, high in [('width', 640, 7680), ('height', 480, 4320),
                               ('x', -7680, 7680), ('y', -4320, 4320)]:
            value = values.get(key)
            if type(value) is int and low <= value <= high:
                defaults[key] = value
    except (OSError, ValueError):
        pass
    return defaults


def save_preferences(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values, indent=2), encoding='utf-8')
    temporary.replace(path)


def find_repo(explicit=None):
    candidates = [Path(explicit)] if explicit else []
    executable = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve()
    candidates.extend(executable.parents)
    for candidate in candidates:
        if (candidate/'START_HANNI.cmd').is_file() and (candidate/'src/hanni/dashboard/launcher.py').is_file():
            return candidate.resolve()
    return None


def complete_local_navigation(sender, args, origin, inject):
    """Canceled navigations must not reset the live document's native bridge."""
    source = str(sender.Source)
    if args.IsSuccess and (source == 'about:blank' or source.startswith(origin + '/')):
        inject(sender, args)


class BackendSession:
    """Only a monitor process started by this client is owned. Never stop an attached session."""
    def __init__(self, url, repo, *, attach_only=False, popen=subprocess.Popen,
                 request=request_json, verify=is_hanni, run=subprocess.run,
                 autostart_assistant=True):
        self.url, self.repo, self.attach_only = validate_url(url), repo, attach_only
        self.popen, self.request, self.verify = popen, request, verify
        self.run = run
        self.autostart_assistant = autostart_assistant
        self.process = None
        self.owned_token = None
        self.owned_epoch = None
        self.ready_path = None
        self.log = None
        self.assistant_process = None
        self.lock = threading.RLock()
        self.exit_requested = threading.Event()

    def connect(self, log_dir):
        if self.exit_requested.is_set():
            return False
        if self.verify(self.url):
            return True
        if self.attach_only:
            return False
        parts = urlsplit(self.url)
        try:
            with socket.create_connection((parts.hostname, parts.port), timeout=.3):
                raise RuntimeError('The selected port belongs to an unverified local service. Choose another dashboard port.')
        except (ConnectionRefusedError, TimeoutError):
            pass
        if self.repo is None or not (self.repo/'.venv/Scripts/python.exe').is_file():
            raise RuntimeError('The HANNI repository and its Python environment were not found. Run setup first or pass --repo-root.')
        if self.autostart_assistant:
            # The original launcher observes this desktop's lifetime and stops
            # only models owned by that assistant session when we exit.
            self.start_assistant()
            for _ in range(1200):
                if self.exit_requested.is_set():
                    return False
                if self.verify(self.url):
                    return True
                if self.assistant_process is not None and self.assistant_process.poll() is not None:
                    raise RuntimeError('The assistant could not start. Check its launch terminal.')
                self.exit_requested.wait(.1)
            raise RuntimeError('Assistant startup is still unavailable. Check its launch terminal; the desktop will reconnect automatically.')
        log_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            # Closing publishes cancellation before cleanup takes this same lock.
            if self.exit_requested.is_set():
                return False
            ready_path = self.ready_path = log_dir/f'monitor-ready-{uuid4().hex}.json'
            self.log = (log_dir/'monitor.log').open('w', encoding='utf-8')
            command = [str(self.repo/'.venv/Scripts/python.exe'), '-m', 'hanni.dashboard.launcher',
                       '--dashboard-only', '--no-browser', '--port', str(parts.port),
                       '--ready-file', str(ready_path)]
            try:
                process = self.process = self.popen(command, cwd=str(self.repo), stdin=subprocess.DEVNULL,
                    stdout=self.log, stderr=self.log,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except OSError:
                self.log.close()
                self.log = None
                raise
        for _ in range(100):
            if self.exit_requested.is_set():
                return False
            if process.poll() is not None:
                raise RuntimeError('The local monitor did not start. See desktop monitor.log.')
            # Actual child PID, origin, and ChatHub epoch bind ownership even after a port collision.
            if ready_path.is_file():
                ready = json.loads(ready_path.read_text(encoding='utf-8'))
                if (not isinstance(ready, dict) or (ready.get('pid') != process.pid and ready.get('parent_pid') != process.pid)
                        or not isinstance(ready.get('epoch'), str)):
                    raise RuntimeError('Local monitor ownership could not be verified.')
                owned_url = validate_url(ready.get('url', ''))
                if self.verify(owned_url):
                    chat = self.request(owned_url, '/api/chat?before=1')
                    if chat.get('epoch') != ready['epoch'] or not isinstance(chat.get('token'), str) or not chat['token']:
                        raise RuntimeError('Owned monitor session identity did not match.')
                    with self.lock:
                        if self.exit_requested.is_set():
                            return False
                        self.url = owned_url
                        self.owned_epoch, self.owned_token = ready['epoch'], chat['token']
                    return True
            time.sleep(.1)
        raise RuntimeError('The local monitor could not be reached. See desktop monitor.log.')

    def stop_owned(self):
        with self.lock:
            process = self.process
            if process is None:
                return
            try:
                if process.poll() is None and self.owned_token:
                    # Token is pinned at owned startup. A replacement service never receives its own token.
                    chat = self.request(self.url, '/api/chat?before=1')
                    if chat.get('epoch') != self.owned_epoch:
                        raise RuntimeError('Owned monitor epoch no longer matches.')
                    self.request(self.url, '/api/shutdown', body={}, token=self.owned_token, timeout=3)
                    process.wait(timeout=8)
            except (OSError, ValueError, RuntimeError, http.client.HTTPException, subprocess.TimeoutExpired):
                LOG.warning('Owned monitor did not acknowledge graceful shutdown.')
            finally:
                # The owned child was launched dashboard-only; it never owns a voice/model session.
                if process.poll() is None:
                    if os.name == 'nt':
                        # A Windows venv redirector may have its own Python child; stop only this owned tree.
                        taskkill = str(Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32/taskkill.exe')
                        self.run([taskkill, '/PID', str(process.pid), '/T', '/F'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                 timeout=5, check=False)
                    else:
                        process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                self.process = None
                self.owned_token = None
                self.owned_epoch = None
                if self.ready_path:
                    self.ready_path.unlink(missing_ok=True)
                    self.ready_path = None
                if self.log:
                    self.log.close()
                    self.log = None

    def start_assistant(self):
        with self.lock:
            if self.exit_requested.is_set():
                return 'Assistant launch cancelled.'
            if self.repo is None:
                raise RuntimeError('Launch from the HANNI repository or pass --repo-root to use Start Assistant.')
            if self.assistant_process is not None and self.assistant_process.poll() is None:
                return 'The assistant launch terminal is already open.'
            if self.process is None and self.verify(self.url):
                return 'A HANNI session is already running. Use its existing launch terminal.'
            self.stop_owned()
            # Fixed foreground launcher, no shell interpolation and no alternate execution pathway.
            command = [str(Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'),
                       '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                       str(self.repo/'scripts/start_dashboard.ps1'), '-NoBrowser',
                       '-DesktopOwnerPid', str(os.getpid()),
                       '-Port', str(urlsplit(self.url).port)]
            self.assistant_process = self.popen(command, cwd=str(self.repo),
                creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            return 'Assistant launch started. Keep its terminal open for confirmations.'


class MiniBridge:
    """Only window preferences/actions; all assistant requests use the existing HTTP controller."""
    def __init__(self, app):
        self._app = app

    def _check(self):
        app = self._app
        if app.closed.is_set() or app.mini is None:
            raise RuntimeError('HANNI Mini is closed.')
        if app.mini.get_current_url() != app.session.url + '/?view=mini':
            raise RuntimeError('Window controls are restricted to the local Mini view.')
        return app

    def get_state(self):
        app = self._check()
        return {**app.hotkey.status(), 'pinned': app.preferences['mini_pinned']}

    def dismiss(self):
        self._check().dismiss_mini()
        return True

    def pin(self, pinned):
        if type(pinned) is not bool:
            raise ValueError('Pinned must be true or false.')
        app = self._check()
        with app.preferences_lock:
            app.preferences['mini_pinned'] = pinned
            app.apply_mini_pin(pinned)
            app.remember()
        return self.get_state()

    def expand(self):
        app = self._check()
        app.restore()
        if app.loaded_url:
            app.window.evaluate_js("window.location.hash = 'chat'")
        app.dismiss_mini()
        return True

    def configure_hotkey(self, shortcut):
        if not isinstance(shortcut, str) or shortcut not in SHORTCUT_CHOICES:
            raise ValueError('Choose one of the supported HANNI Mini shortcuts.')
        app = self._check()
        result = app.hotkey.configure(shortcut)
        if result['shortcut'] == shortcut:
            with app.preferences_lock:
                app.preferences['mini_shortcut'] = shortcut
                app.remember()
        return {**result, 'pinned': app.preferences['mini_pinned']}


class DesktopApp:
    def __init__(self, session, state_dir, title, preferences):
        self.session, self.state_dir, self.title = session, state_dir, title
        self.preferences, self.window, self.tray = preferences, None, None
        self.exiting = False
        self.closed = getattr(session, 'exit_requested', threading.Event())
        self.loaded_url = False
        self.maximized = preferences['maximized']
        self.normal_geometry = {key:preferences[key] for key in ['width', 'height', 'x', 'y']}
        self.action_lock = threading.Lock()
        self.preferences_lock = threading.RLock()
        self.navigation_handlers = []
        self.guarded_windows = set()
        self.mini = None
        self.mini_visible = False
        self.hotkey = None
        self.notification_feed = None
        self.notification_limit = None
        self.notification_lock = threading.Lock()
        self.voice_notification_feed = None

    def remember(self, *args):
        with self.preferences_lock:
            if self.window is not None and not self.maximized:
                self.normal_geometry.update(width=int(self.window.width), height=int(self.window.height),
                                            x=int(self.window.x), y=int(self.window.y))
            self.preferences.update(self.normal_geometry, maximized=self.maximized)
            save_preferences(self.state_dir/'window.json', self.preferences)

    def close_requested(self):
        self.remember()
        if not self.exiting and self.preferences['close_to_tray'] and self.tray:
            self.window.hide()
            return False
        return True

    def minimize(self):
        if self.preferences['minimize_to_tray'] and self.tray:
            self.window.hide()

    def restore(self, *args):
        self.window.show()
        self.window.restore()

    def exit(self, *args):
        self.exiting = True
        self.window.destroy()

    def show_mini(self, *args):
        if self.closed.is_set() or self.mini is None:
            return
        if self.mini.native is None:
            return
        self.mini_visible = True
        self.mini.show()
        self.mini.restore()
        native = self.mini.native
        ctypes.windll.user32.SetForegroundWindow(int(native.Handle.ToInt64()))
        if self.loaded_url:
            self.mini.evaluate_js("document.querySelector('[data-mini-input]')?.focus()")

    def dismiss_mini(self):
        if self.mini:
            self.mini.hide()
        self.mini_visible = False

    def toggle_mini(self):
        foreground = False
        if self.mini and self.mini.native is not None:
            get_foreground = ctypes.windll.user32.GetForegroundWindow
            get_foreground.restype = ctypes.c_void_p
            foreground = get_foreground() == int(self.mini.native.Handle.ToInt64())
        if self.mini_visible and foreground and not self.preferences['mini_pinned']:
            self.dismiss_mini()
        else:
            self.show_mini()

    def apply_mini_pin(self, pinned):
        if self.mini.native is None:
            self.mini.on_top = pinned
            return
        from System import Action
        # pywebview's WinForms setter lacks its own UI dispatch.
        self.mini.native.Invoke(Action(lambda: setattr(self.mini, 'on_top', pinned)))

    def mini_close_requested(self):
        if self.closed.is_set() or self.exiting:
            return True
        self.dismiss_mini()
        return False

    def toggle(self, key):
        with self.preferences_lock:
            self.preferences[key] = not self.preferences[key]
            self.remember()
        if self.tray:
            self.tray.update_menu()

    def notify(self, message, *, voice=False):
        enabled = self.preferences.get('voice_notifications', True) if voice else self.preferences['notifications']
        if self.tray and enabled and self.tray.HAS_NOTIFICATION:
            with self.notification_lock:
                if not voice and self.notification_limit is not None and not self.notification_limit.admit(time.monotonic()):
                    return
                self.tray.notify(message, self.title)
                if voice:
                    LOG.info('Voice mode notification sent to Windows: %s', message)

    def observe_voice_notifications(self):
        if not self.preferences.get('voice_notifications', True):
            self.voice_notification_feed = None
            return
        try:
            from notifications import VoiceModeFeed
        except ModuleNotFoundError:
            from desktop.notifications import VoiceModeFeed
        if self.voice_notification_feed is None:
            self.voice_notification_feed = VoiceModeFeed()
        token = self.session.request(self.session.url, '/api/chat?before=1').get('token')
        if not isinstance(token, str) or not token or len(token) > 512:
            return
        snapshot = self.session.request(self.session.url, '/api/voice', token=token)
        for message in self.voice_notification_feed.observe(snapshot):
            self.notify(message, voice=True)

    def observe_notifications(self):
        if not self.preferences['notifications']:
            self.notification_feed = None
            return
        try:
            from notifications import NotificationFeed
        except ModuleNotFoundError:
            from desktop.notifications import NotificationFeed
        if self.notification_feed is None:
            self.notification_feed = NotificationFeed()
        # The token stays in memory; this does not create native execution or approval methods.
        token = self.session.request(self.session.url, '/api/chat?before=1').get('token')
        if not isinstance(token, str) or not token or len(token) > 512:
            return
        snapshot = self.session.request(self.session.url, '/api/notifications', token=token)
        for title in self.notification_feed.observe(snapshot):
            self.notify(title)

    def launch_assistant(self, *args):
        if not self.action_lock.acquire(blocking=False):
            return
        try:
            # Native user-initiated operation, never a webpage bridge.
            if ctypes.windll.user32.MessageBoxW(None,
                    'Start the existing HANNI assistant in a visible permissions terminal?\n\n'
                    'This starts the configured model and voice session. Closing the desktop will leave that session running.',
                    'Start Assistant', 0x24) != 6:
                return
            result = self.session.start_assistant()
            if 'already' in result:
                ctypes.windll.user32.MessageBoxW(None, result, 'HANNI OS', 0x40)
            else:
                self.notify(result)
        except (OSError, RuntimeError) as error:
            ctypes.windll.user32.MessageBoxW(None, str(error), 'HANNI OS', 0x10)
        finally:
            self.action_lock.release()

    def constrain_navigation(self, window=None):
        """Block foreign navigations, popups, and requests before dispatch in every view."""
        window = window or self.window
        if window.uid in self.guarded_windows:
            return
        self.guarded_windows.add(window.uid)
        native = window.native
        control = native.browser.webview
        def navigation(sender, args):
            value = str(args.Uri)
            if value != 'about:blank' and not value.startswith(self.session.url + '/'):
                args.Cancel = True
        def popup(sender, args):
            args.Handled = True
        def resource(sender, args):
            uri = str(args.Request.Uri)
            if uri != 'about:blank' and not uri.startswith(self.session.url + '/'):
                # Deny dispatch as well as navigation; WebView2 can prepare a request before cancellation.
                args.Response = sender.Environment.CreateWebResourceResponse(
                    None, 403, 'Blocked by local desktop policy', 'Content-Type: text/plain')
        self.navigation_handlers.extend([navigation, popup, resource])
        control.NavigationStarting += navigation
        def completed(sender, args):
            complete_local_navigation(sender, args, self.session.url, native.browser.on_navigation_completed)
        # The stock handler re-injects Javascript on failed/canceled navigation too.
        # Doing so resets the live Mini bridge even though its document stayed in place.
        control.NavigationCompleted -= native.browser.on_navigation_completed
        control.NavigationCompleted += completed
        self.navigation_handlers.append(completed)
        def block_popups(core):
            # pywebview's false OPEN_EXTERNAL_LINKS setting still navigates in the existing view.
            # Remove that stock handler before installing our handled-only policy.
            core.NewWindowRequested -= native.browser.on_new_window_request
            core.NewWindowRequested += popup
            core.WebResourceRequested += resource
        def initialized(sender, args):
            if args.IsSuccess:
                block_popups(sender.CoreWebView2)
        self.navigation_handlers.append(initialized)
        if control.CoreWebView2 is not None:
            block_popups(control.CoreWebView2)
        else:
            control.CoreWebView2InitializationCompleted += initialized
        # Use the native Windows dark caption while retaining all system window buttons.
        enabled = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(native.Handle.ToInt64()), 20,
                                                  ctypes.byref(enabled), ctypes.sizeof(enabled))
        from System import Action
        from System.Drawing import Color
        def menu_colors():
            background, foreground = Color.FromArgb(28,29,33), Color.FromArgb(238,238,239)
            for item in native.Controls:
                if str(item.GetType().Name) == 'MenuStrip':
                    item.BackColor, item.ForeColor = background, foreground
                    for entry in item.Items:
                        entry.BackColor, entry.ForeColor = background, foreground
                        entry.DropDown.BackColor, entry.DropDown.ForeColor = background, foreground
                        for action in entry.DropDownItems:
                            action.BackColor, action.ForeColor = background, foreground
        native.Invoke(Action(menu_colors))

    def monitor(self):
        self.window.events.shown.wait(15)
        if self.mini:
            self.mini.events.shown.wait(15)
        if self.closed.is_set():
            return
        try:
            if self.hotkey:
                self.hotkey.start()
            self.constrain_navigation()
            if self.closed.is_set():
                return
            self.session.connect(self.state_dir)
        except Exception as error:
            if self.closed.is_set():
                return
            LOG.exception('Desktop connection: %s', error)
            self.window.load_html(offline_html(str(error), self.session.url))
        previous = None
        while not self.closed.is_set():
            connected = self.session.verify(self.session.url)
            if connected and not self.loaded_url:
                self.window.load_url(self.session.url + '/#home')
                if self.mini:
                    self.mini.load_url(self.session.url + '/?view=mini')
                self.loaded_url = True
            if connected != previous and previous is not None:
                self.notify('Local HANNI service reconnected.' if connected else 'Local HANNI service disconnected.')
            previous = connected
            if connected:
                try:
                    self.observe_voice_notifications()
                except (OSError, ValueError, RuntimeError, http.client.HTTPException):
                    pass
                try:
                    self.observe_notifications()
                except (OSError, ValueError, RuntimeError, http.client.HTTPException):
                    # Unsupported/temporarily unavailable notifications do not disrupt the workspace.
                    pass
            self.closed.wait(1)

    def on_closed(self):
        self.closed.set()
        if self.hotkey:
            self.hotkey.stop()
        if self.mini:
            self.mini.destroy()
        if self.tray:
            self.tray.stop()


def offline_html(message, url):
    return ('<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
            'content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'none\'">'
            '<style>body{background:#18191c;color:#eeeeef;font:14px/1.6 Segoe UI;margin:0;display:grid;'
            'place-items:center;height:100vh}.body{max-width:560px;padding:32px}h1{font-size:26px}'
            'p{color:#a5a8b0}b{color:#a4c2e9}small{color:#858993}</style></head><body><div class="body">'
            '<b>h.</b><h1>Connect to your workspace</h1><p>' + html.escape(message) + '</p>'
            '<p>Use Application → Start Assistant to start HANNI in its permissions terminal. '
            'This window reconnects automatically when the local service becomes available.</p><small>'
            + html.escape(url) + '</small></div></body></html>')


def resource_path(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))/name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--repo-root', type=Path)
    parser.add_argument('--attach-only', action='store_true')
    parser.add_argument('--state-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'HANNI OS')
    parser.add_argument('--debug-port', type=int, default=None, help='Optional loopback WebView2 CDP port for local verification only.')
    parser.add_argument('--title', default='HANNI OS')
    args = parser.parse_args(argv)
    try:
        url = validate_url(args.url)
    except ValueError as error:
        parser.error(str(error))
    if args.debug_port is not None and not 1024 <= args.debug_port <= 65535:
        parser.error('debug-port must be 1024..65535')
    if os.name != 'nt':
        parser.error('HANNI OS desktop requires Windows.')
    args.state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=args.state_dir/'desktop.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    # State path distinguishes isolated reviews; production runs have a single native window.
    mutex_name = 'Local\\HanniOS-' + hashlib.sha256(str(args.state_dir.resolve()).encode()).hexdigest()[:24]
    ctypes.windll.kernel32.CreateMutexW.restype = ctypes.c_void_p
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183:
        handle = ctypes.windll.user32.FindWindowW(None, args.title)
        if handle:
            ctypes.windll.user32.ShowWindow(handle, 9)
            ctypes.windll.user32.SetForegroundWindow(handle)
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))
        return 0
    import webview
    try:
        from hotkey import GlobalHotkey
        from notifications import NotificationRateLimit
    except ModuleNotFoundError:
        from desktop.hotkey import GlobalHotkey
        from desktop.notifications import NotificationRateLimit
    from webview.menu import Menu, MenuAction, MenuSeparator
    import pystray
    from PIL import Image
    webview.settings.update(ALLOW_FILE_URLS=False, OPEN_EXTERNAL_LINKS_IN_BROWSER=False,
                            ALLOW_DOWNLOADS=False, REMOTE_DEBUGGING_PORT=args.debug_port)
    preferences = load_preferences(args.state_dir/'window.json')
    session = BackendSession(url, find_repo(args.repo_root), attach_only=args.attach_only)
    app = DesktopApp(session, args.state_dir, args.title, preferences)
    app.hotkey = GlobalHotkey(app.toggle_mini, preferences['mini_shortcut'])
    app.notification_limit = NotificationRateLimit()
    screen = webview.screens[0]
    preferences['width'] = min(preferences['width'], screen.width)
    preferences['height'] = min(preferences['height'], screen.height)
    if preferences['x'] is None or preferences['y'] is None or not any(
            s.x <= preferences['x'] < s.x+s.width-80 and s.y <= preferences['y'] < s.y+s.height-80
            for s in webview.screens):
        preferences['x'] = preferences['y'] = None
    menu = [Menu('Application', [MenuAction('Open HANNI Mini', app.show_mini), MenuSeparator(),
            MenuAction('Start Assistant…', app.launch_assistant),
            MenuAction('Restore window', app.restore), MenuSeparator(),
            MenuAction('Exit desktop', app.exit)])]
    app.window = webview.create_window(args.title, html=offline_html('Connecting to the local HANNI service.', url),
        width=preferences['width'], height=preferences['height'], x=preferences['x'], y=preferences['y'],
        min_size=(640,480), resizable=True, maximized=preferences['maximized'],
        background_color='#18191c', text_select=True, menu=menu)
    app.window.events.closing += app.close_requested
    app.window.events.before_show += lambda: app.constrain_navigation(app.window)
    app.window.events.closed += app.on_closed
    app.window.events.minimized += app.minimize
    app.window.events.resized += app.remember
    app.window.events.moved += app.remember
    def maximize(): app.maximized = True; app.remember()
    def normal(): app.maximized = False; app.remember()
    app.window.events.maximized += maximize
    app.window.events.restored += normal
    app.mini = webview.create_window('HANNI Mini', html=offline_html('Connecting to your shared conversation.', url),
        width=640, height=460, min_size=(420, 320), hidden=True, frameless=True, easy_drag=False,
        on_top=preferences['mini_pinned'], background_color='#18191c', text_select=True,
        js_api=MiniBridge(app))
    app.mini.events.before_show += lambda: app.constrain_navigation(app.mini)
    app.mini.events.closing += app.mini_close_requested
    tray_menu = pystray.Menu(
        pystray.MenuItem('Open HANNI OS', app.restore, default=True),
        pystray.MenuItem('Open HANNI Mini', app.show_mini),
        pystray.MenuItem('Start Assistant…', app.launch_assistant),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Close to tray', lambda icon, item:app.toggle('close_to_tray'), checked=lambda item:app.preferences['close_to_tray']),
        pystray.MenuItem('Minimize to tray', lambda icon, item:app.toggle('minimize_to_tray'), checked=lambda item:app.preferences['minimize_to_tray']),
        pystray.MenuItem('Desktop notifications', lambda icon, item:app.toggle('notifications'), checked=lambda item:app.preferences['notifications']),
        pystray.MenuItem('Listening mode notifications', lambda icon, item:app.toggle('voice_notifications'), checked=lambda item:app.preferences['voice_notifications']),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Exit desktop', app.exit))
    try:
        app.tray = pystray.Icon('hanni-os', Image.open(resource_path('hanni.ico')), args.title, tray_menu)
        threading.Thread(target=app.tray.run, name='hanni-desktop-tray', daemon=True).start()
        # CDP testing needs the port, not a visible DevTools window or its remote welcome content.
        webview.start(app.monitor, gui='edgechromium', debug=False,
                      private_mode=False, storage_path=str(args.state_dir/'webview'), icon=str(resource_path('hanni.ico')))
        return 0
    except Exception:
        LOG.exception('Native desktop startup failed')
        ctypes.windll.user32.MessageBoxW(None, 'The desktop could not start. Check desktop.log in your HANNI OS state folder. '
            'The Microsoft Edge WebView2 runtime is required.', 'HANNI OS', 0x10)
        return 1
    finally:
        app.closed.set()
        app.hotkey.stop()
        if app.tray:
            app.tray.stop()
        session.stop_owned()
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == '__main__':
    raise SystemExit(main())
