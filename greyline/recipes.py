"""Command-backend recipes for desktops without a native backend.

Single source of truth for the GNOME/KDE/XFCE wallpaper commands `greyline init`
writes and the README documents. Each is a shell command run by the `command`
backend with {path} (the rendered PNG) substituted. Best-effort / community-verified
— the maintainers run sway and can't test these directly (see the desktop-compat
issue template).
"""

RECIPES = {
    "gnome": (
        'gsettings set org.gnome.desktop.background picture-uri "" && '
        'gsettings set org.gnome.desktop.background picture-uri "file://{path}" && '
        'gsettings set org.gnome.desktop.background picture-uri-dark "file://{path}"'
    ),
    "kde": "plasma-apply-wallpaperimage {path}",
    "xfce": (
        "xfconf-query -c xfce4-desktop "
        "-p /backdrop/screen0/monitor0/workspace0/last-image -s {path}"
    ),
}


def detect_desktop(environ=None):
    """Return a RECIPES key matching $XDG_CURRENT_DESKTOP (gnome/kde/xfce), or None.

    $XDG_CURRENT_DESKTOP can be colon-separated and vary in case (e.g. "ubuntu:GNOME",
    "KDE", "X-Cinnamon"), so match each token case-insensitively.
    """
    import os

    env = environ if environ is not None else os.environ
    tokens = env.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
    for key in RECIPES:
        if key in tokens:
            return key
    return None
