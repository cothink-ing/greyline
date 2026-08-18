"""Geographic <-> pixel affine: anchor point and x round-trip."""

from worldtime import geo


def test_origin_maps_to_offsets():
    # lon=lat=0 collapses the affine to its constant terms.
    x, y = geo.lonlat_to_px(0.0, 0.0)
    assert x == geo.CX
    assert y == geo.CY


def test_x_to_lon_round_trip():
    # x_to_lon ignores the negligible lat term, so test at lat=0 where it is exact.
    for lon in (-150.0, -30.0, 0.0, 45.0, 170.0):
        x, _y = geo.lonlat_to_px(lon, 0.0)
        assert abs(geo.x_to_lon(x) - lon) < 1e-6


def test_latitude_axis_is_inverted():
    # Northern latitudes sit higher on screen (smaller y) than southern ones.
    assert geo.lat_to_y(60.0) < geo.lat_to_y(-60.0)
