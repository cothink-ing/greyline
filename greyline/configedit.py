"""Comment-preserving edits to the user's config.toml, for `greyline config` /
`greyline city` / `greyline init`.

Reading stays on stdlib tomllib (config.py); writing goes through tomlkit so the
heavily-commented default template keeps its comments and layout across edits, and
so [[city]] arrays-of-tables are handled correctly. All config writes funnel through
here (one path).
"""

import os
import shutil
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tomlkit

from . import config, schema


def ensure_config(path=None):
    """Return the user config path, creating it from the packaged default if absent."""
    path = path or config.user_config_path()
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(config.DEFAULT_CONFIG, path)
    return path


def _load(path):
    with open(path, encoding="utf-8") as f:
        return tomlkit.parse(f.read())


def _save(path, doc):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".greyline-", suffix=".toml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _suggest(dotted):
    """' Did you mean X?' for a near-miss key, or ''. Typos are the common case here."""
    import difflib

    close = difflib.get_close_matches(dotted, sorted(schema.known_keys()), n=1)
    return f" Did you mean {close[0]!r}?" if close else ""


def set_key(path, dotted, raw_value):
    """Set a (possibly nested) dotted key, e.g. 'twilight.darkness' -> 'medium'.

    Unknown keys are refused rather than written: a key greyline never reads is
    always a mistake, and writing it silently is how "I set it and nothing
    happened" starts.
    """
    if dotted in schema.TABLE_KEYS:
        raise ValueError(f"{dotted!r} is managed by `greyline {dotted}` — see `greyline help city`")
    if schema.lookup(dotted) is None:
        raise ValueError(f"{dotted!r} is not a greyline config key.{_suggest(dotted)}")
    value = schema.coerce(dotted, raw_value)
    schema.validate(dotted, value)
    doc = _load(path)
    parts = dotted.split(".")
    node = doc
    for p in parts[:-1]:
        if p not in node or not isinstance(node[p], (dict, tomlkit.items.Table)):
            node[p] = tomlkit.table()
        node = node[p]
    node[parts[-1]] = value
    _save(path, doc)
    return value


def unset_key(path, dotted):
    """Remove a dotted key if present. Returns True if something was removed."""
    doc = _load(path)
    parts = dotted.split(".")
    node = doc
    for p in parts[:-1]:
        if not isinstance(node, (dict, tomlkit.items.Table)) or p not in node:
            return False
        node = node[p]
    if not isinstance(node, (dict, tomlkit.items.Table)) or parts[-1] not in node:
        return False
    del node[parts[-1]]
    _save(path, doc)
    return True


def get_key(path, dotted):
    """Return the value at a dotted key from the merged effective config, or None."""
    cfg = config.load(path)
    node = cfg
    for p in dotted.split("."):
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node


def list_cities(path):
    return config.load(path).get("city", [])


def add_city(path, name, lat, lon, tz, home=False, label_side=None):
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"{tz!r} is not a valid IANA timezone") from None
    doc = _load(path)
    if "city" not in doc:
        doc["city"] = tomlkit.aot()
    entry = tomlkit.table()
    entry["name"] = name
    entry["lat"] = float(lat)
    entry["lon"] = float(lon)
    entry["tz"] = tz
    if label_side:
        entry["label_side"] = label_side
    doc["city"].append(entry)
    if home:
        if "home" not in doc:
            doc["home"] = tomlkit.table()
        doc["home"]["tz"] = tz
    _save(path, doc)


def remove_city(path, name):
    """Remove cities matching name (case-insensitive). Returns the count removed."""
    doc = _load(path)
    cities = doc.get("city")
    if not cities:
        return 0
    keep = [c for c in cities if str(c.get("name", "")).lower() != name.lower()]
    removed = len(cities) - len(keep)
    if removed:
        new = tomlkit.aot()
        for c in keep:
            new.append(c)
        doc["city"] = new
    _save(path, doc)
    return removed
