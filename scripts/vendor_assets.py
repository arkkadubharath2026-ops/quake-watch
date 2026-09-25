"""Download pinned frontend assets into static/vendor and verify their SHA-256 hashes.

No CDN is used at runtime (strict CSP: script-src 'self' + nonce). To upgrade a library, change
its version, run with ``--update-hashes``, review the diff of VENDOR_LOCK.json, and commit.

    .venv/Scripts/python scripts/vendor_assets.py            # download + verify
    .venv/Scripts/python scripts/vendor_assets.py --update-hashes
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "static" / "vendor"
LOCK = ROOT / "static" / "vendor" / "VENDOR_LOCK.json"
CDN = "https://cdn.jsdelivr.net/npm"

ASSETS: dict[str, tuple[str, list[str]]] = {
    # name: (package@version, [files within the package])
    "bootstrap": (
        "bootstrap@5.3.8",
        ["dist/css/bootstrap.min.css", "dist/js/bootstrap.bundle.min.js"],
    ),
    "bootstrap-icons": (
        "bootstrap-icons@1.13.1",
        ["font/bootstrap-icons.min.css", "font/fonts/bootstrap-icons.woff2"],
    ),
    "leaflet": ("leaflet@1.9.4", ["dist/leaflet.css", "dist/leaflet.js"]),
    "leaflet.markercluster": (
        "leaflet.markercluster@1.5.3",
        [
            "dist/MarkerCluster.css",
            "dist/MarkerCluster.Default.css",
            "dist/leaflet.markercluster.js",
        ],
    ),
    "chart.js": ("chart.js@4.5.1", ["dist/chart.umd.min.js"]),
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "QuakeWatch vendor script"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https CDN
        return bytes(response.read())


def main(update_hashes: bool) -> int:
    lock: dict[str, str] = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    new_lock: dict[str, str] = {}
    failures = []
    for name, (package, files) in ASSETS.items():
        for file in files:
            relative = f"{name}/{file.split('/', 1)[1] if file.startswith('dist/') else file}"
            target = VENDOR / relative
            content = fetch(f"{CDN}/{package}/{file}")
            digest = hashlib.sha256(content).hexdigest()
            key = f"{package}/{file}"
            expected = lock.get(key)
            if expected and expected != digest and not update_hashes:
                failures.append(f"{key}: expected {expected}, got {digest}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            new_lock[key] = digest
            print(f"ok {key} -> static/vendor/{relative}")
    if failures:
        print("HASH MISMATCH (possible tampering or version drift):", *failures, sep="\n  ")
        return 1
    LOCK.write_text(json.dumps(dict(sorted(new_lock.items())), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(update_hashes="--update-hashes" in sys.argv))
