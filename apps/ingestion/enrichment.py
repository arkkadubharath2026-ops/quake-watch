"""Extract scientific-product summaries from a USGS detail feature (pure).

Only availability metadata and a small allow-listed set of summary properties are kept per
product (the full product contents are large and served by USGS). Values are kept exactly as USGS
publishes them (strings) — QuakeWatch does not reinterpret or invent impact estimates (PRD §11).
"""

from __future__ import annotations

from typing import Any

from apps.core.clock import from_epoch_ms, to_iso
from apps.ingestion.adapters.usgs_models import UsgsDetailFeature, UsgsProduct

PRODUCT_SUMMARY_FIELDS: dict[str, tuple[str, ...]] = {
    "origin": (
        "review-status",
        "evaluation-status",
        "horizontal-error",
        "vertical-error",
        "magnitude-error",
        "magnitude-num-stations-used",
        "standard-error",
        "depth-type",
    ),
    "shakemap": ("maxmmi", "maxpga", "maxpgv", "map-status", "review-status"),
    "losspager": ("alertlevel", "maxmmi", "review-status"),
    "dyfi": ("maxmmi", "num-responses"),
    "moment-tensor": ("derived-magnitude", "derived-magnitude-type", "percent-double-couple"),
    "finite-fault": (),
    "ground-failure": ("landslide-alert", "liquefaction-alert"),
    "oaf": (),
}


def _preferred(products: list[UsgsProduct]) -> UsgsProduct:
    return max(products, key=lambda p: (p.preferredWeight or 0, p.updateTime))


def summarize_products(feature: UsgsDetailFeature) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for product_type, products in feature.properties.products.items():
        if product_type not in PRODUCT_SUMMARY_FIELDS or not products:
            continue
        chosen = _preferred(products)
        fields = PRODUCT_SUMMARY_FIELDS[product_type]
        summary[product_type] = {
            "status": chosen.status,
            "source": chosen.source,
            "code": chosen.code,
            "update_time": to_iso(from_epoch_ms(chosen.updateTime)),
            "preferred_weight": chosen.preferredWeight,
            "versions_available": len(products),
            "properties": {f: chosen.properties[f] for f in fields if f in chosen.properties},
        }
    return summary
