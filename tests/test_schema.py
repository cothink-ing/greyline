"""The config schema: coercion, validation, and that it stays in step with the code.

The last two tests are the point of the file. A schema is only worth having if it
cannot fall behind what greyline actually reads, so rather than trusting review to
keep `SCHEMA` and `Options.from_config` aligned, one test watches that mapping read
the config and the other checks the packaged defaults against the schema.
"""

import pytest

from greyline import config, render, schema


class _Recorder(dict):
    """A config dict that records every dotted key looked up through it."""

    def __init__(self, data, seen, prefix=""):
        super().__init__(data)
        self.seen = seen
        self.prefix = prefix

    def get(self, key, default=None):
        dotted = f"{self.prefix}{key}"
        self.seen.add(dotted)
        value = super().get(key, default)
        if isinstance(value, dict):
            return _Recorder(value, self.seen, f"{dotted}.")
        return value


def test_options_read_nothing_outside_the_schema():
    """Adding a key to Options.from_config without a schema entry fails here.

    That is the drift this schema exists to prevent: an unschema'd key is one
    `greyline config set` will refuse and `config.load` will not type-check, so it
    reaches the renderer unvalidated — exactly the shape of the bug that made a
    mistyped `font_scale` crash every tick.
    """
    seen: set[str] = set()
    render.Options.from_config(_Recorder(config.defaults(), seen))

    known = schema.known_keys()
    prefixes = {k.split(".")[0] for k in known}
    unknown = {key for key in seen if key not in known and key not in prefixes | schema.TABLE_KEYS}
    assert not unknown, (
        f"Options.from_config reads keys the schema does not declare: {sorted(unknown)}"
    )


def test_packaged_defaults_satisfy_the_schema():
    """The shipped config must be an example of a valid one."""
    assert schema.check_config(config.defaults()) == []


def test_every_schema_key_is_documented_in_the_default_config():
    """`greyline help keys` prints default-config.toml, so a key missing from it is a
    key no user can discover. Four were (desaturate, label_background, label_bg_alpha,
    logo_color) until the schema made the gap countable.

    Colours are exempt: the file documents them by pointing at the theme TOMLs rather
    than listing eighteen names it would then have to keep in step.
    """
    with open(config.DEFAULT_CONFIG, encoding="utf-8") as f:
        text = f.read()
    undocumented = [
        key
        for key in sorted(schema.known_keys())
        if not key.startswith("colors.") and key.split(".")[-1] not in text
    ]
    assert not undocumented, f"not documented in default-config.toml: {undocumented}"


def test_unknown_key_is_reported_but_not_fatal():
    warnings = schema.check_config({"them": "modus"})
    assert warnings == ["unknown config key 'them' (ignored)"]


def test_known_key_with_an_unusable_value_raises():
    with pytest.raises(ValueError, match="font_scale"):
        schema.check_config({"font_scale": "huge"})


@pytest.mark.parametrize(
    "key, raw, expected",
    [
        ("logo", "true", True),
        ("logo", "FALSE", False),
        ("bar_height", "115", 115),
        ("font_scale", "0.85", 0.85),
        ("theme", "blue", "blue"),
        ("colors.home", "990000", "990000"),  # never coerced to the int 990000
        ("logo_color", "#fff", "#fff"),
    ],
)
def test_coerce_uses_the_declared_type(key, raw, expected):
    assert schema.coerce(key, raw) == expected


@pytest.mark.parametrize(
    "key, raw",
    [
        ("logo", "yes"),
        ("bar_height", "tall"),
        ("font_scale", "huge"),
    ],
)
def test_coerce_rejects_values_of_the_wrong_type(key, raw):
    with pytest.raises(ValueError, match=key):
        schema.coerce(key, raw)


@pytest.mark.parametrize(
    "key, value",
    [
        ("label_bg_alpha", 900),
        ("label_bg_alpha", -1),
        ("bar_height", -5),
        ("format", "48h"),
        ("backend", "wayland"),
        ("twilight.darkness", "extreme"),
        ("home.tz", "Mars/Olympus"),
        ("colors.home", "not-a-colour"),
        ("resolution", "1920"),
        ("theme", "no-such-theme"),
    ],
)
def test_validate_rejects_bad_values(key, value):
    with pytest.raises(ValueError):
        schema.validate(key, value)


@pytest.mark.parametrize(
    "key, value",
    [
        ("label_bg_alpha", 0),
        ("label_bg_alpha", 255),
        ("format", "12h"),
        ("home.tz", "auto"),
        ("home.tz", "Asia/Kuala_Lumpur"),
        ("colors.night_alpha", 20),
        ("colors.ocean", "#0b0e14"),
        ("resolution", "2560x1440"),
        ("theme", "gruvbox"),  # an alias, not a file
    ],
)
def test_validate_accepts_good_values(key, value):
    schema.validate(key, value)


def test_every_theme_colour_key_is_settable_under_colors():
    """`[colors]` overrides whatever a theme file can set, so the two must agree."""
    from greyline import themes

    for key in themes.COLOR_KEYS:
        assert schema.lookup(f"colors.{key}") is not None, f"colors.{key} is not settable"


def test_flatten_leaves_table_keys_whole():
    flat = dict(schema.flatten({"theme": "blue", "home": {"tz": "auto"}, "city": [{"name": "X"}]}))
    assert flat["theme"] == "blue"
    assert flat["home.tz"] == "auto"
    assert flat["city"] == [{"name": "X"}]
