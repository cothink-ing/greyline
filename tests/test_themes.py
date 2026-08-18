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
    img = render.render(CITIES, dt=DT, out_size=(320, 200), theme=name)
    assert img.size == (320, 200) and img.mode == "RGB"


def test_modus_parity_with_pre_060_dark():
    # The rename must not change a single colour (pins the TOML port byte-for-byte).
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
    # blue deliberately has no night_alpha/logo: the darkness preset must apply.
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
    assert th["home"] == (255, 0, 0)  # overridden
    assert th["ocean"] == (30, 30, 46)  # builtin catppuccin, not modus


def test_new_user_theme_falls_back_to_modus_for_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "mytheme.toml").write_text('ocean = "#102030"\n')
    th = themes.load_theme("mytheme")
    assert th["ocean"] == (16, 32, 48)
    assert th["land"] == (30, 34, 43)  # modus fallback
    # Optional extras are never inherited into a new theme.
    assert "night_alpha" not in th and "logo" not in th
    img = render.render(CITIES, dt=DT, out_size=(320, 200), theme="mytheme")
    assert img.size == (320, 200)


def test_broken_user_theme_never_crashes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "broken.toml").write_text("this is [not toml")
    assert themes.load_theme("broken") == themes.load_theme("modus")
    # Garbage values fall back per key, not wholesale.
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
    assert th["ocean"] == (11, 14, 20)  # invalid override ignored
    assert th["logo"] == (17, 34, 51)


# --- base16 ports (0.7) ---


def test_pre_070_theme_names_still_resolve():
    # Renaming to the upstream base16 slugs must not break anyone's config.
    for old, new in (
        ("gruvbox", "gruvbox-dark-hard"),
        ("catppuccin", "catppuccin-mocha"),
        ("rosepine", "rose-pine"),
        ("tokyonight", "tokyo-night-dark"),
    ):
        assert themes.load_theme(old) == themes.load_theme(new), old


def test_user_file_named_after_an_alias_inherits_the_aliased_builtin(tmp_path, monkeypatch):
    # A partial gruvbox.toml means "gruvbox, but…", not "modus, but…".
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "gruvbox.toml").write_text('home = "#ff0000"\n')
    th = themes.load_theme("gruvbox")
    assert th["home"] == (255, 0, 0)
    assert th["ocean"] == themes.load_theme("gruvbox-dark-hard")["ocean"]


@pytest.mark.parametrize("name", sorted(themes.builtin_themes()))
def test_builtin_themes_keep_land_readable_against_the_ocean(name):
    # Landmasses have to differ from the sea, and from the borders drawn over them.
    th = themes.load_theme(name)
    luma = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]  # noqa: E731
    assert abs(luma(th["land"]) - luma(th["ocean"])) >= 15, f"{name}: land ~ ocean"
    assert th["land"][:3] != th["border"][:3], f"{name}: land == border"


def test_light_themes_carry_a_light_label_plate():
    # The plate behind each clock defaults to black; on a light map that would sit
    # under dark label text. Every light port must override it.
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
    # OPTIONAL_KEYS must not leak a light theme's plate into the dark ones.
    for name in ("modus", "blue", "gruvbox-dark-hard", "tokyo-night-storm"):
        assert "label_bg" not in themes.load_theme(name)


def test_label_bg_reaches_the_render():
    img = render.render(CITIES, dt=DT, out_size=(320, 200), theme="gruvbox-light-medium")
    assert img.size == (320, 200) and img.mode == "RGB"
