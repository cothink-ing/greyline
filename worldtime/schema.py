"""The config schema: every key greyline reads, and what a valid value looks like.

One table, used three ways — `configedit` validates writes against it, `config.load`
validates the file against it, and `tests/test_schema.py` asserts it stays in step with
the code that actually reads the config. Before this existed, `greyline config set`
checked four enums and a colour, wrote everything else unexamined, and a typo'd key or
a wrong-typed value surfaced as a `ValueError` traceback once a minute out of the
renderer (#16 was the same family of bug).

Strictness deliberately differs by path:

  `config set`  rejects an unknown key outright. The user is typing it right now, so
                a typo is best caught at the moment it is made.
  `config.load` warns about unknown keys and carries on, but refuses a *known* key
                holding the wrong type. A config file is also written by hand and by
                home-manager, and a stray key from another version must not take a
                working wallpaper down; a key whose value cannot be used, on the other
                hand, would crash the render anyway and is better said plainly.

`default-config.toml` is not the source of this list. It documents most keys in
comments rather than declaring them, so only ten of the ~24 are readable from it.
"""

from dataclasses import dataclass

_RESOLUTION_HINT = "WxH, e.g. 2560x1440"


@dataclass(frozen=True)
class Key:
    """One config key: how to read a string into it, and what values it accepts."""

    kind: str
    choices: frozenset[str] | None = None
    minimum: int | None = None
    maximum: int | None = None


_B = Key("bool")
_S = Key("str")
_F = Key("float")
_COLOR = Key("color")


def _enum(*values):
    return Key("str", choices=frozenset(values))


SCHEMA: dict[str, Key] = {
    "backend": _enum("auto", "sway", "swww", "hyprpaper", "x11", "windows", "macos", "command"),
    "command": _S,
    "resolution": Key("resolution"),
    "map_style": _enum("vector", "raster"),
    "theme": Key("theme"),
    "format": _enum("24h", "12h"),
    "font_family": _S,
    "font_scale": _F,
    "logo": _B,
    "logo_path": _S,
    "logo_color": _COLOR,
    "logo_invert": _B,
    "logo_scale": _F,
    "logo_max_height": _F,
    "bar_height": Key("int", minimum=0),
    "label_bg_alpha": Key("int", minimum=0, maximum=255),
    "label_background": _B,
    "desaturate": _B,
    "twilight.bands": _B,
    "twilight.darkness": _enum("subtle", "medium", "dramatic"),
    "home.tz": Key("tz"),
    "home.column_highlight": _B,
    "home.color": _COLOR,
    "colors.night_alpha": Key("int", minimum=0, maximum=255),
}

# Managed by `greyline city`, which validates lat/lon/tz itself; not settable as a key.
TABLE_KEYS = frozenset({"city"})


def _color_keys():
    from . import themes

    return themes.COLOR_KEYS | {"logo", "label_bg"}


def lookup(dotted):
    """The Key for a dotted config key, or None if greyline does not read it.

    `colors.*` is resolved against the theme colour names rather than listed out, so
    adding a colour to a theme cannot leave the schema behind.
    """
    if dotted in SCHEMA:
        return SCHEMA[dotted]
    head, _, tail = dotted.partition(".")
    if head == "colors" and tail in _color_keys():
        return _COLOR
    return None


def known_keys():
    """Every settable dotted key, for error messages and tests."""
    return set(SCHEMA) | {f"colors.{k}" for k in _color_keys()}


def _is_hex_color(value):
    s = value.lstrip("#") if isinstance(value, str) else ""
    if len(s) not in (3, 6, 8):
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


def coerce(dotted, raw):
    """Read the CLI string `raw` into the type `dotted` declares.

    Colours stay strings so "990000" cannot become the integer 990000.
    """
    key = lookup(dotted)
    if key is None:
        return raw
    if key.kind in ("str", "color", "theme", "tz", "resolution"):
        return raw
    if key.kind == "bool":
        low = raw.lower()
        if low not in ("true", "false"):
            raise ValueError(f"{dotted}: {raw!r} is not true or false")
        return low == "true"
    try:
        return int(raw) if key.kind == "int" else float(raw)
    except ValueError:
        article = "an integer" if key.kind == "int" else "a number"
        raise ValueError(f"{dotted}: {raw!r} is not {article}") from None


def validate(dotted, value):
    """Raise ValueError if `value` is not usable for `dotted`. Assumes it is coerced."""
    key = lookup(dotted)
    if key is None:
        raise ValueError(f"{dotted!r} is not a greyline config key")

    if key.kind == "bool" and not isinstance(value, bool):
        raise ValueError(f"{dotted}: {value!r} is not true or false")
    if key.kind == "int" and (isinstance(value, bool) or not isinstance(value, int)):
        raise ValueError(f"{dotted}: {value!r} is not an integer")
    if key.kind == "float" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise ValueError(f"{dotted}: {value!r} is not a number")
    if key.kind in ("str", "color", "theme", "tz", "resolution") and not isinstance(value, str):
        raise ValueError(f"{dotted}: {value!r} is not text")

    if key.minimum is not None and value < key.minimum:
        raise ValueError(f"{dotted}: {value} is below the minimum of {key.minimum}")
    if key.maximum is not None and value > key.maximum:
        raise ValueError(f"{dotted}: {value} is above the maximum of {key.maximum}")

    if key.choices is not None and value not in key.choices:
        raise ValueError(f"{dotted}: {value!r} is not one of: {', '.join(sorted(key.choices))}")

    if key.kind == "color" and not _is_hex_color(value):
        raise ValueError(f"{dotted}: {value!r} is not a hex colour (e.g. #e64553)")

    if key.kind == "resolution":
        w, _, h = value.lower().partition("x")
        if not (w.isdigit() and h.isdigit()):
            raise ValueError(f"{dotted}: {value!r} is not {_RESOLUTION_HINT}")

    if key.kind == "theme":
        from . import themes

        allowed = set(themes.available_themes()) | set(themes.ALIASES)
        if value not in allowed:
            raise ValueError(f"{dotted}: {value!r} is not one of: {', '.join(sorted(allowed))}")

    if key.kind == "tz" and value != "auto":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"{dotted}: {value!r} is not a valid IANA timezone") from None


def flatten(cfg, prefix=""):
    """Yield (dotted_key, value) for every leaf in a loaded config dict.

    Table keys (`city`) are yielded whole — their contents are `greyline city`'s
    business, not the schema's.
    """
    for k, v in cfg.items():
        dotted = f"{prefix}{k}"
        if dotted in TABLE_KEYS:
            yield dotted, v
        elif isinstance(v, dict):
            yield from flatten(v, f"{dotted}.")
        else:
            yield dotted, v


def check_config(cfg):
    """Validate a loaded config dict.

    Returns a list of warning strings for keys greyline does not read (which are
    ignored), and raises ValueError on the first known key holding an unusable value.
    """
    warnings = []
    for dotted, value in flatten(cfg):
        if dotted in TABLE_KEYS:
            continue
        if lookup(dotted) is None:
            warnings.append(f"unknown config key {dotted!r} (ignored)")
            continue
        validate(dotted, value)
    return warnings
