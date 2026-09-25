from __future__ import annotations

import pytest

from apps.geo.geodesic import (
    BoundingBox,
    InvalidGeometry,
    haversine_km,
    validate_lat_lon,
    validate_radius_km,
)
from apps.geo.regions import region_from_place, slugify


class TestHaversine:
    def test_zero_distance(self) -> None:
        assert haversine_km(17.385, 78.4867, 17.385, 78.4867) == 0

    def test_known_distance_hyderabad_chennai(self) -> None:
        # Great-circle Hyderabad (17.3850, 78.4867) -> Chennai (13.0827, 80.2707) ≈ 515 km
        assert haversine_km(17.3850, 78.4867, 13.0827, 80.2707) == pytest.approx(515.2, abs=1)

    def test_antipodal_is_half_circumference(self) -> None:
        assert haversine_km(0, 0, 0, 180) == pytest.approx(20015.1, abs=1)

    def test_symmetry_across_antimeridian(self) -> None:
        d1 = haversine_km(0, 179.5, 0, -179.5)
        assert d1 == pytest.approx(111.2, abs=0.5)
        assert d1 == pytest.approx(haversine_km(0, -179.5, 0, 179.5))


class TestValidation:
    @pytest.mark.parametrize(("lat", "lon"), [(91, 0), (-91, 0), (0, 181), (float("nan"), 0)])
    def test_invalid_coordinates(self, lat: float, lon: float) -> None:
        with pytest.raises(InvalidGeometry):
            validate_lat_lon(lat, lon)

    @pytest.mark.parametrize("radius", [0, -5, 20_001, float("inf")])
    def test_invalid_radius(self, radius: float) -> None:
        with pytest.raises(InvalidGeometry):
            validate_radius_km(radius)


class TestBoundingBox:
    def test_parse_and_contains(self) -> None:
        box = BoundingBox.parse("10,70,20,80")
        assert box.contains(15, 75)
        assert not box.contains(25, 75)
        assert not box.crosses_antimeridian
        assert len(box.polygons()) == 1

    def test_antimeridian_split(self) -> None:
        box = BoundingBox.parse("-30,170,-10,-170")
        assert box.crosses_antimeridian
        assert box.contains(-20, 175)
        assert box.contains(-20, -175)
        assert not box.contains(-20, 0)
        west, east = box.polygons()
        assert west[1][0] == 180.0
        assert east[0][0] == -180.0

    @pytest.mark.parametrize("raw", ["1,2,3", "a,b,c,d", "20,0,10,5", "0,0,95,0"])
    def test_invalid(self, raw: str) -> None:
        with pytest.raises(InvalidGeometry):
            BoundingBox.parse(raw)

    def test_area_fraction(self) -> None:
        assert BoundingBox.of(-90, -180, 90, 180).area_fraction() == pytest.approx(1.0)
        assert BoundingBox.of(0, 0, 18, 36).area_fraction() == pytest.approx(0.01)
        assert BoundingBox.of(0, 170, 18, -154).area_fraction() == pytest.approx(0.01)  # wraps


class TestRegions:
    @pytest.mark.parametrize(
        ("place", "key", "name", "kind"),
        [
            ("6 km SE of Pinnacles, CA", "california", "California", "us_state"),
            ("12 km NNE of Pāhala, Hawaii", "hawaii", "Hawaii", "us_state"),
            ("11 km W of Progreso, B.C., MX", "mexico", "Mexico", "country_or_area"),
            ("2 km NNW of Orihuela, Spain", "spain", "Spain", "country_or_area"),
            ("Fiji region", "fiji-region", "Fiji region", "named_region"),
            ("south of the Fiji Islands", "south-of-the-fiji-islands", "south of the Fiji Islands",
             "named_region"),
            ("45 km SW of Kokopo", "kokopo", "Kokopo", "named_region"),
        ],
    )  # fmt: skip
    def test_region_derivation(self, place: str, key: str, name: str, kind: str) -> None:
        region = region_from_place(place)
        assert region is not None
        assert (region.key, region.name, region.kind) == (key, name, kind)

    @pytest.mark.parametrize("place", [None, "", "   ", "Somewhere,"])
    def test_no_region(self, place: str | None) -> None:
        assert region_from_place(place) is None

    def test_slugify_strips_diacritics(self) -> None:
        assert slugify("Pāhala, Hawaiʻi") == "pahala-hawaii"  # noqa: RUF001 - real okina
