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


def _client():
    return os.environ.get("SWWW") or shutil.which("swww") or shutil.which("awww")


def available():
    cli = _client()
    if not cli or not os.environ.get("WAYLAND_DISPLAY"):
        return False
    # `query` only succeeds when the daemon is running.
    return subprocess.run([cli, "query"], capture_output=True).returncode == 0


def outputs():
    cli = _client()
    raw = subprocess.run([cli, "query"], capture_output=True, text=True, check=True).stdout
    result = []
    # Lines look like "eDP-1: 1920x1200, scale: 1, ...". Some builds (the `awww` fork)
    # prefix the line with ": ", so search rather than anchor at the start.
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
    cli = _client()
    subprocess.run(
        [cli, "img", "--outputs", name, "--transition-type", "none", png_path],
        capture_output=True,
        text=True,
        check=True,
    )
