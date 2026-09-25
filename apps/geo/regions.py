"""Derive an application region from a USGS ``place`` string (pure, deterministic).

USGS place strings take two shapes:

* ``"6 km SE of Pinnacles, CA"`` — relative to a nearby place; the text after the last comma is
  a US state/territory abbreviation, a country, or a subdivision name.
* ``"Fiji region"``, ``"south of the Fiji Islands"`` — a Flinn-Engdahl style region name.

The derived region is stored under ``derived`` (never overwriting the source ``place``) and is
labelled with the method so the UI can explain it. ``REGION_METHOD_VERSION`` changes whenever the
mapping rules change, so derived values can be recomputed reproducibly.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

REGION_METHOD_VERSION = 1

US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
    "GU": "Guam", "VI": "U.S. Virgin Islands",
}  # fmt: skip

US_STATE_NAMES = frozenset(US_STATES.values())

# Abbreviations USGS uses for non-US areas in place strings.
OTHER_ABBREVIATIONS: dict[str, str] = {"MX": "Mexico", "B.C.": "Baja California"}

_RELATIVE_RE = re.compile(r"^\s*\d+(\.\d+)?\s*km\s+[NSEW]{1,3}\s+of\s+", re.IGNORECASE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class DerivedRegion:
    key: str
    name: str
    kind: str  # "us_state" | "country_or_area" | "named_region"
    method_version: int = REGION_METHOD_VERSION


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return _SLUG_RE.sub("-", ascii_value.lower()).strip("-")


def region_from_place(place: str | None) -> DerivedRegion | None:
    if place is None:
        return None
    text = " ".join(place.split())
    if not text:
        return None

    if "," in text:
        suffix = text.rsplit(",", 1)[1].strip()
        if not suffix:
            return None
        if suffix.upper() in US_STATES:
            name = US_STATES[suffix.upper()]
            return DerivedRegion(key=slugify(name), name=name, kind="us_state")
        if suffix in OTHER_ABBREVIATIONS:
            name = OTHER_ABBREVIATIONS[suffix]
            return DerivedRegion(key=slugify(name), name=name, kind="country_or_area")
        if suffix in US_STATE_NAMES:
            return DerivedRegion(key=slugify(suffix), name=suffix, kind="us_state")
        return DerivedRegion(key=slugify(suffix), name=suffix, kind="country_or_area")

    name = _RELATIVE_RE.sub("", text)
    key = slugify(name)
    if not key:
        return None
    return DerivedRegion(key=key, name=name, kind="named_region")
