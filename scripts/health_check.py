#!/usr/bin/env python3
"""Run the H.A.N.N.I. health check (the same report as ``hanni health``).

Usage:
    python scripts/health_check.py [--json] [--config-dir DIR] [--data-dir DIR] [--env-file FILE]

Exit status is 0 only if this laptop is healthy.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hanni.core.health import run_health_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_health_check(config_dir=args.config_dir, data_dir=args.data_dir, dotenv_path=args.env_file)
    print(report.to_json() if args.json else report.render_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
