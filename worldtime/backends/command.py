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


def apply(name, png_path):
    cmd = _command()
    if not cmd:
        raise RuntimeError(
            "command backend: no command configured "
            "(set `command` in config or the GREYLINE_COMMAND env var)"
        )
    filled = cmd.replace("{path}", png_path).replace("{output}", name)
    subprocess.run(filled, shell=True, check=True)
