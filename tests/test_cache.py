"""The map-base cache: keying, bounds, and that it never changes or breaks a render.

A cache is only allowed to make things faster. The two tests that matter here are
that a cached render is byte-identical to an uncached one, and that every way the
cache can fail leaves a working wallpaper behind.
"""

from datetime import UTC, datetime

from PIL import Image, ImageChops

from worldtime import cache, render

CITIES = [
    {"name": "London", "lat": 51.51, "lon": -0.13, "tz": "Europe/London", "home": True},
    {"name": "Tokyo", "lat": 35.68, "lon": 139.69, "tz": "Asia/Tokyo", "home": False},
]
DT = datetime(2024, 6, 20, 9, 30, tzinfo=UTC)
SIZE = (320, 200)


def _render():
    return render.render(CITIES, dt=DT, out_size=SIZE).convert("RGB")


def _entries(cache_dir):
    return sorted(p.name for p in cache_dir.glob("base-*.png")) if cache_dir.is_dir() else []


def test_second_render_is_byte_identical_and_uses_the_cache(isolated_cache):
    first = _render()
    assert len(_entries(isolated_cache)) == 1

    second = _render()
    assert ImageChops.difference(first, second).getbbox() is None
    assert len(_entries(isolated_cache)) == 1


def test_render_still_works_when_the_cache_is_corrupt(isolated_cache):
    expected = _render()
    (entry,) = _entries(isolated_cache)
    (isolated_cache / entry).write_bytes(b"not a png")

    got = _render()
    assert ImageChops.difference(expected, got).getbbox() is None


def test_render_still_works_when_the_cache_cannot_be_written(monkeypatch):
    monkeypatch.setattr(cache, "cache_dir", lambda: "/proc/greyline-cannot-exist")
    img = render.render(CITIES, dt=DT, out_size=SIZE)
    assert img.size == SIZE and img.mode == "RGB"


def test_a_different_theme_gets_a_different_entry(isolated_cache):
    render.render(CITIES, render.Options(theme="modus"), dt=DT, out_size=SIZE)
    render.render(CITIES, render.Options(theme="blue"), dt=DT, out_size=SIZE)
    assert len(_entries(isolated_cache)) == 2


def test_key_changes_with_every_input():
    theme = {"ocean": (1, 2, 3)}
    base = cache.key_for((100, 100), theme, ("font", 11), 8.0)
    assert base != cache.key_for((200, 100), theme, ("font", 11), 8.0)
    assert base != cache.key_for((100, 100), {"ocean": (1, 2, 4)}, ("font", 11), 8.0)
    assert base != cache.key_for((100, 100), theme, ("font", 12), 8.0)
    assert base != cache.key_for((100, 100), theme, ("other", 11), 8.0)
    assert base != cache.key_for((100, 100), theme, ("font", 11), 5.5)
    assert base == cache.key_for((100, 100), dict(theme), ("font", 11), 8.0)


def test_key_is_stable_across_theme_dict_ordering():
    a = cache.key_for((10, 10), {"ocean": (1, 2, 3), "land": (4, 5, 6)}, ("f", 8), None)
    b = cache.key_for((10, 10), {"land": (4, 5, 6), "ocean": (1, 2, 3)}, ("f", 8), None)
    assert a == b


def test_store_evicts_the_oldest_beyond_the_cap(isolated_cache):
    """Bounded like the wallpaper buffers are — this is what keeps it off the
    'no unbounded caches' list in CONTRIBUTING.md."""
    import os

    image = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
    for i in range(cache._MAX_ENTRIES + 3):
        cache.store(f"{i:016x}", image)
        # Distinct mtimes, so "oldest" is well defined without sleeping.
        os.utime(cache._path(f"{i:016x}"), (i, i))
    assert len(_entries(isolated_cache)) == cache._MAX_ENTRIES
    survivors = set(_entries(isolated_cache))
    assert f"base-{0:016x}.png" not in survivors
    assert f"base-{cache._MAX_ENTRIES + 2:016x}.png" in survivors


def test_load_returns_none_for_a_missing_entry():
    assert cache.load("0" * 16) is None


def test_clear_removes_every_entry(isolated_cache):
    _render()
    assert cache.clear() == 1
    assert _entries(isolated_cache) == []
