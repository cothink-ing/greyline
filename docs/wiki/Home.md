# greyline

A world map on your desktop background, with clocks for your cities and a day/night
terminator that tracks the sun. A scheduler runs `greyline` once a minute; it renders a
PNG per output, hands each to your wallpaper mechanism, and exits. Nothing stays resident.

These pages are the long-form documentation. All of it also ships with greyline itself,
so `greyline help <topic>` answers the same questions offline, for the version you
actually have installed.

## Setting it up

- **[Installation](Installation)** — pipx, uv, Nix and home-manager, Windows and macOS,
  fonts, scheduling without systemd.
- **[Desktop environments](Desktop-environments)** — GNOME, KDE and XFCE.
- **[Backends](Backends)** — how the PNG reaches your desktop, and how one gets picked.

## Making it yours

- **[Configuration](Configuration)** — every key, its values and its default.
- **[Themes](Themes)** — the 35 bundled palettes, and how to write or convert one.

## When it goes wrong

- **[Troubleshooting](Troubleshooting)** — start with `greyline doctor`.

## How it's built

- **[Architecture](Architecture)** — what runs, in what order, and where each part lives.

Pages marked as generated are produced from the code by `tools/gen_wiki.py`. Edit the
source they are generated from, not the page.
