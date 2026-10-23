"""Original dashboard preview with isolated stores and protected roster copy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from hanni.config.loader import load_config
from scripts.v36_engineering.controlled_launcher import IsolatedGoogleAccess


def main():
    output = ROOT / 'data/v37-manager/preview'
    state = output / 'state'
    state.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        account = os.environ['USERDOMAIN'] + '\\' + os.environ['USERNAME']
        subprocess.run(['icacls', str(state), '/inheritance:r', '/grant:r', account + ':(OI)(CI)F'], check=True, stdout=subprocess.DEVNULL)
    else:
        state.chmod(0o700)
    (state / 'compute').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'data/compute/deployment.json', state / 'compute/deployment.json')
    shutil.copyfile(ROOT / 'data/compute/context-measurements.json', state / 'compute/context-measurements.json')
    with patch('hanni.tools.google_access.GoogleAccess', IsolatedGoogleAccess):
        from hanni.dashboard.server import DashboardServer, Telemetry
        config = load_config(ROOT / 'config', data_dir=state, env={})
        telemetry = Telemetry(config)
        server = DashboardServer(0, telemetry)
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        telemetry.start()
        url = f'http://127.0.0.1:{server.server_port}'
        (output / 'ready.json').write_text(json.dumps({'url': url, 'pid': os.getpid()}), encoding='utf-8')
        print(url, flush=True)
        try:
            deadline = time.monotonic() + 1800
            while time.monotonic() < deadline and not (output / 'stop').exists():
                time.sleep(1)
        finally:
            telemetry.close()
            server.shutdown()
            serving.join(3)
            server.server_close()
            server.chat.close()
            server.chat.db.close()


if __name__ == '__main__':
    main()
