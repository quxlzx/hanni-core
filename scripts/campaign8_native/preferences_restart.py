"""Original native persistence across two sequential owned app processes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from scripts.campaign8_native.session import NativeSession

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    from scripts.campaign8_native.menus import tray_menu
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if psutil.Process(ready['pid']).create_time() != ready['create_time']:
        raise RuntimeError('Owned original backend identity changed.')
    output = args.output.resolve()
    with NativeSession(url=ready['url'], output=output / 'first', maximum_seconds=120) as first:
        first.execute({'id': 'persist-physical-size', 'action': 'resize', 'size': [1100, 700]})
        first.execute({'id': 'persist-close-to-tray', 'action': 'tray_menu', 'name': 'Close to tray'})
        first.execute({'id': 'persist-minimize-to-tray', 'action': 'tray_menu', 'name': 'Minimize to tray'})
        first.execute({'id': 'persist-mini-show', 'action': 'tray_menu', 'name': 'Open HANNI Mini'})
        first.execute({'id': 'persist-mini-pin', 'action': 'click', 'view': 'mini', 'role': 'button', 'name': 'Pin'})
        time.sleep(0.5)
        state = first.output / 'native-state'
        before = json.loads((state / 'window.json').read_text(encoding='utf8'))
        first.report['persistence_before_exit'] = {'saved_original_preferences': before, 'actual_main': first.window_state(first.main), 'actual_mini': first.window_state(first.mini), 'screenshot': first.capture('saved-original-geometry')}
        first.report['original_tray_exit'] = tray_menu(first.identity, 'Exit desktop')
        first.process.wait(timeout=15)
        first.report['complete'] = True
    saved = json.loads((state / 'window.json').read_text(encoding='utf8'))
    with NativeSession(url=ready['url'], output=output / 'second', maximum_seconds=120, state_directory=state) as second:
        second.report['original_persistence_readback'] = {'saved_first_exit': saved, 'original_second_loaded_state': json.loads((state / 'window.json').read_text(encoding='utf8')), 'actual_main': second.window_state(second.main), 'actual_mini': second.window_state(second.mini), 'distinct_owned_pid_or_creation': (first.identity.pid, first.identity.create_time) != (second.identity.pid, second.identity.create_time), 'logical_saved_dimensions': [saved['width'], saved['height']], 'physical_actual_dimensions': [second.window_state(second.main)['window_rect'][2] - second.window_state(second.main)['window_rect'][0], second.window_state(second.main)['window_rect'][3] - second.window_state(second.main)['window_rect'][1]], 'actual_dpi': second.window_state(second.main)['dpi'], 'screenshot': second.capture('restored-original-geometry')}
        second.report['restored_actual_tray_preferences'] = tray_menu(second.identity)
        second.report['original_second_tray_exit'] = tray_menu(second.identity, 'Exit desktop')
        second.process.wait(timeout=15)
        second.report['complete'] = True
    result = {'scope': 'Actual packaged native app, original state persistence, same disposable state directory; no owner preferences', 'first_receipt': str(first.output / 'RESULTS.json'), 'second_receipt': str(second.output / 'RESULTS.json'), 'first_cleanup': first.report['owned_native_cleanup'], 'second_cleanup': second.report['owned_native_cleanup'], 'first_exit_code': first.process.returncode, 'second_exit_code': second.process.returncode, 'backend_preserved': psutil.Process(ready['pid']).create_time() == ready['create_time']}
    (output / 'RESULTS.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
if __name__ == '__main__':
    main()
