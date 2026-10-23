"""Actual menus scoped to an already identity-verified native QA process."""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import subprocess
import time
_TRAY_MAIN = {}

def named_native_control(window, name, *, action='invoke', timeout=8):
    window.verify()
    powershell = Path(os.environ.get('SystemRoot', 'C:\\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = [str(powershell), '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(Path(__file__).with_name('automation.ps1'))]
    result = subprocess.run(command, input=json.dumps({'hwnd': window.hwnd, 'pid': window.process.pid, 'name': name, 'action': action}), text=True, encoding='utf8', capture_output=True, timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    window.verify()
    if result.returncode:
        raise RuntimeError('Owned native menu automation failed: ' + result.stderr[-500:])
    return json.loads(result.stdout.strip().splitlines()[-1])

def application_menu(window, name):
    import win32api
    import win32con
    import win32gui
    window.verify()
    win32gui.ShowWindow(window.hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(window.hwnd)
    try:
        named_native_control(window, 'Application')
        time.sleep(0.15)
        return named_native_control(window, name)
    except RuntimeError as error:
        positions = {'Open HANNI Mini': 0, 'Restore window': 2, 'Exit desktop': 3}
        if name not in positions:
            raise
        import win32process
        origin = win32gui.ClientToScreen(window.hwnd, (0, 0))
        width = win32gui.GetClientRect(window.hwnd)[2]
        strips = []

        def observe(child, unused):
            if win32process.GetWindowThreadProcessId(child)[1] != window.process.pid:
                return
            rect = win32gui.GetWindowRect(child)
            if win32gui.GetClassName(child).startswith('WindowsForms') and win32gui.IsWindowVisible(child) and (0 <= rect[1] - origin[1] <= 4) and (20 <= rect[3] - rect[1] <= 60) and (rect[2] - rect[0] >= width * 0.8):
                strips.append({'hwnd': child, 'class': win32gui.GetClassName(child), 'rect': list(rect)})
        win32gui.EnumChildWindows(window.hwnd, observe, None)
        if len(strips) != 1:
            raise RuntimeError('Original owned MenuStrip child was not unique.') from error
        strip = strips[0]
        cursor_before = win32gui.GetCursorPos()
        point = win32gui.ClientToScreen(strip['hwnd'], (35, (strip['rect'][3] - strip['rect'][1]) // 2))
        window.verify()
        hit = win32gui.WindowFromPoint(point)
        foreground = win32gui.GetForegroundWindow()
        if not hit or win32process.GetWindowThreadProcessId(hit)[1] != window.process.pid or foreground != window.hwnd:
            raise RuntimeError('Actual MenuStrip cursor target or foreground was not owned.')
        try:
            win32api.SetCursorPos(point)
            window.verify()
            if win32process.GetWindowThreadProcessId(win32gui.WindowFromPoint(point))[1] != window.process.pid:
                raise RuntimeError('MenuStrip point ownership changed before mouse input.')
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.2)
            from scripts.campaign8_native.native_controls import keys
            keys(window, [win32con.VK_HOME], preserve_owned_foreground=True)
            for unused in range(positions[name]):
                keys(window, [win32con.VK_DOWN], preserve_owned_foreground=True)
            keys(window, [win32con.VK_RETURN], preserve_owned_foreground=True)
        finally:
            foreground = win32gui.GetForegroundWindow()
            if foreground and win32process.GetWindowThreadProcessId(foreground)[1] == window.process.pid and (win32gui.GetCursorPos() == point):
                win32api.SetCursorPos(cursor_before)
        return {'name': name, 'input_layer': 'Actual cursor click on verified owned MenuStrip then owned-foreground Home/Enter', 'owned_menu_strip': strip, 'point': list(point), 'uia_failure': str(error)[-500:]}

def owned_tray_handles(process):
    import win32gui
    import win32process
    process.verify()
    found = []

    def observe(hwnd, unused):
        if win32process.GetWindowThreadProcessId(hwnd)[1] != process.pid:
            return
        window_class = win32gui.GetClassName(hwnd)
        if window_class.startswith('hanni-os') and window_class.endswith('SystemTrayIcon'):
            found.append(hwnd)
    win32gui.EnumWindows(observe, None)
    return found

def tray_restore(process):
    import win32con
    import win32gui
    handles = owned_tray_handles(process)
    main = _TRAY_MAIN.get((process.pid, process.create_time))
    if main not in handles:
        raise RuntimeError('Discover the actual owned tray popup before default restore.')
    win32gui.PostMessage(main, 1024 + 11, 0, win32con.WM_LBUTTONUP)
    time.sleep(0.2)
    process.verify()
    return {'tray_hwnd': main, 'message': 'Owned tray default Open HANNI OS action'}

def tray_menu(process, name=None):
    """Inspect/invoke the actual owned popup item via its native command ID."""
    import win32con
    import win32gui
    import win32process
    handles = owned_tray_handles(process)
    if not 1 <= len(handles) <= 2:
        raise RuntimeError('The original owned tray window pair is unavailable or ambiguous.')
    menu_window = None
    for tray in handles:
        win32gui.PostMessage(tray, 1024 + 11, 0, win32con.WM_RBUTTONUP)
        deadline = time.monotonic() + 0.7
        while time.monotonic() < deadline:
            found = []

            def observe(hwnd, unused):
                if win32process.GetWindowThreadProcessId(hwnd)[1] == process.pid and win32gui.GetClassName(hwnd) == '#32768':
                    found.append(hwnd)
            win32gui.EnumWindows(observe, None)
            if len(found) == 1:
                menu_window = found[0]
                _TRAY_MAIN[process.pid, process.create_time] = tray
                break
            time.sleep(0.05)
        if menu_window is not None:
            break
    if menu_window is None:
        raise RuntimeError('Owned native tray popup did not open.')
    process.verify()
    menu = win32gui.SendMessage(menu_window, 481, 0, 0)
    items = []
    for index in range(win32gui.GetMenuItemCount(menu)):
        label = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetMenuStringW(menu, index, label, 256, win32con.MF_BYPOSITION)
        if label.value:
            items.append({'name': label.value, 'index': index, 'command_id': win32gui.GetMenuItemID(menu, index), 'checked': bool(win32gui.GetMenuState(menu, index, win32con.MF_BYPOSITION) & win32con.MF_CHECKED)})
    matches = [item for item in items if item['name'] == name] if name is not None else []
    if name is not None and len(matches) != 1:
        win32gui.PostMessage(menu_window, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        raise RuntimeError('Requested actual tray menu item was not found uniquely.')
    if name is not None:
        win32gui.SendMessage(menu_window, 485, matches[0]['index'], 0)
        win32gui.PostMessage(menu_window, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        time.sleep(0.25)
    else:
        win32gui.PostMessage(menu_window, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        time.sleep(0.1)
    process.verify()
    return {'tray_hwnd': tray, 'menu_hwnd': menu_window, 'items': items, 'invoked': name, 'input_layer': 'Actual owned Win32 popup selection/Enter; not a fabricated callback'}
