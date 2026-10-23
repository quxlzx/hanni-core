"""Capture harness authority controls, not native desktop functional passes."""
from types import SimpleNamespace
import pytest
from PIL import Image
from scripts.campaign8_native.owned_window import NativeCaptureUnavailable, OwnedProcess, OwnedWindow, verify_rendered_pixels

def setup_identity():
    process = OwnedProcess(314, 17.0, 'C:/owned/HANNI OS.exe')
    current = SimpleNamespace(create_time=lambda: 17.0, exe=lambda: 'C:/owned/HANNI OS.exe')
    gui = SimpleNamespace(IsWindow=lambda hwnd: True, GetWindowText=lambda hwnd: 'Campaign-owned native window', GetClassName=lambda hwnd: 'WindowsForms10.Window.8')
    api = SimpleNamespace(GetWindowThreadProcessId=lambda hwnd: (8, 314))
    window = OwnedWindow(process, 99, 'Campaign-owned native window', 'WindowsForms10.Window.8')
    return (window, current, gui, api)

def test_owned_capture_identity_positive_without_windows_access():
    window, current, gui, api = setup_identity()
    assert window.verify(gui=gui, process_api=api, process_factory=lambda pid: current)

@pytest.mark.parametrize('mutation', ['process_time', 'process_executable', 'window_missing', 'window_pid', 'window_title', 'window_class'])
def test_owned_capture_identity_fails_closed(mutation):
    window, current, gui, api = setup_identity()
    if mutation == 'process_time':
        current.create_time = lambda: 18.0
    elif mutation == 'process_executable':
        current.exe = lambda: 'C:/personal/other.exe'
    elif mutation == 'window_missing':
        gui.IsWindow = lambda hwnd: False
    elif mutation == 'window_pid':
        api.GetWindowThreadProcessId = lambda hwnd: (8, 777)
    elif mutation == 'window_title':
        gui.GetWindowText = lambda hwnd: 'Another application'
    elif mutation == 'window_class':
        gui.GetClassName = lambda hwnd: 'OtherWindow'
    with pytest.raises(NativeCaptureUnavailable):
        window.verify(gui=gui, process_api=api, process_factory=lambda pid: current)

@pytest.mark.parametrize('color', ['black', 'white', '#18191c'])
def test_empty_hwnd_render_does_not_count_as_native_screenshot(color):
    with pytest.raises(NativeCaptureUnavailable):
        verify_rendered_pixels(Image.new('RGB', (20, 20), color))

def test_actual_rendered_pixel_variation_passes_integrity_gate():
    image = Image.new('RGB', (20, 20), '#18191c')
    image.putpixel((4, 3), (210, 210, 210))
    verify_rendered_pixels(image)
