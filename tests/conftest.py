"""Default tests never depend on the owner's running assistant or devices."""
import os
from pathlib import Path
import sys
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
SUPPORT = Path(__file__).resolve().parent / 'support'
sys.path.insert(0, str(SUPPORT))
root = Path(os.environ.setdefault('PYTEST_HANNI_GUARD_ROOT', str(REPO / '.pytest-work/assistant-harness/guards' / uuid4().hex)))
os.environ['PYTEST_HANNI_REPO'] = str(REPO)
os.environ['PYTHONPATH'] = os.pathsep.join(dict.fromkeys([str(SUPPORT), str(REPO / 'src'), str(REPO), *os.environ.get('PYTHONPATH', '').split(os.pathsep)]))
for key in tuple(os.environ):
    if key.startswith(('HANNI_', 'OPENAI_', 'ANTHROPIC_', 'HONCHO_', 'HF_TOKEN')) or key.upper() in {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'}:
        os.environ.pop(key)
os.environ.update(HANNI_DATA_DIR=str(root / 'data'), HANNI_MODEL_STATE=str(root / 'state'),
    HANNI_CRON_ROOT=str(root / 'state'), HANNI_BRIDGE_TOKEN_FILE=str(root / 'state/bridge.token'),
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
from hanni_test_guard import install
install()
from hanni_test_plugin import isolated_test_boundaries  # noqa: F401; pytest fixture
