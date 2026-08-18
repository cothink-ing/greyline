"""Sway / SwayFX backend — enumerate outputs and set wallpapers over the IPC.

Uses `swaymsg -t get_outputs` for native pixel sizes and `swaymsg output <name>
bg <png> fill` to swap the wallpaper live (no swaybg/swww daemon needed).

If $SWAYSOCK is not in the environment (e.g. a systemd user service that did not
inherit it), the socket is auto-discovered under $XDG_RUNTIME_DIR — so no extra env
wiring is required.
"""

import glob
import json
import os
import shutil
import subprocess


def _swaysock():
    s = os.environ.get("SWAYSOCK")
    if s and os.path.exists(s):
        return s
    rt = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    matches = sorted(glob.glob(os.path.join(rt, "sway-ipc.*.sock")))
    return matches[0] if matches else None


def available():
    return _swaysock() is not None and shutil.which("swaymsg") is not None


def _run(args):
    env = dict(os.environ)
    sock = _swaysock()
    if sock:
        env["SWAYSOCK"] = sock
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True, check=True, env=env)


def outputs():
    raw = _run(["-t", "get_outputs", "-r"]).stdout
    result = []
    for o in json.loads(raw):
        if not o.get("active", False):
            continue
        mode = o.get("current_mode") or {}
        scale = float(o.get("scale", 1.0) or 1.0)
        w = mode.get("width")
        h = mode.get("height")
        if not w or not h:  # fall back to logical rect * scale
            rect = o.get("rect", {})
            w = round(rect.get("width", 0) * scale)
            h = round(rect.get("height", 0) * scale)
        if w and h:
            result.append({"name": o["name"], "width": w, "height": h, "scale": scale})
    return result


def apply(name, png_path):
    _run(["output", name, "bg", png_path, "fill"])
