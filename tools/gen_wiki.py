#!/usr/bin/env python3
"""Generate the wiki's reference pages from `greyline help <topic>`.

The config keys, theme list, backend list and desktop recipes all already have a
single source of truth in the code — greyline/helptext.py renders them from
default-config.toml, themes/*.toml and recipes.RECIPES. Before 0.8 the README
kept a second, hand-maintained copy of each; this generates the web copy instead:

    python tools/gen_wiki.py            # write docs/wiki/*.md
    python tools/gen_wiki.py --check    # fail if they are stale

tests/test_wiki_docs.py runs --check, and .github/workflows/wiki.yml pushes
docs/wiki/ to the GitHub wiki, so the published pages cannot drift from the code.
Edit the source the page is generated from, not the page.

Three parts of the help output describe *this machine* rather than greyline, and
are normalised out: the absolute path of your config and theme directories, the
absolute path of the packaged theme dir, and the "Detected here:" line naming the
backend that happens to be running. Path separators are normalised too, so the
pages a Windows checkout generates match the ones in git.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "docs", "wiki")
WIKI = "https://github.com/cothink-ing/greyline/wiki"

CONFIGURATION_ADDENDUM = """\
## Precedence

A colour can be set in three places. The later one wins:

    theme file  <  [colors]  <  home.color

## Editing

`greyline config set` validates before it writes and preserves the file's comments
and layout, so the config stays readable after the CLI has been through it. A key
greyline does not read, a value of the wrong type, and a number outside its range
are all refused rather than saved:

    $ greyline config set them modus
    error: 'them' is not a greyline config key. Did you mean 'theme'?

Editing the file by hand is equally fine, and is checked on the way in. A key
greyline does not read is reported by `greyline doctor` and otherwise ignored, so a
setting left over from another version cannot stop your wallpaper; a key it *does*
read but cannot use is an error, because the alternative is a renderer that fails
once a minute without saying why.
"""

THEMES_ADDENDUM = """\
## Any other base16 scheme

greyline bundles the popular families; [tinted-theming/schemes][schemes] has
around 340. The script that generated the bundled palettes converts any of them,
and needs nothing but the standard library:

```sh
git clone --depth 1 https://github.com/tinted-theming/schemes /tmp/schemes
python tools/base16_to_theme.py /tmp/schemes/base16/ayu-dark.yaml \\
    --out ~/.config/greyline/themes
greyline config set theme ayu-dark
```

It maps base16's slots to greyline's map roles (the mapping is documented at the
top of the script) and follows the scheme's own `variant: light` for polarity, so
light schemes come out light: the terminator, label plates and grid flip with them.

[schemes]: https://github.com/tinted-theming/schemes
"""

DESKTOPS_ADDENDUM = """\
## This replaces your wallpaper

greyline is not a live-wallpaper engine and not an overlay. It renders a PNG and
sets it as the desktop wallpaper through the desktop's own tool, so you do not
need `swww` or any wallpaper daemon on GNOME. The last image stays after greyline
stops.

The recipes above are best-effort and community-verified: the maintainer runs
sway and cannot test them directly. If yours needs a tweak, please
[open a desktop-compatibility issue](https://github.com/cothink-ing/greyline/issues/new/choose).
"""

PAGES = [
    (
        "Configuration",
        "keys",
        "Every config key, its allowed values and its default, straight from the "
        "packaged `default-config.toml`.",
        CONFIGURATION_ADDENDUM,
    ),
    (
        "Themes",
        "themes",
        "The bundled palettes, the keys a theme file sets, and how to write your own.",
        THEMES_ADDENDUM,
    ),
    (
        "Backends",
        "backends",
        "How the rendered PNG reaches your desktop, and how greyline picks the way it does.",
        None,
    ),
    (
        "Desktop-environments",
        "desktops",
        "GNOME, KDE and XFCE manage their own wallpaper, so greyline drives them "
        "through a shell command.",
        DESKTOPS_ADDENDUM,
    ),
]


def _normalise(text, sentinel_config):
    """Strip everything that describes this machine rather than greyline."""
    out: list[str] = []
    for line in text.split("\n"):
        if line.startswith("Detected here:"):
            continue
        line = line.replace(sentinel_config, "~/.config")
        line = line.replace(ROOT + os.sep, "")
        if os.sep != "/":
            # The only backslashes a help page can contain are the ones os.path.join
            # just put there; the addenda, which do use them, are not passed through here.
            line = line.replace(os.sep, "/")
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def render_page(title, topic, blurb, addendum, helptext, sentinel_config):
    body = _normalise(helptext.render_topic(topic), sentinel_config)
    parts = [
        "<!-- GENERATED by tools/gen_wiki.py from `greyline help "
        f"{topic}` — do not edit this page.",
        "     Change the source it is generated from and re-run the generator. -->",
        "",
        f"# {title}",
        "",
        blurb,
        "",
        "The same page ships with greyline and always matches your installed version:",
        "",
        "```sh",
        f"greyline help {topic}",
        "```",
        "",
        "```",
        body,
        "```",
    ]
    if addendum:
        parts += ["", addendum.rstrip()]
    return "\n".join(parts) + "\n"


def render_all():
    """Render with a throwaway XDG_CONFIG_HOME so the output describes no machine.

    The help pages read the config and user-theme directories from the environment
    at call time, so pointing them at an empty temp dir both fixes the paths (which
    are then rewritten to ~/.config) and drops the "your themes" section, which
    would otherwise list whatever the person running the generator happens to have.
    """
    previous = os.environ.get("XDG_CONFIG_HOME")
    with tempfile.TemporaryDirectory() as sentinel:
        os.environ["XDG_CONFIG_HOME"] = sentinel
        try:
            from greyline import helptext

            return {
                title: render_page(title, topic, blurb, addendum, helptext, sentinel)
                for title, topic, blurb, addendum in PAGES
            }
        finally:
            if previous is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = previous


def main():
    pages = render_all()
    if "--check" in sys.argv:
        stale = []
        for title, text in pages.items():
            path = Path(OUT_DIR, f"{title}.md")
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(f"docs/wiki/{title}.md")
        if stale:
            print(
                f"stale, run tools/gen_wiki.py: {', '.join(stale)}",
                file=sys.stderr,
            )
            return 1
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    for title, text in pages.items():
        Path(OUT_DIR, f"{title}.md").write_text(text, encoding="utf-8")
        print(f"wrote docs/wiki/{title}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
