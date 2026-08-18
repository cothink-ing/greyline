"""Theme loading: built-in and user TOML palettes.

Themes are data, not code — worldtime/themes/*.toml ships the built-ins, and
~/.config/greyline/themes/*.toml (XDG-aware) lets users add new themes or
override built-ins per key. Each file maps semantic keys to hex colours
("#rrggbb" or "#rrggbbaa"); see themes/modus.toml for the reference schema.
"""
import os
import tomllib

from .config import _xdg_config_home

BUILTIN_DIR = os.path.join(os.path.dirname(__file__), "themes")

# Backwards compatibility: every name greyline has ever shipped keeps working.
# "dark" became "modus" (after Modus Vivendi) in 0.6; in 0.7 the palettes moved to
# their upstream base16 slugs, which name the variant a bare family name left
# implicit. The aliases are permanent, and a user theme file with an alias's name
# shadows it (available_themes() is checked first).
ALIASES = {
    "dark": "modus",
    "gruvbox": "gruvbox-dark-hard",
    "catppuccin": "catppuccin-mocha",
    "rosepine": "rose-pine",
    "tokyonight": "tokyo-night-dark",
}
DEFAULT_THEME = "modus"

# Every key render/vectormap index unconditionally. Built-in themes carry all of
# them; partial user themes are merged over a complete base so lookups never fail.
COLOR_KEYS = frozenset({
    "night", "day_wash", "text", "text_stroke", "dot", "dot_outline",
    "home", "home_stroke", "column", "ocean", "land", "border",
    "grid", "grid_label", "idl", "gmt",
})
# Optional per-theme extras — never inherited across themes (blue deliberately has
# no night_alpha/logo and must not gain modus's through the fallback merge).
# label_bg tints the plate behind each clock label; unset means black, which is
# what every dark theme wants and no light theme does.
OPTIONAL_KEYS = frozenset({"night_alpha", "logo", "label_bg"})


def _hex(s):
    """Parse '#rrggbb' / 'rrggbb' / '#rgb' / '#rrggbbaa' to an (r, g, b[, a]) tuple.

    Returns None for anything unparseable (empty, non-string, bad length/digits) so a
    stray config value falls back to the theme default instead of crashing the render.
    """
    if not isinstance(s, str):
        return None
    s = s.strip().lstrip("#")
    if len(s) == 3:  # #rgb shorthand -> #rrggbb
        s = "".join(c * 2 for c in s)
    if len(s) not in (6, 8):
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in range(0, len(s), 2))
    except ValueError:
        return None


def user_theme_dir():
    return os.path.join(_xdg_config_home(), "greyline", "themes")


def _scan(dirpath):
    if not os.path.isdir(dirpath):
        return {}
    return {
        fn[:-5]: os.path.join(dirpath, fn)
        for fn in sorted(os.listdir(dirpath))
        if fn.endswith(".toml")
    }


def available_themes():
    """{name: path} for every selectable theme; user files shadow built-ins."""
    return {**_scan(BUILTIN_DIR), **_scan(user_theme_dir())}


def theme_names():
    return sorted(available_themes())


def _parse(path):
    """Parse a theme file, or None — a broken user file must never crash the
    minutely systemd render."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def _apply(theme, values):
    """Merge hex values over tuple values, keeping the old ones for invalid entries
    (per-key fallback, mirroring how home.color has always behaved)."""
    out = dict(theme)
    for key in COLOR_KEYS | {"logo", "label_bg"}:
        if key in values:
            rgb = _hex(values[key])
            if rgb is not None:
                out[key] = rgb
    na = values.get("night_alpha")
    if isinstance(na, int) and not isinstance(na, bool) and 0 <= na <= 255:
        out["night_alpha"] = na
    return out


def builtin_themes():
    """Built-in palettes as render-ready tuple dicts (render.THEMES snapshot)."""
    return {name: _apply({}, _parse(path)) for name, path in _scan(BUILTIN_DIR).items()}


def load_theme(name, overrides=None):
    """Return a render-ready colour dict for `name` (tuples, not hex strings).

    Merge order: modus base (sans optional extras) < same-name built-in < the
    selected file (user files shadow built-ins) < `overrides` (the [colors]
    table). Unknown names and unreadable files fall back to modus silently.

    The built-in layer follows aliases even when a user file shadows one, so a
    partial ~/.config/greyline/themes/gruvbox.toml still inherits the rest of
    gruvbox-dark-hard rather than dropping all the way back to modus.
    """
    avail = available_themes()
    if name not in avail:
        name = ALIASES.get(name, name)
    path = avail.get(name)
    parsed = _parse(path) if path else None

    default = _parse(os.path.join(BUILTIN_DIR, DEFAULT_THEME + ".toml"))
    if default is None:  # packaging bug — the smoke test exists to catch this
        raise RuntimeError(f"builtin theme {DEFAULT_THEME!r} is missing or invalid")
    if parsed is None:
        name, parsed = DEFAULT_THEME, default

    theme = {k: v for k, v in _apply({}, default).items() if k not in OPTIONAL_KEYS}
    builtin = _parse(os.path.join(BUILTIN_DIR, ALIASES.get(name, name) + ".toml"))
    if builtin is not None:
        theme = _apply(theme, builtin)
    theme = _apply(theme, parsed)
    if isinstance(overrides, dict):
        theme = _apply(theme, overrides)
    return theme
