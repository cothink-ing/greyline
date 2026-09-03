"""Configuration loading + system timezone detection (stdlib only: tomllib).

Merges the shipped default-config.toml with the user's
~/.config/greyline/config.toml (XDG-aware). Resolves the home timezone
("auto" => system tz) and flags the matching city as home.
"""

import os
import tomllib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import schema

_PKG_DIR = os.path.dirname(__file__)
DEFAULT_CONFIG = os.path.join(_PKG_DIR, "default-config.toml")


def _xdg_config_home():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def user_config_path():
    return os.path.join(_xdg_config_home(), "greyline", "config.toml")


def system_timezone():
    """Best-effort IANA name of the system timezone, or None.

    Order: $TZ, then the /etc/localtime symlink target (e.g. NixOS points it at
    .../zoneinfo/Asia/Kuala_Lumpur).
    """
    tz = os.environ.get("TZ")
    if tz:
        try:
            ZoneInfo(tz)
            return tz
        except (ZoneInfoNotFoundError, ValueError):
            pass
    try:
        target = os.path.realpath("/etc/localtime")
        marker = "/zoneinfo/"
        if marker in target:
            name = target.split(marker, 1)[1]
            ZoneInfo(name)
            return name
    except (OSError, ZoneInfoNotFoundError, ValueError):
        pass
    return None


def _deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def defaults():
    """The packaged defaults alone, with no user config merged."""
    with open(DEFAULT_CONFIG, "rb") as f:
        return tomllib.load(f)


def load(path=None):
    """Return the merged config dict, with home cities flagged.

    `path` overrides the user config location (else the XDG path is used if present).

    Raises ValueError if a key greyline reads holds a value it cannot use — a config
    file is also written by hand and by home-manager, so this is the only place such a
    value can be caught before it reaches the renderer as a traceback. Keys greyline
    does not read are ignored here and reported by `greyline doctor`; a stray key from
    another version must not take a working wallpaper down.
    """
    cfg = defaults()

    user_path = path or user_config_path()
    if os.path.isfile(user_path):
        with open(user_path, "rb") as f:
            user = tomllib.load(f)
        cities = user.pop("city", None)
        cfg = _deep_merge(cfg, user)
        if cities is not None:
            cfg["city"] = cities

    schema.check_config(cfg)

    home_tz = cfg.get("home", {}).get("tz", "auto")
    if home_tz == "auto":
        home_tz = system_timezone()
    for c in cfg.get("city", []):
        c["home"] = bool(home_tz) and c.get("tz") == home_tz

    return cfg
