"""Theme loading: built-in and user TOML palettes.

Themes are data, not code — greyline/themes/*.toml ships the built-ins, and
~/.config/greyline/themes/*.toml (XDG-aware) lets users add new themes or
override built-ins per key. Each file maps semantic keys to hex colours
("#rrggbb" or "#rrggbbaa"); see themes/modus.toml for the reference schema.
"""

import os
import tomllib

from .config import _xdg_config_home

BUILTIN_DIR = os.path.join(os.path.dirname(__file__), "themes")

ALIASES = {
    "dark": "modus",
    "gruvbox": "gruvbox-dark-hard",
    "catppuccin": "catppuccin-mocha",
    "rosepine": "rose-pine",
    "tokyonight": "tokyo-night-dark",
}
DEFAULT_THEME = "modus"

COLOR_KEYS = frozenset(
    {
        "night",
        "day_wash",
        "text",
        "text_stroke",
        "dot",
        "dot_outline",
        "home",
        "home_stroke",
        "column",
        "ocean",
        "land",
        "border",
        "grid",
        "grid_label",
        "idl",
        "gmt",
    }
)
OPTIONAL_KEYS = frozenset({"night_alpha", "logo", "label_bg"})


def _hex(s):
    """Parse '#rrggbb' / 'rrggbb' / '#rgb' / '#rrggbbaa' to an (r, g, b[, a]) tuple.

    Returns None for anything unparseable (empty, non-string, bad length/digits) so a
    stray config value falls back to the theme default instead of crashing the render.
    """
    if not isinstance(s, str):
        return None
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) not in (6, 8):
        return None
    try:
        return tuple(int(s[i : i + 2], 16) for i in range(0, len(s), 2))
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
    """Built-in palettes as render-ready tuple dicts, keyed by name."""
    return {name: _apply({}, _parse(path)) for name, path in _scan(BUILTIN_DIR).items()}


def resolve(name):
    """(theme actually used, its file, [problems]) for a requested theme name.

    `load_theme` must not fail — a theme file with a typo in it cannot be allowed to
    stop a wallpaper that redraws every minute — so it falls back to modus and carries
    on. That silence is right for the renderer and wrong for the person who asked for
    one theme and got another, which is the shape of bug #16. Both go through here, so
    what `greyline doctor` reports is what the renderer did, not a second guess at it.

    `problems` is empty when the theme loaded exactly as asked.
    """
    avail = available_themes()
    resolved = name if name in avail else ALIASES.get(name, name)
    path = avail.get(resolved)
    fallback = avail.get(DEFAULT_THEME)

    if path is None:
        return DEFAULT_THEME, fallback, [f"no theme named {name!r} — using {DEFAULT_THEME}"]

    parsed = _parse(path)
    if parsed is None:
        return DEFAULT_THEME, fallback, [f"{path} is not valid TOML — using {DEFAULT_THEME}"]

    problems = []
    unusable = sorted(
        key
        for key in COLOR_KEYS | {"logo", "label_bg"}
        if key in parsed and _hex(parsed[key]) is None
    )
    if unusable:
        problems.append(f"{path}: not a colour, ignored: {', '.join(unusable)}")
    alpha = parsed.get("night_alpha")
    if alpha is not None and not (
        isinstance(alpha, int) and not isinstance(alpha, bool) and 0 <= alpha <= 255
    ):
        problems.append(f"{path}: night_alpha={alpha!r} is not 0-255, ignored")
    return resolved, path, problems


def load_theme(name, overrides=None):
    """Return a render-ready colour dict for `name` (tuples, not hex strings).

    Merge order: modus base (sans optional extras) < same-name built-in < the
    selected file (user files shadow built-ins) < `overrides` (the [colors]
    table). Unknown names and unreadable files fall back to modus; `resolve` reports
    why, and `greyline doctor` prints it.

    The built-in layer follows aliases even when a user file shadows one, so a
    partial ~/.config/greyline/themes/gruvbox.toml still inherits the rest of
    gruvbox-dark-hard rather than dropping all the way back to modus.
    """
    name, path, _ = resolve(name)
    parsed = _parse(path) if path else None

    default = _parse(os.path.join(BUILTIN_DIR, DEFAULT_THEME + ".toml"))
    if default is None:
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


def _relative_luminance(rgb):
    """WCAG 2.x relative luminance of an (r, g, b) colour."""

    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
    """WCAG 2.x contrast ratio between two (r, g, b) colours, 1.0 (same) to 21.0."""
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def label_plate(theme, background, alpha=130):
    """The colour a clock label's text is actually drawn against.

    render.py fills a rounded `label_bg` rectangle behind every label at
    `label_bg_alpha`, so the text contrasts against *that* composite, not against the
    raw map colour underneath. `background` is the map colour the plate sits on (land
    or ocean). At alpha 0 (`label_background = false`) the plate vanishes and the
    answer is the map itself, which is why themes are checked at the shipped default.
    """
    plate = tuple(theme.get("label_bg", (0, 0, 0))[:3])
    t = alpha / 255.0
    return tuple(round(p * t + b * (1 - t)) for p, b in zip(plate, background[:3], strict=True))
