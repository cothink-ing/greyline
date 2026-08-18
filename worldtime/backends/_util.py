"""Shared helpers for backends."""

import re
import shutil
import subprocess


def xrandr_outputs():
    """Connected outputs via xrandr as [{name,width,height,scale}, ...], or []
    if xrandr is unavailable or nothing is connected.
    """
    if not shutil.which("xrandr"):
        return []
    raw = subprocess.run(["xrandr", "--query"], capture_output=True, text=True).stdout
    result = []
    for line in raw.splitlines():
        m = re.match(r"([\w.-]+)\s+connected.*?(\d+)x(\d+)\+\d+\+\d+", line)
        if m:
            result.append(
                {
                    "name": m.group(1),
                    "width": int(m.group(2)),
                    "height": int(m.group(3)),
                    "scale": 1.0,
                }
            )
    return result
