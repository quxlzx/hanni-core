"""Pin historical benchmark owner timezones independently of live configuration."""
from __future__ import annotations

import json
from pathlib import Path
from zoneinfo import ZoneInfo


MANIFEST = Path(__file__).resolve().parents[3] / "evals" / "fixture_timezones.json"


def fixture_timezone(cases_path: Path, *, manifest: Path = MANIFEST) -> str | None:
    """Return the IANA zone for a versioned corpus, if one is pinned."""
    path = Path(cases_path).resolve()
    try:
        relative = path.relative_to(manifest.resolve().parents[1]).as_posix()
    except ValueError:
        return None
    mapping = json.loads(manifest.read_text(encoding="utf-8"))
    zone = mapping.get(relative)
    if zone:
        ZoneInfo(zone)
    return zone
