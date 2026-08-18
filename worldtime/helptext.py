"""Long-form CLI help: the `greyline help <topic>` reference pages, plus the
descriptions and example epilogs argparse prints under each command.

Split out of __main__ so the parser stays readable, and so every page that *can* be
generated is generated from the same data the renderer uses — the theme list from
themes/*.toml, the desktop recipes from recipes.RECIPES, the config-key reference
from the packaged default-config.toml. A reference page that drifts from the code
is worse than no page at all.
"""
import os
import textwrap

from . import backends, config, recipes, themes

DESCRIPTION = """\
greyline — a live world-time desktop wallpaper: a world map with clocks for your
cities, your home city highlighted, and a day/night terminator that tracks the sun.

Run bare (no subcommand) it renders one PNG per output, hands each to your wallpaper
backend, and exits — that is what the systemd timer (or `greyline watch`) invokes
every minute. The subcommands below manage setup, config and scheduling."""

EPILOG = """\
Examples:
  greyline init                             set up config + backend + timer
  greyline city add Tokyo 35.68 139.69 Asia/Tokyo --home
  greyline config set theme gruvbox
  greyline --out /tmp/wall.png --res 2560x1440    render to a file, apply nothing
  greyline doctor                           why isn't my wallpaper changing?

Help:
  greyline help <command>                   e.g. `greyline help city add`
  greyline help topics                      reference pages (keys, themes, ...)"""

HELP_EPILOG = """\
Examples:
  greyline help                 this command list
  greyline help config set      help for one command
  greyline help themes          a reference page

Reference topics: """ + ", ".join(["topics", "keys", "themes", "backends", "desktops"])

INIT_DESCRIPTION = """\
Detect your desktop, write a starter config, pick a wallpaper backend, and schedule
minutely updates (a systemd user timer where available). Safe to re-run: an existing
config is kept and only the backend keys are updated."""

INIT_EPILOG = """\
Examples:
  greyline init                       set everything up
  greyline init --dry-run             show what it would do, change nothing
  greyline init --interval '*:0/5:00' update every 5 minutes instead of every minute"""

WATCH_DESCRIPTION = """\
Render and apply in a foreground loop, for systems without systemd --user (other
init systems, BSD, a bare WM). Put `greyline watch` in your session autostart."""

CONFIG_DESCRIPTION = """\
Read and write ~/.config/greyline/config.toml. Writes are validated (a bad theme or
enum is refused, not written) and preserve the file's comments and layout.
`get` reads the *effective* config: your file merged over the packaged defaults."""

CONFIG_EPILOG = """\
Examples:
  greyline config get                 print the whole config file
  greyline config get twilight.darkness
  greyline config set theme rosepine
  greyline config set format 12h
  greyline config set colors.home '#fabd2f'
  greyline config unset font_scale    revert one key to its default

See `greyline help keys` for every key, its allowed values and default."""

CITY_DESCRIPTION = """\
Manage the clocks on the map. Each city needs a name, latitude, longitude and an
IANA timezone (e.g. Europe/Paris) — DST is then handled by the OS tz database.
Adding your first city replaces the shipped default list wholesale."""

CITY_EPILOG = """\
Examples:
  greyline city list
  greyline city add Tokyo 35.68 139.69 Asia/Tokyo
  greyline city add "Kuala Lumpur" 3.14 101.69 Asia/Kuala_Lumpur --home
  greyline city add Lima -12.05 -77.04 America/Lima --label-side right
  greyline city remove Tokyo

Latitude is +N/-S, longitude +E/-W. --home pins the accented home city (otherwise
it is auto-detected from your system timezone)."""

DOCTOR_DESCRIPTION = """\
Diagnose a wallpaper that isn't updating: print the detected session, the resolved
backend and its outputs, and whether the systemd user timer is available."""

# One line per backend, keyed as in backends._ORDER (+ the manual `command`).
_BACKENDS = {
    "sway": "sway and other wlroots compositors, via swaymsg IPC",
    "swww": "the swww daemon on Wayland, via the swww client",
    "hyprpaper": "Hyprland's hyprpaper, via hyprctl",
    "x11": "bare X11 window managers, via feh or xwallpaper",
    "windows": "Windows, via the desktop wallpaper API",
    "macos": "macOS, via System Events",
    "command": "anything else — your own shell command, run once per output",
}


def _wrap(text, indent="  ", width=88):
    # Theme names and alias arrows are hyphenated; wrapping inside one turns
    # "github-dark" into two half-names on separate lines.
    return textwrap.fill(text, width=width, initial_indent=indent,
                         subsequent_indent=indent, break_on_hyphens=False,
                         break_long_words=False)


def _topics_page():
    return "\n".join([
        "Reference topics — `greyline help <topic>`:",
        "",
        "  keys       every config key, its allowed values and default",
        "  themes     available colour themes and how to write your own",
        "  backends   wallpaper backends and how one gets picked",
        "  desktops   GNOME / KDE / XFCE setup (the `command` backend)",
        "",
        "For a command instead, use `greyline help <command>`, e.g. `greyline help city add`.",
    ])


def _keys_page():
    """The packaged default-config.toml is the key reference — it documents every
    key inline. Print it up to the [[city]] list (managed by `greyline city`).

    Split on a line-initial "[[city]]": the string also appears mid-line in the
    header comment and in the comment documenting the city keys, both of which
    belong in the page."""
    with open(config.DEFAULT_CONFIG, encoding="utf-8") as f:
        head = f.read().partition("\n[[city]]")[0].rstrip()
    return "\n".join([
        "Config keys — shown as the packaged defaults, documented in place.",
        "",
        f"Your config: {config.user_config_path()}",
        "Set them with `greyline config set <key> <value>` (values are validated),",
        "or edit the file directly. Nested keys are dotted: twilight.darkness, home.tz,",
        "colors.home.",
        "",
        head,
        "",
        "…then the [[city]] entries — manage those with `greyline city add|remove|list`.",
    ])


def _themes_page():
    """Built-ins as a wrapped list — there are three dozen, so a name-per-line table
    would push everything else off the screen. User themes stay itemised: those are
    the ones whose file you might be looking for."""
    available = themes.available_themes()
    builtin_dir = os.path.realpath(themes.BUILTIN_DIR)
    builtin, user = [], []
    for name, path in sorted(available.items()):
        target = builtin if os.path.realpath(os.path.dirname(path)) == builtin_dir else user
        target.append(name)

    lines = [
        "Themes — colour palettes, selected with `greyline config set theme <name>`.",
        "",
        f"Built-in ({len(builtin)}) — greyline's own `modus`/`blue`, and ports of the base16",
        "schemes at https://github.com/tinted-theming/schemes:",
        _wrap(", ".join(builtin)),
    ]
    if user:
        lines += ["", f"Yours ({themes.user_theme_dir()}):", _wrap(", ".join(user))]
    lines += [
        "",
        "Older names, kept working forever:",
        _wrap(", ".join(f"{a} = {t}" for a, t in sorted(themes.ALIASES.items()))),
        "",
        "Write your own: put a TOML palette at",
        f"  {os.path.join(themes.user_theme_dir(), '<name>.toml')}",
        "using this as a starting point:",
        f"  {os.path.join(themes.BUILTIN_DIR, 'modus.toml')}",
        "",
        "A user file whose name matches a built-in shadows it. Keys map semantic names to",
        '"#rrggbb" or "#rrggbbaa"; anything you omit falls back to the built-in.',
        "",
        "Keys:",
        _wrap(", ".join(sorted(themes.COLOR_KEYS))),
        "Optional:",
        _wrap(", ".join(sorted(themes.OPTIONAL_KEYS))),
        "",
        "To change one colour without writing a theme file, use the [colors] table:",
        "  greyline config set colors.home '#fabd2f'",
    ]
    return "\n".join(lines)


def _backends_page():
    lines = [
        "Backends — how the rendered PNG reaches your desktop.",
        "",
        "`backend = \"auto\"` (the default) tries these in order and takes the first that",
        "is usable here:",
        "",
    ]
    for name in backends._ORDER:
        lines.append(f"  {name:<12}{_BACKENDS.get(name, '')}")
    lines += [
        "",
        f"  {'command':<12}{_BACKENDS['command']}.",
        f"  {'':<12}Never auto-detected — set it explicitly, see",
        f"  {'':<12}`greyline help desktops`.",
        "",
    ]
    try:
        detected = backends.detect()
    except Exception:  # noqa: BLE001 — help must never fail on a probe
        detected = None
    lines.append(f"Detected here: {detected or '(none — set one manually)'}")
    lines += [
        "",
        "Pin one with `greyline config set backend sway`, or override for a single run",
        "with `greyline --backend sway`. Check the result with `greyline doctor`.",
        "",
        "Note: on a full desktop environment (GNOME/KDE/XFCE) the x11 backend paints the",
        "root window and the DE paints straight over it — use the `command` backend there.",
    ]
    return "\n".join(lines)


def _desktops_page():
    lines = [
        "Desktop environments — GNOME, KDE and XFCE set the wallpaper themselves, so",
        "greyline drives them through the `command` backend: a shell command run once",
        "per output with {path} (the rendered PNG) and {output} substituted.",
        "",
        "`greyline init` detects these and writes the matching recipe for you. To set one",
        "by hand:",
        "",
        "  greyline config set backend command",
        "  greyline config set command '<recipe below>'",
        "",
    ]
    for key, cmd in recipes.RECIPES.items():
        lines += [f"{key}:", f"  {cmd}", ""]
    lines += [
        "These are best-effort and community-verified — the XFCE monitor segment in",
        "particular varies by version and output name; find yours with:",
        "  xfconf-query -c xfce4-desktop -l | grep last-image",
        "",
        "Another desktop? Any command that sets a wallpaper from a file works. Please",
        "open a desktop-compat issue with what worked for you.",
    ]
    return "\n".join(lines)


PAGES = {
    "topics": _topics_page,
    "keys": _keys_page,
    "themes": _themes_page,
    "backends": _backends_page,
    "desktops": _desktops_page,
}


def topic_names():
    return list(PAGES)


def render_topic(name):
    """Return the rendered reference page for `name`, or None if there is none."""
    page = PAGES.get(name)
    return page() if page else None
