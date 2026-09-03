"""Geographic <-> pixel affine: anchor point and x round-trip."""

from greyline import geo


def test_origin_maps_to_offsets():
    x, y = geo.lonlat_to_px(0.0, 0.0)
    assert x == geo.CX
    assert y == geo.CY


def test_x_to_lon_round_trip():
    for lon in (-150.0, -30.0, 0.0, 45.0, 170.0):
        x, _y = geo.lonlat_to_px(lon, 0.0)
        assert abs(geo.x_to_lon(x) - lon) < 1e-6


def test_latitude_axis_is_inverted():
    assert geo.lat_to_y(60.0) < geo.lat_to_y(-60.0)
