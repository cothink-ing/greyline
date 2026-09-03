"""Generic command backend — hand the rendered PNG to a user-supplied command.

For desktops greyline has no native backend for (GNOME, KDE Plasma, XFCE, …),
greyline renders a PNG and then runs *your* command with ``{path}`` (and
``{output}``) substituted, so any desktop with a CLI wallpaper-setter works:

    gsettings / plasma-apply-wallpaperimage / xfconf-query / feh / …

This REPLACES the desktop wallpaper — it does not overlay the existing one. Each
tick overwrites it; the last image stays after greyline exits. Configure via the
config file:

    backend = "command"
    command = 'gsettings set org.gnome.desktop.background picture-uri "file://{path}"'
    resolution = "2560x1440"   # optional; sizes the single rendered image

or the ``GREYLINE_COMMAND`` / ``GREYLINE_RESOLUTION`` environment variables (which
``__main__`` sets from the config/CLI). One image is rendered for the whole
desktop, since a single command typically sets every monitor at once; use
``{output}`` in your command if it can target individual outputs.
"""

import os
import re
import subprocess

from . import _util


def _command():
    return os.environ.get("GREYLINE_COMMAND")


def available():
    return bool(_command())


def _resolution():
    """(width, height) for the single rendered image: explicit GREYLINE_RESOLUTION,
    else the largest xrandr output, else a 1920x1080 fallback.
    """
    res = os.environ.get("GREYLINE_RESOLUTION")
    if res:
        try:
            w, h = res.lower().split("x")
            return int(w), int(h)
        except ValueError:
            pass
    outs = _util.xrandr_outputs()
    if outs:
        o = max(outs, key=lambda o: o["width"] * o["height"])
        return o["width"], o["height"]
    return 1920, 1080


def outputs():
    w, h = _resolution()
    return [{"name": "screen", "width": w, "height": h, "scale": 1.0}]


# The character class shlex.quote treats as needing quoting. Values containing any of
# these change how the shell parses the command once substituted.
_SHELL_UNSAFE = re.compile(r"[^\w@%+=:,./-]")


def _substitute(cmd, name, png_path):
    """Fill {path} and {output} in, or refuse if a value would break the shell.

    Quoting the values instead would be worse than useless here. `shlex.quote` is a
    no-op on an ordinary path, so it would buy nothing in the normal case — and the
    recipes embed the placeholder inside their own quotes (GNOME's ``"file://{path}"``),
    so in the one case it mattered it would produce quotes nested inside quotes and set
    the wallpaper to a path that does not exist. greyline cannot know how a
    user-supplied command quotes its arguments, so it declines rather than guessing.

    In practice this fires only for an exotic ``$XDG_RUNTIME_DIR`` or an output name
    with a space in it; the point is that it says so instead of running something
    unintended.
    """
    for placeholder, value, what in (
        ("{path}", png_path, "the render path"),
        ("{output}", name, "the output name"),
    ):
        if placeholder not in cmd:
            continue
        bad = _SHELL_UNSAFE.search(value)
        if bad:
            raise RuntimeError(
                f"command backend: {what} ({value!r}) contains {bad.group()!r}, which "
                f"would change how the shell reads your command. Substituting it into "
                f"{placeholder} is refused rather than guessed at."
            )
        cmd = cmd.replace(placeholder, value)
    return cmd


def apply(name, png_path):
    cmd = _command()
    if not cmd:
        raise RuntimeError(
            "command backend: no command configured "
            "(set `command` in config or the GREYLINE_COMMAND env var)"
        )
    subprocess.run(_substitute(cmd, name, png_path), shell=True, check=True)
