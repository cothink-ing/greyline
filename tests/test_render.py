"""End-to-end smoke: both map styles produce an RGB image of the requested size."""

import os
from datetime import UTC, datetime

import pytest

from worldtime import render

CITIES = [
    {"name": "London", "lat": 51.51, "lon": -0.13, "tz": "Europe/London", "home": True},
    {"name": "Tokyo", "lat": 35.68, "lon": 139.69, "tz": "Asia/Tokyo", "home": False},
]
DT = datetime(2024, 6, 20, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("style", ["raster", "vector"])
def test_render_returns_rgb_at_size(style):
    if style == "raster" and not os.path.isfile(render.BASE_1400):
        pytest.skip("raster map artwork not bundled (IBM/Lenovo art, see NOTICE)")
    img = render.render(CITIES, dt=DT, out_size=(480, 300), map_style=style)
    assert img.size == (480, 300)
    assert img.mode == "RGB"


@pytest.mark.parametrize(
    "tz, lon, month, expected",
    [
        # DST-observing zones must highlight the *standard* (geographic) column all year,
        # not the DST-shifted one — regression for issue #14.
        ("Europe/London", -0.13, 1, 0.0),  # GMT (winter)
        ("Europe/London", -0.13, 7, 0.0),  # BST → must still be 0, not +1
        ("America/New_York", -74.0, 1, -5.0),  # EST
        ("America/New_York", -74.0, 7, -5.0),  # EDT → must still be -5, not -4
        # Southern hemisphere: DST is in Jan, so the naive min-of-two heuristic would fail.
        ("Australia/Sydney", 151.2, 1, 10.0),  # AEDT → must be +10, not +11
        ("Australia/Sydney", 151.2, 7, 10.0),  # AEST
    ],
)
def test_home_column_uses_standard_offset(monkeypatch, tz, lon, month, expected):
    captured = {}
    real_build_base = render.vectormap.build_base

    def spy(*args, **kwargs):
        captured["home_offset"] = kwargs.get("home_offset")
        return real_build_base(*args, **kwargs)

    monkeypatch.setattr(render.vectormap, "build_base", spy)
    cities = [{"name": "Home", "lat": 0.0, "lon": lon, "tz": tz, "home": True}]
    dt = datetime(2026, month, 15, 12, tzinfo=UTC)
    render.render(cities, dt=dt, out_size=(320, 200), map_style="vector")
    assert captured["home_offset"] == expected


def test_unknown_theme_falls_back():
    img = render.render(CITIES, dt=DT, out_size=(320, 200), theme="does-not-exist")
    assert img.size == (320, 200)


def test_hex_parsing_and_bad_values():
    assert render._hex("#e64553") == (230, 69, 83)
    assert render._hex("990000") == (153, 0, 0)  # no leading '#'
    assert render._hex("#fff") == (255, 255, 255)  # #rgb shorthand
    assert render._hex("000000") == (0, 0, 0)  # black is a real colour, not "unset"
    # 8 digits carry a trailing alpha (theme-file format).
    assert render._hex("#58b88034") == (88, 184, 128, 52)
    assert render._hex("11223344") == (17, 34, 51, 68)
    # Unparseable values return None (theme default) instead of raising.
    for bad in (None, 990000, "", "#ggg", "#12345", "#1234567", "notacolor"):
        assert render._hex(bad) is None


def test_logo_scale_shrinks_the_logo():
    from PIL import Image

    th = render.THEMES["dark"]
    full = render._draw_logo(Image.new("RGBA", (1000, 600)), th, render.LOGO_PNG, logo_scale=1.0)
    half = render._draw_logo(Image.new("RGBA", (1000, 600)), th, render.LOGO_PNG, logo_scale=0.5)
    w_full, w_half = full[2] - full[0], half[2] - half[0]
    assert w_half < w_full and abs(w_half - w_full / 2) <= 2


def test_logo_max_height_caps_tall_logos(tmp_path):
    from PIL import Image

    th = render.THEMES["dark"]
    canvas = (1000, 600)
    # A tall/portrait logo would otherwise blow up: at the fixed ~10.4% width its
    # aspect-derived height dwarfs the canvas. The cap bounds it (and keeps aspect).
    tall = tmp_path / "tall.png"
    Image.new("RGBA", (100, 1000), (255, 0, 0, 255)).save(tall)

    uncapped = render._draw_logo(Image.new("RGBA", canvas), th, str(tall))
    capped = render._draw_logo(Image.new("RGBA", canvas), th, str(tall), logo_max_height=0.5)
    h_uncapped = uncapped[3] - uncapped[1]
    h_capped = capped[3] - capped[1]
    assert h_capped <= 600 * 0.5 + 1 < h_uncapped
    # Aspect ratio preserved after capping (tall source stays 1:10).
    w_capped = capped[2] - capped[0]
    assert abs(w_capped - h_capped / 10) <= 1
