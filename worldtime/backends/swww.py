"""swww backend — any wlroots compositor (Hyprland, river, Wayfire, sway).

Requires a running swww daemon. swww gives buffered, flash-free wallpaper swaps
(unlike `swaymsg output bg`) and owns its own layer-shell surface, so a compositor
config reload does not disturb it.

Some nixpkgs revisions ship the binaries as `awww`/`awww-daemon` instead of
`swww`/`swww-daemon` (same 0.12 CLI). Both names are accepted, as is a `$SWWW`
environment override.
"""

import os
import re
import shutil
import subprocess

TRANSITION_ENV = "GREYLINE_SWWW_TRANSITION"
DEFAULT_TRANSITION = "fade"
DURATION_ENV = "GREYLINE_SWWW_DURATION"
DEFAULT_DURATION = "0.3"


def _client():
    return os.environ.get("SWWW") or shutil.which("swww") or shutil.which("awww")


def available():
    cli = _client()
    if not cli or not os.environ.get("WAYLAND_DISPLAY"):
        return False
    return subprocess.run([cli, "query"], capture_output=True).returncode == 0


def outputs():
    cli = _client()
    raw = subprocess.run([cli, "query"], capture_output=True, text=True, check=True).stdout
    result = []
    for line in raw.splitlines():
        m = re.search(r"([\w.-]+):\s*(\d+)x(\d+)", line)
        if not m:
            continue
        s = re.search(r"scale:\s*([\d.]+)", line)
        result.append(
            {
                "name": m.group(1),
                "width": int(m.group(2)),
                "height": int(m.group(3)),
                "scale": float(s.group(1)) if s else 1.0,
            }
        )
    return result


def apply(name, png_path):
    """Swap this output's wallpaper. A short crossfade by default — swww is buffered, so
    the transition is free and reads better than a hard cut once a minute. Set
    GREYLINE_SWWW_TRANSITION=none (and/or GREYLINE_SWWW_DURATION) for an instant swap."""
    cli = _client()
    transition = os.environ.get(TRANSITION_ENV) or DEFAULT_TRANSITION
    duration = os.environ.get(DURATION_ENV) or DEFAULT_DURATION
    subprocess.run(
        [
            cli,
            "img",
            "--outputs",
            name,
            "--transition-type",
            transition,
            "--transition-duration",
            duration,
            png_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
