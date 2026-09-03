# Contributing to greyline

greyline is a personal project, built and maintained in spare time and released as free
software under GPL-2.0-or-later. Issues, desktop-compatibility recipes and pull requests
are all welcome.

## The most useful thing you can send

The maintainer runs sway on Wayland and cannot test GNOME, KDE or XFCE directly, so the
`command`-backend recipes for those desktops are verified entirely by users. If you run
one of them, a report saying the shipped recipe worked is as valuable as one saying it
did not.

[Open a desktop-compatibility issue](https://github.com/cothinking-dev/greyline/issues/new/choose);
there is a template for it. Include the output of `greyline doctor` and
`greyline --list-outputs`.

Bugs go through the same page. Anything reproducible with
`greyline --out /tmp/wt.png --res 2560x1440` is a rendering bug and needs no wallpaper
setup to investigate, so say if you tried that.

## Working on the code

```sh
nix develop           # or bring your own Python 3.11+ with pillow, tomlkit, pytest
pytest
ruff check . && ruff format .
mypy
```

`nix flake check` runs the tests, ruff and mypy together, which is exactly what CI runs.
Configuration for all three lives in `pyproject.toml`.

Documentation has generators, and they are gated by tests:

```sh
python tools/gen_wiki.py          # docs/wiki/*.md from `greyline help <topic>`
python tools/sync_web_themes.py   # web/themes.js from worldtime/themes/*.toml
```

## What a good change looks like

greyline optimises for universal compatibility, then performance and battery life, then
staying small. In that order. Four consequences, which between them explain most review
feedback:

**No daemon.** A tick renders a PNG, hands it to your existing wallpaper mechanism, and
the process ends. Nothing stays resident between ticks.

**No real-time updates or animation.** A clock accurate to the minute is the contract.
Per-second redraws would cost battery and buy nothing you can read.

**No unbounded files or caches.** Artifacts are bounded and self-managing. The KDE
refresh fix ping-pongs two fixed buffers rather than writing a new timestamped file every
minute, and that is the shape such a fix should take.

**Desktop quirks get solved at the edge.** Prefer a recipe or a command tweak, like
GNOME's empty-then-set, over a background service or a growing pile of workaround state.

When in doubt, a change should make greyline lighter, not heavier. The
[Road to v1](https://github.com/cothinking-dev/greyline/issues/10) tracker applies this
to specific work.

## Documentation

There are three places documentation lives, and only one of them is written by hand for
any given fact:

- **`worldtime/helptext.py`** is the source of truth for the config keys, the theme list,
  the backend list and the desktop recipes. Each is rendered from the data the renderer
  itself uses, so a `greyline help` page cannot describe a greyline that does not exist.
- **`docs/wiki/`** is the GitHub wiki. Four of its pages are generated from the help
  topics by `tools/gen_wiki.py` and carry a banner saying so; edit the source, run the
  generator, and commit the result. The rest are hand-written and can be edited directly.
  A workflow pushes the directory to the wiki on merge, so edits made in the wiki's own
  web editor will be overwritten.
- **`README.md`** is the pitch and the first five minutes. It should stay short enough to
  read in one screen and should not repeat anything the other two already say.

## Commits and pull requests

Conventional-ish subject lines (`fix:`, `feat:`, `docs:`, `chore:`), imperative mood.
User-visible changes get a `CHANGELOG.md` entry under `[Unreleased]`, in the style of the
entries already there: say what broke, why it broke, and what the fix does, rather than
naming the function that changed.
