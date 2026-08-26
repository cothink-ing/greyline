"""Day/night terminator math against known solar geometry."""

from datetime import UTC, datetime

import pytest

from worldtime import sun


def _utc(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=UTC)


def test_solstice_declinations():
    june, _ = sun.subsolar_point(_utc(2024, 6, 20))
    dec, _ = sun.subsolar_point(_utc(2024, 12, 21))
    assert june == pytest.approx(23.4, abs=0.6)
    assert dec == pytest.approx(-23.4, abs=0.6)


def test_equinox_declination_near_zero():
    lat, _ = sun.subsolar_point(_utc(2024, 3, 20))
    assert abs(lat) < 1.5


def test_subsolar_longitude_near_prime_meridian_at_noon_utc():
    _lat, lon = sun.subsolar_point(_utc(2024, 3, 20))
    assert abs(lon) < 5.0


def test_boundary_lat_is_clamped():
    sublat, sublon = sun.subsolar_point(_utc(2024, 6, 20))
    for lon in range(-180, 181, 30):
        for elev in (0.0, -6.0, -12.0, -18.0):
            lat = sun.boundary_lat(lon, sublat, sublon, elev)
            assert -90.0 <= lat <= 90.0


def test_night_hemisphere_follows_declination():
    assert sun.night_is_south(10.0) is True
    assert sun.night_is_south(-10.0) is False
