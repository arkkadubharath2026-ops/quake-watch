"""Reference names for common ANSS / USGS contributing network codes (pure).

Only display metadata: an unknown code is stored with ``name = None`` rather than a guess.
"""

from __future__ import annotations

NETWORK_NAMES: dict[str, str] = {
    "us": "USGS National Earthquake Information Center",
    "ak": "Alaska Earthquake Center",
    "av": "Alaska Volcano Observatory",
    "ci": "Southern California Seismic Network",
    "nc": "Northern California Seismic System",
    "hv": "Hawaiian Volcano Observatory",
    "nn": "Nevada Seismological Laboratory",
    "uw": "Pacific Northwest Seismic Network",
    "uu": "University of Utah Seismograph Stations",
    "mb": "Montana Bureau of Mines and Geology",
    "nm": "New Madrid Seismic Network",
    "se": "Southeastern U.S. Seismic Network",
    "ok": "Oklahoma Geological Survey",
    "tx": "Texas Seismological Network",
    "pr": "Puerto Rico Seismic Network",
    "ld": "Lamont-Doherty Cooperative Seismographic Network",
    "at": "National Tsunami Warning Center",
    "pt": "Pacific Tsunami Warning Center",
}


def network_name(code: str) -> str | None:
    return NETWORK_NAMES.get(code.lower())
