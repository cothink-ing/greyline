#!/usr/bin/env python3
"""Generate web/themes.js from worldtime/themes/*.toml.

The browser demo has to draw the same palettes as the renderer, and it can't read
TOML. Before 0.7 the dict was hand-ported and drifted; with three dozen themes that
stopped being an option, so it is generated:

    python tools/sync_web_themes.py

tests/test_web_themes.py fails if the checked-in file doesn't match, so the demo
can't silently fall behind a theme change.
"""

import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from worldtime import themes  # noqa: E402  (needs ROOT on the path first)

OUT = os.path.join(ROOT, "web", "themes.js")
FIRST = ["modus", "blue"]


def _js_color(value):
    rgb = themes._hex(value)
    return "[" + ",".join(str(c) for c in rgb) + "]" if rgb else None


def render_js():
    files = themes._scan(themes.BUILTIN_DIR)
    order = FIRST + [n for n in sorted(files) if n not in FIRST]

    lines = [
        "// Themes for the browser demo — GENERATED from worldtime/themes/*.toml by",
        "// tools/sync_web_themes.py. Do not edit; edit the TOML and re-run it.",
        "// Colours are [r,g,b] or [r,g,b,a] (a is 0-255); use rgba() to get a canvas string.",
        "",
        "export const THEMES = {",
    ]
    labels = {}
    for name in order:
        with open(files[name], "rb") as f:
            data = tomllib.load(f)
        labels[name] = data.get("name", name)
        entries = []
        for key in sorted(themes.COLOR_KEYS | themes.OPTIONAL_KEYS):
            if key not in data:
                continue
            if key == "night_alpha":
                entries.append(f"night_alpha: {int(data[key])}")
                continue
            color = _js_color(data[key])
            if color:
                entries.append(f"{key}: {color}")
        lines.append(f'  "{name}": {{ ' + ", ".join(entries) + " },")
    lines.append("};")
    lines.append("")
    lines.append("// Display names and the order the demo's theme picker lists them in.")
    lines.append(
        "export const THEME_LABELS = " + json.dumps(labels, ensure_ascii=False, indent=2) + ";"
    )
    lines.append("export const THEME_ORDER = " + json.dumps(order, indent=2) + ";")
    lines.append("")
    lines.append("// Names greyline has shipped in the past, kept working forever.")
    for alias, target in themes.ALIASES.items():
        lines.append(f'THEMES["{alias}"] = THEMES["{target}"];')
    return "\n".join(lines) + "\n"


def main():
    js = render_js()
    if "--check" in sys.argv:
        current = Path(OUT).read_text(encoding="utf-8") if os.path.exists(OUT) else ""
        if current != js:
            print("web/themes.js is stale — run tools/sync_web_themes.py", file=sys.stderr)
            return 1
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
