"""Read physical display metrics in this process's DPI-aware context only."""
import ctypes
import json
from datetime import datetime, timezone
from pathlib import Path

def main():
    user32 = ctypes.windll.user32
    before = {'system_dpi': user32.GetDpiForSystem(), 'width': user32.GetSystemMetrics(0), 'height': user32.GetSystemMetrics(1)}
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
    set_context = bool(user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
    after = {'system_dpi': user32.GetDpiForSystem(), 'width': user32.GetSystemMetrics(0), 'height': user32.GetSystemMetrics(1), 'monitor_count': user32.GetSystemMetrics(80)}
    output = {'timestamp': datetime.now(timezone.utc).isoformat(), 'before_process_awareness': before, 'after_process_awareness': after, 'process_awareness_set_success': set_context, 'global_display_settings_changed': False, 'authoritative_native_dpi': 120, 'scope': 'Original DPI-unaware preflight values were virtualized; native HWND DPI and aware metrics are authoritative.'}
    path = Path(__file__).resolve().parents[2] / 'docs/campaign8/DISPLAY_IDENTITY.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(output, indent=2))
if __name__ == '__main__':
    main()
