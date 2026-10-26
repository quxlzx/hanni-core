"""Build the same Teams package offered by Settings → Integrations."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hanni.teams.package import build_package, local_certificate, main

if __name__ == '__main__':
    main()
