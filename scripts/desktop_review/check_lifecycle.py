"""Real packaged-executable lifecycle and native navigation checks, fixture only."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import win32api
import win32con
import win32gui
import win32process
from PIL import ImageGrab
from playwright.sync_api import sync_playwright, expect

from capture_native import ROOT, frame_capture, find_window, wait_window
from fixture import ReviewFixture


def wait_for(test, description, timeout=15):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if test(): return
        time.sleep(.1)
    raise RuntimeError(description)


def tray_handles(hwnd):
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    found = []
    win32gui.EnumWindows(lambda handle, unused: found.append(handle) if
        win32process.GetWindowThreadProcessId(handle)[1] == pid and
        win32gui.GetClassName(handle).startswith("hanni-os") and
        win32gui.GetClassName(handle).endswith("SystemTrayIcon") else None, None)
    return found


def tray_restore(handles):
    for handle in handles:
        win32gui.PostMessage(handle, 0x400 + 11, 0, win32con.WM_LBUTTONUP)


def select_tray(handles, hwnd, text, screenshot=None):
    # Bring the real app above unrelated windows before its native popup.
    frame_capture(hwnd, screenshot.with_name("tray-owner-native.png") if screenshot else
                  ROOT/"data/hanni-desktop-review/lifecycle/tray-owner-native.png")
    rect = win32gui.GetWindowRect(hwnd)
    win32api.SetCursorPos((rect[2]-30, rect[3]-60))
    for handle in handles:
        win32gui.PostMessage(handle, 0x400 + 11, 0, win32con.WM_RBUTTONUP)
    wait_for(lambda: win32gui.FindWindow("#32768", None), "Native tray menu did not open")
    menu_window = win32gui.FindWindow("#32768", None)
    hmenu = win32gui.SendMessage(menu_window, 0x1E1, 0, 0)  # MN_GETHMENU
    items, indices = [], {}
    for index in range(win32gui.GetMenuItemCount(hmenu)):
        buffer = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetMenuStringW(hmenu, index, buffer, 256, win32con.MF_BYPOSITION)
        if buffer.value:
            items.append(buffer.value); indices[buffer.value] = index
    if screenshot:
        ImageGrab.grab(bbox=rect).save(screenshot)
    item_rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetMenuItemRect.argtypes = [ctypes.wintypes.HWND,
        ctypes.wintypes.HMENU, ctypes.c_uint, ctypes.POINTER(ctypes.wintypes.RECT)]
    if not ctypes.windll.user32.GetMenuItemRect(None, hmenu, indices[text], ctypes.byref(item_rect)):
        raise RuntimeError("Native popup item bounds unavailable")
    win32api.SetCursorPos(((item_rect.left+item_rect.right)//2, (item_rect.top+item_rect.bottom)//2))
    time.sleep(.1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    wait_for(lambda: not win32gui.IsWindow(menu_window), "Native tray menu did not close")
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT/"data/hanni-desktop-review/lifecycle")
    parser.add_argument("--workspace-fixture", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve(); args.output.mkdir(parents=True, exist_ok=True)
    state = args.output/"state"; state.mkdir(exist_ok=True)
    prefs = state/"window.json"
    prefs.write_text(json.dumps({"width": 1000, "height": 720, "x": 70, "y": 70,
        "maximized": False, "close_to_tray": False, "minimize_to_tray": False,
        "notifications": False}), encoding="utf-8")
    title = "HANNI OS Native Lifecycle Review"
    processes = []
    result = {"passed": False, "dpi": ctypes.windll.user32.GetDpiForSystem(),
              "checks": [], "defects": [], "disclosure": "Actual packaged native executable attached to an isolated synthetic fixture. No production session or remote action."}
    factory = ReviewFixture
    if args.workspace_fixture:
        from phase_fixture import PhaseReviewFixture
        factory = PhaseReviewFixture
        result["disclosure"] += " Real isolated workspace; empty offline Google vault; voice inactive/unbound."
    with factory() as fixture:
        def launch(debug_port):
            log = (args.output/f"launch-{len(processes)}.log").open("w", encoding="utf-8")
            process = subprocess.Popen([str(args.exe.resolve()), "--url", fixture.url,
                "--attach-only", "--state-dir", str(state), "--debug-port", str(debug_port),
                "--title", title], stdout=log, stderr=subprocess.STDOUT)
            processes.append((process, log))
            hwnd = wait_window(title)
            return process, hwnd
        def port():
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0)); return sock.getsockname()[1]
        try:
            debug_port = port(); process, hwnd = launch(debug_port)
            with sync_playwright() as p:
                browser = None
                for _ in range(80):
                    try: browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=1000); break
                    except Exception: time.sleep(.1)
                if browser is None: raise RuntimeError("Native CDP connection failed")
                page = None
                for _ in range(300):
                    pages = [page for c in browser.contexts for page in c.pages if page.url.startswith(fixture.url) and '?view=mini' not in page.url]
                    if pages: page = pages[0]; break
                    initial_pages = [p for c in browser.contexts for p in c.pages]
                    if initial_pages:
                        initial_pages[0].wait_for_timeout(100)
                    else:
                        browser.new_browser_cdp_session().send("Target.getTargets")
                if page is None:
                    frame_capture(hwnd, args.output/"startup-failure-native.png")
                    result["startup_body"] = [p.locator("body").inner_text() for c in browser.contexts for p in c.pages]
                    raise RuntimeError(f"Fixture page not loaded; CDP pages: {[p.url for c in browser.contexts for p in c.pages]}")
                expect(page.locator("#chat-input")).to_be_enabled()
                result["checks"].append("Actual executable and loopback fixture connection")
                win32gui.SetWindowPos(hwnd, 0, 20, 20, 640, 480, win32con.SWP_NOZORDER)
                page.wait_for_timeout(300)
                minimum_layout = page.evaluate("""() => ({width:innerWidth,height:innerHeight,
                    elements:Object.fromEntries(['.topbar','.voice-dock','#main-content','.dock-stop'].map(selector=>{
                        const element=document.querySelector(selector),r=element.getBoundingClientRect();
                        return [selector,{x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right,
                            visible:r.top>=0&&r.left>=0&&r.bottom<=innerHeight+1&&r.right<=innerWidth+1}];
                    }))})""")
                result["minimum_window"] = frame_capture(hwnd,args.output/"minimum-main-native.png")
                result["minimum_window"]["layout"] = minimum_layout
                if all(item["visible"] for item in minimum_layout["elements"].values()):
                    result["checks"].append("Actual minimum native window preserves header/main viewport/footer controls at observed125%DPI")
                else:
                    result["defects"].append("Actual minimum native window clips primary viewport or footer controls at125%DPI")
                win32gui.SetWindowPos(hwnd, 0, 70, 70, 1200, 800, win32con.SWP_NOZORDER)
                page.wait_for_timeout(200)
                missing_token = page.evaluate("""async () => {
                    const response = await fetch('/api/cluster/terminal', {method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({id:crypto.randomUUID(),node:'hanni'})});
                    return response.status;
                }""")
                assert missing_token == 403 and not fixture.writes
                result["checks"].append("Real WebView API write without request token rejected403; no machine-action handler invoked")
                api_keys = page.evaluate("Object.keys(window.pywebview?.api || {})")
                assert not api_keys, api_keys
                result["checks"].append("No privileged Javascript native API methods exposed")
                hits = []
                class UntrustedHandler(BaseHTTPRequestHandler):
                    def log_message(self, *args): pass
                    def do_GET(self):
                        hits.append(self.path); self.send_response(200); self.end_headers(); self.wfile.write(b"untrusted")
                untrusted = ThreadingHTTPServer(("127.0.0.1", 0), UntrustedHandler)
                threading.Thread(target=untrusted.serve_forever, daemon=True).start()
                try:
                    target = f"http://127.0.0.1:{untrusted.server_port}"
                    before = page.url; count = sum(len(c.pages) for c in browser.contexts)
                    page.evaluate("url => window.open(url+'/'+'popup-test','_blank')", target)
                    page.wait_for_timeout(500)
                    popup_hits = list(hits)
                    page.evaluate("url => {location.href=url+'/navigation-test'}", target)
                    page.wait_for_timeout(500)
                    result["navigation_guard"] = {"before": before, "after": page.url,
                        "untrusted_requests": list(hits), "popup_requests": popup_hits, "pages_before": count,
                        "pages_after": [p.url for c in browser.contexts for p in c.pages]}
                    guard_ok = page.url == before and not hits and sum(len(c.pages) for c in browser.contexts) == count
                    if guard_ok:
                        result["checks"].append("Native foreign-loopback navigation and popup blocked before any request")
                    else:
                        result["defects"].append("Native navigation/popup allowed untrusted request or window")
                        if page.url != before: page.goto(before)
                finally:
                    untrusted.shutdown(); untrusted.server_close()
                frame_capture(hwnd, args.output/"before-maximize-native.png")
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                wait_for(lambda: bool(ctypes.windll.user32.IsZoomed(hwnd)), "Window did not maximize")
                time.sleep(.3)
                ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd)).save(args.output/"maximized-native.png")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                wait_for(lambda: win32gui.IsIconic(hwnd), "Window did not minimize")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                wait_for(lambda: not win32gui.IsIconic(hwnd), "Window did not restore")
                result["checks"].append("Native maximize/minimize/restore states")
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 100, 100, 1280, 800, 0)
                page.wait_for_timeout(400)
                expected = list(win32gui.GetWindowRect(hwnd))
                frame_capture(hwnd, args.output/"resized-native.png")
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                process.wait(timeout=20)
                assert fixture.hub.ready and not fixture.shutdown.is_set()
                assert json.load(urllib.request.urlopen(fixture.url+"api/workspace"))["version"] == 1
                result["saved_preferences"] = json.loads(prefs.read_text(encoding="utf-8"))
                result["checks"].append("Default native close exits cleanly and attached backend remains alive with no shutdown request")
                # CDP transport has closed with the native window; do not use browser.close.
            process, hwnd = launch(port())
            time.sleep(1)
            actual = list(win32gui.GetWindowRect(hwnd))
            result["geometry_expected"] = expected; result["geometry_restored"] = actual
            assert max(abs(a-b) for a,b in zip(actual,expected)) <= 3, (expected, actual)
            result["checks"].append("Native resized dimensions and position restored on packaged-executable restart at125%scaling")
            handles = tray_handles(hwnd)
            assert handles, "No native tray windows found"
            result["tray_menu_items"] = select_tray(handles, hwnd, "Close to tray", args.output/"tray-menu-native.png")
            wait_for(lambda: json.loads(prefs.read_text(encoding="utf-8"))["close_to_tray"], "Close-to-tray preference did not persist")
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            wait_for(lambda: not win32gui.IsWindowVisible(hwnd), "Close-to-tray did not hide native window")
            assert process.poll() is None and fixture.hub.ready
            tray_restore(handles)
            wait_for(lambda: win32gui.IsWindowVisible(hwnd), "Native tray default action did not restore window")
            select_tray(handles, hwnd, "Minimize to tray")
            wait_for(lambda: json.loads(prefs.read_text(encoding="utf-8"))["minimize_to_tray"], "Minimize-to-tray preference did not persist")
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            wait_for(lambda: not win32gui.IsWindowVisible(hwnd), "Minimize-to-tray did not hide native window")
            tray_restore(handles)
            wait_for(lambda: win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd), "Tray did not restore minimized window")
            result["checks"].append("Actual native tray menu toggles close/minimize preferences, hides window, restores through default tray action")
            select_tray(handles, hwnd, "Exit desktop")
            process.wait(timeout=20)
            assert fixture.hub.ready and not fixture.shutdown.is_set() and not fixture.writes
            result["checks"].append("Native tray Exit desktop exits even with close-to-tray enabled; attached backend and no-write invariants preserved")
            result["passed"] = not result["defects"]
        except Exception as error:
            result["error"] = repr(error)
            raise
        finally:
            for process, log in processes:
                if process.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                log.close()
            (args.output/"results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise RuntimeError("Native lifecycle/security defects remain; see results.json")


if __name__ == "__main__": main()
