"""Theme files: built-in completeness/parity, user overrides, and robustness."""

from datetime import UTC, datetime

import pytest

from worldtime import render, themes

CITIES = [
    {"name": "London", "lat": 51.51, "lon": -0.13, "tz": "Europe/London", "home": True},
    {"name": "Tokyo", "lat": 35.68, "lon": 139.69, "tz": "Asia/Tokyo", "home": False},
]
DT = datetime(2024, 6, 20, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize("name", sorted(themes.builtin_themes()))
def test_every_builtin_theme_is_complete_and_renders(name):
    th = themes.load_theme(name)
    missing = themes.COLOR_KEYS - set(th)
    assert not missing, f"{name}: missing {sorted(missing)}"
    for key in themes.COLOR_KEYS:
        assert len(th[key]) in (3, 4), f"{name}.{key}: {th[key]!r}"
    img = render.render(CITIES, render.Options(theme=name), dt=DT, out_size=(320, 200))
    assert img.size == (320, 200) and img.mode == "RGB"


@pytest.mark.parametrize("name", sorted(themes.builtin_themes()))
def test_every_builtin_theme_has_readable_labels(name):
    """Clock labels must clear WCAG AA against the plate they are drawn on.

    A wallpaper nobody can read the time off is a broken wallpaper, and the
    base16 slot mapping cannot guarantee this on its own: `text` comes from
    base06, which is a *light* accent in Catppuccin Latte and landed at 2.02:1
    there until the generator learned to fall back to base05. This is the check
    that catches the next scheme whose palette breaks the same assumption.

    Measured at the shipped `label_bg_alpha` (130) against both backdrops the
    plate can sit on. Setting `label_background = false` removes the plate and is
    the user's call to make.
    """
    th = themes.load_theme(name)
    for surface in ("land", "ocean"):
        plate = themes.label_plate(th, th[surface])
        ratio = themes.contrast_ratio(th["text"], plate)
        assert ratio >= 4.5, f"{name}: text on the plate over {surface} is {ratio:.2f}:1"


def test_contrast_ratio_matches_wcag_reference_values():
    """Anchors the formula itself, so the threshold above means what it says."""
    assert themes.contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert themes.contrast_ratio((255, 255, 255), (255, 255, 255)) == pytest.approx(1.0)
    assert themes.contrast_ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)


def test_label_plate_composites_toward_the_backdrop_at_low_alpha():
    th = themes.load_theme("modus")
    assert themes.label_plate(th, th["ocean"], alpha=0) == tuple(th["ocean"][:3])
    assert themes.label_plate(th, th["ocean"], alpha=255) == (0, 0, 0)


def test_modus_parity_with_pre_060_dark():
    th = themes.load_theme("modus")
    assert th["ocean"] == (11, 14, 20)
    assert th["land"] == (30, 34, 43)
    assert th["home"] == (255, 209, 64)
    assert th["gmt"] == (88, 184, 128, 52)
    assert th["day_wash"] == (140, 165, 220, 18)
    assert th["night_alpha"] == 12
    assert th["logo"] == (224, 228, 238)


def test_blue_parity_and_no_optional_keys():
    th = themes.load_theme("blue")
    assert th["ocean"] == (61, 97, 210)
    assert th["gmt"] == (90, 220, 130, 64)
    assert "night_alpha" not in th and "logo" not in th


def test_dark_is_a_permanent_alias_for_modus():
    assert themes.load_theme("dark") == themes.load_theme("modus")
    assert render.THEMES["dark"] is render.THEMES["modus"]


def test_user_theme_overrides_builtin_per_key(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "catppuccin.toml").write_text('home = "#ff0000"\n')
    th = themes.load_theme("catppuccin")
    assert th["home"] == (255, 0, 0)
    assert th["ocean"] == (30, 30, 46)


def test_new_user_theme_falls_back_to_modus_for_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "mytheme.toml").write_text('ocean = "#102030"\n')
    th = themes.load_theme("mytheme")
    assert th["ocean"] == (16, 32, 48)
    assert th["land"] == (30, 34, 43)
    assert "night_alpha" not in th and "logo" not in th
    img = render.render(CITIES, render.Options(theme="mytheme"), dt=DT, out_size=(320, 200))
    assert img.size == (320, 200)


def test_broken_user_theme_never_crashes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "broken.toml").write_text("this is [not toml")
    assert themes.load_theme("broken") == themes.load_theme("modus")
    (d / "sloppy.toml").write_text('ocean = "nope"\nhome = "#ff0000"\n')
    th = themes.load_theme("sloppy")
    assert th["ocean"] == (11, 14, 20) and th["home"] == (255, 0, 0)


def test_colors_overrides_apply_last():
    th = themes.load_theme(
        "modus",
        overrides={
            "home": "#fabd2f",
            "night_alpha": 20,
            "ocean": "nope",
            "logo": "#112233",
        },
    )
    assert th["home"] == (250, 189, 47)
    assert th["night_alpha"] == 20
    assert th["ocean"] == (11, 14, 20)
    assert th["logo"] == (17, 34, 51)


def test_pre_070_theme_names_still_resolve():
    for old, new in (
        ("gruvbox", "gruvbox-dark-hard"),
        ("catppuccin", "catppuccin-mocha"),
        ("rosepine", "rose-pine"),
        ("tokyonight", "tokyo-night-dark"),
    ):
        assert themes.load_theme(old) == themes.load_theme(new), old


def test_user_file_named_after_an_alias_inherits_the_aliased_builtin(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "gruvbox.toml").write_text('home = "#ff0000"\n')
    th = themes.load_theme("gruvbox")
    assert th["home"] == (255, 0, 0)
    assert th["ocean"] == themes.load_theme("gruvbox-dark-hard")["ocean"]


@pytest.mark.parametrize("name", sorted(themes.builtin_themes()))
def test_builtin_themes_keep_land_readable_against_the_ocean(name):
    th = themes.load_theme(name)
    luma = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]  # noqa: E731
    assert abs(luma(th["land"]) - luma(th["ocean"])) >= 15, f"{name}: land ~ ocean"
    assert th["land"][:3] != th["border"][:3], f"{name}: land == border"


def test_light_themes_carry_a_light_label_plate():
    for name in (
        "gruvbox-light-medium",
        "everforest-light-hard",
        "rose-pine-dawn",
        "tokyo-night-light",
        "catppuccin-latte",
        "solarized-light",
    ):
        th = themes.load_theme(name)
        assert "label_bg" in th, f"{name}: no label_bg"
        assert sum(th["label_bg"][:3]) > sum(th["text"][:3]), f"{name}: plate darker than text"


def test_dark_themes_leave_the_label_plate_black():
    for name in ("modus", "blue", "gruvbox-dark-hard", "tokyo-night-storm"):
        assert "label_bg" not in themes.load_theme(name)


def test_label_bg_reaches_the_render():
    img = render.render(
        CITIES, render.Options(theme="gruvbox-light-medium"), dt=DT, out_size=(320, 200)
    )
    assert img.size == (320, 200) and img.mode == "RGB"
