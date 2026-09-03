"""End-to-end smoke: both map styles produce an RGB image of the requested size."""

import os
from datetime import UTC, datetime

import pytest

from greyline import render, themes

CITIES = [
    {"name": "London", "lat": 51.51, "lon": -0.13, "tz": "Europe/London", "home": True},
    {"name": "Tokyo", "lat": 35.68, "lon": 139.69, "tz": "Asia/Tokyo", "home": False},
]
DT = datetime(2024, 6, 20, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("style", ["raster", "vector"])
def test_render_returns_rgb_at_size(style):
    if style == "raster" and not os.path.isfile(render.BASE_1400):
        pytest.skip("raster map artwork not bundled (IBM/Lenovo art, see NOTICE)")
    img = render.render(CITIES, render.Options(map_style=style), dt=DT, out_size=(480, 300))
    assert img.size == (480, 300)
    assert img.mode == "RGB"


@pytest.mark.parametrize(
    "tz, lon, month, expected",
    [
        ("Europe/London", -0.13, 1, 0.0),
        ("Europe/London", -0.13, 7, 0.0),
        ("America/New_York", -74.0, 1, -5.0),
        ("America/New_York", -74.0, 7, -5.0),
        ("Australia/Sydney", 151.2, 1, 10.0),
        ("Australia/Sydney", 151.2, 7, 10.0),
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
    render.render(cities, render.Options(map_style="vector"), dt=dt, out_size=(320, 200))
    assert captured["home_offset"] == expected


def test_unknown_theme_falls_back():
    img = render.render(CITIES, render.Options(theme="does-not-exist"), dt=DT, out_size=(320, 200))
    assert img.size == (320, 200)


def test_hex_parsing_and_bad_values():
    assert render._hex("#e64553") == (230, 69, 83)
    assert render._hex("990000") == (153, 0, 0)
    assert render._hex("#fff") == (255, 255, 255)
    assert render._hex("000000") == (0, 0, 0)
    assert render._hex("#58b88034") == (88, 184, 128, 52)
    assert render._hex("11223344") == (17, 34, 51, 68)
    for bad in (None, 990000, "", "#ggg", "#12345", "#1234567", "notacolor"):
        assert render._hex(bad) is None


def test_logo_scale_shrinks_the_logo():
    from PIL import Image

    th = themes.load_theme("dark")
    full = render._draw_logo(Image.new("RGBA", (1000, 600)), th, render.LOGO_PNG, logo_scale=1.0)
    half = render._draw_logo(Image.new("RGBA", (1000, 600)), th, render.LOGO_PNG, logo_scale=0.5)
    w_full, w_half = full[2] - full[0], half[2] - half[0]
    assert w_half < w_full and abs(w_half - w_full / 2) <= 2


def test_logo_max_height_caps_tall_logos(tmp_path):
    from PIL import Image

    th = themes.load_theme("dark")
    canvas = (1000, 600)
    tall = tmp_path / "tall.png"
    Image.new("RGBA", (100, 1000), (255, 0, 0, 255)).save(tall)

    uncapped = render._draw_logo(Image.new("RGBA", canvas), th, str(tall))
    capped = render._draw_logo(Image.new("RGBA", canvas), th, str(tall), logo_max_height=0.5)
    h_uncapped = uncapped[3] - uncapped[1]
    h_capped = capped[3] - capped[1]
    assert h_capped <= 600 * 0.5 + 1 < h_uncapped
    w_capped = capped[2] - capped[0]
    assert abs(w_capped - h_capped / 10) <= 1


def test_recolor_dark_matches_a_per_pixel_reference():
    """The whole-image version has to agree with the obvious loop, pixel for pixel.

    `_recolor_dark` was that loop until it became the expensive part of a tick with
    `logo_invert` set. The reference below is the behaviour it used to have; this is
    what makes the rewrite a refactor rather than a rewrite-and-hope.
    """
    from PIL import Image

    light = (235, 235, 238)
    # A spread of dark/light, opaque/transparent, and colours that must be kept.
    pixels = [
        (x * 17, y * 17, (x + y) * 8 % 256, 0 if (x + y) % 7 == 0 else 255)
        for y in range(16)
        for x in range(16)
    ]
    pixels[0] = (69, 69, 69, 255)  # just under the threshold: recoloured
    pixels[1] = (70, 70, 70, 255)  # exactly on it: left alone
    pixels[2] = (0, 0, 0, 1)  # barely visible, still recoloured
    pixels[3] = (0, 0, 0, 0)  # fully transparent: left alone

    def reference(px):
        r, g, b, a = px
        return (*light, a) if a and max(r, g, b) < 70 else px

    src = Image.new("RGBA", (16, 16))
    src.putdata(pixels)
    expected = Image.new("RGBA", (16, 16))
    expected.putdata([reference(p) for p in pixels])

    got = render._recolor_dark(src, light)
    assert got.mode == "RGBA"
    assert got.tobytes() == expected.tobytes()
