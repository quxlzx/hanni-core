"""Capture a real HANNI executable using isolated synthetic review fixtures.

Full framed PNGs come from Windows ImageGrab, never from a browser mockup.
CDP is used only to navigate/interact and collect layout/error evidence.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

# Win32 coordinates and ImageGrab pixels must share physical DPI coordinates.
# An unaware Python process receives virtualized 96-DPI rectangles at 125%.
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

import win32con
import win32gui
import win32api
import win32process
from PIL import ImageGrab
from playwright.sync_api import sync_playwright, expect

from fixture import ReviewFixture

ROOT = Path(__file__).resolve().parents[2]
SIZES = [(1920, 1080), (1440, 900), (1366, 768), (900, 650)]


def find_window(title):
    found = []
    win32gui.EnumWindows(lambda hwnd, unused: found.append(hwnd)
        if win32gui.GetWindowText(hwnd) == title else None, None)
    return found[0] if found else None


def wait_window(title, timeout=60):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        hwnd = find_window(title)
        if hwnd: return hwnd
        time.sleep(.2)
    raise RuntimeError(f"Native window {title!r} was not created")


def frame_capture(hwnd, path):
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    foreground = win32gui.GetForegroundWindow()
    own_thread = win32api.GetCurrentThreadId()
    foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else own_thread
    attached = foreground_thread != own_thread
    try:
        if attached:
            ctypes.windll.user32.AttachThreadInput(own_thread, foreground_thread, True)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        win32gui.BringWindowToTop(hwnd)
    finally:
        if attached:
            ctypes.windll.user32.AttachThreadInput(own_thread, foreground_thread, False)
    time.sleep(.2)
    if win32gui.GetForegroundWindow() != hwnd:
        raise RuntimeError("Native capture window is not foreground; refusing to capture an occluded application")
    rect = win32gui.GetWindowRect(hwnd)
    ImageGrab.grab(bbox=rect).save(path)
    return {"path": str(path.relative_to(ROOT)), "window_rect": list(rect),
            "window_size": [rect[2]-rect[0], rect[3]-rect[1]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT/"data/hanni-desktop-review/iteration-1")
    parser.add_argument("--skip-interactions", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    title = "HANNI OS Independent Review"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); debug_port = sock.getsockname()[1]
    result = {"disclosure": "Real native executable/window; synthetic isolated telemetry/settings/chat/power/terminal fixture. No model, microphone, real SSH or power requests.",
              "executable": str(args.exe.resolve()), "dpi": ctypes.windll.user32.GetDpiForSystem(),
              "screenshots": [], "checks": [], "javascript_errors": [], "external_requests": [], "csp_errors": []}
    with ReviewFixture() as fixture:
        command = [str(args.exe.resolve()), "--url", fixture.url, "--attach-only",
                   "--state-dir", str(args.output.resolve()/"native-state"),
                   "--debug-port", str(debug_port), "--title", title]
        output = (args.output/"native-launch.log").open("w", encoding="utf-8")
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        try:
            hwnd = wait_window(title)
            result["native_class"] = win32gui.GetClassName(hwnd)
            result["native_pid"] = process.pid
            with sync_playwright() as playwright:
                browser = None
                for _ in range(100):
                    try:
                        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=1000)
                        break
                    except Exception:
                        time.sleep(.2)
                if browser is None: raise RuntimeError("Native WebView2 CDP did not become available")
                page = None
                for _ in range(100):
                    pages = [p for context in browser.contexts for p in context.pages
                             if p.url.startswith(fixture.url)]
                    if pages:
                        page = pages[0]
                        break
                    initial_pages = [p for c in browser.contexts for p in c.pages]
                    if initial_pages:
                        initial_pages[0].wait_for_timeout(100)
                    else:
                        browser.new_browser_cdp_session().send("Target.getTargets")
                if page is None:
                    raise RuntimeError(f"Fixture WebView2 page missing: {[p.url for c in browser.contexts for p in c.pages]}")
                page.on("pageerror", lambda error: result["javascript_errors"].append(str(error)))
                page.on("request", lambda req: result["external_requests"].append(req.url)
                    if req.url.startswith(("http://", "https://")) and not req.url.startswith(fixture.url) else None)
                page.on("console", lambda msg: result["csp_errors"].append(msg.text)
                    if msg.type == "error" and "content security policy" in msg.text.lower() else None)
                expect(page.locator("#chat-input")).to_be_enabled(timeout=30000)
                result["checks"].append("Native executable startup and token-protected backend connection")
                for width, height in SIZES:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 32, width, height, 0)
                    page.wait_for_timeout(300)
                    for screen in ["home", "chat", "mission", "cluster", "settings"]:
                        page.evaluate("s => location.hash=s", screen)
                        expect(page.locator(f".screen-{screen}")).to_be_visible()
                        page.wait_for_timeout(350)
                        overflow = page.evaluate("({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,mainWidth:document.querySelector('.main-content')?.clientWidth,mainScrollWidth:document.querySelector('.main-content')?.scrollWidth})")
                        assert overflow["scrollWidth"] <= overflow["width"] + 1, (screen, width, overflow)
                        image = frame_capture(hwnd, args.output/f"{screen}-{width}x{height}-native.png")
                        assert image["window_size"] == [width, height], ("Unexpected native size", image)
                        image.update(screen=screen, viewport=overflow)
                        result["screenshots"].append(image)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 32, 1366, 768, 0)
                if not args.skip_interactions:
                    page.evaluate("location.hash='cluster'")
                    expect(page.locator("[data-node='hanni']")).to_be_visible()
                    page.locator("[data-node='hanni']").click()
                    page.wait_for_timeout(200)
                    result["screenshots"].append(frame_capture(hwnd, args.output/"cluster-selected-native.png"))
                    page.get_by_role("button", name="Reboot HANNI", exact=True).click()
                    expect(page.get_by_role("dialog", name="Reboot HANNI?")).to_be_visible()
                    result["screenshots"].append(frame_capture(hwnd, args.output/"cluster-confirmation-native.png"))
                    page.get_by_role("dialog").get_by_role("button", name="Cancel", exact=True).click()
                    assert not fixture.writes
                    result["checks"].append("Native cluster detail navigation and power dialog cancellation without writes")
                    page.keyboard.press("Control+k")
                    expect(page.get_by_role("dialog")).to_be_visible()
                    result["screenshots"].append(frame_capture(hwnd, args.output/"command-palette-native.png"))
                    page.keyboard.press("Escape")
                    expect(page.get_by_role("dialog")).to_have_count(0)
                    result["checks"].append("Keyboard command palette and Escape")
                    page.evaluate("location.hash='chat'")
                    page.locator("#chat-input").fill("Check the review fixture status.")
                    page.locator("#chat-input").press("Enter")
                    expect(page.locator(".chat-message.user p")).to_contain_text("review fixture")
                    prompt = fixture.hub.take()
                    assert prompt == "Check the review fixture status."
                    row = fixture.hub.begin(prompt, "browser")
                    fixture.hub.update(row, "Review fixture is connected. These readings are synthetic; no remote action was performed.", "complete")
                    expect(page.locator(".chat-message.assistant p")).to_contain_text("synthetic")
                    result["screenshots"].append(frame_capture(hwnd, args.output/"conversation-active-native.png"))
                    result["checks"].append("Native chat submission through existing ChatHub and synthetic response")
                    page.evaluate("location.hash='home'")
                    page.wait_for_timeout(300)
                    result["screenshots"].append(frame_capture(hwnd, args.output/"home-recent-conversation-native.png"))
                    page.evaluate("location.hash='settings'")
                    expect(page.locator("#microphone-device")).to_be_visible()
                    page.locator("#microphone-device").select_option("1")
                    page.locator("#audio-apply").click()
                    expect(page.get_by_text("Audio choices saved. Restart the voice session to apply them.")).to_be_visible()
                    page.locator("#gpu-route").select_option("review-gpu")
                    page.locator("#gpu-apply").click()
                    expect(page.get_by_text("Routing saved. Restart the model to move an already loaded model.")).to_be_visible()
                    result["screenshots"].append(frame_capture(hwnd, args.output/"settings-saved-native.png"))
                    assert len(fixture.writes) == 2 and all(write["kind"] in {"/api/audio-devices", "/api/gpu-routing"} for write in fixture.writes)
                    result["checks"].append("Native audio/model settings interactions with exactly two synthetic token-protected writes")
                    page.evaluate("location.hash='chat'")
                    page.locator("#chat-input").fill("Preserve this review draft")
                    page.route("**/api/chat", lambda route: route.abort())
                    page.route("**/api/state", lambda route: route.abort())
                    expect(page.locator("#chat-input")).to_be_disabled(timeout=10000)
                    expect(page.locator("#chat-input")).to_have_value("Preserve this review draft")
                    result["screenshots"].append(frame_capture(hwnd, args.output/"disconnected-native.png"))
                    page.unroute("**/api/chat"); page.unroute("**/api/state")
                    expect(page.locator("#chat-input")).to_be_enabled(timeout=10000)
                    result["checks"].append("Native disconnected state, reconnect and draft preservation")
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                assert win32gui.IsIconic(hwnd)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                page.wait_for_timeout(200)
                assert win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd)
                result["checks"].append("Native window minimize and restore")
                assert not result["javascript_errors"], result["javascript_errors"]
                assert not result["external_requests"], result["external_requests"]
                assert not result["csp_errors"], result["csp_errors"]
                result["fixture_writes"] = fixture.writes
                result["passed"] = True
                browser.close()
        except Exception as error:
            result["passed"] = False
            result["error"] = repr(error)
            raise
        finally:
            (args.output/"capture-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            if process.poll() is None:
                # Review instance only; never stop an attached real HANNI backend.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            output.close()
    print(json.dumps({"passed": result["passed"], "screenshots": len(result["screenshots"]), "checks": result["checks"]}, indent=2))


if __name__ == "__main__":
    main()
