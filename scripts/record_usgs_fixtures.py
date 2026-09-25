"""Re-record the real USGS payloads used by the contract tests (tests/fixtures/usgs).

Run when USGS changes its schema or to refresh fixtures:

    .venv/Scripts/python scripts/record_usgs_fixtures.py

Uses only the standard library so it works without the application configured.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://earthquake.usgs.gov"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "usgs"
WINDOW = "starttime=2026-09-01&endtime=2026-09-02&minmagnitude=4.5"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "QuakeWatch fixture recorder"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
        return bytes(response.read())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = {
        "all_day.geojson": f"{BASE}/earthquakes/feed/v1.0/summary/all_day.geojson",
        # Same parameters the adapter sends (orderby + limit change the metadata shape).
        "catalog_window.geojson": f"{BASE}/fdsnws/event/1/query?format=geojson&{WINDOW}"
        "&orderby=time-asc&limit=20000",
        "catalog_count.json": f"{BASE}/fdsnws/event/1/count?format=geojson&{WINDOW}",
    }
    for name, url in targets.items():
        (OUT / name).write_bytes(fetch(url))
        print(f"recorded {name}")

    catalog = json.loads((OUT / "catalog_window.geojson").read_bytes())
    richest = max(catalog["features"], key=lambda f: len(f["properties"].get("types") or ""))
    detail_url = f"{BASE}/earthquakes/feed/v1.0/detail/{richest['id']}.geojson"
    (OUT / "detail_event.geojson").write_bytes(fetch(detail_url))
    print(f"recorded detail_event.geojson ({richest['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
