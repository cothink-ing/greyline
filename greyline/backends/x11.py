"""X11 backend — feh (preferred) or xwallpaper, single combined root image.

X11 has one root window, so per-output rendering isn't separable here; we report
the connected outputs for sizing but set them together via feh's per-output flags.
"""

import shutil
import subprocess

from . import _util


def _tool():
    return shutil.which("feh") or shutil.which("xwallpaper")


def available():
    import os

    return bool(os.environ.get("DISPLAY")) and _tool() is not None


def outputs():
    result = _util.xrandr_outputs()
    if not result:
        result.append({"name": "default", "width": 1920, "height": 1080, "scale": 1.0})
    return result


def apply(name, png_path):
    tool = _tool()
    if tool and tool.endswith("feh"):
        subprocess.run([tool, "--bg-fill", png_path], capture_output=True, text=True, check=True)
    elif tool:
        subprocess.run(
            [tool, "--output", name, "--zoom", png_path], capture_output=True, text=True, check=True
        )
