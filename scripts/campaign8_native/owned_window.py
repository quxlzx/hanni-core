"""Capture only an identity-verified owned HWND, without desktop pixel fallback."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path
import time

class NativeCaptureUnavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class OwnedProcess:
    pid: int
    create_time: float
    executable: str

    def verify(self, process_factory=None):
        if process_factory is None:
            import psutil
            process_factory = psutil.Process
        current = process_factory(self.pid)
        if current.create_time() != self.create_time or str(Path(current.exe()).resolve()).casefold() != str(Path(self.executable).resolve()).casefold():
            raise NativeCaptureUnavailable('Owned native process identity changed.')
        return current

@dataclass(frozen=True)
class OwnedWindow:
    process: OwnedProcess
    hwnd: int
    title: str
    window_class: str

    def verify(self, *, gui=None, process_api=None, process_factory=None):
        self.process.verify(process_factory)
        if gui is None:
            import win32gui as gui
        if process_api is None:
            import win32process as process_api
        if not gui.IsWindow(self.hwnd) or process_api.GetWindowThreadProcessId(self.hwnd)[1] != self.process.pid or gui.GetWindowText(self.hwnd) != self.title or (gui.GetClassName(self.hwnd) != self.window_class):
            raise NativeCaptureUnavailable('Owned native window identity changed.')
        return True

def wait_owned_window(process, title, *, timeout=45):
    import win32gui
    import win32process
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        process.verify()
        found = []

        def observe(hwnd, unused):
            if win32process.GetWindowThreadProcessId(hwnd)[1] == process.pid and win32gui.GetWindowText(hwnd) == title:
                found.append(hwnd)
        win32gui.EnumWindows(observe, None)
        if found:
            result = OwnedWindow(process, found[0], title, win32gui.GetClassName(found[0]))
            result.verify()
            return result
        time.sleep(0.1)
    raise NativeCaptureUnavailable('The owned native window did not become available.')

def verify_rendered_pixels(image):
    """Refuse an empty GPU surface; never substitute a desktop screenshot."""
    from PIL import ImageStat
    stats = ImageStat.Stat(image.convert('RGB'))
    if max(stats.var) <= 0.01 or max(image.getextrema()[0]) == 0:
        raise NativeCaptureUnavailable('Owned HWND returned an empty rendered surface.')

def capture_owned_window(window, output):
    import ctypes
    from ctypes import wintypes
    import win32gui
    import win32ui
    from PIL import Image
    window.verify()
    if not win32gui.IsWindowVisible(window.hwnd) or win32gui.IsIconic(window.hwnd):
        raise NativeCaptureUnavailable('Owned native window is hidden or minimized.')
    rect = win32gui.GetWindowRect(window.hwnd)
    width, height = (rect[2] - rect[0], rect[3] - rect[1])
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise NativeCaptureUnavailable('Owned native capture dimensions are invalid.')
    dc_handle = win32gui.GetWindowDC(window.hwnd)
    source_dc = memory_dc = bitmap = None
    try:
        source_dc = win32ui.CreateDCFromHandle(dc_handle)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)
        memory_dc.FillSolidRect((0, 0, width, height), 0)
        print_window = ctypes.windll.user32.PrintWindow
        print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        print_window.restype = wintypes.BOOL
        if not print_window(window.hwnd, memory_dc.GetSafeHdc(), 2):
            raise NativeCaptureUnavailable('Owned HWND PrintWindow rendering failed.')
        window.verify()
        image = Image.frombuffer('RGB', (width, height), bitmap.GetBitmapBits(True), 'raw', 'BGRX', 0, 1)
        verify_rendered_pixels(image)
        client = win32gui.GetClientRect(window.hwnd)
        client_origin = win32gui.ClientToScreen(window.hwnd, (0, 0))
        cx, cy = (client_origin[0] - rect[0], client_origin[1] - rect[1])
        client_box = (cx, cy + 32, cx + client[2], cy + client[3])
        if client_box[2] <= client_box[0] or client_box[3] <= client_box[1]:
            raise NativeCaptureUnavailable('Owned client capture region is invalid.')
        verify_rendered_pixels(image.crop(client_box))
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)
        window.verify()
        dpi = ctypes.windll.user32.GetDpiForWindow(window.hwnd)
        return {'path': output.as_posix(), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'method': 'Win32 PrintWindow PW_RENDERFULLCONTENT', 'capture_scope': 'Verified owned HWND client and native chrome only', 'hwnd': window.hwnd, 'pid': window.process.pid, 'create_time': window.process.create_time, 'window_class': window.window_class, 'window_title': window.title, 'window_rect': list(rect), 'image_size': [width, height], 'dpi': dpi, 'client_region_verified': list(client_box), 'desktop_pixel_capture': False}
    finally:
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if memory_dc is not None:
            memory_dc.DeleteDC()
        if source_dc is not None:
            source_dc.DeleteDC()
        if dc_handle:
            win32gui.ReleaseDC(window.hwnd, dc_handle)

def close_owned_window(window, *, timeout=15):
    """Graceful owned-window close; never enumerate or kill unrelated processes."""
    import win32gui
    import win32con
    window.verify()
    win32gui.PostMessage(window.hwnd, win32con.WM_CLOSE, 0, 0)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not win32gui.IsWindow(window.hwnd):
            return True
        window.process.verify()
        time.sleep(0.1)
    return False
