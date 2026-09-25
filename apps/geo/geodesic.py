"""Geodesic helpers (pure).

Distances use the haversine formula on a spherical Earth (mean radius 6371.0088 km). Error versus
the WGS-84 ellipsoid is < 0.5 %, which is adequate for watch-radius rules and display; the value is
labelled "derived" wherever it is shown. ArangoDB's GEO_DISTANCE uses the same spherical model, so
application and database distances agree.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088
MAX_RADIUS_KM = 20_000.0


class InvalidGeometry(ValueError):
    pass


def validate_lat_lon(latitude: float, longitude: float) -> None:
    if not (math.isfinite(latitude) and -90.0 <= latitude <= 90.0):
        raise InvalidGeometry(f"latitude {latitude!r} outside [-90, 90]")
    if not (math.isfinite(longitude) and -180.0 <= longitude <= 180.0):
        raise InvalidGeometry(f"longitude {longitude!r} outside [-180, 180]")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Viewport box. ``west > east`` means the box crosses the antimeridian."""

    south: float
    west: float
    north: float
    east: float

    @classmethod
    def parse(cls, raw: str) -> BoundingBox:
        """Parse ``south,west,north,east`` (Leaflet ``toBBoxString`` order is w,s,e,n — see API)."""
        parts = raw.split(",")
        if len(parts) != 4:
            raise InvalidGeometry("bbox must have 4 comma-separated numbers: south,west,north,east")
        try:
            south, west, north, east = (float(p) for p in parts)
        except ValueError as exc:
            raise InvalidGeometry("bbox values must be numbers") from exc
        return cls.of(south, west, north, east)

    @classmethod
    def of(cls, south: float, west: float, north: float, east: float) -> BoundingBox:
        validate_lat_lon(south, west)
        validate_lat_lon(north, east)
        if south > north:
            raise InvalidGeometry("bbox south must be <= north")
        return cls(south=south, west=west, north=north, east=east)

    @property
    def crosses_antimeridian(self) -> bool:
        return self.west > self.east

    def polygons(self) -> list[list[list[float]]]:
        """GeoJSON polygon rings (lon, lat), split at the antimeridian when needed."""
        if self.crosses_antimeridian:
            return [
                _ring(self.south, self.west, self.north, 180.0),
                _ring(self.south, -180.0, self.north, self.east),
            ]
        return [_ring(self.south, self.west, self.north, self.east)]

    def contains(self, latitude: float, longitude: float) -> bool:
        if not self.south <= latitude <= self.north:
            return False
        if self.crosses_antimeridian:
            return longitude >= self.west or longitude <= self.east
        return self.west <= longitude <= self.east

    def area_fraction(self) -> float:
        """Approximate fraction of the globe covered (for choosing clustering granularity)."""
        lon_span = self.east - self.west if self.east >= self.west else self.east - self.west + 360
        lat_span = self.north - self.south
        return min(1.0, (lon_span / 360.0) * (lat_span / 180.0))


def _ring(south: float, west: float, north: float, east: float) -> list[list[float]]:
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def validate_radius_km(radius_km: float) -> None:
    if not (math.isfinite(radius_km) and 0.0 < radius_km <= MAX_RADIUS_KM):
        raise InvalidGeometry(f"radius_km must be in (0, {MAX_RADIUS_KM:.0f}]")
