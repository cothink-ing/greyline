"""CLI config editing: round-trip, comment preservation, validation, city ops."""

import shutil
from pathlib import Path

import pytest

from worldtime import config, configedit


@pytest.fixture
def cfg(tmp_path):
    """A user config seeded from the packaged default."""
    p = tmp_path / "config.toml"
    shutil.copyfile(config.DEFAULT_CONFIG, p)
    return str(p)


def test_set_key_preserves_comments_and_other_keys(cfg):
    before = Path(cfg).read_text()
    assert "#" in before
    configedit.set_key(cfg, "theme", "blue")
    after = Path(cfg).read_text()
    assert "# Default configuration for greyline." in after
    reparsed = config.load(cfg)
    assert reparsed["theme"] == "blue"
    assert reparsed["format"] == "24h"


def test_set_nested_key(cfg):
    configedit.set_key(cfg, "twilight.darkness", "medium")
    assert config.load(cfg)["twilight"]["darkness"] == "medium"


def test_set_key_type_coercion(cfg):
    configedit.set_key(cfg, "logo", "false")
    configedit.set_key(cfg, "bar_height", "115")
    configedit.set_key(cfg, "font_scale", "0.85")
    c = config.load(cfg)
    assert c["logo"] is False and c["bar_height"] == 115 and c["font_scale"] == 0.85


def test_set_key_rejects_bad_enum(cfg):
    with pytest.raises(ValueError):
        configedit.set_key(cfg, "theme", "chartreuse")


def test_set_key_rejects_bad_timezone(cfg):
    with pytest.raises(ValueError):
        configedit.set_key(cfg, "home.tz", "Mars/Olympus_Mons")


def test_unset_key_reverts_to_default(cfg):
    configedit.set_key(cfg, "theme", "blue")
    assert configedit.unset_key(cfg, "theme") is True
    assert config.load(cfg)["theme"] == "modus"
    assert configedit.unset_key(cfg, "theme") is False


def test_unset_key_descending_into_scalar_is_safe(cfg):
    configedit.set_key(cfg, "logo", "true")
    assert configedit.unset_key(cfg, "logo.foo") is False


def test_set_color_key_stays_a_hex_string(cfg):
    configedit.set_key(cfg, "home.color", "990000")
    assert config.load(cfg)["home"]["color"] == "990000"
    configedit.set_key(cfg, "home.color", "#000000")
    assert config.load(cfg)["home"]["color"] == "#000000"


def test_set_color_key_rejects_non_color(cfg):
    with pytest.raises(ValueError):
        configedit.set_key(cfg, "home.color", "chartreuse")


def test_set_theme_accepts_builtins_and_alias(cfg):
    for name in ("catppuccin", "gruvbox", "rosepine", "tokyonight", "modus", "dark"):
        assert configedit.set_key(cfg, "theme", name) == name


def test_set_theme_accepts_user_theme_file(cfg, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "mytheme.toml").write_text('home = "#fabd2f"\n')
    assert configedit.set_key(cfg, "theme", "mytheme") == "mytheme"


def test_colors_table_keys_validate_as_colors(cfg):
    configedit.set_key(cfg, "colors.home", "990000")
    configedit.set_key(cfg, "colors.gmt", "#11223344")
    c = config.load(cfg)
    assert c["colors"]["home"] == "990000"
    assert c["colors"]["gmt"] == "#11223344"
    with pytest.raises(ValueError):
        configedit.set_key(cfg, "colors.ocean", "chartreuse")
    configedit.set_key(cfg, "colors.night_alpha", "20")
    assert config.load(cfg)["colors"]["night_alpha"] == 20


def test_add_and_remove_city(cfg):
    n0 = len(configedit.list_cities(cfg))
    configedit.add_city(
        cfg, "Testville", 1.5, 2.5, "Asia/Kuala_Lumpur", home=True, label_side="left"
    )
    cities = configedit.list_cities(cfg)
    assert len(cities) == n0 + 1
    added = next(c for c in cities if c["name"] == "Testville")
    assert added["lat"] == 1.5 and added["tz"] == "Asia/Kuala_Lumpur"
    assert added["label_side"] == "left"
    assert config.load(cfg)["home"]["tz"] == "Asia/Kuala_Lumpur"
    assert added["home"] is True

    assert configedit.remove_city(cfg, "testville") == 1
    assert all(c["name"] != "Testville" for c in configedit.list_cities(cfg))


def test_add_city_rejects_bad_timezone(cfg):
    with pytest.raises(ValueError):
        configedit.add_city(cfg, "Nowhere", 0.0, 0.0, "Not/AZone")


def test_ensure_config_creates_from_default(tmp_path):
    target = tmp_path / "sub" / "config.toml"
    assert not target.exists()
    configedit.ensure_config(str(target))
    assert target.exists() and config.load(str(target))["city"]
