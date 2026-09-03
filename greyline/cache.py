"""Disk cache for the rendered vector map base.

greyline is a fresh process every minute, so nothing survives a tick in memory — but
the map itself does not change from tick to tick. Ocean, land, borders, the timezone
grid and the two filled zone columns are a pure function of output size, theme, label
font and home UTC offset; only the terminator and the clocks move. Rebuilding all of
it every minute cost 1.6s of a 3.2s tick at 4K, and the peak memory that goes with it,
on a project whose stated priorities put battery life second only to compatibility.

The cache is bounded the same way the wallpaper buffers are: `_MAX_ENTRIES` files,
oldest evicted on write. A miss, a corrupt file or a read-only cache directory is not
an error — it just means building the base, which is what happened before this existed.
The key carries the greyline version, so an upgrade that changes how the map is drawn
cannot serve a stale one.
"""

import contextlib
import hashlib
import json
import os
import tempfile

from PIL import Image

from . import __version__

# Bump when build_base's output changes in a way the inputs below do not capture.
_FORMAT = 1

# One entry per distinct output size in play, plus headroom for a theme change or a
# DST flip without thrashing. At most ~1.6 MB each on a 4K panel.
_MAX_ENTRIES = 6

_PREFIX = "base-"


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "greyline")


def key_for(size, theme, font_desc, home_offset):
    """A short stable digest of everything the base image depends on.

    The whole theme goes in rather than the eight colours the map happens to use
    today: over-invalidating costs one rebuild, under-invalidating shows the user a
    wallpaper that does not match their config.
    """
    payload = {
        "format": _FORMAT,
        "version": __version__,
        "size": list(size),
        "theme": {k: list(v) if isinstance(v, (tuple, list)) else v for k, v in theme.items()},
        "font": list(font_desc),
        "home_offset": home_offset,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _path(key):
    return os.path.join(cache_dir(), f"{_PREFIX}{key}.png")


def load(key):
    """The cached base for `key` as a fresh RGBA image, or None."""
    try:
        with Image.open(_path(key)) as im:
            im.load()
            return im.convert("RGBA")
    except (OSError, ValueError):
        return None


def _evict(directory):
    entries = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.startswith(_PREFIX) and f.endswith(".png")
    ]
    if len(entries) <= _MAX_ENTRIES:
        return
    entries.sort(key=os.path.getmtime, reverse=True)
    for stale in entries[_MAX_ENTRIES:]:
        with contextlib.suppress(OSError):
            os.remove(stale)


def store(key, image):
    """Write `image` under `key`, then evict the oldest entries over the cap.

    Written to a temporary file and renamed, so a tick that overlaps another (a manual
    run while the timer fires) can never leave a half-written PNG for the next one to
    read. Any failure here is swallowed: a cache that cannot be written is a slow
    render, not a broken one.
    """
    directory = cache_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".greyline-", suffix=".png")
        try:
            with os.fdopen(fd, "wb") as f:
                image.save(f, format="PNG", compress_level=1)
            os.replace(tmp, _path(key))
        except BaseException:
            with contextlib.suppress(OSError):
                os.remove(tmp)
            raise
        _evict(directory)
    except OSError:
        return


def clear():
    """Remove every cached base. Returns the number of files removed."""
    directory = cache_dir()
    if not os.path.isdir(directory):
        return 0
    removed = 0
    for name in os.listdir(directory):
        if name.startswith(_PREFIX) and name.endswith(".png"):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(directory, name))
                removed += 1
    return removed
