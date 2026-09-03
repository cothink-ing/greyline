"""Config merge, home-city flagging, and render kwarg mapping."""

from worldtime import config, render


def test_deep_merge_is_recursive():
    base = {"a": 1, "t": {"x": 1, "y": 2}}
    over = {"t": {"y": 9, "z": 3}}
    out = config._deep_merge(base, over)
    assert out == {"a": 1, "t": {"x": 1, "y": 9, "z": 3}}
    assert base["t"] == {"x": 1, "y": 2}


def test_defaults_load_with_cities():
    cfg = config.load(path="/nonexistent/config.toml")
    assert isinstance(cfg.get("city"), list) and cfg["city"]
    assert all({"name", "lat", "lon", "tz"} <= c.keys() for c in cfg["city"])


def test_user_config_overrides_and_replaces_cities(tmp_path):
    user = tmp_path / "config.toml"
    user.write_text(
        'theme = "dark"\n'
        '[home]\ntz = "Europe/London"\n'
        '[[city]]\nname = "London"\nlat = 51.51\nlon = -0.13\ntz = "Europe/London"\n'
        '[[city]]\nname = "Tokyo"\nlat = 35.68\nlon = 139.69\ntz = "Asia/Tokyo"\n'
    )
    cfg = config.load(path=str(user))
    assert cfg["theme"] == "dark"
    assert [c["name"] for c in cfg["city"]] == ["London", "Tokyo"]
    home = [c for c in cfg["city"] if c["home"]]
    assert [c["name"] for c in home] == ["London"]


def test_options_carry_colors_overrides(tmp_path):
    user = tmp_path / "config.toml"
    user.write_text('[colors]\nhome = "#fabd2f"\nnight_alpha = 20\n')
    opts = render.Options.from_config(config.load(path=str(user)))
    assert opts.theme_overrides == {"home": "#fabd2f", "night_alpha": 20}

    bare = render.Options.from_config(config.load(path="/nonexistent/config.toml"))
    assert bare.theme_overrides is None


def test_options_from_the_packaged_defaults_match_the_dataclass_defaults():
    """`Options()` and a config that sets nothing have to mean the same thing —
    otherwise the documented default and the actual default drift apart."""
    from_defaults = render.Options.from_config(config.load(path="/nonexistent/config.toml"))
    assert from_defaults == render.Options()


def test_label_background_false_still_means_no_plate(tmp_path):
    """`label_background` predates `label_bg_alpha` and survives only as its default."""
    user = tmp_path / "config.toml"
    user.write_text("label_background = false\n")
    assert render.Options.from_config(config.load(path=str(user))).label_bg_alpha == 0

    user.write_text("label_background = false\nlabel_bg_alpha = 200\n")
    assert render.Options.from_config(config.load(path=str(user))).label_bg_alpha == 200
