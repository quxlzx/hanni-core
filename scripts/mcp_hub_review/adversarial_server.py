"""SDK mock wrapper recording only synthetic environment-presence assertions."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.fixtures.mcp_hub_mock import main


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--ledger', type=Path, required=True)
    parsed, _ = parser.parse_known_args()
    parsed.ledger.parent.mkdir(parents=True, exist_ok=True)
    with parsed.ledger.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'event': 'process-start',
            'unrelated_present': 'HANNI_MCP_UNRELATED_TEST_SECRET' in os.environ,
            'explicit_present': os.environ.get('HANNI_MCP_EXPLICIT_CHILD') == 'independent-explicit-synthetic'}) + '\n')
    main()
